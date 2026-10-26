"""Read-only integrity review of BeardedWolf's shared service registry.

No network calls, no SSH, no filesystem edits. Results are advisory; only a
verified SSH destination mismatch blocks connection in the GUI.
"""
from collections import Counter
import re


SEVERITY = ("BŁĄD", "UWAGA", "INFORMACJA")


def host_key(value):
    """Compare literal SSH endpoints without guessing DNS aliases."""
    return str(value or "").strip().lower().rstrip(".")


def profile_endpoint_check(site, profiles):
    """Return (level, message) or None; compare known OVH cluster identities.

    Different DNS names do not necessarily mean different servers. Block only
    explicitly different OVH cluster numbers or missing SSH profile; other
    different hostnames require human verification, not an automatic verdict.
    """
    alias = site.get("ssh_alias")
    if not alias:
        return None
    profile = next((p for p in profiles if p.get("alias") == alias), None)
    if profile is None:
        return "BŁĄD", "Profil SSH '%s' nie istnieje na liście połączeń." % alias
    hosting = site.get("hosting") or {}
    if hosting.get("access") != "ssh" or not hosting.get("host"):
        return None
    expected = host_key(hosting.get("host"))
    actual = host_key(profile.get("host"))
    if expected == actual:
        return None
    expected_cluster = re.search(r"(?:^|\.)ssh(?:\d*)?\.cluster(\d+)\.", expected)
    actual_cluster = re.search(r"(?:^|\.)ssh(?:\d*)?\.cluster(\d+)\.", actual)
    if expected_cluster and actual_cluster:
        if expected_cluster.group(1) == actual_cluster.group(1):
            return None
        return ("BŁĄD", "Profil SSH '%s' prowadzi na OVH cluster%s (%s), "
                "a hosting domeny wskazuje cluster%s (%s). "
                "Popraw powiązanie przed połączeniem." %
                (alias, actual_cluster.group(1), actual,
                 expected_cluster.group(1), expected))
    return ("UWAGA", "Profil SSH '%s' prowadzi do %s, a hosting wskazuje %s. "
            "Nazwy mogą być aliasami DNS; zweryfikuj faktyczny serwer." %
            (alias, actual, expected))


def audit_inventory(sites, profiles):
    """Return findings sorted by severity and domain; never change input."""
    issues = []
    seen = Counter(row.get("domain") for row in sites)
    available = {row.get("alias") for row in profiles}

    def report(domain, severity, category, message):
        issues.append({
            "domain": domain, "severity": severity,
            "category": category, "message": message
        })

    for site in sites:
        domain = site.get("domain", "(brak domeny)")
        info = site.get("hosting") or {}
        alias = site.get("ssh_alias")
        category = site.get("type")
        root = site.get("wp_root")

        if seen[domain] > 1:
            report(domain, "BŁĄD", "Rejestr", "Domena występuje więcej niż raz.")
        if alias:
            if alias not in available:
                report(domain, "BŁĄD", "SSH", "Brakuje profilu SSH '%s'." % alias)
            else:
                mismatch = profile_endpoint_check(site, profiles)
                if mismatch:
                    severity, message = mismatch
                    report(domain, severity, "SSH", message)
                elif info.get("access") in ("ftp", "ftps", "sftp"):
                    report(domain, "UWAGA", "Protokół",
                           "Hosting wskazuje %s, a serwis ma profil SSH '%s'. "
                           "To różne protokoły. Zweryfikuj dostęp." %
                           (info.get("access", "").upper(), alias))
                elif info.get("access") != "ssh" or not info.get("host"):
                    report(domain, "UWAGA", "Hosting",
                           "Przypisano SSH '%s', ale dane hostingu nie "
                           "potwierdzają serwera SSH. Sprawdź host i protokół." % alias)

        if root and not alias:
            report(domain, "BŁĄD", "WordPress",
                   "Zapisano katalog WordPress bez przypisanego profilu SSH.")
        if category == "wordpress" and alias and not root:
            report(domain, "UWAGA", "WordPress",
                   "Brak zweryfikowanego katalogu WordPress. "
                   "Nie wykonuj operacji WP-CLI do czasu jego ustalenia.")
        if category == "przekierowanie" and (alias or root):
            report(domain, "UWAGA", "Przekierowanie",
                   "Domena przekierowująca ma przypisanie SSH lub katalog WP. "
                   "Sprawdź, czy dotyczy aktywnej instalacji, a nie starej strony.")
        if category == "sprawdzic":
            report(domain, "INFORMACJA", "Platforma",
                   "Nie ustalono platformy. Nie zakładaj, że jest to WordPress.")
        if info.get("provider", "nieustalony") == "nieustalony":
            report(domain, "INFORMACJA", "Hosting",
                   "Dostawca hostingu nie został ustalony.")

    priority = {sev: idx for idx, sev in enumerate(SEVERITY)}
    return sorted(issues, key=lambda row: (
        priority.get(row["severity"], 99),
        row["domain"], row["category"]
    ))


def audit_summary(issues):
    count = Counter(row["severity"] for row in issues)
    return dict(errors=count["BŁĄD"], warnings=count["UWAGA"],
                info=count["INFORMACJA"])
