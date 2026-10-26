"""BeardedWolf Admin: shared non-secret fleet metadata through Syncthing.

GitHub only contains code. Windows Syncthing folder synchronizes Admin/sites.json
and Admin/servers.json. Never exports passwords, tokens, SSH keys or ~/.ssh/config.
Activation is opt-in and does not silently overwrite an existing shared inventory.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

CONFIG = Path.home() / ".config" / "beardedwolf" / "sync.json"
FILES = ("sites.json", "servers.json")
SITE_FIELDS = ("id", "domain", "group", "type", "public_checks", "authorized",
               "ssh_alias", "wp_root")
HOST_FIELDS = ("provider", "access", "host", "port", "user")


def detect_windows_sync_root():
    """Find the per-user Windows Syncthing folder. No hard-coded Windows username."""
    powershell = shutil.which("powershell.exe")
    wslpath = shutil.which("wslpath")
    if not powershell or not wslpath:
        raise RuntimeError("Autowykrywanie folderu Syncthing wymaga Windows + WSL.")
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command",
         'Join-Path $env:USERPROFILE "BeardedWolf\\Sync"'],
        capture_output=True, text=True, timeout=12, check=True
    )
    windows_folder = result.stdout.strip()
    if not windows_folder:
        raise RuntimeError("Windows nie zwrócił ścieżki BeardedWolf\\Sync.")
    result = subprocess.run(
        [wslpath, "-u", windows_folder], capture_output=True,
        text=True, timeout=10, check=True
    )
    root = Path(result.stdout.strip())
    if not root.is_dir():
        raise RuntimeError("Folder Syncthing nie istnieje: " + str(root) +
                           ". Skonfiguruj jego synchronizację na tym komputerze.")
    return root


def _config():
    if not CONFIG.is_file():
        return None
    if CONFIG.is_symlink():
        raise RuntimeError("Konfiguracja synchronizacji jest dowiązaniem symbolicznym.")
    value = json.loads(CONFIG.read_text(encoding="utf-8"))
    if value.get("schema") != 1 or not isinstance(value.get("root"), str):
        raise ValueError("Nieznany format konfiguracji synchronizacji.")
    return value


def shared_dir():
    data = _config()
    if data is None:
        return None
    root = Path(data["root"]).expanduser()
    if not root.is_dir():
        raise RuntimeError(
            "Folder Syncthing jest niedostępny: " + str(root) +
            ". Nie przełączam się po cichu na nieaktualne dane lokalne."
        )
    parent = root / "Admin"
    if not parent.is_dir() or parent.is_symlink():
        raise RuntimeError("Brak katalogu Admin w skonfigurowanej synchronizacji.")
    return parent


def conflict_files(folder):
    """Syncthing creates .sync-conflict files when the same file changes on 2 PCs."""
    return sorted(p.name for p in folder.iterdir()
                  if p.is_file() and ".sync-conflict-" in p.name
                  and (p.name.startswith("sites") or p.name.startswith("servers")))


def active_file(name):
    if name not in FILES:
        raise ValueError("Synchronizacja obejmuje tylko serwisy i metadane profili SSH.")
    folder = shared_dir()
    if folder is None:
        return None
    conflicts = conflict_files(folder)
    if conflicts:
        raise RuntimeError(
            "Syncthing wykrył konflikt edycji. Nie nadpisuję żadnej wersji: " +
            ", ".join(conflicts) + ". Rozstrzygnij konflikt na dysku."
        )
    target = folder / name
    if target.is_symlink() or not target.is_file():
        raise RuntimeError("Brak bezpiecznego pliku synchronizacji: " + str(target))
    return target


def _write_json(path, payload):
    if path.is_symlink():
        raise RuntimeError("Odmowa nadpisania dowiązania symbolicznego: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".beardedwolf-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def safe_sites(payload):
    """Whitelist metadata: unknown keys and free-form notes never enter Syncthing."""
    if not isinstance(payload, dict) or not isinstance(payload.get("sites"), list):
        raise ValueError("Nieprawidłowa lista serwisów.")
    sites = []
    seen = set()
    for entry in payload["sites"]:
        if not isinstance(entry, dict):
            raise ValueError("Nieprawidłowy wpis serwisu.")
        domain = entry.get("domain")
        if not isinstance(domain, str) or not domain or domain in seen:
            raise ValueError("Duplikat lub brak domeny w synchronizacji.")
        if len(domain) > 253 or not all(c.isascii() and
                                         (c.isalnum() or c in ".-") for c in domain):
            raise ValueError("Nieprawidłowa domena w synchronizacji.")
        seen.add(domain)
        row = {key: entry.get(key) for key in SITE_FIELDS}
        row["id"] = domain
        hosting = entry.get("hosting") or {}
        if not isinstance(hosting, dict):
            raise ValueError("Nieprawidłowy opis hostingu.")
        row["hosting"] = {key: hosting.get(key) for key in HOST_FIELDS}
        # Notes may accidentally contain access codes or private incident details.
        # They stay device-local and are intentionally excluded from shared metadata.
        sites.append(row)
    return {"schema": 1, "sites": sites}


def safe_profiles(profiles):
    """Only SSH aliases/endpoints, never private keys, passwords or config."""
    if not isinstance(profiles, list):
        raise ValueError("Nieprawidłowa lista profili.")
    # Lazy import: bw_servers uses this module as a backend.
    import bw_servers
    checked = [
        bw_servers.validate(p["alias"], p["host"], p["user"], p["port"])
        for p in profiles
    ]
    if len({p["alias"].lower() for p in checked}) != len(checked):
        raise ValueError("Powtórzony alias SSH.")
    return checked


def _backup_local(local_file, suffix):
    if local_file.is_file():
        if local_file.is_symlink():
            raise RuntimeError("Odmowa wykonania kopii dowiązania " + str(local_file))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        path = local_file.with_name(local_file.name + ".pre-sync-" + suffix +
                                     "-" + stamp + ".bak")
        shutil.copy2(local_file, path)
        path.chmod(0o600)
        return path
    return None


def enable(root, mode, local_sites, local_servers):
    """'publish' from original PC, or 'adopt' canonical Syncthing state on another."""
    if mode not in ("publish", "adopt"):
        raise ValueError("Tryb: publish albo adopt.")
    folder = Path(root).expanduser().resolve()
    if folder.name.lower() != "sync" or not folder.is_dir():
        raise RuntimeError("Wskaż istniejący folder BeardedWolf/Sync na Windows.")
    admin = folder / "Admin"
    if admin.is_symlink():
        raise RuntimeError("Katalog Admin nie może być dowiązaniem symbolicznym.")
    admin.mkdir(mode=0o700, exist_ok=True)
    if conflict_files(admin):
        raise RuntimeError("Syncthing ma nierozstrzygnięte konflikty; włączanie przerwane.")
    sites_path = admin / "sites.json"
    servers_path = admin / "servers.json"
    if sites_path.is_symlink() or servers_path.is_symlink():
        raise RuntimeError("Nie używam synchronizowanych dowiązań symbolicznych.")
    old = _config()
    if old is not None:
        raise RuntimeError("Synchronizacja jest już aktywna na tym urządzeniu.")
    backups = []
    if mode == "publish":
        if sites_path.exists() or servers_path.exists():
            raise RuntimeError(
                "Dane w Syncthing już istnieją. Nie nadpisuję ich. "
                "Na drugim komputerze wybierz 'Przyjmij z Syncthing'."
            )
        sites = safe_sites(json.loads(Path(local_sites).read_text(encoding="utf-8")))
        raw_profiles = (json.loads(Path(local_servers).read_text(encoding="utf-8"))
                        if Path(local_servers).exists() else [])
        profiles = safe_profiles(raw_profiles)
        import bw_servers
        bw_servers.make_ssh_config(profiles)  # Preflight: do not publish broken aliases.
        backups.extend(filter(None, (
            _backup_local(Path(local_sites), "publish"),
            _backup_local(Path(local_servers), "publish")
        )))
        # Write the pair before switching the active data source.
        _write_json(sites_path, sites)
        _write_json(servers_path, profiles)
    else:
        if not sites_path.is_file() or not servers_path.is_file():
            raise RuntimeError(
                "Syncthing nie przekazał jeszcze plików Admin/sites.json i "
                "Admin/servers.json z PC-Wilk. Nie nadpisuję lokalnej konfiguracji."
            )
        safe_sites(json.loads(sites_path.read_text(encoding="utf-8")))
        profiles = safe_profiles(json.loads(servers_path.read_text(encoding="utf-8")))
        import bw_servers
        bw_servers.make_ssh_config(profiles)  # Detect duplicate aliases before enabling.
        backups.extend(filter(None, (
            _backup_local(Path(local_sites), "adopt"),
            _backup_local(Path(local_servers), "adopt")
        )))
    _write_json(CONFIG, {"schema": 1, "root": str(folder)})
    return {
        "mode": mode, "folder": str(admin),
        "local_backups": [str(x) for x in backups]
    }


def status():
    try:
        settings = _config()
    except (OSError, ValueError, RuntimeError) as exc:
        return {"enabled": True, "ready": False,
                "message": "Błąd konfiguracji synchronizacji: " + str(exc)}
    if not settings:
        return {"enabled": False, "message": "Nie skonfigurowano."}
    try:
        folder = shared_dir()
        files = [active_file(x) for x in FILES]
        if any(not f.is_file() for f in files):
            raise RuntimeError("Brakuje plików synchronizacji.")
        return {"enabled": True, "ready": True, "folder": str(folder),
                "message": "Lokalne pliki Syncthing dostępne. "
                           "Stan połączenia Syncthing z Lenovo nie jest weryfikowany."}
    except (OSError, ValueError, RuntimeError) as exc:
        return {"enabled": True, "ready": False, "message": str(exc)}
