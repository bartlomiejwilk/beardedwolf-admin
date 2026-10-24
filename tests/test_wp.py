"""Testy offline: kontrola WP-CLI przez SSH i granice zapisu."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_wp


SITE = {"domain": "example.org", "authorized": True,
        "type": "wordpress", "ssh_alias": "jaslo", "wp_root": "/home/web/site"}
PROFILE = {"alias": "jaslo", "host": "ssh.example.org", "user": "web", "port": 22}


class WordpressTests(unittest.TestCase):
    def test_missing_authorization_or_root_blocks(self):
        with self.assertRaises(ValueError):
            bw_wp.environment(dict(SITE, authorized=False))
        with self.assertRaises(ValueError):
            bw_wp.environment(dict(SITE, wp_root=None))
        with self.assertRaises(ValueError):
            bw_wp.environment(dict(SITE, type="sprawdzic"))

    def test_ssh_command_is_noninteractive_and_escaped(self):
        with patch.object(bw_wp, "environment", return_value=(PROFILE, "/home/web/site")), \
             patch.object(bw_wp.subprocess, "run", return_value=SimpleNamespace(
                 returncode=0, stdout='[]', stderr=''
             )) as runner:
            self.assertEqual(bw_wp.remote(SITE, ["plugin", "list", "--format=json"]), "[]")
        argv = runner.call_args.args[0]
        self.assertIn("BatchMode=yes", argv)
        self.assertIn("StrictHostKeyChecking=yes", argv)
        self.assertIn("IdentitiesOnly=yes", argv)
        self.assertIn("jaslo", argv)
        self.assertIn("test -f wp-includes/version.php", argv[-1])
        self.assertNotIn("--all", argv[-1])

    def test_parse_update_list(self):
        responses = iter([
            "6.9.0",
            '[{"version":"6.9.1","update_type":"minor"}]',
            json.dumps([
                {"name": "akismet", "version": "1.0", "update_version": "1.1",
                 "update": "available", "status": "active"},
                {"name": "none", "version": "1.0", "update_version": "",
                 "update": "none", "status": "inactive"}
            ])
        ])
        with patch.object(bw_wp, "environment", return_value=(PROFILE, "/home/web/site")), \
             patch.object(bw_wp, "remote", side_effect=lambda *a, **kw: next(responses)):
            data = bw_wp.list_updates(SITE)
        self.assertTrue(data["core_update"])
        self.assertEqual(data["plugin_count"], 1)
        self.assertEqual(data["plugin_updates"][0]["name"], "akismet")

    def test_reject_stale_plugin_snapshot(self):
        with patch.object(bw_wp, "list_updates", return_value={
            "plugin_updates": [{"name": "akismet", "version": "2.0", "target": "2.1"}]
        }), patch.object(bw_wp, "remote") as remote:
            with self.assertRaises(RuntimeError):
                bw_wp.update_plugin(SITE, "akismet", "1.0", "2.1")
            remote.assert_not_called()

    def test_reject_shell_payload_as_plugin_slug(self):
        with self.assertRaises(ValueError):
            bw_wp.update_plugin(SITE, "akismet; rm -rf /", "1", "2")

    def test_core_update_is_pinned_to_reviewed_version(self):
        with patch.object(bw_wp, "list_updates", return_value={
            "current_core": "6.9.0", "core_targets": ["6.9.1"]
        }), patch.object(bw_wp, "remote", return_value="Success") as remote:
            result = bw_wp.update_core(SITE, "6.9.0", "6.9.1")
            self.assertIn("Success", result)
            self.assertEqual(remote.call_args_list[0].args[1],
                             ["core", "update", "--version=6.9.1"])
            self.assertEqual(remote.call_args_list[1].args[1],
                             ["core", "update-db"])

    def test_unsupported_target_rejected(self):
        with self.assertRaises(ValueError):
            bw_wp.update_core(SITE, "6.9", "--insecure")


if __name__ == "__main__":
    unittest.main()
