# Synchronizacja dwoch komputerow z Windows i Kali WSL 2

Status: aplikacja obsługuje współdzielone metadane przez Syncthing, ale na każdym komputerze trzeba włączyć tę funkcję i sparować urządzenia Syncthing. Sama aktualizacja repozytorium NIE uruchamia synchronizacji.

## Architektura

- Na obu prywatnych komputerach dziala osobna instalacja Windows i osobne Kali WSL 2.
- Repozytoria Git sa lokalne w systemie plikow Linuksa: `~/beardedwolf/repos`.
- Prywatne repozytorium `bartlomiejwilk/beardedwolf-admin` przechowuje kod, skrypty i pozbawiona sekretow konfiguracje. Git nie synchronizuje zmian automatycznie: na pierwszym komputerze commit/push, na drugim pull.
- Syncthing na Windows ma synchronizowac wylacznie katalog `BeardedWolf` z wybranymi raportami i dokumentacja. Nie synchronizujemy `ext4.vhdx`, calego `/home` ani baz aktywnie uzywanych przez aplikacje.
- Restic bedzie oddzielnym, szyfrowanym, wersjonowanym backupem. Syncthing nie zastępuje backupu.
- SanDisk USB 64 GB: planowany backup offline. Aktualnie zawiera Kali Live i NIE jest skonfigurowany jako magazyn kopii zapasowych.

## Foldery Windows (docelowo na obu komputerach)

```text
%USERPROFILE%\BeardedWolf\
  Raporty\DNS\
  Raporty\TLS\
  Raporty\WordPress\
  Raporty\Audyty-WWW\
  Raporty\Incydenty-Prywatne\
  Dokumentacja\
  Eksporty\
```

Foldery mozna utworzyc z PowerShell (nie w powloce Kali):

```powershell
$root = Join-Path $env:USERPROFILE 'BeardedWolf'
@('Raporty\DNS','Raporty\TLS','Raporty\WordPress',
  'Raporty\Audyty-WWW','Raporty\Incydenty-Prywatne',
  'Dokumentacja','Eksporty') | ForEach-Object {
  New-Item -ItemType Directory -Force -Path (Join-Path $root $_) | Out-Null
}
```

## Bezpieczenstwo

1. Kazdy komputer ma osobny klucz SSH do GitHub. Nie kopiujemy `~/.ssh`, `~/.config/gh/hosts.yml`, tokenow ani poświadczen.
2. Samo repozytorium prywatne nie jest odpowiednim magazynem hasel, kluczy i materialu dowodowego. `.gitignore` pomaga, lecz nie gwarantuje ochrony przed przypadkowym commitem.
3. Dane prywatne i poufne wymagaja szyfrowania dyskow obu komputerow. Synchronizacja plikow do drugiego komputera oznacza powstanie drugiej kopii w postaci odszyfrowanej dla zalogowanego uzytkownika.
4. Materialow sluzbowych i cudzych danych z incydentow nie wysylamy automatycznie na prywatne komputery ani do prywatnej chmury bez podstawy i uprawnien.
5. Konflikty zmian w Syncthing nalezy rozstrzygac swiadomie. Usuniecia moga sie synchronizowac; wlacz wersjonowanie oraz niezalezny backup.
6. Pliki raportow generowane przez Kali nalezy **eksportowac** do katalogu Windows. Nie synchronizujemy calego systemu WSL.


## Synchronizacja domen i SSH: dwukierunkowe metadane

BeardedWolf Admin ma zakładkę **Synchronizacja**. Po jej włączeniu na obu komputerach źródłem prawdy stają się pliki w folderze Windows synchronizowanym przez Syncthing:

    %USERPROFILE%\BeardedWolf\Sync\Admin\sites.json
    %USERPROFILE%\BeardedWolf\Sync\Admin\servers.json

- Pierwszy plik zawiera domeny, grupy, platformy, uprawnienia do testów, dostawcę hostingu, przypisanie profilu SSH i katalog WordPress.
- Drugi plik zawiera wyłącznie alias, host, login SSH i port.
- **Nie są synchronizowane** hasła, prywatne klucze SSH, tokeny, całe ~/.ssh, ~/.ssh/config, known_hosts, dane Bitwarden, raporty prywatne, dane incydentów ani notatki tekstowe.
- Każde Kali WSL tworzy swoją lokalną sekcję BeardedWolf w ~/.ssh/config z odwołaniem do **własnych prywatnych kluczy SSH**. Sam alias nie oznacza prawa dostępu do serwera. Klucze publiczne trzeba autoryzować na odpowiednich hostingach także dla Lenovo.
- Aplikacja zapisuje zmiany bezpośrednio we wspólnym folderze. Syncthing przekazuje je między komputerami. Działająca aplikacja sprawdza nowe wersje danych co 5 sekund. Nie potrzeba git push/git pull dla lokalnej inwentaryzacji, ale git pull nadal aktualizuje kod.
- BeardedWolf nie paruje urządzeń Syncthing i nie sprawdza rzeczywistego statusu synchronizacji sieciowej. To należy potwierdzić w Syncthing po obu stronach.

### PC-Wilk: publikacja pierwszego zestawu

1. Sprawdź w Syncthing, że folder Windows %USERPROFILE%\BeardedWolf\Sync jest udostępniony zaufanemu Lenovo. Nie dołączaj poufnych raportów i danych incydentów, jeśli nie masz upoważnienia do ich kopiowania.
2. Uruchom zaktualizowany BeardedWolf Admin, zakładka **Synchronizacja**.
3. Kliknij **Wykryj Windows**, sprawdź lokalizację folderu Sync.
4. Kliknij **PC-Wilk: opublikuj moje ustawienia**. Aplikacja nie nadpisze wcześniejszych plików Admin/sites.json ani Admin/servers.json.
5. Potwierdź zakończenie transferu na obu urządzeniach w panelu Syncthing.

### Lenovo YOGA-WILK: przyjęcie danych

1. Skonfiguruj w Windows na Lenovo Syncthing z takim samym współdzielonym folderem %USERPROFILE%\BeardedWolf\Sync.
2. Zaktualizuj kod repozytorium w Kali WSL i uruchom BeardedWolf Admin.
3. W zakładce **Synchronizacja** kliknij **Wykryj Windows** i **Lenovo: przyjmij dane z Syncthing**.
4. Oryginalne lokalne pliki sites.json i servers.json zostaną zachowane jako kopie *.pre-sync-adopt-*.bak; program nie nadpisuje ich bez kopii.
5. Po synchronizacji zobaczysz identyczne domeny, hostingi i profile SSH. Klucze prywatne nadal musisz skonfigurować osobno na Lenovo.

### Aktualizacja i rozwiązywanie konfliktów

Zmiana domeny, hostingu, powiązania profilu albo parametrów SSH jest od razu zapisywana do folderu Windows, następnie Syncthing przekazuje ją na drugie urządzenie. Kiedy aplikacja jest otwarta, wykrywa ją bez ręcznego kopiowania plików.

Nie zmieniaj tych samych wpisów równocześnie na obu komputerach. Jeśli Syncthing utworzy plik o nazwie zawierającej .sync-conflict-, BeardedWolf zatrzyma odczyty i zapisy, zamiast po cichu wybrać wersję. Porównaj obie wersje, wykonaj kopię, scal prawidłowe zmiany i dopiero rozwiąż konflikt.

Jeśli wspólny folder zniknie lub zostanie odmontowany, aplikacja zgłosi błąd. Nie przełącza się po cichu na przestarzałą lokalną konfigurację. Kopia lokalna pozostaje do odzyskiwania danych. **Syncthing nie zastępuje backupu**, warto włączyć wersjonowanie plików i niezależne kopie. Zadbaj o ochronę obu dysków; nawet bez haseł lista serwerów i loginy techniczne są informacją wrażliwą organizacyjnie.
