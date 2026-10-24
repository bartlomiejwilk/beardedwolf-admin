# BeardedWolf Linux Admin 🐺

Prywatne repozytorium narzedzi i konfiguracji do pracy na **dwoch prywatnych komputerach z Windows + Kali WSL 2**. Zawiera jedynie kod, listy pakietow, dokumentacje i szablony bez sekretow.

## Zawartosc

- [install/packages.txt](install/packages.txt) - sprawdzony zestaw podstawowych pakietow Kali.
- [install/setup-kali.sh](install/setup-kali.sh) - instalator podstawowy, ktory mozna uruchamiac wielokrotnie. Nie wykonuje pelnego upgrade Kali.
- [docs/synchronizacja.md](docs/synchronizacja.md) - plan synchronizacji kodu przez GitHub, raportow przez Syncthing i backupow przez Restic.
- [.gitignore](.gitignore) - podstawowe zabezpieczenie przed przypadkowym dodaniem plikow poufnych. Nie stanowi gwarancji.

## Na Lenovo (istniejace Kali WSL)

Po zmianach w repozytorium:

```bash
cd ~/beardedwolf/repos/beardedwolf-admin
git pull --ff-only
bash -n install/setup-kali.sh
bash install/setup-kali.sh
```

Ostatnie polecenie moze poprosic o haslo sudo i potwierdzenie pakietow. Jesli chcesz jedynie sprawdzic aktualizacje bez instalacji, pomin ostatnia linie.

## Na drugim komputerze

1. Sprawdz ochrone BitLocker i mozliwosc uruchamiania WSL 2; przy zmianach ustawien UEFI zabezpiecz klucz odzyskiwania.
2. Zainstaluj Kali w WSL 2 i utworz wlasne konto uzytkownika.
3. Skonfiguruj **osobny** klucz SSH, dodaj jego klucz publiczny do GitHuba, przetestuj `ssh -T git@github.com`.
4. W Kali zainstaluj `git`, sklonuj repozytorium pod `~/beardedwolf/repos/beardedwolf-admin`.
5. Wykonaj instalator zgodnie z sekcja wyzej.
6. Synchronizacje raportow skonfiguruj osobno w Windows zgodnie z dokumentacja. Nie synchronizuj wirtualnego dysku WSL.

## Zakres i bezpieczenstwo

**GitHub nie synchronizuje automatycznie niezatwierdzonych zmian lokalnych.** Na pierwszym komputerze wykonaj commit i push, a na drugim pull. Nie kopiuj calej dystrybucji WSL jako sposobu codziennej synchronizacji.

Klucze SSH, token GitHub CLI (zwlaszcza `~/.config/gh/hosts.yml`), pliki .env, hasla, zrzuty baz, materialy dowodowe i raporty poufne nie trafiaja do repozytorium. Kazdy komputer przechowuje swoje sekrety oddzielnie; glownym sejfem pozostaje Bitwarden.

Konfiguracja Syncthing/Restic i kopii USB nie zostala jeszcze wdrozona; dokumentacja opisuje plan, nie stan dzialajacej uslugi.

## Modul WordPress / WWW

Po skonfigurowaniu podstawowego Kali (na kazdym komputerze):

```bash
cd ~/beardedwolf/repos/beardedwolf-admin
git pull --ff-only
bash -n install/setup-web.sh
bash install/setup-web.sh
```

Modul instaluje PHP CLI i typowe rozszerzenia, Composer, klienta MariaDB, OpenSSL i `xmllint` z repozytoriow Kali. Nastepnie pobiera WP-CLI w postaci PHAR, weryfikuje jego podpis GPG i sprawdza publiczny klucz po oficjalnym odcisku WP-CLI (63AF7AA15067C05616FDDD88A3A2E8F226F0BC06). WP-CLI trafia do `~/.local/bin/wp`. Jesli w terminalu nie dziala sama komenda `wp`, wywolaj `~/.local/bin/wp --info` lub ustaw PATH dla biezacej sesji: `export PATH="$HOME/.local/bin:$PATH"`.

Skrypt nie skanuje domen ani serwerow, nie loguje przez SSH i nie zmienia zdalnych WordPressow. Zainstalowane narzedzie WP-CLI nie daje automatycznie dostepu do instalacji WordPress na OVH: konieczne sa wlasciwe uprawnienia, konfiguracja SSH i narzedzia po stronie serwera. WP-CLI w tym module nie aktualizuje sie automatycznie przy ponownym wykonaniu skryptu.

Dane poufne, logi i raporty nie trafiaja do GitHub. Raporty nalezy osobno eksportowac do synchronizowanego katalogu Windows, z wyjatkiem materialow, na ktorych synchronizacje nie masz uprawnienia.

## Polecenie `bw`: diagnostyka i raporty

Pierwsza wersja narzedzia: [docs/bw.md](docs/bw.md). Po `git pull --ff-only` wykonaj `bash install/setup-toolkit.sh` i `~/.local/bin/bw doctor`. Dostepne kontrole: `bw dns <domena>` oraz `bw tls <domena>` z raportami HTML. Eksport do Syncthing wymaga **jawnego** `--sync`.
