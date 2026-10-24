# Polecenie bw - pierwsza wersja

Narzędzie do nieinwazyjnych kontroli publicznych danych DNS i połączenia TLS z tworzeniem raportów HTML. Nie skanuje portów, nie wykorzystuje podatności, nie zmienia WordPressa ani konfiguracji serwerów.

## Instalacja (Kali WSL 2, oddzielnie na każdym komputerze)

Najpierw zainstaluj moduły `setup-kali.sh` i `setup-web.sh` opisane w README. Następnie:

```bash
cd ~/beardedwolf/repos/beardedwolf-admin
git pull --ff-only
bash -n install/setup-toolkit.sh
python3 -m py_compile toolkit/bw
bash install/setup-toolkit.sh
~/.local/bin/bw doctor
```

Instalator tworzy lokalny skrypt uruchamiający `~/.local/bin/bw`, który wywołuje moduł Python z repozytorium, ale **nie zmienia jego uprawnień w Git**. Wcześniej instalator tworzył dowiązanie symboliczne i zmieniał uprawnienia `toolkit/bw`, co mogło blokować `git pull`. Aktualny instalator bezpiecznie zastępuje jedynie własne stare dowiązanie; nie nadpisuje innych istniejących programów `bw`. Jeżeli `~/.local/bin` jest w `PATH`, można używać po prostu `bw`.

## Polecenia

```bash
bw doctor
bw dns example.org
bw tls example.org
bw dns example.org --sync
bw tls example.org --sync
```

- `bw doctor` lokalnie sprawdza dostępność narzędzi oraz katalogu Syncthing.
- `bw dns` odczytuje rekordy A, AAAA, MX, NS, SPF i DMARC. Nie weryfikuje DKIM bez wskazanego selektora.
- `bw tls` próbuje zestawić zaufane połączenie TLS na porcie 443 i zapisuje informacje o wersji TLS, szyfrze, ważności certyfikatu i nazwach DNS.
- Bez flagi `--sync` raport zapisuje się w `~/beardedwolf/raporty/DNS` lub `~/beardedwolf/raporty/TLS`.
- **Tylko** z flagą `--sync` raport trafia do `%USERPROFILE%\BeardedWolf\Sync\Raporty\DNS` / `TLS` na bieżącym Windowsie. Znajduje się tam folder współdzielony przez Syncthing.
- `--sync` jest świadomą decyzją o synchronizowaniu wskazanego raportu. Nie używaj go wobec raportów poufnych, jeżeli drugi komputer nie ma odpowiedniej ochrony danych.

Raport powstaje w HTML z oznaczonym językiem `pl`, nagłówkami i datą. Jest to odczyt punktowy, **nie pełny audyt**. Błędy DNS/TLS mogą wynikać np. z niedostępności sieci. Błędy diagnostyki są zapisywane w raporcie i powodują niezerowy kod zakończenia.

Przykładowy test bez synchronizacji:

```bash
~/.local/bin/bw dns example.org
```

Narzędzie wypisze dokładną ścieżkę utworzonego raportu.
