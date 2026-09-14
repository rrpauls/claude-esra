# ESRA for Claude Code

**Claude Code implementation of ESRA — Evolutionary Self-Recursive Architecture**

Five on-demand skills plus a dependency-free local runtime that make deliberate,
value-aligned self-improvement structured, auditable, bounded, and reversible — without
ever auto-executing a cycle, auto-promoting an experiment, or touching git/GitHub on
its own.

[ESRA specification](https://github.com/rrpauls/esra) ·
[Hermes implementation](https://github.com/rrpauls/hermes-esra) ·
[OpenAI/Codex implementation](https://github.com/rrpauls/chatgpt-esra) ·
[Installation](INSTALL.md) ·
[Hermes parity](docs/HERMES_PARITY.md) · [Runtime guide](docs/RUNTIME.md) ·
[Compatibility matrix](https://github.com/rrpauls/esra/blob/main/conformance/compatibility-matrix.json) ·
[Apache-2.0 License](LICENSE)

## What this is

ESRA turns "that went well/badly" into a repeatable checklist: observe, value-align,
analyze, experiment, integrate, and — periodically — audit the loop itself. This
repository is a portable Claude Code plugin implementation that maps the intended
workflow coverage of [`hermes-esra`](https://github.com/rrpauls/hermes-esra) and
follows the same consolidation approach as
[`chatgpt-esra`](https://github.com/rrpauls/chatgpt-esra), while using Claude Code's own
plugin manifest, skill discovery, hooks, and permission model end to end.

| Layer          | Components                                                                            | Purpose                                                             |
| -------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Skills         | `esra-orchestrator`, `esra-decisions`, `esra-experiments`, `esra-reflection`, `esra-crisis` | On-demand reasoning workflows, auto-discovered by Claude Code        |
| Runtime        | `scripts/esra_runtime.py`                                                               | Triggers, evidence logs, baselines, experiments, audits, oversight artifacts |
| Lifecycle hook | `hooks/hooks.json`, `scripts/esra_hook.py`                                              | Privacy-preserving session/task counters, no stdout, never blocks    |
| Manifest       | `.claude-plugin/plugin.json`                                                            | Standard Claude Code plugin metadata and component paths             |
| Conformance    | `esra-conformance.json`                                                                 | ESRA protocol version and evidence-backed capability maturity         |
| Portable export | `scripts/esra_export.py`                                                                | Privacy-filtered ESRA 1.2 `cycle-event` JSONL                         |

See [`docs/HERMES_PARITY.md`](docs/HERMES_PARITY.md) for the full component mapping and
the specific adaptations this port makes for Claude Code's plugin model, and
[`docs/RUNTIME.md`](docs/RUNTIME.md) for the complete command reference.

## Install

Download the release ZIP and load it directly in Claude Code 2.1.128 or newer:

```bash
claude --plugin-url https://github.com/rrpauls/claude-esra/releases/download/v0.3.0/claude-esra-v0.3.0.zip
```

See [`INSTALL.md`](INSTALL.md) for local ZIP and development-checkout options.

### Local development

Local development / testing, without a marketplace:

```bash
git clone https://github.com/rrpauls/claude-esra.git
claude --plugin-dir ./claude-esra
```

For persistent managed distribution, validate and publish it through a Claude Code
plugin marketplace. See Claude Code's current [plugin docs](https://code.claude.com/docs/en/plugins)
because distribution is owned by Claude Code and can change:

```bash
claude plugin validate --strict ./claude-esra
claude plugin install claude-esra@your-marketplace
```

**Review the hook before enabling this in a shared or project scope.** Claude Code
requires reviewing/trusting non-managed plugin hooks; run `/hooks` inside a session to
inspect what `hooks/hooks.json` registers, or read `scripts/esra_hook.py` — it is
80 lines and does nothing beyond writing one privacy-preserving JSON line per lifecycle
event.

## Operational guarantees

- Skills activate selectively; routine one-step tasks do not trigger a full ESRA cycle.
- A trigger recommendation never executes a cycle or modifies anything by itself.
- Experiments run only commands you explicitly supply, execute without a shell, and
  never auto-promote a result — `experiment decide` records a human decision, and even
  that decision cannot promote a canary-only experiment.
- The lifecycle hook emits no stdout, cannot block or steer a response, always exits 0,
  and stores a hashed session id and a directory basename — never prompts, transcripts,
  or tool input/output.
- `oversight` writes a local Markdown proposal with a suggested verification plan and
  branch name; it never creates a git branch, commit, issue, or pull request.
- All state lives locally under Claude Code's per-plugin data directory (or `--data-dir`
  / `$ESRA_DATA_DIR` if you override it) and never leaves the machine on its own.

## Development

Python 3.10+ (no third-party dependency required for `scripts/`; `pytest` is an optional
convenience for `tests/`).

```bash
python3 -m py_compile scripts/*.py
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

## Repository relationship

| Repository                                                     | Role                                                  |
| ---------------------------------------------------------------- | ------------------------------------------------------ |
| [rrpauls/esra](https://github.com/rrpauls/esra)                  | Architecture specification                              |
| [rrpauls/hermes-esra](https://github.com/rrpauls/hermes-esra)    | Hermes-specific implementation and provenance source     |
| [rrpauls/chatgpt-esra](https://github.com/rrpauls/chatgpt-esra)  | OpenAI/Codex implementation, same consolidation approach |
| **claude-esra** (this repo)                                     | Claude Code plugin implementation                        |

## License

Apache-2.0 — see [LICENSE](LICENSE). Attribution and platform trademark notices
are recorded in [NOTICE](NOTICE); adapted material retains provenance notices in
`docs/HERMES_PARITY.md` and in this README.

"Claude" and "Claude Code" are trademarks of Anthropic, PBC. This is an independent,
unofficial project and is not endorsed by or affiliated with Anthropic.
