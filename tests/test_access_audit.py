"""Offline tests for endpoint export and remote path parsing."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_access
import bw_paths


class AccessAuditTests(unittest.TestCase):
    def test_ssh_parser_exports_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config"
            path.write_text(
                "Host jaslo\n HostName ssh.example.org\n User u123\n"
                " Port 22\n IdentityFile ~/.ssh/sensitive_key\n"
                "Host *\n ProxyCommand false\n", encoding="utf-8"
            )
            rows = bw_access.parse_ssh_config(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["host"], "ssh.example.org")
            self.assertNotIn("IdentityFile", str(rows))
            self.assertNotIn("ProxyCommand", str(rows))

    def test_ssh_path_discovery_read_only(self):
        profiles = [{"alias": "jaslo", "host": "ssh.example.org",
                     "user": "u", "port": 22}]
        response = SimpleNamespace(
            returncode=0, stderr="",
            stdout="/home/u/site/wp-includes/version.php\n"
        )
        with patch.object(bw_paths.bw_servers, "load_profiles",
                          return_value=profiles):
            with patch.object(bw_paths.subprocess, "run",
                              return_value=response) as call:
                paths = bw_paths.ssh_roots("jaslo")
        self.assertEqual(paths, ["/home/u/site"])
        command = call.call_args.args[0]
        self.assertIn("BatchMode=yes", command)
        self.assertIn("StrictHostKeyChecking=yes", command)
        self.assertIn("-type f", command[-1])


if __name__ == "__main__":
    unittest.main()
