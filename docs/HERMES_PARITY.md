# Hermes ESRA functional parity

This implementation targets behavioral parity with `rrpauls/hermes-esra`'s 15 meta-skills
and 9 tools, following the same consolidation approach `rrpauls/chatgpt-esra` used for
OpenAI/Codex. Parity means preserving useful outcomes and safeguards, not copying
Hermes-specific paths, automatic assumptions, or class names — and not copying
Codex-specific plugin mechanics that don't exist in Claude Code either.

## Skill coverage

| Hermes skill                    | Claude Code equivalent                                    |
| -------------------------------- | ----------------------------------------------------------- |
| `hermes-evolution-orchestrator`  | `esra-orchestrator`                                          |
| `esra-runtime`                   | `esra-orchestrator` plus `docs/RUNTIME.md`                    |
| `ooda-framework`                 | `esra-decisions`                                              |
| `value-clarifier`                | `esra-decisions` and the experiment value-alignment gate      |
| `optimizer-philosopher`          | `esra-decisions`                                              |
| `system-dynamics-thinker`        | `esra-decisions`                                              |
| `self-observer`                  | `esra-reflection`, restricted to observable transcript/tool evidence |
| `self-improver`                  | `esra-reflection` plus `esra-experiments`                     |
| `mental-model-updater`           | `esra-reflection` revised-working-rule method                 |
| `loop-auditor`                   | `esra-reflection` audit mode plus runtime `audit`/`oversight`  |
| `experimenter`                   | `esra-experiments` plus runtime `experiment`                  |
| `antifragility-builder`          | `esra-crisis` resilience method                                |
| `crisis-manager`                 | `esra-crisis`                                                  |
| `hermes-codebase-engineer`       | Claude Code's native repository tools; ESRA applies selectively on top |
| `github-actions-integrator`      | Claude Code's native git/GitHub tools and any GitHub connector the user enables; ESRA's runtime never touches them directly |

Five narrower skills, each with `SKILL.md` under ~350 lines, keep the always-on
metadata cost low (Claude Code loads name+description for every installed skill on
every turn, and the full body only when a skill actually triggers — see
`claude plugin details` for exact token accounting once this is installed).

## Runtime coverage

| Hermes component         | Claude Code implementation                                        | Notes |
| ------------------------- | -------------------------------------------------------------------- | ----- |
| `evolution_hook.py`       | `esra_runtime.py trigger`; plugin lifecycle hook                      | Scoring and rate limits recommend one cycle; never auto-executes it |
| `esra_logger.py`          | private `events.jsonl` under the plugin data directory                | Concise evidence and lifecycle records, rotated at 5 MiB |
| `evolution_dashboard.py`  | `esra_runtime.py dashboard`                                           | Event, outcome, and recency summary |
| `baseline_metrics.py`     | `esra_runtime.py baseline`                                            | Named numeric KPI snapshots, 99-entry history |
| `skill_validator.py`      | `scripts/validate_skills.py`, `esra_runtime.py validate skills`       | Frontmatter, name/directory match, description length, body size |
| `experiment_runner.py`    | `esra_runtime.py experiment`                                          | Canary, staged, A/B, stress; timeout; stop-on-failure; explicit decision |
| `hermes_integration.py`   | Claude Code plugin discovery (`.claude-plugin/plugin.json`, `skills/`) | Native plugin installation replaces manual skill injection into a home directory |
| `human_oversight.py`      | `esra_runtime.py oversight` plus normal, user-authorized git/GitHub actions | Produces a local review artifact and branch-name suggestion; it never mutates git or GitHub itself |
| `esra_paths.py`           | `--data-dir`, `$ESRA_DATA_DIR`, `$CLAUDE_PLUGIN_DATA`, safe-path helpers | No dependency on a Hermes home directory; uses Claude Code's per-plugin persistent data directory by default |

## Deliberate host adaptations for Claude Code

- **No plugin-root `CLAUDE.md`.** Claude Code explicitly does not load a `CLAUDE.md`
  placed at a plugin's root as project context — plugins contribute context through
  skills, agents, and hooks instead. So unlike Hermes's `AGENTS.md`, the triggers and
  "when to use this" guidance for the orchestrator live entirely in
  `skills/esra-orchestrator/SKILL.md`'s frontmatter `description` and body.
- **Automatic post-task evolution becomes a bounded, rate-limited recommendation**, not
  a steering hook. `esra_hook.py` records that a lifecycle event happened (`SessionStart`,
  `UserPromptSubmit`, `Stop`, `SessionEnd`) and nothing else — it emits no stdout, so it
  cannot inject context, block a tool call, or start a cycle by itself.
- **Self-observation is limited to observable task evidence.** The skills make no
  claims about hidden mental state, introspective access, or persistent memory across
  sessions; ESRA here is a functional workflow over observable outcomes, consistent
  with the parent specification's framing of ESRA as "not a model of true (phenomenal)
  consciousness."
- **Plugin agents in Claude Code cannot carry their own hooks, MCP servers, or a
  permission mode** (a documented platform restriction, for security reasons). This
  implementation therefore ships ESRA as five skills plus a shared `hooks/hooks.json`
  at the plugin level, rather than as a dedicated `loop-auditor` subagent — a subagent
  would not be able to log lifecycle events or call MCP tools on its own regardless.
- **Skill injection becomes plugin installation and native discovery.** Duplicate
  same-name skills are not merged; if this plugin's skill names collide with another
  installed plugin's, that is surfaced through Claude Code's normal `/plugin` and
  `claude plugin validate` diagnostics, not through ESRA's own logic.
- **git and GitHub actions remain normal, explicit, user-authorized actions** taken
  with Claude Code's own tools (or a GitHub connector the user has enabled) rather than
  side effects of a runtime helper. `esra_runtime.py oversight` writes a Markdown
  proposal and a suggested branch name; it never runs `git` or calls any GitHub API.
- **Runtime logs do not retain prompt or transcript content.** The hook adapter hashes
  the session identifier, keeps only the working-directory basename, and discards tool
  input/output, transcript paths, and turn identifiers entirely.
- **Commands run without a shell.** Both `experiment create --baseline-command` and
  `--candidate-command` are parsed with `shlex.split` and executed via `subprocess.run`
  with no shell, so they cannot use pipes, redirection, or shell expansion — matching
  Claude Code's own preference for exec-form, unambiguous command execution.

These adaptations retain the operational purpose of each Hermes component while
following Claude Code's plugin, skill-discovery, hook, and permission model.
