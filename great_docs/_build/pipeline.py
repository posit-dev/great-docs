"""
State shared by the steps of one documentation build
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Run"]


@dataclass
class Run:
    """
    Values read by several steps of one documentation build

    Each build starts from a new `Run` with no results from earlier builds.

    Attributes
    ----------
    package_name
        The detected package name, or `""` when none was found.
    watch
        Whether the site is served in watch mode.
    has_api_reference
        Whether the site has an API reference. Preparing the build directory sets it to
        `False` when the reference is disabled, the project is not a Python project, or the
        package has nothing to document.
    api_discovery_done
        Whether this build has already discovered the package's exports.
    mcp_pages_generated
        Whether the build wrote MCP reference pages, or `None` before the MCP step decides.
    """

    package_name: str
    watch: bool
    has_api_reference: bool = True
    api_discovery_done: bool = False
    mcp_pages_generated: bool | None = None
