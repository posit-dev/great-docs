"""
Build the lookup index used to resolve inter-project references
"""

from __future__ import annotations

from .index import (
    AliasResolution,
    Index,
    IndexEntry,
    build_index,
    resolve_aliases,
    root_modules,
)
from .lua import write_index
from .project import build_project_index
from .sources import Source, cache_path, load_source, sources_from_config

__all__ = (
    "AliasResolution",
    "Index",
    "IndexEntry",
    "Source",
    "build_index",
    "build_project_index",
    "cache_path",
    "load_source",
    "resolve_aliases",
    "root_modules",
    "sources_from_config",
    "write_index",
)
