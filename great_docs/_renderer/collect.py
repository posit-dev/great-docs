from __future__ import annotations

from great_docs._renderer import layout
from great_docs._renderer.utils import PydanticTransformer, ctx_node


class CollectTransformer(PydanticTransformer):
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.items: list[layout.Item] = []
        self.pages: list[layout.Page] = []

    def find_page_node(self):
        crnt_node = ctx_node.get()

        while True:
            if crnt_node.value is None:
                raise ValueError(f"No page detected above current element: {crnt_node.value}")

            if isinstance(crnt_node.value, layout.Page):
                return crnt_node

            crnt_node = crnt_node.parent

        return crnt_node

    def exit(self, el):
        if isinstance(el, layout.Doc):
            return self._exit_doc(el)
        if isinstance(el, layout.Page):
            return self._exit_page(el)
        return super().exit(el)

    def _exit_doc(self, el: layout.Doc):
        page_node = self.find_page_node()
        p_el = page_node.value

        uri = f"{self.base_dir}/{p_el.path}.html#{el.anchor}"

        name_path = el.obj.path
        canonical_path = el.obj.canonical_path

        self.items.append(layout.Item(name=name_path, obj=el.obj, uri=uri, dispname=None))

        if name_path != canonical_path:
            self.items.append(
                layout.Item(name=canonical_path, obj=el.obj, uri=uri, dispname=name_path)
            )

        return el

    def _exit_page(self, el: layout.Page):
        self.pages.append(el)
        return el


def collect(el: layout._Base, base_dir: str):
    """Return all pages and items in a layout.

    Parameters
    ----------
    el:
        An element, like layout.Section or layout.Page, to collect pages and items from.
    base_dir:
        The directory where API pages will live.

    """

    trans = CollectTransformer(base_dir=base_dir)
    trans.visit(el)

    return trans.pages, trans.items
