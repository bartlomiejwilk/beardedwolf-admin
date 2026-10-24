"""Nieinwazyjne rozpoznawanie publicznych cech serwisu dla BeardedWolf Admin.
Nie stwierdza dostępności SSH/FTP i nie identyfikuje dostawcy hostingu na podstawie IP.
"""
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
}
MAX_PAGE = 128 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def inspect_public(domain):
    """Jeden GET strony głównej + DNS CNAME; bez logowania lub skanowania ścieżek."""
    url = "https://" + domain + "/"
    opener = urllib.request.build_opener(NoRedirect)
    result = {
        "type_suggestion": None,
        "confidence": "brak",
        "evidence": [],
        "http_status": None,
        "redirect_target": None,
        "cname": None,
        "errors": [],
    }
    try:
        proc = subprocess.run(
            ["dig", "+time=2", "+tries=1", "+short", domain, "CNAME"],
            capture_output=True, text=True, timeout=4, check=False
        )
        if proc.returncode == 0:
            name = proc.stdout.strip().splitlines()
            if name:
                result["cname"] = name[0].strip().rstrip(".")[:253]
    except (OSError, subprocess.SubprocessError) as exc:
        result["errors"].append("Nie uzyskano CNAME: " + type(exc).__name__)

    request = urllib.request.Request(url, headers=HEADERS, method="GET")
    try:
        try:
            response = opener.open(request, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            code = response.status if hasattr(response, "status") else response.code
            result["http_status"] = int(code)
            if 300 <= code < 400:
                location = response.headers.get("Location")
                if location:
                    result["redirect_target"] = urllib.parse.urljoin(url, location)[:2000]
                    result["evidence"].append("Strona odsyła kodem HTTP " + str(code))
                return result
            if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                result["evidence"].append("Odpowiedź nie zawiera dokumentu HTML")
                return result
            page = response.read(MAX_PAGE).decode("utf-8", "replace")
            head = page[:30000]
            link = str(response.headers.get("Link", ""))
            generator = bool(re.search(
                r'<meta\s+[^>]*name=["\']generator["\'][^>]*content=["\']WordPress(?:\s|["\'])',
                head, flags=re.I
            ) or re.search(
                r'<meta\s+[^>]*content=["\']WordPress(?:\s|["\'])[^>]*name=["\']generator["\']',
                head, flags=re.I
            ))
            wp_api = bool(re.search(r'rel=["\']https://api\.w\.org/?["\']', link, re.I)
                          or re.search(r'rel=["\']https://api\.w\.org/?["\']', head, re.I))
            wp_assets = ("/wp-content/" in page.lower() or "/wp-includes/" in page.lower())
            if generator:
                result["evidence"].append('Meta generator wskazuje "WordPress"')
            if wp_api:
                result["evidence"].append("Wykryto deklarację API WordPress (api.w.org)")
            if wp_assets:
                result["evidence"].append("W kodzie strony są odwołania do zasobów wp-content/wp-includes")
            if generator or (wp_api and wp_assets):
                result["type_suggestion"] = "wordpress"
                result["confidence"] = "wysoka"
            elif wp_api or wp_assets:
                result["type_suggestion"] = "wordpress"
                result["confidence"] = "wstępna"
    except (OSError, ValueError) as exc:
        result["errors"].append("Nie udało się pobrać HTML: " + type(exc).__name__)
    return result
