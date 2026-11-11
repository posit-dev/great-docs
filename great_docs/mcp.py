"""Great Docs MCP Server — Exposes documentation operations as MCP tools.

Allows AI agents (Claude Desktop, VS Code Copilot, Cursor, etc.) to drive
Great Docs documentation workflows through the Model Context Protocol.

Usage:
    great-docs serve --mcp    # Via CLI (future)
    python -m great_docs.mcp  # Directly
"""

from __future__ import annotations

import shlex as shlex
from pathlib import Path as Path
from typing import TYPE_CHECKING as TYPE_CHECKING
from typing import Any as Any
from urllib.parse import parse_qs as parse_qs
from urllib.parse import urlsplit as urlsplit

from jsonschema import Draft202012Validator as Draft202012Validator
from mcp.server import Server as Server
from mcp.server.context import ServerRequestContext as ServerRequestContext
from mcp.server.stdio import stdio_server as stdio_server
from mcp.types import CallToolRequestParams as CallToolRequestParams
from mcp.types import CallToolResult as CallToolResult
from mcp.types import CompleteRequestParams as CompleteRequestParams
from mcp.types import CompleteResult as CompleteResult
from mcp.types import Completion as Completion
from mcp.types import CompletionArgument as CompletionArgument
from mcp.types import CompletionContext as CompletionContext
from mcp.types import GetPromptRequestParams as GetPromptRequestParams
from mcp.types import GetPromptResult as GetPromptResult
from mcp.types import ListPromptsResult as ListPromptsResult
from mcp.types import ListResourcesResult as ListResourcesResult
from mcp.types import ListResourceTemplatesResult as ListResourceTemplatesResult
from mcp.types import ListToolsResult as ListToolsResult
from mcp.types import PaginatedRequestParams as PaginatedRequestParams
from mcp.types import Prompt as Prompt
from mcp.types import PromptArgument as PromptArgument
from mcp.types import PromptMessage as PromptMessage
from mcp.types import PromptReference as PromptReference
from mcp.types import ReadResourceRequestParams as ReadResourceRequestParams
from mcp.types import ReadResourceResult as ReadResourceResult
from mcp.types import Resource as Resource
from mcp.types import ResourceTemplate as ResourceTemplate
from mcp.types import ResourceTemplateReference as ResourceTemplateReference
from mcp.types import TextContent as TextContent
from mcp.types import TextResourceContents as TextResourceContents
from mcp.types import Tool as Tool

from ._build import outputs as outputs
from ._build.ownership import is_in_great_docs_build_dir as is_in_great_docs_build_dir
from ._build.ownership import recognised_build_dirs as recognised_build_dirs
from ._build.steps import PROJECT_ERRORS as PROJECT_ERRORS
from ._build.steps import USER_CODE_ERRORS as USER_CODE_ERRORS
from ._build.steps import BuildError as BuildError
from ._content import user_guide as user_guide
from ._mcp.completions import handle_completion as handle_completion
from ._mcp.prompts import get_prompt as get_prompt
from ._mcp.prompts import list_prompts as list_prompts
from ._mcp.resources import list_resource_templates as list_resource_templates
from ._mcp.resources import list_resources as list_resources
from ._mcp.resources import read_resource as read_resource
from ._mcp.server import run_mcp_server as run_mcp_server
from ._mcp.server import server as server
from ._mcp.tools import call_tool as call_tool
from ._mcp.tools import list_tools as list_tools
from ._project.layout import CONVENTIONAL_DOC_DIRS as CONVENTIONAL_DOC_DIRS
from ._project.layout import Layout as Layout
from ._project.layout import LayoutError as LayoutError

if __name__ == "__main__":
    import asyncio

    asyncio.run(run_mcp_server())
