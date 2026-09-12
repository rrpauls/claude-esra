---
name: esra-experiments
description: Design and run a bounded, reversible experiment to test a proposed improvement before committing to it — canary, staged, A/B, or stress mode via the local esra_runtime.py, with a mandatory value-alignment score and no automatic promotion. Use when the user wants to "try a change safely", "test this before we commit", "compare the old and new approach", "see if this actually helps", or when esra-decisions or esra-orchestrator hands off an idea that needs evidence before it's adopted. Also use for systematic, incremental improvement of an existing skill, script, or process (the self-improver role): small hypothesis, small test, small integration.
---

# ESRA Experiments

Consolidates the ESRA `experimenter` and `self-improver` roles. Every experiment here is
a real, bounded command run through `scripts/esra_runtime.py experiment`, never a
simulated or hand-waved one — if you can't express the test as a runnable command, it
isn't ready to be an experiment yet.

## Before creating an experiment

Run the value-alignment check in `esra-decisions` first. You need an honest
`--alignment-score` and you should already know your `--minimum-alignment` (default
0.6). `esra_runtime.py` refuses to create or run an experiment whose alignment score is
below its own minimum — this is enforced, not just suggested.

## 1. Create the experiment

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" experiment create <name> \
  --hypothesis "the candidate keeps behavior X and improves Y" \
  --baseline-command "<the current/old command>" \
  --candidate-command "<the proposed/new command>" \
  --guardrail "<the condition that must hold, e.g. 'exit code 0 and same output shape'>" \
  --alignment-score 0.8 --minimum-alignment 0.6
```

Both commands are parsed into argument arrays and run **without a shell** — no piping,
redirection, or shell expansion. Keep them to single, self-contained commands you would
be comfortable running unattended. Never put anything that could print a secret into
either command; captured output is stored (truncated to 1,000 characters per stream) for
debugging.

## 2. Pick a mode and run it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" experiment run <name> --mode canary --timeout 30
```

| Mode | What it does | When to use |
| --- | --- | --- |
| `canary` | Runs only the candidate once | First look at a risky change |
| `staged` | Runs baseline, then candidate only if baseline succeeded | Candidate depends on a working baseline |
| `ab` | Runs baseline and candidate once each | Direct comparison |
| `stress` | Runs the candidate `--repeat` times, stops on first failure by default | Checking robustness under repetition |

Canary and staged stop after a candidate failure. A **successful canary is still only
`more-evidence`** — it can reject an unsafe candidate outright, but it cannot by itself
justify adopting it. Use `ab` or `stress` before treating a change as validated.

## 3. Report and decide

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" experiment report <name>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" experiment decide <name> \
  --decision more-evidence --notes "why"
```

`--decision` is one of `promote`, `rollback`, `more-evidence`. This records a decision;
it does **not** apply the change anywhere. Applying a promoted change (editing a file,
updating a skill, opening a PR) is a separate, explicit step you take with the user's
normal tools and normal review — `esra_runtime.py` never edits files or touches git on
its own. The runtime also blocks `promote` when the only evidence is a canary run, to
keep "it didn't crash once" from being read as "this is safe to adopt."

## Small-scale, incremental improvement (self-improver)

Not every improvement needs the full experiment lifecycle. For a small, easily-reversed
change to an existing skill, script, or process:

1. State the specific hypothesis in one sentence ("shortening this description will
   reduce under-triggering without adding false positives").
2. Make the smallest change that tests it.
3. Verify with the most direct check available (re-run the skill, re-run the tests,
   ask the user).
4. Record it: `esra_runtime.py record --task ... --outcome ... --evidence ... --change
   ... --verification ...` (see `esra-orchestrator`).

If the change is bigger, harder to reverse, or the person would want to see evidence
before trusting it, use the full experiment flow above instead of skipping straight to
editing things.
