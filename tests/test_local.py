"""BeardedWolf Admin: szybkie testy regresyjne bez połączeń z siecią."""
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))
import bw_servers  # noqa: E402

loader = SourceFileLoader("bw_cli_test", str(ROOT / "toolkit" / "bw"))
spec = importlib.util.spec_from_loader("bw_cli_test", loader)
bw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bw)


class DomainTests(unittest.TestCase):
    def test_valid_domain(self):
        self.assertEqual(bw.domain_name("Example.ORG."), "example.org")

    def test_reject_shell_payload(self):
        with self.assertRaises(Exception):
            bw.domain_name("example.org; touch /tmp/x")

    def test_reject_invalid_domain(self):
        with self.assertRaises(Exception):
            bw.domain_name("test")


class SshTests(unittest.TestCase):
    def test_valid_profile(self):
        p = bw_servers.validate("ovh-jaslo", "ssh.cluster114.hosting.ovh.net", "jaslo", "22")
        self.assertEqual(p["port"], 22)

    def test_reject_injected_hostname(self):
        with self.assertRaises(ValueError):
            bw_servers.validate("bad", "ssh.example.com\nProxyCommand evil", "u", 22)

    def test_ssh_config_keeps_external_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config"
            config.write_text("Host github.com\n    User git\n", encoding="utf-8")
            with patch.object(bw_servers, "SSH_CONFIG", config):
                content = bw_servers.make_ssh_config([
                    bw_servers.validate("myserver", "example.org", "tester", "2222")
                ])
            self.assertIn("Host github.com", content)
            self.assertIn("Host myserver", content)
            self.assertIn("    AddKeysToAgent yes", content)
            self.assertIn("    ForwardAgent no", content)
            self.assertIn("id_ed25519_bw_myserver", content)
            self.assertNotIn("id_ed25519_bw_servers\n", content)


class BundleTests(unittest.TestCase):
    def test_suite_aggregates_selected_checks(self):
        def mock_section(kind, domain):
            return [("Test", kind + ":" + domain)], kind == "TLS"

        with patch.object(bw, "report_sections", side_effect=mock_section):
            with patch.object(bw, "save_report", return_value=Path("/tmp/report.html")) as saver:
                path, failed = bw.run_suite("example.org", ["DNS", "TLS"], False)
        self.assertEqual(str(path), "/tmp/report.html")
        self.assertTrue(failed)
        args = saver.call_args.args
        self.assertEqual(args[0:2], ("PAKIET", "example.org"))
        self.assertEqual(args[2], [
            ("DNS: Test", "DNS:example.org"),
            ("TLS: Test", "TLS:example.org")
        ])


if __name__ == "__main__":
    unittest.main()
