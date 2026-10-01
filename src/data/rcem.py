"""
RCEm — rynkowa miesięczna cena energii (PSE).

Źródło oficjalne: https://www.pse.pl/oire/rcem-rynkowa-miesieczna-cena-energii-elektrycznej
Tabela HTML (brak API) albo średnia z rce_prices. Cena za miesiąc M jest publikowana
11. dnia miesiąca M+1, także w weekend i święto. Korekta wygasa z końcem 12. miesiąca
po zakończeniu miesiąca, którego cena dotyczy.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Union
from urllib.request import Request, urlopen

import pandas as pd

DEFAULT_DB = 'data/energy_model.db'
SEED_PATH = Path(__file__).resolve().parents[2] / 'data' / 'rcem_pse_seed.json'
PSE_RCEM_URL = 'https://www.pse.pl/oire/rcem-rynkowa-miesieczna-cena-energii-elektrycznej'

_MONTHS_PL = {
    'styczeń': 1,
    'luty': 2,
    'marzec': 3,
    'kwiecień': 4,
    'maj': 5,
    'czerwiec': 6,
    'lipiec': 7,
    'sierpień': 8,
    'wrzesień': 9,
    'październik': 10,
    'listopad': 11,
    'grudzień': 12,
}

RCEM_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS rcem_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_month VARCHAR(7) NOT NULL,
    rce_pln_mwh REAL NOT NULL,
    rce_pln_kwh REAL NOT NULL,
    corrected_rce_pln_mwh REAL,
    corrected_rce_pln_kwh REAL,
    publication_date DATE,
    source VARCHAR(50) DEFAULT 'pse_seed',
    notes TEXT,
    UNIQUE(period_month, source)
);
CREATE INDEX IF NOT EXISTS idx_rcem_period ON rcem_prices(period_month);
'''


def ensure_rcem_table(conn: sqlite3.Connection) -> None:
    conn.executescript(RCEM_TABLE_SQL)
    conn.commit()


def _month_key(d: Union[str, pd.Timestamp]) -> str:
    ts = pd.Timestamp(d)
    return ts.strftime('%Y-%m')


def load_seed() -> dict:
    if not SEED_PATH.is_file():
        return {}
    with open(SEED_PATH, encoding='utf-8') as f:
        payload = json.load(f)
    return {k: v for k, v in payload.items() if k.startswith('20')}


def save_rcem_to_db(
    period_month: str,
    rce_pln_mwh: float,
    db_path: str = DEFAULT_DB,
    corrected_rce_pln_mwh: Optional[float] = None,
    publication_date: Optional[str] = None,
    source: str = 'pse_seed',
    notes: Optional[str] = None,
) -> None:
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    conn.execute(
        '''
        INSERT OR REPLACE INTO rcem_prices (
            period_month, rce_pln_mwh, rce_pln_kwh,
            corrected_rce_pln_mwh, corrected_rce_pln_kwh,
            publication_date, source, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            period_month,
            rce_pln_mwh,
            rce_pln_mwh / 1000.0,
            corrected_rce_pln_mwh,
            corrected_rce_pln_mwh / 1000.0 if corrected_rce_pln_mwh is not None else None,
            publication_date,
            source,
            notes,
        ),
    )
    conn.commit()
    conn.close()


def import_seed_to_db(db_path: str = DEFAULT_DB) -> int:
    """Importuje oficjalne RCEm z data/rcem_pse_seed.json."""
    seed = load_seed()
    for month, row in seed.items():
        save_rcem_to_db(
            month,
            row['rce_pln_mwh'],
            db_path=db_path,
            corrected_rce_pln_mwh=row.get('corrected_rce_pln_mwh'),
            source='pse_official',
            notes='PSE RCEm — publikacja pse.pl/oire/rcem',
        )
    return len(seed)


class RcEmNotPublished(RuntimeError):
    """11. dnia miesiąca tabela PSE nie zawiera jeszcze ceny za poprzedni miesiąc."""


class _RcemHtmlParser(HTMLParser):
    """Zbiera wiersze tabel z pse.pl (komórki mogą mieć zagnieżdżone span)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._depth = 0
        self._rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == 'table':
            self._depth += 1
            if self._depth == 1:
                self._rows = []
        elif self._depth and tag == 'tr':
            self._row = []
        elif self._depth and tag in ('td', 'th'):
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ('td', 'th') and self._in_cell:
            text = re.sub(r'\s+', ' ', ''.join(self._cell)).strip()
            self._row.append(text)
            self._in_cell = False
        elif tag == 'tr' and self._depth and self._row:
            self._rows.append(self._row)
            self._row = []
        elif tag == 'table' and self._depth:
            self._depth -= 1
            if self._depth == 0:
                self.tables.append(self._rows)

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data)


def _parse_price(text: str) -> Optional[float]:
    cleaned = text.replace('\xa0', '').replace(' ', '').strip()
    if cleaned in {'', '-', '–', '—'}:
        return None
    return float(cleaned.replace(',', '.'))


def _parse_pl_date(text: str) -> Optional[str]:
    cleaned = text.strip()
    if cleaned in {'', '-', '–', '—'}:
        return None
    return datetime.strptime(cleaned, '%d.%m.%Y').date().isoformat()


def _month_number(label: str) -> Optional[int]:
    name = label.lower().split('*')[0].strip()
    return _MONTHS_PL.get(name)


def parse_rcem_html(html: str) -> dict[str, dict]:
    """Tabela PSE → {YYYY-MM: cena, data publikacji, ostatnia korekta}.

    Gdy miesiąc ma kilka wierszy „skorygowana RCEm”, zostaje publikacja z najpóźniejszą datą.
    """
    parser = _RcemHtmlParser()
    parser.feed(html)
    parsed: dict[str, dict] = {}
    for table in parser.tables:
        year: Optional[int] = None
        month: Optional[int] = None
        for row in table:
            head = row[0] if row else ''
            if re.fullmatch(r'20\d\d', head):
                year = int(head)
                month = None
                continue
            month_no = _month_number(head)
            if month_no is not None and year is not None and len(row) == 1:
                month = month_no
                continue
            if year is None or month is None or len(row) < 3:
                continue
            key = f'{year:04d}-{month:02d}'
            label = head.lower()
            price = _parse_price(row[1])
            published = _parse_pl_date(row[2])
            if label.startswith('rcem') and 'skorygowana' not in label:
                if price is None:
                    continue
                slot = parsed.setdefault(key, {})
                slot['rce_pln_mwh'] = price
                slot['publication_date'] = published
                continue
            if 'skorygowana' not in label or price is None or published is None:
                continue
            slot = parsed.setdefault(key, {})
            previous = slot.get('corrected_publication_date')
            if previous is None or published >= previous:
                slot['corrected_rce_pln_mwh'] = price
                slot['corrected_publication_date'] = published
    return {k: v for k, v in parsed.items() if 'rce_pln_mwh' in v}


def fetch_rcem_html(url: str = PSE_RCEM_URL, timeout: int = 30) -> str:
    request = Request(url, headers={'User-Agent': 'smart-energy-model/rcem'})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or 'utf-8'
        return response.read().decode(charset, errors='replace')


def correction_window_open(period_month: str, as_of: date) -> bool:
    """Korekta RCEm jest dopuszczalna do końca 12. miesiąca po zakończeniu okresu."""
    period_end = pd.Timestamp(f'{period_month}-01') + pd.offsets.MonthEnd(0)
    expiry = period_end + pd.DateOffset(months=12) + pd.offsets.MonthEnd(0)
    return pd.Timestamp(as_of) <= expiry


def previous_calendar_month(as_of: date) -> str:
    previous = pd.Timestamp(as_of).replace(day=1) - pd.Timedelta(days=1)
    return previous.strftime('%Y-%m')


def sync_official_rcem(
    db_path: str = DEFAULT_DB,
    as_of: Optional[date] = None,
    html: Optional[str] = None,
) -> list[dict]:
    """Zapisuje do rcem_prices miesiące, dla których okno korekty jest jeszcze otwarte.

    11. dnia miesiąca wymaga ceny za poprzedni miesiąc — tego dnia PSE podaje ją oficjalnie.
    """
    today = as_of or date.today()
    page = html if html is not None else fetch_rcem_html()
    parsed = parse_rcem_html(page)
    if today.day == 11:
        expected = previous_calendar_month(today)
        if expected not in parsed:
            raise RcEmNotPublished(
                f'Brak RCEm za {expected} na stronie PSE ({PSE_RCEM_URL}). '
                'Publikacja przypada na 11. dzień miesiąca, także w weekend i święto.'
            )

    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    changes: list[dict] = []
    for period_month in sorted(parsed):
        if not correction_window_open(period_month, today):
            continue
        row = parsed[period_month]
        corrected = row.get('corrected_rce_pln_mwh')
        existing = conn.execute(
            '''
            SELECT rce_pln_mwh, corrected_rce_pln_mwh
            FROM rcem_prices
            WHERE period_month = ? AND source = 'pse_official'
            ''',
            (period_month,),
        ).fetchone()
        same_base = existing is not None and abs(float(existing[0]) - row['rce_pln_mwh']) < 0.001
        old_corr = None if existing is None or existing[1] is None else float(existing[1])
        same_corr = (old_corr is None and corrected is None) or (
            old_corr is not None and corrected is not None and abs(old_corr - corrected) < 0.001
        )
        action = 'unchanged' if same_base and same_corr else ('updated' if existing else 'inserted')
        if action != 'unchanged':
            notes = f"PSE RCEm, publikacja {row.get('publication_date') or '—'}"
            corr_date = row.get('corrected_publication_date')
            if corr_date:
                notes += f'; korekta {corr_date}'
            save_rcem_to_db(
                period_month,
                row['rce_pln_mwh'],
                db_path=db_path,
                corrected_rce_pln_mwh=corrected,
                publication_date=row.get('publication_date'),
                source='pse_official',
                notes=notes,
            )
        changes.append({
            'period_month': period_month,
            'rce_pln_mwh': row['rce_pln_mwh'],
            'corrected_rce_pln_mwh': corrected,
            'publication_date': row.get('publication_date'),
            'corrected_publication_date': row.get('corrected_publication_date'),
            'action': action,
        })
    conn.close()
    return changes


def compute_rcem_from_hourly(
    db_path: str,
    period_month: str,
) -> Optional[float]:
    """
    Średnia arytmetyczna kwadransowych RCE z rce_prices za dany miesiąc kalendarzowy.
    Przybliżenie oficjalnej RCEm (średnia ważona PSE).
    """
    start = f'{period_month}-01'
    end = (pd.Timestamp(start) + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            '''
            SELECT AVG(rce_pln_mwh), COUNT(*)
            FROM rce_prices
            WHERE business_date BETWEEN ? AND ?
            ''',
            (start, end),
        ).fetchone()
    except sqlite3.OperationalError:
        conn.close()
        return None
    conn.close()
    if not row or not row[0] or row[1] == 0:
        return None
    return round(float(row[0]), 2)


def update_rcem_from_hourly(db_path: str, start_month: str, end_month: str) -> int:
    """Oblicza RCEm z rce_prices i zapisuje jako source=computed_from_rce."""
    cur = pd.Timestamp(f'{start_month}-01')
    end = pd.Timestamp(f'{end_month}-01')
    n = 0
    while cur <= end:
        month = cur.strftime('%Y-%m')
        avg = compute_rcem_from_hourly(db_path, month)
        if avg is not None:
            save_rcem_to_db(
                month,
                avg,
                db_path=db_path,
                source='computed_from_rce',
                notes=f'Średnia z {month} kwadransów rce_prices',
            )
            n += 1
        cur += pd.offsets.MonthBegin(1)
    return n


def get_rcem(
    period_month: str,
    db_path: str = DEFAULT_DB,
    prefer: str = 'official',
    use_corrected: bool = True,
) -> Optional[dict]:
    """
    Zwraca RCEm dla YYYY-MM.

    prefer: 'official' | 'computed' | 'any'
    use_corrected: użyj skorygowanej RCEm jeśli dostępna (PSE).
    """
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    rows = pd.read_sql_query(
        '''
        SELECT period_month, rce_pln_mwh, rce_pln_kwh,
               corrected_rce_pln_mwh, corrected_rce_pln_kwh, source, notes
        FROM rcem_prices
        WHERE period_month = ?
        ORDER BY
            CASE source
                WHEN 'pse_official' THEN 0
                WHEN 'pse_seed' THEN 1
                WHEN 'computed_from_rce' THEN 2
                ELSE 3
            END
        ''',
        conn,
        params=(period_month,),
    )
    conn.close()

    if rows.empty and prefer != 'computed':
        seed = load_seed()
        if period_month in seed:
            entry = seed[period_month]
            mwh = entry.get('corrected_rce_pln_mwh') if use_corrected else None
            mwh = mwh or entry['rce_pln_mwh']
            return {
                'period_month': period_month,
                'rce_pln_mwh': mwh,
                'rce_pln_kwh': mwh / 1000.0,
                'source': 'pse_seed_file',
                'is_corrected': 'corrected_rce_pln_mwh' in entry and use_corrected,
            }
        if prefer == 'official':
            avg = compute_rcem_from_hourly(db_path, period_month)
            if avg is not None:
                return {
                    'period_month': period_month,
                    'rce_pln_mwh': avg,
                    'rce_pln_kwh': avg / 1000.0,
                    'source': 'computed_from_rce',
                    'is_corrected': False,
                }
        return None

    if prefer == 'computed':
        computed = rows[rows['source'] == 'computed_from_rce']
        if not computed.empty:
            rows = computed
        elif prefer == 'computed':
            avg = compute_rcem_from_hourly(db_path, period_month)
            if avg is not None:
                return {
                    'period_month': period_month,
                    'rce_pln_mwh': avg,
                    'rce_pln_kwh': avg / 1000.0,
                    'source': 'computed_from_rce',
                    'is_corrected': False,
                }

    row = rows.iloc[0]
    mwh = row['rce_pln_mwh']
    if use_corrected and pd.notna(row.get('corrected_rce_pln_mwh')):
        mwh = row['corrected_rce_pln_mwh']
    return {
        'period_month': period_month,
        'rce_pln_mwh': float(mwh),
        'rce_pln_kwh': float(mwh) / 1000.0,
        'source': row['source'],
        'is_corrected': use_corrected and pd.notna(row.get('corrected_rce_pln_mwh')),
    }


def list_rcem(db_path: str = DEFAULT_DB) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    ensure_rcem_table(conn)
    df = pd.read_sql_query(
        'SELECT * FROM rcem_prices ORDER BY period_month',
        conn,
    )
    conn.close()
    return df
