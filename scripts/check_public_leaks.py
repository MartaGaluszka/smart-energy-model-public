#!/usr/bin/env python3
"""Guard przed wyciekiem danych do publicznego repo (smart-energy-model-public).

Tryby:
  --staged            skanuje DODANE linie w git index (hook pre-commit)
  --outgoing          skanuje to, co wychodzi na remote (hook pre-push, czyta stdin gita)
  --history           audyt całej historii wszystkich gałęzi (dodane linie + komunikaty)
  --tracked           skanuje wszystkie śledzone pliki tekstowe (HEAD)
  --install-hook      wersjonowane hooki w .githooks/ + core.hooksPath (pre-commit, pre-push)
  --repo PATH         repo do skanowania (domyślnie: bieżący katalog)

Wychodzi kodem 1, gdy coś znajdzie. Nie czyta .env — działa wyłącznie na wzorcach.
Zakazane w public: ścieżki lokalne, dokładne GPS, IP lokalne, sekrety,
linki do prywatnych notatek, zakazane pliki. Dozwolone: współrzędne miasta
(Kraków-Obserwatorium) — lista ALLOWED_COORDS.

Po świeżym klonie repo publicznego:
  python3 scripts/check_public_leaks.py --install-hook
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SELF = 'scripts/check_public_leaks.py'

# Współrzędne miasta (Kraków-Obserwatorium) są jawne i dozwolone.
ALLOWED_COORDS = {'50.06', '50.0647', '19.94', '19.9450', '19.945'}

# Całe słowa / zapisy współrzędnych — nie luźne "lat"/"lon"/"GPS" w prozie (daty dd.mm!).
COORD_CONTEXT = re.compile(
    r'\b(?:lat|lon|lng|latitude|longitude)\b|WEATHER_(?:LAT|LON)|°\s*[NE]\b',
    re.IGNORECASE,
)
COORD_VALUE = re.compile(r'(?<![\d.])((?:49|50|19|20)\.\d{2,})(?!\d)')

RULES: list[tuple[str, re.Pattern[str]]] = [
    ('ścieżka lokalna /Users/<nazwa>', re.compile(r'/Users/(?!<user>|\.\.\.)[A-Za-z0-9_.-]+')),
    ('IP lokalne 192.168.x.x', re.compile(r'\b192\.168\.\d{1,3}\.\d{1,3}\b')),
    (
        'link do prywatnej notatki (paper-trade / RCB)',
        re.compile(r'\]\([^)]*(?:PAPER_TRADE|paper_trade|RCB_ALERTS)[^)]*\)'),
    ),
    (
        'sekret (klucz/token/hasło z wartością)',
        re.compile(
            r'(?i)\b(?:api[_-]?key|secret|passw(?:or)?d|token)\b\s*[:=]\s*["\']?'
            r'(?![A-Za-z_]*\()[A-Za-z0-9+/_-]{20,}'
        ),
    ),
]

FORBIDDEN_PATH = re.compile(
    r'(^|/)(\.env|\.cursor/.*|.*\.joblib|.*\.pem|.*\.key|credentials.*'
    r'|NOTATKA_PAPER_TRADE.*|NOTATKA_RCB.*|paper_trade.*|paper_trade_accu.*)$'
)
ALLOWED_PATH = re.compile(r'(^|/)\.env\.example$')

TEXT_SKIP = re.compile(r'\.(png|jpe?g|gif|ico|pdf|parquet|xlsx?|pkl|zip|gz|woff2?)$', re.I)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ['git', *args], cwd=repo, capture_output=True, text=True, errors='ignore', check=True
    ).stdout


def check_line(line: str) -> list[str]:
    found = [name for name, rx in RULES if rx.search(line)]
    if COORD_CONTEXT.search(line):
        for m in COORD_VALUE.finditer(line):
            if m.group(1) not in ALLOWED_COORDS:
                found.append(f'dokładne GPS ({m.group(1)})')
                break
    return found


def scan_staged(repo: Path) -> list[str]:
    problems: list[str] = []
    for path in git(repo, 'diff', '--cached', '--name-only', '--diff-filter=AM').split('\n'):
        if path and FORBIDDEN_PATH.search(path) and not ALLOWED_PATH.search(path):
            problems.append(f'{path}: zakazany plik w public')
    cur = None
    for raw in git(repo, 'diff', '--cached', '-U0', '--no-color', '--text').split('\n'):
        if raw.startswith('+++ b/'):
            cur = raw[6:]
        elif raw.startswith('+') and not raw.startswith('+++') and cur and cur != SELF:
            for what in check_line(raw[1:]):
                problems.append(f'{cur}: {what}: {raw[1:].strip()[:110]}')
    return problems


def scan_tracked(repo: Path) -> list[str]:
    problems: list[str] = []
    for path in git(repo, 'ls-files').split('\n'):
        if not path or path == SELF:
            continue
        if FORBIDDEN_PATH.search(path) and not ALLOWED_PATH.search(path):
            problems.append(f'{path}: zakazany plik w public')
            continue
        if TEXT_SKIP.search(path):
            continue
        try:
            text = (repo / path).read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for i, line in enumerate(text.split('\n'), 1):
            for what in check_line(line):
                problems.append(f'{path}:{i}: {what}: {line.strip()[:110]}')
    return problems


ZERO_SHA = '0' * 40


def scan_log(repo: Path, rev_args: list[str]) -> list[str]:
    """Skanuje DODANE linie, zakazane ścieżki i komunikaty commitów w podanych rewizjach."""
    problems: list[str] = []
    text = git(
        repo, 'log', *rev_args, '-p', '-U0', '--no-color', '--text', '--no-renames',
        '--format=@@COMMIT %h %s',
    )
    commit = '?'
    cur: str | None = None
    for raw in text.split('\n'):
        if raw.startswith('@@COMMIT '):
            commit = raw[9:]
            cur = None
            short = commit.split(' ', 1)
            for what in check_line(commit):
                problems.append(f'{short[0]} (komunikat): {what}: {commit[:110]}')
        elif raw.startswith('+++ b/'):
            cur = raw[6:]
            if FORBIDDEN_PATH.search(cur) and not ALLOWED_PATH.search(cur):
                problems.append(f'{commit.split(" ", 1)[0]} {cur}: zakazany plik w public')
        elif raw.startswith('+') and not raw.startswith('+++') and cur and cur != SELF:
            for what in check_line(raw[1:]):
                problems.append(f'{commit.split(" ", 1)[0]} {cur}: {what}: {raw[1:].strip()[:110]}')
    return problems


def scan_outgoing(repo: Path, stdin_lines: list[str]) -> list[str]:
    """pre-push: stdin = '<local ref> <local sha> <remote ref> <remote sha>' na wiersz."""
    problems: list[str] = []
    for line in stdin_lines:
        parts = line.split()
        if len(parts) != 4:
            continue
        _lref, local, _rref, remote = parts
        if local == ZERO_SHA:  # usuwanie gałęzi
            continue
        have_remote = remote != ZERO_SHA and subprocess.run(
            ['git', 'cat-file', '-e', f'{remote}^{{commit}}'], cwd=repo, capture_output=True
        ).returncode == 0
        if have_remote:
            revs = [f'{remote}..{local}']
        else:  # nowa gałąź lub force-push z nieznanym SHA: wszystko, czego nie ma na żadnym remote
            revs = [local, '--not', '--remotes']
        problems += scan_log(repo, revs)
    return problems


def install_hook(repo: Path) -> None:
    """Wersjonowane hooki w .githooks/ + core.hooksPath (działa w każdym klonie po instalacji)."""
    hooks = repo / '.githooks'
    hooks.mkdir(exist_ok=True)
    guard = '"$(git rev-parse --show-toplevel)/scripts/check_public_leaks.py"'
    (hooks / 'pre-commit').write_text(
        '#!/usr/bin/env bash\n'
        '# Guard: blokuje commit z danymi lokalnymi/prywatnymi (public repo).\n'
        f'exec python3 {guard} --staged\n'
    )
    (hooks / 'pre-push').write_text(
        '#!/usr/bin/env bash\n'
        '# Guard: skanuje wszystko, co wychodzi na remote (dodane linie, pliki, komunikaty).\n'
        f'exec python3 {guard} --outgoing\n'
    )
    for h in ('pre-commit', 'pre-push'):
        (hooks / h).chmod(0o755)
    subprocess.run(['git', 'config', 'core.hooksPath', '.githooks'], cwd=repo, check=True)
    legacy = repo / '.git' / 'hooks' / 'pre-commit'
    if legacy.exists() and 'check_public_leaks' in legacy.read_text(errors='ignore'):
        legacy.unlink()
    print(f'Zainstalowano hooki: {hooks}/pre-commit, pre-push (core.hooksPath=.githooks)')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('--repo', type=Path, default=Path('.'))
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--staged', action='store_true', help='dodane linie w indexie (pre-commit)')
    mode.add_argument('--outgoing', action='store_true', help='to, co wychodzi (pre-push, czyta stdin)')
    mode.add_argument('--history', action='store_true', help='cała historia wszystkich gałęzi')
    mode.add_argument('--tracked', action='store_true', help='wszystkie śledzone pliki (HEAD)')
    mode.add_argument('--install-hook', action='store_true', help='zainstaluj .githooks + hooksPath')
    args = ap.parse_args()
    repo = args.repo.resolve()

    if args.install_hook:
        install_hook(repo)
        return 0

    if args.staged:
        problems = scan_staged(repo)
    elif args.outgoing:
        problems = scan_outgoing(repo, sys.stdin.read().splitlines())
    elif args.history:
        problems = scan_log(repo, ['--all'])
    else:
        problems = scan_tracked(repo)

    if problems:
        print(f'❌ Guard public-leaks: {len(problems)} problem(ów)', file=sys.stderr)
        for p in problems[:60]:
            print('  •', p, file=sys.stderr)
        if len(problems) > 60:
            print(f'  … i {len(problems) - 60} więcej', file=sys.stderr)
        return 1
    print('✓ Guard public-leaks: czysto')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
