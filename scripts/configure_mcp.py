#!/usr/bin/env python3
"""Print a local MCP configuration; do not modify host settings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    arguments = parser.parse_args()
    interpreter = arguments.python.expanduser().resolve()
    if not interpreter.is_file():
        parser.error("Python interpreter does not exist")
    print(
        json.dumps(
            {
                "mcpServers": {
                    "compass": {
                        "command": str(interpreter),
                        "args": [str(ROOT / "integrations" / "mcp_server.py")],
                        "env": {"COMPASS_DB": str(arguments.db.expanduser().absolute())},
                    }
                }
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
