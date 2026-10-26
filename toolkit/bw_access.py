"""Local BeardedWolf SSH metadata review, without passwords or remote calls."""
import argparse
import json
from pathlib import Path
import re
import socket

import bw_servers


def parse_ssh_config(path):
    """Only allowlisted Host metadata; never read or export key material."""
    rows = []
    current = None
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or line.lstrip().startswith("#"):
            continue
        key, value = parts[0].lower(), parts[1].strip()
        if key == "host":
            aliases = value.split()
            current = None
            if len(aliases) == 1 and re.fullmatch(
                    r"[a-zA-Z][a-zA-Z0-9_-]{0,31}", aliases[0]):
                current = {"alias": aliases[0], "host": "",
                           "user": "", "port": 22, "protocol": "ssh"}
                rows.append(current)
        elif key == "match":
            # Conditional Match directives do not belong to a global Host profile.
            current = None
        elif current is not None and key in ("hostname", "user", "port"):
            if key == "hostname":
                current["host"] = value
            elif key == "user":
                current["user"] = value
            else:
                try:
                    current["port"] = int(value)
                except ValueError:
                    current["port"] = None
    return [r for r in rows if r["host"]]


def inventory():
    """Loaded BeardedWolf profiles plus unrelated user-configured SSH aliases."""
    rows = [dict(p, protocol="ssh", source="beardedwolf")
            for p in bw_servers.load_profiles()]
    seen = {r["alias"].lower() for r in rows}
    for p in parse_ssh_config(Path.home() / ".ssh" / "config"):
        if p["alias"].lower() not in seen:
            rows.append(dict(p, source="openssh"))
    return rows


def inspect(records):
    """Prepare import decisions; do not change the user's SSH setup."""
    known = {p["alias"]: p for p in bw_servers.load_profiles()}
    findings = []
    for row in records:
        if row.get("protocol") not in ("ssh", None):
            state = "SKIP_PROTOCOL"
        else:
            try:
                profile = bw_servers.validate(row["alias"], row["host"],
                                              row["user"], row["port"])
                old = known.get(profile["alias"])
                state = "SAME" if old == profile else (
                    "CONFLICT" if old else "NEW")
            except (ValueError, KeyError, TypeError):
                state = "INCOMPLETE"
        findings.append({"state": state, "alias": row.get("alias"),
                         "host": row.get("host"), "user": row.get("user"),
                         "port": row.get("port"), "source": row.get("source")})
    return findings


def main():
    parser = argparse.ArgumentParser(description="Lokalna inwentaryzacja metadanych SSH")
    parser.add_argument("mode", choices=["export", "review"])
    parser.add_argument("path", type=Path, help="Lokalny plik JSON bez haseł")
    args = parser.parse_args()
    if args.mode == "export":
        if args.path.exists():
            raise ValueError("Plik już istnieje, nie nadpisuję: " + str(args.path))
        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_text(json.dumps({
            "schema": 1, "device": socket.gethostname(),
            "profiles": inventory()
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.path.chmod(0o600)
        print("Zapisano metadane połączeń, bez haseł i kluczy:", args.path)
    else:
        data = json.loads(args.path.read_text(encoding="utf-8-sig"))
        if data.get("schema") != 1 or not isinstance(data.get("profiles"), list):
            raise ValueError("Nieobsługiwany format pliku.")
        for item in inspect(data["profiles"]):
            print("{state:>13}  {alias}  {user}@{host}:{port}  ({source})".format(**item))
        print("Tryb tylko do odczytu. Wspólny rejestr Syncthing nie został zmieniony.")


if __name__ == "__main__":
    main()
