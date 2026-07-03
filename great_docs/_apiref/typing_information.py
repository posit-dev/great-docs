from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from . import inventory
from ._render import get_render_type
from ._type_checks import griffe_to_doc, is_protocol, is_typealias, is_typevar
from .introspect import get_object
from .pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    Header,
    Meta,
)

if TYPE_CHECKING:
    from typing import Any, Callable

    import griffe as gf

    from .api_reference import APIReference


@dataclass
class _TypeCategory:
    """One category of typing objects, rendered under its own header"""

    title: str
    items: list[inventory.InventoryItem]
    # Turns off the render information that a typing object of this
    # category does not need.
    configure: Callable[[Any], None]
    renders: list[Any] = field(init=False)

    def __post_init__(self) -> None:
        self.renders = []
        for item in self.items:
            docable = griffe_to_doc(item.obj)
            render = get_render_type(docable)(docable, 3)
            self.configure(render)
            self.renders.append(render)


@dataclass
class TypeSections(Block):
    protocols_items: list[inventory.InventoryItem]
    typevars_items: list[inventory.InventoryItem]
    typealiases_items: list[inventory.InventoryItem]

    def __post_init__(self) -> None:
        def hide_members_summary(r: Any) -> None:
            r.show_members_summary = False

        def hide_signature_name(r: Any) -> None:
            r.show_signature_name = False

        def hide_signature_name_and_annotation(r: Any) -> None:
            r.show_signature_name = False
            r.show_signature_annotation = False

        self.categories = [
            _TypeCategory("Protocols", self.protocols_items, hide_members_summary),
            _TypeCategory("Type Variables", self.typevars_items, hide_signature_name),
            _TypeCategory(
                "Type Aliases", self.typealiases_items, hide_signature_name_and_annotation
            ),
        ]

    def __str__(self) -> str:
        return str(self.render_body())

    @cached_property
    def items(self) -> list[inventory.InventoryItem]:
        """
        All type-information items — protocols, type variables, and type aliases
        """
        return [item for category in self.categories for item in category.items]

    def render_body(self) -> BlockContent:
        content: list[Block | str] = []

        for category in self.categories:
            if category.renders:
                content.extend(
                    [
                        Header(2, category.title),
                        *[str(r) for r in category.renders],
                    ]
                )

        return Blocks(content)


@dataclass
class TypeInformation(Block):
    module_path: str
    api_ref: APIReference

    def __post_init__(self) -> None:
        self.package = self.api_ref.package
        self.dir = self.api_ref.settings.dir

    def __str__(self) -> str:
        return str(self.content)

    @cached_property
    def base_uri(self) -> str:
        """
        The module's output path, relative to the build directory

        It does not have an extension.

        With the right extensions, this is where:
            - the module's aliases should be written (.qmd)
            - the interlinks should point (.html#anchor)
        """
        path = self.module_path
        if path.startswith(self.package):
            path = path[len(self.package) + 1 :]
        return f"{self.dir}/{path}"

    @cached_property
    def sections(self) -> TypeSections:
        def make_item(obj: gf.Object | gf.Alias) -> inventory.InventoryItem:
            """
            Build an `InventoryItem` for a typing object
            """
            return inventory.InventoryItem(
                name=obj.canonical_path,
                obj=obj,
                uri=f"{self.base_uri}.html#{obj.canonical_path}",
                dispname=obj.canonical_path,
            )

        members = list(get_object(self.module_path).members.values())
        return TypeSections(
            protocols_items=[make_item(m) for m in members if is_protocol(m)],
            typevars_items=[make_item(m) for m in members if is_typevar(m)],
            typealiases_items=[make_item(m) for m in members if is_typealias(m)],
        )

    @cached_property
    def content(self) -> BlockContent:
        meta = Meta({"title": "Typing Information"})
        return Blocks([meta, self.sections])

    def write(self) -> None:
        """
        Write the typing-information page to its `.qmd` file
        """
        self.api_ref.items.extend(self.sections.items)
        filepath = Path(f"{self.base_uri}.qmd")
        _ = filepath.write_text(str(self))
