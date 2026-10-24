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

    def test_unknown_platform_autofills_wordpress_only_with_strong_evidence(self):
        fleet.set_authorized("example.org", True)
        fleet.update_site("example.org", "private", "sprawdzic")
        strong = {"type_suggestion": "wordpress", "confidence": "wysoka",
                  "evidence": ["WP API", "wp-content"], "errors": []}
        with patch.object(fleet.bw_discover, "inspect_public", return_value=strong), \
             patch.object(fleet.base, "report_sections",
                          side_effect=lambda kind, domain: ([("Status", kind)], False)), \
             patch.object(fleet, "probe_url",
                          side_effect=lambda url: (404 if "__bw-audit-" in url else 200, url, {})):
            report, _ = fleet.public_probe(fleet.get_site("example.org"))
        self.assertEqual(fleet.get_site("example.org")["type"], "wordpress")
        self.assertEqual(report["discovery"]["type_suggestion"], "wordpress")
        self.assertTrue(report["discovery"].get("auto_updated"))
        self.assertTrue(fleet.get_site("example.org")["authorized"])

    def test_weak_evidence_does_not_change_platform(self):
        fleet.set_authorized("example.org", True)
        fleet.update_site("example.org", "private", "sprawdzic")
        weak = {"type_suggestion": "wordpress", "confidence": "wstępna",
                "evidence": ["wp-content"], "errors": []}
        with patch.object(fleet.bw_discover, "inspect_public", return_value=weak), \
             patch.object(fleet.base, "report_sections",
                          side_effect=lambda kind, domain: ([("Status", kind)], False)), \
             patch.object(fleet, "probe_url",
                          side_effect=lambda url: (200, url, {})):
            report, _ = fleet.public_probe(fleet.get_site("example.org"))
        self.assertEqual(fleet.get_site("example.org")["type"], "sprawdzic")
        self.assertFalse(report["discovery"].get("auto_updated", False))

    def test_manual_platform_never_overwritten(self):
        fleet.set_authorized("example.org", True)
        with patch.object(fleet.bw_discover, "inspect_public") as discovery, \
             patch.object(fleet.base, "report_sections",
                          side_effect=lambda kind, domain: ([("Status", kind)], False)), \
             patch.object(fleet, "probe_url",
                          side_effect=lambda url: (200, url, {})):
            fleet.public_probe(fleet.get_site("example.org"))
        discovery.assert_not_called()

    def test_inventory_crud_keeps_reports(self):
        fleet.add_site("new.example.org", "jdk", "sprawdzic")
        self.assertEqual(fleet.get_site("new.example.org")["type"], "sprawdzic")
        fleet.update_site("new.example.org", "um", "wordpress")
        self.assertEqual(fleet.get_site("new.example.org")["group"], "um")
        fleet.remove_site("new.example.org")
        with self.assertRaises(ValueError):
            fleet.get_site("new.example.org")

    def test_duplicate_domain_rejected(self):
        with self.assertRaises(ValueError):
            fleet.add_site("example.org", "prywatne", "wordpress")

    def test_invalid_platform_rejected(self):
        with self.assertRaises(ValueError):
            fleet.add_site("new.example.org", "prywatne", "php -r evil")

    def test_assign_ssh_preserves_authorization_and_root(self):
        fleet.set_authorized("example.org", True)
        with patch.object(fleet.bw_servers, "load_profiles", return_value=[
            {"alias": "jaslo", "host": "ssh.cluster114.hosting.ovh.net", "user": "jaslo", "port": 22}
        ]):
            saved = fleet.assign_ssh("example.org", "jaslo", "/home/jaslo/beardedwolf")
            self.assertEqual(saved["ssh_alias"], "jaslo")
            self.assertEqual(saved["wp_root"], "/home/jaslo/beardedwolf")
            site = fleet.get_site("example.org")
            self.assertTrue((self.settings / "sites.json.previous.bak").exists())
            self.assertTrue(site["authorized"])
            self.assertEqual(site["ssh_alias"], "jaslo")
            fleet.assign_ssh("example.org", None, "")
            self.assertIsNone(fleet.get_site("example.org")["ssh_alias"])
            self.assertIsNone(fleet.get_site("example.org")["wp_root"])

    def test_reject_missing_local_profile(self):
        with patch.object(fleet.bw_servers, "load_profiles", return_value=[]):
            with self.assertRaisesRegex(ValueError, "Nie znaleziono"):
                fleet.assign_ssh("example.org", "jdk", "/home/jdkjasj/jdk")

    def test_reject_relative_and_traversal_path(self):
        for root in ("../site", "/home/jaslo/../secret", "/tmp\ncommand", "/tmp/./site"):
            with self.assertRaises(ValueError):
                fleet.validate_wp_root(root)
        self.assertEqual(fleet.validate_wp_root("/home/jaslo/wordpress"),
                         "/home/jaslo/wordpress")

    def test_suggestions_require_profile_and_confirmation(self):
        with patch.object(fleet, "SSH_SUGGESTIONS", {"example.org": "jaslo"}), \
             patch.object(fleet.bw_servers, "load_profiles", return_value=[
                 {"alias": "jaslo", "host": "ssh.cluster114.hosting.ovh.net",
                  "user": "jaslo", "port": 22}
             ]):
            self.assertEqual(fleet.suggestion_preview(), [("example.org", "jaslo")])
            self.assertIsNone(fleet.get_site("example.org").get("ssh_alias"))
            self.assertEqual(fleet.apply_suggestions(), [("example.org", "jaslo")])
            self.assertEqual(fleet.suggestion_preview(), [])
            self.assertEqual(fleet.get_site("example.org")["ssh_alias"], "jaslo")
            self.assertIsNone(fleet.get_site("example.org")["wp_root"])

    def test_suggestions_do_not_overwrite_existing_mapping(self):
        with patch.object(fleet, "SSH_SUGGESTIONS", {"example.org": "jaslo"}), \
             patch.object(fleet.bw_servers, "load_profiles", return_value=[
                 {"alias": "jaslo", "host": "ssh.cluster114.hosting.ovh.net", "user": "jaslo", "port": 22},
                 {"alias": "other", "host": "ssh.example.org", "user": "other", "port": 22}
             ]):
            fleet.assign_ssh("example.org", "other", "/home/other/site")
            self.assertEqual(fleet.apply_suggestions(), [])
            self.assertEqual(fleet.get_site("example.org")["wp_root"], "/home/other/site")

    def test_hosting_migration_keeps_local_ssh_and_scope(self):
        fleet.set_authorized("example.org", True)
        with patch.object(fleet.bw_servers, "load_profiles", return_value=[
            {"alias": "myssh", "host": "ssh.example.org", "user": "web", "port": 22}
        ]):
            fleet.assign_ssh("example.org", "myssh", "/home/web/site")
        # Deliberately remove newly added hosting metadata as with a legacy installation.
        payload = fleet.inventory()
        del payload["sites"][0]["hosting"]
        fleet.atomic_json(fleet.SITES_FILE, payload)
        defaults = self.settings / "hosting-defaults.json"
        defaults.write_text(json.dumps({"sites": {
            "example.org": {"provider": "OVHcloud", "access": "ftp",
                            "host": "ftp.cluster130.hosting.ovh.net", "port": 21}
        }}), encoding="utf-8")
        with patch.object(fleet, "HOSTING_DEFAULTS", defaults):
            migrated = fleet.get_site("example.org")
        self.assertEqual(migrated["hosting"]["provider"], "OVHcloud")
        self.assertEqual(migrated["hosting"]["access"], "ftp")
        self.assertTrue(migrated["authorized"])
        self.assertEqual(migrated["ssh_alias"], "myssh")
        self.assertEqual(migrated["wp_root"], "/home/web/site")
        self.assertTrue((self.settings / "sites.json.previous.bak").exists())

    def test_ftp_metadata_without_ssh_assignment(self):
        saved = fleet.update_hosting(
            "example.org", "OVHcloud", "ftp",
            "ftp.cluster130.hosting.ovh.net", 21, "parkowd"
        )
        self.assertEqual(saved["access"], "ftp")
        self.assertEqual(saved["user"], "parkowd")
        self.assertIsNone(fleet.get_site("example.org")["ssh_alias"])
        self.assertEqual(fleet.hosting_info(fleet.get_site("example.org"))["port"], 21)

    def test_reject_credentials_in_host_and_invalid_hosting(self):
        for host in ("ftp://parkowd@ftp.cluster130.hosting.ovh.net:21/",
                     "parkowd:secret@ftp.cluster130.hosting.ovh.net",
                     "ftp.example.org;rm -rf"):
            with self.assertRaises(ValueError):
                fleet.normalize_hosting("OVHcloud", "ftp", host, 21)
        with self.assertRaises(ValueError):
            fleet.normalize_hosting("OVHcloud", "ftp", "ftp.example.org", 21,
                                    "parkowd:secret")
        with self.assertRaises(ValueError):
            fleet.normalize_hosting("OVHcloud", "sudoss", None, None)

    def test_provider_edit_does_not_reset_platform_or_ssh(self):
        fleet.set_authorized("example.org", True)
        fleet.update_site("example.org", "um", "wordpress")
        fleet.update_hosting("example.org", "nazwa.pl", "unknown")
        current = fleet.get_site("example.org")
        self.assertTrue(current["authorized"])
        self.assertEqual(current["group"], "um")
        self.assertEqual(current["type"], "wordpress")
        self.assertEqual(current["hosting"]["provider"], "nazwa.pl")

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
