"""Pure offline unit tests for registry integrity and SSH endpoint safety."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_integrity


def site(domain="example.org", *, kind="wordpress", alias="prod",
         root="/home/app", access="ssh", host="ssh.cluster126.hosting.ovh.net"):
    return {"domain": domain, "type": kind, "ssh_alias": alias,
            "wp_root": root, "hosting": {"provider": "OVHcloud",
            "access": access, "host": host}}


class IntegrityTests(unittest.TestCase):
    profiles = [{"alias": "prod", "host": "ssh.cluster126.hosting.ovh.net",
                 "user": "web", "port": 22}]

    def test_matching_ssh_host_is_clean(self):
        self.assertIsNone(bw_integrity.profile_endpoint_check(site(), self.profiles))
        self.assertEqual(bw_integrity.audit_inventory([site()], self.profiles), [])

    def test_wrong_ssh_host_is_error(self):
        row = site(host="ssh.cluster114.hosting.ovh.net")
        issues = bw_integrity.audit_inventory([row], self.profiles)
        self.assertEqual(issues[0]["severity"], "BŁĄD")
        self.assertIn("cluster114", issues[0]["message"])
        self.assertIn("cluster126", issues[0]["message"])

    def test_known_host_case_and_final_dot(self):
        row = site(host="SSH.Cluster126.Hosting.OVH.Net.")
        self.assertIsNone(bw_integrity.profile_endpoint_check(row, self.profiles))

    def test_same_cluster_ovh_aliases(self):
        profile = [dict(self.profiles[0], host="ssh01.cluster126.gra.hosting.ovh.net")]
        self.assertIsNone(bw_integrity.profile_endpoint_check(site(), profile))

    def test_unknown_hostname_equivalence_is_only_warning(self):
        profile = [dict(self.profiles[0], host="ssh-alias.example.org")]
        result = bw_integrity.profile_endpoint_check(site(), profile)
        self.assertEqual(result[0], "UWAGA")

    def test_missing_profile_is_error(self):
        issues = bw_integrity.audit_inventory(
            [site(alias="unknown")], self.profiles)
        self.assertEqual(issues[0]["severity"], "BŁĄD")

    def test_ftp_not_assumed_to_be_ssh(self):
        row = site(access="ftp", host="ftp.cluster130.hosting.ovh.net")
        self.assertIsNone(bw_integrity.profile_endpoint_check(row, self.profiles))
        issues = bw_integrity.audit_inventory([row], self.profiles)
        self.assertTrue(any("różne protokoły" in x["message"] for x in issues))
        self.assertFalse(any(x["severity"] == "BŁĄD" for x in issues))

    def test_redirect_with_ssh_has_advisory(self):
        row = site(domain="bip.jdkjaslo.pl", kind="przekierowanie", root=None)
        issues = bw_integrity.audit_inventory([row], self.profiles)
        self.assertTrue(any(x["category"] == "Przekierowanie" for x in issues))
        self.assertFalse(any(x["severity"] == "BŁĄD" for x in issues))

    def test_missing_wordpress_path_is_warning(self):
        issues = bw_integrity.audit_inventory(
            [site(root=None)], self.profiles)
        self.assertEqual(issues[0]["category"], "WordPress")
        self.assertEqual(issues[0]["severity"], "UWAGA")

    def test_no_ssh_alias_root_is_error(self):
        issues = bw_integrity.audit_inventory(
            [site(alias=None)], self.profiles)
        self.assertEqual(issues[0]["severity"], "BŁĄD")

    def test_no_mutation(self):
        row = site()
        data = {"sites": [row], "profiles": list(self.profiles)}
        import copy
        before = copy.deepcopy(data)
        bw_integrity.audit_inventory(data["sites"], data["profiles"])
        self.assertEqual(data, before)

    def test_summary(self):
        issues = bw_integrity.audit_inventory([
            site("a.org", root=None), site("b.org", kind="sprawdzic")
        ], self.profiles)
        self.assertEqual(bw_integrity.audit_summary(issues)["warnings"], 1)
        self.assertEqual(bw_integrity.audit_summary(issues)["info"], 1)


if __name__ == "__main__":
    unittest.main()
