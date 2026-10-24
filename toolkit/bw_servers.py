"""Lokalne profile SSH BeardedWolf, bez haseł i kluczy prywatnych w Git."""
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile

CONFIG_DIR = Path.home() / ".config" / "beardedwolf"
PROFILE_FILE = CONFIG_DIR / "servers.json"
SSH_DIR = Path.home() / ".ssh"
SSH_CONFIG = SSH_DIR / "config"
KEY_FILE = SSH_DIR / "id_ed25519_bw_servers"
BEGIN = "# BEGIN BEARDEDWOLF SERVERS"
END = "# END BEARDEDWOLF SERVERS"


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


def load_profiles():
    if not PROFILE_FILE.exists():
        return []
    data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Nieprawidłowy plik profili SSH")
    return [validate(x["alias"], x["host"], x["user"], x["port"]) for x in data]


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
            f"    IdentityFile {KEY_FILE}",
            "    IdentitiesOnly yes",
            "    AddKeysToAgent yes",
            "    ForwardAgent no",
            "    ServerAliveInterval 30",
            "    ServerAliveCountMax 3",
            "",
        ])
    blocks.append(END)
    # Preserve preexisting user-defined configuration outside our block.
    return base.rstrip("\n") + ("\n\n" if base.strip() else "") + "\n".join(blocks) + "\n"


def add_profile(alias, host, user, port):
    profile = validate(alias.strip(), host.strip(), user.strip(), port)
    profiles = load_profiles()
    if any(x["alias"].lower() == profile["alias"].lower() for x in profiles):
        raise ValueError("Alias jest już skonfigurowany. Wybierz inną nazwę.")
    new_profiles = profiles + [profile]
    config = make_ssh_config(new_profiles)
    atomic_save(SSH_CONFIG, config)
    atomic_save(PROFILE_FILE, json.dumps(new_profiles, ensure_ascii=False, indent=2) + "\n")
    return profile


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


def create_key():
    if KEY_FILE.exists() or Path(str(KEY_FILE) + ".pub").exists():
        raise ValueError("Klucz BeardedWolf SSH już istnieje. Nie nadpisuję go.")
    SSH_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    SSH_DIR.chmod(0o700)
    terminal(["ssh-keygen", "-t", "ed25519", "-a", "100", "-f", str(KEY_FILE),
              "-C", "BeardedWolf-Admin"], title="Nowy klucz serwerów SSH")


def install_public_key(profile):
    public_key = Path(str(KEY_FILE) + ".pub")
    if not public_key.is_file():
        raise ValueError("Najpierw wygeneruj klucz SSH do serwerów.")
    terminal(["ssh-copy-id", "-i", str(public_key), "-p",
              str(profile["port"]), profile["user"] + "@" + profile["host"]],
             title="Jednorazowe dodanie klucza SSH", use_agent=False)


def connect(profile):
    if not KEY_FILE.is_file():
        raise ValueError("Najpierw wygeneruj osobny klucz SSH do serwerów.")
    terminal(["ssh", profile["alias"]], title="SSH: " + profile["alias"], use_agent=True)


def verify_connection(profile):
    if not shutil.which("keychain"):
        raise RuntimeError("Brak pakietu keychain.")
    cmd = 'eval "$(keychain --eval --quiet --noask)" || exit 1; ' + shlex.join(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", profile["alias"], "exit"]
    )
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=15)
    return result.returncode == 0, (result.stderr or result.stdout).strip()
