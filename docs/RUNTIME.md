# Claude Code runtime

`scripts/esra_runtime.py` is the dependency-free operational layer behind the five
skills in this plugin. It is stdlib-only Python 3 (3.10+ for the type-hint syntax used;
tested on 3.11) and never shells out to `git`, `gh`, or any package manager.

## State and privacy

State resolution order:

1. `--data-dir`
2. `$ESRA_DATA_DIR`
3. `$CLAUDE_PLUGIN_DATA` — the per-plugin persistent directory Claude Code provides
   automatically to an installed plugin (`~/.claude/plugins/data/<plugin-id>/`)
4. `~/.claude/esra` — used when running the script directly outside of a plugin install

State directories are created `0700` and generated files `0600` where the operating
system supports POSIX permissions. The runtime refuses to write through a symlinked
state file or directory. The event log rotates at 5 MiB by default (one prior segment
kept); set `ESRA_MAX_LOG_BYTES` to change the threshold. Named baselines keep up to 99
earlier snapshots.

Every path field (`${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`) used in
`hooks/hooks.json` and in the skill bodies is substituted by Claude Code itself before
the command runs — nothing in this plugin resolves those variables manually.

## Commands

### Trigger recommendation

```bash
python3 scripts/esra_runtime.py trigger \
  --complexity 8 --major-change --new-skill --confidence 0.6 --session my-session
```

Returns a JSON recommendation only. Rate limits default to one recommendation per
supplied `--session` value and three per UTC day. `--explicit` models a direct user
request and overrides the score; `--force` bypasses only the rate limit, never the
score itself.

### Record a completed cycle

```bash
python3 scripts/esra_runtime.py record \
  --task plugin-port \
  --outcome success \
  --evidence "validator passed" \
  --change "used a Claude Code plugin hook instead of a Hermes post-task hook" \
  --verification "unit tests and an isolated hook subprocess test both passed"
```

Store concise evidence pointers only — never secrets, full transcripts, or hidden
deliberation.

### Portable ESRA 1.2 export

```bash
python3 scripts/esra_export.py \
  --data-dir ~/.claude/esra --output /tmp/esra-events.jsonl
```

The read-only exporter maps legacy runtime records to one
`cycle-event@1.0.0` object per line. It exports an allowlisted payload and
omits prompts, transcripts, raw session identifiers, command output, and
hidden reasoning. Existing runtime files are not modified.

### Baseline metrics

```bash
python3 scripts/esra_runtime.py baseline \
  --name skill-footprint \
  --metric skills=5 \
  --metric approx_lines=1450
```

### Bounded command experiment

```bash
python3 scripts/esra_runtime.py experiment create validator-speed \
  --hypothesis "the candidate retains correctness with lower latency" \
  --baseline-command "python3 scripts/validate_skills.py" \
  --candidate-command "python3 scripts/esra_runtime.py validate skills" \
  --guardrail "both commands must exit zero" \
  --alignment-score 1.0 --minimum-alignment 0.6

python3 scripts/esra_runtime.py experiment run validator-speed --mode ab --timeout 30
python3 scripts/esra_runtime.py experiment report validator-speed
python3 scripts/esra_runtime.py experiment decide validator-speed \
  --decision more-evidence --notes "sample is too small for promotion"
```

Commands are parsed into argument arrays with `shlex.split` and run without a shell —
no pipes, redirection, or shell expansion. Modes are `canary`, `staged`, `ab`, and
`stress`. Creating or running an experiment below its own `--minimum-alignment`
threshold is blocked. Canary and staged stop after a candidate failure. Captured output
is truncated to 1,000 characters per stream. Reports are written under the runtime's
private data directory as both JSON (inside the experiment record) and Markdown
(`experiments/reports/<name>.md`).

A successful canary run always leaves the experiment eligible only for `more-evidence`
or `rollback` — `experiment decide --decision promote` is refused when the only
recorded runs are canaries, so "it didn't crash once" can never by itself read as
"promoted." Do not use experiment commands that might print secrets: the runtime stores
the final output tail (truncated) for debugging.

### Validation, dashboard, audit, and oversight

```bash
python3 scripts/esra_runtime.py validate skills
python3 scripts/esra_runtime.py dashboard --json
python3 scripts/esra_runtime.py audit --limit 10
python3 scripts/esra_runtime.py oversight \
  --id refine-trigger --title "Refine the ESRA trigger threshold" \
  --summary "Raise the routine-task boundary" \
  --evidence "two of five recent recommendations were declined as too eager" \
  --verification "re-run the same five scenarios; confirm both now score below 0.5"
```

`oversight` writes a local Markdown proposal with a suggested branch name. It
deliberately does not create a git branch, commit, issue, or pull request — applying an
approved change stays an explicit, normal action you or the user take afterward.

## Claude Code lifecycle hook

`hooks/hooks.json` wires `SessionStart`, `UserPromptSubmit`, `Stop`, and `SessionEnd` to
`scripts/esra_hook.py`. The adapter:

- Reads one JSON event on stdin (the shape Claude Code sends a `command` hook).
- Emits nothing on stdout, so it can never inject context, block a tool call, or steer
  a response.
- Always exits `0`.
- Records only the event name, a SHA-256-truncated session hash, and the working
  directory's basename — never the prompt, transcript path, or tool input/output.
- Never starts an ESRA cycle and never invokes a skill.

Claude Code requires reviewing and trusting non-managed plugin hooks before they run
(see `/hooks` inside a session, and the plugin-scope trust rules for project-installed
plugins); inspect `hooks/hooks.json` and `scripts/esra_hook.py` before enabling this
plugin in a shared or project scope.

To exercise the adapter without Claude Code:

```bash
printf '%s' '{"hook_event_name":"Stop","session_id":"demo","cwd":"/tmp/project"}' \
  | ESRA_DATA_DIR=/tmp/esra-hook-demo python3 scripts/esra_hook.py
cat /tmp/esra-hook-demo/events.jsonl
```

## Development

```bash
pip install --break-system-packages pytest  # optional; unittest also works standalone
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests -v
python3 scripts/validate_skills.py
```

No third-party runtime dependency is required for `scripts/` itself; `pytest` above is
only a convenience for running `tests/` with nicer output than `unittest`.
