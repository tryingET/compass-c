#!/usr/bin/env python3
"""Build deterministic toolkit, standalone-skill, and plugin archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from compass_c import VERSION

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "compass"
MANIFEST = "MANIFEST_SHA256.txt"


def source_paths() -> list[Path]:
    """Resolve an explicit file allowlist, never an ambient directory sweep.

    Git's index declares checkout sources, including staged additions and current
    edits to tracked files. Extracted toolkits reuse their distribution manifest
    as the source allowlist. Its hashes describe the original archive; edits to
    declared sources are permitted and receive fresh hashes when rebuilt.
    """
    if (ROOT / ".git").exists():
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("GIT_")
        }
        try:
            process = subprocess.run(
                ["git", "-C", str(ROOT), "ls-files", "--cached", "-z"],
                capture_output=True,
                check=True,
                timeout=30,
                env=environment,
            )
            names = process.stdout.decode("utf-8").split("\0")
            names = [name for name in names if name]
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            raise ValueError("Cannot read the Git source index for distribution") from exc
    else:
        manifest = ROOT / MANIFEST
        if not manifest.is_file() or manifest.is_symlink():
            raise ValueError("Archive sources require a Git index or toolkit manifest")
        names = []
        for line in manifest.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"[0-9a-f]{64}  (.+)", line)
            if match is None:
                raise ValueError("Malformed distribution manifest entry")
            names.append(match[1])
    if not names or len(names) != len(set(names)):
        raise ValueError("Source index or manifest must contain unique, nonempty paths")
    paths = []
    for name in names:
        relative = PurePosixPath(name)
        if (
            relative.is_absolute()
            or not relative.parts
            or relative.as_posix() != name
            or any(part in {".", ".."} for part in relative.parts)
            or "\\" in name
            or ":" in name
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
        ):
            raise ValueError("Source index or manifest contains an unsafe path")
        if name != MANIFEST:
            paths.append(ROOT / relative)
    return paths


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    excluded_parts = {
        "__pycache__",
        ".git",
        ".compass",
        ".ontology",
        ".venv",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "htmlcov",
        "node_modules",
    }
    if any((ROOT / parent).is_symlink() for parent in (relative, *relative.parents)):
        return False
    return (
        path.is_file()
        and not any(
            part in excluded_parts or part.endswith(".egg-info") or part.startswith("pytest-of-")
            for part in relative.parts
        )
        and path.suffix.lower()
        not in {
            ".pyc",
            ".zip",
            ".db",
            ".sqlite",
            ".sqlite3",
            ".pem",
            ".key",
            ".p12",
            ".pfx",
        }
        and not re.search(r"\.(?:db|sqlite|sqlite3)-(?:wal|shm|journal)$", path.name)
        and not path.name.startswith(".env")
        and not path.name.startswith(".coverage")
        and path.name
        not in {
            "publication-receipt.json",
            "installation-receipt.json",
            ".install-receipt.json",
            ".DS_Store",
        }
    )


def source_files(prefix: str = "") -> dict[str, bytes]:
    result = {}
    for path in source_paths():
        name = path.relative_to(ROOT).as_posix()
        if (
            name.startswith(prefix)
            and included(path)
            and not name.startswith("integrations/plugin/")
        ):
            result[name[len(prefix) :]] = path.read_bytes()
    return result


def archive(path: Path, top: str, files: dict[str, bytes]) -> None:
    payload = dict(files)
    payload[MANIFEST] = (
        "\n".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}" for name, data in sorted(payload.items())
        )
        + "\n"
    ).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(f"{top}/{name}", date_time=(2026, 9, 5, 0, 0, 0))
            info.create_system = 3  # Explicit Unix mode semantics on every build host.
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith((".py", ".sh")) else 0o100644) << 16
            output.writestr(info, data)


def skill_files() -> dict[str, bytes]:
    return source_files("skills/compass/")


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
    license_path = ROOT / "LICENSE"
    if license_path not in source_paths() or not included(license_path):
        raise ValueError("Distribution requires a declared, regular LICENSE file")
    result["LICENSE"] = license_path.read_bytes()
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

    skill = skill_files()
    toolkit = source_files()
    products = [
        (f"COMPASS-C_toolkit_v{VERSION}.zip", "compass-c", toolkit),
        (f"COMPASS_skill_v{VERSION}.zip", "compass", skill),
        (f"COMPASS_plugin_v{VERSION}.zip", "compass", plugin_files()),
    ]
    arguments.output.mkdir(parents=True, exist_ok=True)
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
