"""Lokalne profile SSH BeardedWolf, bez haseł i kluczy prywatnych w Git."""
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile
import bw_sync

CONFIG_DIR = Path.home() / ".config" / "beardedwolf"
PROFILE_FILE = CONFIG_DIR / "servers.json"
DEFAULT_PROFILE_FILE = PROFILE_FILE
SSH_DIR = Path.home() / ".ssh"
SSH_CONFIG = SSH_DIR / "config"

# Only this WSL instance; never stored in Syncthing or GitHub.
PAUSE_NAME = "ssh-disabled.local"


def ssh_paused():
    return (CONFIG_DIR / PAUSE_NAME).is_file()


def require_ssh_enabled():
    if ssh_paused():
        raise RuntimeError(
            "SSH wstrzymane lokalnie. Przywroc profile dopiero po sprawdzeniu kluczy i autoryzacji."
        )

BEGIN = "# BEGIN BEARDEDWOLF SERVERS"
END = "# END BEARDEDWOLF SERVERS"


def key_for(profile):
    """Separate protected ED25519 identity for each host alias."""
    return SSH_DIR / ("id_ed25519_bw_" + profile["alias"])


def validate(alias, host, user, port):
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,31}", alias):
        raise ValueError("Alias: litery/cyfry, '_' lub '-', bez spacji (maks. 32 znaki).")
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.-]{0,63}", user):
        raise ValueError("Nieprawidłowa nazwa konta SSH.")
    if len(host) > 253 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.:-]*", host):
        raise ValueError("Podaj poprawną nazwę hosta lub adres IP, bez protokołu.")
    try:
        num = int(port)
        if not 1 <= num <= 65535:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Port SSH musi mieć wartość od 1 do 65535.") from exc
    return dict(alias=alias, host=host, user=user, port=num)


def shared_profile_file():
    # Tests and explicit isolated configurations must never access a live share.
    if PROFILE_FILE != DEFAULT_PROFILE_FILE:
        return None
    return bw_sync.active_file("servers.json")


def load_profiles():
    shared = shared_profile_file()
    source = shared or PROFILE_FILE
    if not source.exists():
        return []
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Nieprawidłowy plik profili SSH")
    profiles = [validate(x["alias"], x["host"], x["user"], x["port"]) for x in data]
    if shared is not None:
        # Recreate only the BeardedWolf-owned SSH configuration section on this
        # machine. The IdentityFile paths are machine-local; keys are never synced.
        desired = make_ssh_config([] if ssh_paused() else profiles)
        current = SSH_CONFIG.read_text(encoding="utf-8") if SSH_CONFIG.exists() else ""
        if desired != current:
            if SSH_CONFIG.is_symlink():
                raise RuntimeError("~/.ssh/config jest dowiązaniem symbolicznym.")
            SSH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            SSH_DIR.chmod(0o700)
            if SSH_CONFIG.is_file():
                backup = SSH_DIR / "config.beardedwolf.previous.bak"
                if backup.is_symlink():
                    raise RuntimeError("Kopia SSH config jest dowiązaniem symbolicznym.")
                shutil.copy2(SSH_CONFIG, backup)
                backup.chmod(0o600)
            atomic_save(SSH_CONFIG, desired)
    return profiles


def atomic_save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path == SSH_CONFIG:
        SSH_DIR.chmod(0o700)
    fd, temp = tempfile.mkstemp(prefix=".bw-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def make_ssh_config(profiles):
    existing = SSH_CONFIG.read_text(encoding="utf-8") if SSH_CONFIG.exists() else ""
    if existing.count(BEGIN) != existing.count(END) or existing.count(BEGIN) > 1:
        raise ValueError("Uszkodzone znaczniki sekcji BeardedWolf w ~/.ssh/config")
    base = existing
    if BEGIN in existing:
        base = re.sub(r"(?ms)^" + re.escape(BEGIN) + r"\n.*?^" +
                      re.escape(END) + r"\n?", "", existing)
        if BEGIN in base or END in base:
            raise ValueError("Nie udało się poprawnie odtworzyć ~/.ssh/config")
    other_aliases = set()
    for raw in re.findall(r"(?im)^\s*Host\s+(.+)$", base):
        other_aliases.update(raw.lower().split())
    for entry in profiles:
        if entry["alias"].lower() in other_aliases:
            raise ValueError(f"Alias {entry['alias']} jest już używany w ~/.ssh/config")
    blocks = [BEGIN]
    for p in profiles:
        blocks.extend([
            f"Host {p['alias']}",
            f"    HostName {p['host']}",
            f"    User {p['user']}",
            f"    Port {p['port']}",
            f"    IdentityFile {key_for(p)}",
            "    IdentitiesOnly yes",
            "    AddKeysToAgent yes",
            "    ForwardAgent no",
            "    ServerAliveInterval 30",
            "    ServerAliveCountMax 3",
            "",
        ])
    blocks.append(END)
    # SSH uses the first matching value. Put specific aliases BEFORE user Host * defaults.
    return "\n".join(blocks) + "\n\n" + base.lstrip("\n")


def save_profiles(profiles):
    """Zapisz lokalne profile i sekcję SSH, nie dotykając kluczy ani serwerów."""
    if SSH_CONFIG.is_symlink() or PROFILE_FILE.is_symlink():
        raise ValueError("Pliki konfiguracyjne są dowiązaniami symbolicznymi; wymagana ręczna kontrola.")
    if len({p["alias"].lower() for p in profiles}) != len(profiles):
        raise ValueError("Alias musi być unikatowy.")
    config = make_ssh_config([] if ssh_paused() else profiles)
    SSH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    SSH_DIR.chmod(0o700)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    CONFIG_DIR.chmod(0o700)
    if SSH_CONFIG.exists():
        initial = SSH_DIR / "config.beardedwolf.original.bak"
        if not initial.exists():
            shutil.copy2(SSH_CONFIG, initial)
            initial.chmod(0o600)
        backup = SSH_DIR / "config.beardedwolf.previous.bak"
        shutil.copy2(SSH_CONFIG, backup)
        backup.chmod(0o600)
    if PROFILE_FILE.exists():
        backup = CONFIG_DIR / "servers.json.previous.bak"
        shutil.copy2(PROFILE_FILE, backup)
        backup.chmod(0o600)
    atomic_save(SSH_CONFIG, config)
    destination = shared_profile_file() or PROFILE_FILE
    atomic_save(destination, json.dumps(profiles, ensure_ascii=False, indent=2) + "\n")


def add_profile(alias, host, user, port):
    profile = validate(alias.strip(), host.strip(), user.strip(), port)
    profiles = load_profiles()
    if any(x["alias"].lower() == profile["alias"].lower() for x in profiles):
        raise ValueError("Alias jest już skonfigurowany. Wybierz inną nazwę.")
    save_profiles(profiles + [profile])
    return profile


def update_profile(alias, host, user, port):
    """Edytuj adres, login i port, zachowując alias i przypisany klucz SSH."""
    profiles = load_profiles()
    index = next((i for i, p in enumerate(profiles) if p["alias"] == alias), None)
    if index is None:
        raise ValueError(f"Profil {alias} nie istnieje.")
    updated = validate(alias, host.strip(), user.strip(), port)
    profiles[index] = updated
    save_profiles(profiles)
    return updated


def delete_profile(alias):
    """Usuń tylko lokalny profil i alias SSH; nie kasuj żadnych kluczy."""
    profiles = load_profiles()
    remaining = [p for p in profiles if p["alias"] != alias]
    if len(remaining) == len(profiles):
        raise ValueError(f"Profil {alias} nie istnieje.")
    save_profiles(remaining)


def terminal(args, *, title="BeardedWolf SSH", use_agent=False):
    if not shutil.which("xfce4-terminal"):
        raise RuntimeError("Brak xfce4-terminal. Uruchom narzędzie w pulpicie Kali XFCE.")
    command = shlex.join([str(x) for x in args])
    if use_agent:
        # Keychain stores agent metadata locally. Passphrase never enters a command argument.
        command = 'eval "$(keychain --eval --quiet --noask)" || exit 1; exec ' + command
        argv = ["bash", "-c", command]
    else:
        argv = list(map(str, args))
    subprocess.Popen([
        "xfce4-terminal", "--disable-server", "--hold",
        "--title=" + title, "--command=" + shlex.join(argv)
    ], start_new_session=True)


def create_key(profile):
    key_file = key_for(profile)
    if key_file.exists() or Path(str(key_file) + ".pub").exists():
        raise ValueError("Klucz dla tego serwera już istnieje. Nie nadpisuję go.")
    SSH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    SSH_DIR.chmod(0o700)
    terminal(["ssh-keygen", "-t", "ed25519", "-a", "100", "-f", str(key_file),
              "-C", "BeardedWolf-" + profile["alias"]],
             title="Nowy klucz SSH: " + profile["alias"])


def install_public_key(profile):
    require_ssh_enabled()
    public_key = Path(str(key_for(profile)) + ".pub")
    if not public_key.is_file():
        raise ValueError("Najpierw wygeneruj klucz SSH do serwerów.")
    terminal(["ssh-copy-id", "-i", str(public_key), "-p",
              str(profile["port"]), profile["user"] + "@" + profile["host"]],
             title="Jednorazowe dodanie klucza SSH", use_agent=False)


def connect(profile):
    require_ssh_enabled()
    if not key_for(profile).is_file():
        raise ValueError("Najpierw wygeneruj osobny klucz SSH do serwerów.")
    terminal(["ssh", profile["alias"]], title="SSH: " + profile["alias"], use_agent=True)


def verify_connection(profile):
    require_ssh_enabled()
    if not shutil.which("keychain"):
        raise RuntimeError("Brak pakietu keychain.")
    cmd = 'eval "$(keychain --eval --quiet --noask)" || exit 1; ' + shlex.join(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", profile["alias"], "exit"]
    )
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=15)
    return result.returncode == 0, (result.stderr or result.stdout).strip()
