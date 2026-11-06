"""Great Docs MCP Server — Exposes documentation operations as MCP tools.

Allows AI agents (Claude Desktop, VS Code Copilot, Cursor, etc.) to drive
Great Docs documentation workflows through the Model Context Protocol.

Usage:
    great-docs serve --mcp    # Via CLI (future)
    python -m great_docs.mcp  # Directly
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Completion,
    CompletionArgument,
    CompletionContext,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    PromptReference,
    Resource,
    ResourceTemplate,
    ResourceTemplateReference,
    TextContent,
    Tool,
)

from ._build import outputs
from ._build.steps import USER_CODE_ERRORS, BuildError
from ._content import user_guide
from ._layout import CONVENTIONAL_DOC_DIRS, Layout, LayoutError
from ._utils import is_in_great_docs_build_dir, recognised_build_dirs

if TYPE_CHECKING:
    from ._api_diff import ApiSnapshot
    from ._project import Project
    from ._reference.exports import Exports

# Server-level instructions — displayed to the AI at connection time
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

# Project failures produce failed tool results, resource error text or no completion
# suggestions. These include invalid configuration or layout (`ValueError`), file
# access errors, package import or loading errors, and build failures (`BuildError`
# inherits from `RuntimeError`). Other exceptions propagate as protocol errors.
_PROJECT_ERRORS: tuple[type[Exception], ...] = (*USER_CODE_ERRORS, ValueError)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_root(project_path: str | None = None) -> Path:
    """Resolve the project root directory."""
    if project_path:
        p = Path(project_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Project path does not exist: {p}")
        return p
    return Path.cwd()


def _sibling_build_dirs(root: Path, layout: Layout | None = None) -> list[Path]:
    """
    Return historical Great Docs build directories under `root`

    Include only directories whose `_quarto.yml` contains the Great Docs
    marker. Ignore symlinks and unmarked matches because they may contain user
    files.

    Parameters
    ----------
    root
        Project root containing the build directories.

    Returns
    -------
    Marked sibling directories in name order.
    """
    return recognised_build_dirs(layout or Layout.make(root))


def _build_output_dirs(root: Path, layout: Layout | None = None) -> list[Path]:
    """
    Return all Great Docs build directories under `root`

    The current `great-docs/` directory comes first, when present, followed by
    marked historical sibling directories in name order.

    Parameters
    ----------
    root
        Project root containing the build directories.

    Returns
    -------
    Current and historical build directories.
    """
    layout = layout or Layout.make(root)
    current = (
        [layout.build_dir]
        if layout.build_dir.is_dir() and not layout.build_dir.is_symlink()
        else []
    )
    return current + _sibling_build_dirs(root, layout)


def _get_great_docs(
    project_path: str | None = None, config_path: str | None = None, *, create: bool = False
) -> Any:
    """Resolve the selected documentation project"""
    from .core import GreatDocs

    return GreatDocs(project_path=project_path, config_path=config_path, create=create)


def _get_exports(project_path: str | None, config_path: str | None) -> Exports:
    """
    Prepare export discovery for the selected project

    Read the configuration and packaging files now; load packages and discover exports
    when requested.

    Parameters
    ----------
    project_path
        The project directory, or `None` to use the current directory.
    config_path
        The configuration file, or `None` to locate it within the project.

    Returns
    -------
    :
        An export discovery object for the selected project.
    """
    from ._reference.exports import Exports

    return Exports.make(
        Layout.make(
            Path(project_path) if project_path else Path.cwd(),
            Path(config_path) if config_path else None,
        )
    )


def _get_layout(arguments: dict, *, create: bool = False) -> Layout:
    """Resolve paths for a tool's project and configuration arguments"""
    config_path = arguments.get("config_path")
    return Layout.make(
        _get_project_root(arguments.get("project_path")),
        Path(config_path) if config_path else None,
        create=create,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------


class _ToolCallContent(list[TextContent]):
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
        result = _ToolCallContent([TextContent(type="text", text="\n".join(errors))])
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
            return await _handle_status(arguments)
        elif name == "gd_add_page":
            return await _handle_add_page(arguments)
        elif name == "gd_api_diff":
            return await _handle_api_diff(arguments)
        else:
            result = _ToolCallContent([TextContent(type="text", text=f"Unknown tool: {name}")])
            result.is_error = True
            return result
    except _PROJECT_ERRORS as e:
        result = _ToolCallContent([TextContent(type="text", text=f"Error: {e}")])
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
        for ver_dir in _sibling_build_dirs(_get_project_root(project_path), _get_layout(arguments)):
            shutil.rmtree(ver_dir)

    # Include the build log in both success and error responses
    output = io.StringIO()
    try:
        with redirect_stdout(output):
            docs.build()
    except BuildError as e:
        result = _ToolCallContent(
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
    layout = _get_layout(arguments)
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

    package_exports = _get_exports(project_path, arguments.get("config_path"))
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
    from ._checks.lint import run_lint

    project_path = arguments.get("project_path")
    checks_arg = arguments.get("checks")

    root = _get_project_root(project_path)
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

    layout = _get_layout(arguments, create=generate)
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


async def _handle_status(arguments: dict) -> list[TextContent]:
    """Show project documentation status."""
    project_path = arguments.get("project_path")
    root = _get_project_root(project_path)

    lines = [f"Project: {root.name}", f"Path: {root}", ""]

    # Config status
    layout = _get_layout(arguments)
    root = layout.package_root
    config_path = layout.config_path
    if config_path.exists():
        lines.append(f"Configuration: {config_path.relative_to(root)} ✓")
        exports = _get_exports(project_path, arguments.get("config_path"))
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
    build_dirs = _build_output_dirs(root, layout)
    if build_dirs:
        lines.append(f"Build output directories: {len(build_dirs)}")
        for d in build_dirs:
            lines.append(f"  - {d.name}")
    else:
        lines.append("Build output: none (run `gd_build` to generate)")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_add_page(arguments: dict) -> list[TextContent]:
    """Add a new documentation page."""
    project_path = arguments.get("project_path")
    title = arguments["title"]
    section = arguments.get("section", "user_guide")
    filename = arguments.get("filename")
    content = arguments.get("content", "")

    layout = _get_layout(arguments)
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
        f'title: "{title}"',
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
    from ._api_diff import snapshot_at_tag, snapshot_from_griffe

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
    from ._api_diff import diff_snapshots

    project_path = arguments.get("project_path")
    base_ref = arguments.get("base")
    head_ref = arguments.get("head")

    project = _get_exports(project_path, arguments.get("config_path")).project
    importable_name = project.importable_name
    if not project.name or not importable_name:
        return [TextContent(type="text", text="Error: Could not detect package name.")]

    if not base_ref and head_ref:
        return [TextContent(type="text", text="Provide a base ref to compare against.")]

    root = _get_layout(arguments).package_root
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


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


async def list_prompts() -> list[Prompt]:
    """List pre-built prompt templates for documentation workflows."""
    return [
        Prompt(
            name="setup-docs",
            description=(
                "Guide the user through setting up Great Docs for a new Python project. "
                "Scans the package, generates config, and runs an initial build."
            ),
            arguments=[
                PromptArgument(
                    name="project_path",
                    description="Path to the Python project root directory.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="write-user-guide",
            description=(
                "Help write a user guide page for a specific topic. Generates well-structured "
                "Quarto markdown with examples, cross-references, and proper frontmatter."
            ),
            arguments=[
                PromptArgument(
                    name="topic",
                    description="The topic or feature to document.",
                    required=True,
                ),
                PromptArgument(
                    name="audience",
                    description="Target audience level (beginner, intermediate, advanced).",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="debug-build",
            description=(
                "Diagnose and fix a Great Docs build failure. Reads the build log, "
                "identifies the error, and suggests fixes."
            ),
            arguments=[
                PromptArgument(
                    name="error_message",
                    description="The error message or symptom observed.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="improve-docstrings",
            description=(
                "Review and improve docstrings for a module or class. Ensures "
                "consistent style, complete parameter documentation, and useful examples."
            ),
            arguments=[
                PromptArgument(
                    name="symbol",
                    description="The module, class, or function name to improve.",
                    required=True,
                ),
                PromptArgument(
                    name="style",
                    description="Docstring style: numpy, google, or sphinx.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="api-changelog",
            description=(
                "Generate a changelog entry from API differences between two versions. "
                "Produces markdown suitable for a CHANGELOG or release notes."
            ),
            arguments=[
                PromptArgument(
                    name="base_version",
                    description="The base version to compare from (e.g., v0.9.0).",
                    required=False,
                ),
                PromptArgument(
                    name="head_version",
                    description="The target version to compare to (e.g., v0.10.0 or HEAD).",
                    required=False,
                ),
            ],
        ),
    ]


async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Return the expanded prompt messages for a given prompt template."""
    args = arguments or {}

    if name == "setup-docs":
        project = args.get("project_path", "the current directory")
        return GetPromptResult(
            description="Set up Great Docs for a Python project",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"I want to set up documentation for my Python project at {project}. "
                            "Please:\n"
                            "1. Use `gd_scan` to discover the package's public API\n"
                            "2. Use `gd_config` with generate=true to create a starter config\n"
                            "3. Use `gd_build` to run the initial build\n"
                            "4. Report what was documented and suggest next steps "
                            "(user guide pages, CLI docs, custom sections)"
                        ),
                    ),
                ),
            ],
        )

    elif name == "write-user-guide":
        topic = args.get("topic", "the feature")
        audience = args.get("audience", "intermediate")
        return GetPromptResult(
            description=f"Write a user guide page about: {topic}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Write a user guide page about '{topic}' for a {audience} audience.\n\n"
                            "Requirements:\n"
                            "- Use Quarto markdown (.qmd format)\n"
                            "- Start with a clear introduction explaining why this matters\n"
                            "- Include practical code examples with expected output\n"
                            "- Use cross-references to related API functions where relevant\n"
                            "- Add callout blocks (:::{.callout-tip}) for best practices\n"
                            "- End with a 'Next Steps' section linking to related pages\n\n"
                            "Use `gd_add_page` to create the page when done, "
                            "with section='user_guide'."
                        ),
                    ),
                ),
            ],
        )

    elif name == "debug-build":
        error = args.get("error_message", "")
        context = f" The error was: {error}" if error else ""
        return GetPromptResult(
            description="Debug a Great Docs build failure",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"My Great Docs build is failing.{context}\n\n"
                            "Please help me diagnose and fix it:\n"
                            "1. Read the `gd://build-log` resource for recent build output\n"
                            "2. Use `gd_status` to check project state\n"
                            "3. Use `gd_lint` to find configuration issues\n"
                            "4. Identify the root cause and provide a fix\n"
                            "5. Re-run `gd_build` to verify the fix works"
                        ),
                    ),
                ),
            ],
        )

    elif name == "improve-docstrings":
        symbol = args.get("symbol", "")
        style = args.get("style", "numpy")
        return GetPromptResult(
            description=f"Improve docstrings for: {symbol}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Review and improve the docstrings for `{symbol}` "
                            f"using {style} style.\n\n"
                            "Check for:\n"
                            "- Missing parameter descriptions\n"
                            "- Missing return type documentation\n"
                            "- Missing or outdated examples\n"
                            "- Inconsistent style with the rest of the project\n"
                            "- Opportunities to add cross-references (e.g., 'See Also')\n\n"
                            "Use `gd_scan` to see the full API surface, then "
                            "use `gd_lint` with checks=['docstrings'] to validate your changes."
                        ),
                    ),
                ),
            ],
        )

    elif name == "api-changelog":
        base = args.get("base_version", "the previous release")
        head = args.get("head_version", "HEAD")
        return GetPromptResult(
            description=f"Generate changelog: {base} → {head}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Generate a changelog entry for changes between {base} and {head}.\n\n"
                            "Steps:\n"
                            f"1. Use `gd_api_diff` with base='{base}' to get API changes\n"
                            "2. Categorize changes into: Added, Changed, Deprecated, Removed, Fixed\n"
                            "3. Write a markdown changelog entry with:\n"
                            "   - A summary paragraph describing the release theme\n"
                            "   - Categorized bullet points for each change\n"
                            "   - Migration notes for any breaking changes\n"
                            "   - Links to relevant documentation pages"
                        ),
                    ),
                ),
            ],
        )

    else:
        return GetPromptResult(
            description="Unknown prompt",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=f"Unknown prompt: {name}"),
                ),
            ],
        )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


async def list_resources() -> list[Resource]:
    """List available documentation resources."""
    resources = []
    root = Path.cwd()

    # Configuration file
    try:
        config_path = Layout.make(root).config_path
    except LayoutError:
        config_path = None
    if config_path is not None and config_path.exists():
        resources.append(
            Resource(
                name="configuration",
                uri="gd://config",
                description="Current Great Docs configuration (great-docs.yml).",
                mimeType="text/yaml",
            )
        )

    # Build log
    resources.append(
        Resource(
            name="build-log",
            uri="gd://build-log",
            description=(
                "Most recent build log output. Shows step-by-step build progress, "
                "warnings, and errors."
            ),
            mimeType="text/plain",
        )
    )

    # API surface
    resources.append(
        Resource(
            name="api-surface",
            uri="gd://api-surface",
            description=(
                "Discovered public API exports for the current package. "
                "Lists classes, functions, constants, and their categorization."
            ),
            mimeType="text/plain",
        )
    )

    # Project status
    resources.append(
        Resource(
            name="project-status",
            uri="gd://status",
            description=(
                "Current project documentation status: package info, "
                "configuration state, build artifacts, and enabled features."
            ),
            mimeType="text/plain",
        )
    )

    # Pyproject.toml
    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        resources.append(
            Resource(
                name="pyproject",
                uri="gd://pyproject",
                description="Project metadata from pyproject.toml.",
                mimeType="text/plain",
            )
        )

    return resources


async def read_resource(uri: str) -> str:
    """
    Read a documentation resource from a `gd://` URI

    The `project_path` and `config_path` query parameters select the project and
    configuration as they do for tool calls. Without these parameters, use
    automatic project configuration discovery.

    Parameters
    ----------
    uri
        The resource URI, including any project and configuration query parameters.

    Returns
    -------
    :
        The resource content or a message describing an unavailable resource.
    """
    parts = urlsplit(uri)
    uri_str = parts._replace(query="").geturl()
    query = parse_qs(parts.query)
    arguments = {name: query[name][0] for name in ("project_path", "config_path") if name in query}
    root = _get_project_root(arguments.get("project_path"))

    if uri_str == "gd://config":
        config_path = _get_layout(arguments).config_path
        if not config_path.exists():
            return "# No great-docs.yml found.\n# Run `gd_config` with generate=true to create one."
        return config_path.read_text(encoding="utf-8")

    elif uri_str == "gd://build-log":
        build_dirs = _build_output_dirs(root, _get_layout(arguments))
        if build_dirs:
            names = ", ".join(d.name for d in build_dirs)
            return (
                f"Build output directories: {names}\n"
                "Great Docs prints logs during the build and does not save them to a file."
            )
        return "No build output found. Run `gd_build` to generate documentation."

    elif uri_str == "gd://api-surface":
        try:
            package_exports = _get_exports(
                arguments.get("project_path"), arguments.get("config_path")
            )
            project = package_exports.project
            importable_name = project.importable_name
            if not project.name or not importable_name:
                return "Error: Could not detect package name."
            exports = package_exports.names(importable_name)
            if not exports:
                return f"No exports discovered for {importable_name}."
            categories = package_exports.categorise(importable_name, exports)

            lines = [f"Package: {importable_name}", f"Total exports: {len(exports)}", ""]
            for cat_key, label in [
                ("classes", "Classes"),
                ("dataclasses", "Dataclasses"),
                ("functions", "Functions"),
                ("async_functions", "Async Functions"),
                ("constants", "Constants"),
                ("enums", "Enumerations"),
                ("exceptions", "Exceptions"),
                ("type_aliases", "Type Aliases"),
            ]:
                items = categories.get(cat_key)
                if items:
                    lines.append(f"## {label}")
                    for item in items:
                        lines.append(f"  - {item}")
                    lines.append("")
            return "\n".join(lines)
        except _PROJECT_ERRORS as e:
            return f"Error discovering API surface: {e}"

    elif uri_str == "gd://status":
        result = await _handle_status(arguments)
        return result[0].text

    elif uri_str == "gd://pyproject":
        pyproject_path = root / "pyproject.toml"
        if not pyproject_path.exists():
            return "# No pyproject.toml found."
        return pyproject_path.read_text(encoding="utf-8")

    elif uri_str.startswith("gd://reference/"):
        # Dynamic reference page resource (from template)
        symbol = uri_str.removeprefix("gd://reference/")
        try:
            importable_name = _get_exports(
                arguments.get("project_path"), arguments.get("config_path")
            ).project.importable_name
            if not importable_name:
                return "Error: Could not detect package name."
            # Try to get docstring for the symbol
            import importlib

            mod = importlib.import_module(importable_name)
            obj = getattr(mod, symbol, None)
            if obj is None:
                return f"Symbol '{symbol}' not found in {importable_name}."
            doc = getattr(obj, "__doc__", None) or "No docstring available."
            kind = type(obj).__name__
            return f"# {importable_name}.{symbol}\nKind: {kind}\n\n{doc}"
        except _PROJECT_ERRORS as e:
            return f"Error reading reference for '{symbol}': {e}"

    elif uri_str.startswith("gd://page/"):
        # Dynamic page content (from template)
        page_path = uri_str.removeprefix("gd://page/")
        target = root / page_path
        if not target.exists():
            return f"Page not found: {page_path}"
        return target.read_text(encoding="utf-8")

    else:
        return f"Unknown resource URI: {uri_str}"


# ---------------------------------------------------------------------------
# Resource Templates
# ---------------------------------------------------------------------------


async def list_resource_templates() -> list[ResourceTemplate]:
    """List dynamic resource templates."""
    return [
        *[
            ResourceTemplate(
                name=f"selected-{resource}",
                uriTemplate=f"gd://{resource}{{?project_path,config_path}}",
                description=f"Read {description}. Select a configuration with config_path when automatic discovery is ambiguous or a custom path is used.",
                mimeType="text/yaml" if resource == "config" else "text/plain",
            )
            for resource, description in (
                ("config", "the project configuration"),
                ("api-surface", "the selected package's public API"),
                ("status", "the selected documentation project's status"),
                ("build-log", "the selected documentation project's build output locations"),
            )
        ],
        ResourceTemplate(
            name="reference-symbol",
            uriTemplate="gd://reference/{symbol}{?project_path,config_path}",
            description=(
                "Read documentation for a specific API symbol. "
                "Returns the symbol's kind, module path, and docstring."
            ),
            mimeType="text/plain",
        ),
        ResourceTemplate(
            name="doc-page",
            uriTemplate="gd://page/{path}{?project_path,config_path}",
            description=(
                "Read the source content of any documentation page (.qmd file). "
                "Path is relative to the project root (e.g., 'user_guide/getting-started.qmd')."
            ),
            mimeType="text/plain",
        ),
    ]


# ---------------------------------------------------------------------------
# Completions
# ---------------------------------------------------------------------------


async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: CompletionContext | None = None,
) -> Completion | None:
    """
    Suggest values for prompt and resource template arguments

    Parameters
    ----------
    ref
        The prompt or resource template to complete.
    argument
        The argument name and partial value to complete.
    context
        Previously supplied arguments, including any project and configuration
        selection. Omit to use the default project configuration discovery.

    Returns
    -------
    :
        Matching suggestions, or `None` for an unsupported completion or a
        handled project error.
    """
    value = argument.value or ""
    arguments = (context.arguments if context else None) or {}

    # Prompt argument completions
    if isinstance(ref, PromptReference):
        if ref.name == "write-user-guide" and argument.name == "audience":
            options = ["beginner", "intermediate", "advanced"]
            filtered = [o for o in options if o.startswith(value.lower())]
            return Completion(values=filtered)

        if ref.name == "write-user-guide" and argument.name == "topic":
            # Suggest common doc topics
            topics = [
                "getting-started",
                "installation",
                "configuration",
                "theming",
                "deployment",
                "custom-pages",
                "API reference",
                "CLI usage",
                "multi-version docs",
            ]
            filtered = [t for t in topics if value.lower() in t.lower()]
            return Completion(values=filtered[:10])

        if ref.name == "improve-docstrings" and argument.name == "style":
            options = ["numpy", "google", "sphinx"]
            filtered = [o for o in options if o.startswith(value.lower())]
            return Completion(values=filtered)

        if ref.name == "improve-docstrings" and argument.name == "symbol":
            # Complete with actual package symbols
            try:
                package_exports = _get_exports(
                    arguments.get("project_path"), arguments.get("config_path")
                )
                importable_name = package_exports.project.importable_name
                if not importable_name:
                    return Completion(values=[])
                exports = package_exports.names(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except _PROJECT_ERRORS:
                return None

        if argument.name == "project_path":
            # Suggest current directory
            return Completion(values=[str(Path.cwd())])

        if argument.name == "config_path":
            root = _get_project_root(arguments.get("project_path"))
            paths = [root / "great-docs.yml"] + [
                root / name / "great-docs.yml" for name in CONVENTIONAL_DOC_DIRS
            ]
            return Completion(
                values=[str(path) for path in paths if path.is_file() and value in str(path)]
            )

    # Resource template completions
    if isinstance(ref, ResourceTemplateReference):
        if "reference" in str(ref.uri) and argument.name == "symbol":
            try:
                package_exports = _get_exports(
                    arguments.get("project_path"), arguments.get("config_path")
                )
                importable_name = package_exports.project.importable_name
                if not importable_name:
                    return Completion(values=[])
                exports = package_exports.names(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except _PROJECT_ERRORS:
                return None

        if "page" in str(ref.uri) and argument.name == "path":
            # List source pages without their generated build copies.
            layout = _get_layout(arguments)
            root = layout.package_root
            rel_paths = (p.relative_to(root) for p in layout.source_dir.rglob("*.qmd"))
            qmd_files = sorted(
                str(rel)
                for rel in rel_paths
                if not is_in_great_docs_build_dir(rel.parts, root, layout)
            )
            filtered = [f for f in qmd_files if value.lower() in f.lower()]
            return Completion(values=filtered[:20], hasMore=len(filtered) > 20)

    return None


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

# MCP validates request parameters before these adapters run. The adapters wrap
# handler output in protocol result models and preserve tool failure status.
from mcp.server.context import ServerRequestContext
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    CompleteRequestParams,
    CompleteResult,
    GetPromptRequestParams,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    TextResourceContents,
)


async def _on_list_tools(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListToolsResult:
    return ListToolsResult(tools=await list_tools())


async def _on_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    content = await call_tool(params.name, params.arguments or {})
    return CallToolResult(
        content=list(content),
        is_error=isinstance(content, _ToolCallContent) and content.is_error,
    )


async def _on_list_prompts(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListPromptsResult:
    return ListPromptsResult(prompts=await list_prompts())


async def _on_get_prompt(
    ctx: ServerRequestContext, params: GetPromptRequestParams
) -> GetPromptResult:
    return await get_prompt(params.name, params.arguments)


async def _on_list_resources(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListResourcesResult:
    return ListResourcesResult(resources=await list_resources())


async def _on_read_resource(
    ctx: ServerRequestContext, params: ReadResourceRequestParams
) -> ReadResourceResult:
    text = await read_resource(params.uri)
    return ReadResourceResult(contents=[TextResourceContents(uri=params.uri, text=text)])


async def _on_list_resource_templates(
    ctx: ServerRequestContext, params: PaginatedRequestParams | None
) -> ListResourceTemplatesResult:
    return ListResourceTemplatesResult(resource_templates=await list_resource_templates())


async def _on_completion(
    ctx: ServerRequestContext, params: CompleteRequestParams
) -> CompleteResult:
    completion = await handle_completion(params.ref, params.argument, params.context)
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


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


async def run_mcp_server() -> None:
    """Run the Great Docs MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_mcp_server())
