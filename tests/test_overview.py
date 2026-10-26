import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_overview


class OverviewTests(unittest.TestCase):
    def test_redirect_last(self):
        normal = {"domain": "site.org", "type": "wordpress", "authorized": True}
        redirect = {"domain": "redirect.org", "type": "przekierowanie",
                    "authorized": True}
        self.assertLess(bw_overview.order(normal, None),
                        bw_overview.order(redirect, None))

    def test_unchecked_is_not_healthy(self):
        site = {"domain": "site.org", "type": "wordpress", "authorized": True}
        self.assertEqual(bw_overview.presentation(site, None)[1], "unknown")

    def test_bad_tls_is_critical(self):
        site = {"domain": "site.org", "type": "wordpress", "authorized": True}
        status = {"http": 200, "status": "DOSTĘPNA", "tls": "BŁĄD TLS"}
        self.assertEqual(bw_overview.presentation(site, status)[1], "critical")


if __name__ == "__main__":
    unittest.main()
