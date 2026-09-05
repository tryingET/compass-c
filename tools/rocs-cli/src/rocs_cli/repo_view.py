from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rocs_cli.errors import RocsCliError
from rocs_cli.layers import LayerSpec, repo_root as _repo_root, resolve_layers
from rocs_cli.model import OntDoc, collect_docs
from rocs_cli.source_contract import (
    SOURCE_CONTRACT_V1,
    SourceContractError,
    source_contract_conformance,
)


@dataclass(frozen=True)
class RepoView:
    repo: Path
    layers: list[LayerSpec]
    meta: dict[str, Any]
    concepts: dict[str, OntDoc]
    relations: dict[str, OntDoc]

    def source_conformance(
        self,
        operation: str,
        *,
        complete_success: bool,
        resource_exhausted: bool = False,
    ) -> dict[str, Any] | None:
        return source_contract_conformance(
            [*self.concepts.values(), *self.relations.values()],
            self.layers,
            operation=operation,
            complete_success=complete_success,
            resource_exhausted=resource_exhausted,
        )


def _system_exit_message(exc: SystemExit) -> str | None:
    code = exc.code
    if isinstance(code, str):
        msg = code.strip()
        return msg or None
    return None


def load_repo_view(
    repo: str | Path,
    *,
    profile: str | None,
    resolve_refs: bool,
    workspace_root: str | None = None,
    workspace_ref_mode: str | None = None,
    only: str | None = None,
    layer: str | None = None,
    load_docs: bool = True,
) -> RepoView:
    repo_path = _repo_root(str(repo))
    layers, meta = resolve_layers(
        repo_path,
        profile=profile,
        resolve_refs=resolve_refs,
        workspace_root=workspace_root,
        workspace_ref_mode=workspace_ref_mode,
        only=only,
        layer=layer,
    )

    concepts: dict[str, OntDoc] = {}
    relations: dict[str, OntDoc] = {}
    if load_docs:
        try:
            concepts, relations = collect_docs(layers)
        except RocsCliError:
            raise
        except SourceContractError as e:
            raise RocsCliError(
                kind=e.kind if e.kind == "resource_exhausted" else "content",
                message=e.message,
                details={
                    "source_contract": SOURCE_CONTRACT_V1,
                    "phase": e.phase,
                    **({"path": e.path} if e.path else {}),
                },
            ) from e
        except ValueError as e:
            raise RocsCliError(kind="content", message=str(e)) from e
        except SystemExit as e:
            message = _system_exit_message(e) or "invalid ontology content"
            raise RocsCliError(kind="content", message=message) from None

    return RepoView(repo=repo_path, layers=layers, meta=meta, concepts=concepts, relations=relations)
