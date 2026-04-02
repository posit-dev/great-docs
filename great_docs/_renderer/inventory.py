from __future__ import annotations

import json
from typing import Callable

from . import layout
from ._griffe import dataclasses as dc


def convert_inventory(inv: "dict | object", out_name: str | None = None) -> None:
    """Convert an inventory to JSON.

    Parameters
    ----------
    inv: dict or sphobjinv.Inventory
        Inventory data. If a dict, writes directly as JSON.
        If an sphobjinv Inventory, converts to dict first.
    out_name: str, optional
        Output file name.
    """
    if out_name is None:
        raise TypeError("out_name is required")

    # If it's already our simplified dict format, write directly
    if isinstance(inv, dict):
        with open(out_name, "w") as f:
            json.dump(inv, f)
        return

    # Try sphobjinv Inventory format (backwards compat)
    try:
        obj = inv.json_dict()
        long = list(obj.items())
        meta, entries = long[:3], [v for k, v in long[3:]]
        out = dict(meta)
        out["items"] = entries
        with open(out_name, "w") as f:
            json.dump(out, f)
    except AttributeError:
        raise TypeError(f"Unsupported inventory type: {type(inv)}")


def create_inventory(
    project: str,
    version: str,
    items: "list",
    uri: "str | Callable | None" = None,
    dispname: "str | Callable | None" = None,
) -> dict:
    """Return a inventory as a dictionary.

    Parameters
    ----------
    project: str
        Name of the project.
    version: str
        Version of the project.
    items: list
        List of Item or griffe object items to include.
    uri:
        Link relative to the docs. Not used when items are layout.Item.
    dispname:
        Display name. Not used when items are layout.Item.

    Returns
    -------
    dict
        Inventory dictionary with project, version, count, and items.
    """
    if uri is None:
        uri = lambda s: f"{s.canonical_path}.html"
    if dispname is None:
        dispname = "-"

    inv_items = []
    for item in items:
        inv_items.append(_create_inventory_item(item, uri, dispname))

    return {
        "project": project,
        "version": version,
        "count": len(inv_items),
        "items": inv_items,
    }


def _create_inventory_item(
    item: "layout.Item | dc.Object | dc.Alias",
    uri: "str | Callable",
    dispname: "str | Callable" = "-",
    priority: str = "1",
) -> dict:
    """Create a single inventory item dict."""

    if isinstance(item, layout.Item):
        return {
            "name": item.name,
            "domain": "py",
            "role": item.obj.kind.value,
            "priority": priority,
            "uri": item.uri,
            "dispname": item.dispname or "-",
        }
    elif isinstance(item, (dc.Object, dc.Alias)):
        target = item
        return {
            "name": target.path,
            "domain": "py",
            "role": target.kind.value,
            "priority": priority,
            "uri": _maybe_call(uri, target),
            "dispname": _maybe_call(dispname, target),
        }
    else:
        raise TypeError(f"Unsupported item type: {type(item)}")


def _maybe_call(s: "str | Callable", obj: object) -> str:
    if callable(s):
        return s(obj)
    elif isinstance(s, str):
        return s

    raise TypeError(f"Expected string or callable, received: {type(s)}")
