# BeardedWolf Operations Center

Ta wersja nie nadpisuje oryginalnego panelu ani wspólnych danych Syncthing.
Uruchamia alternatywny interfejs oparty na istniejącej logice AdminApp.

## Aktualizacja na Lenovo i PC-Wilk

W terminalu Kali:

    cd ~/beardedwolf/repos/beardedwolf-admin
    git status --short
    git pull --ff-only
    python3 -m unittest discover -s tests -v
    bash install/use-command-center.sh

Zamknij poprzednie okno panelu i otwórz ikonę BeardedWolf Admin z pulpitu Kali.
Skrypt wykrywa Python z Tkinter (na Lenovo był to python3.14), nie uruchamia apt,
nie modyfikuje kluczy SSH ani stanu Syncthing.

## Ekran główny

Tabela zaczyna się od domeny i stanu WWW. Kolejność: problemy dostępności,
uwagi, strony niesprawdzone, działające i na końcu przekierowania.
Kafelki statystyk podsumowują wyłącznie rzeczywiste pomiary.
HTTP 200 oznacza odpowiedź HTTP, nie poprawność wszystkich funkcji serwisu.
403 może oznaczać kontrolę dostępu, niekoniecznie awarię.

## Inwentaryzacja połączeń bez poświadczeń

Na każdym Kali można wyeksportować lokalne metadane SSH:

    python3 toolkit/bw_access.py export ~/beardedwolf-ssh-YOGA-WILK.json

W przypadku już istniejącego pliku wybierz inną nazwę. Raport zawiera
nazwy hostów, aliasy, porty i loginy, **nie** zawiera haseł, tokenów,
prywatnych kluczy, ścieżek do nich ani znanych kluczy hostów.

Na komputerze Windows bez WSL można uruchomić w PowerShell:

    .\install\export-windows-ssh.ps1

Jeżeli polityka wykonywania skryptów w urzędzie blokuje uruchomienie, uzgodnij to z administratorem IT. Nie obchodź polityki zabezpieczeń.\nSkrypt dotyczy konfiguracji Windows OpenSSH w katalogu użytkownika, bez
uprawnień administratora. Inne źródła, np. FileZilla, należy eksportować
w aplikacji i bezpiecznie wczytać przez zakładkę Dostępy / import.
Przed udostępnieniem wyeksportowanych plików upewnij się, że nie zawierają
danych objętych ograniczeniami organizacyjnymi.

W zakładce **Dostępy / import** operator może wyświetlić różnice,
a nowy kompletny profil SSH dodać pojedynczo po potwierdzeniu.
Istniejące aliasy, inne protokoły i konflikty nie są automatycznie
nadpisywane. Import nowego profilu trafia do Syncthing, jeśli synchronizacja
jest aktywna, dlatego informacji z komputera urzędowego **nie należy**
przenosić na urządzenia prywatne bez formalnego uprawnienia.

## Odczyt katalogów WordPress

Po nadaniu uprawnień i sprawdzeniu autoryzacji klucza:

    python3 toolkit/bw_paths.py ssh jaslo --depth 4 --ack

To ograniczony czasowo odczyt nazw katalogów. Nie otwiera zawartości
wp-config.php, nie zapisuje plików i nie łączy automatycznie znalezionych
katalogów z domenami. Operator musi zweryfikować wynik.

Jeżeli SSH nie jest dostępne, ale serwer obsługuje szyfrowane FTPS:

    python3 toolkit/bw_paths.py ftps ftp.example.org --user login --base / --depth 3 --ack

Hasło FTPS jest pobierane interaktywnie przez getpass, nie w argumentach,
pliku eksportu ani rozmowie. Narzędzie nie przełącza się na nieszyfrowane
FTP i nie wykonuje transferów plików. Serwery bez SSH i FTPS wymagają
indywidualnego postępowania oraz decyzji administratora.

## Dane dostępowe i komputer urzędowy

Bitwarden pozostaje magazynem poświadczeń. Nie przesyłaj haseł i kluczy
prywatnych do GitHuba, Syncthing ani przez czat. W środowisku urzędowym
eksport, instalacja narzędzi i przenoszenie informacji technicznych muszą
pozostawać zgodne z zasadami SZBI oraz zakresem uprawnień operatora.


## Zakładki w nowym interfejsie

- **Pulpit**: domeny i dostępność w pierwszych kolumnach, problemy u góry, przekierowania na końcu.
- **Dostępy / import**: eksport z Kali, porównanie lokalnych plików JSON lub XML FileZilli (bez przenoszenia haseł); nowy profil SSH dodaje się indywidualnie po potwierdzeniu.
- **Katalogi WordPress**: operator wybiera domenę, potwierdza odczyt przez SSH lub FTPS, przegląda listę znalezionych katalogów i dopiero zatwierdza wybraną ścieżkę. Nie ma automatycznego zgadywania powiązań ani zapisu bez zgody.

Na serwisach z uprawnieniami tylko do FTP bez TLS funkcja nie przesyła hasła przez sieć w sposób niezaszyfrowany. Dla zasobów służbowych obowiązują zasady uprawnień i ochrony informacji organizacji. Samo uruchomienie panelu nie wykonuje żadnego zdalnego odczytu plików.


## Wstrzymanie niesprawnych profili SSH na jednym komputerze

Nie usuwaj synchronizowanego pliku servers.json ani nie kasuj kluczy SSH.
Panel rekonstruuje wlasna sekcje w ~/.ssh/config z Syncthing przy kazdym
odczycie profili. Wstrzymanie musi byc obslugiwane przez kod aplikacji.

Na konkretnym komputerze, w jego Kali (np. PC-Wilk):

    cd ~/beardedwolf/repos/beardedwolf-admin
    git pull --ff-only
    python3 -m unittest discover -s tests -v
    python3 toolkit/bw_local_ssh.py status
    python3 toolkit/bw_local_ssh.py pause --yes
    python3 toolkit/bw_local_ssh.py status

Skrypt wykonuje kopie istniejacego ~/.ssh/config i metadanych serwerow
w ~/.local/state/beardedwolf/ssh-backups/<czas>/, poza Syncthing.
Wylacza lokalne aliasy generowane przez BeardedWolf, ale nie usuwa ich
ze wspolnego rejestru ani przypisan domen. Nie modyfikuje prywatnych kluczy,
authorized_keys i innych sekcji SSH uzytkownika.

Po sprawdzeniu loginu, hosta i lokalnego klucza mozna wlaczyc JEDEN profil:

    python3 toolkit/bw_local_ssh.py allow jaslo --yes
    python3 toolkit/bw_local_ssh.py status

Polecenie allow przywraca jedynie wskazany alias na tym komputerze;
nie uruchamia polaczenia ani zmian na serwerze. Przywrocenie wszystkich
dawnych aliasow, wyłącznie na danym komputerze (OSTROZNIE):

    python3 toolkit/bw_local_ssh.py resume --yes

Uzycie przyciskow SSH i operacji WP-CLI dla wstrzymanych profili jest
zablokowane. Komputer Lenovo zachowuje swoj odrebny stan lokalny.
