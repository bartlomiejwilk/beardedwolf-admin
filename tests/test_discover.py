"""Testy offline rozpoznawania platformy HTTP, bez zapytań do internetu."""
from email.message import Message
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_discover


class Response:
    def __init__(self, body, status=200, content_type="text/html", link=None):
        self.body = io.BytesIO(body.encode("utf-8"))
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if link is not None:
            self.headers["Link"] = link

    def read(self, size):
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()


class DiscoverTests(unittest.TestCase):
    def inspect(self, response):
        with patch.object(
            bw_discover.subprocess, "run",
            return_value=SimpleNamespace(returncode=0, stdout="")
        ), patch.object(
            bw_discover.urllib.request, "build_opener",
            return_value=SimpleNamespace(open=lambda req, timeout: response)
        ):
            return bw_discover.inspect_public("example.org")

    def test_wordpress_api_and_asset_strong(self):
        result = self.inspect(Response(
            '<html><link rel="stylesheet" href="/wp-content/themes/x/style.css"></html>',
            link='<https://example.org/wp-json/>; rel="https://api.w.org/"'
        ))
        self.assertEqual(result["type_suggestion"], "wordpress")
        self.assertEqual(result["confidence"], "wysoka")

    def test_wordpress_asset_alone_weak(self):
        result = self.inspect(Response(
            '<html><script src="/wp-content/plugins/a.js"></script></html>'
        ))
        self.assertEqual(result["confidence"], "wstępna")

    def test_other_site_is_unresolved(self):
        result = self.inspect(Response("<html><title>Welcome</title></html>"))
        self.assertIsNone(result["type_suggestion"])
        self.assertEqual(result["confidence"], "brak")

    def test_no_html_no_fingerprint(self):
        result = self.inspect(Response('{"ok":true}', content_type="application/json"))
        self.assertIsNone(result["type_suggestion"])

    def test_response_is_read_limited(self):
        result = self.inspect(Response(
            "<html>" + "a" * (bw_discover.MAX_PAGE + 5000) +
            '<meta name="generator" content="WordPress 9.0"></html>'
        ))
        self.assertIsNone(result["type_suggestion"])


if __name__ == "__main__":
    unittest.main()
