"""
Build and write one project's interlinks index
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .index import AliasClaims, Index, build_index
from .sources import load_sources
from .sphinx_inventory import (
    CALLABLE_ROLES,
    INVENTORY_FILENAME,
    ROLE_SYNONYMS,
    Inventory,
    decode,
)

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


def _quote_lua(value: str) -> str:
    """Quote a string for a Lua source chunk"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_index(index: Index, path: Path) -> None:
    """
    Write the index as a Lua chunk for the filter

    Quarto runs one Pandoc process per file, and each process loads the index.
    Loading Lua source is faster than decoding JSON.

    The chunk records ambiguous local names so the filter leaves unqualified
    references to them unlinked, even when an external inventory publishes the
    same spelling.

    Parameters
    ----------
    index :
        The index to write.
    path :
        Where to write it.
    """
    lines = [
        "return {",
        f"  add_function_parentheses = {str(index.add_function_parentheses).lower()},",
        "  role_synonyms = {",
    ]
    for abbrev in sorted(ROLE_SYNONYMS):
        lines.append(f"    [{_quote_lua(abbrev)}] = {_quote_lua(ROLE_SYNONYMS[abbrev])},")
    lines.append("  },")
    lines.append("  callable_roles = {")
    for role in sorted(CALLABLE_ROLES):
        lines.append(f"    [{_quote_lua(role)}] = true,")
    lines.append("  },")
    lines.append("  ambiguous = {")
    for name in sorted(index.dropped):
        lines.append(f"    [{_quote_lua(name)}] = true,")
    lines.append("  },")
    lines.append("  prefixes = {")
    for alias in sorted(index.prefixes):
        roots = ", ".join(_quote_lua(r) for r in index.prefixes[alias])
        lines.append(f"    [{_quote_lua(alias)}] = {{{roots}}},")
    lines.append("  },")
    lines.append("  names = {")

    for name in sorted(index.names):
        parts = []
        for e in index.names[name]:
            fields = [
                f"uri = {_quote_lua(e.uri)}",
                f"domain = {_quote_lua(e.domain)}",
                f"role = {_quote_lua(e.role)}",
            ]
            if e.source:
                fields.append(f"source = {_quote_lua(e.source)}")
            if e.is_local:
                fields.append('["local"] = true')
            parts.append("{" + ", ".join(fields) + "}")
        lines.append(f"    [{_quote_lua(name)}] = {{{', '.join(parts)}}},")

    lines.append("  },")
    lines.append("}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Remove an earlier compiled index because the filter loads it before this
    # source chunk.
    path.with_suffix(".luac").unlink(missing_ok=True)
