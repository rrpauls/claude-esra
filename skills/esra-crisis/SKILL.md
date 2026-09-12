---
name: esra-crisis
description: Handle a high-stakes, time-pressured, or highly uncertain decision carefully, and turn a stressful failure, outage, or near-miss into a concrete resilience improvement (antifragility) rather than just a postmortem. Use when the user is dealing with production incidents, irreversible actions, data loss risk, security issues, tight deadlines with real consequences, or explicitly asks "what should I do in this situation" under pressure; also use after any failure or close call to identify what would make the system or process stronger against a repeat, not just patched for this one instance.
---

# ESRA Crisis

Consolidates the ESRA `crisis-manager` and `antifragility-builder` roles. This is the
skill for when getting it right matters more than getting it fast, or vice versa, and
the two are in tension.

## High-stakes decisions under uncertainty

1. **Stop and name the actual stakes.** What's reversible vs. irreversible here? What's
   the worst realistic outcome of acting, and of not acting?
2. **Prefer the reversible option** when stakes are high and information is
   incomplete — a change you can undo beats a slightly-better change you can't, almost
   every time.
3. **Surface what you don't know**, explicitly, rather than proceeding as if you do.
   "I don't have visibility into X, so this recommendation assumes Y" is more useful
   than a confident guess.
4. **Don't skip the value-alignment check** just because it's urgent — run the quick
   version from `esra-decisions` (a one-line honest gut-check is still better than
   none) rather than skipping it entirely. Urgency is a reason to be fast, not a reason
   to skip judgment.
5. **Escalate to the person, don't just act, when the action is irreversible, affects
   others, or is outside what they asked you to handle.** ESRA's "conservative
   behaviour when in doubt" principle means pausing to confirm beats confidently doing
   the wrong irreversible thing quickly.

## Antifragility: getting stronger from the stress, not just past it

After a failure, outage, or near-miss (including a failed `esra-experiments` run),
don't stop at "here's what happened and here's the fix." Ask the antifragility
question: **what would make this class of problem structurally less likely or less
damaging next time, not just this instance fixed?**

- Was this a one-off mistake, or a gap in a check/test/process that will recur in a
  different shape?
- Would a smaller, cheaper safeguard (a test, a guardrail, a default) have caught this
  before it became a crisis?
- Does fixing this the "quick way" leave the same gap open for next time? If so, note
  that explicitly even if you fix it the quick way for now.

Record the resilience insight the same way as any other cycle outcome:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/esra_runtime.py" record \
  --task "<short name>" --outcome <success|partial|failure|abandoned> \
  --evidence "<what actually broke and how you know>" \
  --change "<the safeguard added or proposed, not just the immediate fix>" \
  --verification "<how you'd confirm the safeguard actually helps next time>"
```

If the fix is itself risky enough to want testing first, hand off to
`esra-experiments`. If the incident reveals something structurally wrong with the ESRA
workflow itself (a skill, the runtime, a hook), hand off to `esra-reflection`'s
oversight step rather than changing it in the heat of the moment.

## What this skill does not do

It does not take irreversible action on your behalf without confirmation, does not
fabricate certainty it doesn't have to sound more reassuring, and does not treat
"antifragile" as license to take on more risk than the situation calls for —
antifragility here means designing for graceful failure and fast recovery, not seeking
out stress for its own sake.
