"""Run an arbitrary MCP server module over stdio.

This is a tiny, version-agnostic launcher used by `great_docs._mcpref.reference`
to introspect an MCP server *through the wire protocol* rather than by reaching
into the `mcp` library's internal handler registries (which change between
major releases). The launcher imports the target module, locates its server
instance, and runs it over stdio using whichever `run` shape the installed
`mcp` version exposes.

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

    # FastMCP knows how to run itself over stdio.
    if hasattr(server, "run_stdio_async"):
        await server.run_stdio_async()
        return

    # FastMCP exposes the underlying low-level server as `_mcp_server`.
    low = getattr(server, "_mcp_server", server)  # pragma: no cover

    from mcp.server.stdio import stdio_server  # pragma: no cover

    async with stdio_server() as (read_stream, write_stream):  # pragma: no cover
        # mcp v1 requires initialization options; v2's `run` takes only the
        # streams. Try the v1 shape first and fall back on signature mismatch.
        init_options = None
        if hasattr(low, "create_initialization_options"):
            try:
                init_options = low.create_initialization_options()
            except Exception:
                init_options = None

        if init_options is not None:
            try:
                await low.run(read_stream, write_stream, init_options)
                return
            except TypeError:
                pass

        await low.run(read_stream, write_stream)


if __name__ == "__main__":
    module = sys.argv[1] if len(sys.argv) > 1 else ""
    var = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    if not module:
        raise SystemExit("usage: python -m great_docs._mcpref.runner <module> [<var>]")
    asyncio.run(_run(module, var))
