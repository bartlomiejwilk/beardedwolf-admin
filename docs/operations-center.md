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

## Natychmiastowy eksport rzeczywistych dostepow Windows

Prywatny backup jest niezalezny od eksportu JSON z samymi metadanymi.

1. W Windows PowerShell uruchom lokalny skrypt:
   `install/export-windows-private.ps1`
2. Powstaje osobny katalog `Documents/BeardedWolf-AccessAudit/PRIVATE-KOMPUTER-data/`
   z oryginalnymi `FileZilla/sitemanager.xml`, `Windows-OpenSSH/`
   (config i klucze), oraz jesli istnieja `PuTTY.reg`,
   `WinSCP.reg` i `WinSCP.ini`.
3. **Katalog zawiera SEKRETY**, wiec nie wysylaj go do czatu,
   repozytorium GitHub ani do Syncthing. Windows ACL ogranicza dostep;
   sam katalog NIE jest zaszyfrowany. Przenos go tylko na dysku BitLocker
   i po uwzglednieniu ograniczen organizacyjnych.
4. Hasel chronionych FileZilla master password ani DPAPI WinSCP
   ten backup nie odszyfrowuje. Oryginalne programy moga ich nadal uzywac
   w oryginalnym koncie Windows.

W zakladce **Logowania Windows** BeardedWolf odczytuje istniejace nazwy
połączeń FileZilla i aliasy z `.ssh/config`. Dwuklik na FileZilla
uruchamia oryginalny zapisany wpis klienta Windows z zachowaniem
jego dotychczasowej konfiguracji uwierzytelnienia. Dwuklik na SSH
uruchamia Windows ssh.exe, ktory korzysta z tego samego lokalnego konta,
kluczy i ssh-agent co dotychczas. Nie potrzeba kopiowac zadnego hasla
do kodu programu. Jest to integracja z istniejacymi programami
Windows, a nie niezalezny magazyn hasel BeardedWolf.

**Ograniczenia:** nowa funkcja wymaga Windows z WSL interoperability i
zainstalowanej FileZilli, jesli operator chce otwierac jej sesje.
Konfiguracje WinSCP/PuTTY sa kopiowane do backupu, ale automatyczne
otwieranie z panelu dotyczy obecnie FileZilli i Windows OpenSSH.
Danych urzedowych nie nalezy automatycznie przenosic na prywatny PC.


## Powiazania domen z aktualnymi logowaniami oraz SSH bez aliasu

Nowa zakladka **Powiazania** (osiagalna takze przyciskiem w zakladce
**Logowania Windows**) odczytuje biezacy rejestr domen, lokalne profile
SSH BeardedWolf i aktualna liste FileZilla z Windows. Wpisy usuniete przez
operatora z FileZilli nie sa pobierane ze starych eksportow.

Po wyborze domeny i zapisanej sesji operator moze zatwierdzic przypisanie.
Dla SSH zapisuje sie `ssh_alias` bez usuwania danych FTP. Dla FTP/SFTP
zapisuje sie host, port, login i protokol w sekcji `hosting`, a profil
SSH zostaje nienaruszony. Zmiana SSH na inny serwer zeruje poprzednia
sciezke WordPress, bo moglaby wskazywac zly serwer. Hasla sa uzywane przez
oryginalna FileZille i nie sa importowane do rejestru ani synchronizowane.

Przycisk **Test SSH bez aliasu** wykonuje jeden jawnie potwierdzony test
Windows OpenSSH z `-F none -p PORT -l LOGIN HOST exit`, bez hasla, z
`BatchMode=yes` i walidacja znanego klucza hosta. W trybie bez aliasu
specyficzne opcje `IdentityFile` przypisane aliasowi nie obowiazuja.
Odrzucone klucze nie oznaczaja nieaktywnego konta. Przyciskiem **Otworz
wybrane logowanie** mozna wykonac interaktywny test haslem w Windows
SSH albo uruchomic FileZille z jej zapisanym kontem SFTP/FTP.
Nie uruchamia sie prob na innych serwerach niz wybrane przez operatora.
