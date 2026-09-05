#!/usr/bin/env python3
"""Validate portable and repo-local skill structure, never model behavior."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "compass"
NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LINK_RE = re.compile(r"\[[^]]+\]\(([^)]+)\)")
SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{16,}"
)


def fail(message: str) -> None:
    raise ValueError(message)


def frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        fail("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail("SKILL.md frontmatter is not closed")
    metadata = yaml.safe_load(text[4:end])
    if not isinstance(metadata, dict):
        fail("SKILL.md frontmatter must be an object")
    return metadata, text[end + 5 :]


def validate_files(skill: Path | None = None) -> None:
    skill = SKILL if skill is None else skill
    if not skill.is_dir() or skill.is_symlink():
        fail(f"skill root must be a real directory: {skill}")
    for path in skill.rglob("*"):
        if path.is_symlink():
            fail(f"symlink is not portable: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(skill)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if len(relative.parts) > 2:
            fail(f"resource nesting exceeds one directory: {relative}")
        if path.suffix in {".db", ".sqlite", ".sqlite3"}:
            fail(f"runtime state in skill package: {relative}")
        raw = path.read_bytes()
        if b"\x00" in raw:
            fail(f"binary resource is not allowed: {relative}")
        decoded = raw.decode("utf-8")
        if SECRET_RE.search(decoded):
            fail(f"credential-shaped content in {relative}")
        if path.suffix == ".py":
            ast.parse(decoded, filename=str(relative))


def validate_skill(skill: Path | None = None) -> None:
    skill = SKILL if skill is None else skill
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    metadata, body = frontmatter(text)
    name = metadata.get("name")
    description = metadata.get("description")
    if name != skill.name or not NAME_RE.fullmatch(str(name)) or len(name) > 64:
        fail("skill name must match the lowercase hyphenated folder")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        fail("description must contain 1..1024 characters")
    if len(body.splitlines()) > 250:
        fail("SKILL.md body exceeds 250 lines")
    for target in LINK_RE.findall(body):
        if "://" in target or target.startswith("#"):
            continue
        relative = Path(target)
        if relative.is_absolute() or ".." in relative.parts:
            fail(f"unsafe resource reference: {target}")
        if not (skill / relative).is_file():
            fail(f"missing resource reference: {target}")


def validate_evals(skill: Path | None = None) -> None:
    skill = SKILL if skill is None else skill
    data = json.loads((skill / "evals" / "cases.json").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail("evaluation corpus must be an object")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        fail("evaluation corpus is empty")
    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            fail("evaluation cases must be objects")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in case_ids:
            fail("evaluation case IDs must be unique nonempty strings")
        case_ids.add(case_id)
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            fail(f"prompt must be a nonempty string: {case_id}")
        rubric = case.get("expected_output")
        if not isinstance(rubric, dict):
            fail(f"rubric must be an object: {case_id}")
        criteria = rubric.get("criteria")
        if type(rubric.get("rubric_version")) is not int or rubric["rubric_version"] != 1:
            fail(f"unsupported rubric version: {case_id}")
        if not isinstance(criteria, list):
            fail(f"invalid rubric for {case_id}")
        if not 2 <= len(criteria) <= 8:
            fail(f"rubric must have 2..8 criteria: {case_id}")
        if not all(isinstance(criterion, dict) for criterion in criteria):
            fail(f"criteria must be objects: {case_id}")
        criterion_ids = [criterion.get("id") for criterion in criteria]
        if not all(isinstance(item, str) and item.strip() for item in criterion_ids):
            fail(f"criterion IDs must be nonempty strings: {case_id}")
        if len(criterion_ids) != len(set(criterion_ids)):
            fail(f"criterion IDs must be unique strings: {case_id}")
        if not all(
            criterion.get("required") is True
            and isinstance(criterion.get("description"), str)
            and criterion["description"].startswith("Pass only when ")
            and criterion["description"][len("Pass only when ") :].strip()
            for criterion in criteria
        ):
            fail(f"criteria must be required, atomic pass contracts: {case_id}")


def main() -> int:
    try:
        for skill in (SKILL, ROOT / ".pi/skills/compass-c-maintainer"):
            validate_files(skill)
            validate_skill(skill)
            validate_evals(skill)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "skill": "compass",
                "skills": ["compass", "compass-c-maintainer"],
                "status": "structurally_valid",
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
