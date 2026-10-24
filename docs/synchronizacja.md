# Synchronizacja dwoch komputerow z Windows i Kali WSL 2

Status: projekt konfiguracji. Samo dodanie tego pliku NIE uruchamia synchronizacji.

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
