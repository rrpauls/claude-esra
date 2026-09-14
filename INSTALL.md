# Install ESRA for Claude Code

ESRA is one Claude Code plugin containing five on-demand skills. Python 3.10 or newer is required only for the optional local runtime and lifecycle hook.

## Release ZIP

Claude Code 2.1.128 or newer can load a plugin ZIP directly for one session:

```bash
claude --plugin-url https://github.com/rrpauls/claude-esra/releases/download/v0.3.0/claude-esra-v0.3.0.zip
```

You can also download the asset and load it locally:

```bash
claude --plugin-dir /absolute/path/to/claude-esra-v0.3.0.zip
```

Inside Claude Code, invoke a skill as `/claude-esra:esra-decisions` (or choose another of the five `esra-*` skills). Review the lifecycle hook with `/hooks`; disable it there if you only want the skills.

## Development checkout

```bash
git clone https://github.com/rrpauls/claude-esra.git
claude --plugin-dir ./claude-esra
```

The plugin does not require Hermes and does not write to Hermes paths. Local ESRA state stays under Claude Code's per-plugin data directory unless `$ESRA_DATA_DIR` is explicitly set.
