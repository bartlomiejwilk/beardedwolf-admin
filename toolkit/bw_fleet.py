#!/usr/bin/env python3
"""BeardedWolf Admin - rejestr serwisów, pasywne kontrole i zatwierdzane baseline.
Nie łączy się przez SSH, nie modyfikuje serwisów i nie synchronizuje raportów.
"""
import argparse
from datetime import datetime, timezone
from html import escape
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import re
import shutil
from pathlib import Path
from pathlib import PurePosixPath
import bw_servers
import bw_discover
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = Path.home() / ".config" / "beardedwolf"
SITES_FILE = SETTINGS / "sites.json"
CATALOG_FILE = ROOT / "config" / "checks.json"
INITIAL_SITES = ROOT / "config" / "sites.json"
HOSTING_DEFAULTS = ROOT / "config" / "hosting-defaults.json"
REPORT_DIR = Path.home() / "beardedwolf" / "raporty" / "FLEET"

loader = SourceFileLoader("bw_fleet_base", str(ROOT / "toolkit" / "bw"))
spec = importlib.util.spec_from_loader("bw_fleet_base", loader)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.7",
}
ALLOWED_TYPES = {"wordpress", "aplikacja", "przekierowanie", "sprawdzic"}

# Powiązania znane z wcześniejszej konfiguracji kont OVH. TYLKO podpowiedzi.
# Nie przypisujemy hostingu automatycznie, nie zapisujemy ścieżek bez weryfikacji.
SSH_SUGGESTIONS = {
    "beardedwolf.pl": "jaslo",
    "art.beardedwolf.pl": "jaslo",
    "labdostepnosci.pl": "jaslo",
    "szeptogra.pl": "jaslo",
    "jdkjaslo.pl": "jdk",
    "kino.jdkjaslo.pl": "jdk",
}



def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise RuntimeError(f"Nie zapisuję do dowiązania symbolicznego: {path}")
    if path == SITES_FILE and path.is_file():
        backup = path.with_name("sites.json.previous.bak")
        if backup.is_symlink():
            raise RuntimeError("Kopia rejestru serwisów jest dowiązaniem symbolicznym")
        shutil.copy2(path, backup)
        backup.chmod(0o600)
    fd, tmp = tempfile.mkstemp(prefix=".bw-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


HOSTING_ACCESS = {"unknown", "ssh", "ftp", "ftps", "sftp"}


def normalize_hosting(provider=None, access="unknown", host=None, port=None, user=None):
    """Keep server metadata separate from site platform and SSH authorization."""
    provider = (provider or "nieustalony").strip()
    if not provider or len(provider) > 80 or any(ord(x) < 32 or ord(x) == 127 for x in provider):
        raise ValueError("Nieprawidłowa nazwa dostawcy hostingu")
    if access not in HOSTING_ACCESS:
        raise ValueError("Dostęp musi być SSH, FTP, FTPS, SFTP lub nieustalony")
    host = (host or "").strip() or None
    if host and (len(host) > 253 or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9.:-]*", host)):
        raise ValueError("Adres hosta musi być nazwą DNS lub adresem IP bez loginu i schematu URL")
    if port in ("", None):
        port = None
    else:
        try:
            port = int(port)
        except (ValueError, TypeError) as exc:
            raise ValueError("Port musi być liczbą od 1 do 65535") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Port musi być liczbą od 1 do 65535")
    if port is not None and not host:
        raise ValueError("Nie podawaj portu bez adresu hosta")
    user = (user or "").strip() or None
    if user and (len(user) > 90 or not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.@-]*", user)):
        raise ValueError("Nieprawidłowy login serwera; nie wpisuj hasła ani adresu URL")
    return {"provider": provider, "access": access, "host": host, "port": port, "user": user}


def hosting_defaults():
    raw = json.loads(HOSTING_DEFAULTS.read_text(encoding="utf-8"))["sites"]
    return {domain: normalize_hosting(**details) for domain, details in raw.items()}


def hosting_info(site):
    """Read stored metadata, compatible with older local inventories."""
    raw = site.get("hosting")
    return normalize_hosting(**raw) if raw else normalize_hosting()


def inventory():
    if not SITES_FILE.exists():
        defaults = json.loads(INITIAL_SITES.read_text(encoding="utf-8"))
        atomic_json(SITES_FILE, defaults)
    payload = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    rows = payload["sites"]
    defaults = hosting_defaults()
    migrated = False
    for site in rows:
        if "hosting" not in site:
            site["hosting"] = dict(defaults.get(site["domain"], normalize_hosting()))
            migrated = True
    if migrated:
        # One-time extension of the local inventory, preserving user edits and SSH mappings.
        atomic_json(SITES_FILE, payload)
    seen = set()
    for site in rows:
        domain = base.domain_name(site["domain"])
        if domain in seen:
            raise ValueError("Duplikat domeny w rejestrze: " + domain)
        seen.add(domain)
        if domain != site["domain"]:
            raise ValueError("Domena musi być znormalizowana: " + domain)
        if site["type"] not in ALLOWED_TYPES:
            raise ValueError("Nieznany typ serwisu: " + site["type"])
    return payload


def catalog():
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))["checks"]


def get_site(domain):
    domain = base.domain_name(domain)
    for site in inventory()["sites"]:
        if site["domain"] == domain:
            return site
    raise ValueError("Brak domeny w rejestrze: " + domain)


def add_site(domain, group, platform):
    domain = base.domain_name(domain)
    group = group.strip()
    if not group or len(group) > 64 or any(c in group for c in "\r\n<>"):
        raise ValueError("Podaj prawidłową nazwę grupy (do 64 znaków)")
    if platform not in ALLOWED_TYPES:
        raise ValueError("Nieprawidłowy typ serwisu")
    payload = inventory()
    if any(row["domain"] == domain for row in payload["sites"]):
        raise ValueError("Domena już istnieje w rejestrze")
    payload["sites"].append({
        "id": domain, "domain": domain, "group": group, "type": platform,
        "public_checks": True, "authorized": False,
        "ssh_alias": None, "wp_root": None,
        "hosting": normalize_hosting(),
        "notes": "Nowy serwis: wymaga potwierdzenia uprawnień i konfiguracji.",
    })
    atomic_json(SITES_FILE, payload)


def update_site(domain, group, platform):
    domain = base.domain_name(domain)
    group = group.strip()
    if not group or len(group) > 64 or any(c in group for c in "\r\n<>"):
        raise ValueError("Podaj prawidłową nazwę grupy")
    if platform not in ALLOWED_TYPES:
        raise ValueError("Nieprawidłowy typ serwisu")
    payload = inventory()
    for site in payload["sites"]:
        if site["domain"] == domain:
            site["group"], site["type"] = group, platform
            atomic_json(SITES_FILE, payload)
            return
    raise ValueError("Nie znaleziono serwisu: " + domain)


def update_hosting(domain, provider, access, host=None, port=None, user=None):
    """Save nonsecret endpoint information locally. Never initiate a connection."""
    domain = base.domain_name(domain)
    info = normalize_hosting(provider, access, host, port, user)
    payload = inventory()
    for site in payload["sites"]:
        if site["domain"] == domain:
            site["hosting"] = info
            atomic_json(SITES_FILE, payload)
            return info
    raise ValueError("Brak serwisu w inwentaryzacji: " + domain)


def remove_site(domain):
    domain = base.domain_name(domain)
    payload = inventory()
    retained = [s for s in payload["sites"] if s["domain"] != domain]
    if len(retained) == len(payload["sites"]):
        raise ValueError("Nie znaleziono serwisu: " + domain)
    payload["sites"] = retained
    atomic_json(SITES_FILE, payload)


def validate_wp_root(value):
    """Katalog serwisu zdalnego: ścieżka Linux, nie polecenie powłoki."""
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    if (len(value) > 700 or not value.startswith("/") or
            any(ord(char) < 32 or ord(char) == 127 for char in value) or
            any(part in ("..", ".") for part in value.split("/")) or
            value.startswith("//") or "\x00" in value):
        raise ValueError("Podaj bezwzględną ścieżkę katalogu Linux bez '..' i znaków sterujących")
    return str(PurePosixPath(value))


def assign_ssh(domain, alias=None, wp_root=None):
    """Zapis mapowania lokalnie. Nie wykonuj SSH ani testów hostowych."""
    domain = base.domain_name(domain)
    alias = alias.strip() if isinstance(alias, str) else None
    if not alias:
        alias = None
    path = validate_wp_root(wp_root)
    if alias is None and path:
        raise ValueError("Katalog WordPress wymaga przypisanego profilu SSH.")
    if alias is not None:
        available = {p["alias"] for p in bw_servers.load_profiles()}
        if alias not in available:
            raise ValueError("Nie znaleziono lokalnego profilu SSH: " + alias)
    payload = inventory()
    for site in payload["sites"]:
        if site["domain"] == domain:
            site["ssh_alias"] = alias
            site["wp_root"] = path
            atomic_json(SITES_FILE, payload)
            return {"domain": domain, "ssh_alias": alias, "wp_root": path}
    raise ValueError("Brak domeny w lokalnej inwentaryzacji: " + domain)


def suggestion_preview():
    """Wskazówki dla istniejących profili i tylko nieprzypisanych serwisów."""
    active_profiles = {p["alias"] for p in bw_servers.load_profiles()}
    sites = {s["domain"]: s for s in inventory()["sites"]}
    result = []
    for domain, alias in SSH_SUGGESTIONS.items():
        site = sites.get(domain)
        if site and alias in active_profiles and not site.get("ssh_alias"):
            result.append((domain, alias))
    return result


def apply_suggestions():
    """Świadomie wywoływane po potwierdzeniu w GUI; nigdy nie nadpisuje mapowań."""
    preview = suggestion_preview()
    if not preview:
        return []
    payload = inventory()
    assigned = []
    for site in payload["sites"]:
        suggestion = next((alias for domain, alias in preview
                           if site["domain"] == domain), None)
        if suggestion and not site.get("ssh_alias"):
            site["ssh_alias"] = suggestion
            site["wp_root"] = None
            assigned.append((site["domain"], suggestion))
    if assigned:
        atomic_json(SITES_FILE, payload)
    return assigned


def set_authorized(domain, authorized):
    payload = inventory()
    matched = False
    for site in payload["sites"]:
        if site["domain"] == domain:
            site["authorized"] = bool(authorized)
            matched = True
    if not matched:
        raise ValueError("Brak domeny w rejestrze")
    atomic_json(SITES_FILE, payload)


def site_report_dir(domain):
    return REPORT_DIR / base.domain_name(domain)


def safe_report(report):
    directory = site_report_dir(report["domain"])
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    json_path = directory / ("audit_" + stamp + ".json")
    atomic_json(json_path, report)
    report["file"] = str(json_path)
    rows = []
    for check in report["checks"]:
        details = "\n".join(f"{name}: {value}" for name, value in check["details"].items())
        rows.append(
            "<tr><th scope='row'>" + escape(check["id"]) + " " +
            escape(check["name"]) + "</th><td>" +
            escape(check["state"]) + "</td><td><pre>" +
            escape(details) + "</pre></td></tr>"
        )
    alerts = "".join("<li>" + escape(text) + "</li>" for text in report["alerts"])
    discovery = report.get("discovery") or {}
    discovery_rows = []
    for key in ("http_status", "type_suggestion", "confidence", "cname", "redirect_target"):
        value = discovery.get(key)
        if value is not None:
            discovery_rows.append("<li><strong>" + escape(key) + ":</strong> " +
                                  escape(str(value)) + "</li>")
    for evidence in discovery.get("evidence", []):
        discovery_rows.append("<li>" + escape(evidence) + "</li>")
    for error in discovery.get("errors", []):
        discovery_rows.append("<li>" + escape(error) + "</li>")
    html = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BeardedWolf: raport audytu</title>
<style>body{max-width:92ch;margin:2rem auto;padding:0 1rem;font:1rem/1.55 system-ui,sans-serif;color:#161616;background:#fff}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #777;padding:.65rem;text-align:left;vertical-align:top}
pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}tr:nth-child(even){background:#f3f3f3}</style>
</head><body><main><h1>BeardedWolf: audyt serwisu</h1>
<p><strong>Domena:</strong> DOMAIN</p><p><strong>Data:</strong> DATE</p>
<p><strong>Stan:</strong> STATUS. Porównanie tylko z zatwierdzonym baseline.</p>
<h2>Rozpoznanie platformy (poszlaki)</h2><ul>DISCOVERY</ul>
<p>Brak cech WordPressa nie oznacza, że strona nie korzysta z WordPressa.
Dostawca hostingu oraz SSH/FTP wymagają osobnego potwierdzenia.</p>
<h2>Zmiany i ostrzeżenia</h2><ul>ALERTS</ul>
<h2>Kontrole publiczne</h2>
<table><thead><tr><th scope="col">Kontrola</th><th scope="col">Status</th><th scope="col">Wynik</th></tr></thead>
<tbody>ROWS</tbody></table>
<p>Kontrole wymagające SSH, WP-CLI, logów lub dostępu do bazy NIE zostały wykonane.
Brak alertu nie oznacza bezpieczeństwa serwisu. Raport zapisany wyłącznie lokalnie.</p>
</main></body></html>
"""
    html = (html.replace("DOMAIN", escape(report["domain"]))
            .replace("DATE", escape(report["timestamp"]))
            .replace("STATUS", escape(report["state"]))
            .replace("ALERTS", alerts or "<li>Brak zgłoszonych zmian w wykonanych kontrolach.</li>")
            .replace("DISCOVERY", "".join(discovery_rows) or "<li>Brak dostępnych danych</li>")
            .replace("ROWS", "\n".join(rows)))
    html_path = json_path.with_suffix(".html")
    if html_path.is_symlink():
        raise RuntimeError("Nie nadpisuję dowiązania")
    with html_path.open("x", encoding="utf-8") as stream:
        stream.write(html)
    html_path.chmod(0o600)
    return json_path, html_path


def latest_report(domain):
    directory = site_report_dir(domain)
    matches = sorted(directory.glob("audit_*.json"), reverse=True)
    if not matches:
        raise ValueError("Brak wcześniejszego raportu dla " + domain)
    return json.loads(matches[0].read_text(encoding="utf-8"))


def approve_baseline(domain):
    site = get_site(domain)
    if not site.get("authorized"):
        raise ValueError("Najpierw potwierdź zakres zarządzania domeną")
    previous = latest_report(domain)
    baseline = {
        "domain": domain, "approved_at": datetime.now(timezone.utc).isoformat(),
        "source_scan": previous["timestamp"],
        "checks": {item["id"]: item["details"] for item in previous["checks"]
                   if item["state"] == "OBSERVED"}
    }
    if not baseline["checks"]:
        raise ValueError("Brak udanych kontroli do zatwierdzenia")
    path = site_report_dir(domain) / "baseline-approved.json"
    atomic_json(path, baseline)
    return path


def probe_url(url):
    # Bez podążania za przekierowaniami na inne hosty / adresy wewnętrzne.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    request = urllib.request.Request(url, headers=HEADERS, method="HEAD")
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, response.geturl(), response.headers
    except urllib.error.HTTPError as exc:
        destination = exc.headers.get("Location", "")
        target = urllib.parse.urljoin(url, destination) if (
            300 <= exc.code < 400 and destination
        ) else exc.geturl()
        return exc.code, target, exc.headers


def public_probe(site):
    if not site.get("authorized"):
        raise ValueError("Serwis nie ma potwierdzonego zakresu zarządzania")
    if not site.get("public_checks"):
        raise ValueError("Testy publiczne są wyłączone dla tej domeny")
    domain = site["domain"]
    observed = []
    failures = []
    # Rozpoznanie jest wykonywane przy każdym teście, ale nie nadpisuje ręcznych ustawień.
    discovery = {"evidence": ["Platforma określona ręcznie; rozpoznanie automatyczne pominięte."]}
    if site["type"] == "sprawdzic":
        try:
            discovery = bw_discover.inspect_public(domain)
            if (discovery["type_suggestion"] == "wordpress" and
                    discovery["confidence"] == "wysoka"):
                # Tylko wysoko wiarygodny WordPress, zachowując grupę i przypisany hosting.
                update_site(domain, site["group"], "wordpress")
                site = dict(site, type="wordpress")
                discovery["auto_updated"] = True
        except Exception as exc:
            discovery = {"errors": ["Rozpoznanie niedostępne: " + type(exc).__name__]}


    for check_id, kind, title in [
        ("T34", "DNS", "Rekordy DNS"),
        ("T35", "TLS", "Certyfikat i połączenie TLS"),
        ("T24", "HTTP", "HTTPS i nagłówki"),
    ]:
        try:
            rows, failed = base.report_sections(kind, domain)
            state = "ERROR" if failed else "OBSERVED"
            details = {name: value for name, value in rows}
        except Exception as exc:
            state, details = "ERROR", {"Problem": str(exc)}
        observed.append({"id": check_id, "name": title, "state": state, "details": details})
        if state == "ERROR":
            failures.append(check_id + ": nie udało się wykonać pomiaru")

    # Wskazniki HTTP, bez enumeracji zasobow czy odczytu kont z REST API.
    try:
        started = time.monotonic()
        code, target, _headers = probe_url("https://" + domain + "/")
        millis = int((time.monotonic() - started) * 1000)
        final_host = urllib.parse.urlsplit(target).hostname or ""
        observed.append({
            "id": "T23", "name": "Przekierowania HTTP",
            "state": "OBSERVED",
            "details": {"http_status": str(code), "final_host": final_host,
                        "redirected": str(target != ("https://" + domain + "/"))}
        })
        observed.append({
            "id": "T25", "name": "Odpowiedź serwera i opóźnienie",
            "state": "OBSERVED",
            "details": {"http_status": str(code), "response_ms": str(millis)}
        })
        if code >= 500:
            failures.append(f"T25: Serwer zwrócił HTTP {code}")
        if millis > 3500:
            failures.append(f"T25: Czas otrzymania nagłówków HTTP {millis} ms (powyżej 3500 ms).")
        if final_host not in {domain, "www." + domain} and site["type"] != "przekierowanie":
            failures.append("T23: Odpowiedź przekierowano na innego hosta: " + final_host)
    except Exception as exc:
        for check_id, title in (("T23", "Przekierowania HTTP"), ("T25", "Odpowiedź serwera")):
            observed.append({"id": check_id, "name": title, "state": "ERROR",
                             "details": {"Problem": str(exc)}})
        failures.append("T23/T25: nie udało się wykonać kontroli HTTP")

    # Punktowy HEAD, bez pobierania listy użytkowników ani skanowania portów.
    if site["type"] == "wordpress":
        token = secrets.token_urlsafe(10)
        for check_id, title, path in [
            ("T19", "REST Users (sam status)", "/wp-json/wp/v2/users"),
            ("T20", "Endpoint logowania WordPress", "/wp-login.php"),
            ("T21", "Endpoint XML-RPC", "/xmlrpc.php"),
            ("T22", "Nieznany URL", "/__bw-audit-" + token),
        ]:
            try:
                code, target, headers = probe_url("https://" + domain + path)
                details = {"http_status": str(code), "final_host": urllib.parse.urlsplit(target).hostname or ""}
                if check_id == "T22" and code == 200:
                    failures.append("T22: Nieznany URL zwrócił HTTP 200. Zweryfikuj routing.")
                observed.append({"id": check_id, "name": title, "state": "OBSERVED",
                                 "details": details})
            except Exception as exc:
                observed.append({"id": check_id, "name": title, "state": "ERROR",
                                 "details": {"Problem": str(exc)}})
                failures.append(check_id + ": nie udało się wykonać pomiaru")

    baseline_file = site_report_dir(domain) / "baseline-approved.json"
    baseline = (json.loads(baseline_file.read_text(encoding="utf-8"))
                if baseline_file.exists() else None)
    changed = []
    if baseline:
        for check in observed:
            if check["state"] != "OBSERVED":
                continue
            reference = baseline["checks"].get(check["id"])
            if reference is None:
                changed.append(check["id"] + ": brak tej kontroli w stanie odniesienia")
            elif {k: v for k, v in reference.items() if k != "response_ms"} != {
                    k: v for k, v in check["details"].items() if k != "response_ms"}:
                changed.append(check["id"] + ": zmiana względem zatwierdzonego baseline")
    else:
        changed.append("Brak zatwierdzonego baseline: wyniki są tylko obserwacjami.")

    report = {
        "domain": domain, "timestamp": datetime.now(timezone.utc).isoformat(),
        "state": "WYMAGA_WERYFIKACJI" if failures or (baseline and changed) else
                 ("BRAK_BASELINE" if not baseline else "BEZ_ZMIAN"),
        "checks": observed, "alerts": failures + changed, "baseline": bool(baseline),
        "discovery": discovery,
        "host_checks_state": "NOT_RUN_NO_AUTHENTICATED_SESSION"
    }
    paths = safe_report(report)
    return report, paths


def main():
    parser = argparse.ArgumentParser(description="BeardedWolf: inwentaryzacja i audyty wielu domen")
    cmds = parser.add_subparsers(dest="command", required=True)
    cmds.add_parser("sites", help="Lista serwisów")
    cmds.add_parser("checks", help="Katalog kontroli T01-T40")
    for name in ("confirm", "unconfirm", "scan", "baseline-approve"):
        sub = cmds.add_parser(name)
        sub.add_argument("domain", type=base.domain_name)
    cmds.add_parser("scan-all", help="Pasywne kontrole wszystkich potwierdzonych serwisów")
    args = parser.parse_args()
    if args.command == "sites":
        for site in inventory()["sites"]:
            hosting = hosting_info(site)
            print(("✓ " if site["authorized"] else "○ ") + site["domain"] +
                  "  [" + site["group"] + ", " + site["type"] + "]" +
                  " hosting=" + hosting["provider"] +
                  " protokol=" + hosting["access"] +
                  " host=" + (hosting["host"] or "nieustalony") +
                  " ssh_alias=" + (site.get("ssh_alias") or "brak"))
        return 0
    if args.command == "checks":
        for check in catalog():
            print(check["id"], check["name"], check["access"], check["status"])
        return 0
    try:
        if args.command in ("confirm", "unconfirm"):
            set_authorized(args.domain, args.command == "confirm")
            print("Zapisano:", args.domain)
        elif args.command == "baseline-approve":
            print("Zatwierdzono:", approve_baseline(args.domain))
        elif args.command == "scan":
            report, (_, html) = public_probe(get_site(args.domain))
            print(report["state"], report["domain"], html)
        elif args.command == "scan-all":
            sites = [s for s in inventory()["sites"]
                     if s.get("authorized") and s.get("public_checks")]
            if not sites:
                print("Brak zatwierdzonych stron. Najpierw użyj confirm domena.pl.")
                return 2
            failures = 0
            for site in sites:
                try:
                    report, (_, html) = public_probe(site)
                    print(report["state"], site["domain"], html)
                    failures += report["state"] == "WYMAGA_WERYFIKACJI"
                except Exception as exc:
                    print("BŁĄD", site["domain"], exc, file=sys.stderr)
                    failures += 1
            print(f"Przebadano {len(sites)} serwisów, uwag {failures}.")
            return 1 if failures else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print("Błąd:", exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
