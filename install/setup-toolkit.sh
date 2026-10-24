#!/usr/bin/env bash
# BeardedWolf Admin: instalacja lokalnego polecenia bw bez praw roota.
set -Eeuo pipefail
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
source="$repo_root/toolkit/bw"
target="$HOME/.local/bin/bw"
if [[ ! -f "$source" ]]; then
  printf 'Brak pliku: %s\n' "$source" >&2
  exit 1
fi
if [[ -e "$target" || -L "$target" ]]; then
  if [[ ! -L "$target" || "$(readlink -f -- "$target")" != "$(readlink -f -- "$source")" ]]; then
    printf 'Istniejacy plik %s nie nalezy do tego repozytorium; nie nadpisuje.\n' "$target" >&2
    exit 1
  fi
fi
mkdir -p "$HOME/.local/bin"
chmod 755 "$source"
ln -sfn -- "$source" "$target"
printf 'Zainstalowano: %s -> %s\n' "$target" "$source"
if ! command -v bw >/dev/null 2>&1; then
  printf 'W tej sesji uzywaj: %s doctor\n' "$target"
fi
