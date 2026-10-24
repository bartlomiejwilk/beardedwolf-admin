#!/usr/bin/env bash
# BeardedWolf Admin: lokalny wrapper bw bez zmiany praw plikow sledzonych przez Git.
set -Eeuo pipefail
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
source="$repo_root/toolkit/bw"
target="$HOME/.local/bin/bw"
if [[ ! -f "$source" ]]; then
  printf 'Brak pliku: %s\n' "$source" >&2
  exit 1
fi
if [[ -L "$target" ]]; then
  # Migrate only our own symlink from previous installer releases.
  if [[ "$(readlink -f -- "$target")" != "$(readlink -f -- "$source")" ]]; then
    printf 'Istniejacy link %s wskazuje inny program; nie nadpisuje.\n' "$target" >&2
    exit 1
  fi
elif [[ -e "$target" ]]; then
  printf 'Plik %s juz istnieje; nie nadpisuje cudzej konfiguracji.\n' "$target" >&2
  exit 1
fi

mkdir -p "$HOME/.local/bin"
tmp="$(mktemp "$HOME/.local/bin/.bw-launch-XXXXXXXX")"
trap 'rm -f -- "$tmp"' EXIT
printf '#!/usr/bin/env bash\nexec /usr/bin/python3 %q "$@"\n' "$source" > "$tmp"
chmod 755 "$tmp"
mv -f -- "$tmp" "$target"
printf 'Zainstalowano lokalny launcher: %s\n' "$target"
printf 'Nie modyfikowano uprawnien pliku %s\n' "$source"
if ! command -v bw >/dev/null 2>&1; then
  printf 'Aby uzyc komendy bw, dodaj ~/.local/bin do PATH lub uruchom: %s doctor\n' "$target"
fi
