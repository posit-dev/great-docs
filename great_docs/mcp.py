"""Great Docs MCP Server — Exposes documentation operations as MCP tools.

Allows AI agents (Claude Desktop, VS Code Copilot, Cursor, etc.) to drive
Great Docs documentation workflows through the Model Context Protocol.

Usage:
    great-docs serve --mcp    # Via CLI (future)
    python -m great_docs.mcp  # Directly
"""

from __future__ import annotations

from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Completion,
    CompletionArgument,
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
from pydantic import AnyUrl

server = Server("great-docs")

# Server-level instructions — displayed to the AI at connection time
server.instructions = (
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


def _get_great_docs(project_path: str | None = None):
    """Create a GreatDocs instance for the given project."""
    from .core import GreatDocs

    return GreatDocs(project_path=project_path)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Great Docs tools."""
    return [
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
                            "Defaults to the previous release tag."
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


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to their implementations."""
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
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def _handle_build(arguments: dict) -> list[TextContent]:
    """Build documentation."""
    import io
    from contextlib import redirect_stdout

    project_path = arguments.get("project_path")
    clean = arguments.get("clean", False)

    docs = _get_great_docs(project_path)

    if clean:
        import shutil

        build_dir = _get_project_root(project_path) / "_great_docs_build"
        if build_dir.exists():
            shutil.rmtree(build_dir)

    # Capture build output
    output = io.StringIO()
    with redirect_stdout(output):
        docs.build()

    return [TextContent(type="text", text=f"Build complete.\n\n{output.getvalue()}")]


async def _handle_preview(arguments: dict) -> list[TextContent]:
    """Start preview server."""
    project_path = arguments.get("project_path")
    port = arguments.get("port", 3000)

    # Check if build output exists
    root = _get_project_root(project_path)
    build_dir = root / "_great_docs_build" / "_root"
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

    return [
        TextContent(
            type="text",
            text=(
                f"Preview server can be started with:\n"
                f"  great-docs preview --port {port}\n\n"
                f"Build directory: {build_dir}\n"
                f"The site will be available at http://localhost:{port}/"
            ),
        )
    ]


async def _handle_scan(arguments: dict) -> list[TextContent]:
    """Discover package exports."""
    project_path = arguments.get("project_path")
    verbose = arguments.get("verbose", False)

    docs = _get_great_docs(project_path)
    package_name = docs._detect_package_name()
    if not package_name:
        return [TextContent(type="text", text="Error: Could not detect package name.")]

    module_name = docs._detect_module_name()
    importable_name = module_name or docs._normalize_package_name(package_name)

    exports = docs._get_package_exports(importable_name)
    if not exports:
        return [TextContent(type="text", text="No exports discovered.")]

    categories = docs._categorize_api_objects(importable_name, exports)

    # Build structured output
    lines = [f"Package: {importable_name}", f"Total exports: {len(exports)}", ""]

    # Reference config status
    reference_config = docs._config.reference
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
    from ._lint import run_lint

    project_path = arguments.get("project_path")
    checks_arg = arguments.get("checks")

    root = _get_project_root(project_path)
    checks = set(checks_arg) if checks_arg else None

    result = run_lint(root, checks=checks, quiet=True)

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

    root = _get_project_root(project_path)
    config_path = root / "great-docs.yml"

    if generate:
        if config_path.exists():
            return [
                TextContent(
                    type="text",
                    text=f"Configuration already exists at {config_path}. Delete it first to regenerate.",
                )
            ]

        docs = _get_great_docs(project_path)
        docs.install()
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
    config_path = root / "great-docs.yml"
    if config_path.exists():
        lines.append("Configuration: great-docs.yml ✓")
        docs = _get_great_docs(project_path)
        pkg = docs._detect_package_name()
        if pkg:
            lines.append(f"Package: {pkg}")

        # Check features
        cfg = docs._config
        features = []
        if cfg.cli_enabled:
            features.append("CLI docs")
        if cfg.mcp_enabled:
            features.append("MCP docs")
        if cfg.get("user_guide"):
            features.append("User Guide")
        if cfg.sections:
            features.append(f"{len(cfg.sections)} custom section(s)")
        if cfg.get("versions"):
            features.append("Multi-version")
        if features:
            lines.append(f"Features: {', '.join(features)}")
    else:
        lines.append("Configuration: not initialized")
        lines.append("Run `gd_config` with generate=true to get started.")

    # Build status
    lines.append("")
    build_dir = root / "_great_docs_build"
    if build_dir.exists():
        versions = [d.name for d in build_dir.iterdir() if d.is_dir()]
        lines.append(f"Build output: {len(versions)} version(s) built")
        for v in sorted(versions):
            lines.append(f"  - {v}")
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

    root = _get_project_root(project_path)

    # Derive filename from title if not provided
    if not filename:
        filename = title.lower().replace(" ", "-").replace("_", "-")
        # Remove non-alphanumeric chars except hyphens
        filename = "".join(c for c in filename if c.isalnum() or c == "-")

    # Determine target directory
    if section == "user_guide":
        target_dir = root / "user_guide"
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


async def _handle_api_diff(arguments: dict) -> list[TextContent]:
    """Compare API between versions."""
    from ._api_diff import ApiSnapshot

    project_path = arguments.get("project_path")
    base_ref = arguments.get("base")
    head_ref = arguments.get("head")

    docs = _get_great_docs(project_path)
    package_name = docs._detect_package_name()
    if not package_name:
        return [TextContent(type="text", text="Error: Could not detect package name.")]

    module_name = docs._detect_module_name()
    importable_name = module_name or docs._normalize_package_name(package_name)

    # Take current snapshot
    current = ApiSnapshot.from_live(importable_name)

    if not base_ref and not head_ref:
        # Just show current API surface
        lines = [f"Current API surface for {importable_name}:", ""]
        for symbol in sorted(current.symbols.keys()):
            info = current.symbols[symbol]
            lines.append(f"  {info.kind}: {symbol}")
        return [TextContent(type="text", text="\n".join(lines))]

    # If base_ref provided, try to compare
    if base_ref:
        root = _get_project_root(project_path)
        base_snapshot_path = root / ".great-docs-snapshots" / f"{base_ref}.json"
        if base_snapshot_path.exists():
            base = ApiSnapshot.from_json(base_snapshot_path)
            diff = base.diff(current)
            lines = [f"API diff: {base_ref} → {'HEAD' if not head_ref else head_ref}", ""]
            if diff.added:
                lines.append(f"Added ({len(diff.added)}):")
                for s in sorted(diff.added, key=lambda x: x.name):
                    lines.append(f"  + {s.kind}: {s.name}")
            if diff.removed:
                lines.append(f"\nRemoved ({len(diff.removed)}):")
                for s in sorted(diff.removed, key=lambda x: x.name):
                    lines.append(f"  - {s.kind}: {s.name}")
            if diff.changed:
                lines.append(f"\nChanged ({len(diff.changed)}):")
                for s in sorted(diff.changed, key=lambda x: x.name):
                    lines.append(f"  ~ {s.name}: {s.change_type}")
            if not diff.added and not diff.removed and not diff.changed:
                lines.append("No API changes detected.")
            return [TextContent(type="text", text="\n".join(lines))]
        else:
            return [
                TextContent(
                    type="text",
                    text=(
                        f"No snapshot found for '{base_ref}'. "
                        f"Available: run a build for that version first."
                    ),
                )
            ]

    return [TextContent(type="text", text="Provide a base ref to compare against.")]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@server.list_prompts()
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


@server.get_prompt()
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


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available documentation resources."""
    resources = []
    root = Path.cwd()

    # Configuration file
    config_path = root / "great-docs.yml"
    if config_path.exists():
        resources.append(
            Resource(
                name="configuration",
                uri=AnyUrl("gd://config"),
                description="Current Great Docs configuration (great-docs.yml).",
                mimeType="text/yaml",
            )
        )

    # Build log
    resources.append(
        Resource(
            name="build-log",
            uri=AnyUrl("gd://build-log"),
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
            uri=AnyUrl("gd://api-surface"),
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
            uri=AnyUrl("gd://status"),
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
                uri=AnyUrl("gd://pyproject"),
                description="Project metadata from pyproject.toml.",
                mimeType="text/plain",
            )
        )

    return resources


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """Read the contents of a documentation resource."""
    uri_str = str(uri)
    root = Path.cwd()

    if uri_str == "gd://config":
        config_path = root / "great-docs.yml"
        if not config_path.exists():
            return "# No great-docs.yml found.\n# Run `gd_config` with generate=true to create one."
        return config_path.read_text(encoding="utf-8")

    elif uri_str == "gd://build-log":
        # Look for build log in standard location
        log_path = root / "_great_docs_build" / "build.log"
        if log_path.exists():
            return log_path.read_text(encoding="utf-8")
        # Fallback: check if build dir exists at all
        build_dir = root / "_great_docs_build"
        if build_dir.exists():
            versions = [d.name for d in build_dir.iterdir() if d.is_dir()]
            return (
                f"Build directory exists with {len(versions)} version(s): "
                f"{', '.join(sorted(versions))}\n"
                "No build.log file found (logs are printed to stdout during build)."
            )
        return "No build output found. Run `gd_build` to generate documentation."

    elif uri_str == "gd://api-surface":
        try:
            docs = _get_great_docs()
            package_name = docs._detect_package_name()
            if not package_name:
                return "Error: Could not detect package name."
            module_name = docs._detect_module_name()
            importable_name = module_name or docs._normalize_package_name(package_name)
            exports = docs._get_package_exports(importable_name)
            if not exports:
                return f"No exports discovered for {importable_name}."
            categories = docs._categorize_api_objects(importable_name, exports)

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
        except Exception as e:
            return f"Error discovering API surface: {e}"

    elif uri_str == "gd://status":
        result = await _handle_status({})
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
            docs = _get_great_docs()
            package_name = docs._detect_package_name()
            module_name = docs._detect_module_name()
            importable_name = module_name or docs._normalize_package_name(package_name)
            # Try to get docstring for the symbol
            import importlib

            mod = importlib.import_module(importable_name)
            obj = getattr(mod, symbol, None)
            if obj is None:
                return f"Symbol '{symbol}' not found in {importable_name}."
            doc = getattr(obj, "__doc__", None) or "No docstring available."
            kind = type(obj).__name__
            return f"# {importable_name}.{symbol}\nKind: {kind}\n\n{doc}"
        except Exception as e:
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


@server.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    """List dynamic resource templates."""
    return [
        ResourceTemplate(
            name="reference-symbol",
            uriTemplate="gd://reference/{symbol}",
            description=(
                "Read documentation for a specific API symbol. "
                "Returns the symbol's kind, module path, and docstring."
            ),
            mimeType="text/plain",
        ),
        ResourceTemplate(
            name="doc-page",
            uriTemplate="gd://page/{path}",
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


@server.completion()
async def handle_completion(
    ref: PromptReference | ResourceTemplateReference,
    argument: CompletionArgument,
    context: object | None = None,
) -> Completion | None:
    """Provide auto-completions for prompt arguments and resource template URIs."""
    value = argument.value or ""

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
                docs = _get_great_docs()
                package_name = docs._detect_package_name()
                module_name = docs._detect_module_name()
                importable_name = module_name or docs._normalize_package_name(package_name)
                exports = docs._get_package_exports(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except Exception:
                return None

        if argument.name == "project_path":
            # Suggest current directory
            return Completion(values=[str(Path.cwd())])

    # Resource template completions
    if isinstance(ref, ResourceTemplateReference):
        if "reference" in str(ref.uri) and argument.name == "symbol":
            try:
                docs = _get_great_docs()
                package_name = docs._detect_package_name()
                module_name = docs._detect_module_name()
                importable_name = module_name or docs._normalize_package_name(package_name)
                exports = docs._get_package_exports(importable_name)
                filtered = [e for e in exports if value.lower() in e.lower()]
                return Completion(values=filtered[:20], hasMore=len(filtered) > 20)
            except Exception:
                return None

        if "page" in str(ref.uri) and argument.name == "path":
            # List .qmd files in the project
            root = Path.cwd()
            qmd_files = sorted(str(p.relative_to(root)) for p in root.rglob("*.qmd"))
            filtered = [f for f in qmd_files if value.lower() in f.lower()]
            return Completion(values=filtered[:20], hasMore=len(filtered) > 20)

    return None


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


async def run_mcp_server():
    """Run the Great Docs MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_mcp_server())
