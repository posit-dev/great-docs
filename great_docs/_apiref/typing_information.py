from __future__ import annotations

from contextlib import nullcontext
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

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._customisation import Extension
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
        *,
        extension: Extension | None = None,
        page_path: str | None = None,
        prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None = None,
    ) -> _TypeCategory:
        """Construct category renderers using the typing workflow's presentation"""
        renderers: list[RenderObjType] = []
        retained_items: list[inventory.InventoryItem] = []
        for item in items:
            doc = griffe_to_doc(item.obj, prepare=prepare)
            if doc is None:
                continue
            occurrence = f"{item.name} on {page_path}" if page_path else item.name
            context = extension.error_context("render", occurrence) if extension else nullcontext()
            with context:
                renderer = choices.make(doc, 3, settings=settings, _purpose=purpose)
            renderers.append(renderer)
            retained_items.append(item)
        return cls(title, retained_items, renderers)


@dataclass
class TypeSections(Block):
    protocols_items: list[inventory.InventoryItem]
    typevars_items: list[inventory.InventoryItem]
    typealiases_items: list[inventory.InventoryItem]
    settings: Settings
    renderers: Renderers = field(default_factory=Renderers, kw_only=True)
    extension: Extension | None = field(default=None, kw_only=True)
    """Active owner for renderer failures, or `None` for standalone sections"""
    page_path: str | None = field(default=None, kw_only=True)
    """The typing page's path, which a rendering failure names"""

    prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None = field(
        default=None, kw_only=True
    )
    """Operation preparation, or `None` to prepare with the supplied or default owner"""

    def __post_init__(self) -> None:
        from ._customisation import Extension

        extension = self.extension or Extension(self.settings)
        try:
            extension.load()
            self.categories = self._make_categories(extension)
        finally:
            if self.extension is None:
                extension.close()

    def _make_categories(self, extension: Extension) -> list[_TypeCategory]:
        """Prepare all categories through one shared operation owner"""
        return [
            _TypeCategory.make(
                "Protocols",
                self.protocols_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.PROTOCOL,
                extension=extension,
                page_path=self.page_path,
                prepare=self.prepare or extension.prepare,
            ),
            _TypeCategory.make(
                "Type Variables",
                self.typevars_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_VARIABLE,
                extension=extension,
                page_path=self.page_path,
                prepare=self.prepare or extension.prepare,
            ),
            _TypeCategory.make(
                "Type Aliases",
                self.typealiases_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_ALIAS,
                extension=extension,
                page_path=self.page_path,
                prepare=self.prepare or extension.prepare,
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
        content = self.content
        with self.api_ref.extension.error_context("render", f"{self.base_uri}.qmd"):
            return str(content)

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

        module = self.api_ref.prepare(self.api_ref.get_object(self.module_path))
        members: list[gf.Object | gf.Alias] = []
        for member in list(module.members.values()) if module is not None else ():
            if not self._is_own(member):
                continue
            candidate = (
                self.api_ref.get_object(f"{self.module_path}:{member.name}")
                if self.api_ref.settings.dynamic
                else member
            )
            prepared = self.api_ref.prepare(candidate)
            if prepared is not None:
                members.append(prepared)
        return TypeSections(
            protocols_items=[make_item(m) for m in members if is_protocol(m)],
            typevars_items=[make_item(m) for m in members if is_typevar(m)],
            typealiases_items=[make_item(m) for m in members if is_typealias(m)],
            settings=self.api_ref.settings,
            renderers=self.api_ref.renderers,
            extension=self.api_ref.extension,
            page_path=f"{self.base_uri}.qmd",
            prepare=self.api_ref.prepare,
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
