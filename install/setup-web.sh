#!/usr/bin/env bash
# BeardedWolf Admin - PHP, Composer, narzedzia WWW i zweryfikowany WP-CLI.
# Dziala lokalnie w Kali WSL. Nie laczy sie z serwerami i nie zmienia WordPressa.
set -Eeuo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
package_file="$script_dir/packages-web.txt"

if [[ ! -f /etc/os-release ]]; then
  printf 'Brak /etc/os-release.\n' >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != "kali" ]]; then
  printf 'Skrypt jest przeznaczony dla Kali Linux, wykryto: %s\n' "${ID:-unknown}" >&2
  exit 1
fi
if [[ ! -r "$package_file" ]]; then
  printf 'Brak pliku pakietow: %s\n' "$package_file" >&2
  exit 1
fi

mapfile -t packages < <(grep -Ev '^[[:space:]]*(#|$)' "$package_file")
if (("${#packages[@]}" == 0)); then
  printf 'Pusta lista pakietow.\n' >&2
  exit 1
fi

printf '\nBeardedWolf Admin: narzedzia WordPress i WWW\n'
printf 'Pakiety: %s\n' "${packages[*]}"
sudo apt-get update
sudo apt-get install "${packages[@]}"

# WP-CLI: weryfikacja podpisu GPG z przypietym odciskiem
# klucza wydan WP-CLI opublikowanym w oficjalnej dokumentacji.
expected_fpr="63AF7AA15067C05616FDDD88A3A2E8F226F0BC06"
wp_path="$HOME/.local/bin/wp"
if [[ -x "$wp_path" ]]; then
  printf '\nWP-CLI istnieje: %s (bez nadpisywania)\n' "$wp_path"
else
  tmpdir="$(mktemp -d)"
  trap 'rm -rf -- "$tmpdir"' EXIT
  mkdir -m 700 "$tmpdir/gnupg"
  base="https://raw.githubusercontent.com/wp-cli/builds/gh-pages"

  curl -fLsS --retry 3 "$base/phar/wp-cli.phar" -o "$tmpdir/wp-cli.phar"
  curl -fLsS --retry 3 "$base/phar/wp-cli.phar.asc" -o "$tmpdir/wp-cli.phar.asc"
  curl -fLsS --retry 3 "$base/wp-cli.pgp" -o "$tmpdir/wp-cli.pgp"

  actual_fpr="$(gpg --homedir "$tmpdir/gnupg" \
    --with-colons --import-options show-only --import "$tmpdir/wp-cli.pgp" 2>/dev/null |
    awk -F: '$1=="fpr" {print $10; exit}')"
  if [[ "$actual_fpr" != "$expected_fpr" ]]; then
    printf 'Nieprawidlowy odcisk klucza WP-CLI: %s\n' "$actual_fpr" >&2
    exit 1
  fi
  gpg --homedir "$tmpdir/gnupg" --batch --import "$tmpdir/wp-cli.pgp"
  gpg --homedir "$tmpdir/gnupg" --batch --verify "$tmpdir/wp-cli.phar.asc" "$tmpdir/wp-cli.phar"
  php "$tmpdir/wp-cli.phar" --info >/dev/null
  install -Dm755 "$tmpdir/wp-cli.phar" "$wp_path"
  printf 'WP-CLI zweryfikowany i zainstalowany: %s\n' "$wp_path"
fi

printf '\nWersje narzedzi:\n'
php --version | head -n 1
composer --version | head -n 1
"$wp_path" --info | grep -E 'PHP version:|WP-CLI version:' || true

if ! command -v wp >/dev/null 2>&1; then
  printf '\nAby wywolywac wp bez pelnej sciezki w tej sesji:\n'
  printf 'export PATH="$HOME/.local/bin:$PATH"\n'
fi
printf '\nZakonczono. Nie wykonywano skanowania ani zmian w zdalnych serwerach.\n'
