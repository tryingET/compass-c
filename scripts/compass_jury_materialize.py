"""Normalize DSPx-emitted sources for this repo; never synthesize program behavior."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import subprocess
import textwrap
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ("program.py", "module.py", "signature.py")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def wrap_literals(source: str) -> str:
    """Split long plain string tokens without changing their values or the AST."""
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.STRING or len(token.string) <= 85:
            continue
        value = ast.literal_eval(token.string)
        if not isinstance(value, str):
            continue
        chunks = textwrap.wrap(
            value,
            width=64,
            replace_whitespace=False,
            drop_whitespace=False,
            break_on_hyphens=False,
        )
        if "".join(chunks) != value:
            raise ValueError("literal wrapping changed text")
        replacement = "(\n" + "\n".join("    " + repr(chunk) for chunk in chunks) + "\n)"
        start = offsets[token.start[0] - 1] + token.start[1]
        end = offsets[token.end[0] - 1] + token.end[1]
        edits.append((start, end, replacement))
    result = source
    for start, end, replacement in reversed(edits):
        result = result[:start] + replacement + result[end:]
    if ast.dump(ast.parse(result)) != ast.dump(ast.parse(source)):
        raise ValueError("literal normalization changed the AST")
    return result


def wrap_docstrings(source: str) -> str:
    """Reflow long generated docstrings; preserve words, not whitespace bytes."""
    lines = source.splitlines(keepends=True)
    for node in sorted(
        ast.walk(ast.parse(source)), key=lambda n: getattr(n, "lineno", 0), reverse=True
    ):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and len(first.value.value) > 90
        ):
            continue
        value = first.value.value
        if '"""' in value or "\\" in value:
            raise ValueError("unsupported generated docstring escaping")
        indent = " " * first.col_offset
        wrapped = textwrap.wrap(
            value, width=90 - len(indent), break_on_hyphens=False, break_long_words=False
        )
        if " ".join(value.split()) != " ".join(" ".join(wrapped).split()):
            raise ValueError("docstring words changed")
        replacement = indent + '"""' + "\n" + "\n".join(indent + part for part in wrapped)
        replacement += "\n" + indent + '"""\n'
        lines[first.lineno - 1 : first.end_lineno] = [replacement]
    return "".join(lines)


def split_metadata(output: Path) -> None:
    """Move pure generated constant declarations, retaining public re-exports."""
    target = output / "program.py"
    source = target.read_text()
    lines = source.splitlines(keepends=True)
    declarations = []
    names = []
    for node in ast.parse(source).body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id.isupper()
        ):
            continue
        ast.literal_eval(node.value)  # Only pure literal data may move.
        names.append(node.targets[0].id)
        declarations.extend(lines[node.lineno - 1 : node.end_lineno])
        for index in range(node.lineno - 1, node.end_lineno):
            lines[index] = ""
    if not names:
        raise ValueError("no generated metadata declarations")
    imports = (
        "from metadata import (\n" + "".join(f"    {name} as {name},\n" for name in names) + ")\n"
    )
    body = "".join(lines).replace(
        "from __future__ import annotations\n", "from __future__ import annotations\n" + imports, 1
    )
    target.write_text(body)
    (output / "metadata.py").write_text("".join(declarations))


def materialize(native: Path, output: Path) -> None:
    sources = {name: (native / name).read_bytes() for name in FILES}
    manifest = json.loads((native / "manifest.json").read_text())
    if not manifest["topology_execution"]["materialized"]:
        raise ValueError("DSPx did not materialize the topology")
    output.mkdir()  # Refuse replacement of an existing reviewed program.
    for name, raw in sources.items():
        (output / name).write_text(wrap_literals(raw.decode("utf-8")))
    paths = [str(output / name) for name in FILES]
    # Only unused imports and import ordering change after the AST-preserving wrap.
    subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--extra",
            "dev",
            "ruff",
            "check",
            "--select",
            "I,F401",
            "--fix",
            *paths,
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["uv", "run", "--frozen", "--extra", "dev", "ruff", "format", *paths],
        cwd=ROOT,
        check=True,
    )
    for path in paths:
        target = Path(path)
        target.write_text(wrap_docstrings(target.read_text()))
    subprocess.run(
        ["uv", "run", "--frozen", "--extra", "dev", "ruff", "format", *paths],
        cwd=ROOT,
        check=True,
    )
    split_metadata(output)
    paths.append(str(output / "metadata.py"))
    subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--extra",
            "dev",
            "ruff",
            "check",
            "--select",
            "I,F401",
            "--fix",
            *paths,
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["uv", "run", "--frozen", "--extra", "dev", "ruff", "format", *paths],
        cwd=ROOT,
        check=True,
    )
    receipt = {
        "schema_version": 1,
        "generator": "DSPx program-gen",
        "generation_provider": "stub",
        "live_model_called": False,
        "native_manifest_sha256": digest((native / "manifest.json").read_bytes()),
        "native_receipt_sha256": digest((native / "manifest.json.meta.json").read_bytes()),
        "intent_yaml_sha256": digest((output.parent / "intent.yaml").read_bytes()),
        "intent": manifest["intent"],
        "topology_execution": manifest["topology_execution"],
        "transformations": [
            "AST-preserving string wrapping",
            "Ruff I,F401 fixes",
            "generated docstring whitespace reflow (words preserved)",
            "pure literal metadata split with public re-exports",
            "Ruff format",
        ],
        "native_source_sha256": {name: digest(raw) for name, raw in sources.items()},
        "source_sha256": {
            name: digest((output / name).read_bytes()) for name in (*FILES, "metadata.py")
        },
        "provenance": "local_generation_and_normalization_not_provider_authentication",
    }
    (output / "generation.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    materialize(args.native, args.output)
