"""
Typing-information pages and their inventory entries

Load and prepare a module's own protocols, type variables and type aliases through the
reference, and render them with the same renderers and project context as
the other API pages.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
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
        purpose: _RenderingPurpose,
        *,
        choices: Renderers,
        extension: Extension,
        page_path: str | None,
        prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None],
    ) -> _TypeCategory:
        """
        Prepare a category's objects and create a renderer for each

        Leave out the objects that object hooks exclude, from both the renderers and the
        inventory entries. Every object in the category renders at the same heading level
        and for the same purpose.

        Parameters
        ----------
        title
            The category heading.
        items
            Candidate objects and their typing-page inventory destinations.
        purpose
            How every object in the category is presented.
        choices
            The renderers selected for the category's objects.
        extension
            The extension, which supplies the render context and names the object in a
            rendering failure.
        page_path
            The typing page's path, or `None` when it is unknown.
        prepare
            The function that prepares each candidate object.

        Returns
        -------
        :
            The category with the entries that hooks did not exclude and one renderer for
            each.
        """
        context_page_path = output_page_path(page_path, extension.output_root)
        renderers: list[RenderObjType] = []
        retained_items: list[inventory.InventoryItem] = []
        for item in items:
            doc = griffe_to_doc(item.obj, prepare=prepare)
            if doc is None:
                continue
            occurrence = f"{item.name} on {page_path}" if page_path else item.name
            with extension.error_context("render", occurrence):
                renderer = choices.make(
                    doc,
                    3,
                    extension=extension,
                    context_page_path=context_page_path,
                    _purpose=purpose,
                )
            renderers.append(renderer)
            retained_items.append(item)
        return cls(title, retained_items, renderers)


@dataclass
class TypeSections(Block):
    """
    The typing categories of one page, with their renderers and inventory entries

    The protocols, type variables and type aliases are prepared when the sections are
    created. Keep the extension open until rendering finishes so custom renderers can
    import project helpers. An empty category gets no heading, and an excluded object
    gets no inventory entry.
    """

    protocols_items: list[inventory.InventoryItem]
    """Candidate protocol inventory entries"""
    typevars_items: list[inventory.InventoryItem]
    """Candidate type-variable inventory entries"""
    typealiases_items: list[inventory.InventoryItem]
    """Candidate type-alias inventory entries"""
    renderers: Renderers = field(default_factory=Renderers, kw_only=True)
    """The renderers selected for every category"""
    extension: Extension = field(kw_only=True)
    """
    The extension that supplies settings and prepares objects by default
    """
    page_path: str | None = field(default=None, kw_only=True)
    """The typing page's path, which a rendering failure names"""

    prepare: InitVar[Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None] = field(
        default=None, kw_only=True
    )
    """The reference's preparation function, or `None` to use the extension's"""

    def __post_init__(
        self, prepare: Callable[[gf.Object | gf.Alias], gf.Object | gf.Alias | None] | None
    ) -> None:
        """
        Prepare every category's objects before any of them is rendered

        Parameters
        ----------
        prepare :
            The reference's preparation function, or `None` to use the extension's.
        """
        prepare = prepare or self.extension.prepare
        categories = (
            ("Protocols", self.protocols_items, _RenderingPurpose.PROTOCOL),
            ("Type Variables", self.typevars_items, _RenderingPurpose.TYPE_VARIABLE),
            ("Type Aliases", self.typealiases_items, _RenderingPurpose.TYPE_ALIAS),
        )
        self.categories = [
            _TypeCategory.make(
                title,
                items,
                purpose,
                choices=self.renderers,
                extension=self.extension,
                page_path=self.page_path,
                prepare=prepare,
            )
            for title, items, purpose in categories
        ]
        """The protocol, type-variable and type-alias categories, in that order"""

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

    Load and prepare the module's members through the reference before sorting them into
    protocols, type variables and type aliases. An object that the module re-exports from
    elsewhere in the package shares its prepared documentation with its other names.
    `collect` adds the page's inventory entries and returns the page without writing it.
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
            renderers=self.api_ref.renderers,
            extension=self.api_ref.extension,
            page_path=f"{self.base_uri}.qmd",
            prepare=self.api_ref.prepare,
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
