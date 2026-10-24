"""FileZilla XML: lokalny odczyt bez ujawniania haseł, bez sieci."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_filezilla


EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<FileZilla3 version="3.70.6" platform="windows">
  <Servers>
    <Folder expanded="1">Hosting
      <Server>
        <Host>ftp.cluster130.hosting.ovh.net</Host>
        <Port>21</Port>
        <Protocol>0</Protocol>
        <User>parkowd</User>
        <Pass encoding="base64">U2VrcmV0TmllRG9Qb2themFuaWE=</Pass>
        <Name>Parkowa</Name>
        <LocalDir>C:\\Users\\User\\Secret</LocalDir>
        <RemoteDir>1 0 4 home 6 public</RemoteDir>
      </Server>
      <Server>
        <Host>ssh.example.org</Host>
        <Port>22</Port>
        <Protocol>1</Protocol>
        <User>tester</User>
        <Pass encoding="base64">QUJDRDEyMzQ=</Pass>
        <Name>Serwer SFTP</Name>
      </Server>
    </Folder>
  </Servers>
</FileZilla3>
"""


class FileZillaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "FileZilla.xml"
        self.file.write_text(EXPORT, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_no_secrets_in_any_output(self):
        result = bw_filezilla.read_export(self.file)
        self.assertEqual(len(result), 2)
        first, second = result
        self.assertEqual(first["host"], "ftp.cluster130.hosting.ovh.net")
        self.assertEqual(first["user"], "parkowd")
        self.assertEqual(first["port"], 21)
        self.assertEqual(first["access"], "ftp")
        self.assertEqual(second["access"], "sftp")
        self.assertNotIn("Pass", repr(result))
        self.assertNotIn("U2VrcmV0", repr(result))
        self.assertNotIn("QUJDRDEyMzQ", repr(result))
        self.assertNotIn("RemoteDir", repr(result))
        self.assertNotIn("LocalDir", repr(result))

    def test_reject_xml_dtd_entities(self):
        self.file.write_text(
            '<!DOCTYPE FileZilla3 [<!ENTITY evil SYSTEM "file:///etc/passwd">]>'
            "<FileZilla3><Servers></Servers></FileZilla3>", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            bw_filezilla.read_export(self.file)

    def test_reject_invalid_xml(self):
        self.file.write_text("<FileZilla3><Servers></FileZilla3>", encoding="utf-8")
        with self.assertRaises(ValueError):
            bw_filezilla.read_export(self.file)

    def test_reject_unsupported_root(self):
        self.file.write_text("<foo/>", encoding="utf-8")
        with self.assertRaises(ValueError):
            bw_filezilla.read_export(self.file)

    def test_unknown_protocol_not_assumed_to_be_ssh(self):
        self.file.write_text(
            "<FileZilla3><Servers><Server><Host>example.org</Host>"
            "<Protocol>999</Protocol></Server></Servers></FileZilla3>",
            encoding="utf-8"
        )
        self.assertEqual(bw_filezilla.read_export(self.file)[0]["access"], "unknown")


if __name__ == "__main__":
    unittest.main()
