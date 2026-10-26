"""Windows saved connections: offline tests without touching Windows secrets."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "toolkit"))
import bw_windows_saved as win

class SavedWindowsTests(unittest.TestCase):
    def test_filezilla_site_path_and_no_password_extraction(self):
        xml = """<?xml version="1.0"?>
<FileZilla3><Servers><Folder>Folder<Server>
<Host>ftp.example.org</Host><Port>21</Port><Protocol>0</Protocol>
<User>demo</User><Pass encoding="base64">Tk9UX0FfUkVBTF9QQVNT</Pass>
<Name>My site</Name></Server></Folder></Servers></FileZilla3>"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"sitemanager.xml"
            path.write_text(xml,encoding="utf-8")
            records = win.filezilla_sites(path)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["path"],"0/Folder/My site")
        self.assertNotIn("Pass",records[0])
        self.assertNotIn("password",records[0])
    def test_windows_ssh_aliases_ignore_wildcards(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"config"
            path.write_text("Host *\nHost canis\nHost SSH-prod\nHost prefix*\n",encoding="utf-8")
            self.assertEqual(win.windows_ssh_aliases(path),["canis","SSH-prod"])
    def test_invalid_windows_ssh_is_rejected(self):
        with self.assertRaises(ValueError):
            win.connect_windows_ssh("prod;whoami")

if __name__=="__main__":
    unittest.main()
