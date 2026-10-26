"""Offline tests of direct SSH probe classification and domain association."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_ssh_direct


class DirectSSHTests(unittest.TestCase):
    @patch.object(bw_ssh_direct.shutil, "which", return_value="/mnt/c/Windows/System32/OpenSSH/ssh.exe")
    @patch.object(bw_ssh_direct.subprocess, "run")
    def test_direct_probe_ignores_alias_configs(self, run, _which):
        run.return_value = SimpleNamespace(
            returncode=0, stderr="", stdout=""
        )
        state, _ = bw_ssh_direct.test_direct("ssh.example.org", "demo", 22)
        self.assertEqual(state, "OK")
        args = run.call_args.args[0]
        self.assertEqual(args[1:3], ["-F", "none"])
        self.assertIn("BatchMode=yes", args)
        self.assertEqual(args[-2:], ["ssh.example.org", "exit"])

    @patch.object(bw_ssh_direct.shutil, "which", return_value="/mnt/c/Windows/System32/OpenSSH/ssh.exe")
    @patch.object(bw_ssh_direct.subprocess, "run")
    def test_ssh_rejected_key_not_classified_as_offline(self, run, _which):
        run.return_value = SimpleNamespace(
            returncode=255, stderr="Permission denied (publickey).", stdout=""
        )
        state, _ = bw_ssh_direct.test_direct("ssh.example.org", "demo", 22)
        self.assertEqual(state, "AUTH_NEEDED")

    def test_reject_suspicious_host_values(self):
        with self.assertRaises(ValueError):
            bw_ssh_direct.test_direct("host;touch /tmp/x", "user", 22)



if __name__ == "__main__":
    unittest.main()
