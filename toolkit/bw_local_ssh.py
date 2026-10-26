"""Device-local quarantine of BeardedWolf-generated SSH aliases.

Never deletes credentials, server inventory, WordPress site assignments or
Syncthing files. Makes a rollback snapshot outside synchronized folders.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

import bw_servers
import bw_sync


def marker():
    return bw_servers.CONFIG_DIR / bw_servers.PAUSE_NAME


def archive_copy(source, directory, label):
    if source.is_symlink():
        raise RuntimeError("Odmowa kopiowania dowiazania: " + str(source))
    if source.is_file():
        destination = directory / label
        shutil.copy2(source, destination)
        destination.chmod(0o600)
        return True
    return False


def backup():
    folder = Path.home() / ".local" / "state" / "beardedwolf" / "ssh-backups"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    snapshot = folder / stamp
    snapshot.mkdir(mode=0o700)
    archive_copy(bw_servers.SSH_CONFIG, snapshot, "ssh-config")
    archive_copy(bw_servers.PROFILE_FILE, snapshot, "local-servers.json")
    shared = bw_sync.active_file("servers.json")
    if shared is not None:
        archive_copy(shared, snapshot, "syncthing-servers.json")
    return snapshot


def pause():
    flag = marker()
    if flag.is_symlink():
        raise RuntimeError("Plik blokady jest dowiazaniem. Przerwano.")
    if flag.exists():
        print("Polaczenia BeardedWolf sa juz wstrzymane na tym Kali.")
        return
    snapshot = backup()
    flag.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flag.write_text("Device-local SSH pause; no synchronization.\n", encoding="utf-8")
    flag.chmod(0o600)
    try:
        profiles = bw_servers.load_profiles()
    except Exception:
        flag.unlink(missing_ok=True)
        raise
    print("WSTRZYMANO lokalne aliasy SSH BeardedWolf:", len(profiles))
    print("Kopia zapasowa:", snapshot)
    print("Nie usunieto profili Syncthing, przypisan domen ani kluczy SSH.")
    print("Inne wpisy uzytkownika w ~/.ssh/config pozostaly nietkniete.")


def resume():
    flag = marker()
    if not flag.is_file() or flag.is_symlink():
        print("Brak lokalnej blokady BeardedWolf SSH.")
        return
    flag.unlink()
    try:
        profiles = bw_servers.load_profiles()
    except Exception:
        flag.write_text("Restored after unsuccessful resume.\n", encoding="utf-8")
        flag.chmod(0o600)
        raise
    print("PRZYWROCONO lokalne aliasy SSH BeardedWolf:", len(profiles))
    print("Klucze nie byly modyfikowane. Polaczenia wymagaja testu.")


def status():
    flag = marker()
    profiles = bw_servers.load_profiles()
    print("Kali:", "WSTRZYMANE" if flag.is_file() else "AKTYWNE")
    print("Wspolne profile (zachowane):", len(profiles))
    available = sum(bw_servers.key_for(p).is_file() for p in profiles)
    print("Profile z plikiem lokalnego klucza prywatnego:", available, "/", len(profiles))
    print("To nie potwierdza prawidlowosci kluczy ani dostepu do serwerow.")


def main():
    parser = argparse.ArgumentParser(description="Lokalne wstrzymanie SSH BeardedWolf")
    parser.add_argument("action", choices=["pause", "resume", "status"])
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if args.action != "status" and not args.yes:
        parser.error("Dodaj --yes po zatwierdzeniu tej operacji.")
    if args.action == "pause":
        pause()
    elif args.action == "resume":
        resume()
    else:
        status()


if __name__ == "__main__":
    main()
