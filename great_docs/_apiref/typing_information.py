from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import griffe as gf

from great_docs.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    Header,
    Meta,
)

from . import inventory
from ._conversion import griffe_to_doc
from ._rendering._context import _RenderingPurpose
from ._rendering._renderers import Renderers
from ._type_checks import is_protocol, is_typealias, is_typevar
from .introspect import get_object

if TYPE_CHECKING:
    from ._settings import Settings
    from .api_reference import APIReference
    from .typing import RenderObjType


@dataclass
class _TypeCategory:
    """One category of typing objects, rendered under its own heading"""

    title: str
    items: list[inventory.InventoryItem]
    renderers: list[RenderObjType]

    @classmethod
    def make(
        cls,
        title: str,
        items: list[inventory.InventoryItem],
        settings: Settings,
        choices: Renderers,
        purpose: _RenderingPurpose,
    ) -> _TypeCategory:
        """Construct category renderers using the typing workflow's presentation"""
        renderers: list[RenderObjType] = [
            choices.make(griffe_to_doc(item.obj), 3, settings=settings, _purpose=purpose)
            for item in items
        ]
        return cls(title, items, renderers)


@dataclass
class TypeSections(Block):
    protocols_items: list[inventory.InventoryItem]
    typevars_items: list[inventory.InventoryItem]
    typealiases_items: list[inventory.InventoryItem]
    settings: Settings
    renderers: Renderers = field(default_factory=Renderers, kw_only=True)

    def __post_init__(self) -> None:
        self.categories = [
            _TypeCategory.make(
                "Protocols",
                self.protocols_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.PROTOCOL,
            ),
            _TypeCategory.make(
                "Type Variables",
                self.typevars_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_VARIABLE,
            ),
            _TypeCategory.make(
                "Type Aliases",
                self.typealiases_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_ALIAS,
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
            if category.renderers:
                content.extend(
                    [
                        Header(2, category.title),
                        *[str(r) for r in category.renderers],
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

    def _is_own(self, obj: gf.Object | gf.Alias) -> bool:
        """
        Whether `obj` belongs to the documented package

        The page documents the package's own protocols, type variables, and
        type aliases, including the ones the module re-exports from
        elsewhere in the package. A name imported from outside it, such as
        `typing.AnyStr`, is documented where it is defined.

        Parameters
        ----------
        obj :
            A member of the typing module.

        Returns
        -------
        :
            `True` when the object is defined in the package.
        """
        if not isinstance(obj, gf.Alias):
            return True
        target = obj.target_path
        return target == self.package or target.startswith(f"{self.package}.")

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

        members = [m for m in get_object(self.module_path).members.values() if self._is_own(m)]
        return TypeSections(
            protocols_items=[make_item(m) for m in members if is_protocol(m)],
            typevars_items=[make_item(m) for m in members if is_typevar(m)],
            typealiases_items=[make_item(m) for m in members if is_typealias(m)],
            settings=self.api_ref.settings,
            renderers=self.api_ref.renderers,
        )

    @cached_property
    def content(self) -> BlockContent:
        meta = Meta({"title": "Typing Information", "body-classes": "doc-api-page doc-py-api-page"})
        return Blocks([meta, self.sections])

    def write(self) -> None:
        """
        Write the typing-information page to its `.qmd` file
        """
        self.api_ref.items.extend(self.sections.items)
        filepath = Path(f"{self.base_uri}.qmd")
        _ = filepath.write_text(str(self))
