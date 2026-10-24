"""Testy lokalne stanów monitoringu HTTP/TLS bez połączeń sieciowych."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_monitor


class DashboardChecks(unittest.TestCase):
    def test_success_and_redirect_are_distinct(self):
        self.assertEqual(bw_monitor.classify_http(200), "DOSTĘPNA")
        self.assertEqual(bw_monitor.classify_http(301), "PRZEKIEROWANIE")
        self.assertEqual(bw_monitor.classify_http(403), "DOSTĘP OGRANICZONY")
        self.assertEqual(bw_monitor.classify_http(500), "AWARIA HTTP")
        self.assertEqual(bw_monitor.classify_http(None), "BŁĄD")

    def test_tls_warning_precedes_http_green(self):
        self.assertEqual(
            bw_monitor.display_status({"http": 200, "status": "DOSTĘPNA", "tls": "WYGASA"}),
            "UWAGA TLS"
        )

    def test_no_status_is_not_ok(self):
        self.assertEqual(bw_monitor.display_status({}), "NIE SPRAWDZONO")
        self.assertEqual(bw_monitor.display_status({"status": "DOSTĘPNA"}, stale=True),
                         "WYNIK HISTORYCZNY")


if __name__ == "__main__":
    unittest.main()
