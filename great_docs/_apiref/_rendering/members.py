"""Grouped member summaries and bodies for classes and modules"""

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
    """A member heading with independently optional summary and body"""

    title: Header | None = None
    """The group heading"""
    summary: BlockContent = None
    """The members' summary table, or `None` to omit it"""
    body: BlockContent = None
    """The documentation of members on the same page, or `None` for a summary-only group"""

    def __str__(self) -> str:
        return str(Blocks([self.title, self.summary, self.body]))


@dataclass
class MembersRendererMixin(ObjectRenderer):
    """
    Grouped member summaries and bodies for classes and modules

    i.e. modules and classes
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self.doc = cast("DocClass | DocModule", self.doc)  # pyright: ignore[reportUnnecessaryCast]
        self.obj = cast("gf.Class | gf.Module", self.obj)  # pyright: ignore[reportUnnecessaryCast]

    def render_body(self) -> BlockContent:
        """
        Render the docstring and member docs
        """
        docstring = super().render_body()

        if not self.doc.members:
            return docstring

        item = self.doc.members[0]
        # TODO: Look into these instance checks, confirm that we can have different types
        # and fix the typing.
        if isinstance(item, Doc):  # pyright: ignore[reportUnnecessaryIsInstance]
            members = self.render_members()
        elif isinstance(item, MemberPage):  # pyright: ignore[reportUnnecessaryIsInstance]
            members = self.render_member_pages()
        else:
            raise ValueError(f"Cannot render members of type {type(item)}")

        return Blocks([docstring, *members])

    def render_members(self) -> list[RenderedMemberGroup | None]:
        """
        Render the docs of member objects

        The member objects are type aliases, attributes, classes and
        functions/methods
        """
        return [
            self.render_type_aliases(),
            self.render_attributes(),
            self.render_classes(),
            self.render_functions(),
        ]

    def render_member_pages(self) -> list[RenderedMemberGroup | None]:
        """
        Render the docs of member objects

        The member objects are type aliases, attributes, classes and
        functions/methods
        """
        return [
            self.render_type_alias_member_pages(),
            self.render_attribute_member_pages(),
            self.render_class_member_pages(),
            self.render_function_member_pages(),
        ]

    @cached_property
    def attributes(self) -> list[DocAttribute]:
        """
        Members that are attributes

        For a module, this will be the objects at the top level that
        are not classes or functions.
        """
        return [x for x in self.doc.members if is_doc_attribute(x)]

    @cached_property
    def classes(self) -> list[DocClass]:
        """
        Members that are classes

        For a module, this will be the classes at the top level.
        For a class, this will be the nested classes e.g. classes
        B and C below:

        ```python
        class A:

            class B:
                pass

            class C:
                pass
        ```
        """
        return [x for x in self.doc.members if is_doc_class(x)]

    @cached_property
    def functions(self) -> list[DocFunction]:
        """
        Members that are functions

        For a module, this will be functions at the top level.
        For a class, this will be the instance methods, static methods
        and class methods.
        """
        return [x for x in self.doc.members if is_doc_function(x)]

    @cached_property
    def type_aliases(self) -> list[DocTypeAlias]:
        """
        Members that are PEP 695 type aliases
        """
        return [x for x in self.doc.members if is_doc_type_alias(x)]

    @cached_property
    def attribute_member_pages(self) -> list[MemberPage]:
        """
        Member pages of attributes

        For a module, this will be the objects at the top level that
        are not classes or functions.
        """
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_attribute]

    @cached_property
    def class_member_pages(self) -> list[MemberPage]:
        """
        Member pages of classes
        """
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_class]

    @cached_property
    def function_member_pages(self) -> list[MemberPage]:
        """
        Member pages of functions
        """
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_function]

    @cached_property
    def type_alias_member_pages(self) -> list[MemberPage]:
        """
        Member pages of type aliases
        """
        pages = cast("list[MemberPage]", self.doc.members)
        return [p for p in pages if p.obj.is_type_alias]

    def render_classes(self) -> RenderedMemberGroup | None:
        """
        Render the class members of the Doc
        """
        return self._render_members_group("classes")

    def render_functions(self) -> RenderedMemberGroup | None:
        """
        Render the function members of the Doc
        """
        return self._render_members_group("functions")

    def render_attributes(self) -> RenderedMemberGroup | None:
        """
        Render the attribute members of the Doc
        """
        return self._render_members_group("attributes")

    def render_type_aliases(self) -> RenderedMemberGroup | None:
        """
        Render the type alias members of the Doc
        """
        return self._render_members_group("type-aliases")

    def render_class_member_pages(self) -> RenderedMemberGroup | None:
        """
        Render the member pages of classes
        """
        return self._render_member_pages_group("classes")

    def render_function_member_pages(self) -> RenderedMemberGroup | None:
        """
        Render the member pages of functions
        """
        return self._render_member_pages_group("functions")

    def render_attribute_member_pages(self) -> RenderedMemberGroup | None:
        """
        Render the member pages of attributes
        """
        return self._render_member_pages_group("attributes")

    def render_type_alias_member_pages(self) -> RenderedMemberGroup | None:
        """
        Render the member pages of type aliases
        """
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
        Render links and descriptions for embedded or separately documented members

        Return `None` to omit the summary without changing semantic membership.
        Typing protocol pages omit their member summary by default.
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

        Return `None` to omit the body without changing semantic membership.
        Separate-page groups never call this method.
        """
        return Blocks(renderers) if renderers else None

    def render_attributes_section(self, el: gf.DocstringSectionAttributes) -> BlockContent:
        """
        Render an `Attributes` section

        Only an object with members — a class or a module — can have
        attributes to describe.
        """
        return self.render_definition_items(el)
