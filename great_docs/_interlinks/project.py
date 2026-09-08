"""
Build and write one project's interlinks index
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .._sphinx_inventory import INVENTORY_FILENAME, Inventory, decode
from .index import Index, build_index
from .lua import write_index
from .sources import Source, load_source, sources_from_config

if TYPE_CHECKING:
    from .._apiref.api_reference import APIReference
    from ..config import Config


def build_project_index(
    project_path: Path,
    config: Config,
    package_name: str,
    ref: APIReference | None,
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
    ref :
        Built API reference, or `None` when only external links are available.

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

    claims: list[tuple[str, str]] = []
    if ref is not None:
        claims = [(alias, item.name) for item in ref.items for alias in item.aliases]

    cache_dir = config.cache_dir / "interlinks"
    external: list[tuple[Source, Inventory]] = []
    configured, notes = sources_from_config(config.interlinks_sources)
    for source in configured:
        inv, note = load_source(source, cache_dir, root=config.project_root)
        if note:
            notes.append(note)
        if inv is None:
            continue
        external.append((source, inv))

    index = build_index(
        local,
        claims,
        external,
        add_function_parentheses=config.interlinks_add_function_parentheses,
    )
    write_index(index, project_path / "_inv" / "index.lua")

    return index, notes
