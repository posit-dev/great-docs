"""
Select an MCP server and publish its reference pages and discovery manifest
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from ..config import Config
from . import reference


def discover_server(config: Config, package: str | None) -> dict[str, Any] | None:
    """
    Find the configured MCP server or the first conventional module in a package

    Probing a conventional module imports the documented package.

    Parameters
    ----------
    config
        The documentation configuration.
    package
        The importable package name, when one is available.

    Returns
    -------
    :
        The server metadata, or `None` if no candidate is available.
    """
    module_path = config.mcp_module
    if not module_path and package:
        for candidate in (f"{package}.mcp", f"{package}.mcp_server", f"{package}.server"):
            try:
                _ = importlib.import_module(candidate)
            except ImportError:
                continue
            module_path = candidate
            break

    if not module_path:
        print("No MCP module configured or found")
        return None

    return reference.discover_mcp_server(
        module_path=module_path,
        server_var=config.mcp_server_var,
    )


def build_mcp_reference(
    config: Config,
    server_info: dict[str, Any],
    build_dir: Path,
    package_name: str | None,
    repo_url: str | None,
) -> list[str | dict[str, Any]]:
    """
    Write MCP reference pages and publish a manifest when pages exist

    Parameters
    ----------
    config
        The documentation configuration.
    server_info
        Metadata returned by MCP server discovery.
    build_dir
        The Quarto project directory.
    package_name
        The installable package name, when known.
    repo_url
        The repository URL, when known.

    Returns
    -------
    :
        Sidebar items for the generated reference pages.
    """
    files = reference.generate_mcp_reference_pages(
        server_info=server_info,
        output_dir=build_dir / "reference" / "mcp",
        categories=config.mcp_categories or None,
        display_name=config.mcp_name,
        language=config.lang,
    )
    if files:
        _ = reference.generate_mcp_manifest(
            server_info=server_info,
            output_dir=build_dir,
            package_name=package_name,
            repo_url=repo_url,
            site_url=config.site_url,
        )
    return files
