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
from pathlib import Path
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


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise RuntimeError(f"Nie zapisuję do dowiązania symbolicznego: {path}")
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


def inventory():
    if not SITES_FILE.exists():
        defaults = json.loads(INITIAL_SITES.read_text(encoding="utf-8"))
        atomic_json(SITES_FILE, defaults)
    payload = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    rows = payload["sites"]
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


def remove_site(domain):
    domain = base.domain_name(domain)
    payload = inventory()
    retained = [s for s in payload["sites"] if s["domain"] != domain]
    if len(retained) == len(payload["sites"]):
        raise ValueError("Nie znaleziono serwisu: " + domain)
    payload["sites"] = retained
    atomic_json(SITES_FILE, payload)


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
    html = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BeardedWolf: raport audytu</title>
<style>body{max-width:92ch;margin:2rem auto;padding:0 1rem;font:1rem/1.55 system-ui,sans-serif;color:#161616;background:#fff}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #777;padding:.65rem;text-align:left;vertical-align:top}
pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}tr:nth-child(even){background:#f3f3f3}</style>
</head><body><main><h1>BeardedWolf: audyt serwisu</h1>
<p><strong>Domena:</strong> DOMAIN</p><p><strong>Data:</strong> DATE</p>
<p><strong>Stan:</strong> STATUS. Porównanie tylko z zatwierdzonym baseline.</p>
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
        if final_host not in {domain, "www." + domain}:
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
            print(("✓ " if site["authorized"] else "○ ") + site["domain"] +
                  "  [" + site["group"] + ", " + site["type"] + "]")
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
