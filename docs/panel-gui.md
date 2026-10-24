# BeardedWolf Admin GUI: testy domen i serwery SSH

Graficzny panel dla **Kali Linux WSL 2 z pulpitem XFCE (Win-KeX)**. Projekt działa lokalnie. Użytkownik uruchamia aplikację dwuklikiem z pulpitu Kali lub z menu aplikacji.

## Instalacja na każdym komputerze (jednorazowa)

Przy działającym pulpicie XFCE otwórz terminal Kali i wykonaj:

```bash
cd ~/beardedwolf/repos/beardedwolf-admin
git pull --ff-only
bash -n install/setup-gui.sh
bash install/setup-gui.sh
```

Instalator doinstaluje `python3-tk`, `keychain`, `xdg-utils`, `xfce4-terminal` i `openssh-client`, sprawdzi składnię wszystkich modułów GUI, a potem umieści **BeardedWolf Admin** na pulpicie Kali i w menu aplikacji XFCE. Jeśli środowisko XFCE zapyta o zaufanie do skrótu `.desktop`, potwierdź po upewnieniu się, że jego ścieżka wskazuje na lokalne repozytorium.

Możesz także uruchomić panel z terminala graficznego: `/usr/bin/python3 ~/beardedwolf/repos/beardedwolf-admin/toolkit/bw_gui.py`.

Testy regresyjne, bez wykonywania połączeń sieciowych:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

## Zakładka „Testy domen”

Wpisz domenę, wybierz zakres i kliknij **Uruchom wybrane testy**. Dostępne kontrole:

- **DNS**: A, AAAA, MX, NS, SPF i DMARC (tylko odczyt; brak walidacji polityk, DKIM wymaga selektora).
- **TLS**: zaufanie do certyfikatu, jego termin ważności, protokół TLS i szyfr na porcie 443.
- **WWW**: pojedyncze żądanie HTTPS HEAD, a gdy serwer nie obsługuje HEAD, GET, z kontrolą odpowiedzi, przekierowania i wybranych nagłówków bezpieczeństwa.

Wynik jest jednym semantycznym plikiem HTML w `~/beardedwolf/raporty/PAKIET`. Brak danego nagłówka nie oznacza automatycznie podatności. Nie są wykonywane testy penetracyjne, exploitacje, logowania, enumeracja podstron ani skanowanie portów.

Eksport do Syncthing **domyślnie jest wyłączony**. Trzeba go jawnie zaznaczyć i potwierdzić, pamiętając o ograniczeniach przechowywania raportów na niezaszyfrowanym komputerze.

Z konsoli dostępne są również `bw http example.org` i `bw suite example.org`.

## Zakładka „Serwery SSH”

Wpisujesz alias (np. `ovh-jaslo`), host SSH, login i port, po czym zapisujesz profil. Dane są lokalne:

- `~/.config/beardedwolf/servers.json` (bez haseł);
- `~/.ssh/config` (sekcja oznaczona jako zarządzana przez BeardedWolf);
- `~/.ssh/id_ed25519_bw_servers` (oddzielny klucz prywatny **dla każdego komputera**, bez synchronizacji).

**Pierwsza konfiguracja dostępu do serwera:**

1. Kliknij **Utwórz klucz SSH**, wybierz silną *passphrase* i zapisz ją w Bitwardenie. Klucz tworzony jest raz na komputer i nie nadpisuje istniejącego.
2. Zapisz profil serwera. Wybierz go na liście.
3. Kliknij **Dodaj klucz na serwer**. To uruchamia `ssh-copy-id`, modyfikuje wyłącznie `authorized_keys` zdalnego konta i zwykle wymaga jednorazowego hasła serwera. **Przed zaakceptowaniem nowego hosta zweryfikuj odcisk klucza SSH przez niezależny kanał**. Jeśli dostawca nie pozwala na `ssh-copy-id`, klucz publiczny można dodać przez jego panel lub uprawnionego administratora.
4. Kliknij **Połącz SSH**. `keychain` uruchamia/wznawia agenta, OpenSSH dodaje klucz do agenta po podaniu passphrase przy pierwszym użyciu. Później agent pamięta klucz, więc zazwyczaj nie trzeba ponownie wpisywać ani hasła serwera, ani passphrase w tej samej sesji WSL. Agent działa do zakończenia sesji lub usunięcia kluczy.
5. **Test połączenia** próbuje połączyć się bez interakcji i uruchamia jedynie `exit`, bez zmian na serwerze.

Połączenie z danym serwerem wymaga, aby konto SSH było dostępne, klucz został zaakceptowany, a jego użytkownik posiadał odpowiednie uprawnienia. SSH nie omija ograniczeń hostingu. Nie włączaj logowania root bez potrzeby i nie udostępniaj prywatnego klucza na GitHub, Syncthing ani przez komunikatory.

Przy serwerach należących do różnych organizacji rozważ osobne klucze i niezależne profile uprawnień; bieżąca pierwsza wersja GUI używa jednego klucza serwerowego na komputer. Narzędzie nie zapisuje haseł ani tokenów, a Bitwarden pozostaje głównym menedżerem haseł.

## Diagnostyka

Jeżeli panel nie otwiera się po kliknięciu ikony:

```bash
python3 ~/beardedwolf/repos/beardedwolf-admin/toolkit/bw_gui.py
```

Komunikat o błędzie pojawi się w terminalu. W pierwszej wersji aplikacja wymaga działającego pulpitu graficznego Kali.

### `python3-tk` zainstalowany, a `tkinter` nie działa

W środowisku może występować kilka interpreterów Pythona (np. w `/usr/local/bin` i `/usr/bin`). Instalator i skrót aplikacji używają teraz konsekwentnie `/usr/bin/python3`, zgodnego z `python3-tk` z menedżera pakietów Kali. Jeśli instalacja była wcześniej przerwana, wykonaj `git pull --ff-only` i ponownie `bash install/setup-gui.sh`. Nie instaluj Tkinter za pomocą `sudo pip`, ponieważ może to uszkodzić zależności systemowe.

Jeżeli `~/.local/bin/bw` już istnieje, ale działa polecenie `bw doctor`, pomiń ponowną instalację `setup-toolkit.sh`; panel GUI nie wymaga wymiany działającego pliku. Nie usuwaj tego pliku bez sprawdzenia jego zawartości.
