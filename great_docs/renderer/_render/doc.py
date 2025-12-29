from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from functools import cached_property, singledispatchmethod
from typing import TYPE_CHECKING, Literal, cast

import griffe as gf
from quartodoc import ast as qast
from quartodoc import layout
from quartodoc.pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    CodeBlock,
    DefinitionList,
    Div,
    Header,
)
from quartodoc.pandoc.components import Attr
from quartodoc.pandoc.inlines import Code, Inline, Inlines, Link, Span

from .._format import (
    HAS_RUFF,
    format_name,
    format_see_also,
    format_value,
    markdown_escape,
    pretty_code,
    render_formatted_expr,
    repr_obj,
)
from .._pandoc.inlines import InterLink
from .._utils import is_protocol, is_typealias, is_typevar
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quartodoc.pandoc.blocks import DefinitionItem
    from quartodoc.pandoc.inlines import InlineContentItem

    from ..typing import (
        Annotation,
        AnyDocstringSection,
        DocObjectKind,
        SummaryItem,
    )


@dataclass
class __RenderDoc(RenderBase):
    """
    Render a layout.Doc object
    """

    show_title: bool = True
    """
    Whether to show the title of the object

    The title includes:

        1. symbol for the object
        2. name of the object
        3. labels the object

    Each of this can be independently turned off.
    """

    show_signature: bool = True
    """Whether to show the signature"""

    show_signature_name: bool = True
    """Whether to show the name of the object in the signature"""

    show_signature_annotation: bool = False
    """
    Where to show type annotations in the signature

    The default is False because they are better displayed in the
    parameter definitions.
    """

    show_object_name: bool = True
    """
    Whether to show the name of the object

    This is part of the title
    """

    show_object_symbol: bool = True
    """
    Whether to show the symbol of the object

    This is part of the title
    """

    show_object_labels: bool = True
    """
    Whether to show the labels of the object

    This is part of the title
    """

    contained: bool = False
    """
    Whether to this object's documentation will be contained within
    that of another. e.g. a method's documentation is commonly contained
    within that of a class.
    """

    subject_above_signature: bool | None = None
    """
    Place the subject above the signature

    If `bool`, the setting will always be respected.
    If `None` the placement will depend on the context; the preffered
    location will be above the signature but in some cases it will be
    below.
    """

    # page_path: str = field(init=False, repr=False, default="")
    page_path: str = ""
    """
    Name of the page where this object's rendered content
    will be written. It should be the name of the object
    as listed in the quartodoc yaml section. e.g

    Given

    ```yaml
    sections:
      - title: RenderClasses
        - name: base.RenderBase
          package: great_docs.renderer._render
        - RenderDoc
    ```

    `RenderBase` will be written to `*/base.RenderBase.qmd` and
    `RenderDoc` will be written to `*/RenderDoc.qmd`. By default,
    they will also be summarised as `base.RenderBase` and `RenderDoc`.

    If the object isn't listed, e.g the class methods of `RenderDoc`
    this the page_path will be an empty string.
    """

    def __post_init__(self):
        # The layout_obj is too general. It is typed to include all
        # classes of documentable objects. And for layout.Doc objects,
        # the core object is a griffe object contained within.
        # For convenience, we create attributes with narrower types
        # using cast instead of TypeAlias so that subclasses can
        # create narrower types.
        self.doc = cast("layout.Doc", self.layout_obj)
        """Doc Object"""

        self.obj = self.doc.obj
        """Griffe object (or alias)"""

        self.show_signature = self.renderer.show_signature

    @cached_property
    def kind(self) -> DocObjectKind:
        """
        Return the object's kind
        """
        obj = self.obj
        kind = obj.kind.value
        if obj.is_function and obj.parent and obj.parent.is_class:
            kind = "method"
        if kind == "attribute":
            if is_typealias(obj):
                kind = "type"
            elif is_typevar(obj):
                kind = "typevar"
        return kind

    @cached_property
    def labels(self) -> Sequence[str]:
        """
        Return labels for an object (iff object is a function/method)
        """
        # Only check for the labels we care about
        lst = (
            "cached",
            "property",
            "classmethod",
            "staticmethod",
            "abstractmethod",
            "typing.overload",
        )
        if self.obj.is_function or self.obj.is_attribute:
            return tuple(label.replace(".", "-") for label in lst if label in self.obj.labels)
        elif self.obj.is_class and is_protocol(self.obj):
            return ("Protocol",)
        else:
            return ()

    @cached_property
    def display_name(self) -> str:
        format = self.renderer.display_name_format
        if format == "auto":
            format = "full" if self.level == 1 else "name"
        elif format == "relative" and self.level > 1:
            format = "name"
        return markdown_escape(format_name(self.obj, format))

    @cached_property
    def raw_title(self) -> str:
        format = "canonical" if self.level == 1 else "name"
        return markdown_escape(format_name(self.obj, format))

    @cached_property
    def signature_name(self) -> str:
        return format_name(self.obj, self.renderer.signature_name_format)

    def render_description(self) -> BlockContent:
        """
        Render the description of the object

        The descriptions consists of the docstring subject and the
        signature.
        """
        direction = 1 if self.subject_above_signature else -1
        subject_and_signature = [
            self.render_docstring_subject(),
            self.render_signature() if self.show_signature else None,
        ][::direction]
        return Blocks(subject_and_signature)

    def render_signature(self) -> BlockContent:
        """
        Render the signature of the object being documented
        """

    def render_labels(self) -> Span | Literal[""]:
        """
        Create codes used for doc labels

        Given the label names, it returns a Code object that
        creates the following HTML
        <span class="doc-labels">
            <code class="doc-label doc-label-name1"></code>
            <code class="doc-label doc-label-name2"></code>
        </span>
        """
        if not self.labels:
            return ""

        codes = [
            Code(" ", Attr(classes=["doc-label", f"doc-label-{l.lower()}"])) for l in self.labels
        ]
        return Span(codes, Attr(classes=["doc-labels"]))

    def render_annotation(self, annotation: Annotation | None = None) -> str:
        """
        Render an annotation

        This can be used to renderer the annotation of:

            1. self - if it is an Attribute & annotation is None
            2. annotation - annotation of a parameter in the signature
               of self
        """
        if annotation is None:
            if not (
                isinstance(self.obj, gf.Attribute)
                or (isinstance(self.obj, gf.Alias) and self.obj.is_attribute)
            ):
                msg = f"Cannot render annotation for type {type(self.obj)}."
                raise TypeError(msg)

            annotation = self.obj.annotation

        def _render(ann: Annotation | None) -> str | InterLink:
            # Recursively render annotation
            if ann is None:
                return ""
            elif isinstance(ann, str):
                return repr_obj(ann)
            elif isinstance(ann, gf.ExprName):
                return InterLink(markdown_escape(ann.name), ann.canonical_path)
            else:
                assert isinstance(ann, gf.Expr)
                if isinstance(ann, gf.ExprSubscript) and ann.canonical_name == "InitVar":
                    ann = cast("gf.Expr", ann.slice)
                # A type annotation with ~ removes the qualname prefix
                path_str = ann.canonical_path
                if path_str[0] == "~":
                    return InterLink(ann.canonical_name, path_str[1:])
                return "".join(str(_render(a)) for a in ann)

        return pretty_code(str(_render(annotation)))

    def render_variable_definition(
        self,
        name: str | None,
        annotation: str | gf.Expr | None,
        default: str | gf.Expr | None,
    ) -> Inline:
        """
        Create code snippet that declares a variable

        This applies to function parameters and module/class attributes

        Parameters
        ----------
        name :
            Name of the variable
        annotation :
            Type Annotation of the variable or parameter
        default :
            Default value of the variable/parameter.
        """
        items: list[InlineContentItem] = []

        if name:
            items.append(Span(name, Attr(classes=["doc-parameter-name"])))

        if annotation:
            if isinstance(annotation, gf.Expr):
                # NOTE: We have two ways of rendering the annotation.
                # - self.render_annotation: Is more intuitive but when we use it we
                #   cannot format code that may be too wide.
                # - render_formatted_expr: Has more moving parts it needs ruff but it
                #   seems to work well so far.
                annotation = (
                    render_formatted_expr(annotation)
                    if HAS_RUFF and len(str(annotation)) > 79
                    else self.render_annotation(annotation)
                )

            items.extend(
                [
                    Span(":", Attr(classes=["doc-parameter-annotation-sep"])) if name else None,
                    Span(annotation, Attr(classes=["doc-parameter-annotation"])),
                ]
            )

        if default is not None:
            default = (
                render_formatted_expr(default)
                if isinstance(default, gf.Expr)
                else format_value(default)
            )

            # Equal sign and space around it depends on name and annotation
            equals = Span("=", Attr(classes=["doc-parameter-default-sep", "op"])) if name else None
            space = " " if annotation else None
            items.extend(
                [space, equals, space, Span(default, Attr(classes=["doc-parameter-default"]))]
            )
        return Inlines(items)

    def render_title(self) -> BlockContent:
        """
        Render the header of a docstring, including any anchors
        """
        symbol = (
            Code(
                # Pandoc requires some space to create empty code tags
                " ",
                Attr(classes=["doc-symbol", f"doc-symbol-{self.kind}"]),
            )
            if self.show_object_symbol
            else None
        )

        name = (
            Span(
                self.display_name,
                Attr(classes=["doc-object-name", f"doc-{self.kind}-name"]),
            )
            if self.show_object_name
            else None
        )

        labels = self.render_labels() if self.show_object_labels else None

        classes = ["title", "doc-object", f"doc-{self.kind}"]
        if hasattr(self.obj, "members") and self.obj.members:
            classes.append("doc-has-member-docs")

        return Header(
            level=self.level,
            content=Inlines([symbol, name, labels]),
            attr=Attr(identifier=self.obj.path, classes=classes),
        )

    @cached_property
    def docstring_subject(self) -> str | None:
        """
        The first line of docstring
        """
        if (
            self.obj.docstring
            and (sections := self.obj.docstring.parsed)
            and isinstance(sections[0], gf.DocstringSectionText)
        ):
            return self.obj.docstring.value.splitlines()[0]

    def render_docstring_subject(self) -> BlockContent:
        """
        Render the subject of docstring
        """
        return Div(Span(self.docstring_subject), Attr(classes=["doc-subject"]))

    @cached_property
    def docstring_sections_content(self) -> list[tuple[str, AnyDocstringSection]]:
        """
        The sections of the docstring before they are marked up

        Subclasses can override this method to easily peek at the available
        sections, remove, modify, or even add some more.

        Returns
        -------
        :
            List of (title, DocstringSection)
        """
        items: list[tuple[str, AnyDocstringSection]] = []

        if not self.obj.docstring:
            return []

        sections = cast(
            "list[gf.DocstringSection]",
            qast.transform(self.obj.docstring.parsed),  # pyright: ignore[reportUnknownMemberType]
        )

        # Remove the docstring subject from the top of the docstring
        if self.docstring_subject:
            # The sections are cached value that we have to be careful not modify.
            # We modify a copy of first section and we create a new list
            first_section = copy(sections[0])
            first_section.value = "\n".join(first_section.value.splitlines()[1:])
            sections = [first_section, *sections[1:]]

        for i, section in enumerate(sections):
            section_kind: gf.DocstringSectionKind = section.kind
            title = (section.title or section_kind).strip().title()

            if section_kind == "text":
                assert i == 0, f"unexpected text section {section_kind}"

            items.append((title, section))

        return items

    @cached_property
    def docstring_sections(self) -> list[Block]:
        """
        Rendered sections of the docstring.

        Each section is produced by parsing the docstring into titled sections
        and wrapping the section content in markup-generating blocks.
        """
        sections: list[Block] = []
        for title, section in self.docstring_sections_content:
            body = self.render_docstring_section(section) or ""
            slug = title.lower().replace(" ", "-")
            section_classes = [f"doc-{slug}"]
            if title in ("Text", "Deprecated"):
                content = Div(body, Attr(classes=section_classes))
            else:
                header = Header(
                    self.level + 1,
                    title,
                    Attr(classes=section_classes),
                )
                content = Blocks([header, body])
            sections.append(content)
        return sections

    def render_body(self) -> BlockContent:
        """
        Render the docsting of the Doc object
        """
        return None if not self.docstring_sections else Blocks(self.docstring_sections)

    @singledispatchmethod
    def render_docstring_section(self, el: gf.DocstringSection) -> BlockContent:
        """
        Render a section of a docstring

        Parameters
        ----------
        el :
            The section to render

        Notes
        -----
        To render a given type of section differently, register a
        [](`~functools.singledispatchmethod`) method for that type
        of section.
        """
        new_el = qast.transform(el)  # pyright: ignore[reportUnknownMemberType]
        if isinstance(new_el, qast.ExampleCode):
            return CodeBlock(el.value, Attr(classes=["python"]))
        return el.value

    @render_docstring_section.register
    def _(self, el: gf.DocstringSectionExamples):
        return Blocks([self.render_docstring_section(qast.transform(c)) for c in el.value])  # pyright: ignore[reportUnknownMemberType]

    @render_docstring_section.register
    def _(self, el: gf.DocstringSectionDeprecated):
        content = Div(
            Inlines(
                [
                    Span(
                        f"Deprecated since version {el.value.version}:",
                        Attr(classes=["versionmodified", "deprecated"]),
                    ),
                    el.value.description.strip(),
                ]
            ),
            Attr(classes=["doc-deprecated"]),
        )
        return str(content)

    @render_docstring_section.register
    def _(self, el: gf.DocstringSectionAdmonition):
        """
        This catches unofficial numpydoc sections
        """
        return el.value.description

    @render_docstring_section.register
    def _(self, el: qast.DocstringSectionSeeAlso):
        """
        Render See Also section
        """
        content = format_see_also(el.value)
        items: list[DefinitionItem] = []
        for line in content.split("\n"):
            if not line.strip():
                continue
            term, *desc = line.split(":")
            items.append((term, ":".join(desc)))
        return DefinitionList(items)

    @property
    def summary_name(self) -> str:
        """
        The name of object as it will appear in the summary table
        """
        return self.doc.name

    def render_summary(self) -> Sequence[SummaryItem]:
        """
        Return a line item that summarises the object
        """
        # The page where this object will be written
        link = Link(
            markdown_escape(self.summary_name),
            f"{self.page_path}#{self.doc.anchor}",
        )
        return [(str(link), self.docstring_subject)]


class RenderDoc(__RenderDoc):
    """
    Extend rendering of all objects that have docstrings

    These are modules, classes, functions and attributes.
    """
