# BeardedWolf Admin: wiele serwisów i 40 kontroli

## Stan wdrożenia

Pierwsza wersja tego modułu dodaje **inwentaryzację i bazę dla wszystkich 40 kontroli**, działające testy publiczne oraz kontrolowany baseline. Nie jest jeszcze kompletnym hostowym IDS/FIM. Nie oznaczamy kontroli, których nie wykonaliśmy, jako „OK”.

| ID | Stan |
|---|---|
| T19 | HEAD do REST Users: tylko kod HTTP, bez pobierania kont |
| T20 | HEAD do standardowego wp-login.php (nie obejmuje niestandardowych adresów logowania) |
| T21 | HEAD do xmlrpc.php |
| T22 | HEAD do jednego nieznanego URL, ostrzeżenie przy HTTP 200 |
| T23 | Końcowy cel przekierowania HTTP, porównanie z baseline |
| T24 | HTTPS, kod odpowiedzi i wybrane nagłówki |
| T25 | HTTP 5xx i czas otrzymania nagłówków jako orientacyjny wskaźnik, **nie rzeczywisty TTFB** |
| T34 | Rekordy DNS: A, AAAA, MX, NS, SPF i DMARC, bez pełnej walidacji polityk |
| T35 | Certyfikat i parametry połączenia TLS |

Pozostałe **31 kontroli** znajduje się w `config/checks.json` ze statusem `planned`. Wymagają agentów, audytów przez SSH, logów, WP-CLI na hostingu, danych z bazy lub działań manualnych. Plan obejmuje m.in. sumy kontrolne WordPressa, wykrywanie administratorów, pliki PHP w uploads, cron, opcje bazy, konfiguracje PHP, logi logowania, porównanie między serwisami i test przywracania backupu. Pełny zakres: T01–T40 z dokumentu wejściowego.

## Inwentaryzacja

Plik startowy `config/sites.json` obejmuje 22 domeny i subdomeny z wcześniejszych prac. To **wstępny katalog**, a nie formalne potwierdzenie uprawnień ani zapewnienie, że wszystkie domeny nadal są aktywne. Przy pierwszym uruchomieniu moduł kopiuje go do lokalnego `~/.config/beardedwolf/sites.json`. Nie synchronizuje i nie nadpisuje późniejszych zmian użytkownika.

Każdy wpis ma grupę (`prywatne`, `jdk`, `um`, itp.), typ (`wordpress`, `aplikacja`, `przekierowanie`, `sprawdzic`) i pole `authorized`, domyślnie **false**. Lokalny rejestr przechowuje ponadto przypisany alias SSH (`ssh_alias`) oraz opcjonalny katalog serwisu na serwerze (`wp_root`). Powiązania mogą zostać uzupełnione przez użytkownika w interfejsie, ale samo ich zapisanie nie wykonuje żadnego połączenia SSH i nie oznacza autoryzacji testów hostowych.

W panelu GUI jest zakładka **Wszystkie serwisy**: edycja rejestru, potwierdzenie zakresu uprawnień, wstrzymanie testów, skan jednego albo wszystkich potwierdzonych serwisów, otwarcie raportu, zatwierdzenie baseline. Dwuklik na serwisie pozwala zmienić metadane. Usunięcie z rejestru nie kasuje raportów, kluczy i kont.

## Powiązania stron z SSH i ścieżkami instalacji

W zakładce **Wszystkie serwisy** zaznacz serwis i wybierz **Przypisz SSH / katalog**. W oknie ustaw lokalny profil z zakładki **Serwery SSH** (`jaslo`, `jdk` itd.) oraz ewentualnie zweryfikowaną, **bezwzględną ścieżkę Linux** do katalogu z instalacją WordPress, np. `/home/jaslo/beardedwolf`. Zapis jest lokalny w `~/.config/beardedwolf/sites.json`. Pole może być puste, jeśli ścieżka jest nieznana lub serwis nie korzysta z WordPressa. Zapisany alias musi istnieć lokalnie; nie można przypisać nieistniejącego profilu SSH.

**Sugerowane powiązania OVH**: przycisk pokazuje listę wszystkich przypisań **przed zapisem** i wymaga osobnego potwierdzenia. Podpowiedzi dotyczą wyłącznie:

| Domena | Sugerowany alias |
|---|---|
| `beardedwolf.pl` | `jaslo` |
| `art.beardedwolf.pl` | `jaslo` |
| `labdostepnosci.pl` | `jaslo` |
| `szeptogra.pl` | `jaslo` |
| `jdkjaslo.pl` | `jdk` |
| `kino.jdkjaslo.pl` | `jdk` |

Podpowiedź jest dostępna tylko wtedy, gdy lokalny profil istnieje. Nie nadpisuje wcześniej przypisanych hostów. **Nie przypisujemy automatycznie** hostingu UM Jasło, serwisów zewnętrznych, domen przekierowujących ani tych, dla których nie znamy jednoznacznie lokalizacji. Aliasy `jaslo` i `jdk` to nazwy profili z PC-Wilk, a nie obowiązkowe nazwy na innych komputerach. Na Lenovo powiązanie należy wykonać z użyciem aliasów tam zdefiniowanych.

Przycisk **Połącz z SSH strony** otwiera interaktywną sesję terminala dla przypisanego profilu po potwierdzeniu. Nie wykonuje komend na serwerze automatycznie. Usunięcie przypisania następuje przez wybór `(brak)` i wyczyszczenie pola katalogu. Powiązanie może być osierocone, jeśli profil SSH usunięto z innego narzędzia; wtedy trzeba przypisać aktualny profil, nie odtwarzamy go w ciemno.

**Ważne:** sam alias nie wystarcza do uruchomienia hostowych T01–T18, T26–T33 i T36–T39. Wymagają jeszcze autoryzacji użycia narzędzi na danej instalacji, sprawdzenia poprawnego połączenia kluczem SSH, weryfikacji ścieżki na serwerze i wdrożenia odczytowego modułu audytowego. Nie kopiujemy kluczy prywatnych ani plików `wp-config.php` na lokalny komputer.

Przy tej aktualizacji wprowadzono również **sortowanie tabel** w zakładkach Serwery SSH, Wszystkie serwisy oraz Kontrole T01–T40. Kliknięcie nagłówka sortuje rosnąco, kolejne malejąco, bez zmiany danych ani identyfikatorów przypisanych do wybranego wiersza.

## Hosting i dostęp: SSH, FTP, SFTP

Karta **Wszystkie serwisy** rozróżnia platformę serwisu (WordPress / aplikacja / przekierowanie / nieustalona) od **dostawcy hostingu**, **adresu serwera** i **potwierdzonego protokołu dostępu**. Pole `sprawdzic` z wcześniejszych wersji jest w tabeli wyświetlane jako „nieustalona”. Samo wskazanie dostawcy nie daje dostępu do plików.

**Dane przekazane 24 października 2026 r.:**

| Serwis | Dostawca | Protokół / host | Stan przypisania |
|---|---|---|---|
| `jaslopttk.pl` | OVHcloud | SSH: `ssh.cluster128.hosting.ovh.net`, port 22 | Brak potwierdzonego loginu SSH i lokalnego profilu |
| `um.jaslo.pl` | nazwa.pl | Serwer i protokół nieustalone | Nie przypisujemy SSH |
| `jasloiregion.pl` | cyber_Folks | Serwer i protokół nieustalone | Nie przypisujemy SSH |
| `nzozmedykjaslo.pl` | OVHcloud | FTP: `ftp.cluster130.hosting.ovh.net`, port 21 | SSH niepotwierdzone |
| `parkowajaslo.pl` | OVHcloud | FTP: `ftp.cluster130.hosting.ovh.net`, port 21 | SSH niepotwierdzone |

Własne serwisy na cluster114 i serwisy JDK na cluster126 zachowują już istniejące propozycje profili `jaslo` i `jdk`. **Nie należy dopisywać do pola SSH serwerów FTP tylko dlatego, że adres ma postać `ftp.cluster...`.** Sama znajomość nazwy SSH na cluster128 również nie pozwala na logowanie bez loginu i autoryzacji klucza.

Dla Parkowej znany jest login FTP `parkowd`, jednak nie zapisujemy go w plikach startowych GitHuba. Można go bezpiecznie wpisać w *lokalnym* oknie **Hosting / dostęp** po zaznaczeniu `parkowajaslo.pl`. Hasła pozostają w Bitwardenie i **nigdy** nie są wprowadzane do panelu BeardedWolf Admin.

Przy pierwszym otwarciu nowej wersji lokalny `~/.config/beardedwolf/sites.json` zostanie **jednorazowo rozszerzony o brakujące pola hostingu**, z zachowaniem starych profili SSH, uprawnień i baseline. Automatyczny zapis tworzy kopię `~/.config/beardedwolf/sites.json.previous.bak`. Jeśli pole `hosting` było już zdefiniowane, nie zostanie nadpisane.

Panel prezentuje dostępne pola hostingu oraz pozwala je ręcznie edytować. Nie próbuje automatycznie połączyć się FTP, SFTP, SSH ani używać niezabezpieczonego FTP na porcie 21. Aby uzyskać zaszyfrowany transfer, sprawdź w panelu **OVHcloud → Hosting → FTP–SSH**, czy dla danego użytkownika dostępne jest **SFTP** (i czy dla pakietu można aktywować SSH); samo FTP nie potwierdza ani SSH, ani SFTP.

## Jak uruchamiać

Na komputerze z Kali WSL 2 i XFCE:

```bash
cd ~/beardedwolf/repos/beardedwolf-admin
git pull --ff-only
/usr/bin/python3 -m unittest discover -s tests -v
```

Zamknij i uruchom ponownie **BeardedWolf Admin** z ikony. Wybierz zakładkę `Wszystkie serwisy`.

Przy pierwszym skanie wybierz jeden własny serwis, kliknij **Potwierdź zakres**, następnie **Test wybranego** i przejrzyj raport HTML. Jeśli stan jest prawidłowy, kliknij **Zatwierdź baseline**. Kolejne badania wskażą różnice. Zatwierdzanie baseline nie powinno następować automatycznie, bo wtedy można by zaakceptować stan po incydencie.

CLI (nieobowiązkowe, do automatyzacji później):

```bash
python3 toolkit/bw_fleet.py sites
python3 toolkit/bw_fleet.py checks
python3 toolkit/bw_fleet.py confirm beardedwolf.pl
python3 toolkit/bw_fleet.py scan beardedwolf.pl
python3 toolkit/bw_fleet.py baseline-approve beardedwolf.pl
python3 toolkit/bw_fleet.py scan-all
```

Wyniki lokalne: `~/beardedwolf/raporty/FLEET/<domena>/audit_*.html` i `audit_*.json`; zaakceptowany wzorzec w `baseline-approved.json`. Brak automatycznego transferu do Syncthing i brak chmurowego uploadu.

## Założenia bezpieczeństwa i ograniczenia

- Testy są uruchamiane tylko na domenach z lokalnie zatwierdzonym zakresem, w sposób punktowy. Nie wykonują skanowania portów, enumeracji plików ani prób włamań.
- Zapytania WWW wysyłają realistyczny `User-Agent` i `Accept`; inspekcja przekierowań nie podąża za nimi na kolejne hosty.
- Baseline porównuje zaobserwowane wyniki, ale nie nadaje automatycznie oceny bezpieczeństwa. Przy braku baseline status to `BRAK_BASELINE`. Nieuzyskane wyniki są błędami kontroli, a nie sukcesami.
- Różnice nie muszą oznaczać ataku, szczególnie po aktualizacji WP, migracji hostingu i zmianie DNS. Duża część testów wymaga zatwierdzonych wyjątków per serwis.
- Nie uruchamiamy testów baz danych ani operacji SSH tylko na podstawie tego, że domena jest w katalogu.
- Czas odpowiedzi jest tylko czasem uzyskania nagłówków po żądaniu HEAD; dla rzetelnego TTFB potrzebny osobny pomiar i porównanie statystyczne.
- Automatyczne cykliczne audyty, retencja, centralne alerty, uwierzytelniony FIM i okresowe testy backupu są **kolejnymi etapami**, nie są jeszcze wdrożone.

## Plan dalszego wdrożenia

1. Potwierdzić mapę domen, właścicieli, rodzaj systemu i uprawnienia do hostingu.
2. Przypisać każdej instalacji WordPress zweryfikowany host SSH, login i katalog główny. Klucze prywatne pozostają na komputerach lokalnych.
3. Wdrożyć odczytowe moduły hostowe T01–T18, T26–T33 i T36–T39, z kontrolą obciążenia serwerów współdzielonych.
4. Przygotować i zatwierdzić bezpieczny baseline (pliki, administratorzy, wtyczki, CRON) oraz zgłaszanie różnic między serwisami.
5. Dodać uruchamianie według harmonogramu na uprawnionej maszynie, bez zależności od działającego GUI; rozdzielić raporty organizacyjne od prywatnych i ograniczyć dostęp do danych.
