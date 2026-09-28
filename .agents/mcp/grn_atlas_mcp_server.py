#!/usr/bin/env python3
"""Local stdio MCP server exposing GRN Atlas benchmark tools to Codex."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool, ToolAnnotations

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
sys.path.insert(0, str(SKILLS_DIR))

import _test_llm_orchestration as orchestration

SERVER = Server(
    "grn-atlas-tools",
    version="0.1.0",
    instructions=(
        "Use these read-only GRN Atlas analysis tools to answer regulatory-network "
        "questions. For multi-step questions, use each returned result to choose the next tool."
    ),
)
HTTP_URL = os.environ.get("GRN_MCP_HTTP", "http://127.0.0.1:8001")


def _tools() -> list[Tool]:
    return [
        Tool(
            name=definition["function"]["name"],
            description=definition["function"].get("description", ""),
            inputSchema=definition["function"].get("parameters", {"type": "object", "properties": {}}),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
        )
        for definition in orchestration.TOOLS
    ]


@SERVER.list_tools()
async def list_tools() -> list[Tool]:
    return _tools()


@SERVER.call_tool()
async def call_tool(name: str, arguments: dict) -> dict | list[TextContent]:
    output = await asyncio.to_thread(orchestration.execute_tool, name, arguments, HTTP_URL, 12000)
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return [TextContent(type="text", text=output)]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await SERVER.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="grn-atlas-tools",
                server_version="0.1.0",
                capabilities=SERVER.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
