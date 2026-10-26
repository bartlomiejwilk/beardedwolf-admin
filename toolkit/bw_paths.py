"""Explicit, read-only remote WordPress path discovery.

SSH uses existing OpenSSH host-key and key auth; FTPS prompts locally for the
password and requires TLS. No wp-config.php content, no FTP upload, no writes.
"""
import argparse
from collections import deque
from ftplib import FTP_TLS, error_perm
from getpass import getpass
from pathlib import PurePosixPath
import shlex
import ssl
import subprocess

import bw_servers

LIMIT = 40


def ssh_roots(alias, depth=5):
    profiles = {p["alias"]: p for p in bw_servers.load_profiles()}
    if alias not in profiles:
        raise ValueError("Nie ma tego profilu SSH w panelu.")
    depth = max(2, min(6, int(depth)))
    # Single bounded listing, read-only, never print wp-config.php or read files.
    find = ('find "$HOME" -maxdepth ' + str(depth) +
            ' -type f -path "*/wp-includes/version.php" -print 2>/dev/null')
    try:
        result = subprocess.run([
            "ssh", "-T", "-o", "BatchMode=yes", "-o",
            "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8",
            "-o", "IdentitiesOnly=yes", alias, "sh -c " + shlex.quote(find)
        ], text=True, capture_output=True, timeout=35, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Przekroczono limit 35 s. Zawęź zakres, bez ponawiania dużych skanów.") from exc
    if result.returncode not in (0, 1):
        raise RuntimeError("SSH niedostępne lub odmowa dostępu. Sprawdź profil i klucz lokalnie.")
    matches = []
    for line in result.stdout.splitlines():
        marker = "/wp-includes/version.php"
        if line.endswith(marker):
            path = str(PurePosixPath(line[:-len(marker)]))
            if path.startswith("/") and path not in matches:
                matches.append(path)
        if len(matches) >= LIMIT:
            break
    return matches


def _list_dirs(ftp):
    try:
        return sorted(name for name, facts in ftp.mlsd()
                      if facts.get("type") == "dir" and name not in (".", ".."))
    except (error_perm, AttributeError):
        return []


def ftps_roots(host, user, password, base="/", depth=3):
    """FTPS directory names only. No content retrieval, no insecure FTP downgrade."""
    if not host or not user:
        raise ValueError("FTPS wymaga hosta i użytkownika.")
    context = ssl.create_default_context()
    found = []
    explored = 0
    ftp = FTP_TLS(context=context, timeout=8)
    try:
        ftp.connect(host=host, port=21, timeout=8)
        ftp.login(user=user, passwd=password)
        ftp.prot_p()
        queue = deque([(base, 0)])
        while queue and explored < 120 and len(found) < LIMIT:
            folder, level = queue.popleft()
            try:
                ftp.cwd(folder)
                names = _list_dirs(ftp)
            except (error_perm, OSError):
                continue
            explored += 1
            if "wp-includes" in names and "wp-admin" in names:
                found.append(folder)
            if level < max(1, min(4, depth)):
                for name in names:
                    if name.startswith(".") or "/" in name or "\\" in name:
                        continue
                    queue.append((str(PurePosixPath(folder) / name), level + 1))
    finally:
        try:
            ftp.quit()
        except (OSError, EOFError):
            ftp.close()
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Odczyt katalogów WordPress przez SSH lub szyfrowany FTPS"
    )
    parser.add_argument("protocol", choices=("ssh", "ftps"))
    parser.add_argument("target", help="Alias SSH albo serwer FTPS")
    parser.add_argument("--user", help="Login FTPS")
    parser.add_argument("--base", default="/", help="Początkowy katalog FTPS")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--ack", action="store_true",
                        help="Potwierdzam uprawnienia do odczytu katalogów")
    args = parser.parse_args()
    if not args.ack:
        parser.error("Podaj --ack po potwierdzeniu uprawnień. Nic nie uruchomiono.")
    if args.protocol == "ssh":
        paths = ssh_roots(args.target, args.depth)
    else:
        if not args.user:
            parser.error("FTPS wymaga --user. Hasło zostanie zapytane lokalnie.")
        paths = ftps_roots(args.target, args.user, getpass("Hasło FTPS: "),
                           args.base, args.depth)
    print("Katalogi z rozpoznanymi strukturami WordPress:", len(paths))
    for path in paths:
        print("  ", path)
    print("Nie zmieniono żadnych plików ani przypisań w BeardedWolf Admin.")


if __name__ == "__main__":
    main()
