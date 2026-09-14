import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.build_installer import build


ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def test_archive_is_a_self_contained_claude_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "claude-esra.zip"
            build(output)

            with ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn(".claude-plugin/plugin.json", names)
                self.assertIn("INSTALL.md", names)
                self.assertIn("hooks/hooks.json", names)
                self.assertEqual(
                    len([name for name in names if name.endswith("/SKILL.md")]),
                    5,
                )
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith("build_installer.py") for name in names))

                manifest = json.loads(archive.read(".claude-plugin/plugin.json"))
                conformance = json.loads(archive.read("esra-conformance.json"))
                self.assertEqual(manifest["name"], "claude-esra")
                self.assertEqual(manifest["version"], conformance["implementation_version"])


if __name__ == "__main__":
    unittest.main()
