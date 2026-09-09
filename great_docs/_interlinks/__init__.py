"""
Build the lookup index used to resolve inter-project references
"""

from __future__ import annotations

from .index import (
    AliasClaims,
    AliasResolution,
    Index,
    IndexEntry,
    build_index,
    resolve_aliases,
    root_modules,
)
from .lua import write_index
from .project import build_project_index
from .sources import LoadedSources, Source, load_source, load_sources, sources_from_config

__all__ = (
    "AliasClaims",
    "AliasResolution",
    "Index",
    "IndexEntry",
    "LoadedSources",
    "Source",
    "build_index",
    "build_project_index",
    "load_source",
    "load_sources",
    "resolve_aliases",
    "root_modules",
    "sources_from_config",
    "write_index",
)
