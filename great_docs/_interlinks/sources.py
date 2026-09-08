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
from stat import S_ISREG
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


class InventoryCache:
    """Downloaded inventories kept between builds"""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, source: Source) -> Path:
        """
        Return where a source's download is kept

        Include the source location in the key so a new documentation version
        does not reuse an older inventory under the new URL prefix.

        Parameters
        ----------
        source :
            The source being cached.

        Returns
        -------
        :
            Path to the cache entry.
        """
        digest = hashlib.md5(source.location.encode("utf-8")).hexdigest()[:12]
        return self.directory / f"{source.name}-{digest}.inv"

    def read(self, source: Source) -> Inventory | None:
        """
        Read a cached inventory

        Every way a cache entry can be unusable is a miss: absent, unreadable,
        truncated, or not an inventory at all.

        Parameters
        ----------
        source :
            The source to read the entry for.

        Returns
        -------
        :
            The inventory, or `None` when the entry cannot be used.
        """
        try:
            return decode(self.path_for(source).read_bytes())
        except (OSError, ValueError, zlib.error):
            return None

    def is_fresh(self, source: Source, max_age: timedelta) -> bool:
        """
        Report whether a cache entry is young enough to use without refetching

        Parameters
        ----------
        source :
            The source to test the entry for.
        max_age :
            How long an entry is used without refetching.

        Returns
        -------
        :
            Whether the entry is a regular file and is younger than
            `max_age`. A directory occupying the cache path is not fresh,
            since it holds no bytes `read` could ever return.
        """
        try:
            info = self.path_for(source).stat()
        except OSError:
            return False
        if not S_ISREG(info.st_mode):
            return False
        age = time.time() - info.st_mtime
        return age < max_age.total_seconds()

    def store(self, source: Source, data: bytes) -> str:
        """
        Replace a source's cache entry with fresh bytes

        Write to a process-unique temporary name and rename, so a parallel
        build never observes a half-written entry.

        Parameters
        ----------
        source :
            The source the bytes were read for.
        data :
            The inventory file's contents.

        Returns
        -------
        :
            An empty string, or a note for the build log when the entry could
            not be written.
        """
        path = self.path_for(source)
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)
        except OSError as exc:
            # The download itself succeeded; a caching problem is not a reason
            # to discard it, only to refetch again next time.
            return f"{source.name}: downloaded but could not cache it ({exc})"
        return ""


def cache_path(source: Source, cache_dir: Path) -> Path:
    """
    Return the cache path for a source inventory

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
    return InventoryCache(cache_dir).path_for(source)


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
        return _read_local(source, location, root)

    cache = InventoryCache(cache_dir)

    if cache.is_fresh(source, max_age):
        inv = cache.read(source)
        if inv is not None:
            return inv, ""

    def fall_back(exc: Exception) -> tuple[Inventory | None, str]:
        inv = cache.read(source)
        if inv is not None:
            return inv, f"{source.name}: using cached inventory ({exc})"
        return None, f"{source.name}: could not read {location} ({exc})"

    try:
        response = requests.get(location, timeout=_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return fall_back(exc)

    try:
        inv = decode(response.content)
    except (ValueError, zlib.error) as exc:
        return fall_back(exc)

    return inv, cache.store(source, response.content)


def _read_local(source: Source, location: str, root: Path | None) -> tuple[Inventory | None, str]:
    """
    Read an inventory from the filesystem

    Parameters
    ----------
    source :
        The source being read.
    location :
        Path to the inventory, absolute or relative to `root`.
    root :
        Directory a relative path is read from.

    Returns
    -------
    :
        The inventory, and a note for the build log.
    """
    path = Path(location)
    if not path.is_absolute() and root is not None:
        path = root / path
    try:
        return decode(path.read_bytes()), ""
    except FileNotFoundError:
        return None, f"{source.name}: no inventory at {location}"
    except (OSError, ValueError, zlib.error) as exc:
        return None, f"{source.name}: could not read {location} ({exc})"
