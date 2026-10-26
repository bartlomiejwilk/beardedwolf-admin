"""Device-local SSH pause must never edit synchronized profiles or key files."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_local_ssh
import bw_servers


class LocalSSHTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patcher = patch.object(bw_servers, "CONFIG_DIR", self.root)
        self.patcher.start()
        self.profiles = [
            {"alias": "jaslo", "host": "ssh.cluster114.hosting.ovh.net",
             "user": "jaslo", "port": 22},
            {"alias": "jdk", "host": "ssh.cluster126.hosting.ovh.net",
             "user": "jdkjasj", "port": 22},
        ]

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_without_pause_all_profiles_are_active(self):
        self.assertEqual(bw_servers.locally_active_profiles(self.profiles),
                         self.profiles)

    def test_paused_list_is_empty(self):
        (self.root / bw_servers.PAUSE_NAME).write_text(
            json.dumps({"schema": 1, "enabled": []}), encoding="utf-8"
        )
        self.assertEqual(bw_servers.locally_active_profiles(self.profiles), [])
        with self.assertRaises(RuntimeError):
            bw_servers.require_ssh_enabled("jaslo")

    def test_selective_enable(self):
        (self.root / bw_servers.PAUSE_NAME).write_text(
            json.dumps({"schema": 1, "enabled": ["jdk"]}), encoding="utf-8"
        )
        self.assertEqual([p["alias"] for p in
                          bw_servers.locally_active_profiles(self.profiles)],
                         ["jdk"])
        bw_servers.require_ssh_enabled("jdk")
        with self.assertRaises(RuntimeError):
            bw_servers.require_ssh_enabled("jaslo")

    def test_invalid_pause_file_is_not_ignored(self):
        (self.root / bw_servers.PAUSE_NAME).write_text("not json")
        with self.assertRaises(ValueError):
            bw_servers.locally_active_profiles(self.profiles)

    def test_pause_operation_uses_only_local_marker(self):
        with patch.object(bw_local_ssh, "backup", return_value=self.root), \
             patch.object(bw_servers, "load_profiles",
                          return_value=self.profiles):
            bw_local_ssh.pause()
        pausefile = self.root / bw_servers.PAUSE_NAME
        self.assertTrue(pausefile.is_file())
        self.assertEqual(json.loads(pausefile.read_text())["enabled"], [])


if __name__ == "__main__":
    unittest.main()
