"""Offline tests for shared metadata, safety and two-device synchronization."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_sync
import bw_fleet as fleet
import bw_servers


class SyncthingMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.root = root
        self.sync = root / "BeardedWolf" / "Sync"
        self.sync.mkdir(parents=True)
        self.settings = root / "device1"
        self.settings.mkdir()
        self.sshdir = root / "ssh1"
        self.sshdir.mkdir()
        self.sites = self.settings / "sites.json"
        self.profiles = self.settings / "servers.json"
        self.sync_config = self.settings / "sync.json"
        self.sites.write_text(json.dumps({
            "schema": 1,
            "sites": [
                {"domain": "example.org", "id": "example.org", "group": "private",
                 "type": "wordpress", "public_checks": True, "authorized": True,
                 "ssh_alias": "jaslo", "wp_root": "/home/web/site",
                 "notes": "PRYWATNE NOTATKI NIE DO SYNCHRONIZACJI",
                 "secret_field": "SECRET-MUST-NOT-SYNC",
                 "hosting": {"provider": "OVHcloud", "access": "ssh",
                             "host": "ssh.example.org", "port": 22, "user": "web"}}
            ]
        }), encoding="utf-8")
        self.profiles.write_text(json.dumps([
            {"alias": "jaslo", "host": "ssh.example.org", "user": "web", "port": 22}
        ]), encoding="utf-8")
        self.patches = [
            patch.object(bw_sync, "CONFIG", self.sync_config),
            patch.object(fleet, "SITES_FILE", self.sites),
            patch.object(fleet, "DEFAULT_SITES_FILE", self.sites),
            patch.object(bw_servers, "PROFILE_FILE", self.profiles),
            patch.object(bw_servers, "DEFAULT_PROFILE_FILE", self.profiles),
            patch.object(bw_servers, "CONFIG_DIR", self.settings),
            patch.object(bw_servers, "SSH_DIR", self.sshdir),
            patch.object(bw_servers, "SSH_CONFIG", self.sshdir / "config")
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def publish(self):
        return bw_sync.enable(self.sync, "publish", self.sites, self.profiles)

    def test_publish_strips_notes_unknown_keys_and_all_secrets(self):
        result = self.publish()
        self.assertEqual(result["mode"], "publish")
        raw = (self.sync / "Admin" / "sites.json").read_text(encoding="utf-8")
        self.assertNotIn("PRYWATNE NOTATKI", raw)
        self.assertNotIn("SECRET-MUST-NOT-SYNC", raw)
        self.assertNotIn("secret_field", raw)
        profile_raw = (self.sync / "Admin" / "servers.json").read_text(encoding="utf-8")
        self.assertNotIn("IdentityFile", profile_raw)
        self.assertNotIn("private_key", profile_raw)
        self.assertEqual(fleet.get_site("example.org")["ssh_alias"], "jaslo")
        self.assertEqual(fleet.get_site("example.org")["notes"],
                         "PRYWATNE NOTATKI NIE DO SYNCHRONIZACJI")
        self.assertEqual(bw_servers.load_profiles()[0]["alias"], "jaslo")
        self.assertTrue((self.sshdir / "config").is_file())
        self.assertFalse((self.sshdir / "id_ed25519_bw_jaslo").exists())

    def test_live_change_on_shared_file_reflected_in_inventory(self):
        self.publish()
        source = self.sync / "Admin" / "sites.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["sites"][0]["wp_root"] = "/home/web/new-path"
        source.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(fleet.get_site("example.org")["wp_root"], "/home/web/new-path")
        fleet.update_site("example.org", "new-group", "wordpress")
        self.assertEqual(json.loads(source.read_text(encoding="utf-8"))["sites"][0]["group"],
                         "new-group")
        self.assertEqual(json.loads(self.sites.read_text(encoding="utf-8"))["sites"][0]["group"],
                         "private")

    def test_profile_changes_live_in_shared_store(self):
        self.publish()
        bw_servers.update_profile("jaslo", "ssh2.example.org", "web", 2222)
        shared = json.loads((self.sync / "Admin" / "servers.json").read_text(encoding="utf-8"))
        self.assertEqual(shared[0]["host"], "ssh2.example.org")
        self.assertEqual(bw_servers.load_profiles()[0]["port"], 2222)
        self.assertIn("Port 2222", (self.sshdir / "config").read_text(encoding="utf-8"))

    def test_adopt_does_not_overwrite_local_inventory_or_profiles(self):
        self.publish()
        second = self.root / "device2"
        second.mkdir()
        alternate = second / "sites.json"
        alternate.write_text('{"schema":1,"sites":[]}', encoding="utf-8")
        alternate_profiles = second / "servers.json"
        alternate_profiles.write_text("[]", encoding="utf-8")
        with patch.object(bw_sync, "CONFIG", second / "sync.json"):
            result = bw_sync.enable(self.sync, "adopt", alternate, alternate_profiles)
            self.assertEqual(len(result["local_backups"]), 2)
        self.assertEqual(json.loads(alternate.read_text(encoding="utf-8"))["sites"], [])
        self.assertEqual(json.loads(alternate_profiles.read_text(encoding="utf-8")), [])

    def test_never_overwrite_existing_syncthing_data_on_publish(self):
        self.publish()
        second = self.root / "device2"
        second.mkdir()
        with patch.object(bw_sync, "CONFIG", second / "sync.json"):
            with self.assertRaisesRegex(RuntimeError, "już istnieją"):
                bw_sync.enable(self.sync, "publish", self.sites, self.profiles)

    def test_syncthing_conflict_blocks_writes_and_reads(self):
        self.publish()
        conflict = self.sync / "Admin" / "sites.sync-conflict-20261026-012345-DEV.json"
        conflict.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "konflikt"):
            fleet.inventory()
        with self.assertRaisesRegex(RuntimeError, "konflikt"):
            bw_servers.load_profiles()

    def test_missing_share_is_error_not_local_fallback(self):
        self.publish()
        renamed = self.root / "disconnected"
        self.sync.rename(renamed)
        with self.assertRaisesRegex(RuntimeError, "niedostępny"):
            fleet.inventory()


if __name__ == "__main__":
    unittest.main()
