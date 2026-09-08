"""
Read the inventories of the projects this one links to
"""

from __future__ import annotations

import hashlib
import os
import time
import zlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import requests

from .._sphinx_inventory import INVENTORY_FILENAME, Inventory, decode

_TIMEOUT = 30
"""Seconds to wait for an inventory download"""


@dataclass(frozen=True)
class Source:
    """An external project's documentation and its inventory location"""

    name: str
    url: str
    aliases: tuple[str, ...] = ()
    site_url: str = ""
    """Where the source's pages are actually served, when that differs from `url`"""

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
            site_url=str(value.get("site_url", "") or ""),
        )

    @property
    def location(self) -> str:
        """Where the inventory is read from, by the convention every project follows"""
        return f"{self.url.rstrip('/')}/{INVENTORY_FILENAME}"

    @property
    def is_local_path(self) -> bool:
        """Whether `url` names a filesystem location rather than a served one"""
        return "://" not in self.url


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

    Use an older cache when downloading, decoding, or reading the fresh copy
    fails. Report and skip a source when neither its local inventory nor its
    cache is readable. A download that decodes but cannot be cached is still
    returned, since caching is an optimization the read must not depend on.

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
        try:
            if not path.exists():
                return None, f"{source.name}: no inventory at {location}"
            return decode(path.read_bytes()), ""
        except (ValueError, zlib.error, OSError) as exc:
            return None, f"{source.name}: could not read {location} ({exc})"

    cached = cache_path(source, cache_dir)

    def _read_cache() -> Inventory | None:
        try:
            if not cached.exists():
                return None
            return decode(cached.read_bytes())
        except (ValueError, zlib.error, OSError):
            return None

    try:
        cache_is_fresh = (
            cached.exists() and time.time() - cached.stat().st_mtime < max_age.total_seconds()
        )
    except OSError:
        cache_is_fresh = False

    if cache_is_fresh:
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

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f"{cached.suffix}.{os.getpid()}.tmp")
        tmp.write_bytes(response.content)
        os.replace(tmp, cached)
    except OSError as exc:
        # The download itself succeeded; a caching problem is not a reason to
        # discard it, only to refetch again next time.
        return inv, f"{source.name}: downloaded but could not cache it ({exc})"

    return inv, ""
