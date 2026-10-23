"""MCP Server documentation generator.

Introspects an MCP server module to extract tool, resource, and prompt
definitions, then generates Quarto reference pages.

Introspection is performed over the MCP *wire protocol*: the target server is
launched in a subprocess (via `great_docs._mcp_runner`) and queried with a
standard MCP client. This keeps discovery independent of the `mcp` library's
internal handler registries, which change between major releases: the JSON the
protocol returns is stable regardless of the installed library version.
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
from pathlib import Path
from typing import Any

from ._translations import get_translation

# How long (seconds) to wait for the server subprocess to answer each request
# before giving up on protocol introspection.
_PROTOCOL_TIMEOUT = 30.0


def discover_mcp_server(
    module_path: str,
    server_var: str | None = None,
) -> dict[str, Any] | None:
    """
    Import an MCP server module and extract tool/resource/prompt metadata.

    Parameters
    ----------
    module_path
        Importable module path (e.g., `"sweet.mcp"`).
    server_var
        Name of the Server variable in the module. If `None`, auto-detects
        the first `mcp.server.Server` instance.

    Returns
    -------
    dict | None
        Server metadata dict with keys: name, tools, resources, prompts.
        Returns None if the module cannot be imported or no server found.
    """
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        print(f"Could not import MCP module {module_path}: {e}")
        return None

    server = _locate_server(module, server_var)
    if server is None:
        print(f"No MCP Server instance found in {module_path}")
        return None

    # Primary path: introspect through the wire protocol (version-agnostic).
    info = _introspect_via_protocol(module_path, server_var)

    if info is None:
        # Protocol introspection failed entirely (e.g., the server could not be
        # launched). Fall back to a best-effort static scan of the source so at
        # least the tool list is populated.
        print(
            f"MCP protocol introspection failed for {module_path}; "
            "falling back to static source scan"
        )
        info = {
            "tools": [],
            "resources": [],
            "prompts": [],
            "resource_templates": [],
            "instructions": None,
            "completions_enabled": False,
        }

    if not info["tools"]:
        info["tools"] = _extract_tools_from_source(module)

    # Fill in the server name from the module if the protocol did not supply one.
    if not info.get("name"):
        info["name"] = getattr(server, "name", None) or module_path.split(".")[-1]
    info["module"] = module_path

    return info


def _locate_server(module: Any, server_var: str | None) -> Any:
    """Locate the MCP `Server`/`FastMCP` instance in an imported module."""
    if server_var:
        return getattr(module, server_var, None)

    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        type_name = type(obj).__name__
        module_name = type(obj).__module__ or ""
        if "mcp" in module_name and type_name in ("Server", "FastMCP"):
            return obj
    return None


def _introspect_via_protocol(
    module_path: str,
    server_var: str | None,
) -> dict[str, Any] | None:
    """Launch the server and read its capabilities over the MCP protocol.

    Runs the target server in a subprocess via `great_docs._mcp_runner` and
    speaks the MCP protocol to it with a standard client session. Returns the
    server metadata dict, or `None` if the client could not connect or the
    `mcp` client APIs are unavailable.
    """
    try:
        import asyncio
    except Exception:  # pragma: no cover
        return None  # pragma: no cover

    try:
        return asyncio.run(_collect_over_protocol(module_path, server_var))
    except Exception as e:
        print(f"Could not introspect MCP server over protocol: {e}")
        return None


async def _collect_over_protocol(  # pragma: no cover
    module_path: str,
    server_var: str | None,
) -> dict[str, Any] | None:
    """Connect to the server subprocess and collect all metadata as plain dicts."""
    import asyncio

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    args = ["-m", "great_docs._mcp_runner", module_path]
    if server_var:
        args.append(server_var)

    params = StdioServerParameters(
        command=sys.executable,
        args=args,
        env=dict(os.environ),
        cwd=os.getcwd(),
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = _dump(await asyncio.wait_for(session.initialize(), _PROTOCOL_TIMEOUT))

            server_name = (init.get("serverInfo") or {}).get("name")

            instructions = init.get("instructions")
            if instructions and isinstance(instructions, str) and instructions.strip():
                instructions = instructions.strip()
            else:
                instructions = None

            caps = init.get("capabilities") or {}
            completions_enabled = caps.get("completions") is not None

            tools = await _list_tools(session)
            resources = await _list_resources(session)
            resource_templates = await _list_resource_templates(session)
            prompts = await _list_prompts(session)

            return {
                "name": server_name,
                "tools": tools,
                "resources": resources,
                "prompts": prompts,
                "resource_templates": resource_templates,
                "instructions": instructions,
                "completions_enabled": completions_enabled,
            }


def _dump(obj: Any) -> dict[str, Any]:
    """Serialize an MCP result/model to its wire-JSON dict (camelCase keys).

    `mcp` v1 and v2 disagree on Python attribute names (v2 switched result
    models to snake_case), but `model_dump(by_alias=True)` emits the stable
    camelCase field names defined by the MCP protocol in *both* versions. Read
    from that dict rather than touching attributes so discovery is not coupled to
    a particular library version.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(by_alias=True, exclude_none=True)
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict(by_alias=True)
        except Exception:
            pass
    return {}


async def _call_list(method: Any, cursor: str | None) -> dict[str, Any]:  # pragma: no cover
    """Call an MCP client `list_*` method across `mcp` v1/v2 signatures.

    `mcp` v1 paginates via a `cursor=` keyword; v2 wraps it in a
    `params=PaginatedRequestParams(cursor=...)` object. Detect which shape the
    installed client exposes, call accordingly, and return the result as a
    wire-JSON dict.
    """
    import asyncio
    import inspect

    try:
        param_names = set(inspect.signature(method).parameters)
    except (TypeError, ValueError):
        param_names = set()

    if cursor is None:
        call = method()
    elif "cursor" in param_names:
        call = method(cursor=cursor)
    elif "params" in param_names:
        from mcp.types import PaginatedRequestParams

        call = method(params=PaginatedRequestParams(cursor=cursor))
    else:
        call = method()

    return _dump(await asyncio.wait_for(call, _PROTOCOL_TIMEOUT))


async def _list_tools(session: Any) -> list[dict[str, Any]]:  # pragma: no cover
    """Fetch all tools, following pagination cursors."""
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        result = await _call_list(session.list_tools, cursor)
        for tool in result.get("tools", []) or []:
            tools.append(
                {
                    "name": tool.get("name", "unknown"),
                    "description": tool.get("description", "") or "",
                    "input_schema": tool.get("inputSchema") or {},
                }
            )
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return tools


async def _list_resources(session: Any) -> list[dict[str, Any]]:  # pragma: no cover
    """Fetch all resources, following pagination cursors."""
    resources: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        try:
            result = await _call_list(session.list_resources, cursor)
        except Exception:
            break
        for r in result.get("resources", []) or []:
            resources.append(
                {
                    "uri": str(r.get("uri", "")),
                    "name": r.get("name", "") or "",
                    "description": r.get("description", "") or "",
                    "mime_type": r.get("mimeType"),
                }
            )
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return resources


async def _list_resource_templates(session: Any) -> list[dict[str, Any]]:  # pragma: no cover
    """Fetch all resource templates."""
    templates: list[dict[str, Any]] = []
    try:
        result = await _call_list(session.list_resource_templates, None)
    except Exception:
        return templates
    for t in result.get("resourceTemplates", []) or []:
        templates.append(
            {
                "name": t.get("name", "") or "",
                "uri_template": str(t.get("uriTemplate", "") or ""),
                "description": t.get("description", "") or "",
                "mime_type": t.get("mimeType"),
            }
        )
    return templates


async def _list_prompts(session: Any) -> list[dict[str, Any]]:  # pragma: no cover
    """Fetch all prompts along with their expanded message content."""
    prompts: list[dict[str, Any]] = []
    try:
        result = await _call_list(session.list_prompts, None)
    except Exception:
        return prompts

    for p in result.get("prompts", []) or []:
        arguments = []
        required_names = []
        for arg in p.get("arguments") or []:
            is_required = bool(arg.get("required", False))
            arg_name = arg.get("name", "")
            arguments.append(
                {
                    "name": arg_name,
                    "description": arg.get("description", "") or "",
                    "required": is_required,
                }
            )
            if is_required:
                required_names.append(arg_name)

        name = p.get("name", "")
        prompt_data: dict[str, Any] = {
            "name": name,
            "description": p.get("description", "") or "",
            "arguments": arguments,
            "messages": _messages_for_prompt(
                await _get_prompt_messages(session, name, required_names)
            ),
        }
        prompts.append(prompt_data)

    return prompts


async def _get_prompt_messages(  # pragma: no cover
    session: Any, name: str, required_names: list[str]
) -> list[dict[str, Any]]:
    """Call `prompts/get` for a prompt, tolerating required-argument servers."""
    import asyncio

    # Try with no arguments first; if the server rejects that because arguments
    # are required, retry with placeholder values so we can still show a preview.
    attempts: list[dict[str, str]] = [{}]
    if required_names:
        attempts.append({n: f"<{n}>" for n in required_names})

    for args in attempts:
        try:
            result = await asyncio.wait_for(session.get_prompt(name, args), _PROTOCOL_TIMEOUT)
            return _dump(result).get("messages", []) or []
        except Exception:
            continue
    return []


def _messages_for_prompt(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Flatten MCP prompt messages (wire-JSON dicts) into `{role, text}` dicts."""
    out: list[dict[str, str]] = []
    for msg in messages or []:
        role = msg.get("role", "user")
        content = msg.get("content")
        # Content may be a single content block or a list of them.
        blocks = content if isinstance(content, list) else [content]
        for block in blocks:
            text = block.get("text", "") if isinstance(block, dict) else ""
            if text:
                out.append({"role": role, "text": text})
    return out


def _extract_tools_from_source(module: Any) -> list[dict[str, Any]]:
    """Fallback: parse Tool() calls from module source."""
    tools: list[dict[str, Any]] = []
    try:
        source = inspect.getsource(module)
    except (OSError, TypeError):
        return tools

    # Simple regex-based extraction for Tool(name=..., description=...)
    # This is a fallback when async introspection fails
    pattern = re.compile(
        r'Tool\(\s*name\s*=\s*["\']([^"\']+)["\']\s*,\s*description\s*=\s*'
        r'(?:["\']([^"\']*)["\']|\(\s*["\']([^"\']*)["\'])',
        re.DOTALL,
    )
    for match in pattern.finditer(source):
        name = match.group(1)
        desc = match.group(2) or match.group(3) or ""
        tools.append({"name": name, "description": desc, "input_schema": {}})

    return tools


def categorize_tools(
    tools: list[dict[str, Any]],
    manual_categories: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Group tools into categories.

    Parameters
    ----------
    tools
        List of tool dicts (from discover_mcp_server).
    manual_categories
        Optional explicit mapping: {"Category Name": ["tool_a", "tool_b"]}.
        Tools not in any manual category are grouped by common prefix.

    Returns
    -------
    list[dict]
        List of {"title": str, "tools": list[dict]} section dicts.
    """
    if manual_categories:
        sections = []
        assigned: set[str] = set()

        for category_name, tool_names in manual_categories.items():
            matched = [t for t in tools if t["name"] in tool_names]
            if matched:
                sections.append({"title": category_name, "tools": matched})
                assigned.update(t["name"] for t in matched)

        # Collect unassigned tools
        remaining = [t for t in tools if t["name"] not in assigned]
        if remaining:
            sections.append({"title": "Other Tools", "tools": remaining})

        return sections

    # Auto-categorize by common prefix (e.g., sweet_load → "Load", sweet_validate → "Validate")
    prefix_groups: dict[str, list[dict]] = {}
    for tool in tools:
        name = tool["name"]
        # Strip package prefix (e.g., "sweet_" → "")
        parts = name.split("_")
        if len(parts) >= 2:
            # Use second part as category hint
            category_key = parts[1] if len(parts) > 2 else parts[-1]
        else:
            category_key = name

        prefix_groups.setdefault(category_key, []).append(tool)

    # Convert to sections, merging small groups
    sections: list[dict[str, Any]] = []
    small_tools: list[dict] = []

    for key, group_tools in sorted(prefix_groups.items()):
        if len(group_tools) >= 2:
            title = key.replace("_", " ").title()
            sections.append({"title": title, "tools": group_tools})
        else:
            small_tools.extend(group_tools)

    if small_tools:
        sections.append({"title": "General", "tools": small_tools})

    return sections


def generate_mcp_reference_pages(
    server_info: dict[str, Any],
    output_dir: Path,
    categories: dict[str, list[str]] | None = None,
    display_name: str | None = None,
    language: str = "en",
) -> list[str | dict]:
    """
    Generate Quarto .qmd pages for an MCP server's tools.

    Parameters
    ----------
    server_info
        Server metadata from discover_mcp_server().
    output_dir
        Directory to write reference pages into (e.g., project_path/reference/mcp).
    categories
        Optional manual tool categories.
    display_name
        Display name override for the server.

    Returns
    -------
    list[str | dict]
        Sidebar items for the generated pages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    server_name = display_name or server_info["name"]
    tools = server_info["tools"]
    resources = server_info["resources"]
    prompts = server_info["prompts"]
    resource_templates = server_info.get("resource_templates", [])

    sections = categorize_tools(tools, categories)
    generated_paths: list[str] = []
    sidebar_items: list[str | dict] = []

    # Generate index page
    index_content = _generate_mcp_index_page(server_name, server_info, sections, language)
    index_path = output_dir / "index.qmd"
    index_path.write_text(index_content, encoding="utf-8")
    generated_paths.append("reference/mcp/index.qmd")

    # Generate individual tool pages
    for tool in tools:
        page_content = _generate_tool_page(tool, server_name, language)
        safe_name = tool["name"].replace("-", "_")
        page_path = output_dir / f"{safe_name}.qmd"
        page_path.write_text(page_content, encoding="utf-8")
        generated_paths.append(f"reference/mcp/{safe_name}.qmd")

    # Generate resource pages (if any)
    for resource in resources:
        page_content = _generate_resource_page(resource, server_name, language)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", resource["name"])
        page_path = output_dir / f"resource_{safe_name}.qmd"
        page_path.write_text(page_content, encoding="utf-8")
        generated_paths.append(f"reference/mcp/resource_{safe_name}.qmd")

    # Generate resource template pages (if any)
    for template in resource_templates:
        page_content = _generate_resource_template_page(template, server_name, language)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", template["name"])
        page_path = output_dir / f"template_{safe_name}.qmd"
        page_path.write_text(page_content, encoding="utf-8")
        generated_paths.append(f"reference/mcp/template_{safe_name}.qmd")

    # Generate prompt pages (if any)
    for prompt in prompts:
        page_content = _generate_prompt_page(prompt, server_name, language)
        safe_name = prompt["name"].replace("-", "_")
        page_path = output_dir / f"prompt_{safe_name}.qmd"
        page_path.write_text(page_content, encoding="utf-8")
        generated_paths.append(f"reference/mcp/prompt_{safe_name}.qmd")

    # Build sidebar structure by section
    for section in sections:
        section_paths = [
            f"reference/mcp/{t['name'].replace('-', '_')}.qmd" for t in section["tools"]
        ]
        sidebar_items.append({"section": section["title"], "contents": section_paths})

    # Add resource section to sidebar
    if resources:
        resource_paths = [
            f"reference/mcp/resource_{re.sub(r'[^a-zA-Z0-9_]', '_', r['name'])}.qmd"
            for r in resources
        ]
        sidebar_items.append({"section": "Resources", "contents": resource_paths})

    # Add resource template section to sidebar
    if resource_templates:
        template_paths = [
            f"reference/mcp/template_{re.sub(r'[^a-zA-Z0-9_]', '_', t['name'])}.qmd"
            for t in resource_templates
        ]
        sidebar_items.append({"section": "Resource Templates", "contents": template_paths})

    # Add prompt section to sidebar
    if prompts:
        prompt_paths = [f"reference/mcp/prompt_{p['name'].replace('-', '_')}.qmd" for p in prompts]
        sidebar_items.append({"section": "Prompts", "contents": prompt_paths})

    # Print summary
    if generated_paths:
        print("Generating MCP reference .qmd files:")
        for p in generated_paths:
            print(f"  - {p}")

    return sidebar_items


def _first_sentence(text: str) -> str:
    """Extract the first sentence, handling periods in filenames/identifiers."""
    # Split on ". " (period + space) which indicates a real sentence boundary
    parts = re.split(r"\.\s", text, maxsplit=1)
    result = parts[0].strip()
    # Remove trailing period if present (from end-of-string sentences)
    result = result.rstrip(".")
    return result + "." if result else ""


def _generate_mcp_index_page(
    server_name: str,
    server_info: dict[str, Any],
    sections: list[dict[str, Any]],
    language: str = "en",
) -> str:
    """Generate the MCP reference index page."""
    lines: list[str] = []

    # Front matter
    lines.append("---")
    lines.append(f'title: "{get_translation("mcp_reference", language)}"')
    lines.append("body-classes: doc-reference doc-mcp-reference")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    # Disabling breadcrumbs lets Quarto use the page title in the narrow-screen
    # navigation bar; CSS adds the prefix for the reference type.
    lines.append("bread-crumbs: false")
    lines.append("---")
    lines.append("")

    # Capability tiles — raw HTML so Quarto renders them correctly
    n_tools = len(server_info["tools"])
    n_resources = len(server_info["resources"])
    n_prompts = len(server_info["prompts"])
    n_templates = len(server_info.get("resource_templates", []))
    has_completions = server_info.get("completions_enabled", False)
    has_instructions = bool(server_info.get("instructions"))

    completions_mark = "✓" if has_completions else "✗"
    instructions_mark = "✓" if has_instructions else "✗"

    lines.append('<div class="mcp-capability-tiles">')
    lines.append(
        f'<span class="mcp-tile mcp-tile-tools">'
        f'<span class="mcp-tile-label">{get_translation("mcp_tools", language)}</span>'
        f'<span class="mcp-tile-count">{n_tools}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-resources">'
        f'<span class="mcp-tile-label">{get_translation("mcp_resources", language)}</span>'
        f'<span class="mcp-tile-count">{n_resources}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-templates">'
        f'<span class="mcp-tile-label">{get_translation("mcp_resource_templates", language)}</span>'
        f'<span class="mcp-tile-count">{n_templates}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-prompts">'
        f'<span class="mcp-tile-label">{get_translation("mcp_prompts", language)}</span>'
        f'<span class="mcp-tile-count">{n_prompts}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-instructions">'
        f'<span class="mcp-tile-label">{get_translation("mcp_instructions", language)}</span>'
        f'<span class="mcp-tile-count">{instructions_mark}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-completions">'
        f'<span class="mcp-tile-label">{get_translation("mcp_completions", language)}</span>'
        f'<span class="mcp-tile-count">{completions_mark}</span></span>'
    )
    lines.append("</div>")
    lines.append("")

    # Server instructions (if present)
    instructions = server_info.get("instructions")
    if instructions:
        instr_title = get_translation("mcp_server_instructions", language)
        lines.append(f'::: {{.details summary="{instr_title}" type="note"}}')
        lines.append("")
        lines.append("```text")
        lines.append(instructions)
        lines.append("```")
        lines.append("")
        lines.append(":::")
        lines.append("")

    # Completions note (if enabled)
    if has_completions:
        comp_title = get_translation("mcp_completions", language)
        lines.append(f'::: {{.details summary="{comp_title}" type="tip"}}')
        lines.append("")
        lines.append(get_translation("mcp_completions_desc", language))
        lines.append("")
        lines.append(":::")
        lines.append("")

    # Tool listing by section
    for section in sections:
        lines.append(f"### {section['title']} {{.doc-group}}")
        lines.append("")
        for tool in section["tools"]:
            name = tool["name"]
            desc = _first_sentence(tool["description"])
            safe_name = name.replace("-", "_")
            lines.append(
                f"[{name}]({safe_name}.qmd){{.doc-function .doc-label .doc-label-mcp-tool}}"
            )
            lines.append("")
            lines.append(f":   {desc}")
            lines.append("")

    # Resources section
    if server_info["resources"]:
        lines.append(f"### {get_translation('mcp_resources', language)} {{.doc-group}}")
        lines.append("")
        for r in server_info["resources"]:
            name = r["name"]
            desc_line = _first_sentence(r.get("description", "") or "")
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
            lines.append(
                f"[{name}](resource_{safe}.qmd){{.doc-function .doc-label .doc-label-mcp-resource}}"
            )
            lines.append("")
            lines.append(f":   {desc_line}")
            lines.append("")

    # Resource templates section
    resource_templates = server_info.get("resource_templates", [])
    if resource_templates:
        lines.append(f"### {get_translation('mcp_resource_templates', language)} {{.doc-group}}")
        lines.append("")
        for t in resource_templates:
            name = t["name"]
            desc_line = _first_sentence(t.get("description", "") or "")
            safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
            lines.append(
                f"[{name}](template_{safe}.qmd)"
                f"{{.doc-function .doc-label .doc-label-mcp-resource-template}}"
            )
            lines.append("")
            lines.append(f":   {desc_line}")
            lines.append("")

    # Prompts section
    if server_info["prompts"]:
        lines.append(f"### {get_translation('mcp_prompts', language)} {{.doc-group}}")
        lines.append("")
        for p in server_info["prompts"]:
            name = p["name"]
            desc_line = _first_sentence(p.get("description", "") or "")
            safe = name.replace("-", "_")
            lines.append(
                f"[{name}](prompt_{safe}.qmd){{.doc-function .doc-label .doc-label-mcp-prompt}}"
            )
            lines.append("")
            lines.append(f":   {desc_line}")
            lines.append("")

    return "\n".join(lines) + "\n"


def _generate_tool_page(tool: dict[str, Any], server_name: str, language: str = "en") -> str:
    """Generate a reference page for a single MCP tool."""
    lines: list[str] = []
    name = tool["name"]
    description = tool["description"]
    schema = tool.get("input_schema", {})

    # Front matter — plain title for sidebar label; heading rendered below
    lines.append("---")
    lines.append(f'title: "{name}"')
    lines.append("title-block-style: none")
    lines.append("bread-crumbs: false")
    lines.append("body-classes: doc-api-page doc-mcp-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    lines.append("---")
    lines.append("")
    lines.append(f"# [{name}]{{.doc-object-name .doc-label .doc-label-mcp-tool}} {{.title}}")
    lines.append("")

    # Description
    if description:
        sentences = description.split(". ")
        short_desc = sentences[0].strip()
        if not short_desc.endswith("."):
            short_desc += "."
        lines.append("::: {.doc-subject}")
        lines.append(short_desc)
        lines.append(":::")
        lines.append("")

        if len(sentences) > 1:
            extended = ". ".join(sentences[1:]).strip()
            if extended:
                lines.append("::: {.doc-text}")
                lines.append(extended)
                lines.append(":::")
                lines.append("")

    # Signature / Usage (JSON call format)
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    if properties:
        params = []
        for param_name, param_info in properties.items():
            if param_name in required:
                params.append(f'  "{param_name}": ...')
            else:
                default = param_info.get("default")
                if default is not None:
                    params.append(f'  "{param_name}": {_json_value(default)}')
                else:
                    params.append(f'  "{param_name}": ...  // optional')

        lines.append("::: {.doc-signature .doc-function}")
        lines.append("```json")
        lines.append("{")
        lines.append(f'  "tool": "{name}",')
        lines.append('  "arguments": {')
        for i, p in enumerate(params):
            sep = "," if i < len(params) - 1 else ""
            lines.append(f"  {p}{sep}")
        lines.append("  }")
        lines.append("}")
        lines.append("```")
        lines.append(":::")
        lines.append("")

    # Match the Python API's definition-list format. Write this heading at `###`
    # because MCP pages keep the site-wide shift. Disabling that shift prevents
    # Quarto from hoisting the `.title` heading and creates a duplicate title.
    if properties:
        lines.append(f"### {get_translation('mcp_parameters', language)} {{.doc-parameters}}")
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for param_name, param_info in properties.items():
            param_type = _schema_type_display(param_info)
            param_desc = param_info.get("description", "")
            is_required = param_name in required
            default = param_info.get("default")

            # Build the parameter header line using HTML spans (pandoc spans
            # don't work inside raw <code> elements)
            header = f'<code><span class="doc-parameter-name">{param_name}</span>'
            header += '<span class="doc-parameter-annotation-sep">:</span> '
            header += f'<span class="doc-parameter-annotation">{param_type}</span>'
            if default is not None:
                header += ' <span class="doc-parameter-default-sep op">=</span> '
                header += f'<span class="doc-parameter-default">{_json_value(default)}</span>'
            header += "</code>"
            lines.append(header)
            lines.append("")

            # Description as definition-list body
            desc_parts = []
            if param_desc:
                desc_parts.append(param_desc)
            if "enum" in param_info:
                values = ", ".join(f"`{v}`" for v in param_info["enum"])
                desc_parts.append(f"Allowed values: {values}")
            if is_required:
                desc_parts.append("[required]{.badge .bg-primary}")

            desc_text = " ".join(desc_parts) if desc_parts else "No description."
            lines.append(f":   {desc_text}")
            lines.append("")
        lines.append(":::")
        lines.append("")

    return "\n".join(lines) + "\n"


def _generate_resource_page(
    resource: dict[str, Any], server_name: str, language: str = "en"
) -> str:
    """Generate a reference page for an MCP resource."""
    lines: list[str] = []
    name = resource["name"]
    uri = resource.get("uri", "")
    description = resource.get("description", "")
    mime_type = resource.get("mime_type")

    lines.append("---")
    lines.append(f'title: "{name}"')
    lines.append("title-block-style: none")
    lines.append("bread-crumbs: false")
    lines.append("body-classes: doc-api-page doc-mcp-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    lines.append("---")
    lines.append("")
    lines.append(f"# [{name}]{{.doc-object-name .doc-label .doc-label-mcp-resource}} {{.title}}")
    lines.append("")

    if description:
        lines.append("::: {.doc-subject}")
        lines.append(description)
        lines.append(":::")
        lines.append("")

    lines.append(f"### {get_translation('mcp_details', language)} {{.doc-parameters}}")
    lines.append("")
    lines.append(f"**URI:** `{uri}`")
    lines.append("")
    if mime_type:
        lines.append(f"**MIME Type:** `{mime_type}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def _generate_resource_template_page(
    template: dict[str, Any], server_name: str, language: str = "en"
) -> str:
    """Generate a reference page for an MCP resource template."""
    lines: list[str] = []
    name = template["name"]
    uri_template = template.get("uri_template", "")
    description = template.get("description", "")
    mime_type = template.get("mime_type")

    lines.append("---")
    lines.append(f'title: "{name}"')
    lines.append("title-block-style: none")
    lines.append("bread-crumbs: false")
    lines.append("body-classes: doc-api-page doc-mcp-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    lines.append("---")
    lines.append("")
    lines.append(
        f"# [{name}]{{.doc-object-name .doc-label .doc-label-mcp-resource-template}} {{.title}}"
    )
    lines.append("")

    if description:
        lines.append("::: {.doc-subject}")
        lines.append(description)
        lines.append(":::")
        lines.append("")

    lines.append(f"### {get_translation('mcp_details', language)} {{.doc-parameters}}")
    lines.append("")
    lines.append(f"**URI Template:** `{uri_template}`")
    lines.append("")
    if mime_type:
        lines.append(f"**MIME Type:** `{mime_type}`")
        lines.append("")

    # Extract template variables from URI pattern (e.g., {symbol}, {path})
    import re as _re

    variables = _re.findall(r"\{(\w+)\}", uri_template)
    if variables:
        lines.append(
            f"### {get_translation('mcp_template_variables', language)} {{.doc-parameters}}"
        )
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for var in variables:
            lines.append(
                f'<code><span class="doc-parameter-name">{var}</span>'
                f'<span class="doc-parameter-annotation-sep">:</span> '
                f'<span class="doc-parameter-annotation">string</span>'
                f"</code>"
            )
            lines.append("")
            lines.append(":   Variable substituted into the URI pattern.")
            lines.append("")
        lines.append(":::")
        lines.append("")

    return "\n".join(lines) + "\n"


def _generate_prompt_page(prompt: dict[str, Any], server_name: str, language: str = "en") -> str:
    """Generate a reference page for an MCP prompt."""
    lines: list[str] = []
    name = prompt["name"]
    description = prompt.get("description", "")
    arguments = prompt.get("arguments", [])
    messages = prompt.get("messages", [])

    lines.append("---")
    lines.append(f'title: "{name}"')
    lines.append("title-block-style: none")
    lines.append("bread-crumbs: false")
    lines.append("body-classes: doc-api-page doc-mcp-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    lines.append("---")
    lines.append("")
    lines.append(f"# [{name}]{{.doc-object-name .doc-label .doc-label-mcp-prompt}} {{.title}}")
    lines.append("")

    if description:
        lines.append("::: {.doc-subject}")
        lines.append(description)
        lines.append(":::")
        lines.append("")

    if arguments:
        lines.append(f"### {get_translation('mcp_arguments', language)} {{.doc-parameters}}")
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for arg in arguments:
            arg_name = arg["name"]
            arg_desc = arg.get("description", "")
            is_required = arg.get("required", False)

            header = f'<code><span class="doc-parameter-name">{arg_name}</span>'
            header += '<span class="doc-parameter-annotation-sep">:</span> '
            header += '<span class="doc-parameter-annotation">string</span>'
            header += "</code>"
            lines.append(header)
            lines.append("")

            desc_parts = []
            if arg_desc:
                desc_parts.append(arg_desc)
            if is_required:
                desc_parts.append("[required]{.badge .bg-primary}")
            desc_text = " ".join(desc_parts) if desc_parts else "No description."
            lines.append(f":   {desc_text}")
            lines.append("")
        lines.append(":::")
        lines.append("")

    # Prompt message content
    if messages:
        lines.append(f"### {get_translation('mcp_prompt_text', language)}")
        lines.append("")
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if text:
                lines.append(
                    f'::: {{.callout-note title="{get_translation("mcp_user_message", language) if role == "user" else role.capitalize()}"}}'
                )
                lines.append("")
                lines.append("```text")
                lines.append(text)
                lines.append("```")
                lines.append("")
                lines.append(":::")
                lines.append("")

    return "\n".join(lines) + "\n"


def _schema_type_display(param_info: dict) -> str:
    """Convert JSON Schema type info to a readable display string."""
    ptype = param_info.get("type", "any")

    if ptype == "array":
        items = param_info.get("items", {})
        item_type = items.get("type", "any")
        return f"array[{item_type}]"
    elif ptype == "object":
        return "object"
    elif "enum" in param_info:
        return f"{ptype} (enum)"
    else:
        return ptype


def _json_value(value: Any) -> str:
    """Format a default value as a JSON-like string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, str):
        return f'"{value}"'
    elif value is None:
        return "null"
    else:
        return str(value)


def generate_mcp_manifest(
    server_info: dict[str, Any],
    output_dir: Path,
    *,
    package_name: str | None = None,
    repo_url: str | None = None,
    site_url: str | None = None,
    install_command: str | None = None,
) -> Path:
    """
    Generate a .well-known/mcp.json discovery manifest.

    This manifest enables clients and registries to auto-discover the MCP server
    and its capabilities from the documentation site URL.

    Parameters
    ----------
    server_info
        Server metadata from discover_mcp_server().
    output_dir
        The build project path (e.g., project_path). The manifest is placed
        at `output_dir/.well-known/mcp.json`.
    package_name
        The pip-installable package name (e.g., "great-docs").
    repo_url
        Repository URL (e.g., "https://github.com/posit-dev/great-docs").
    site_url
        Canonical documentation site URL.
    install_command
        Custom install command. Defaults to `pip install {package_name}[mcp]`.

    Returns
    -------
    Path
        Path to the generated mcp.json file.
    """
    import json

    well_known_dir = output_dir / ".well-known"
    well_known_dir.mkdir(parents=True, exist_ok=True)

    tools = server_info.get("tools", [])
    resources = server_info.get("resources", [])
    prompts = server_info.get("prompts", [])

    # Build the manifest
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "server": {
            "name": server_info["name"],
            "description": f"MCP server with {len(tools)} tools",
            "transport": ["stdio"],
        },
        "capabilities": {},
    }

    # Tools summary
    if tools:
        manifest["capabilities"]["tools"] = {
            "count": len(tools),
            "list": [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                }
                for t in tools
            ],
        }

    # Resources summary
    if resources:
        manifest["capabilities"]["resources"] = {
            "count": len(resources),
            "list": [
                {
                    "uri": r.get("uri", ""),
                    "name": r.get("name", ""),
                    "description": r.get("description", ""),
                }
                for r in resources
            ],
        }

    # Prompts summary
    if prompts:
        manifest["capabilities"]["prompts"] = {
            "count": len(prompts),
            "list": [
                {
                    "name": p["name"],
                    "description": p.get("description", ""),
                }
                for p in prompts
            ],
        }

    # Installation info
    install_info: dict[str, Any] = {}
    if package_name:
        install_info["package"] = package_name
        install_info["install"] = install_command or f"pip install {package_name}[mcp]"
    if repo_url:
        install_info["repository"] = repo_url
    if install_info:
        manifest["installation"] = install_info

    # Run command (how to start the server)
    module_path = server_info.get("module", "")
    if module_path:
        manifest["server"]["run"] = {
            "command": "python",
            "args": ["-m", module_path],
        }

    # Documentation link
    if site_url:
        manifest["documentation"] = {
            "url": site_url.rstrip("/") + "/reference/mcp/",
            "site": site_url,
        }

    # Write manifest
    manifest_path = well_known_dir / "mcp.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Generated .well-known/mcp.json ({len(tools)} tools)")
    return manifest_path
