from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import griffe as gf

from .._sphinx_inventory import Inventory, InventoryEntry, encode, role_for_kind
from ._walkable import Walkable


@dataclass
class InventoryItem(Walkable):
    """A documented object with a URI pointing to its rendered location"""

    obj: gf.Object | gf.Alias
    name: str = ""
    uri: str | None = None
    dispname: str | None = None
    aliases: tuple[str, ...] = ()
    """Short names this object claims, before ambiguity is arbitrated"""


def write_inventory(inv: dict[str, Any], out_name: str) -> None:
    """Write an inventory to an `objects.inv` file

    Parameters
    ----------
    inv :
        Inventory data.
    out_name :
        Output file name.
    """
    entries = tuple(
        InventoryEntry(
            name=item["name"],
            domain=item["domain"],
            role=item["role"],
            priority=int(item["priority"]),
            uri=item["uri"] or "",
            dispname=item["name"] if item["dispname"] == "-" else item["dispname"],
        )
        for item in inv["items"]
    )
    data = encode(Inventory(project=inv["project"], version=inv["version"], entries=entries))
    with open(out_name, "wb") as f:
        f.write(data)


def create_inventory(
    project: str,
    version: str,
    items: list[InventoryItem],
) -> dict[str, Any]:
    """Build the inventory as a dictionary of project, version, count, and items

    Parameters
    ----------
    project :
        Name of the project.
    version :
        Version of the project.
    items :
        Documented objects to include.
    """
    return {
        "project": project,
        "version": version,
        "count": len(items),
        "items": [_create_inventory_item(item) for item in items],
    }


def _inventory_role(obj: gf.Object | gf.Alias) -> str:
    """
    Return the Sphinx role for a documented object

    Griffe has no `method` kind of its own, and no `data` kind: a method is a
    `Function` whose parent is a class, and a module-level constant is an
    `Attribute`. The published inventory needs both distinctions, because a
    consumer's intersphinx lookup matches against Sphinx's own vocabulary.

    Parameters
    ----------
    obj :
        The documented object.

    Returns
    -------
    :
        The Sphinx role.
    """
    parent = obj.parent
    return role_for_kind(obj.kind.value, in_class=parent is not None and parent.is_class)


def _create_inventory_item(item: InventoryItem, priority: str = "1") -> dict[str, Any]:
    """Build a single inventory entry as a dict"""
    return {
        "name": item.name,
        "domain": "py",
        "role": _inventory_role(item.obj),
        "priority": priority,
        "uri": item.uri,
        "dispname": item.dispname or "-",
    }
