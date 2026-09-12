from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import esra_export  # noqa: E402


class ExportTests(unittest.TestCase):
    def test_exports_schema_shaped_events_and_redacts_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            records = [
                {
                    "ts": "2026-09-12T18:00:00+00:00",
                    "event": "cycle_record",
                    "id": "cycle-1",
                    "task": "adapter",
                    "outcome": "success",
                    "evidence": "tests passed",
                    "verification": "schema validation",
                    "prompt": "private prompt",
                    "stdout": "secret output",
                    "session": "raw-session",
                },
                {
                    "ts": "2026-09-12T18:01:00+00:00",
                    "event": "experiment_blocked",
                    "name": "exp-1",
                },
            ]
            (base / "events.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
            )

            exported = esra_export.export_events(base)
            self.assertEqual(len(exported), 2)
            self.assertEqual(exported[0]["implementation"], "claude-esra")
            self.assertEqual(exported[0]["event_type"], "integration")
            self.assertEqual(exported[0]["outcome"], "success")
            self.assertEqual(exported[1]["outcome"], "not-run")
            raw = json.dumps(exported)
            self.assertNotIn("private prompt", raw)
            self.assertNotIn("secret output", raw)
            self.assertNotIn("raw-session", raw)

    def test_output_is_deterministic_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / "data"
            base.mkdir()
            (base / "events.jsonl").write_text(
                '{"ts":"2026-09-12T18:00:00Z","event":"trigger","recommend_cycle":true}\n',
                encoding="utf-8",
            )
            first = esra_export.export_events(base)
            second = esra_export.export_events(base)
            self.assertEqual(first, second)
            output = Path(temporary) / "portable.jsonl"
            esra_export.write_jsonl(first, str(output))
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(output.read_text()), first[0])


if __name__ == "__main__":
    unittest.main()
