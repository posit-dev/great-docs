from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ._griffe import dataclasses as dc
from ._walkable import _Walkable  # pyright: ignore[reportPrivateUsage]


@dataclass
class InventoryItem(_Walkable):
    """A documented object with a URI pointing to its rendered location"""

    obj: dc.Object | dc.Alias
    name: str = ""
    uri: str | None = None
    dispname: str | None = None


def convert_inventory(inv: dict[str, Any], out_name: str) -> None:
    """Write an inventory to a JSON file

    Parameters
    ----------
    inv :
        Inventory data.
    out_name :
        Output file name.
    """
    with open(out_name, "w") as f:
        json.dump(inv, f)


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


def _create_inventory_item(item: InventoryItem, priority: str = "1") -> dict[str, Any]:
    """Build a single inventory entry as a dict"""
    return {
        "name": item.name,
        "domain": "py",
        "role": item.obj.kind.value,
        "priority": priority,
        "uri": item.uri,
        "dispname": item.dispname or "-",
    }
