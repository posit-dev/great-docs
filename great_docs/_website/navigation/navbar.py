"""
Placement and order of the links on the navbar's left side

Items match by label. Once a configuration write translates a label, its English
name no longer matches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ..._contribution import NavbarLink
    from ...config import Config

__all__ = ["add_link", "reorder"]

_REFERENCE_LABEL = "Reference"


def add_link(quarto_config: dict[str, Any], link: NavbarLink, *, after: str | None = None) -> bool:
    """
    Add a link to the navbar's left side unless its label is already present

    The link follows the item labelled `after`. Without `after`, or when no item has
    that label, it precedes the item labelled `Reference`, or goes last when there is
    none. The link's `before` target is not consulted.

    Parameters
    ----------
    quarto_config
        The Quarto configuration, changed in place.
    link
        The link to add.
    after
        The label of the item the link follows.

    Returns
    -------
    :
        Whether the link was added. A configuration without `website.navbar.left`
        is left unchanged.
    """
    navbar = quarto_config.get("website", {}).get("navbar")
    if not navbar or "left" not in navbar:
        return False
    items = cast("list[Any]", navbar["left"])
    labels = [_label(item) for item in items]
    if link.text in labels:
        return False
    if after and after in labels:
        position = labels.index(after) + 1
    elif _REFERENCE_LABEL in labels:
        position = labels.index(_REFERENCE_LABEL)
    else:
        position = len(items)
    items.insert(position, {"text": link.text, "href": link.href})
    return True


def reorder(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Order the navbar's left side by the labels listed in `navbar_order`

    Listed items come first, in the listed order; the other labelled items follow in
    their current order. Items without a label are dropped, and only one of the items
    that share a label is kept.

    Parameters
    ----------
    quarto_config
        The Quarto configuration, changed in place.
    config
        The Great Docs configuration.

    Returns
    -------
    :
    """
    order = config.navbar_order
    if not order:
        return
    navbar = cast("dict[str, Any]", quarto_config.get("website", {}).get("navbar", {}))
    left = cast("list[Any]", navbar.get("left", []))
    if not left:
        return

    labelled = [
        cast("dict[str, Any]", item) for item in left if isinstance(item, dict) and "text" in item
    ]
    by_label = {item["text"]: item for item in labelled}
    ordered = [by_label.pop(label) for label in order if label in by_label]
    for item in labelled:
        if item["text"] in by_label:
            ordered.append(item)
            del by_label[item["text"]]
    navbar["left"] = ordered


def _label(item: object) -> Any:
    """
    Read the label of a navbar item

    Parameters
    ----------
    item
        An entry of the navbar's left side.

    Returns
    -------
    :
        The item's `text`, or `None` when the item is not a mapping or has no `text`.
    """
    if not isinstance(item, dict):
        return None
    return cast("dict[str, Any]", item).get("text")
