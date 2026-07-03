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
    """A resolved section tree's pages (to write) and inventory items (to index)"""

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.items: list[InventoryItem] = []
        self.pages: list[Page] = []

    def find_page_node(self) -> Page:
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
