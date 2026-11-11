"""MCP server construction and protocol adapters"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.context import ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    CompleteRequestParams,
    CompleteResult,
    Completion,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    TextResourceContents,
)

from . import completions as _completions
from . import prompts as _prompts
from . import resources as _resources
from . import tools as _tools

_INSTRUCTIONS = (
    "You are connected to the Great Docs MCP server. Great Docs is a Python "
    "documentation generator that produces Quarto-based reference sites from "
    "package introspection.\n\n"
    "Available capabilities:\n"
    "- **Tools**: Build docs, preview, scan packages, lint, manage config, "
    "add pages, and compare API versions.\n"
    "- **Prompts**: Pre-built prompt templates for common documentation "
    "workflows (project setup, writing guides, debugging builds).\n"
    "- **Resources**: Read project configuration, build logs, and API surface "
    "data directly.\n\n"
    "Start with `gd_status` to understand the current project state, then use "
    "tools and prompts to accomplish documentation tasks."
)


async def _on_list_tools(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListToolsResult:
    return ListToolsResult(tools=await _tools.list_tools())


async def _on_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    content = await _tools.call_tool(params.name, params.arguments or {})
    return CallToolResult(
        content=list(content),
        is_error=isinstance(content, _tools.ToolCallContent) and content.is_error,
    )


async def _on_list_prompts(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListPromptsResult:
    return ListPromptsResult(prompts=await _prompts.list_prompts())


async def _on_get_prompt(
    ctx: ServerRequestContext, params: GetPromptRequestParams
) -> GetPromptResult:
    return await _prompts.get_prompt(params.name, params.arguments)


async def _on_list_resources(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListResourcesResult:
    return ListResourcesResult(resources=await _resources.list_resources())


async def _on_read_resource(
    ctx: ServerRequestContext, params: ReadResourceRequestParams
) -> ReadResourceResult:
    text = await _resources.read_resource(params.uri)
    return ReadResourceResult(contents=[TextResourceContents(uri=params.uri, text=text)])


async def _on_list_resource_templates(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListResourceTemplatesResult:
    return ListResourceTemplatesResult(
        resource_templates=await _resources.list_resource_templates()
    )


async def _on_completion(
    ctx: ServerRequestContext, params: CompleteRequestParams
) -> CompleteResult:
    completion = await _completions.handle_completion(params.ref, params.argument, params.context)
    if completion is None:
        completion = Completion(values=[])
    return CompleteResult(completion=completion)


server = Server(
    name="great-docs",
    instructions=_INSTRUCTIONS,
    on_list_tools=_on_list_tools,
    on_call_tool=_on_call_tool,
    on_list_prompts=_on_list_prompts,
    on_get_prompt=_on_get_prompt,
    on_list_resources=_on_list_resources,
    on_read_resource=_on_read_resource,
    on_list_resource_templates=_on_list_resource_templates,
    on_completion=_on_completion,
)


async def run_mcp_server() -> None:
    """Run the Great Docs MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
