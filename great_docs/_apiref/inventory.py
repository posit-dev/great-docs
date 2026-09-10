from __future__ import annotations

from dataclasses import dataclass

import griffe as gf

from .._sphinx_inventory import (
    Inventory,
    InventoryEntry,
    encode,
    is_builtin_exception,
    role_for_kind,
)
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


def reference_uri(dir: str, stem: str, anchor: str | None = None) -> str:
    """
    Return a reference page's URI, relative to the site root

    Parameters
    ----------
    dir :
        Directory the reference pages are written to.
    stem :
        The page's path without its suffix.
    anchor :
        Fragment identifying an object on the page, when it is not the page's
        own subject.

    Returns
    -------
    :
        The URI a consumer joins to the site URL.
    """
    uri = f"{dir}/{stem}.html"
    return f"{uri}#{anchor}" if anchor else uri


def write_inventory(inv: Inventory, out_name: str) -> None:
    """
    Write an inventory to an `objects.inv` file

    Parameters
    ----------
    inv :
        The inventory to write.
    out_name :
        Output file name.
    """
    with open(out_name, "wb") as f:
        f.write(encode(inv))


def create_inventory(
    project: str,
    version: str,
    items: list[InventoryItem],
) -> Inventory:
    """
    Build the inventory a project publishes

    Parameters
    ----------
    project :
        Name of the project.
    version :
        Version of the project.
    items :
        Documented objects to include.

    Returns
    -------
    :
        The inventory.
    """
    entries = tuple(
        InventoryEntry(
            name=item.name,
            domain="py",
            role=_inventory_role(item.obj),
            priority=1,
            uri=item.uri or "",
            dispname=item.dispname or item.name,
        )
        for item in items
    )
    return Inventory(project=project, version=version, entries=entries)


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
    return role_for_kind(
        obj.kind.value,
        in_class=parent is not None and parent.is_class,
        is_exception=_is_exception(obj),
    )


def _is_exception(obj: gf.Object | gf.Alias) -> bool:
    """
    Report whether a documented class derives from one of Python's exceptions

    Griffe leaves a base outside the loaded tree unresolved, so a class
    deriving straight from `Exception` is recognised by the name it names,
    and one deriving from another class in the project by walking the
    ancestors griffe did resolve. A base neither of those reaches, such as a
    third-party exception, is not recognised.

    Parameters
    ----------
    obj :
        The documented object.

    Returns
    -------
    :
        Whether the object is an exception class.
    """
    try:
        if obj.kind.value != "class":
            return False
        ancestors = [obj, *obj.mro()]  # pyright: ignore[reportAttributeAccessIssue]
    except (gf.AliasResolutionError, gf.CyclicAliasError, ValueError):
        return False
    return any(
        is_builtin_exception(str(base)) for cls in ancestors for base in getattr(cls, "bases", ())
    )
