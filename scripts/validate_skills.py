#!/usr/bin/env python3
"""Standalone CI entry point: validate every skills/<name>/SKILL.md in this repo.

This is a thin wrapper around the same checks `esra_runtime.py validate skills`
uses, kept separate so CI and pre-publish checks don't need to touch the
runtime's state directory at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import esra_runtime  # noqa: E402


def main() -> int:
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    problems: list[str] = []
    checked = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        checked += 1
        problems.extend(esra_runtime.validate_skill_file(skill_md))

    result = {"skills_dir": str(skills_dir), "checked": checked, "problems": problems, "ok": not problems}
    print(json.dumps(result, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
