"""
Persistent API reference sections for reuse between builds
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from importlib.machinery import PathFinder
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .. import __version__

if TYPE_CHECKING:
    from .exports import Exports

__all__ = ["PATH", "Discovery", "sections"]

# Watch mode checks entries beside its build directory for earlier builds. Keep the cache
# file in a separate directory so it is not treated as a build.
PATH = Path("api-discovery", "sections.json")
"""The saved discovery's path within the project's cache directory"""


@dataclass(frozen=True)
class Discovery:
    """A package's API reference sections and whether they came from the cache"""

    sections: list[dict[str, Any]] | None
    """The sections, or `None` when the package has nothing to document"""

    reused: bool
    """Whether the sections were saved by an earlier build instead of discovered in this one"""


def sections(exports: Exports, name: str, *, reuse: bool) -> Discovery:
    """
    Find a package's API reference sections, reusing cached sections when allowed

    Cached sections remain valid while the Great Docs version, the package's importable
    name, the configuration file and the contents of the package's files are unchanged.
    Discover and save sections when the cache is invalid or `reuse` is false. Treat a
    missing, unreadable or malformed cache as absent. If the package's files cannot be
    found or read, discover sections without saving them.

    Parameters
    ----------
    exports
        The build's export discovery, including configuration and package search paths.
    name
        The package's importable name.
    reuse
        Whether to reuse valid cached sections instead of discovering them.

    Returns
    -------
    :
        The sections and whether they were reused.

    Raises
    ------
    BuildError
        If the `reference` setting names an object the loaded package lacks.
    """
    path = exports.config.cache_dir / PATH
    key = _key(exports, name)
    if reuse and key is not None and (saved := _read(path, key)) is not None:
        return saved
    found = exports.sections(name)
    if key is not None:
        _write(path, key, found)
    return Discovery(found, reused=False)


def _key(exports: Exports, name: str) -> str | None:
    """
    Compute a cache key from the inputs to API reference discovery

    Parameters
    ----------
    exports
        The build's export discovery.
    name
        The package's importable name.

    Returns
    -------
    :
        The hexadecimal digest, or `None` when the package's files cannot be found or read.
    """
    top_level = name.replace("-", "_").partition(".")[0]
    files = _package_files(top_level, exports.project.search_paths())
    if files is None:
        return None
    digest = hashlib.sha256()
    try:
        config_text = exports.config.config_path.read_bytes()
    except FileNotFoundError:
        config_text = b""
    except OSError:
        return None
    parts = [__version__.encode(), name.encode(), config_text]
    try:
        for file in files:
            parts += [str(file).encode(), file.read_bytes()]
    except OSError:
        return None
    for part in parts:
        # Prefix each part's length so different part boundaries produce different inputs.
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return digest.hexdigest()


def _package_files(module: str, search_paths: list[str | Path]) -> list[Path] | None:
    """
    List the files of the top-level module resolved from the search paths

    Search without importing the module. Include all files under a package's directories
    except those in `__pycache__` directories.

    Parameters
    ----------
    module
        The top-level module's name.
    search_paths
        The directories to search, in order.

    Returns
    -------
    :
        The files in a stable order, or `None` when the module is not found or its files
        cannot be listed.
    """
    spec = PathFinder.find_spec(module, [str(path) for path in search_paths])
    if spec is None:
        return None
    if spec.submodule_search_locations is None:
        if not spec.has_location or spec.origin is None:
            return None
        return [Path(spec.origin)]
    try:
        return [
            file
            for location in sorted(Path(entry) for entry in spec.submodule_search_locations)
            for file in sorted(location.rglob("*"))
            if "__pycache__" not in file.relative_to(location).parts and file.is_file()
        ]
    except OSError:
        return None


def _read(path: Path, key: str) -> Discovery | None:
    """
    Read cached sections whose key matches the current inputs

    Parameters
    ----------
    path
        The cache file's path.
    key
        The digest of the current inputs.

    Returns
    -------
    :
        The cached sections marked as reused, or `None` if the file is missing, unreadable,
        malformed or saved for different inputs.
    """
    try:
        saved: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(saved, dict):
        return None
    saved = cast("dict[str, object]", saved)
    if saved.get("key") != key:
        return None
    found = saved.get("sections")
    if found is None:
        return Discovery(None, reused=True)
    if not isinstance(found, list):
        return None
    found = cast("list[object]", found)
    if not all(isinstance(section, dict) for section in found):
        return None
    return Discovery(cast("list[dict[str, Any]]", found), reused=True)


def _write(path: Path, key: str, found: list[dict[str, Any]] | None) -> None:
    """
    Save discovered sections for later builds and warn if saving fails

    Parameters
    ----------
    path
        The cache file's path.
    key
        The digest of the inputs that produced the sections.
    found
        The discovered sections.

    Returns
    -------
    :
    """
    try:
        text = json.dumps({"key": key, "sections": found}, indent=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(text, encoding="utf-8")
    except (OSError, TypeError, ValueError) as error:
        print(f"Warning: Could not save the API discovery: {error}", file=sys.stderr)
