#!/usr/bin/env python3
"""Build the deterministic Claude Code plugin ZIP distributed in Releases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


PLUGIN_FILES = (
    ".claude-plugin/plugin.json",
    "INSTALL.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "esra-conformance.json",
    "scripts/esra_export.py",
    "scripts/esra_hook.py",
    "scripts/esra_runtime.py",
    "scripts/validate_skills.py",
)
PLUGIN_DIRECTORIES = ("docs", "hooks", "skills")


def archive_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def included_plugin_files(repo_root: Path) -> list[Path]:
    files = [repo_root / relative for relative in PLUGIN_FILES]
    for directory in PLUGIN_DIRECTORIES:
        files.extend(
            path
            for path in (repo_root / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing installer input: {missing[0]}")
    return sorted(set(files))


def manifest_version(repo_root: Path) -> str:
    manifest = json.loads(
        (repo_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    return str(manifest["version"])


def build(output: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w") as archive:
        for source in included_plugin_files(repo_root):
            relative = source.relative_to(repo_root).as_posix()
            archive.writestr(archive_info(relative), source.read_bytes())


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    default = f"dist/claude-esra-v{manifest_version(repo_root)}.zip"
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=default)
    args = parser.parse_args()
    build(Path(args.output).resolve())


if __name__ == "__main__":
    main()
