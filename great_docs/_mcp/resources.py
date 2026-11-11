"""Documentation resources and resource templates"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mcp.types import (
    Resource,
    ResourceTemplate,
)

from .._project.layout import Layout, LayoutError
from . import context as _context
from . import tools as _tools


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
    root = _context.get_project_root(arguments.get("project_path"))

    if uri_str == "gd://config":
        config_path = _context.get_layout(arguments).config_path
        if not config_path.exists():
            return "# No great-docs.yml found.\n# Run `gd_config` with generate=true to create one."
        return config_path.read_text(encoding="utf-8")

    elif uri_str == "gd://build-log":
        build_dirs = _context.build_output_dirs(root, _context.get_layout(arguments))
        if build_dirs:
            names = ", ".join(d.name for d in build_dirs)
            return (
                f"Build output directories: {names}\n"
                "Great Docs prints logs during the build and does not save them to a file."
            )
        return "No build output found. Run `gd_build` to generate documentation."

    elif uri_str == "gd://api-surface":
        try:
            package_exports = _context.get_exports(
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
        except _context.REPORTED_ERRORS as e:
            return f"Error discovering API surface: {e}"

    elif uri_str == "gd://status":
        result = await _tools.handle_status(arguments)
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
            importable_name = _context.get_exports(
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
        except _context.REPORTED_ERRORS as e:
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
