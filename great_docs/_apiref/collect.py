from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from ._render._label import get_label
from ._visitor import NodeTransformer, NodeVisitor, ctx_node
from .content import Doc, MemberPage, Page, Section
from .inventory import InventoryItem, reference_uri
from .spec import claim_page_path


@dataclass
class Manifest:
    """The pages and inventory items produced from a resolved section tree"""

    pages: list[Page]
    items: list[InventoryItem]


class _ManifestBuilder(NodeVisitor):
    """A resolved section tree's pages (to write) and inventory items (to index)"""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.items: list[InventoryItem] = []
        self.pages: list[Page] = []

    def enclosing_page(self) -> Page:
        """Find the nearest `Page` enclosing the current node"""
        node = ctx_node.get()

        while node is not None:
            if isinstance(node.value, Page):
                return node.value
            node = node.parent

        raise ValueError("No `Page` ancestor above the current element")

    def exit(self, el: object) -> object:
        if isinstance(el, Doc):
            return self._exit_doc(el)
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_doc(self, el: Doc) -> Doc:
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
        self.pages.append(el)
        return el


def build_manifest(sections: list[Section], *, dir: str) -> Manifest:
    """Build the manifest of pages and inventory items found in a resolved section list"""

    b = _ManifestBuilder(base_dir=dir)
    _ = b.visit(sections)

    return Manifest(pages=b.pages, items=b.items)


class _PackagePrefixRemover(NodeTransformer):
    """A node tree whose Page paths have the leading package-name component removed"""

    def __init__(self, package: str) -> None:
        self.package = package

    def exit(self, el: object) -> object:
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_page(self, el: Page) -> Page:
        parts = el.path.split(".")
        if parts[0] == self.package and len(parts) > 1:
            return el.replace(path=".".join(parts[1:]))
        return el


def remove_package_prefix(sections: list[Section], package: str) -> list[Section]:
    """Remove the leading package name from every `Page` path in resolved sections"""

    remover = _PackagePrefixRemover(package)
    return remover.visit(sections)  # type: ignore[return-value]


class _MemberPagePathClaimer(NodeTransformer):
    """A node tree whose member pages have paths no other page shares case-insensitively"""

    def __init__(self, claimed: dict[str, str]) -> None:
        self.claimed = claimed

    def exit(self, el: object) -> object:
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
    """
    claimed: dict[str, str] = {}
    for section in sections:
        for entry in section.contents:
            if isinstance(entry, Page) and not isinstance(entry, MemberPage):
                _ = claim_page_path(entry.path, claimed)

    claimer = _MemberPagePathClaimer(claimed)
    return claimer.visit(sections)  # type: ignore[return-value]
