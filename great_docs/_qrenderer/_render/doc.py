from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from functools import cached_property, singledispatchmethod
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs._qrenderer._render._label import get_label

from .. import _ast as qast
from .. import layout
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
from .._rst_converters import _convert_rst_text
from .._type_checks import package_info
from ..pandoc.blocks import (
    Block,
    BlockContent,
    Blocks,
    CodeBlock,
    DefinitionList,
    Div,
    Header,
    InlineContent,
    Para,
)
from ..pandoc.components import Attr
from ..pandoc.inlines import Inline, Inlines, Inlines0, Link, Span
from .base import RenderBase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..pandoc.blocks import DefinitionItem
    from ..pandoc.inlines import InlineContentItem
    from ..typing import (
        Annotation,
        AnyDocstringSection,
        DisplayNameFormat,
        DocObjectKind,
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
    as listed in the great_docs._renderer yaml section. e.g

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

    show_source_link: bool = True
    """Whether to show a link to the source code"""

    display_name_format: DisplayNameFormat = "doc"
    """Format for the display name"""

    signature_name_format: DisplayNameFormat = "doc"
    """Format for the signature name"""

    def __post_init__(self):
        # The layout_obj is too general. It is typed to include all
        # classes of documentable objects. And for layout.Doc objects,
        # the core object is a griffe object contained within.
        # For convenience, we create attributes with narrower types
        # using cast instead of TypeAlias so that subclasses can
        # create narrower types.
        self.doc = cast("layout.Doc", self.layout_obj)
        """Doc Object"""

        self.obj = cast("gf.Object | gf.Alias", self.doc.obj)
        """Griffe object (or alias)"""

    @cached_property
    def kind(self) -> DocObjectKind:
        """
        Return the object's kind

        class, function, method, property, attribute, module, alias
        """
        return self.obj.kind.value

    @cached_property
    def label(self) -> str:
        """
        Return a label for the object
        """
        return get_label(self.obj).lower()

    @cached_property
    def display_name(self) -> str:
        format = self.display_name_format
        if format == "relative" and self.level > 1:
            format = "name"
        name = format_name(self.doc, format)

        # Append () to callable objects (functions, methods) to match classic
        # renderer behavior and user expectations
        if self.kind == "function":
            name += "()"

        return markdown_escape(name)

    @cached_property
    def signature_name(self) -> str:
        return format_name(self.doc, self.signature_name_format)

    def render_description(self) -> BlockContent:
        """
        Render the description of the object

        The descriptions consists of the docstring subject and the
        signature.
        """
        direction = 1 if self.subject_above_signature else -1
        subject_and_signature = [
            self.render_docstring_subject(),
            self.render_usage_source(),
            self.render_signature() if self.show_signature else None,
        ][::direction]
        return Blocks(subject_and_signature)

    def render_signature(self) -> BlockContent:
        """
        Render the signature of the object being documented
        """

    @cached_property
    def _title(self) -> InlineContent:
        return Span(
            self.display_name,
            Attr(
                classes=[
                    "doc-object-name",
                    f"doc-{self.kind}",
                    "doc-label",
                    f"doc-label-{self.label}",
                ],
            ),
        )

    def render_title(self) -> BlockContent:
        """
        Render the header of a docstring, including any anchors

        The title includes markup for labels You can style it with CSS or override
        this method to output something different.


        Markup and Styling
        ------------------
        Create markup that includes the name of the object and labels that apply to it.
        e.g.

        ```html
        <h2>
            <span class="doc-object-name doc-attribute doc-label doc-label-property">
                SomeClass.value
            </span>
        </h2>
        ```

        You can target these classes in main content (with `.content`) or the sidebar
        with (`.sidebar`). The markup for the labels is not rendered if there are no
        labels. If there is more than one label, each label has its own class code.
        """
        return Header(level=self.level, content=self._title)

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

        def _render(ann: Annotation | None) -> str:
            # Recursively render annotation as plain text (no links)
            if ann is None:
                return ""
            elif isinstance(ann, str):
                return repr_obj(ann)
            elif isinstance(ann, gf.ExprName):
                return markdown_escape(ann.name)
            else:
                assert isinstance(ann, gf.Expr)
                if isinstance(ann, gf.ExprSubscript) and ann.canonical_name == "InitVar":
                    ann = cast("gf.Expr", ann.slice)
                # A type annotation with ~ removes the qualname prefix
                path_str = ann.canonical_path
                if path_str[0] == "~":
                    return ann.canonical_name
                return "".join(_render(a) for a in ann)

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
                    " ",
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
        return Inlines0(items)

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
        return Div(Para(self.docstring_subject), Attr(classes=["doc-subject"]))

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
            if not body:
                continue
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
        return _convert_rst_text(el.value)

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
        return _convert_rst_text(el.value.description)

    @render_docstring_section.register
    def _(self, el: qast.DocstringSectionWarnings):
        return _convert_rst_text(el.value)

    @render_docstring_section.register
    def _(self, el: qast.DocstringSectionNotes):
        return _convert_rst_text(el.value)

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
        name = self.doc.name
        # Append () to callable objects in summary tables
        if self.kind == "function":
            name += "()"
        return name

    def render_summary(self) -> Sequence[DefinitionItem]:
        """
        Return a line item that summarises the object

        Markup and Styling
        ------------------

        | HTML Elements   | CSS Selector                                              |
        |:----------------|:----------------------------------------------------------|
        | `<a>`{.html}    | `.doc-index .doc-group > dl dt > a.doc-{kind}-name`{.css} |
        | `<p>`{.html}    | `.doc-index .doc-group > dl dd > p`{.css}                 |

        See Also
        --------
        great_docs.renderer.RenderReferenceSection.render_body : For more context about
        where the rendered link and text are placed.
        """
        # The page where this object will be written
        # For contained members (e.g. methods within a class page), use the
        # short name as anchor since Quarto generates section IDs from heading
        # text (e.g. "get" not "package.ClassName.get").
        anchor = self.doc.name if self.contained else self.doc.anchor
        link = Link(
            markdown_escape(self.summary_name),
            f"{self.page_path}#{anchor}",
            attr=Attr(classes=[f"doc-{self.kind}", "doc-label", f"doc-label-{self.label}"]),
        )
        return [(str(link), self.docstring_subject)]

    def render_usage_source(self) -> BlockContent:
        """
        Row with usage and source
        """
        source = self.source_link if self.show_source_link else None
        return Div(
            ["Usage", source],
            attr=Attr(classes=["doc-usage-source"]),
        )

    @cached_property
    def source_link(self) -> Link | None:
        """
        Link to source code where the object is described
        """
        base_url = package_info("GITHUB_REPO_URL")
        if not base_url or base_url == "None":
            return None
        branch = package_info("GIT_REF")
        relative_path = self.obj.relative_package_filepath
        start, end = self.obj.lineno, self.obj.endlineno
        anchor = f"#L{start}-L{end}" if start != end else f"#L{start}"
        url = f"{base_url}/blob/{branch}/{relative_path}{anchor}"
        return Link("Source", url, attr=Attr(attributes={"target": "_blank", "rel": "noopener"}))


class RenderDoc(__RenderDoc):
    """
    Extend rendering of all objects that have docstrings

    These are modules, classes, functions and attributes.
    """
