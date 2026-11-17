"""
Typing-information pages and their inventory entries

Load and prepare a module's own protocols, type variables and type aliases through the
reference, and render them with the same renderers and project context as
the other API pages.
"""

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
from ._rendering._context import _RenderingPurpose, output_page_path
from ._rendering._renderers import Renderers
from ._type_checks import is_protocol, is_typealias, is_typevar

if TYPE_CHECKING:
    from collections.abc import Callable

    from ._customisation import Extension
    from ._settings import Settings
    from .api_reference import APIReference
    from .typing import RenderObjType
    from .write import RenderedPage


@dataclass
class _TypeCategory:
    """One category of typing objects, rendered under its own heading"""

    title: str
    """The category heading"""
    items: list[inventory.InventoryItem]
    """The inventory entries of the category's prepared objects that hooks did not exclude"""
    renderers: list[RenderObjType]
    """One renderer for each entry in `items`"""

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
        output_root: Path | None = None,
        prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None = None,
    ) -> _TypeCategory:
        """
        Prepare a category's objects and create a renderer for each

        Filter semantic exclusions from both renderer and inventory lists. Preserve
        one heading depth and typing presentation purpose for this category; use the
        active operation for appearance context and configured render failures.
        """
        renderers: list[RenderObjType] = []
        retained_items: list[inventory.InventoryItem] = []
        for item in items:
            doc = griffe_to_doc(item.obj, prepare=prepare)
            if doc is None:
                continue
            occurrence = f"{item.name} on {page_path}" if page_path else item.name
            context = extension.error_context("render", occurrence) if extension else nullcontext()
            with context:
                renderer = choices.make(
                    doc,
                    3,
                    settings=settings,
                    _purpose=purpose,
                    extension=extension,
                    output_root=output_root,
                    context_page_path=output_page_path(page_path, output_root),
                )
            renderers.append(renderer)
            retained_items.append(item)
        return cls(title, retained_items, renderers)


@dataclass
class TypeSections(Block):
    """
    The typing categories of one page, with their renderers and inventory entries

    Create protocol, variable and alias categories explicitly. Supplied operation
    preparation shares canonical facts; standalone sections own temporary default
    preparation. Keep the extension open until rendering finishes.
    Empty categories produce no heading and excluded objects produce no inventory item.
    """

    protocols_items: list[inventory.InventoryItem]
    """Candidate protocol inventory entries"""
    typevars_items: list[inventory.InventoryItem]
    """Candidate type-variable inventory entries"""
    typealiases_items: list[inventory.InventoryItem]
    """Candidate type-alias inventory entries"""
    settings: Settings
    """The operation settings used for preparation and presentation"""
    renderers: Renderers = field(default_factory=Renderers, kw_only=True)
    """The renderers selected for every category"""
    extension: Extension | None = field(default=None, kw_only=True)
    """Active owner for renderer failures, or `None` for standalone sections"""
    page_path: str | None = field(default=None, kw_only=True)
    """The typing page's path, which a rendering failure names"""
    output_root: Path | None = field(default=None, kw_only=True)
    """The documentation output root"""

    prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None = field(
        default=None, kw_only=True
    )
    """Operation preparation, or `None` to prepare with the supplied or default owner"""

    def __post_init__(self) -> None:
        """Prepare all category records before their presentation is requested"""
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
                extension=self.extension,
                page_path=self.page_path,
                output_root=self.output_root,
                prepare=self.prepare or extension.prepare,
            ),
            _TypeCategory.make(
                "Type Variables",
                self.typevars_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_VARIABLE,
                extension=self.extension,
                page_path=self.page_path,
                output_root=self.output_root,
                prepare=self.prepare or extension.prepare,
            ),
            _TypeCategory.make(
                "Type Aliases",
                self.typealiases_items,
                self.settings,
                self.renderers,
                _RenderingPurpose.TYPE_ALIAS,
                extension=self.extension,
                page_path=self.page_path,
                output_root=self.output_root,
                prepare=self.prepare or extension.prepare,
            ),
        ]

    def __str__(self) -> str:
        """Render the prepared typing categories as Quarto Markdown"""
        return str(self.render_body())

    @cached_property
    def items(self) -> list[inventory.InventoryItem]:
        """The inventory entries of every category, without excluded objects"""
        return [item for category in self.categories for item in category.items]

    def render_body(self) -> BlockContent:
        """
        Render each non-empty category under its heading

        Returns
        -------
        :
            The category headings, each followed by its rendered objects.
        """
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
    """
    The typing-information page of one module in the documented package

    Acquire and prepare through the active reference before classifying protocols,
    variables and aliases. Re-exported objects from the documented package share
    canonical facts. Collection registers inventory entries and returns source;
    direct writing publishes that one page.
    """

    module_path: str
    """The import path of the typing module to document"""
    api_ref: APIReference
    """The reference that loads, prepares and renders the objects"""

    def __post_init__(self) -> None:
        """Record the reference's package and output directory"""
        self.package = self.api_ref.package
        self.dir = self.api_ref.settings.dir

    def __str__(self) -> str:
        """Render the typing page with the selected renderers"""
        content = self.content
        with self.api_ref.extension.error_context("render", f"{self.base_uri}.qmd"):
            return str(content)

    @cached_property
    def base_uri(self) -> str:
        """
        The typing page's path without a filename suffix

        The path is the module path, relative to the documented package when the module
        is inside it, under the reference directory. It is relative to the working
        directory unless the reference directory is absolute.
        """
        path = self.module_path
        if path.startswith(self.package):
            path = path[len(self.package) + 1 :]
        return f"{self.dir}/{path}"

    def _is_own(self, obj: gf.Object | gf.Alias) -> bool:
        """
        Check whether an object belongs to the documented package

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
        """
        The module's typing categories, prepared once

        Load members with the reference's parser and dynamic setting before sorting them.
        Leave out imports from other packages and objects that object hooks exclude, but
        keep aliases to the package's own objects.
        """

        def make_item(obj: gf.Object | gf.Alias) -> inventory.InventoryItem:
            """Build an `InventoryItem` for a typing object"""
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
            output_root=self.api_ref.output_root,
        )

    @cached_property
    def content(self) -> BlockContent:
        """The typing page: its metadata followed by its categories"""
        meta = Meta({"title": "Typing Information", "body-classes": "doc-api-page doc-py-api-page"})
        return Blocks([meta, self.sections])

    def collect(self) -> RenderedPage:
        """
        Render the typing page without writing it, adding its entries to the inventory

        Render before computing the reference fingerprint so it includes any helpers
        the renderers import.

        Returns
        -------
        :
            The rendered page and the path to write it to.
        """
        from .write import RenderedPage

        content = str(self)
        self.api_ref.items.extend(self.sections.items)
        return RenderedPage(Path(f"{self.base_uri}.qmd"), content)

    def write(self) -> None:
        """Write the typing-information page directly without a final input marker"""
        self.collect().write()
