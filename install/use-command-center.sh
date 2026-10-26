#!/usr/bin/env bash
# Switch the existing Kali desktop icon to BeardedWolf Operations Center.
# Local-only: no apt upgrade, no changes to SSH credentials or Syncthing.
set -Eeuo pipefail
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
[[ -f "$root/toolkit/bw_launcher.py" && -f "$root/toolkit/bw_console.py" ]] || {
  echo "Brak modulu centrum dowodzenia. Najpierw git pull." >&2
  exit 1
}
python=""
for executable in /usr/bin/python3.14 /usr/bin/python3.15 /usr/bin/python3 /usr/bin/python3.13; do
  if [[ -x "$executable" ]] && "$executable" -c 'import tkinter' >/dev/null 2>&1; then
    python="$executable"
    break
  fi
done
[[ -n "$python" ]] || { echo "Brak interpretera Python z Tkinter." >&2; exit 1; }
"$python" -m py_compile "$root/toolkit/bw_launcher.py" "$root/toolkit/bw_console.py" "$root/toolkit/bw_theme.py" "$root/toolkit/bw_overview.py" "$root/toolkit/bw_paths.py" "$root/toolkit/bw_access.py" "$root/toolkit/bw_ops_access.py" "$root/toolkit/bw_ops_paths.py" "$root/toolkit/bw_ops_saved.py" "$root/toolkit/bw_windows_saved.py"
folder="$HOME/.local/share/applications"
mkdir -p "$folder"
shortcut="$folder/beardedwolf-admin.desktop"
if [[ -f "$shortcut" ]]; then
  cp -p "$shortcut" "$folder/beardedwolf-admin.before-console.bak"
fi
cat > "$shortcut" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BeardedWolf Operations Center
GenericName=Centrum monitorowania serwisow i infrastruktury
Comment=Monitoring WWW, TLS, WordPress, SSH i rejestr infrastruktury
Exec=$python $root/toolkit/bw_launcher.py
TryExec=$python
Icon=network-server
Terminal=false
StartupNotify=true
Categories=Network;System;Utility;
EOF
chmod 755 "$shortcut"
desktop="$HOME/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
  found="$(xdg-user-dir DESKTOP)"
  [[ -n "$found" && "$found" != "$HOME" ]] && desktop="$found"
fi
mkdir -p "$desktop"
cp "$shortcut" "$desktop/BeardedWolf Admin.desktop"
chmod 755 "$desktop/BeardedWolf Admin.desktop"
gio set "$desktop/BeardedWolf Admin.desktop" metadata::trusted true >/dev/null 2>&1 || true
echo "Gotowe. Otworz z pulpitu Kali: BeardedWolf Admin."
echo "Wersja python: $python. Dane Syncthing i SSH pozostaly bez zmian."
