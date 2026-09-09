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
from typing import TYPE_CHECKING, Any

import requests

from .._sphinx_inventory import INVENTORY_FILENAME, Inventory, decode

if TYPE_CHECKING:
    from ..config import Config

_TIMEOUT = 30
"""Seconds to wait for an inventory download"""


@dataclass(frozen=True)
class Source:
    """
    An external project's documentation

    One `url` answers both questions a source is asked: its inventory is read
    from `<url>/objects.inv`, and every URI in that inventory is resolved
    against `<url>`. A `url` addressing a directory on disk is read the same
    way and prefixes links the same way. Whether those links resolve from the
    reading page is the site's arrangement to get right, not this module's.
    """

    name: str
    url: str
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError(f"source {self.name!r} has no url to read its inventory from")

    @property
    def inventory_location(self) -> str:
        """Where the inventory is read from, by the convention every project follows"""
        return f"{self.url.rstrip('/')}/{INVENTORY_FILENAME}"

    @property
    def link_prefix(self) -> str:
        """What every URI in this source's inventory is prefixed with"""
        return self.url.rstrip("/")


def _is_served(url: str) -> bool:
    """
    Report whether a url addresses a served location rather than the filesystem

    Parameters
    ----------
    url :
        The configured url.

    Returns
    -------
    :
        Whether the url carries a scheme.
    """
    return "://" in url


def _is_relative(url: str) -> bool:
    """
    Report whether a url is resolved relative to the page that carries the link

    Parameters
    ----------
    url :
        The configured url.

    Returns
    -------
    :
        Whether the url carries neither a scheme nor a leading slash.
    """
    return not _is_served(url) and not url.startswith("/")


def sources_from_config(sources: dict[str, Any]) -> tuple[list[Source], list[str]]:
    """
    Build the sources declared in the configuration

    Reject an entry with no `url`, since neither its inventory nor its links
    have an address without one. That is the only reason an entry is rejected.

    Note a relative `url` rather than rejecting it. One prefix is written into
    the index and used from pages at every depth, so a relative one resolves to
    a different place from each of them. Report it and write the links as
    configured, since a site whose pages all sit at one depth still works.

    Parameters
    ----------
    sources :
        The `interlinks.sources` mapping.

    Returns
    -------
    :
        The usable sources, and a note for each entry that was rejected or that
        names a url whose links cannot resolve from every page.
    """
    usable: list[Source] = []
    notes: list[str] = []
    for name, value in sources.items():
        value = value or {}
        url = str(value.get("url", "") or "")
        if not url:
            notes.append(f"{name}: no url configured; it will not be linked")
            continue
        if _is_relative(url):
            notes.append(
                f"{name}: '{url}' is relative, so links into it resolve from wherever the "
                "reading page sits; give a url that is the same on disk and on the site"
            )
        usable.append(Source(name=name, url=url, aliases=tuple(value.get("aliases", []) or [])))
    return usable, notes


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
        digest = hashlib.md5(source.inventory_location.encode("utf-8")).hexdigest()[:12]
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
    returned, since caching is an optimisation the read must not depend on.

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
    location = source.inventory_location
    if not _is_served(location):
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


@dataclass(frozen=True)
class LoadedSources:
    """Configured sources and the inventories that were read"""

    read: tuple[tuple[Source, Inventory], ...] = ()
    """Sources paired with successfully read inventories"""

    unread: tuple[str, ...] = ()
    """Source names whose inventories could not be read"""

    notes: tuple[str, ...] = ()
    """Notes for the build log"""


def load_sources(config: Config) -> LoadedSources:
    """
    Load the inventories for configured sources

    Sources without a URL are not unread. The build cannot resolve a reference
    to them either.

    Parameters
    ----------
    config :
        Project configuration, for the declared sources, the cache directory
        and the root used to read a relative URL.

    Returns
    -------
    :
        The read and unread sources and build-log notes.
    """
    configured, notes = sources_from_config(config.interlinks_sources)
    cache_dir = config.cache_dir / "interlinks"
    read: list[tuple[Source, Inventory]] = []
    unread: list[str] = []

    for source in configured:
        inv, note = load_source(source, cache_dir, root=config.project_root)
        if note:
            notes.append(note)
        if inv is None:
            unread.append(source.name)
            continue
        read.append((source, inv))

    return LoadedSources(read=tuple(read), unread=tuple(unread), notes=tuple(notes))
