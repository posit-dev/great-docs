from __future__ import annotations

from dataclasses import dataclass

from ._visitor import NodeTransformer, NodeVisitor, ctx_node
from .content import Doc, Page, Section
from .inventory import InventoryItem


@dataclass
class Manifest:
    """The pages and inventory items produced from a resolved section tree"""

    pages: list[Page]
    items: list[InventoryItem]


class _ManifestBuilder(NodeVisitor):
    """Accumulated pages and inventory items produced by a single traversal of a resolved tree."""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.items: list[InventoryItem] = []
        self.pages: list[Page] = []

    def find_page_node(self) -> Page:
        """The nearest `Page` ancestor of the current node in the traversal context."""
        crnt_node = ctx_node.get()

        while True:
            if crnt_node.value is None:
                raise ValueError(f"No page detected above current element: {crnt_node.value}")

            if isinstance(crnt_node.value, Page):
                return crnt_node.value

            if crnt_node.parent is None:
                raise ValueError("Reached root without finding a Page ancestor")

            crnt_node = crnt_node.parent

    def exit(self, el: object) -> object:
        if isinstance(el, Doc):
            return self._exit_doc(el)
        if isinstance(el, Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_doc(self, el: Doc) -> Doc:
        p_el = self.find_page_node()

        uri = f"{self.base_dir}/{p_el.path}.html#{el.anchor}"

        obj = el.obj
        name_path = obj.path
        canonical_path = obj.canonical_path

        self.items.append(InventoryItem(name=name_path, obj=obj, uri=uri, dispname=None))

        if name_path != canonical_path:
            self.items.append(
                InventoryItem(name=canonical_path, obj=obj, uri=uri, dispname=name_path)
            )

        return el

    def _exit_page(self, el: Page) -> Page:
        self.pages.append(el)
        return el


def build_manifest(sections: list[Section], *, dir: str) -> Manifest:
    """All pages and inventory items found in a resolved section list."""

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
            new_path = ".".join(parts[1:])
            new_el = el.copy()
            assert isinstance(new_el, Page)
            new_el.path = new_path
            return new_el
        return el


def remove_package_prefix(sections: list[Section], package: str) -> list[Section]:
    """Resolved sections with the leading package name removed from every `Page` path."""

    remover = _PackagePrefixRemover(package)
    return remover.visit(sections)  # type: ignore[return-value]
