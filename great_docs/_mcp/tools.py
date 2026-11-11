"""Documentation tool schemas, validation and handlers"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator
from mcp.types import (
    TextContent,
    Tool,
)

from .._build import outputs
from .._build.steps import BuildError
from .._content import user_guide

if TYPE_CHECKING:
    from .._api_evolution.model import ApiSnapshot
    from .._project import Project

from . import context as _context


def _get_great_docs(
    project_path: str | None = None, config_path: str | None = None, *, create: bool = False
) -> Any:
    """Resolve the selected documentation project"""
    from ..core import GreatDocs

    return GreatDocs(project_path=project_path, config_path=config_path, create=create)


async def list_tools() -> list[Tool]:
    """List all available Great Docs tools."""
    tools = [
        Tool(
            name="gd_build",
            description=(
                "Build documentation for a Python package. Runs the full Great Docs "
                "pipeline: API discovery, page generation, Quarto rendering."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": (
                            "Path to the project root directory. "
                            "Defaults to the current working directory."
                        ),
                    },
                    "clean": {
                        "type": "boolean",
                        "description": "Remove previous build artifacts before building.",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="gd_preview",
            description=(
                "Start a local preview server for the documentation site. "
                "Returns the URL where the site is accessible."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "port": {
                        "type": "integer",
                        "description": "Port for the preview server.",
                        "default": 3000,
                    },
                },
            },
        ),
        Tool(
            name="gd_scan",
            description=(
                "Discover package exports and preview what can be documented. "
                "Shows classes, functions, constants, and other public API members. "
                "Indicates which items are already configured in the reference section."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Include method names for each class.",
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="gd_lint",
            description=(
                "Lint docstrings and documentation configuration for issues. "
                "Checks for missing docstrings, inconsistent styles, broken "
                "cross-references, and stale version markers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "checks": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "docstrings",
                                "cross-refs",
                                "style",
                                "directives",
                                "stale-versions",
                            ],
                        },
                        "description": ("Specific checks to run. If omitted, all checks are run."),
                    },
                },
            },
        ),
        Tool(
            name="gd_config",
            description=(
                "Show the current Great Docs configuration for a project, "
                "or generate a starter configuration file (great-docs.yml)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "generate": {
                        "type": "boolean",
                        "description": (
                            "Generate a starter great-docs.yml file. "
                            "If false, shows the current effective configuration."
                        ),
                        "default": False,
                    },
                },
            },
        ),
        Tool(
            name="gd_status",
            description=(
                "Show current project documentation status: detected package, "
                "configuration state, build artifacts, and available features."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                },
            },
        ),
        Tool(
            name="gd_add_page",
            description=(
                "Add a new documentation page (user guide, tutorial, or custom page). "
                "Creates the .qmd file with proper frontmatter and registers it in navigation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Page title.",
                    },
                    "section": {
                        "type": "string",
                        "enum": ["user_guide", "recipes", "custom"],
                        "description": "Which section to add the page to.",
                        "default": "user_guide",
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Filename for the page (without extension). "
                            "Auto-generated from title if omitted."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "Initial page content (Quarto markdown). Optional.",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="gd_api_diff",
            description=(
                "Compare the public API between two versions of the package. "
                "Shows added, removed, and changed symbols (classes, functions, parameters)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project root directory.",
                    },
                    "base": {
                        "type": "string",
                        "description": (
                            "Base version/ref to compare from (git tag, branch, or commit). "
                            "Without it, the tool lists the current API surface."
                        ),
                    },
                    "head": {
                        "type": "string",
                        "description": (
                            "Head version/ref to compare to. Defaults to current working tree."
                        ),
                    },
                },
            },
        ),
    ]

    for tool in tools:
        schema = tool.input_schema
        schema["properties"]["config_path"] = {
            "type": "string",
            "description": "Configuration file path. Relative paths use the server's current working directory.",
        }
    return tools


class ToolCallContent(list[TextContent]):
    """list[TextContent] that also carries whether the call ended in error.

    call_tool() is tested directly as a plain list of TextContent, so this
    stays a list subclass; is_error just rides along for callers that check.
    """

    is_error: bool = False


async def _argument_errors(name: str, arguments: dict[str, Any]) -> list[str]:
    """
    List violations of a tool's input schema

    MCP validates request parameters but does not check tool arguments against
    the tool's schema. Report argument errors before dispatch so clients receive
    a failed tool result they can correct. Allow arguments the schema does not
    declare.

    Parameters
    ----------
    name
        The tool name.
    arguments
        The supplied argument names and values.

    Returns
    -------
    :
        One message listing any missing required arguments in schema order,
        followed by one message per other schema violation. Each later message
        names the argument or list item, such as `checks` or `checks[1]`.
        The list is empty for valid arguments or an unknown tool.
    """
    schema = next((tool.input_schema for tool in await list_tools() if tool.name == name), None)
    if schema is None:
        return []
    errors: list[str] = []
    required: list[str] = schema.get("required", [])
    if missing := [argument for argument in required if argument not in arguments]:
        errors.append(f"Error: missing required argument: {', '.join(missing)}")
    for error in Draft202012Validator(schema).iter_errors(arguments):
        if error.validator == "required" and not error.absolute_path:
            continue
        path = "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
        )
        errors.append(f"Error: invalid argument {path.removeprefix('.')}: {error.message}")
    return errors


async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Run a tool and return its text output

    Parameters
    ----------
    name
        The tool name.
    arguments
        The supplied argument names and values.

    Returns
    -------
    :
        The tool output. Unknown tools, invalid arguments and handled
        project errors return error text with `is_error=True`.
    """
    if errors := await _argument_errors(name, arguments):
        result = ToolCallContent([TextContent(type="text", text="\n".join(errors))])
        result.is_error = True
        return result
    try:
        if name == "gd_build":
            return await _handle_build(arguments)
        elif name == "gd_preview":
            return await _handle_preview(arguments)
        elif name == "gd_scan":
            return await _handle_scan(arguments)
        elif name == "gd_lint":
            return await _handle_lint(arguments)
        elif name == "gd_config":
            return await _handle_config(arguments)
        elif name == "gd_status":
            return await handle_status(arguments)
        elif name == "gd_add_page":
            return await _handle_add_page(arguments)
        elif name == "gd_api_diff":
            return await _handle_api_diff(arguments)
        else:
            result = ToolCallContent([TextContent(type="text", text=f"Unknown tool: {name}")])
            result.is_error = True
            return result
    except _context.REPORTED_ERRORS as e:
        result = ToolCallContent([TextContent(type="text", text=f"Error: {e}")])
        result.is_error = True
        return result


async def _handle_build(arguments: dict) -> list[TextContent]:
    """Build documentation."""
    import io
    from contextlib import redirect_stdout

    project_path = arguments.get("project_path")
    clean = arguments.get("clean", False)

    docs = _get_great_docs(project_path, arguments.get("config_path"))

    if clean:
        import shutil

        outputs.validate(
            docs.layout.load_config(),
            docs.layout,
        )
        for ver_dir in _context.sibling_build_dirs(
            _context.get_project_root(project_path), _context.get_layout(arguments)
        ):
            shutil.rmtree(ver_dir)

    # Include the build log in both success and error responses
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            docs.build()
    except BuildError as e:
        result = ToolCallContent(
            [TextContent(type="text", text=f"Build failed: {e}\n\n{output.getvalue()}")]
        )
        result.is_error = True
        return result

    return [TextContent(type="text", text=f"Build complete.\n\n{output.getvalue()}")]


async def _handle_preview(arguments: dict) -> list[TextContent]:
    """Start preview server."""
    project_path = arguments.get("project_path")
    port = arguments.get("port", 3000)

    # Check if build output exists
    layout = _context.get_layout(arguments)
    build_dir = layout.build_dir
    if not build_dir.exists():
        return [
            TextContent(
                type="text",
                text=(
                    "No build output found. Run `gd_build` first, "
                    "then use `gd_preview` to serve the site."
                ),
            )
        ]

    command = shlex.join(
        [
            "great-docs",
            "preview",
            "--project-path",
            str(layout.package_root),
            "--config",
            str(layout.config_path),
            "--port",
            str(port),
        ]
    )
    return [
        TextContent(
            type="text",
            text=(
                f"Preview server can be started with:\n"
                f"  {command}\n\n"
                f"Build directory: {build_dir}\n"
                f"The site will be available at http://localhost:{port}/"
            ),
        )
    ]


async def _handle_scan(arguments: dict) -> list[TextContent]:
    """Discover package exports."""
    project_path = arguments.get("project_path")
    verbose = arguments.get("verbose", False)

    package_exports = _context.get_exports(project_path, arguments.get("config_path"))
    project = package_exports.project
    importable_name = project.importable_name
    if not project.name or not importable_name:
        return [TextContent(type="text", text="Error: Could not detect package name.")]

    exports = package_exports.names(importable_name)
    if not exports:
        return [TextContent(type="text", text="No exports discovered.")]

    categories = package_exports.categorise(importable_name, exports)

    # Build structured output
    lines = [f"Package: {importable_name}", f"Total exports: {len(exports)}", ""]

    # Reference config status
    reference_config = package_exports.config.reference
    ref_items = set()
    for section in reference_config:
        for item in section.get("contents", []):
            if isinstance(item, str):
                ref_items.add(item)
            elif isinstance(item, dict):
                ref_items.add(item.get("name", ""))

    # Class-like categories
    for cat_key, label in [
        ("classes", "Classes"),
        ("dataclasses", "Dataclasses"),
        ("abstract_classes", "Abstract Classes"),
        ("protocols", "Protocols"),
    ]:
        cat_items = categories.get(cat_key)
        if cat_items:
            lines.append(f"## {label}")
            for class_name in cat_items:
                marker = "[x]" if class_name in ref_items else "[ ]"
                lines.append(f"  {marker} {class_name}")
                if verbose:
                    methods = categories.get("class_method_names", {}).get(class_name, [])
                    for method in methods:
                        full = f"{class_name}.{method}"
                        m = "[x]" if full in ref_items else "[ ]"
                        lines.append(f"      {m} {full}")
            lines.append("")

    # Flat categories
    for cat_key, label in [
        ("enums", "Enumerations"),
        ("exceptions", "Exceptions"),
        ("functions", "Functions"),
        ("async_functions", "Async Functions"),
        ("constants", "Constants"),
        ("type_aliases", "Type Aliases"),
    ]:
        cat_items = categories.get(cat_key)
        if cat_items:
            lines.append(f"## {label}")
            for name in cat_items:
                marker = "[x]" if name in ref_items else "[ ]"
                lines.append(f"  {marker} {name}")
            lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_lint(arguments: dict) -> list[TextContent]:
    """Run documentation lint checks."""
    from .._checks.lint import run_lint

    project_path = arguments.get("project_path")
    checks_arg = arguments.get("checks")

    root = _context.get_project_root(project_path)
    checks = set(checks_arg) if checks_arg else None

    result = run_lint(root, checks=checks, quiet=True, config_path=arguments.get("config_path"))

    if not result.issues:
        return [TextContent(type="text", text="No lint issues found. Documentation looks good!")]

    lines = [f"Found {len(result.issues)} issue(s):", ""]
    for issue in result.issues:
        severity = issue.severity.upper()
        symbol = f" ({issue.symbol})" if issue.symbol else ""
        lines.append(f"[{severity}] {issue.check}{symbol}: {issue.message}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_config(arguments: dict) -> list[TextContent]:
    """Show or generate configuration."""
    project_path = arguments.get("project_path")
    generate = arguments.get("generate", False)

    layout = _context.get_layout(arguments, create=generate)
    config_path = layout.config_path

    if generate:
        if config_path.exists():
            return [
                TextContent(
                    type="text",
                    text=f"Configuration already exists at {config_path}. Delete it first to regenerate.",
                )
            ]

        docs = _get_great_docs(project_path, arguments.get("config_path"), create=True)
        docs.install(force=True)
        return [
            TextContent(
                type="text",
                text=f"Generated configuration at {config_path}.",
            )
        ]

    # Show current config
    if not config_path.exists():
        return [
            TextContent(
                type="text",
                text=(
                    "No great-docs.yml found. Use `gd_config` with generate=true "
                    "to create one, or run `great-docs init`."
                ),
            )
        ]

    content = config_path.read_text(encoding="utf-8")
    return [TextContent(type="text", text=f"```yaml\n{content}\n```")]


async def handle_status(arguments: dict) -> list[TextContent]:
    """Show project documentation status."""
    project_path = arguments.get("project_path")
    root = _context.get_project_root(project_path)

    lines = [f"Project: {root.name}", f"Path: {root}", ""]

    # Config status
    layout = _context.get_layout(arguments)
    root = layout.package_root
    config_path = layout.config_path
    if config_path.exists():
        lines.append(f"Configuration: {config_path.relative_to(root)} ✓")
        exports = _context.get_exports(project_path, arguments.get("config_path"))
        pkg = exports.project.name
        if pkg:
            lines.append(f"Package: {pkg}")

        # Check features
        cfg = exports.config
        features = []
        if cfg.cli_enabled:
            features.append("CLI docs")
        if cfg.mcp_enabled:
            features.append("MCP docs")
        if cfg["user_guide"]:
            features.append("User Guide")
        if cfg.sections:
            features.append(f"{len(cfg.sections)} custom section(s)")
        if cfg["versions"]:
            features.append("Multi-version")
        if features:
            lines.append(f"Features: {', '.join(features)}")
    else:
        lines.append("Configuration: not initialized")
        lines.append("Run `gd_config` with generate=true to get started.")

    # Build status
    lines.append("")
    build_dirs = _context.build_output_dirs(root, layout)
    if build_dirs:
        lines.append(f"Build output directories: {len(build_dirs)}")
        for d in build_dirs:
            lines.append(f"  - {d.name}")
    else:
        lines.append("Build output: none (run `gd_build` to generate)")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_add_page(arguments: dict) -> list[TextContent]:
    """Add a new documentation page."""
    from yaml12 import format_yaml

    project_path = arguments.get("project_path")
    title = arguments["title"]
    section = arguments.get("section", "user_guide")
    filename = arguments.get("filename")
    content = arguments.get("content", "")

    layout = _context.get_layout(arguments)
    root = layout.source_dir

    # Derive filename from title if not provided
    if not filename:
        filename = title.lower().replace(" ", "-").replace("_", "-")
        # Remove non-alphanumeric chars except hyphens
        filename = "".join(c for c in filename if c.isalnum() or c == "-")

    # Determine target directory
    if section == "user_guide":
        config = layout.load_config()
        # A configured directory that does not exist yet receives the page
        target_dir = user_guide.find_dir(config, layout, report=lambda _: None) or root / (
            config.user_guide_dir or "user_guide"
        )
    elif section == "recipes":
        target_dir = root / "recipes"
    else:
        target_dir = root / "custom"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{filename}.qmd"

    if target_file.exists():
        return [TextContent(type="text", text=f"Page already exists: {target_file}")]

    # Build page content
    page_lines = [
        "---",
        format_yaml({"title": title}).rstrip(),
        "---",
        "",
    ]
    if content:
        page_lines.append(content)
        page_lines.append("")

    target_file.write_text("\n".join(page_lines), encoding="utf-8")

    return [
        TextContent(
            type="text",
            text=f"Created page: {target_file.relative_to(root)}\nTitle: {title}",
        )
    ]


def _api_snapshot(
    project: Project, importable_name: str, root: Path, ref: str | None
) -> ApiSnapshot | None:
    """
    Capture the project's public API from a git ref or the working tree

    Parameters
    ----------
    project
        The documented project.
    importable_name
        Importable name of the project's package.
    root
        Git repository containing the project.
    ref
        Git tag, branch or commit; `None` and `HEAD` select the working tree.

    Returns
    -------
    :
        The snapshot, or `None` when the package source cannot be read at `ref`.
    """
    from .._api_evolution.snapshot import snapshot_at_tag, snapshot_from_griffe

    if ref is None or ref.upper() == "HEAD":
        # Read the project source even when the package is uninstalled.
        search_paths = [str(path) for path in project.search_paths()]
        return snapshot_from_griffe(importable_name, version="HEAD", search_paths=search_paths)
    return snapshot_at_tag(root, ref, importable_name)


async def _handle_api_diff(arguments: dict) -> list[TextContent]:
    """
    List the current public API or compare API snapshots

    Omit both refs to list the working tree's API. Supply `base` to compare
    that ref with the working tree or an explicit `head` ref.

    Parameters
    ----------
    arguments
        Tool arguments selecting the project and optional `base` and `head` refs.

    Returns
    -------
    :
        MCP text responses containing the API listing, comparison or error message.
    """
    from .._api_evolution.compare import diff_snapshots

    project_path = arguments.get("project_path")
    base_ref = arguments.get("base")
    head_ref = arguments.get("head")

    project = _context.get_exports(project_path, arguments.get("config_path")).project
    importable_name = project.importable_name
    if not project.name or not importable_name:
        return [TextContent(type="text", text="Error: Could not detect package name.")]

    if not base_ref and head_ref:
        return [TextContent(type="text", text="Provide a base ref to compare against.")]

    root = _context.get_layout(arguments).package_root
    head = _api_snapshot(project, importable_name, root, head_ref)
    if head is not None and not base_ref:
        lines = [f"Current API surface for {importable_name}:", ""]
        for symbol in sorted(head.symbols):
            lines.append(f"  {head.symbols[symbol].kind}: {symbol}")
        return [TextContent(type="text", text="\n".join(lines))]

    base = _api_snapshot(project, importable_name, root, base_ref)
    if base is None or head is None:
        ref = base_ref if base is None else head_ref
        return [
            TextContent(
                type="text",
                text=(
                    f"Could not build an API snapshot at '{ref}'. Check that the ref exists "
                    "and the package source is present at it."
                ),
            )
        ]
    diff = diff_snapshots(base, head)

    lines = [f"API diff: {diff.old_version} → {diff.new_version}"]
    if diff.added:
        lines += ["", f"Added ({len(diff.added)}):"]
        lines.extend(f"  + {change.symbol}" for change in diff.added)
    if diff.removed:
        lines += ["", f"Removed ({len(diff.removed)}):"]
        lines.extend(f"  - {change.symbol}" for change in diff.removed)
    if diff.changed:
        lines += ["", f"Changed ({len(diff.changed)}):"]
        for change in diff.changed:
            lines.append(f"  ~ {change.symbol}")
            lines.extend(f"      {detail}" for detail in change.details)
    if not diff.added and not diff.removed and not diff.changed:
        lines += ["", "No API changes detected."]
    return [TextContent(type="text", text="\n".join(lines))]
