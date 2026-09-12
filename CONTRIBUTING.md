# Contributing

1. Before any change: `python3 -m py_compile scripts/*.py && python3 -m unittest
   discover -s tests -v && python3 scripts/validate_skills.py`.
2. Keep `scripts/` dependency-free (stdlib only). If a change genuinely needs a
   third-party package, discuss it in an issue first — one of this plugin's operational
   guarantees is that it never shells out for package installs on its own.
3. Skill changes: run `python3 scripts/esra_runtime.py validate skills` and keep each
   `SKILL.md` under roughly 500 lines; split into a `references/` file if it grows past
   that.
4. Any change to `hooks/hooks.json` or `scripts/esra_hook.py` must keep the hook silent
   on stdout, exiting 0 unconditionally, and free of prompt/transcript/tool-I/O content
   in what it logs — this is covered by `tests/test_hook.py`.
5. Prefer branches `feature/…` for roadmap work or `evolve/skill-name-vN` for skill
   evolution proposed via `esra_runtime.py oversight` (see `docs/RUNTIME.md`).
6. For structural changes to a skill or the runtime, write an oversight proposal first:
   `python3 scripts/esra_runtime.py oversight --id ... --title ... --summary ...
   --evidence ... --verification ...`. This is a local Markdown artifact meant to make
   the change reviewable before it's applied — it doesn't replace a normal PR
   description, it feeds one.
7. Before publishing a release, run `claude plugin validate ./claude-esra --strict`
   (requires a local Claude Code install) to catch manifest and frontmatter issues the
   test suite here can't see.

Details and phase plan, once one exists, belong in `ROADMAP.md`.
