"""
Build the index that the interlinks filter resolves links against
"""

from __future__ import annotations

import time
from collections.abc import Container, Iterable
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
    """Which short names resolve, and which are claimed by more than one object"""

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
    """Another project's documentation, and where to read its inventory"""

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

    Returns
    -------
    :
        The inventory, and a note for the build log.
    """
    location = source.location
    if "://" not in location:
        path = Path(location)
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
