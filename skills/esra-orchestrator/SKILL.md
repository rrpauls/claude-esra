---
name: esra-orchestrator
description: Conduct one bounded Evolutionary Self-Recursive Architecture (ESRA) cycle — a structured, value-aligned, human-reviewed self-improvement pass over a completed task, a new skill, or a recurring failure pattern. Use this whenever the user says "orchestrate evolution", "run an ESRA cycle", "run a self-improvement cycle", or asks to review/audit how a task or skill went; also consult it after any complex multi-step task, after creating or editing a skill, or after a significant course-correction, to recommend (never force) whether a cycle is worth running. Routes to esra-decisions, esra-experiments, esra-reflection, and esra-crisis for the deeper stages, and documents the esra_runtime.py CLI paths.
---

# ESRA Orchestrator

This is the entry point for the Claude Code implementation of **ESRA — Evolutionary
Self-Recursive Architecture** (spec: https://github.com/rrpauls/esra, provenance:
https://github.com/rrpauls/hermes-esra). It conducts one full or partial ESRA cycle by
routing to the other four skills in this plugin and to the local runtime.

**What ESRA is here.** A repeatable checklist for turning "that went well/badly" into a
concrete, evidence-backed, reversible change — with an explicit value-alignment gate
before anything is tried, and a human decision before anything is kept. It is not a
claim that Claude has persistent goals, hidden state, or the ability to modify itself
outside of the current conversation. Every "cycle" here is bounded to the current
session's evidence and ends in a proposal, not an autonomous action.

## When to run a cycle

Recommend a cycle after:
- A complex, multi-step task finishes (successfully or not).
- A new skill, command, or agent is created or substantially edited.
- The user explicitly asks for one ("orchestrate evolution", "run full ESRA cycle",
  "audit this").
- A repeated failure pattern shows up across a conversation.

Do **not** run a cycle for routine, single-step requests — that defeats the purpose and
wastes the person's time. When in doubt, ask via the `trigger` command below rather than
assuming.

## Step 1 — Get (or produce) a trigger recommendation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" trigger \
  --complexity 7 --major-change --confidence 0.6 --session "<short session tag>"
```

- `--complexity` 0–10, your own honest estimate of how involved the task was.
- `--major-change` / `--new-skill` are flags for the corresponding conditions above.
- `--confidence` 0.0–1.0, your confidence in the task's outcome; lower confidence raises
  the recommendation score.
- `--explicit` if the user asked directly; this overrides the score.

The command returns a JSON recommendation only — `{"recommend_cycle": true/false, ...}`.
It is rate-limited (one recommendation per session tag, three per UTC day) so it does
not nag. **It never starts a cycle itself.** Tell the user what it recommends and why,
then ask or proceed based on their preference.

## Step 2 — Run the stages that apply

A full cycle walks through the other four skills in this plugin, each of which is also
independently triggerable:

| Stage | Skill | Produces |
| --- | --- | --- |
| Observe + reflect | `esra-reflection` | Observation notes, a revised working rule |
| Value-align + analyze | `esra-decisions` | An alignment check, trade-off analysis |
| Experiment | `esra-experiments` | A bounded, reversible test and its evidence |
| Antifragility / high-stakes | `esra-crisis` | What would make this more robust under stress |
| Meta-audit (periodic) | `esra-reflection` (audit mode) | Pattern review across recorded cycles |

A **fast cycle** skips straight to `esra-experiments` when the idea is small and
reversible. A **value cycle** runs only `esra-decisions` when direction, not
implementation, is in question. An **audit cycle** runs only the audit mode in
`esra-reflection`. Pick the smallest cycle that fits — do not run all four stages for a
one-line fix.

## Step 3 — Record the outcome

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" record \
  --task "short task name" \
  --outcome success \
  --evidence "what you observed, one line" \
  --change "what was actually changed, if anything" \
  --verification "how you or the user checked it"
```

`--outcome` is one of `success`, `partial`, `failure`, `abandoned`. This just appends a
line to a private local log (`events.jsonl`) — it is not visible to anyone but this
Claude Code installation, and it never leaves the machine.

## Step 4 — Check the dashboard or audit periodically

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" dashboard
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" audit --limit 10
```

`audit` is a pattern-level summary over the local log (counts, recent non-success
outcomes) — not a claim about hidden model state. Every 3–5 cycles, or when something
looks systematically wrong, consider `esra-reflection`'s audit mode for a deeper,
narrative pass, and — if a structural change to a skill or the runtime looks warranted —
`esra-runtime.py oversight` to write a local, human-reviewed proposal (see
`esra-reflection`). Nothing in this plugin creates a git commit, branch, issue, or pull
request on its own; those stay explicit, user-authorized actions.

## Runtime location and validation

The runtime is `scripts/esra_runtime.py` inside this plugin
(`${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py`), a dependency-free, stdlib-only Python
3 script. Full command reference: `docs/RUNTIME.md` in this plugin. To sanity-check the
five skills themselves (frontmatter, naming, size):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" validate skills
```

State lives under `$CLAUDE_PLUGIN_DATA` (Claude Code's per-plugin persistent directory)
by default, or `--data-dir` / `$ESRA_DATA_DIR` to override. See `docs/HERMES_PARITY.md`
for how this maps back to the original Hermes implementation and what was deliberately
left out or changed for Claude Code's permission and plugin model.
