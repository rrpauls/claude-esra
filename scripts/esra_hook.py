#!/usr/bin/env python3
"""ESRA lifecycle hook adapter for Claude Code.

Reads one hook event as JSON on stdin (the shape Claude Code sends to a
`command` hook: at least `hook_event_name`, plus fields such as
`session_id` and `cwd` depending on the event) and appends a single,
privacy-preserving record to the local event log via esra_runtime.

Deliberate constraints, matching docs/HERMES_PARITY.md:
- Emits nothing on stdout, so it can never inject context or a decision.
- Always exits 0: a malformed event, a missing field, or a logging failure
  must never block a session, a prompt, or a tool call.
- Never starts an ESRA cycle and never calls a skill. It only records that
  a lifecycle event happened.
- Discards prompt text, transcript paths, tool input/output, and full
  session/turn identifiers. Only the event name, a hashed session
  identifier, a truncated timestamp, and the working directory basename
  are kept.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import esra_runtime  # noqa: E402  (import after sys.path tweak, by design)
except Exception:  # pragma: no cover - if the runtime module itself is broken, still exit 0
    esra_runtime = None

RELEVANT_EVENTS = {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def safe_workspace_basename(cwd: str | None) -> str | None:
    if not cwd:
        return None
    try:
        return Path(cwd).name or None
    except Exception:
        return None


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # never fail the session over a malformed hook payload

    event_name = payload.get("hook_event_name")
    if event_name not in RELEVANT_EVENTS:
        return 0

    session_id = payload.get("session_id")
    record = {
        "event": "lifecycle",
        "hook_event": event_name,
        "session_hash": hash_identifier(str(session_id)) if session_id else None,
        "workspace": safe_workspace_basename(payload.get("cwd")),
    }

    if esra_runtime is not None:
        try:
            data_dir = esra_runtime.ensure_dir(esra_runtime.resolve_data_dir(None))
            esra_runtime.append_event(data_dir, record)
        except Exception:
            pass  # logging is best-effort; never block the session over it

    return 0


if __name__ == "__main__":
    sys.exit(main())
