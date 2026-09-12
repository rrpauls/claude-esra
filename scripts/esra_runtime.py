#!/usr/bin/env python3
"""ESRA runtime for Claude Code.

Dependency-free operational layer behind the claude-esra skills. It never
executes an improvement cycle by itself, never auto-promotes an experiment,
and never mutates git or GitHub state. Every command either records local
evidence or produces a recommendation/proposal a human or the model still
has to act on explicitly.

State resolution order: --data-dir, then $ESRA_DATA_DIR, then
$CLAUDE_PLUGIN_DATA (set by Claude Code for an installed plugin), then
~/.claude/esra. State directories are created 0700 and state files 0600
where the platform supports POSIX permissions; symlinked state paths are
refused.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024
MAX_BASELINE_HISTORY = 99
MAX_OUTPUT_CHARS = 1000
DAILY_TRIGGER_LIMIT = 3


# ---------------------------------------------------------------------------
# Paths, state directory, and safe I/O
# ---------------------------------------------------------------------------

def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def resolve_data_dir(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser()
    env = os.environ.get("ESRA_DATA_DIR")
    if env:
        return Path(env).expanduser()
    plugin_data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if plugin_data:
        return Path(plugin_data).expanduser()
    return Path.home() / ".claude" / "esra"


def ensure_dir(path: Path) -> Path:
    if path.exists() and path.is_symlink():
        die(f"refusing symlinked directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def safe_open(path: Path, mode: str = "w"):
    if path.exists() and path.is_symlink():
        die(f"refusing symlinked file: {path}")
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_APPEND if mode == "a" else os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    return os.fdopen(fd, mode)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------

def rotate_if_needed(path: Path) -> None:
    max_bytes = int(os.environ.get("ESRA_MAX_LOG_BYTES", DEFAULT_MAX_LOG_BYTES))
    if path.exists() and path.stat().st_size >= max_bytes:
        backup = path.with_name(path.name + ".1")
        if backup.exists():
            backup.unlink()
        path.rename(backup)


def append_event(data_dir: Path, event: dict) -> None:
    path = data_dir / "events.jsonl"
    rotate_if_needed(path)
    record = {"ts": now_iso(), **event}
    with safe_open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def load_events(data_dir: Path) -> list[dict]:
    events: list[dict] = []
    for name in ("events.jsonl.1", "events.jsonl"):
        path = data_dir / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def load_state(data_dir: Path) -> dict:
    path = data_dir / "state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(data_dir: Path, state: dict) -> None:
    with safe_open(data_dir / "state.json", "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# trigger: score whether a full ESRA cycle is worth recommending
# ---------------------------------------------------------------------------

def compute_trigger_score(complexity: float, major_change: bool, new_skill: bool, confidence: float) -> float:
    score = min(max(complexity, 0.0), 10.0) / 10.0 * 0.4
    score += 0.3 if major_change else 0.0
    score += 0.2 if new_skill else 0.0
    score += max(0.0, 0.7 - confidence) * (0.3 / 0.7) if confidence is not None else 0.0
    return round(min(score, 1.0), 2)


def cmd_trigger(args: argparse.Namespace, data_dir: Path) -> None:
    state = load_state(data_dir)
    session = args.session or "default"
    today = datetime.now(timezone.utc).date().isoformat()
    day_count = state.get("trigger_day", {}).get(today, 0)
    already_this_session = session in state.get("trigger_sessions", {})

    score = compute_trigger_score(args.complexity, args.major_change, args.new_skill, args.confidence)
    scored_recommend = score >= 0.5 or args.explicit

    blocked_reason = None
    if not args.force:
        if already_this_session:
            blocked_reason = "a recommendation was already made for this session"
        elif day_count >= DAILY_TRIGGER_LIMIT:
            blocked_reason = "daily recommendation limit reached"

    recommend = scored_recommend and blocked_reason is None

    result = {
        "recommend_cycle": recommend,
        "score": score,
        "reason": blocked_reason or ("explicit request" if args.explicit else "scored from inputs"),
        "inputs": {
            "complexity": args.complexity,
            "major_change": args.major_change,
            "new_skill": args.new_skill,
            "confidence": args.confidence,
        },
        "note": "This is a recommendation only. It never starts a cycle by itself.",
    }

    if recommend or args.force:
        sessions = state.setdefault("trigger_sessions", {})
        sessions[session] = now_iso()
        day = state.setdefault("trigger_day", {})
        day[today] = day_count + 1
        save_state(data_dir, state)

    append_event(data_dir, {"event": "trigger", "session": session, **result})
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# record: log a completed cycle as evidence
# ---------------------------------------------------------------------------

def cmd_record(args: argparse.Namespace, data_dir: Path) -> None:
    event = {
        "event": "cycle_record",
        "id": str(uuid.uuid4()),
        "task": args.task,
        "outcome": args.outcome,
        "evidence": args.evidence,
        "change": args.change,
        "verification": args.verification,
    }
    append_event(data_dir, event)
    print(json.dumps(event, indent=2))


# ---------------------------------------------------------------------------
# baseline: named numeric KPI snapshots
# ---------------------------------------------------------------------------

def parse_metric(item: str) -> tuple[str, object]:
    if "=" not in item:
        die(f"invalid --metric {item!r}, expected key=value")
    key, raw_value = item.split("=", 1)
    try:
        value: object = float(raw_value) if "." in raw_value else int(raw_value)
    except ValueError:
        value = raw_value
    return key.strip(), value


def cmd_baseline(args: argparse.Namespace, data_dir: Path) -> None:
    baselines_dir = ensure_dir(data_dir / "baselines")
    metrics = dict(parse_metric(item) for item in (args.metric or []))
    record = {"name": args.name, "ts": now_iso(), "metrics": metrics}

    history_path = baselines_dir / f"{args.name}.history.jsonl"
    history: list[dict] = []
    if history_path.exists():
        with open(history_path, encoding="utf-8") as f:
            history = [json.loads(line) for line in f if line.strip()]
    history.append(record)
    history = history[-MAX_BASELINE_HISTORY:]
    with safe_open(history_path, "w") as f:
        for entry in history:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    with safe_open(baselines_dir / f"{args.name}.json", "w") as f:
        json.dump(record, f, indent=2, sort_keys=True)

    append_event(data_dir, {"event": "baseline", "name": args.name, "metrics": metrics})
    print(json.dumps(record, indent=2))


# ---------------------------------------------------------------------------
# experiment: bounded command experiments (canary / staged / ab / stress)
# ---------------------------------------------------------------------------

def experiment_path(data_dir: Path, name: str) -> Path:
    return data_dir / "experiments" / f"{name}.json"


def load_experiment(data_dir: Path, name: str) -> dict:
    path = experiment_path(data_dir, name)
    if not path.exists():
        die(f"unknown experiment {name!r}; create it first with 'experiment create'")
    return json.loads(path.read_text(encoding="utf-8"))


def save_experiment(data_dir: Path, name: str, record: dict) -> None:
    with safe_open(experiment_path(data_dir, name), "w") as f:
        json.dump(record, f, indent=2, sort_keys=True)


def run_command_capture(command: str, timeout: float) -> dict:
    argv = shlex.split(command)
    if not argv:
        return {"argv": argv, "returncode": None, "stdout": "", "stderr": "empty command", "timed_out": False}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "argv": argv,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-MAX_OUTPUT_CHARS:],
            "stderr": proc.stderr[-MAX_OUTPUT_CHARS:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "argv": argv,
            "returncode": None,
            "stdout": stdout[-MAX_OUTPUT_CHARS:],
            "stderr": stderr[-MAX_OUTPUT_CHARS:],
            "timed_out": True,
        }
    except FileNotFoundError as exc:
        return {"argv": argv, "returncode": None, "stdout": "", "stderr": str(exc), "timed_out": False}


def cmd_experiment_create(args: argparse.Namespace, data_dir: Path) -> None:
    ensure_dir(data_dir / "experiments")
    path = experiment_path(data_dir, args.name)
    if path.exists():
        die(f"experiment {args.name!r} already exists")
    if args.alignment_score < args.minimum_alignment:
        die("blocked: alignment-score is below minimum-alignment; the experiment is not value-aligned enough to create")
    record = {
        "name": args.name,
        "hypothesis": args.hypothesis,
        "baseline_command": args.baseline_command,
        "candidate_command": args.candidate_command,
        "guardrail": args.guardrail,
        "alignment_score": args.alignment_score,
        "minimum_alignment": args.minimum_alignment,
        "created": now_iso(),
        "runs": [],
        "decision": None,
    }
    save_experiment(data_dir, args.name, record)
    append_event(data_dir, {"event": "experiment_create", "name": args.name})
    print(json.dumps(record, indent=2))


def cmd_experiment_run(args: argparse.Namespace, data_dir: Path) -> None:
    record = load_experiment(data_dir, args.name)
    if record["alignment_score"] < record["minimum_alignment"]:
        die("blocked: experiment alignment score is below its minimum-alignment threshold")

    run_entry: dict = {
        "id": str(uuid.uuid4()),
        "ts": now_iso(),
        "mode": args.mode,
        "timeout": args.timeout,
        "steps": [],
    }

    if args.mode == "canary":
        run_entry["steps"].append({"role": "candidate", **run_command_capture(record["candidate_command"], args.timeout)})
    elif args.mode == "staged":
        baseline_step = run_command_capture(record["baseline_command"], args.timeout)
        run_entry["steps"].append({"role": "baseline", **baseline_step})
        if baseline_step["returncode"] == 0:
            run_entry["steps"].append({"role": "candidate", **run_command_capture(record["candidate_command"], args.timeout)})
        else:
            run_entry["stopped_early"] = "baseline failed"
    elif args.mode == "ab":
        run_entry["steps"].append({"role": "baseline", **run_command_capture(record["baseline_command"], args.timeout)})
        run_entry["steps"].append({"role": "candidate", **run_command_capture(record["candidate_command"], args.timeout)})
    elif args.mode == "stress":
        for i in range(max(1, args.repeat)):
            step = run_command_capture(record["candidate_command"], args.timeout)
            step["iteration"] = i
            run_entry["steps"].append({"role": "candidate", **step})
            if step["returncode"] != 0 and args.stop_on_failure:
                run_entry["stopped_early"] = f"candidate failed on iteration {i}"
                break
    else:  # pragma: no cover - argparse restricts choices
        die(f"unknown mode {args.mode!r}")

    record.setdefault("runs", []).append(run_entry)
    save_experiment(data_dir, args.name, record)
    append_event(data_dir, {"event": "experiment_run", "name": args.name, "mode": args.mode, "run_id": run_entry["id"]})
    print(json.dumps(run_entry, indent=2))


def cmd_experiment_report(args: argparse.Namespace, data_dir: Path) -> None:
    record = load_experiment(data_dir, args.name)
    lines = [
        f"# Experiment report: {record['name']}",
        "",
        f"- Hypothesis: {record['hypothesis']}",
        f"- Guardrail: {record['guardrail']}",
        f"- Alignment score: {record['alignment_score']} (minimum {record['minimum_alignment']})",
        f"- Runs recorded: {len(record.get('runs', []))}",
        f"- Decision: {record.get('decision') or 'none yet'}",
        "",
        "## Runs",
        "",
    ]
    for run in record.get("runs", []):
        lines.append(f"### {run['mode']} — {run['ts']} ({run['id']})")
        for step in run["steps"]:
            lines.append(f"- {step['role']}: exit={step['returncode']} timed_out={step.get('timed_out')}")
        if run.get("stopped_early"):
            lines.append(f"  stopped early: {run['stopped_early']}")
        lines.append("")
    lines.append(
        "A completed run is evidence, not a promotion. Record a human decision with `experiment decide`."
    )
    report_dir = ensure_dir(data_dir / "experiments" / "reports")
    with safe_open(report_dir / f"{args.name}.md", "w") as f:
        f.write("\n".join(lines))
    append_event(data_dir, {"event": "experiment_report", "name": args.name})
    print("\n".join(lines))


def cmd_experiment_decide(args: argparse.Namespace, data_dir: Path) -> None:
    record = load_experiment(data_dir, args.name)
    run_modes = {r["mode"] for r in record.get("runs", [])}
    if args.decision == "promote" and not record.get("runs"):
        die("cannot promote an experiment with no recorded runs")
    if args.decision == "promote" and run_modes <= {"canary"}:
        die(
            "blocked: canary-only evidence cannot justify promotion; it can only reject a candidate "
            "or return more-evidence. Run 'staged', 'ab', or 'stress' before promoting."
        )
    decision = {"choice": args.decision, "notes": args.notes, "ts": now_iso()}
    record["decision"] = decision
    save_experiment(data_dir, args.name, record)
    append_event(data_dir, {"event": "experiment_decide", "name": args.name, "decision": args.decision})
    print(json.dumps(decision, indent=2))


# ---------------------------------------------------------------------------
# validate skills
# ---------------------------------------------------------------------------

def find_default_skills_dir() -> Path:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return Path(plugin_root) / "skills"
    return Path(__file__).resolve().parent.parent / "skills"


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    raw = text[3:end].strip("\n")
    body = text[end + 4:]
    data: dict = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, body


def validate_skill_file(path: Path) -> list[str]:
    problems: list[str] = []
    if path.is_symlink():
        problems.append(f"{path}: refusing a symlinked SKILL.md")
        return problems
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    if frontmatter is None:
        problems.append(f"{path}: missing YAML frontmatter")
        return problems
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not name:
        problems.append(f"{path}: frontmatter missing 'name'")
    elif name != path.parent.name:
        problems.append(f"{path}: frontmatter name '{name}' does not match directory '{path.parent.name}'")
    if not description:
        problems.append(f"{path}: frontmatter missing 'description'")
    elif len(description) < 20:
        problems.append(f"{path}: description is only {len(description)} chars; likely too short to trigger reliably")
    line_count = len(body.splitlines())
    if line_count > 500:
        problems.append(f"{path}: body is {line_count} lines, over the ~500-line guideline; split into references/")
    return problems


def cmd_validate_skills(args: argparse.Namespace, data_dir: Path) -> None:
    skills_dir = Path(args.skills_dir) if args.skills_dir else find_default_skills_dir()
    problems: list[str] = []
    checked = 0
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            checked += 1
            problems.extend(validate_skill_file(skill_md))
    else:
        problems.append(f"skills directory not found: {skills_dir}")
    result = {"skills_dir": str(skills_dir), "checked": checked, "problems": problems, "ok": not problems}
    append_event(data_dir, {"event": "validate_skills", "checked": checked, "problems": len(problems)})
    print(json.dumps(result, indent=2))
    if problems:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# dashboard / audit / oversight
# ---------------------------------------------------------------------------

def cmd_dashboard(args: argparse.Namespace, data_dir: Path) -> None:
    events = load_events(data_dir)
    by_event: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    for e in events:
        kind = e.get("event", "unknown")
        by_event[kind] = by_event.get(kind, 0) + 1
        if kind == "cycle_record":
            outcome = e.get("outcome", "unknown")
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
    summary = {
        "data_dir": str(data_dir),
        "total_events": len(events),
        "events_by_type": by_event,
        "cycle_outcomes": outcomes,
        "recent": events[-10:],
    }
    if args.json:
        print(json.dumps(summary, indent=2))
        return
    print(f"ESRA dashboard — {data_dir}")
    print(f"total events: {len(events)}")
    for kind, count in sorted(by_event.items()):
        print(f"  {kind}: {count}")
    if outcomes:
        print("cycle outcomes:")
        for outcome, count in sorted(outcomes.items()):
            print(f"  {outcome}: {count}")
    print("recent:")
    for e in summary["recent"]:
        print(f"  {e.get('ts')}  {e.get('event')}")


def cmd_audit(args: argparse.Namespace, data_dir: Path) -> None:
    events = load_events(data_dir)
    cycles = [e for e in events if e.get("event") == "cycle_record"]
    non_success = [e for e in cycles if e.get("outcome") not in (None, "success")]
    triggers = [e for e in events if e.get("event") == "trigger"]
    recommended = sum(1 for t in triggers if t.get("recommend_cycle"))
    report = {
        "window_events": len(events),
        "cycles_recorded": len(cycles),
        "non_success_outcomes": len(non_success),
        "triggers_seen": len(triggers),
        "triggers_recommended": recommended,
        "recent_non_success": non_success[-args.limit:],
        "note": (
            "Pattern summary over local evidence only, not a claim about hidden model state. "
            "Structural changes to skills or the runtime need a human-reviewed proposal (see 'oversight')."
        ),
    }
    append_event(data_dir, {"event": "audit", "cycles": len(cycles), "non_success": len(non_success)})
    print(json.dumps(report, indent=2))


def cmd_oversight(args: argparse.Namespace, data_dir: Path) -> None:
    oversight_dir = ensure_dir(data_dir / "oversight")
    path = oversight_dir / f"{args.id}.md"
    if path.exists():
        die(f"oversight proposal {args.id!r} already exists")
    lines = [
        f"# Oversight proposal: {args.title}",
        "",
        f"- id: {args.id}",
        f"- created: {now_iso()}",
        "",
        "## Summary",
        "",
        args.summary,
        "",
        "## Evidence",
        "",
    ]
    lines.extend(f"- {item}" for item in args.evidence)
    lines += [
        "",
        "## Suggested verification",
        "",
        args.verification,
        "",
        "## Suggested branch name",
        "",
        f"`evolve/{args.id}`",
        "",
        "_This file is a local, human-reviewed proposal. It does not create a branch, issue, "
        "commit, or pull request; that stays an explicit, authorized action._",
    ]
    content = "\n".join(lines)
    with safe_open(path, "w") as f:
        f.write(content)
    append_event(data_dir, {"event": "oversight", "id": args.id})
    print(content)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esra_runtime.py", description="Dependency-free ESRA runtime for Claude Code.")
    parser.add_argument("--data-dir", help="override the state directory for this invocation")
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("trigger", help="score whether a full ESRA cycle is worth recommending")
    t.add_argument("--complexity", type=float, default=0.0)
    t.add_argument("--major-change", action="store_true")
    t.add_argument("--new-skill", action="store_true")
    t.add_argument("--confidence", type=float, default=1.0)
    t.add_argument("--explicit", action="store_true", help="model a direct user request")
    t.add_argument("--force", action="store_true", help="bypass only the rate limit, not the score")
    t.add_argument("--session", default=None)

    r = sub.add_parser("record", help="record a completed cycle as local evidence")
    r.add_argument("--task", required=True)
    r.add_argument("--outcome", required=True, choices=["success", "partial", "failure", "abandoned"])
    r.add_argument("--evidence", required=True)
    r.add_argument("--change", required=True)
    r.add_argument("--verification", required=True)

    b = sub.add_parser("baseline", help="store a named baseline metrics snapshot")
    b.add_argument("--name", required=True)
    b.add_argument("--metric", action="append", help="key=value, repeatable")

    e = sub.add_parser("experiment", help="bounded command experiments")
    esub = e.add_subparsers(dest="experiment_command", required=True)

    ec = esub.add_parser("create")
    ec.add_argument("name")
    ec.add_argument("--hypothesis", required=True)
    ec.add_argument("--baseline-command", required=True)
    ec.add_argument("--candidate-command", required=True)
    ec.add_argument("--guardrail", required=True)
    ec.add_argument("--alignment-score", type=float, required=True)
    ec.add_argument("--minimum-alignment", type=float, default=0.6)

    er = esub.add_parser("run")
    er.add_argument("name")
    er.add_argument("--mode", choices=["canary", "staged", "ab", "stress"], default="canary")
    er.add_argument("--timeout", type=float, default=30)
    er.add_argument("--repeat", type=int, default=3, help="stress mode iteration count")
    er.add_argument("--stop-on-failure", dest="stop_on_failure", action="store_true", default=True)
    er.add_argument("--no-stop-on-failure", dest="stop_on_failure", action="store_false")

    erep = esub.add_parser("report")
    erep.add_argument("name")

    ed = esub.add_parser("decide")
    ed.add_argument("name")
    ed.add_argument("--decision", required=True, choices=["promote", "rollback", "more-evidence"])
    ed.add_argument("--notes", default="")

    v = sub.add_parser("validate", help="validate skills")
    vsub = v.add_subparsers(dest="validate_command", required=True)
    vs = vsub.add_parser("skills")
    vs.add_argument("--skills-dir", default=None)

    d = sub.add_parser("dashboard", help="summarize recorded events")
    d.add_argument("--json", action="store_true")

    a = sub.add_parser("audit", help="pattern-level review of recorded evidence")
    a.add_argument("--limit", type=int, default=10)

    o = sub.add_parser("oversight", help="write a local human-reviewed change proposal")
    o.add_argument("--id", required=True)
    o.add_argument("--title", required=True)
    o.add_argument("--summary", required=True)
    o.add_argument("--evidence", action="append", required=True)
    o.add_argument("--verification", required=True)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    data_dir = ensure_dir(resolve_data_dir(args.data_dir))

    if args.command == "trigger":
        cmd_trigger(args, data_dir)
    elif args.command == "record":
        cmd_record(args, data_dir)
    elif args.command == "baseline":
        cmd_baseline(args, data_dir)
    elif args.command == "experiment":
        {
            "create": cmd_experiment_create,
            "run": cmd_experiment_run,
            "report": cmd_experiment_report,
            "decide": cmd_experiment_decide,
        }[args.experiment_command](args, data_dir)
    elif args.command == "validate":
        if args.validate_command == "skills":
            cmd_validate_skills(args, data_dir)
    elif args.command == "dashboard":
        cmd_dashboard(args, data_dir)
    elif args.command == "audit":
        cmd_audit(args, data_dir)
    elif args.command == "oversight":
        cmd_oversight(args, data_dir)


if __name__ == "__main__":
    main()
