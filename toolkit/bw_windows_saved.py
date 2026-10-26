"""Use existing Windows credentials IN PLACE: FileZilla saved sites and OpenSSH.

The GUI never exports, decodes or prints saved passwords. FileZilla
authenticates from its own Windows Site Manager; Windows ssh.exe uses its
own config, ssh-agent and private keys. This is a local workflow.
"""
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from bw_filezilla import read_export


def _run_windows(args, timeout=8):
    return subprocess.run(args, capture_output=True, text=True,
                          timeout=timeout, check=True).stdout.strip()


def windows_config():
    """Resolve only active Windows user's configuration; not guessing usernames."""
    if not shutil.which("cmd.exe"):
        raise RuntimeError("Uruchom w Kali WSL z aktywna integracja Windows.")
    home = _run_windows(["cmd.exe", "/d", "/c", "echo %USERPROFILE%"])
    if not home or "%" in home or not re.match(r"^[A-Za-z]:\\", home):
        raise RuntimeError("Nie moge ustalic katalogu uzytkownika Windows.")
    linux_home = _run_windows(["wslpath", "-u", home])
    root = Path(linux_home)
    return root, root / "AppData" / "Roaming" / "FileZilla" / "sitemanager.xml"


def _folder_title(node):
    return (node.text or "").strip()


def _site_title(node):
    child = node.find("Name")
    return ((child.text or "").strip() if child is not None else ""
            ) or (node.text or "").strip()


def _escape_segment(name):
    # FileZilla CLI -c path syntax: backslash-escape / and \.
    return name.replace("\\", "\\\\").replace("/", "\\/")


def filezilla_sites(path):
    """Display names and saved-site identifiers only. No password access."""
    path = Path(path)
    if not path.is_file():
        return []
    # Existing password-safe parser handles size limits and DTD rejection.
    allowed = read_export(path)
    if not allowed:
        return []
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    servers = root.find("Servers")
    if servers is None:
        return []
    rows = []

    def traverse(node, prefix):
        for child in node:
            if child.tag == "Folder":
                name = _folder_title(child)
                if name:
                    traverse(child, prefix + [name])
            elif child.tag == "Server":
                name = _site_title(child)
                host = (child.findtext("Host") or "").strip()
                port = (child.findtext("Port") or "").strip()
                user = (child.findtext("User") or "").strip()
                protocol = (child.findtext("Protocol") or "").strip()
                if not name or not host:
                    continue
                # Only display connections already accepted by safe parser.
                if not any(a["host"] == host and str(a["port"]) ==
                           (port or str(22 if protocol == "1" else 21))
                           for a in allowed):
                    continue
                site_key = "0/" + "/".join(_escape_segment(n)
                                           for n in prefix + [name])
                if '"' in site_key or "\n" in site_key:
                    continue
                rows.append({
                    "name": name,
                    "path": site_key,
                    "host": host,
                    "user": user,
                    "port": port or ("22" if protocol == "1" else "21"),
                    "protocol": {"1": "SFTP", "0": "FTP", "3": "FTPS", "4": "FTPS"}.get(
                        protocol, "INNY"),
                    "source": "FileZilla Windows",
                })
    traverse(servers, [])
    return rows


def _filezilla_exe():
    home, _ = windows_config()
    # Official executable locations. Never download or install software.
    for path in (
        Path("/mnt/c/Program Files/FileZilla FTP Client/filezilla.exe"),
        Path("/mnt/c/Program Files (x86)/FileZilla FTP Client/filezilla.exe"),
        home / "AppData" / "Local" / "Programs" / "FileZilla FTP Client" / "filezilla.exe",
    ):
        if path.is_file():
            return path
    raise RuntimeError(
        "Nie wykrylem FileZilli w Windows. Sprawdz lokalizacje filezilla.exe."
    )


def open_filezilla_site(site):
    """Windows FileZilla retrieves password from its ORIGINAL saved site."""
    path = site.get("path", "")
    if not path.startswith("0/") or '"' in path or "\n" in path:
        raise ValueError("Nieprawidlowa sciezka zapisanego profilu FileZilla.")
    binary = _filezilla_exe()
    subprocess.Popen([str(binary), "-c", path],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def windows_ssh_aliases(config):
    """Only explicit alias names, no key material."""
    path = Path(config)
    if not path.is_file():
        return []
    aliases = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        found = re.match(r"^\s*Host\s+([a-zA-Z0-9_.-]+)\s*$", line, re.I)
        if found:
            alias = found.group(1)
            if "*" not in alias and "?" not in alias:
                aliases.append(alias)
    return sorted(set(aliases), key=str.casefold)


def connect_windows_ssh(alias):
    """Call Windows ssh.exe in a separate Windows terminal with existing keys."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", alias):
        raise ValueError("Niedozwolony alias SSH.")
    home, _ = windows_config()
    config = home / ".ssh" / "config"
    if alias not in windows_ssh_aliases(config):
        raise ValueError("Alias nie istnieje w Windows .ssh/config.")
    subprocess.Popen(["cmd.exe", "/d", "/c", "start", '""', "cmd.exe",
                      "/k", "ssh.exe", alias],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
