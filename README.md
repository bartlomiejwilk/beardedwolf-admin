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

## Graficzny panel testow i SSH

Na Kali z uruchomionym pulpitem XFCE: `git pull --ff-only` i `bash install/setup-gui.sh`. Instalator doda ikone **BeardedWolf Admin** do pulpitu i menu Kali. Aplikacja pozwala wybrac testy DNS/TLS/HTTPS i jednym kliknieciem utworzyc zbiorczy raport HTML, domyslnie lokalny. Druga zakladka zarzadza lokalnymi profilami SSH, oddzielnym kluczem SSH dla każdego serwera i jednorazowym dodawaniem klucza na serwer. Uwierzytelnianie kluczem + keychain pozwala potem laczyc sie bez kazdorazowego wpisywania hasla serwera. Szczegoly i zasady bezpieczenstwa: [docs/panel-gui.md](docs/panel-gui.md).

Komendy tekstowe: `bw http example.org`, `bw suite example.org`, `bw suite example.org --sync` (ostatnia jawnie eksportuje raport do Syncthing). Nie sa to testy penetracyjne ani pelny audyt podatnosci.

### Serwery SSH: edycja i usuwanie

W zakladce **Serwery SSH** kliknij istniejacy profil, aby zaladowac go do formularza. Mozesz zmienic host, login i port, a potem wybrac **Zapisz zmiany**. Alias zostaje bez zmian, bo jest powiazany z kluczem SSH. **Usun zaznaczony** usuwa jedynie profil lokalny, nigdy klucze SSH ani `authorized_keys` na serwerze. Przed edycja lub usunieciem narzedzie zapisuje kopie poprzedniej konfiguracji.

## Zarzadzanie wieloma serwisami (inwentaryzacja i kontrole T01-T40)

Nowa zakladka **Wszystkie serwisy** w panelu XFCE pozwala dodawac i edytowac serwisy, potwierdzac zakres testow, uruchamiac pasywne kontrole wybranej domeny lub calej potwierdzonej grupy, otwierac raporty i zatwierdzac baseline. Startowy katalog zawiera 22 domeny/subdomeny i wymaga weryfikacji. Plik uzytkownika: `~/.config/beardedwolf/sites.json`. Raporty sa przechowywane lokalnie w `~/beardedwolf/raporty/FLEET/` i nie sa domyslnie synchronizowane.

Katalog `config/checks.json` zawiera T01-T40. Obecnie dziala **9 podstawowych kontroli publicznych**; pozostale 31 nie sa jeszcze wykonywane, wymagaja m.in. wlasciwego dostepu SSH i lokalizacji WordPress. Zaden niewykonany test nie jest prezentowany jako OK.

Po `git pull --ff-only` i ponownym uruchomieniu panelu widoczna bedzie nowa zakladka. Testy lokalne: `python3 -m unittest discover -s tests -v`. Szczegoly ograniczen, uprawnien i plan wdrozenia: [docs/flota-serwisow.md](docs/flota-serwisow.md).

## Przypisywanie stron do profili SSH i sortowanie tabel

W zakladce **Wszystkie serwisy** jest przycisk **Przypisz SSH / katalog**. Pozwala wskazac jeden z rzeczywiscie zapisanych lokalnie profili SSH (np. `jaslo`, `jdk`) i opcjonalny zweryfikowany katalog WWW/WordPress na serwerze. **Sugerowane powiazania OVH** pokazuje szesc znanych przypisan przed potwierdzeniem, nie nadpisuje juz istniejacych. Bez aktywnego lokalnego profilu nie zapisze mapowania. Przycisk **Polacz z SSH strony** otwiera sesje po oddzielnym potwierdzeniu, nie wykonuje automatycznych testow hostowych. Profile SSH nadal pozostaja tylko na danym komputerze. Szczegoly: [docs/flota-serwisow.md](docs/flota-serwisow.md).

Klikniecie naglowka kolumny w tabelach **Wszystkie serwisy**, **Serwery SSH** i **Kontrole T01-T40** zmienia sortowanie rosnaco/malejaco bez zmiany zapamietanego przypisania wierszy do obiektow.

## Dostawcy hostingowi i dostep FTP / SSH

Lista serwisow wyswietla teraz osobno **platforme**, **hosting**, **potwierdzony dostep** i **adres serwera**. Przycisk **Hosting / dostep** edytuje lokalnie te dane bez podawania hasel. W dokumentacji [flota-serwisow.md](docs/flota-serwisow.md) zapisano nowe potwierdzenia: PTTK (OVH cluster128, SSH, login nieustalony), UM (nazwa.pl), Jasloiregion (cyber_Folks), NZOZ i Parkowa (OVH cluster130, dostep FTP, SSH niepotwierdzone). Nie utozsamiamy FTP z SSH/SFTP. Starsze rejestry sa rozszerzane tylko o brakujace pola, z kopia zapasowa i zachowaniem mapowania SSH.

## Rozpoznawanie nieustalonych stron i bezpieczny import FileZilli

Klikniecie **Test wybranego** dla domeny o platformie `sprawdzic` wykonuje dodatkowo jednorazowa analize strony glownej i CNAME. Gdy pojawia sie silne sygnaly WordPressa, panel zapisuje `wordpress` w lokalnym rejestrze; przy slabszych sygnalach tylko pokazuje sugestie i dowody w raporcie, bez nadpisywania ustawien. Publiczny HTTP/DNS nie potwierdza dostawcy hostingu ani dostepu SSH.

Przycisk **Import FileZilla** pozwala na PC-Wilk wskazac lokalny `FileZilla.xml` / `sitemanager.xml` i przypisac wybrane metadane do jednej zaznaczonej strony. Import nie pobiera wartosci pola hasla `Pass`, nie dekoduje Base64, nie przenosi `LocalDir` i `RemoteDir`, nie wykonuje polaczen i nie publikuje eksportu w GitHub. Hasla przechowujemy w Bitwardenie. Szczegoly: [docs/flota-serwisow.md](docs/flota-serwisow.md).

## Pulpit kafelków i zarządzanie aktualizacjami WordPress

Pierwszy ekran BeardedWolf Admin pokazuje kafelki wszystkich zinwentaryzowanych domen: status WWW/HTTP, czas otrzymania nagłówków, TLS i termin certyfikatu, datę sprawdzenia oraz informację o dostępnych aktualizacjach WordPress (jeśli były sprawdzane). Odświeżanie publiczne wykonywane jest tylko dla domen z potwierdzonym zakresem testów. Brak badania jest widoczny jako **NIE SPRAWDZONO**, nie jako „OK”. Widok ma filtrowanie po grupach i przycisk **Szczegóły** kierujący do strony w rejestrze.

Dla serwisów WordPress przycisk **Aktualizacje WP** pozwala sprawdzić przez SSH zdalnym WP-CLI dostępną wersję Core i liczbę aktualizacji wtyczek, a następnie **ręcznie zaktualizować zaznaczone wtyczki lub Core**. Nie ma automatycznego instalowania aktualizacji na otwarciu programu. Zapisy na serwerze wymagają autoryzacji, prawidłowej ścieżki WordPress, działającego profilu SSH, aktualnej kopii plików i bazy oraz podwójnego potwierdzenia. Aktualizacja Core obejmuje także `wp core update-db`. Każda operacja jest odnotowywana lokalnie bez poświadczeń. Instrukcja i ograniczenia: [docs/flota-serwisow.md](docs/flota-serwisow.md).

Repozytorium zawiera odtwarzalne testy offline i zadanie GitHub Actions: `python3 -m unittest discover -s tests -v`.


## Wspólna inwentaryzacja PC-Wilk ↔ Lenovo YOGA-WILK

BeardedWolf Admin potrafi korzystać z jednego rejestru domen i metadanych SSH w folderze Syncthing Windows. Po aktywowaniu na obu urządzeniach zmiany listy domen, dostawców hostingu, przypisań SSH, katalogów WordPress oraz profili SSH (alias/host/użytkownik/port) zapisują się do Syncthing i trafiają na drugi komputer. GUI sprawdza nowe wersje co 5 sekund. Prywatne klucze, hasła, pełny ~/.ssh i notatki tekstowe **nie** są synchronizowane.

Pierwsze włączenie wymaga działania i sparowania Syncthing na obu Windows. W zakładce **Synchronizacja** na PC-Wilk użyj **Wykryj Windows**, a następnie **PC-Wilk: opublikuj moje ustawienia**. Na Lenovo, po faktycznym dostarczeniu obu plików przez Syncthing, użyj **Lenovo: przyjmij dane z Syncthing**. Dotychczasowe lokalne rejestry zostają jako kopie zapasowe. Aplikacja nie nadpisuje istniejącego folderu ze stanem, zgłasza konflikty Syncthing i nie obiecuje połączenia SSH, gdy na drugim komputerze brakuje osobnego klucza.

Szczegółowa instrukcja: [docs/synchronizacja.md](docs/synchronizacja.md).


## Porządkowanie inwentaryzacji

W panelu **Wszystkie serwisy** dostępne są wyszukiwanie i filtr grup, a w zakładce **Do wyjaśnienia** kontrola spójności danych bez połączeń sieciowych. Zgłaszane są błędne przypisania profili SSH do różnych klastrów OVH, brakujące profile, niezweryfikowane katalogi WordPress i podejrzane powiązania domen przekierowujących. **Nie następuje automatyczna zmiana zapisanych profili ani uprawnień.** Aplikacja blokuje wyraźnie błędne powiązania z innym klastrem podczas ręcznych połączeń SSH i operacji WP-CLI; różne nazwy w obrębie tego samego klastra są akceptowane. Status „TESTY DOZWOLONE” dotyczy jedynie zakresu pasywnych testów, a nie poprawności hostingu lub SSH.
