import json
import subprocess
import sys
import tempfile
from pathlib import Path

import unittest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
HOOK_PATH = SCRIPTS_DIR / "esra_hook.py"


class TestHookAdapter(unittest.TestCase):
    def run_hook(self, payload: dict, data_dir: Path):
        env = {"ESRA_DATA_DIR": str(data_dir), "PATH": "/usr/bin:/bin"}
        return subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

    def test_silent_and_zero_exit_on_valid_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "esra-data"
            result = self.run_hook(
                {"hook_event_name": "Stop", "session_id": "abc123", "cwd": "/tmp/my-project"},
                data_dir,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            log = data_dir / "events.jsonl"
            self.assertTrue(log.exists())
            record = json.loads(log.read_text().strip().splitlines()[-1])
            self.assertEqual(record["hook_event"], "Stop")
            self.assertNotIn("abc123", json.dumps(record))  # raw session id must not leak
            self.assertEqual(record["workspace"], "my-project")

    def test_ignores_irrelevant_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "esra-data"
            result = self.run_hook({"hook_event_name": "PreToolUse"}, data_dir)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_never_fails_on_malformed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "esra-data"
            env = {"ESRA_DATA_DIR": str(data_dir), "PATH": "/usr/bin:/bin"}
            result = subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                input="not json at all {{{",
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
