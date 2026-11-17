"""
Member groups of classes and modules

Members are grouped by kind. A group documents its members on the same page or
links to their own pages. Its summary and body render through separate methods,
a group with neither is omitted, and hidden members stay in the inventory.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, cast

from great_docs._translations import translate
from great_docs.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    Header,
)
from great_docs.pandoc.components import Attr

from .._type_checks import (
    is_doc_attribute,
    is_doc_class,
    is_doc_function,
    is_doc_type_alias,
)
from ..content import Doc, DocClass, MemberPage
from ._context import _RenderingPurpose
from ._tables import summary_table
from .objects import ObjectRenderer

if TYPE_CHECKING:
    from typing import Literal

    import griffe as gf

    from ..content import DocAttribute, DocFunction, DocModule, DocTypeAlias


@dataclass
class RenderedMemberGroup(Block):
    """
    A rendered member group, with its heading, summary and body

    A group of members on their own pages has only a summary. A group of members
    documented on the same page may have a summary, a body or both. A group with
    neither is omitted, so no empty heading remains.
    """

    title: Header | None = None
    """The group heading"""
    summary: BlockContent = None
    """The members' summary table, or `None` to omit it"""
    body: BlockContent = None
    """The documentation of members on the same page, or `None` for a summary-only group"""

    def __str__(self) -> str:
        """Compose the group heading, summary and optional body as Quarto Markdown"""
        return str(Blocks([self.title, self.summary, self.body]))


@dataclass
class MembersRendererMixin(ObjectRenderer):
    """
    The member groups of a class or module

    The groups follow the docstring body. A group of members on the same page shows a
    summary and each member's documentation; a group of members on their own pages
    shows only summary links. A method per kind renders each group, and
    `render_members_summary` and `render_members_body` render its parts. Hiding a
    group or its parts leaves the members in the reference.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to a class or module"""
        super().__post_init__()
        self.doc = cast("DocClass | DocModule", self.doc)  # pyright: ignore[reportUnnecessaryCast]
        self.obj = cast("gf.Class | gf.Module", self.obj)  # pyright: ignore[reportUnnecessaryCast]

    def render_body(self) -> BlockContent:
        """
        Render the docstring body followed by the member groups

        Members on the same page get their full documentation; members on their own
        pages get summary links.
        """
        docstring = super().render_body()

        if not self.doc.members:
            return docstring

        item = self.doc.members[0]
        # A parent's members are either all `Doc` nodes or all `MemberPage` nodes.
        if isinstance(item, Doc):  # pyright: ignore[reportUnnecessaryIsInstance]
            members = self.render_members()
        elif isinstance(item, MemberPage):  # pyright: ignore[reportUnnecessaryIsInstance]
            members = self.render_member_pages()
        else:
            raise ValueError(f"Cannot render members of type {type(item)}")

        return Blocks([docstring, *members])

    def render_members(self) -> list[RenderedMemberGroup | None]:
        """
        Render the groups of members documented on this page

        The groups are type aliases, attributes, classes, then functions or methods.
        Override one group's method to omit or replace only that group.
        """
        return [
            self.render_type_aliases(),
            self.render_attributes(),
            self.render_classes(),
            self.render_functions(),
        ]

    def render_member_pages(self) -> list[RenderedMemberGroup | None]:
        """
        Render the groups of links to members on their own pages

        The groups are type aliases, attributes, classes, then functions or methods.
        They show summary rows only, without member bodies.
        """
        return [
            self.render_type_alias_member_pages(),
            self.render_attribute_member_pages(),
            self.render_class_member_pages(),
            self.render_function_member_pages(),
        ]

    @cached_property
    def attributes(self) -> list[DocAttribute]:
        """The members that are attributes"""
        return [x for x in self.doc.members if is_doc_attribute(x)]

    @cached_property
    def classes(self) -> list[DocClass]:
        """The members that are classes"""
        return [x for x in self.doc.members if is_doc_class(x)]

    @cached_property
    def functions(self) -> list[DocFunction]:
        """The members that are functions or methods"""
        return [x for x in self.doc.members if is_doc_function(x)]

    @cached_property
    def type_aliases(self) -> list[DocTypeAlias]:
        """The members that are PEP 695 type aliases"""
        return [x for x in self.doc.members if is_doc_type_alias(x)]

    @cached_property
    def attribute_member_pages(self) -> list[MemberPage]:
        """The attribute members documented on their own pages"""
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_attribute]

    @cached_property
    def class_member_pages(self) -> list[MemberPage]:
        """The class members documented on their own pages"""
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_class]

    @cached_property
    def function_member_pages(self) -> list[MemberPage]:
        """The function or method members documented on their own pages"""
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_function]

    @cached_property
    def type_alias_member_pages(self) -> list[MemberPage]:
        """The type-alias members documented on their own pages"""
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_type_alias]

    def render_classes(self) -> RenderedMemberGroup | None:
        """Render the group of classes documented on this page, or return `None` to omit it"""
        return self._render_members_group("classes")

    def render_functions(self) -> RenderedMemberGroup | None:
        """Render the group of functions or methods on this page, or return `None` to omit it"""
        return self._render_members_group("functions")

    def render_attributes(self) -> RenderedMemberGroup | None:
        """Render the group of attributes documented on this page, or return `None` to omit it"""
        return self._render_members_group("attributes")

    def render_type_aliases(self) -> RenderedMemberGroup | None:
        """Render the group of type aliases on this page, or return `None` to omit it"""
        return self._render_members_group("type-aliases")

    def render_class_member_pages(self) -> RenderedMemberGroup | None:
        """Render links to classes on their own pages, or return `None` to omit them"""
        return self._render_member_pages_group("classes")

    def render_function_member_pages(self) -> RenderedMemberGroup | None:
        """Render links to functions or methods on their own pages, or return `None` to omit them"""
        return self._render_member_pages_group("functions")

    def render_attribute_member_pages(self) -> RenderedMemberGroup | None:
        """Render links to attributes on their own pages, or return `None` to omit them"""
        return self._render_member_pages_group("attributes")

    def render_type_alias_member_pages(self) -> RenderedMemberGroup | None:
        """Render links to type aliases on their own pages, or return `None` to omit them"""
        return self._render_member_pages_group("type-aliases")

    def _render_members_group(
        self,
        group: Literal["type-aliases", "classes", "functions", "attributes"],
    ) -> RenderedMemberGroup | None:
        """Build the group of members of one kind documented on this page"""
        members = {
            "type-aliases": self.type_aliases,
            "classes": self.classes,
            "attributes": self.attributes,
            "functions": self.functions,
        }[group]
        member_renderers: list[ObjectRenderer] = [
            self.renderers.make(
                obj,
                self.level + 2,
                contained=True,
                page_path=self.page_path,
                settings=self.settings,
                extension=self.extension,
                output_root=self.output_root,
                context_page_path=self.context_page_path,
                _purpose=_RenderingPurpose.OBJECT,
            )
            for obj in members
        ]
        return self._render_group(group, member_renderers, separate=False)

    def _render_member_pages_group(
        self,
        group: Literal["type-aliases", "classes", "functions", "attributes"],
    ) -> RenderedMemberGroup | None:
        """Build the group of links to members of one kind on their own pages"""
        pages = {
            "type-aliases": self.type_alias_member_pages,
            "classes": self.class_member_pages,
            "attributes": self.attribute_member_pages,
            "functions": self.function_member_pages,
        }[group]
        member_renderers: list[ObjectRenderer] = [
            self.renderers.make(
                Doc.from_griffe(page.obj.name, page.obj, anchor=""),
                contained=False,
                page_path=f"{page.path}.qmd",
                settings=self.settings,
                extension=self.extension,
                output_root=self.output_root,
                context_page_path=self.context_page_path,
            )
            for page in pages
        ]
        return self._render_group(group, member_renderers, separate=True)

    def _render_group(
        self,
        kind: Literal["type-aliases", "classes", "functions", "attributes"],
        member_renderers: list[ObjectRenderer],
        *,
        separate: bool,
    ) -> RenderedMemberGroup | None:
        """Build a member group with its heading, or return `None` when it has no content"""
        if not member_renderers:
            return None
        summary = self.render_members_summary(kind, member_renderers)
        body = None if separate else self.render_members_body(kind, member_renderers)
        if summary is None and body is None:
            return None
        slug = (
            "methods"
            if kind == "functions" and isinstance(self.doc, DocClass) and not separate
            else kind
        )
        classes = [f"doc-{slug}", "doc-pages"] if separate else [f"doc-{slug}"]
        title = Header(
            self.level + 1,
            translate(slug.replace("-", "_"), self.settings.lang),
            Attr(classes=classes),
        )
        return RenderedMemberGroup(title, summary, body)

    def render_members_summary(
        self,
        kind: Literal["type-aliases", "classes", "functions", "attributes"],
        renderers: list[ObjectRenderer],
    ) -> BlockContent:
        """
        Render the summary table of a member group

        Parameters
        ----------
        kind
            The kind of member in the group.
        renderers
            The renderers of the group's members.

        Returns
        -------
        :
            The summary table, or `None` to omit it; the members stay in the reference.
            Pages for typing protocols omit the summary but keep the members'
            documentation.
        """
        if self._purpose is _RenderingPurpose.PROTOCOL:
            return None
        rows = [row for renderer in renderers for row in renderer.render_summary()]
        return summary_table(rows, self.settings.lang) if rows else None

    def render_members_body(
        self,
        kind: Literal["type-aliases", "classes", "functions", "attributes"],
        renderers: list[ObjectRenderer],
    ) -> BlockContent:
        """
        Render the documentation of a group's members on this page

        Parameters
        ----------
        kind
            The kind of member in the group.
        renderers
            The renderers of the group's members, which share this page's context.

        Returns
        -------
        :
            The members' documentation, or `None` to omit it; the members stay in the
            reference. Groups of members on their own pages have no body.
        """
        return Blocks(renderers) if renderers else None

    def render_attributes_section(self, el: gf.DocstringSectionAttributes) -> BlockContent:
        """Render an `Attributes` section"""
        return self.render_definition_items(el)
