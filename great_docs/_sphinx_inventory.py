"""
Read and write the Sphinx `objects.inv` inventory format

A version 2 inventory is four plain header lines followed by a zlib stream of
records, one per documented object:

    # Sphinx inventory version 2
    # Project: {project}
    # Version: {version}
    # The remainder of this file is compressed using zlib.
    {name} {domain}:{role} {priority} {uri} {dispname}
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass

INVENTORY_FILENAME = "objects.inv"
"""What a project publishes its inventory as, the name every consumer looks for"""

_VERSION_LINE = b"# Sphinx inventory version 2"

_ZLIB_NOTE = b"# The remainder of this file is compressed using zlib."

# The name may contain spaces, so it matches lazily and the fields after it
# anchor the record. The uri may be empty.
_RECORD = re.compile(r"(.+?)\s+(\S+):(\S+)\s+(-?\d+)\s+?(\S*)\s+(.*)")


@dataclass(frozen=True)
class InventoryEntry:
    """A documented object and the page it is published on"""

    name: str
    domain: str
    role: str
    priority: int
    uri: str
    dispname: str


@dataclass(frozen=True)
class Inventory:
    """The objects a project documents, and where they are published"""

    project: str
    version: str
    entries: tuple[InventoryEntry, ...]


def decode(data: bytes) -> Inventory:
    """
    Decode the bytes of an `objects.inv` file

    The two shorthands the format allows are expanded: a `uri` ending in `$`
    takes an anchor equal to the name, and a `dispname` of `-` equals the name.

    Parameters
    ----------
    data :
        Contents of the file.

    Returns
    -------
    :
        The decoded inventory.

    Raises
    ------
    ValueError
        If the data is not a version 2 inventory.
    """
    parts = data.split(b"\n", 4)
    if len(parts) < 5 or not parts[0].startswith(_VERSION_LINE):
        raise ValueError("Not a version 2 Sphinx inventory")

    project = parts[1].partition(b":")[2].strip().decode("utf-8")
    version = parts[2].partition(b":")[2].strip().decode("utf-8")
    body = zlib.decompress(parts[4]).decode("utf-8")

    entries: list[InventoryEntry] = []
    for line in body.splitlines():
        m = _RECORD.fullmatch(line)
        if m is None:
            continue
        name, domain, role, priority, uri, dispname = m.groups()
        if uri.endswith("$"):
            uri = f"{uri[:-1]}{name}"
        entries.append(
            InventoryEntry(
                name=name,
                domain=domain,
                role=role,
                priority=int(priority),
                uri=uri,
                dispname=name if dispname == "-" else dispname,
            )
        )

    return Inventory(project=project, version=version, entries=tuple(entries))


def encode(inv: Inventory) -> bytes:
    """
    Encode an inventory as an `objects.inv` file

    Parameters
    ----------
    inv :
        The inventory to write.

    Returns
    -------
    :
        Contents for the file.
    """
    header = b"\n".join(
        (
            _VERSION_LINE,
            f"# Project: {inv.project}".encode("utf-8"),
            f"# Version: {inv.version}".encode("utf-8"),
            _ZLIB_NOTE,
            b"",
        )
    )
    records = "".join(
        "{} {}:{} {} {} {}\n".format(
            e.name,
            e.domain,
            e.role,
            e.priority,
            e.uri,
            "-" if e.dispname == e.name else e.dispname,
        )
        for e in inv.entries
    )
    return header + zlib.compress(records.encode("utf-8"), 9)
