"""
Build and write one project's interlinks index
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .._sphinx_inventory import INVENTORY_FILENAME, Inventory, decode
from .index import AliasClaims, Index, build_index
from .lua import write_index
from .sources import load_sources

if TYPE_CHECKING:
    from ..config import Config


def build_project_index(
    project_path: Path,
    config: Config,
    package_name: str,
    claims: AliasClaims,
) -> tuple[Index, list[str]]:
    """
    Build and write the interlinks index for a project

    Read the project's `objects.inv` when available, merge it with the
    sources declared in `config.interlinks_sources`, and write the result to
    `project_path/_inv/index.lua` for the interlinks filter.

    Parameters
    ----------
    project_path :
        Project directory containing the local inventory and receiving the
        generated index.
    config :
        Project configuration containing interlinks settings, the cache
        directory, and the root for resolving relative source URLs.
    package_name :
        Project name to use when `project_path` has no `objects.inv`.
    claims :
        The short names this project's documented objects claim. Empty when
        only external links are available.

    Returns
    -------
    :
        The merged index and notes for sources that could not be read.
    """
    inventory_path = project_path / INVENTORY_FILENAME
    if inventory_path.exists():
        local = decode(inventory_path.read_bytes())
    else:
        local = Inventory(project=package_name, version="", entries=())

    sources = load_sources(config)
    index = build_index(
        local,
        claims,
        sources.read,
        add_function_parentheses=config.interlinks_add_function_parentheses,
    )
    write_index(index, project_path / "_inv" / "index.lua")

    return index, list(sources.notes)
