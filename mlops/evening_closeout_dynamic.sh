#!/usr/bin/env bash
# Dynamiczne domknięcie dnia — uruchamiane CZĘSTO (co ~10 min, launchd StartInterval),
# ale samo decyduje, kiedy faktycznie coś zrobić (evening_closeout.py --if-after-sunset).
#
# Zachód słońca w Polsce wędruje od ~15:45 (grudzień) do ~21:00 (czerwiec), więc stała
# godzina (dawniej 22:42) była często o kilka godzin PÓŹNIEJSZA niż potrzeba. Ten skrypt
# jest tani/no-op poza właściwym oknem (patrz evening_closeout.py), więc bezpiecznie
# można go odpalać co 10 minut przez cały dzień/wieczór.
#
# launchd (co EVENING_DYNAMIC_INTERVAL_S sekund, patrz plist):
#   pl.smart-energy-model.evening-dynamic
#
# Stary stały job o 22:42 (pl.smart-energy-model.evening) zostaje jako SIATKA
# BEZPIECZEŃSTWA — gdyby coś tu zawiodło (np. zegar/lokalizacja), i tak domknie dzień
# najpóźniej o 22:42 (record_evening_closeout jest idempotentne — nadpisuje wiersz dnia).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p "${PROJECT_ROOT}/logs"

# shellcheck source=/dev/null
source "${PROJECT_ROOT}/mlops/_venv.sh"

# Margines po zachodzie słońca — patrz decyzja w docs/ZADANIA_IMPLEMENTACJA_MOBILNA.md (T1.17):
# 30 min, nie 15 — bufor na resztkową produkcję o zmierzchu + opóźnienie sync FoxESS.
MARGIN_MINUTES="${EVENING_CLOSEOUT_MARGIN_MINUTES:-30}"

"$PYTHON" "${PROJECT_ROOT}/mlops/evening_closeout.py" --if-after-sunset "${MARGIN_MINUTES}"
