"""
Build the lookup index used to resolve inter-project references
"""

from __future__ import annotations

import hashlib
import os
import time
import zlib
from collections import Counter
from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from ._sphinx_inventory import INVENTORY_FILENAME, Inventory, decode

if TYPE_CHECKING:
    from ._apiref.api_reference import APIReference
    from .config import Config

_TIMEOUT = 30
"""Seconds to wait for an inventory download"""


@dataclass(frozen=True)
class AliasResolution:
    """Resolved short names and names claimed by multiple objects"""

    kept: dict[str, str] = field(default_factory=dict)
    dropped: dict[str, tuple[str, ...]] = field(default_factory=dict)


def resolve_aliases(
    claims: Iterable[tuple[str, str]],
    *,
    taken: Container[str],
) -> AliasResolution:
    """
    Keep the short names that exactly one object claims

    A name claimed by two objects is ambiguous, so it is dropped rather than
    resolved to whichever object happens to sort first. A name that is already
    a real name in the inventory is skipped without being reported, because the
    real name resolves it.

    Parameters
    ----------
    claims :
        `(alias, target)` pairs, where target is the object's full name.
    taken :
        Real inventory names, which an alias may not shadow.

    Returns
    -------
    :
        The aliases that resolve, and the ambiguous ones with their claimants.
    """
    claimants: dict[str, set[str]] = {}
    for alias, target in claims:
        if alias in taken:
            continue
        claimants.setdefault(alias, set()).add(target)

    kept = {a: next(iter(t)) for a, t in claimants.items() if len(t) == 1}
    dropped = {a: tuple(sorted(t)) for a, t in claimants.items() if len(t) > 1}
    return AliasResolution(kept=kept, dropped=dropped)


@dataclass(frozen=True)
class Source:
    """An external project's documentation and its inventory location"""

    name: str
    url: str
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, name: str, value: Any) -> Source:
        """
        Build a source from one `interlinks.sources` entry

        Parameters
        ----------
        name :
            The key the entry is filed under.
        value :
            The entry's fields.

        Returns
        -------
        :
            The source.
        """
        value = value or {}
        return cls(
            name=name,
            url=str(value.get("url", "") or ""),
            aliases=tuple(value.get("aliases", []) or []),
        )

    @property
    def location(self) -> str:
        """Where the inventory is read from, by the convention every project follows"""
        return f"{self.url.rstrip('/')}/{INVENTORY_FILENAME}"


def sources_from_config(sources: dict[str, Any]) -> list[Source]:
    """
    Build the sources declared in the configuration

    An entry with no `url` is skipped; without it no URI in that inventory can
    be resolved.

    Parameters
    ----------
    sources :
        The `interlinks.sources` mapping.

    Returns
    -------
    :
        One source per usable entry.
    """
    out = [Source.from_config(name, value) for name, value in sources.items()]
    return [s for s in out if s.url]


def cache_path(source: Source, cache_dir: Path) -> Path:
    """
    Return the cache path for a source inventory

    Include the source location in the key so a new documentation version does
    not reuse an older inventory under the new URL prefix.

    Parameters
    ----------
    source :
        The source being cached.
    cache_dir :
        Directory downloads are kept under.

    Returns
    -------
    :
        Path to the cached inventory.
    """
    digest = hashlib.md5(source.location.encode("utf-8")).hexdigest()[:12]
    return cache_dir / f"{source.name}-{digest}.inv"


def load_source(
    source: Source,
    cache_dir: Path,
    *,
    max_age: timedelta = timedelta(days=7),
    root: Path | None = None,
) -> tuple[Inventory | None, str]:
    """
    Read a source inventory, using a fresh cache entry when available

    Use an older cache when downloading or decoding the fresh copy fails.
    Report and skip a source when neither its local inventory nor its cache is
    readable.

    Parameters
    ----------
    source :
        The source to read.
    cache_dir :
        Where downloads are kept between builds.
    max_age :
        How long a cached download is used without refetching.
    root :
        Directory a relative `url` is read from, which is the project the
        configuration belongs to rather than wherever the build is running.

    Returns
    -------
    :
        The inventory, and a note for the build log.
    """
    location = source.location
    if "://" not in location:
        path = Path(location)
        if not path.is_absolute() and root is not None:
            path = root / path
        if not path.exists():
            return None, f"{source.name}: no inventory at {location}"
        try:
            return decode(path.read_bytes()), ""
        except (ValueError, zlib.error) as exc:
            return None, f"{source.name}: could not read {location} ({exc})"

    cached = cache_path(source, cache_dir)

    def _read_cache() -> Inventory | None:
        if not cached.exists():
            return None
        try:
            return decode(cached.read_bytes())
        except (ValueError, zlib.error):
            return None

    if cached.exists() and time.time() - cached.stat().st_mtime < max_age.total_seconds():
        inv = _read_cache()
        if inv is not None:
            return inv, ""

    def _fall_back(exc: Exception) -> tuple[Inventory | None, str]:
        inv = _read_cache()
        if inv is not None:
            return inv, f"{source.name}: using cached inventory ({exc})"
        return None, f"{source.name}: could not read {location} ({exc})"

    try:
        response = requests.get(location, timeout=_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return _fall_back(exc)

    try:
        inv = decode(response.content)
    except (ValueError, zlib.error) as exc:
        return _fall_back(exc)

    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cached.with_suffix(f"{cached.suffix}.{os.getpid()}.tmp")
    tmp.write_bytes(response.content)
    os.replace(tmp, cached)
    return inv, ""


@dataclass(frozen=True)
class IndexEntry:
    """A reference target and the page that documents it"""

    uri: str
    domain: str
    role: str
    source: str = ""
    is_local: bool = False


@dataclass(frozen=True)
class Index:
    """The names and targets needed to resolve references"""

    names: dict[str, tuple[IndexEntry, ...]] = field(default_factory=dict)
    prefixes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    dropped: dict[str, tuple[str, ...]] = field(default_factory=dict)
    add_function_parentheses: bool = True
    """Whether a link to a function or method shows a trailing `()`"""


def root_modules(inv: Inventory) -> tuple[str, ...]:
    """
    Find the modules an inventory documents, most frequent first

    An alias is written against a module, not against the name the source is
    filed under, so a source keyed `scikit-learn` serving `sklearn.*` names
    still resolves.

    Parameters
    ----------
    inv :
        The inventory to inspect.

    Returns
    -------
    :
        Root module names.
    """
    counts = Counter(e.name.split(".")[0] for e in inv.entries)
    return tuple(name for name, _ in counts.most_common())


def build_index(
    local: Inventory,
    claims: Iterable[tuple[str, str]],
    external: Sequence[tuple[Source, Inventory]],
    *,
    add_function_parentheses: bool = True,
) -> Index:
    """
    Merge every inventory into one lookup table

    Candidates for a name are ordered so that this project wins over another,
    and a higher priority wins within a project. Short names claimed by exactly
    one object are added as ordinary entries; ambiguous ones are reported
    instead.

    Parameters
    ----------
    local :
        This project's inventory.
    claims :
        `(alias, target)` pairs from the documented objects.
    external :
        Each source and the inventory read for it.
    add_function_parentheses :
        Whether a link to a function or method shows a trailing `()`.

    Returns
    -------
    :
        The index.
    """
    found: dict[str, list[tuple[tuple[int, int], IndexEntry]]] = {}

    def add(name: str, rank: int, priority: int, entry: IndexEntry) -> None:
        found.setdefault(name, []).append(((rank, -priority), entry))

    for e in local.entries:
        add(
            e.name,
            0,
            e.priority,
            IndexEntry(uri=f"/{e.uri.lstrip('/')}", domain=e.domain, role=e.role, is_local=True),
        )

    prefixes: dict[str, tuple[str, ...]] = {}
    for source, inv in external:
        base = source.url.rstrip("/")
        for e in inv.entries:
            add(
                e.name,
                1,
                e.priority,
                IndexEntry(
                    uri=f"{base}/{e.uri.lstrip('/')}",
                    domain=e.domain,
                    role=e.role,
                    source=source.name,
                ),
            )
        roots = root_modules(inv)
        for alias in source.aliases:
            prefixes[alias] = roots

    ordered = {
        name: tuple(entry for _, entry in sorted(items, key=lambda pair: pair[0]))
        for name, items in found.items()
    }

    resolution = resolve_aliases(claims, taken=ordered)
    for alias, target in resolution.kept.items():
        if target in ordered:
            ordered[alias] = ordered[target]

    return Index(
        names=ordered,
        prefixes=prefixes,
        dropped=resolution.dropped,
        add_function_parentheses=add_function_parentheses,
    )


def _quote_lua(value: str) -> str:
    """Quote a string for a Lua source chunk"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_index(index: Index, path: Path) -> None:
    """
    Write the index as a Lua chunk the filter loads

    A chunk is written rather than JSON because Quarto runs one pandoc process
    per file and each one loads the index; Lua reads its own syntax faster than
    it decodes JSON.

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
        "  prefixes = {",
    ]
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
    notes: list[str] = []
    for source in sources_from_config(config.interlinks_sources):
        inv, note = load_source(source, cache_dir, root=config.project_root)
        if note:
            notes.append(note)
        if inv is not None:
            external.append((source, inv))

    index = build_index(
        local,
        claims,
        external,
        add_function_parentheses=config.interlinks_add_function_parentheses,
    )
    write_index(index, project_path / "_inv" / "index.lua")

    return index, notes
