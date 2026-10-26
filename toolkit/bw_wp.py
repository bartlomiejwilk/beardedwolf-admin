"""Bezpieczna kontrola i ręczna aktualizacja WordPress przez istniejące profile SSH.

Brak automatycznej instalacji WP-CLI, brak haseł w komendach, brak uruchomienia
aktualizacji z pulpitu kafelków. Zmiany wyłącznie po odrębnym potwierdzeniu GUI.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import shlex
import subprocess

import bw_fleet
import bw_servers
import bw_integrity

MAX_OUTPUT = 100000
PLUGIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,125}\Z")
WP_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}\Z")


def environment(site):
    if not site.get("authorized") or site.get("type") != "wordpress":
        raise ValueError("Serwis musi mieć zatwierdzony zakres i platformę WordPress")
    root = bw_fleet.validate_wp_root(site.get("wp_root"))
    alias = site.get("ssh_alias")
    if not root or not alias:
        raise ValueError("Przypisz serwisowi potwierdzony profil SSH i katalog WordPress")
    profiles = {p["alias"]: p for p in bw_servers.load_profiles()}
    if alias not in profiles:
        raise ValueError("Nie istnieje lokalny profil SSH: " + str(alias))
    mismatch = bw_integrity.profile_endpoint_check(site, list(profiles.values()))
    if mismatch and mismatch[0] == "BŁĄD":
        raise ValueError("Zatrzymano operację WP-CLI: " + mismatch[1])
    if not bw_servers.key_for(profiles[alias]).is_file():
        raise ValueError("Brak prywatnego klucza SSH dla wskazanego profilu")
    return profiles[alias], root


def remote(site, args, *, timeout=55):
    """Jedna określona komenda zdalna. Nigdy nie podstawiamy poleceń użytkownika."""
    profile, root = environment(site)
    # cwd i wp-config.php są kontrolowane, nie wypisujemy zawartości konfiguracji.
    prelude = "cd " + shlex.quote(root) + " && test -f wp-includes/version.php && "
    argv = ["wp", "--path=" + root] + list(args)
    command = prelude + shlex.join(argv)
    result = subprocess.run([
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2", "-o", "IdentitiesOnly=yes",
        profile["alias"], "sh -c " + shlex.quote(command)
    ], capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        # Nie ujawniamy potencjalnie poufnego stdout/stderr z serwera w GUI.
        raise RuntimeError("Zdalna komenda WP-CLI nie powiodła się. "
                           "Sprawdź SSH, ścieżkę, uprawnienia i dostępność WP-CLI "
                           f"(kod: {result.returncode}).")
    return result.stdout[:MAX_OUTPUT].strip()


def json_array(text, label):
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Nieprawidłowy wynik JSON z WP-CLI: {label}") from exc
    if not isinstance(parsed, list):
        raise RuntimeError(f"Nieoczekiwany format wyników WP-CLI: {label}")
    return parsed


def list_updates(site):
    """Odczyt danych przez SSH, bez zapisu w katalogu WWW."""
    profile, root = environment(site)
    version = remote(site, ["core", "version"])
    if not WP_VERSION.fullmatch(version):
        raise RuntimeError("Nie można odczytać jednoznacznej wersji WordPress")
    core = json_array(remote(site, ["core", "check-update", "--format=json"]), "core")
    plugins = json_array(remote(site, ["plugin", "list", "--format=json"]), "plugins")
    available = []
    for item in plugins:
        if item.get("update") == "available" and PLUGIN_NAME.fullmatch(str(item.get("name", ""))):
            available.append({
                "name": item["name"], "version": str(item.get("version", "")),
                "target": str(item.get("update_version", "")),
                "status": str(item.get("status", ""))
            })
    core_targets = [x["version"] for x in core
                    if isinstance(x, dict) and WP_VERSION.fullmatch(str(x.get("version", "")))]
    return {
        "domain": site["domain"], "profile": profile["alias"], "wp_root": root,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "current_core": version,
        "core_targets": core_targets,
        "plugin_updates": available,
        "plugin_count": len(available),
        "core_update": bool(core_targets),
    }


def record_operation(domain, operation, target, success, details=""):
    """Zapis lokalny bez sekretów i pełnego stdout/stderr z serwera."""
    path = bw_fleet.site_report_dir(domain)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = datetime.now(timezone.utc)
    report = path / ("wp_change_" + timestamp.strftime("%Y%m%dT%H%M%S_%f") + ".json")
    bw_fleet.atomic_json(report, {
        "domain": domain, "operation": operation, "target": target,
        "success": bool(success), "checked_at": timestamp.isoformat(),
        "description": details[:400],
        "backup_confirmed_by_user": True,
        "backup_verified_by_software": False,
    })
    return report


def update_plugin(site, name, expected_version, expected_target):
    """Aktualizacja JEDNEJ wybranej wtyczki, nigdy --all."""
    if not PLUGIN_NAME.fullmatch(str(name)):
        raise ValueError("Niedozwolona nazwa wtyczki")
    fresh = list_updates(site)
    candidate = next((p for p in fresh["plugin_updates"] if p["name"] == name), None)
    if not candidate or candidate["version"] != expected_version or candidate["target"] != expected_target:
        raise RuntimeError("Lista aktualizacji uległa zmianie. Odśwież przed modyfikacją.")
    # Świadoma aktualizacja konkretnej wtyczki, bez --insecure lub --force.
    output = remote(site, ["plugin", "update", name], timeout=180)
    return output[-5000:]


def update_core(site, expected_current, target):
    """Aktualizacja wskazanej wersji Core; baza po osobnym potwierdzeniu/operatorze."""
    if not WP_VERSION.fullmatch(str(target)):
        raise ValueError("Niedozwolona wersja docelowa WordPress")
    fresh = list_updates(site)
    if fresh["current_core"] != expected_current or target not in fresh["core_targets"]:
        raise RuntimeError("Zmieniono wersję Core lub ofertę aktualizacji. Odśwież listę.")
    output = remote(site, ["core", "update", "--version=" + target], timeout=240)
    # Po zmianie plików Core wykonujemy wymaganą aktualizację schematu bazy.
    # To operacja modyfikująca bazę, wyraźnie objęta potwierdzeniem w GUI.
    try:
        db_result = remote(site, ["core", "update-db"], timeout=240)
    except Exception as exc:
        raise RuntimeError("Pliki Core zaktualizowano, ale aktualizacja bazy mogła "
                           "się nie udać! Sprawdź stan serwisu i kopię zapasową "
                           "przed kolejnymi zmianami.") from exc
    return (output[-2500:] + "\nBaza danych: " + db_result[-1800:])
