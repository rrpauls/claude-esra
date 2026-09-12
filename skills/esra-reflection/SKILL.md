---
name: esra-reflection
description: Honestly review what happened in a task using only observable evidence (no claims about hidden internal state), update a concrete "working rule" for next time, and — periodically, or when a pattern of problems shows up — run a meta-audit over the local ESRA event log and write a human-reviewed oversight proposal for a structural change. Use when the user asks "what went wrong", "what should we do differently next time", "review our recent cycles", "audit the loop", or after esra-orchestrator records a non-success outcome. This is also the right skill for "did this skill/process actually work across the last few times we used it".
---

# ESRA Reflection

Consolidates the ESRA `self-observer`, `mental-model-updater`, and `loop-auditor` roles.

## Self-observation: evidence only

When reviewing how a task went, stick to what's actually observable in this
conversation and any files/commands/output you inspected:

- What was asked, what was tried, what happened (success, partial, failure, or
  abandoned)?
- What evidence supports that verdict — a test passing, output matching expectations,
  the user confirming it, an error message?
- What surprised you, if anything?

**Do not** describe this as insight into "internal state," "hidden reasoning," or
anything Claude cannot actually observe from the transcript and tool results. ESRA is a
functional workflow for improving observable outcomes, not a claim about consciousness,
introspective access, or persistent memory across sessions — state only what the
evidence in front of you actually shows.

## Mental-model update: the revised working rule

Turn the observation into one concrete, testable rule for next time — a diff to how you
approach a similar situation, not a vague resolution:

- Bad: "I should be more careful with edge cases."
- Better: "When editing a shared config file, check for other files that import it
  before assuming the edit is self-contained."

Write the before/after as an explicit small diff-like statement (old approach → new
approach) so it's checkable, not just felt. If the rule is about a specific file,
skill, or script, propose the actual edit to the user rather than only describing it.

## Recording

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" record \
  --task "<short name>" --outcome <success|partial|failure|abandoned> \
  --evidence "<what you observed>" \
  --change "<the revised working rule, or 'none' if unchanged>" \
  --verification "<how this could be checked next time>"
```

## Meta-audit (loop-auditor)

Run this every 3–5 recorded cycles, when a failure pattern repeats, or on explicit
request ("audit the loop"):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" audit --limit 10
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" dashboard --json
```

This returns counts and recent non-success entries from the local log — a pattern
summary, not a claim about anything beyond what was actually recorded. Look for:

- The same kind of task failing or going only "partial" more than once.
- Triggers being recommended but consistently declined (a sign the scoring or the
  workflow itself needs adjusting, not just the individual tasks).
- Experiments stuck at `more-evidence` repeatedly (a sign the experiment design, not
  the candidate, may be the problem).

## Proposing a structural change

If the audit surfaces something worth changing about a skill, the runtime, or the
overall workflow, write it up as a local, human-reviewed proposal rather than editing
anything directly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" oversight \
  --id "shorten-trigger-threshold" \
  --title "Raise the routine-task boundary in esra_runtime.py trigger" \
  --summary "Two of the last five recommendations were declined as too eager." \
  --evidence "audit: 2/5 recommended cycles marked abandoned" \
  --evidence "both were single-file, low-complexity edits" \
  --verification "re-run the same five scenarios; confirm the two edge cases now score below 0.5"
```

This writes a Markdown file under the local ESRA data directory with a suggested branch
name and verification plan. **It does not create a git branch, commit, issue, or pull
request.** Making the actual change (editing `esra_runtime.py`, a `SKILL.md`, or
`hooks/hooks.json`) and committing it are explicit, user-authorized actions you take
normally — the proposal exists so that structural, recursive changes to this plugin
always pass through a visible, reviewable step before anyone applies them, in keeping
with ESRA's "Loop-Auditor has the right of veto over dangerous changes" principle, read
here as "nothing structural ships without a human seeing the diff and evidence first."
