---
name: esra-decisions
description: Structure a non-trivial decision with an Observe-Orient-Decide-Act pass, a mandatory value-alignment check, and (when consequences are non-obvious) a trade-off/ethics review plus a systems-dynamics pass for feedback loops and leverage points. Use before any experiment, before proposing a structural change to a skill/workflow/architecture, when the user asks "should I do X or Y", "what are the trade-offs", "think this through with me", or when a choice has second- or third-order consequences worth surfacing before acting. This is the mandatory gate esra-experiments calls before any experiment is designed.
---

# ESRA Decisions

Consolidates the ESRA `value-clarifier`, `optimizer-philosopher`, and
`system-dynamics-thinker` roles into one on-demand decision workflow. Use it whenever a
choice is big enough that skipping straight to "just do it" would be a mistake, and
always before `esra-experiments` designs an experiment.

## 1. Orient with OODA

- **Observe**: What actually happened or what is actually being asked? Stick to
  evidence in the conversation and any files/commands you've actually inspected — not
  assumptions.
- **Orient**: What's the real goal underneath the literal request? What constraints
  (time, risk, reversibility, who else is affected) matter here?
- **Decide**: List the live options, including "do nothing" and "ask the user first."
- **Act**: Name the smallest next step, not the whole plan.

Keep this brief for small decisions — a sentence per step is often enough. Expand it
for anything structural or hard to reverse.

## 2. Value-alignment check (mandatory before any experiment)

Before `esra-experiments` runs anything, or before proposing a structural change,
answer honestly:

- Does this serve what the user actually asked for, or does it serve a tangential goal
  (e.g., "make the code more elegant" when they asked for a bug fix)?
- Would the user be comfortable if they saw exactly what this does, with no
  euphemisms?
- Is there a lower-risk way to get the same benefit?
- Score alignment 0.0–1.0 honestly. Low scores (below ~0.6) mean: don't run the
  experiment, or scope it down until the score is defensible. This score is what
  `esra_runtime.py experiment create --alignment-score` records, and the runtime
  refuses to create or run an experiment below its own `--minimum-alignment` threshold.

This gate is non-optional in the sense that skipping it is itself the failure mode ESRA
exists to prevent — but it is a step *you* reason through, not a hidden numeric model
enforced against you. Say the score and the reasoning out loud to the user for anything
non-trivial.

## 3. Trade-off and ethics pass (optimizer-philosopher)

For decisions with real stakes, make the trade-offs explicit rather than implicit:

- What is gained, what is given up, and who bears the cost of each?
- Is there a values conflict being smoothed over (e.g., speed vs. correctness, user
  convenience vs. their stated long-term interest)?
- What would you tell the user if they asked "what am I not seeing here"? Tell them
  that, unprompted, as part of the recommendation.

## 4. Systems-dynamics pass (leverage points)

For decisions that affect a recurring workflow, a shared codebase, or anything with
feedback loops:

- Where is the actual bottleneck, versus where does it merely feel like the problem is?
- Is this a one-off fix or does it change a stock (accumulated state) or a flow (rate of
  change)? Fixes to flows compound; fixes to one-off symptoms don't.
- Could this change create a new failure mode under repetition or scale, even if it
  looks fine once?
- Prefer the highest-leverage change that is still reversible over the most thorough
  change that isn't.

## 5. Output

State, in a few lines: the decision, the alignment score and why, the main trade-off,
and (if relevant) the leverage point being targeted. Hand off to:

- `esra-experiments` if the decision needs to be tested before committing.
- `esra-crisis` if this is a high-stakes or time-pressured call with real uncertainty.
- The user directly if the decision is really theirs to make and your job here is just
  to lay out the options clearly.

## What this skill deliberately does not do

It does not claim insight into anyone's hidden motives, including the user's or
Claude's own. It reasons from what's observable in the conversation and states
assumptions explicitly rather than presenting guesses as facts. It never blocks the
user from proceeding — a low alignment score is a strong recommendation to reconsider
or rescope, not a hard technical block outside of what `esra_runtime.py` enforces for
experiments it actually runs.
