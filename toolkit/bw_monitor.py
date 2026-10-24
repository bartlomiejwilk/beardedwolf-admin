"""Pasywny przegląd stanu WWW/TLS: pojedyncze HEAD per serwis, bez SSH.
Wyniki z konkretnym czasem, błędy jawne, cache lokalny tylko jako historia.
"""
from datetime import datetime, timezone
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 7


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def classify_http(code):
    if code is None:
        return "BŁĄD"
    if code >= 500:
        return "AWARIA HTTP"
    if code in (401, 403):
        return "DOSTĘP OGRANICZONY"
    if 200 <= code < 400:
        return "DOSTĘPNA" if code < 300 else "PRZEKIEROWANIE"
    if 400 <= code < 500:
        return "BŁĄD HTTP"
    return "INNY STATUS"


def check(domain):
    now = datetime.now(timezone.utc).isoformat()
    result = {
        "domain": domain, "checked_at": now, "http": None,
        "status": "NIE SPRAWDZONO", "response_ms": None,
        "location": None, "tls": "NIE SPRAWDZONO",
        "tls_days": None, "tls_expires": None, "error": None
    }
    url = "https://" + domain + "/"
    opener = urllib.request.build_opener(NoRedirect)
    start = time.monotonic()
    try:
        request = urllib.request.Request(url, headers=HEADERS, method="HEAD")
        try:
            response = opener.open(request, timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            code = int(response.status if hasattr(response, "status") else response.code)
            result["http"] = code
            result["status"] = classify_http(code)
            if 300 <= code < 400:
                location = response.headers.get("Location", "")
                # Keep target limited and do not follow it to a different host.
                result["location"] = urllib.parse.urljoin(url, location)[:350] if location else None
            result["response_ms"] = int(1000 * (time.monotonic() - start))
    except Exception as exc:
        result["status"] = "BŁĄD POŁĄCZENIA"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:180]
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=domain) as connection:
                certificate = connection.getpeercert()
                end = certificate.get("notAfter")
                if not end:
                    result["tls"] = "CERTYFIKAT BEZ DATY"
                else:
                    date = datetime.strptime(end, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    days = int((date - datetime.now(timezone.utc)).total_seconds() // 86400)
                    result["tls_days"] = days
                    result["tls_expires"] = date.date().isoformat()
                    result["tls"] = "WYGASA" if days < 14 else "WAŻNY"
    except (OSError, ssl.SSLError, ValueError) as exc:
        result["tls"] = "BŁĄD TLS"
        if not result["error"]:
            result["error"] = type(exc).__name__ + ": " + str(exc)[:180]
    return result


def display_status(data, stale=False):
    if not data:
        return "NIE SPRAWDZONO"
    if stale:
        return "WYNIK HISTORYCZNY"
    if data.get("tls") in ("BŁĄD TLS", "WYGASA"):
        return "UWAGA TLS"
    return data.get("status", "NIE SPRAWDZONO")
