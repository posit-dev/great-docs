from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, cast

from great_docs.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    Header,
)
from great_docs.pandoc.components import Attr

from .._globals import translate
from .._type_checks import (
    griffe_to_doc,
    is_doc_attribute,
    is_doc_class,
    is_doc_function,
    is_doc_type_alias,
)
from ..content import Doc, DocClass, MemberPage
from ._tables import summary_table
from .doc import RenderDoc

if TYPE_CHECKING:
    from typing import Literal

    import griffe as gf

    from ..content import DocAttribute, DocFunction, DocModule, DocTypeAlias


@dataclass
class RenderedMembersGroup(Block):
    title: Header | None = None
    summary: str | None = None
    members_body: Block | None = None

    def __str__(self):
        return str(Blocks([self.title, self.summary, self.members_body]))


@dataclass
class RenderedMemberPagesGroup(Block):
    title: Header | None = None
    summary: str | None = None

    def __str__(self):
        return str(Blocks([self.title, self.summary]))


@dataclass
class __RenderDocMembersMixin(RenderDoc):
    """
    Mixin to render Doc objects that have members

    i.e. modules and classes
    """

    show_members: bool = True
    """All members (type aliases, attributes, classes and functions) """
    show_attributes: bool = True
    show_classes: bool = True
    show_functions: bool = True
    show_type_aliases: bool = True

    show_members_summary: bool = True
    """All member (type alias, attribute, class and function) summaries"""
    show_attributes_summary: bool = True
    show_classes_summary: bool = True
    show_functions_summary: bool = True
    show_type_aliases_summary: bool = True

    show_members_body: bool = True
    """All member (type alias, attribute, class and function) bodies"""
    show_attributes_body: bool = True
    show_classes_body: bool = True
    show_functions_body: bool = True
    show_type_aliases_body: bool = True

    def __post_init__(self):
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

    def render_members(self) -> list[RenderedMembersGroup | None]:
        """
        Render the docs of member objects

        The member objects are type aliases, attributes, classes and
        functions/methods
        """
        if not self.show_members:
            return []
        return [
            self.render_type_aliases(),
            self.render_attributes(),
            self.render_classes(),
            self.render_functions(),
        ]

    def render_member_pages(self) -> list[RenderedMemberPagesGroup | None]:
        """
        Render the docs of member objects

        The member objects are type aliases, attributes, classes and
        functions/methods
        """
        if not self.show_members:
            return []
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

    def render_classes(self) -> RenderedMembersGroup | None:
        """
        Render the class members of the Doc
        """
        return self._render_members_group("classes") if self.show_classes else None

    def render_functions(self) -> RenderedMembersGroup | None:
        """
        Render the function members of the Doc
        """
        return self._render_members_group("functions") if self.show_functions else None

    def render_attributes(self) -> RenderedMembersGroup | None:
        """
        Render the attribute members of the Doc
        """
        return self._render_members_group("attributes") if self.show_attributes else None

    def render_type_aliases(self) -> RenderedMembersGroup | None:
        """
        Render the type alias members of the Doc
        """
        return self._render_members_group("type-aliases") if self.show_type_aliases else None

    def render_class_member_pages(self) -> RenderedMemberPagesGroup | None:
        """
        Render the member pages of classes
        """
        return self._render_member_pages_group("classes") if self.show_classes else None

    def render_function_member_pages(self) -> RenderedMemberPagesGroup | None:
        """
        Render the member pages of functions
        """
        return self._render_member_pages_group("functions") if self.show_functions else None

    def render_attribute_member_pages(self) -> RenderedMemberPagesGroup | None:
        """
        Render the member pages of attributes
        """
        return self._render_member_pages_group("attributes") if self.show_attributes else None

    def render_type_alias_member_pages(self) -> RenderedMemberPagesGroup | None:
        """
        Render the member pages of type aliases
        """
        return self._render_member_pages_group("type-aliases") if self.show_type_aliases else None

    def _render_members_group(
        self,
        group: Literal["type-aliases", "classes", "functions", "attributes"],
    ) -> RenderedMembersGroup | None:
        """
        Render all of type alias, class, function or attribute members

        Parameters
        ----------
        docables
            List of `content.Doc` subclasses. One for each member.

        member_group
            An identifier for the type of the members.
        """
        from . import RenderDocAttribute, RenderDocClass, RenderDocFunction, RenderDocTypeAlias

        slug = group

        if group == "type-aliases":
            docables, Render = self.type_aliases, RenderDocTypeAlias
            show_summary = self.show_type_aliases_summary
            show_body = self.show_type_aliases_body
        elif group == "classes":
            docables, Render = self.classes, RenderDocClass
            show_summary = self.show_classes_summary
            show_body = self.show_classes_body
        elif group == "attributes":
            docables, Render = self.attributes, RenderDocAttribute
            show_summary = self.show_attributes_summary
            show_body = self.show_attributes_body
        else:
            docables, Render = self.functions, RenderDocFunction
            show_summary = self.show_functions_summary
            show_body = self.show_functions_body
            if isinstance(self.doc, DocClass):
                slug = "methods"

        if not docables:
            return None

        title = Header(
            self.level + 1,
            translate(slug.replace("-", "_")),
            Attr(classes=[f"doc-{slug}"]),
        )

        render_objs = [Render(obj, self.level + 2, contained=True) for obj in docables]

        if self.show_members_summary and show_summary:
            rows = [row for r in render_objs for row in r.render_summary()]
            summary = summary_table(rows)
        else:
            summary = None

        body = Blocks(render_objs) if show_body else None
        return RenderedMembersGroup(title, summary, body)

    def _render_member_pages_group(
        self,
        group: Literal["type-aliases", "classes", "functions", "attributes"],
    ) -> RenderedMemberPagesGroup | None:
        """
        Render all of the type alias, class, function or attribute member pages

        Parameters
        ----------
        docables
            List of `content.Doc` subclasses. One for each member.

        member_group
            An identifier for the type of the members.
        """
        from . import RenderDocAttribute, RenderDocClass, RenderDocFunction, RenderDocTypeAlias

        slug = group

        if group == "type-aliases":
            pages, Render = self.type_alias_member_pages, RenderDocTypeAlias
            show_summary = self.show_type_aliases_summary
        elif group == "classes":
            pages, Render = self.class_member_pages, RenderDocClass
            show_summary = self.show_classes_summary
        elif group == "attributes":
            pages, Render = self.attribute_member_pages, RenderDocAttribute
            show_summary = self.show_attributes_summary
        else:
            pages, Render = self.function_member_pages, RenderDocFunction
            show_summary = self.show_functions_summary
            if isinstance(self.doc, DocClass):
                slug = "functions"

        if not pages:
            return None

        title = Header(
            self.level + 1,
            translate(slug.replace("-", "_")),
            Attr(classes=[f"doc-{slug}", "doc-pages"]),
        )

        render_objs = [
            Render(
                griffe_to_doc(page.obj, deep=False),
                contained=False,
                page_path=f"{page.path}.qmd",
            )
            for page in pages
        ]

        if self.show_members_summary and show_summary:
            rows = [row for r in render_objs for row in r.render_summary()]
            summary = summary_table(rows)
        else:
            summary = None

        return RenderedMemberPagesGroup(title, summary)

    def render_attributes_section(self, el: gf.DocstringSectionAttributes) -> BlockContent:
        """
        Render an `Attributes` section

        Only an object with members — a class or a module — can have
        attributes to describe.
        """
        return self.render_definition_items(el)


class RenderDocMembersMixin(__RenderDocMembersMixin, RenderDoc):
    """
    Extension point for the rendering of objects that have members
    """
