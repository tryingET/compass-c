from __future__ import annotations

import os
from pathlib import Path

from rocs_cli.errors import RocsCliError
from rocs_cli.managed_surface import strip_inline_hash_comment


def load_env_file(path: Path, *, override: bool = False) -> None:
    """
    Minimal dotenv loader (KEY=VALUE). Used to support local workflows where `.env`
    is sourced without exporting variables.
    """
    if not path.exists():
        raise RocsCliError(kind="config", message=f"env file not found: {path}", details={"path": str(path)})
    for raw in path.read_text("utf-8").splitlines():
        line = strip_inline_hash_comment(raw).strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k:
            continue
        if not override and k in os.environ:
            continue
        os.environ[k] = v
