"""Read-only command-center presentation rules for WWW and TLS monitoring."""

BAD_HTTP = {"AWARIA HTTP", "BŁĄD HTTP", "BŁĄD POŁĄCZENIA", "BŁĄD"}
WARN_HTTP = {"DOSTĘP OGRANICZONY", "INNY STATUS"}


def is_redirect(site, measurement=None):
    return site.get("type") == "przekierowanie" or bool(
        measurement and measurement.get("status") == "PRZEKIEROWANIE"
    )


def presentation(site, measurement):
    """Returns (label, severity, HTTP, TLS, latency) without connectivity claims."""
    if not site.get("authorized") or not site.get("public_checks", True):
        return "NIE SPRAWDZONO", "unknown", "—", "—", "—"
    if measurement is None:
        return "OCZEKUJE NA TEST", "unknown", "—", "—", "—"
    http_status = measurement.get("status", "NIE SPRAWDZONO")
    tls = measurement.get("tls", "NIE SPRAWDZONO")
    code = measurement.get("http")
    latency = measurement.get("response_ms")
    http_text = str(code) if code is not None else "BRAK"
    latency_text = str(latency) + " ms" if latency is not None else "—"
    if http_status in BAD_HTTP:
        return "PROBLEM Z WWW", "critical", http_text, tls, latency_text
    if tls == "BŁĄD TLS":
        return "PROBLEM Z TLS", "critical", http_text, tls, latency_text
    if tls in ("WYGASA", "CERTYFIKAT BEZ DATY"):
        return "SPRAWDŹ TLS", "warning", http_text, tls, latency_text
    if http_status in WARN_HTTP:
        return "SPRAWDŹ WWW", "warning", http_text, tls, latency_text
    if http_status == "PRZEKIEROWANIE":
        return "PRZEKIEROWANIE", "redirect", http_text, tls, latency_text
    if http_status == "DOSTĘPNA" and tls == "WAŻNY":
        return "DOSTĘPNA", "healthy", http_text, tls, latency_text
    return "NIEPEŁNY POMIAR", "unknown", http_text, tls, latency_text


def order(site, measurement):
    """Redirects always last; incidents first, then warnings and working sites."""
    label, severity, _, _, _ = presentation(site, measurement)
    weights = {"critical": 0, "warning": 1, "unknown": 2,
               "healthy": 3, "redirect": 4}
    return (1 if is_redirect(site, measurement) else 0,
            weights.get(severity, 2),
            site["domain"].lower())


def metrics(sites, results):
    """Counts only actual known measurements and avoids claiming all domains are up."""
    summary = {"total": len(sites), "healthy": 0, "alerts": 0,
               "unchecked": 0, "redirects": 0}
    for site in sites:
        data = results.get(site["domain"])
        _, severity, _, _, _ = presentation(site, data)
        if is_redirect(site, data):
            summary["redirects"] += 1
        elif severity == "healthy":
            summary["healthy"] += 1
        elif severity in ("warning", "critical"):
            summary["alerts"] += 1
        else:
            summary["unchecked"] += 1
    return summary
