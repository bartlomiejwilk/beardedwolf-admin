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

Każdy wpis ma grupę (`prywatne`, `jdk`, `um`, itp.), typ (`wordpress`, `aplikacja`, `przekierowanie`, `sprawdzic`) i pole `authorized`, domyślnie **false**. W przyszłości będzie można indywidualnie połączyć serwis z właściwym aliasem SSH i katalogiem WordPressa. Na razie pola `ssh_alias` i `wp_root` pozostają nieustalone i nie są wykorzystywane.

W panelu GUI jest zakładka **Wszystkie serwisy**: edycja rejestru, potwierdzenie zakresu uprawnień, wstrzymanie testów, skan jednego albo wszystkich potwierdzonych serwisów, otwarcie raportu, zatwierdzenie baseline. Dwuklik na serwisie pozwala zmienić metadane. Usunięcie z rejestru nie kasuje raportów, kluczy i kont.

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
