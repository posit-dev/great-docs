from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, partial

from ._rendering._label import get_label
from ._visitor import NodeTransformer, NodeVisitor, ctx_node
from .content import Doc, MemberPage, Page, Section
from .inventory import InventoryItem, class_targets, reference_uri
from .spec import claim_page_path


@dataclass
class Manifest:
    """The pages and inventory items produced from a resolved section tree"""

    pages: list[Page]
    items: list[InventoryItem]

    @cached_property
    def class_targets(self) -> dict[str, InventoryItem]:
        """The published destinations for qualified class names"""
        return class_targets(self.items)


class _ManifestBuilder(NodeVisitor):
    """A resolved section tree's pages (to write) and inventory items (to index)"""

    def __init__(self, base_dir: str) -> None:
        """
        Start with no pages and no inventory items

        Parameters
        ----------
        base_dir
            The directory that inventory URIs are relative to.
        """
        self.base_dir = base_dir
        self.items: list[InventoryItem] = []
        self.pages: list[Page] = []

    def enclosing_page(self) -> Page:
        """
        Find the nearest `Page` enclosing the current node

        Returns
        -------
        :
            The enclosing page.

        Raises
        ------
        ValueError
            If no ancestor of the current node is a page.
        """
        node = ctx_node.get()

        while node is not None:
            if isinstance(node.value, Page):
                return node.value
            node = node.parent

        raise ValueError("No `Page` ancestor above the current element")

    def exit(self, el: object) -> object:
        """
        Record a documented object or a page after visiting its children

        Parameters
        ----------
        el
            The node being left.

        Returns
        -------
        :
            The node, unchanged.
        """
        if isinstance(el, Doc):
            return self._exit_doc(el)
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_doc(self, el: Doc) -> Doc:
        """
        Record inventory items for a documented object at its enclosing page

        An object whose canonical path differs from its documented path gets a second
        item under the canonical path.

        Parameters
        ----------
        el
            The documented object.

        Returns
        -------
        :
            The documented object, unchanged.
        """
        p_el = self.enclosing_page()

        anchor = None if isinstance(p_el, MemberPage) and el is p_el.contents[0] else el.anchor
        uri = reference_uri(self.base_dir, p_el.path, anchor)

        obj = el.obj
        name_path = obj.path
        canonical_path = obj.canonical_path

        # Bare member names often collide across classes (`flush`, `close`), so
        # claim `Class.member` as a shorter unambiguous form.
        aliases = (el.name, obj.name)
        parent = obj.parent
        if parent is not None and parent.is_class:
            aliases = (*aliases, f"{parent.name}.{obj.name}")

        self.items.append(
            InventoryItem(
                name=name_path,
                obj=obj,
                uri=uri,
                dispname=None,
                aliases=aliases,
            )
        )

        if name_path != canonical_path:
            self.items.append(
                InventoryItem(name=canonical_path, obj=obj, uri=uri, dispname=name_path)
            )

        return el

    def _exit_page(self, el: Page) -> Page:
        """
        Record a page to write

        Parameters
        ----------
        el
            The page.

        Returns
        -------
        :
            The page, unchanged.
        """
        self.pages.append(el)
        return el


def build_manifest(sections: list[Section], *, dir: str) -> Manifest:
    """
    Build the manifest of pages and inventory items found in a resolved section list

    Parameters
    ----------
    sections
        The resolved sections.
    dir
        The directory that inventory URIs are relative to.

    Returns
    -------
    :
        The pages in traversal order and their inventory items.
    """

    b = _ManifestBuilder(base_dir=dir)
    _ = b.visit(sections)

    return Manifest(pages=b.pages, items=b.items)


class _PackagePrefixRemover(NodeTransformer):
    """A node tree whose Page paths have the leading package-name component removed"""

    def __init__(self, package: str) -> None:
        """
        Remove the given package name from page paths

        Parameters
        ----------
        package
            The package name to remove.
        """
        self.package = package

    def exit(self, el: object) -> object:
        """
        Remove the package name from a page's path

        Parameters
        ----------
        el
            The node being left.

        Returns
        -------
        :
            The node, or a copy of a page with the shorter path.
        """
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_page(self, el: Page) -> Page:
        """
        Remove the package name from a page's path

        Parameters
        ----------
        el
            The page.

        Returns
        -------
        :
            A copy with the shorter path, or the page itself when its path does not start
            with the package name or has no other component.
        """
        parts = el.path.split(".")
        if parts[0] == self.package and len(parts) > 1:
            return el.replace(path=".".join(parts[1:]))
        return el


def remove_package_prefix(sections: list[Section], package: str) -> list[Section]:
    """
    Remove the leading package name from every `Page` path in resolved sections

    Parameters
    ----------
    sections
        The resolved sections.
    package
        The package name to remove.

    Returns
    -------
    :
        The sections with the shorter page paths.
    """

    remover = _PackagePrefixRemover(package)
    return remover.visit(sections)  # type: ignore[return-value]


class _MemberPagePathClaimer(NodeTransformer):
    """A node tree whose member pages have paths no other page shares case-insensitively"""

    def __init__(self, claimed: dict[str, str]) -> None:
        """
        Claim member page paths that do not clash with the paths already claimed

        Parameters
        ----------
        claimed
            The paths already claimed, keyed by their casefolded form. Each claimed member
            page path is added to it.
        """
        self.claimed = claimed

    def exit(self, el: object) -> object:
        """
        Give a member page a path no other page shares case-insensitively

        Parameters
        ----------
        el
            The node being left.

        Returns
        -------
        :
            The node, or a copy of a member page with a new path.
        """
        if isinstance(el, MemberPage):
            path = claim_page_path(el.path, self.claimed, partial(get_label, el.obj))
            return el if path == el.path else el.replace(path=path)
        return super().exit(el)


def unique_member_page_paths(sections: list[Section]) -> list[Section]:
    """
    Give every member page a path no other page shares case-insensitively

    Top-level pages already carry unique paths (see `spec.unique_page_paths()`)
    and the sidebar and `llms.txt` link to them by those paths, so they are
    claimed first and never move. A member page (from `members_on_same_page: false`)
    that would share a file with another page on a case-insensitive filesystem
    gets the member's label as a suffix instead (`Widget.Run-method`).

    Parameters
    ----------
    sections
        The resolved sections.

    Returns
    -------
    :
        The sections with any clashing member page paths replaced.
    """
    claimed: dict[str, str] = {}
    for section in sections:
        for entry in section.contents:
            if isinstance(entry, Page) and not isinstance(entry, MemberPage):
                _ = claim_page_path(entry.path, claimed)

    claimer = _MemberPagePathClaimer(claimed)
    return claimer.visit(sections)  # type: ignore[return-value]
