#!/usr/bin/env python3
"""One local stdio MCP request for the opt-in Pi model canary; never edits host settings."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from compass_c.cli import parse_json

ROOT = Path(__file__).resolve().parents[1]


async def request(db: Path, tool: str | None, arguments: dict):
    config = json.loads(
        subprocess.check_output(
            [sys.executable, str(ROOT / "scripts/configure_mcp.py"), "--db", str(db)],
            text=True,
        )
    )["mcpServers"]["compass"]
    async with stdio_client(StdioServerParameters(**config)) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=30) as session:
            initialized = await session.initialize()
            tools = (await session.list_tools()).tools
            if tool is None:
                return {
                    "instructions": initialized.instructions,
                    "server": initialized.server_info.model_dump(by_alias=True),
                    "tools": [t.model_dump(by_alias=True, exclude_none=True) for t in tools],
                }
            if tool not in {t.name for t in tools}:
                raise ValueError("Tool is not advertised by the live server")
            result = await session.call_tool(tool, arguments)
            return {
                "isError": result.is_error,
                "content": [
                    part.model_dump(by_alias=True, exclude_none=True) for part in result.content
                ],
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--tool")
    parser.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    arguments = parse_json(args.arguments)
    if not isinstance(arguments, dict):
        parser.error("Arguments must be a JSON object")
    print(json.dumps(asyncio.run(request(args.db, args.tool, arguments))))


if __name__ == "__main__":
    main()
