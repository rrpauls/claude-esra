import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = tuple(sorted((ROOT / "skills").glob("*/SKILL.md")))


class SkillQualityTests(unittest.TestCase):
    def test_every_skill_has_a_routine_bypass_or_narrow_trigger(self):
        for path in SKILLS:
            text = path.read_text(encoding="utf-8").lower()
            has_boundary = any(
                phrase in text
                for phrase in (
                    "skip routine",
                    "not required for ordinary",
                    "skip straightforward",
                    "skip ordinary",
                    "routine answers",
                    "recurring errors",
                )
            )
            self.assertTrue(has_boundary, path.parent.name)

    def test_orchestrator_blocks_recursive_reviews(self):
        text = (ROOT / "skills" / "esra-orchestrator" / "SKILL.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("never let an esra review", text)
        self.assertIn("one review per primary task", text)

    def test_focused_skills_do_not_require_companion_activation(self):
        for path in SKILLS:
            if path.parent.name == "esra-orchestrator":
                continue
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn("mandatory before", text, path.parent.name)
            self.assertNotIn("mandatory gate", text, path.parent.name)


if __name__ == "__main__":
    unittest.main()
