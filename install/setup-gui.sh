#!/usr/bin/env bash
# Instaluje graficzny panel BeardedWolf Admin (Kali WSL 2 + XFCE).
set -Eeuo pipefail

if [[ ! -f /etc/os-release ]]; then
  echo "Brak identyfikacji systemu." >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "kali" ]]; then
  echo "Ten instalator obsluguje Kali Linux." >&2
  exit 1
fi

repo="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
[[ -f "$repo/toolkit/bw_gui.py" && -f "$repo/toolkit/bw_servers.py" ]] || {
  echo "Brakuje plikow panelu GUI." >&2
  exit 1
}

sudo apt-get update
sudo apt-get install -y python3-tk keychain xdg-utils xfce4-terminal openssh-client

# Uzywamy systemowego Pythona (z pakietami apt), nie binarnego z PATH
# (np. /usr/local/bin/python3 lub srodowiska wirtualnego).
PYTHON=/usr/bin/python3
if ! "$PYTHON" -c 'import tkinter; print("Tkinter jest dostepny:", tkinter.TkVersion)'; then
  echo "Nie udalo sie zaladowac tkinter z systemowego Pythona." >&2
  echo "Python w PATH: $(command -v python3 || true)" >&2
  echo "Python systemowy: $("$PYTHON" --version 2>&1)" >&2
  dpkg-query -W python3-tk >&2 || true
  exit 1
fi

cache_dir="$HOME/.cache/beardedwolf-admin/pycache"
mkdir -p "$cache_dir"
PYTHONPYCACHEPREFIX="$cache_dir" "$PYTHON" -m py_compile \
  "$repo/toolkit/bw" "$repo/toolkit/bw_gui.py" "$repo/toolkit/bw_servers.py"
echo "Sprawdzono skladnie Python."

app_dir="$HOME/.local/share/applications"
mkdir -p "$app_dir"
shortcut="$app_dir/beardedwolf-admin.desktop"

cat > "$shortcut" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BeardedWolf Admin
GenericName=Panel diagnostyczny i SSH
Comment=Testy DNS, TLS i WWW oraz bezpieczne polaczenia SSH
Exec=/usr/bin/python3 $repo/toolkit/bw_gui.py
TryExec=/usr/bin/python3
Icon=utilities-system-monitor
Terminal=false
StartupNotify=true
Categories=Network;System;Utility;
EOF
chmod 755 "$shortcut"
echo "Dodano do menu aplikacji Kali: $shortcut"

desktop="$HOME/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
  candidate="$(xdg-user-dir DESKTOP)"
  [[ -n "$candidate" && "$candidate" != "$HOME" ]] && desktop="$candidate"
fi
mkdir -p "$desktop"
desktop_shortcut="$desktop/BeardedWolf Admin.desktop"
cp -- "$shortcut" "$desktop_shortcut"
chmod 755 "$desktop_shortcut"
# Xfce/GIO moze wymagac osobnego zaufania przy pierwszym uruchomieniu.
if command -v gio >/dev/null 2>&1; then
  gio set "$desktop_shortcut" metadata::trusted true >/dev/null 2>&1 || true
fi

printf '\nGotowe. Ikona na pulpicie Kali: %s\n' "$desktop_shortcut"
printf 'Mozesz uruchomic bez pulpitu klikajac wpis w menu aplikacji XFCE.\n'
printf 'Test w terminalu sesji graficznej: /usr/bin/python3 %s/toolkit/bw_gui.py\n' "$repo"
printf 'Wszystkie profile i klucze SSH zostaja w katalogu domowym, poza repozytorium.\n'
