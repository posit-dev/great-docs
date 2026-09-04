"""
Build the lookup index used to resolve inter-project references
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests

from ._sphinx_inventory import Inventory, decode

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
    inv: str = ""
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
            inv=str(value.get("inv", "") or ""),
            aliases=tuple(value.get("aliases", []) or []),
        )

    @property
    def location(self) -> str:
        """Where the inventory is read from"""
        if self.inv:
            return self.inv
        return f"{self.url.rstrip('/')}/objects.inv"


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


def load_source(
    source: Source,
    cache_dir: Path,
    *,
    max_age: timedelta = timedelta(days=7),
    root: Path | None = None,
) -> tuple[Inventory | None, str]:
    """
    Read a source's inventory, from the cache when it is fresh enough

    A download failure falls back to any cached copy whatever its age. A source
    that cannot be read at all is reported and skipped, leaving its references
    unresolved.

    Parameters
    ----------
    source :
        The source to read.
    cache_dir :
        Where downloads are kept between builds.
    max_age :
        How long a cached download is used without refetching.
    root :
        Directory a relative `inv` path is read from, which is the project the
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
        return decode(path.read_bytes()), ""

    cached = cache_dir / f"{source.name}.inv"
    if cached.exists() and time.time() - cached.stat().st_mtime < max_age.total_seconds():
        return decode(cached.read_bytes()), ""

    try:
        response = requests.get(location, timeout=_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        if cached.exists():
            return decode(cached.read_bytes()), f"{source.name}: using cached inventory ({exc})"
        return None, f"{source.name}: could not read {location} ({exc})"

    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(response.content)
    return decode(response.content), ""


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

    return Index(names=ordered, prefixes=prefixes, dropped=resolution.dropped)


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
    lines = ["return {", "  prefixes = {"]
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
