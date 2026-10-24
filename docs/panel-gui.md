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
- `~/.ssh/id_ed25519_bw_<alias>` (oddzielny klucz prywatny **dla każdego profilu serwera i każdego komputera**, bez synchronizacji).

**Edycja i usuwanie profili:** wybierz serwer w tabeli. Formularz automatycznie wczyta jego ustawienia, a przycisk zmieni nazwę na **Zapisz zmiany**. Możesz zmienić adres SSH, login i port bez generowania nowego klucza. Alias jest zablokowany podczas edycji, bo odpowiada nazwie pliku klucza SSH (np. `jdk` → `~/.ssh/id_ed25519_bw_jdk`). Przycisk **Anuluj edycję / wyczyść** wraca do dodawania nowego serwera. **Usuń zaznaczony** wymaga potwierdzenia i usuwa tylko profil lokalny i sekcję aliasu w konfiguracji SSH. Nie kasuje klucza prywatnego/publicznego i nie wycofuje klucza z `authorized_keys` na serwerze. Kopie konfiguracji są zapisywane w `~/.ssh/config.beardedwolf.original.bak`, `~/.ssh/config.beardedwolf.previous.bak` i `~/.config/beardedwolf/servers.json.previous.bak` (jeśli poprzednie pliki istniały). Dla całkowitego odebrania dostępu należy dodatkowo unieważnić klucz publiczny na serwerze z zachowaniem uprawnień administracyjnych.

**Pierwsza konfiguracja dostępu do serwera:**

1. **Zapisz profil serwera**: alias, adres hosta, login SSH i port. Wybierz go na liście.
2. Kliknij **Utwórz klucz serwera**, wybierz silną *passphrase* i zapisz ją w Bitwardenie. Klucz tworzony jest oddzielnie dla każdego serwera i komputera, bez nadpisywania istniejącego.
3. Kliknij **Dodaj klucz na serwer**. To uruchamia `ssh-copy-id`, modyfikuje wyłącznie `authorized_keys` zdalnego konta i zwykle wymaga jednorazowego hasła serwera. **Przed zaakceptowaniem nowego hosta zweryfikuj odcisk klucza SSH przez niezależny kanał**. Jeśli dostawca nie pozwala na `ssh-copy-id`, klucz publiczny można dodać przez jego panel lub uprawnionego administratora.
4. Kliknij **Połącz SSH**. `keychain` uruchamia/wznawia agenta, OpenSSH dodaje klucz do agenta po podaniu passphrase przy pierwszym użyciu. Później agent pamięta klucz, więc zazwyczaj nie trzeba ponownie wpisywać ani hasła serwera, ani passphrase w tej samej sesji WSL. Agent działa do zakończenia sesji lub usunięcia kluczy.
5. **Test połączenia** próbuje połączyć się bez interakcji i uruchamia jedynie `exit`, bez zmian na serwerze.

Połączenie z danym serwerem wymaga, aby konto SSH było dostępne, klucz został zaakceptowany, a jego użytkownik posiadał odpowiednie uprawnienia. SSH nie omija ograniczeń hostingu. Nie włączaj logowania root bez potrzeby i nie udostępniaj prywatnego klucza na GitHub, Syncthing ani przez komunikatory.

Serwery należące do różnych organizacji otrzymują osobne klucze i profile uprawnień. Każdy alias ma swój klucz ED25519. Bez względu na to ogranicz uprawnienia kont zgodnie z zakresem obowiązków. Narzędzie nie zapisuje haseł ani tokenów, a Bitwarden pozostaje głównym menedżerem haseł.

## Diagnostyka

Jeżeli panel nie otwiera się po kliknięciu ikony:

```bash
python3 ~/beardedwolf/repos/beardedwolf-admin/toolkit/bw_gui.py
```

Komunikat o błędzie pojawi się w terminalu. W pierwszej wersji aplikacja wymaga działającego pulpitu graficznego Kali.

### `python3-tk` zainstalowany, a `tkinter` nie działa

W środowisku może występować kilka interpreterów Pythona (np. w `/usr/local/bin` i `/usr/bin`). Instalator sprawdza po kolei dostępne interpretery i wybiera ten, dla którego działa `import tkinter`, bez zmieniania globalnego `/usr/bin/python3`. W przypadku Kali z Pythonem 3.13 jako domyślnym i pakietem `python3-tk 3.14.7-3` zwykle będzie to `/usr/bin/python3.14`. Skrót na pulpicie zapisuje tę wybraną ścieżkę. Jeśli instalacja była wcześniej przerwana, wykonaj `git pull --ff-only` i ponownie `bash install/setup-gui.sh`. Nie instaluj Tkinter za pomocą `sudo pip`, ponieważ może to uszkodzić zależności systemowe.

Jeżeli `~/.local/bin/bw` już istnieje, ale działa polecenie `bw doctor`, pomiń ponowną instalację `setup-toolkit.sh`; panel GUI nie wymaga wymiany działającego pliku. Nie usuwaj tego pliku bez sprawdzenia jego zawartości.

### Szybka kontrola przy niezgodności wersji

```bash
/usr/bin/python3 --version
/usr/bin/python3.14 -c 'import tkinter; print("Tkinter OK:", tkinter.TkVersion)'
```

Jeżeli druga komenda działa, uruchom najnowszy instalator `bash install/setup-gui.sh` po `git pull --ff-only`. Instalator sam wybierze właściwą wersję. Nie wykonuj `sudo ln -sf /usr/bin/python3.14 /usr/bin/python3`; zmiana globalnej ścieżki interpretera może mieć uboczne skutki.

### Przykład: korekta profilu JDK na PC-Wilk

Wybierz już istniejący alias `jdk` (nie `ovh-jdk`). Ustaw host na `ssh.cluster126.hosting.ovh.net`, login `jdkjasj`, port `22`, a następnie kliknij **Zapisz zmiany**. Klucz `~/.ssh/id_ed25519_bw_jdk` pozostanie nietknięty. Sprawdź w terminalu `ssh -G jdk | grep -E '^(hostname|user|port|identityfile) '`. Samo poprawienie profilu nie oznacza jeszcze, że klucz publiczny Kali jest uprawniony na serwerze: wymaga to osobnej, świadomej autoryzacji.
