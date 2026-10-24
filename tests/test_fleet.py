"""Testy lokalne audytu wielu serwisów, bez połączeń sieciowych."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_fleet as fleet


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.settings = root / "settings"
        self.reports = root / "reports"
        self.initial = root / "sites.json"
        self.initial.write_text(json.dumps({
            "schema": 1,
            "sites": [{"id": "example.org", "domain": "example.org",
                       "group": "private", "type": "wordpress",
                       "public_checks": True, "authorized": False,
                       "ssh_alias": None, "wp_root": None}]
        }), encoding="utf-8")
        self.patches = [
            patch.object(fleet, "SETTINGS", self.settings),
            patch.object(fleet, "SITES_FILE", self.settings / "sites.json"),
            patch.object(fleet, "INITIAL_SITES", self.initial),
            patch.object(fleet, "REPORT_DIR", self.reports)
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.folder.cleanup()

    def test_defaults_not_authorized(self):
        self.assertFalse(fleet.get_site("example.org")["authorized"])
        with self.assertRaisesRegex(ValueError, "potwierdzonego"):
            fleet.public_probe(fleet.get_site("example.org"))

    def test_approved_baseline_requires_explicit_action(self):
        fleet.set_authorized("example.org", True)
        self.assertTrue(fleet.get_site("example.org")["authorized"])

        def sections(kind, domain):
            return ([("Test", "value-" + kind)], False)

        def url(url):
            status = 404 if "__bw-audit" in url else 200
            return status, url, {}

        with patch.object(fleet.base, "report_sections", side_effect=sections), \
             patch.object(fleet, "probe_url", side_effect=url):
            report, (data_path, html_path) = fleet.public_probe(fleet.get_site("example.org"))
            self.assertEqual(report["state"], "BRAK_BASELINE")
            self.assertFalse((html_path.parent / "baseline-approved.json").exists())
            self.assertTrue(html_path.exists())
            self.assertEqual(json.loads(data_path.read_text())["domain"], "example.org")
            baseline_path = fleet.approve_baseline("example.org")
            self.assertTrue(baseline_path.exists())
            second, _ = fleet.public_probe(fleet.get_site("example.org"))
            self.assertEqual(second["state"], "BEZ_ZMIAN")
            self.assertTrue(second["baseline"])
            self.assertEqual(second["host_checks_state"],
                             "NOT_RUN_NO_AUTHENTICATED_SESSION")

    def test_deny_non_inventory_domain(self):
        with self.assertRaisesRegex(ValueError, "Brak domeny"):
            fleet.get_site("unknown.example.org")

    def test_unconfirm_blocks_audit(self):
        fleet.set_authorized("example.org", True)
        fleet.set_authorized("example.org", False)
        with self.assertRaises(ValueError):
            fleet.public_probe(fleet.get_site("example.org"))

    def test_catalog_contains_40_controls(self):
        self.assertEqual(len(fleet.catalog()), 40)
        self.assertEqual(fleet.catalog()[0]["id"], "T01")
        self.assertEqual(fleet.catalog()[-1]["id"], "T40")


if __name__ == "__main__":
    unittest.main()
