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

import json
import sys
from typing import Any

try:
    import mcp.server.stdio as _mcp_stdio
    import mcp.types as _mcp_types
    from mcp.server import Server as _Server

    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False


def run_server() -> None:
    """Start the MCP server on stdio."""
    if not _HAS_MCP:
        print(
            "MCP server requires: pip install 'agentcrdt[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from agentcrdt.fact import WorldFact
    from agentcrdt.merger import WorldMerger
    from agentcrdt.store import WorldStore

    server = _Server("agentcrdt")

    @server.list_tools()
    async def list_tools() -> list[_mcp_types.Tool]:
        return [
            _mcp_types.Tool(
                name="set_world_fact",
                description=(
                    "Create or update a world fact in a WorldStore. "
                    "Uses LWW CRDT semantics (higher version wins, then timestamp)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "store_path": {
                            "type": "string",
                            "description": "Path to the SQLite store file (created if absent).",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Fact domain, e.g. 'life', 'alliance', 'possession'.",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity name, e.g. 'king', 'treaty-1'.",
                        },
                        "attribute": {
                            "type": "string",
                            "description": "Attribute name, e.g. 'alive', 'valid', 'owner'.",
                        },
                        "value": {
                            "description": "Fact value — string, number, or boolean.",
                        },
                        "author": {
                            "type": "string",
                            "description": "Agent ID that is asserting this fact.",
                        },
                        "version": {
                            "type": "integer",
                            "description": "CRDT version counter (default 0).",
                            "default": 0,
                        },
                    },
                    "required": ["store_path", "domain", "entity", "attribute", "value", "author"],
                },
            ),
            _mcp_types.Tool(
                name="get_world_facts",
                description=(
                    "Retrieve facts from a WorldStore, optionally filtered by domain and/or entity."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "store_path": {
                            "type": "string",
                            "description": "Path to the SQLite store file.",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Optional domain filter.",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Optional entity filter (applied after domain filter).",
                        },
                    },
                    "required": ["store_path"],
                },
            ),
            _mcp_types.Tool(
                name="merge_world_state",
                description=(
                    "Merge a remote WorldStore into a local one using CRDT LWW semantics. "
                    "Returns a summary of merged facts and any contradiction events detected."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "local_path": {
                            "type": "string",
                            "description": "Path to the local (target) SQLite store file.",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Path to the remote (source) SQLite store file.",
                        },
                    },
                    "required": ["local_path", "remote_path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[_mcp_types.TextContent]:
        if name == "set_world_fact":
            store_path: str = arguments["store_path"]
            domain: str = arguments["domain"]
            entity: str = arguments["entity"]
            attribute: str = arguments["attribute"]
            value: Any = arguments["value"]
            author: str = arguments["author"]
            version: int = int(arguments.get("version", 0))

            fact = WorldFact(
                domain=domain,
                entity=entity,
                attribute=attribute,
                value=value,
                version=version,
                agent_id=author,
            )
            with WorldStore(store_path) as store:
                store.set_fact(fact)

            result = {
                "status": "ok",
                "fact_id": fact.id,
                "key": f"{domain}.{entity}.{attribute}",
                "value": value,
                "version": version,
                "author": author,
            }
            return [_mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_world_facts":
            store_path = arguments["store_path"]
            domain_opt: str | None = arguments.get("domain")
            entity_opt: str | None = arguments.get("entity")

            with WorldStore(store_path) as store:
                facts = store.list_facts(domain=domain_opt)

            if entity_opt:
                facts = [f for f in facts if f.entity == entity_opt]

            result = {"facts": [f.to_dict() for f in facts], "count": len(facts)}
            return [_mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "merge_world_state":
            local_path: str = arguments["local_path"]
            remote_path: str = arguments["remote_path"]

            with WorldStore(local_path) as local, WorldStore(remote_path) as remote:
                merge_result = WorldMerger().merge(local, remote)

            result = merge_result.to_dict()
            return [_mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with _mcp_stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
