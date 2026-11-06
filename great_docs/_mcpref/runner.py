"""
Run an MCP server module over stdio for protocol introspection

Import the target module, locate its server instance and run it over stdio.
Protocol introspection avoids reliance on the `mcp` library's internal
handler registries, which change between major releases.

Usage:

    python -m great_docs._mcpref.runner <module_path> [<server_var>]
"""

from __future__ import annotations

import asyncio
import importlib
import sys

from .reference import locate_server


async def _run(module_path: str, server_var: str | None) -> None:
    module = importlib.import_module(module_path)
    server = locate_server(module, server_var)
    if server is None:
        raise SystemExit(f"No MCP server instance found in {module_path}")

    # MCPServer (FastMCP before mcp 2.0) provides its own stdio runner.
    if hasattr(server, "run_stdio_async"):
        await server.run_stdio_async()
        return

    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    module = sys.argv[1] if len(sys.argv) > 1 else ""
    var = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    if not module:
        raise SystemExit("usage: python -m great_docs._mcpref.runner <module> [<var>]")
    asyncio.run(_run(module, var))
