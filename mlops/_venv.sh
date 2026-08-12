# Wspólne środowisko Python dla skryptów mlops/ i scripts/analysis/.
# Na macOS poza venv nie ma komendy `python` — zawsze używaj $PYTHON.
#
# Użycie (PROJECT_ROOT już ustawione):
#   # shellcheck source=/dev/null
#   source "${PROJECT_ROOT}/mlops/_venv.sh"
#
# Potem: "$PYTHON" mlops/sync_data.py …

if [[ -z "${PROJECT_ROOT:-}" ]]; then
  echo "❌ _venv.sh: ustaw PROJECT_ROOT przed source" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

PYTHON="${PROJECT_ROOT}/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "❌ Brak ${PYTHON}" >&2
  echo "   Uruchom: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# PATH: bare `python` działa też po activate / w subprocessach
export PATH="${PROJECT_ROOT}/venv/bin:${PATH}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/.env"
  set +a
fi
