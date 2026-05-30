"""MCP Server documentation generator.

Introspects an MCP server module to extract tool, resource, and prompt
definitions, then generates Quarto reference pages.
"""

from __future__ import annotations

import importlib
import inspect
import re
from pathlib import Path
from typing import Any

from ._translations import get_translation


def discover_mcp_server(
    module_path: str,
    server_var: str | None = None,
) -> dict[str, Any] | None:
    """
    Import an MCP server module and extract tool/resource/prompt metadata.

    Parameters
    ----------
    module_path
        Importable module path (e.g., "sweet.mcp").
    server_var
        Name of the Server variable in the module. If None, auto-detects
        the first ``mcp.server.Server`` instance.

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

    # Find the Server instance
    server = None
    if server_var:
        server = getattr(module, server_var, None)
    else:
        # Auto-detect: look for mcp.server.Server instances
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            type_name = type(obj).__name__
            module_name = type(obj).__module__ or ""
            if type_name == "Server" and "mcp" in module_name:
                server = obj
                break

    if server is None:
        print(f"No MCP Server instance found in {module_path}")
        return None

    # Extract server name
    server_name = getattr(server, "name", None) or module_path.split(".")[-1]

    # Extract tools by calling the registered list_tools handler
    tools = _extract_tools(module, server)
    resources = _extract_resources(module, server)
    prompts = _extract_prompts(module, server)
    resource_templates = _extract_resource_templates(module, server)
    instructions = _extract_instructions(server)
    completions_enabled = _extract_completions_enabled(server)

    return {
        "name": server_name,
        "module": module_path,
        "tools": tools,
        "resources": resources,
        "prompts": prompts,
        "resource_templates": resource_templates,
        "instructions": instructions,
        "completions_enabled": completions_enabled,
    }


def _extract_tools(module: Any, server: Any) -> list[dict[str, Any]]:
    """Extract tool definitions from the server's registered handlers."""
    tools: list[dict[str, Any]] = []

    # Strategy 1: Call the list_tools handler directly (async → run sync)
    import asyncio

    handler = None

    # The mcp library stores handlers keyed by request type classes
    request_handlers = getattr(server, "request_handlers", {})
    if not request_handlers:
        request_handlers = getattr(server, "_request_handlers", {})

    for key, handler_fn in request_handlers.items():
        key_str = getattr(key, "__name__", str(key))
        if "ListTools" in key_str or "list_tools" in key_str:
            handler = handler_fn
            break

    if handler:
        try:
            # Run the async handler
            loop = asyncio.new_event_loop()
            try:
                # Build a minimal request object if needed
                try:
                    from mcp.types import ListToolsRequest

                    req = ListToolsRequest(method="tools/list")
                except Exception:
                    req = None
                result = loop.run_until_complete(handler(req))
                # Result may be wrapped in ServerResult with .root
                inner = getattr(result, "root", result)
                tool_list = getattr(inner, "tools", None)
                if tool_list is None and isinstance(inner, (list, tuple)):
                    tool_list = inner
                if tool_list:
                    for tool in tool_list:
                        tools.append(_tool_to_dict(tool))
            finally:
                loop.close()
        except Exception:
            pass

    # Strategy 2: If handler approach failed, scan for Tool() instantiations
    # by looking at the source of the list_tools function
    if not tools:
        tools = _extract_tools_from_source(module)

    return tools


def _tool_to_dict(tool: Any) -> dict[str, Any]:
    """Convert an MCP Tool object to a plain dictionary."""
    schema = getattr(tool, "inputSchema", {}) or {}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    elif hasattr(schema, "dict"):
        schema = schema.dict()

    return {
        "name": getattr(tool, "name", "unknown"),
        "description": getattr(tool, "description", ""),
        "input_schema": schema,
    }


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


def _extract_resources(module: Any, server: Any) -> list[dict[str, Any]]:
    """Extract resource definitions from the server."""
    resources: list[dict[str, Any]] = []
    import asyncio

    request_handlers = getattr(server, "request_handlers", {})
    if not request_handlers:
        request_handlers = getattr(server, "_request_handlers", {})

    for key, handler_fn in request_handlers.items():
        key_str = getattr(key, "__name__", str(key))
        if "ListResources" in key_str or "list_resources" in key_str:
            try:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler_fn(None))
                    inner = getattr(result, "root", result)
                    resource_list = getattr(inner, "resources", None)
                    if resource_list is None and isinstance(inner, (list, tuple)):
                        resource_list = inner
                    if resource_list:
                        for r in resource_list:
                            resources.append(
                                {
                                    "uri": str(getattr(r, "uri", "")),
                                    "name": getattr(r, "name", ""),
                                    "description": getattr(r, "description", ""),
                                    "mime_type": getattr(r, "mimeType", None),
                                }
                            )
                finally:
                    loop.close()
            except Exception:
                pass
            break

    return resources


def _extract_prompts(module: Any, server: Any) -> list[dict[str, Any]]:
    """Extract prompt definitions from the server, including message content."""
    prompts: list[dict[str, Any]] = []
    import asyncio

    request_handlers = getattr(server, "request_handlers", {})
    if not request_handlers:
        request_handlers = getattr(server, "_request_handlers", {})

    # First, get the prompt list
    list_handler = None
    get_handler = None
    for key, handler_fn in request_handlers.items():
        key_str = getattr(key, "__name__", str(key))
        if "ListPrompts" in key_str or "list_prompts" in key_str:
            list_handler = handler_fn
        if "GetPrompt" in key_str or "get_prompt" in key_str:
            get_handler = handler_fn

    if list_handler:
        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(list_handler(None))
                inner = getattr(result, "root", result)
                prompt_list = getattr(inner, "prompts", None)
                if prompt_list is None and isinstance(inner, (list, tuple)):
                    prompt_list = inner
                if prompt_list:
                    for p in prompt_list:
                        arguments = []
                        for arg in getattr(p, "arguments", []) or []:
                            arguments.append(
                                {
                                    "name": getattr(arg, "name", ""),
                                    "description": getattr(arg, "description", ""),
                                    "required": getattr(arg, "required", False),
                                }
                            )
                        prompt_data: dict[str, Any] = {
                            "name": getattr(p, "name", ""),
                            "description": getattr(p, "description", ""),
                            "arguments": arguments,
                            "messages": [],
                        }

                        # Try to get the actual prompt messages
                        if get_handler:
                            try:
                                from mcp.types import GetPromptRequest, GetPromptRequestParams

                                req = GetPromptRequest(
                                    method="prompts/get",
                                    params=GetPromptRequestParams(
                                        name=getattr(p, "name", ""),
                                        arguments=None,
                                    ),
                                )
                                get_result = loop.run_until_complete(get_handler(req))
                                get_inner = getattr(get_result, "root", get_result)
                                messages = getattr(get_inner, "messages", []) or []
                                for msg in messages:
                                    role = getattr(msg, "role", "user")
                                    content = getattr(msg, "content", None)
                                    if content:
                                        text = getattr(content, "text", "")
                                        if text:
                                            prompt_data["messages"].append(
                                                {"role": role, "text": text}
                                            )
                            except Exception:
                                pass

                        prompts.append(prompt_data)
            finally:
                loop.close()
        except Exception:
            pass

    return prompts


def _extract_resource_templates(module: Any, server: Any) -> list[dict[str, Any]]:
    """Extract resource template definitions from the server."""
    templates: list[dict[str, Any]] = []
    import asyncio

    request_handlers = getattr(server, "request_handlers", {})
    if not request_handlers:
        request_handlers = getattr(server, "_request_handlers", {})

    for key, handler_fn in request_handlers.items():
        key_str = getattr(key, "__name__", str(key))
        if "ListResourceTemplates" in key_str or "list_resource_templates" in key_str:
            try:
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(handler_fn(None))
                    inner = getattr(result, "root", result)
                    template_list = getattr(inner, "resourceTemplates", None)
                    if template_list is None and isinstance(inner, (list, tuple)):
                        template_list = inner
                    if template_list:
                        for t in template_list:
                            templates.append(
                                {
                                    "name": getattr(t, "name", ""),
                                    "uri_template": getattr(t, "uriTemplate", ""),
                                    "description": getattr(t, "description", ""),
                                    "mime_type": getattr(t, "mimeType", None),
                                }
                            )
                finally:
                    loop.close()
            except Exception:
                pass
            break

    return templates


def _extract_instructions(server: Any) -> str | None:
    """Extract server-level instructions if set."""
    instructions = getattr(server, "instructions", None)
    if instructions and isinstance(instructions, str) and instructions.strip():
        return instructions.strip()
    return None


def _extract_completions_enabled(server: Any) -> bool:
    """Check whether the server has a completions handler registered."""
    request_handlers = getattr(server, "request_handlers", {})
    if not request_handlers:
        request_handlers = getattr(server, "_request_handlers", {})

    for key in request_handlers:
        key_str = getattr(key, "__name__", str(key))
        if "Complete" in key_str or "completion" in key_str:
            return True
    return False


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
    lines.append("body-classes: doc-api-page doc-reference")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
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
        f'<span class="mcp-tile mcp-tile-completions">'
        f'<span class="mcp-tile-label">{get_translation("mcp_completions", language)}</span>'
        f'<span class="mcp-tile-count">{completions_mark}</span></span>'
    )
    lines.append(
        f'<span class="mcp-tile mcp-tile-instructions">'
        f'<span class="mcp-tile-label">{get_translation("mcp_instructions", language)}</span>'
        f'<span class="mcp-tile-count">{instructions_mark}</span></span>'
    )
    lines.append("</div>")
    lines.append("")

    # Server instructions (if present)
    instructions = server_info.get("instructions")
    if instructions:
        instr_title = get_translation("mcp_server_instructions", language)
        lines.append(f"::: {{.callout-note collapse='true' title='{instr_title}'}}")
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
        lines.append(f"::: {{.callout-tip collapse='true' title='{comp_title}'}}")
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
    lines.append("body-classes: doc-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
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

        lines.append("::: {.doc-signature .doc-Kind.FUNCTION}")
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

    # Parameters section — uses definition list format matching Python API style
    if properties:
        lines.append(f"## {get_translation('mcp_parameters', language)} {{.doc-parameters}}")
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
    lines.append("body-classes: doc-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
    lines.append("---")
    lines.append("")
    lines.append(f"# [{name}]{{.doc-object-name .doc-label .doc-label-mcp-resource}} {{.title}}")
    lines.append("")

    if description:
        lines.append("::: {.doc-subject}")
        lines.append(description)
        lines.append(":::")
        lines.append("")

    lines.append(f"## {get_translation('mcp_details', language)} {{.doc-parameters}}")
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
    lines.append("body-classes: doc-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
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

    lines.append(f"## {get_translation('mcp_details', language)} {{.doc-parameters}}")
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
            f"## {get_translation('mcp_template_variables', language)} {{.doc-parameters}}"
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
    lines.append("body-classes: doc-api-page")
    lines.append("sidebar: mcp-reference")
    lines.append("page-navigation: false")
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
        lines.append(f"## {get_translation('mcp_arguments', language)} {{.doc-parameters}}")
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
        lines.append(f"## {get_translation('mcp_prompt_text', language)}")
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
        at ``output_dir/.well-known/mcp.json``.
    package_name
        The pip-installable package name (e.g., "great-docs").
    repo_url
        Repository URL (e.g., "https://github.com/posit-dev/great-docs").
    site_url
        Canonical documentation site URL.
    install_command
        Custom install command. Defaults to ``pip install {package_name}[mcp]``.

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
