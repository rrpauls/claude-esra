import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import esra_runtime  # noqa: E402


class RuntimeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name) / "esra-data"

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, argv):
        return esra_runtime.main(["--data-dir", str(self.data_dir)] + argv)


class TestDataDirResolution(RuntimeTestCase):
    def test_cli_flag_wins(self):
        self.assertEqual(esra_runtime.resolve_data_dir("/tmp/x"), Path("/tmp/x"))

    def test_env_fallbacks(self, ):
        os.environ.pop("ESRA_DATA_DIR", None)
        os.environ.pop("CLAUDE_PLUGIN_DATA", None)
        try:
            os.environ["ESRA_DATA_DIR"] = "/tmp/from-env"
            self.assertEqual(esra_runtime.resolve_data_dir(None), Path("/tmp/from-env"))
            del os.environ["ESRA_DATA_DIR"]
            os.environ["CLAUDE_PLUGIN_DATA"] = "/tmp/from-plugin-data"
            self.assertEqual(esra_runtime.resolve_data_dir(None), Path("/tmp/from-plugin-data"))
        finally:
            os.environ.pop("ESRA_DATA_DIR", None)
            os.environ.pop("CLAUDE_PLUGIN_DATA", None)

    def test_creates_private_directory(self):
        d = esra_runtime.ensure_dir(self.data_dir)
        self.assertTrue(d.exists())
        if os.name == "posix":
            mode = stat.S_IMODE(d.stat().st_mode)
            self.assertEqual(mode, 0o700)


class TestTrigger(RuntimeTestCase):
    def test_low_inputs_do_not_recommend(self):
        self.run_cli(["trigger", "--complexity", "1", "--confidence", "1.0", "--session", "s1"])
        events = esra_runtime.load_events(self.data_dir)
        self.assertFalse(events[-1]["recommend_cycle"])

    def test_high_complexity_recommends(self):
        self.run_cli(["trigger", "--complexity", "9", "--major-change", "--confidence", "0.3", "--session", "s2"])
        events = esra_runtime.load_events(self.data_dir)
        self.assertTrue(events[-1]["recommend_cycle"])

    def test_explicit_overrides_score(self):
        self.run_cli(["trigger", "--complexity", "0", "--confidence", "1.0", "--explicit", "--session", "s3"])
        events = esra_runtime.load_events(self.data_dir)
        self.assertTrue(events[-1]["recommend_cycle"])

    def test_same_session_rate_limited(self):
        self.run_cli(["trigger", "--complexity", "9", "--major-change", "--confidence", "0.1", "--session", "s4"])
        self.run_cli(["trigger", "--complexity", "9", "--major-change", "--confidence", "0.1", "--session", "s4"])
        events = esra_runtime.load_events(self.data_dir)
        self.assertFalse(events[-1]["recommend_cycle"])
        self.assertIn("already", events[-1]["reason"])

    def test_force_bypasses_rate_limit_not_score(self):
        self.run_cli(["trigger", "--complexity", "0", "--confidence", "1.0", "--session", "s5", "--force"])
        events = esra_runtime.load_events(self.data_dir)
        # Score is still low; --force only bypasses the rate limit, never the score.
        self.assertFalse(events[-1]["recommend_cycle"])


class TestRecordAndBaseline(RuntimeTestCase):
    def test_record_roundtrip(self):
        self.run_cli([
            "record", "--task", "t1", "--outcome", "success",
            "--evidence", "e", "--change", "c", "--verification", "v",
        ])
        events = esra_runtime.load_events(self.data_dir)
        self.assertEqual(events[-1]["event"], "cycle_record")
        self.assertEqual(events[-1]["outcome"], "success")

    def test_baseline_history_trims(self):
        for i in range(esra_runtime.MAX_BASELINE_HISTORY + 5):
            self.run_cli(["baseline", "--name", "kpi", "--metric", f"n={i}"])
        history_path = self.data_dir / "baselines" / "kpi.history.jsonl"
        lines = history_path.read_text().strip().splitlines()
        self.assertEqual(len(lines), esra_runtime.MAX_BASELINE_HISTORY)


class TestExperimentLifecycle(RuntimeTestCase):
    def create(self, name="exp1", alignment=0.9, minimum=0.6):
        return self.run_cli([
            "experiment", "create", name,
            "--hypothesis", "h",
            "--baseline-command", "python3 -c \"print(1)\"",
            "--candidate-command", "python3 -c \"print(1)\"",
            "--guardrail", "must exit 0",
            "--alignment-score", str(alignment),
            "--minimum-alignment", str(minimum),
        ])

    def test_create_blocks_low_alignment(self):
        with self.assertRaises(SystemExit):
            self.create(alignment=0.2, minimum=0.6)

    def test_canary_then_promote_is_blocked(self):
        self.create()
        self.run_cli(["experiment", "run", "exp1", "--mode", "canary"])
        with self.assertRaises(SystemExit):
            self.run_cli(["experiment", "decide", "exp1", "--decision", "promote"])

    def test_ab_then_promote_allowed(self):
        self.create()
        self.run_cli(["experiment", "run", "exp1", "--mode", "ab"])
        self.run_cli(["experiment", "decide", "exp1", "--decision", "promote", "--notes", "ok"])
        record = json.loads((self.data_dir / "experiments" / "exp1.json").read_text())
        self.assertEqual(record["decision"]["choice"], "promote")

    def test_stress_stops_on_failure(self):
        self.create()
        # candidate command exits nonzero
        record_path = self.data_dir / "experiments" / "exp1.json"
        record = json.loads(record_path.read_text())
        record["candidate_command"] = "python3 -c \"import sys; sys.exit(1)\""
        record_path.write_text(json.dumps(record))
        self.run_cli(["experiment", "run", "exp1", "--mode", "stress", "--repeat", "5"])
        record = json.loads(record_path.read_text())
        last_run = record["runs"][-1]
        self.assertEqual(len(last_run["steps"]), 1)
        self.assertIn("stopped_early", last_run)

    def test_report_writes_markdown(self):
        self.create()
        self.run_cli(["experiment", "run", "exp1", "--mode", "canary"])
        self.run_cli(["experiment", "report", "exp1"])
        report_path = self.data_dir / "experiments" / "reports" / "exp1.md"
        self.assertTrue(report_path.exists())


class TestValidateSkills(RuntimeTestCase):
    def test_bundled_skills_pass(self):
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        problems = []
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            problems.extend(esra_runtime.validate_skill_file(skill_md))
        self.assertEqual(problems, [], f"skills failed validation: {problems}")

    def test_cli_reports_ok_for_bundled_skills(self):
        skills_dir = Path(__file__).resolve().parent.parent / "skills"
        # Should return normally (no SystemExit) when there are no problems.
        self.run_cli(["validate", "skills", "--skills-dir", str(skills_dir)])

    def test_detects_missing_description(self):
        skills_dir = Path(self.data_dir) / "fixture-skills"
        skill_dir = skills_dir / "broken-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: broken-skill\n---\nbody\n")
        problems = esra_runtime.validate_skill_file(skill_dir / "SKILL.md")
        self.assertTrue(any("description" in p for p in problems))


class TestDashboardAndAudit(RuntimeTestCase):
    def test_dashboard_counts_events(self):
        self.run_cli(["record", "--task", "t", "--outcome", "failure", "--evidence", "e", "--change", "c", "--verification", "v"])
        self.run_cli(["dashboard", "--json"])  # dashboard is read-only; must not raise
        events = esra_runtime.load_events(self.data_dir)
        kinds = [e["event"] for e in events]
        self.assertIn("cycle_record", kinds)

    def test_audit_surfaces_non_success(self):
        self.run_cli(["record", "--task", "t", "--outcome", "failure", "--evidence", "e", "--change", "c", "--verification", "v"])
        self.run_cli(["audit"])
        events = esra_runtime.load_events(self.data_dir)
        audit_events = [e for e in events if e["event"] == "audit"]
        self.assertEqual(audit_events[-1]["non_success"], 1)


class TestOversight(RuntimeTestCase):
    def test_oversight_writes_local_file_only(self):
        self.run_cli([
            "oversight", "--id", "test-1", "--title", "Title",
            "--summary", "Summary", "--evidence", "ev1", "--verification", "how",
        ])
        path = self.data_dir / "oversight" / "test-1.md"
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("does not create a branch", content)


class TestSymlinkRefusal(RuntimeTestCase):
    def test_refuses_symlinked_state_file(self):
        esra_runtime.ensure_dir(self.data_dir)
        target = Path(self._tmp.name) / "elsewhere.json"
        target.write_text("{}")
        link = self.data_dir / "state.json"
        os.symlink(target, link)
        with self.assertRaises(SystemExit):
            esra_runtime.safe_open(link, "w")


if __name__ == "__main__":
    unittest.main()
