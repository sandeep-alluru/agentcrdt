"""MCP server for agentcrdt.

Start:  python -m agentcrdt.mcp_server
Or:     agentcrdt-mcp

Add to Claude Desktop (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "agentcrdt": {
                "command": "agentcrdt-mcp"
            }
        }
    }
"""

from __future__ import annotations

import sys
from typing import Any


def _require_mcp() -> Any:
    try:
        import mcp.server.stdio
        import mcp.types as types
        from mcp.server import Server
        return mcp, types, Server
    except ImportError:
        print(
            "MCP server requires: pip install 'agentcrdt[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)


def run_server() -> None:
    """Start the MCP server on stdio."""
    mcp_mod, types, server_cls = _require_mcp()

    server = server_cls("agentcrdt")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        # TODO: define tools matching your CLI commands
        return []

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with mcp_mod.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
