#!/usr/bin/env bash
# Start BeardedWolf Admin through WSLg without depending on Win-KeX.
set -Eeuo pipefail
umask 077
repo="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
log_dir="$HOME/.cache/beardedwolf-admin"
mkdir -p "$log_dir"
chmod 700 "$log_dir"
log_file="$log_dir/gui-start.log"
: >> "$log_file"
chmod 600 "$log_file"
echo "[$(date -Is)] BeardedWolf Admin: start GUI" >> "$log_file"
python=""
for candidate in /usr/bin/python3.14 /usr/bin/python3 /usr/bin/python3.15 /usr/bin/python3.13; do
  if [[ -x "$candidate" ]] && "$candidate" -c 'import tkinter' >/dev/null 2>&1; then
    python="$candidate"
    break
  fi
done
if [[ -z "$python" ]]; then
  echo "Brak Python z Tkinter. Sprawdź install/setup-gui.sh."
  echo "Brak zgodnego Python/Tkinter" >> "$log_file"
  exit 1
fi
# Prefer Windows-integrated WSLg; Win-KeX stays separately available.
if [[ -S /mnt/wslg/.X11-unix/X0 ]]; then
  export DISPLAY=:0
elif [[ -z "${DISPLAY:-}" ]]; then
  echo "Brak DISPLAY. Uruchom WSLg lub pulpit Win-KeX."
  echo "Brak DISPLAY" >> "$log_file"
  exit 1
fi
if [[ ! -f "$repo/toolkit/bw_gui.py" ]]; then
  echo "Nie znaleziono aplikacji: $repo/toolkit/bw_gui.py"
  exit 1
fi
echo "Interpreter: $python; DISPLAY=${DISPLAY:-nieustawiony}" >> "$log_file"
if "$python" -u "$repo/toolkit/bw_gui.py" >> "$log_file" 2>&1; then
  echo "[$(date -Is)] Okno zamknięto." >> "$log_file"
else
  status=$?
  echo "BeardedWolf Admin nie uruchomił się (kod: $status)."
  echo "Log: $log_file"
  echo "[$(date -Is)] Błąd GUI: kod $status" >> "$log_file"
  exit "$status"
fi
