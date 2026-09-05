"""Deterministic synthetic ROCS repository generator."""

from __future__ import annotations
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")


def generate_repo(out: Path, *, count: int = 200) -> Path:
    if count < 0:
        raise ValueError("count must be non-negative")
    out = out.expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f"output must be empty: {out}")
    _write(
        out / "ontology/manifest.yaml",
        'rocs:\n  layer: core\n  id: "bench.core"\n  version: "0.0.0"\n  created: "2026-01-01"\n',
    )
    _write(out / "ontology/src/system4d.yaml", "system4d: {}\n")
    _write(
        out / "ontology/src/reference/relations/is_a.md",
        '---\nont:\n  id: "core.rel.is_a"\n  type: relation\n  labels: ["is_a"]\n  description: "taxonomy"\n  group: taxonomy\n  characteristics:\n    transitive: true\n    symmetric: false\n---\n\n# is_a\n\n## Definition\ntaxonomy\n\n## Domain / Range\n- Domain: subtype concept\n- Range: supertype concept\n',
    )
    for i in range(1, count + 1):
        relation = (
            "  relations: []" if i == 1 else f'  relations:\n    - type: is_a\n      target: "core.Bench{i - 1:04d}"'
        )
        cid = f"core.Bench{i:04d}"
        _write(
            out / f"ontology/src/reference/concepts/{cid}.md",
            f'---\nont:\n  id: "{cid}"\n  type: concept\n  labels: ["Bench{i:04d}"]\n  description: "bench concept {i}"\n{relation}\n  examples: ["example"]\n  anti_examples: ["anti-example"]\n---\n\n# {cid}\n\n## Definition\nbench concept {i}\n',
        )
    return out
