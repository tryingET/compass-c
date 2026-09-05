#!/usr/bin/env python3
"""Build deterministic toolkit, standalone-skill, and plugin archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from compass_c import VERSION

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "compass"


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    excluded_parts = {"__pycache__", ".git", ".compass", ".venv", "dist", "build"}
    return (
        path.is_file()
        and not path.is_symlink()
        and not any(part in excluded_parts or part.endswith(".egg-info") for part in relative.parts)
        and path.suffix not in {".pyc", ".zip", ".db", ".sqlite", ".sqlite3"}
        and not path.name.startswith(".env")
        and path.name not in {"publication-receipt.json", "installation-receipt.json"}
    )


def archive(path: Path, top: str, files: dict[str, bytes]) -> None:
    payload = dict(files)
    payload["MANIFEST_SHA256.txt"] = (
        "\n".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}" for name, data in sorted(payload.items())
        )
        + "\n"
    ).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(f"{top}/{name}", date_time=(2026, 9, 5, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith(".py") else 0o100644) << 16
            output.writestr(info, data)


def skill_files() -> dict[str, bytes]:
    return {
        path.relative_to(SKILL).as_posix(): path.read_bytes()
        for path in SKILL.rglob("*")
        if included(path)
    }


def plugin_files() -> dict[str, bytes]:
    result = {f"skills/compass/{name}": data for name, data in skill_files().items()}
    manifest = {
        "name": "compass",
        "version": VERSION,
        "description": "Advisory decision comparisons and bounded computational checks.",
        "skills": "./skills/",
        "repository": "https://github.com/tryingET/compass-c",
        "license": "SEE LICENSE",
    }
    result[".codex-plugin/plugin.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    result["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    result["README.md"] = (
        b"# COMPASS skills-only plugin\n\nGenerated from `skills/compass`. "
        b"It registers no external tools or MCP server. Review LICENSE before host installation.\n"
    )
    return result


def sync_plugin(*, check: bool) -> None:
    destination = ROOT / "integrations" / "plugin"
    expected = plugin_files()
    actual = (
        {
            path.relative_to(destination).as_posix(): path.read_bytes()
            for path in destination.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        if destination.exists()
        else {}
    )
    if check:
        if actual != expected:
            raise ValueError(
                "Generated plugin drifted; run scripts/build_archives.py --sync-plugin"
            )
        return
    unmanaged = set(actual) - set(expected)
    if unmanaged:
        raise ValueError(f"Unmanaged generated-plugin files: {sorted(unmanaged)}")
    for name, data in expected.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--sync-plugin", action="store_true")
    parser.add_argument("--check-plugin", action="store_true")
    arguments = parser.parse_args()
    if arguments.sync_plugin or arguments.check_plugin:
        sync_plugin(check=arguments.check_plugin)
        print(json.dumps({"plugin_consistent": True, "installed": False}))
        return 0

    arguments.output.mkdir(parents=True, exist_ok=True)
    skill = skill_files()
    toolkit = {
        path.relative_to(ROOT).as_posix(): path.read_bytes()
        for path in ROOT.rglob("*")
        if included(path) and "integrations/plugin" not in path.as_posix()
    }
    products = [
        (f"COMPASS-C_toolkit_v{VERSION}.zip", "compass-c", toolkit),
        (f"COMPASS_skill_v{VERSION}.zip", "compass", skill),
        (f"COMPASS_plugin_v{VERSION}.zip", "compass", plugin_files()),
    ]
    for filename, top, files in products:
        target = arguments.output / filename
        archive(target, top, files)
        print(
            json.dumps(
                {
                    "path": str(target.resolve()),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "files": len(files) + 1,
                    "published": False,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
