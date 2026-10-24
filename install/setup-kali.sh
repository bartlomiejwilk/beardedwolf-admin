#!/usr/bin/env bash
# BeardedWolf Admin: instalacja podstawowych narzedzi na Kali WSL.
# Skrypt nie importuje kluczy SSH, nie loguje do GitHub i nie zmienia BitLockera/UEFI.
set -Eeuo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
package_file="$script_dir/packages.txt"

if [[ ! -r "$package_file" ]]; then
  printf 'Brak listy pakietow: %s\n' "$package_file" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  printf 'Nie znaleziono /etc/os-release.\n' >&2
  exit 1
fi
. /etc/os-release
if [[ "$ID" != "kali" ]]; then
  printf 'Ten instalator jest przeznaczony dla Kali Linux; wykryto: %s\n' "$ID" >&2
  exit 1
fi

# Mapfile czyta tylko niepuste linie niebedace komentarzami.
mapfile -t packages < <(grep -Ev '^[[:space:]]*(#|$)' "$package_file")
if (( ${#packages[@]} == 0 )); then
  printf 'Lista pakietow jest pusta.\n' >&2
  exit 1
fi

printf '\nBeardedWolf Admin: podstawowa konfiguracja Kali\n'
printf 'Pakiety do sprawdzenia / zainstalowania: %s\n' "${packages[*]}"
printf '\nAPT moze poprosic o potwierdzenie instalacji.\n'
sudo apt-get update
sudo apt-get install "${packages[@]}"

mkdir -p "$HOME/beardedwolf/repos" "$HOME/beardedwolf/toolkit" "$HOME/beardedwolf/config"
chmod 700 "$HOME/beardedwolf/config"

printf '\nPodstawowa instalacja zakonczona.\n'
printf 'Repozytoria: %s\n' "$HOME/beardedwolf/repos"
printf 'GitHub CLI: '
if command -v gh >/dev/null 2>&1; then
  gh --version | head -n 1
else
  printf 'niezainstalowany; instrukcja: https://github.com/cli/cli/blob/trunk/docs/install_linux.md\n'
fi
printf 'Nie wykonano upgrade calego systemu, nie synchronizowano sekretow ani raportow.\n'
