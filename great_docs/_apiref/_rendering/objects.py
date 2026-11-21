"""
Presentation of prepared Python objects and their docstring sections

Render an object's heading, subject, signature, docstring sections and summary
row. Rendering leaves the prepared documentation unchanged because every appearance
of the object shares it.
"""

from __future__ import annotations

import logging
import re
from copy import copy
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs._apiref._rendering._label import get_label
from great_docs._translations import translate, translate_versioned
from great_docs.pandoc.blocks import (
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
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code, Inline, Inlines, Inlines0, Link, Span

from .. import content
from .._docstring_sections import (
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
    ExampleCode,
    ExampleText,
    transform,
    transform_sections,
)
from .._docstring_summary import summary_lines
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
from ._context import RenderContext, _RenderingPurpose
from ._section_dispatch import SECTION_METHOD
from ._source_links import source_link
from .base import BaseRenderer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from great_docs.pandoc.blocks import DefinitionItem
    from great_docs.pandoc.inlines import InlineContentItem

    from ..typing import (
        Annotation,
        AnyDocstringSection,
        DisplayNameFormat,
        DocObjectKind,
        DocstringDefinitionType,
        DocstringSectionWithDefinitions,
    )

_log = logging.getLogger(__name__)

# Translate standard docstring section titles and preserve custom titles.
_SECTION_TITLE_KEYS = {
    "Parameters": "parameters",
    "Returns": "returns",
    "Raises": "raises",
    "Examples": "examples",
    "Notes": "notes",
    "Attributes": "attributes",
    "Methods": "methods",
    "See Also": "see_also",
    "Warnings": "warnings_section",
    "References": "references_section",
}


@dataclass
class ObjectRenderer(BaseRenderer):
    """
    The presentation of one prepared Python object or authored alias

    The heading, lead content and body each have their own render method. Each
    object kind sets the order of its signature and subject, and kinds with members
    add member groups after the object's own docstring. Use `context` to customise
    a particular appearance.
    """

    _purpose: _RenderingPurpose = field(default=_RenderingPurpose.OBJECT, kw_only=True)

    contained: bool = False
    """
    Whether this object is documented inside another object's documentation

    A contained member's summary row links to its heading on the same page, and its
    `context` reports the containing page.
    """

    page_path: str | None = None
    """
    The page that this object's summary row links to

    API pages supply a path relative to the reference directory. `None` links within
    the current page, and contained members always link to a local anchor.
    For the containing page relative to the output directory, use `context.page_path`.
    """

    display_name_format: DisplayNameFormat = "doc"
    """Format for the display name"""

    signature_name_format: DisplayNameFormat = "doc"
    """Format for the signature name"""

    def __post_init__(self) -> None:
        """Expose the documentation node as `doc` and its prepared Python object as `obj`"""
        self.doc = cast("content.Doc", self.node)
        """The prepared documentation node for this appearance"""

        self.obj = self.doc.obj
        """The prepared Python object, or the authored alias that names it"""

    def __str__(self) -> str:
        """Include the published link target alongside the native heading ID"""
        rendered = super().__str__()
        anchor = self.doc.anchor
        if not self.page_path or not anchor:
            return rendered
        title = self.title
        if isinstance(title, Header) and title.attr and title.attr.identifier == anchor:
            return rendered
        return str(Blocks([Div(attr=Attr(identifier=anchor)), rendered]))

    @cached_property
    def context(self) -> RenderContext:
        """
        The frozen record of this object's appearance

        The record refers to the prepared documentation rather than copying it. Its
        page path and project roots are `None` when unknown.
        """
        return RenderContext(
            obj=self.obj,
            authored_name=self.doc.name,
            canonical_identity=self.obj.canonical_path,
            page_path=self.context_page_path,
            level=self.level,
            contained=self.contained,
            source_root=self.extension.source_root,
            output_root=self.output_root,
            settings=self.settings,
        )

    @cached_property
    def kind(self) -> DocObjectKind:
        """
        The object's kind

        class, function, method, property, attribute, type alias, module, alias
        """
        return self.obj.kind.value

    @cached_property
    def kind_slug(self) -> str:
        """
        The object's kind as a CSS class slug

        Some kinds (e.g. `type alias`) contain a space, which a browser would
        otherwise parse as two separate classes.
        """
        return self.kind.replace(" ", "-")

    @cached_property
    def label(self) -> str:
        """The lower-case kind label used in the CSS classes of headings and summary rows"""
        return get_label(self.obj).lower()

    @cached_property
    def display_name(self) -> str:
        """
        The Markdown-escaped name shown in the heading

        Below the top heading level, the `relative` format shows only the name. Function
        and method names end in parentheses.
        """
        format = self.display_name_format
        if format == "relative" and self.level > 1:
            format = "name"
        name = format_name(self.doc, format)

        # Parentheses distinguish callable labels from plain value names.
        if self.kind == "function":
            name += "()"

        return markdown_escape(name)

    @cached_property
    def signature_name(self) -> str:
        """The name shown in the signature, formatted by `signature_name_format`"""
        return format_name(self.doc, self.signature_name_format)

    def render_description(self) -> BlockContent:
        """
        Render the signature, the Usage and source row, and the subject, in that order

        Callable and value renderers use their own order. Return `None` from
        `render_signature`, `render_usage_source` or `render_docstring_subject` to omit
        that part.

        Returns
        -------
        :
            The parts that are not omitted.
        """
        return Blocks([self.signature, self.render_usage_source(), self.render_docstring_subject()])

    @cached_property
    def signature(self) -> BlockContent:
        """The signature from `render_signature`, cached once per renderer instance"""
        return self.render_signature()

    def render_signature(self) -> BlockContent:
        """
        Render the object declaration, or return `None` to omit it

        Returns
        -------
        :
            The declaration, or `None` to omit it.
        """

    @cached_property
    def title_content(self) -> InlineContent:
        """
        The object's labelled name as inline text

        `title` is the block that places this label in the document: a heading, or
        `None` where no heading is shown. An API page's front-matter title is the
        label of its first object, even when that object's `title` is `None`.

        Override `render_title_content` to change it.
        """
        return self.render_title_content()

    def render_title_content(self) -> InlineContent:
        """
        Render the object's display name and labels as inline text

        The result is the text of the object's heading and, for the first object on an
        API page, the page's front-matter title.

        Returns
        -------
        :
            The labelled display name. Return text rather than `None`; the front matter
            would otherwise show the title `None`.
        """
        return Span(
            self.display_name,
            Attr(
                classes=[
                    "doc-object-name",
                    f"doc-{self.kind_slug}",
                    "doc-label",
                    f"doc-label-{self.label}",
                ],
            ),
        )

    def render_title(self) -> BlockContent:
        """
        Render the heading that holds `title_content`, or return `None` to omit it

        Contained objects and the objects of a multi-object page keep their headings.
        Override `render_title_content` instead to change the label, so the heading and
        the page's front-matter title stay the same.

        Returns
        -------
        :
            The heading, or `None` for the object of a single-object API page, whose
            front matter already shows `title_content`.
        """
        if self._purpose is _RenderingPurpose.API_PAGE and self.level == 1:
            return None
        # A qualified title can already yield the published ID. Claim it on the
        # heading so the page carries that ID once.
        title_id = self.display_name.removesuffix("()").lower()
        attr = Attr(identifier=title_id) if self.page_path and title_id == self.doc.anchor else None
        return Header(level=self.level, content=self.title_content, attr=attr)

    def render_annotation(self, annotation: Annotation | None = None) -> str:
        """
        Render an annotation as highlighted inline content

        Parameters
        ----------
        annotation
            The annotation to render. `None` uses the current attribute's annotation.

        Returns
        -------
        :
            The highlighted annotation text with supported expression markup.

        Raises
        ------
        TypeError
            If no annotation is supplied and the current object is not an attribute.
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
            """
            Render one annotation fragment without resolving cross references

            Parameters
            ----------
            ann
                The annotation fragment. `None` renders as empty text.

            Returns
            -------
            :
                The fragment as plain text, with names escaped for Markdown.
            """
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
        Render a variable or parameter declaration as inline markup

        Parameters
        ----------
        name
            The declaration name, or an empty value to omit it and its separators.
        annotation
            The annotation to display, or `None` to omit it.
        default
            The default or assigned value, or `None` to omit it.

        Returns
        -------
        :
            Inline name, annotation and value markup with their corresponding CSS classes.
        """
        items: list[InlineContentItem] = []

        if name:
            items.append(Span(name, Attr(classes=["doc-parameter-name"])))

        if annotation:
            if isinstance(annotation, gf.Expr):
                # Long expressions need line wrapping; short expressions retain
                # the ordinary annotation markup.
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
    def _docstring_sections(self) -> list[gf.DocstringSection]:
        """
        The prepared docstring sections, normalised for rendering

        Normalisation gives See Also, Notes, Warnings and example fragments their own
        section types. An object without a docstring has no sections.
        """
        if not self.obj.docstring:
            return []
        return transform_sections(self.obj.docstring.parsed)

    @cached_property
    def _docstring_subject_lines(self) -> list[str]:
        """
        The lines of the docstring's first paragraph, which make up the subject
        """
        sections = self._docstring_sections
        if not sections or not isinstance(sections[0], gf.DocstringSectionText):
            return []
        return summary_lines(sections[0].value)

    @cached_property
    def docstring_subject(self) -> str | None:
        """
        The first paragraph of the docstring, on one line, shown as the subject

        The paragraph may wrap over several lines; it ends at the first blank line. There
        is no subject when the docstring does not start with a text section, or when it
        opens with a code fence, display maths (`$$`) or a fenced div (`:::`). Body
        callbacks do not receive the subject.
        """
        lines = self._docstring_subject_lines
        return " ".join(line.strip() for line in lines) if lines else None

    def render_docstring_subject(self) -> BlockContent:
        """
        Render the subject of the docstring

        Returns
        -------
        :
            The subject paragraph in a `doc-subject` division.
        """
        return Div(Para(self.docstring_subject), Attr(classes=["doc-subject"]))

    @cached_property
    def docstring_sections_content(self) -> list[tuple[str, AnyDocstringSection]]:
        """
        The title and prepared section of each docstring section after the subject

        The section objects belong to the shared prepared documentation, so treat them
        as read-only. Override a section-rendering method to change that section's
        markup.
        """
        items: list[tuple[str, AnyDocstringSection]] = []

        if not self.obj.docstring:
            return []

        sections = list(self._docstring_sections)

        # Remove the docstring subject from the top of the docstring
        if subject_lines := self._docstring_subject_lines:
            # Copy the first section, because every appearance of the object shares it.
            first_section = copy(sections[0])
            first_section.value = "\n".join(first_section.value.splitlines()[len(subject_lines) :])
            sections = [first_section, *sections[1:]]

        for i, section in enumerate(sections):
            section_kind: gf.DocstringSectionKind = section.kind
            raw_title = (section.title or section_kind).strip()
            # Apply .title() only to text outside backtick-delimited code spans
            # so that e.g. "What Can Be Used in `value=`?" keeps `value=` verbatim.
            parts = raw_title.split("`")
            title = "`".join(part if idx % 2 else part.title() for idx, part in enumerate(parts))

            if section_kind == "text" and i > 0:
                # Some docstrings (e.g., numpy-style with Examples) produce
                # trailing text sections. Treat them as additional description
                # content rather than crashing.
                title = "Text"

            items.append((title, section))

        return items

    @cached_property
    def docstring_sections(self) -> list[Block]:
        """
        The rendered docstring sections, omitting empty ones

        Text and deprecation sections render as divs. Other sections get a heading one
        level below the object. Standard titles are translated into the reference's
        language; custom titles keep their own text.
        """
        sections: list[Block] = []
        for title, section in self.docstring_sections_content:
            body = self.render_docstring_section(section) or ""
            if not body:
                continue
            # Build a slug-safe CSS class: strip backticks and non-alphanumeric
            # characters (except hyphens/spaces) before lowercasing and hyphenating.
            slug_raw = title.replace("`", "")
            slug = re.sub(r"[^a-z0-9 -]", "", slug_raw.lower())
            slug = re.sub(r"[ -]+", "-", slug).strip("-")
            section_classes = [f"doc-{slug}"]
            if title in ("Text", "Deprecated"):
                content = Div(body, Attr(classes=section_classes))
            else:
                key = _SECTION_TITLE_KEYS.get(title)
                header = Header(
                    self.level + 1,
                    translate(key, self.settings.lang) if key else title,
                    Attr(classes=section_classes),
                )
                content = Blocks([header, body])
            sections.append(content)
        return sections

    def render_body(self) -> BlockContent:
        """
        Render the object's docstring body

        Renderers for objects with members add member groups after it. Override
        `render_docstring_body` to change the docstring sections while keeping
        those groups.

        Returns
        -------
        :
            The rendered docstring sections, or `None` to omit them.
        """
        return self.render_docstring_body()

    def render_docstring_body(self) -> BlockContent:
        """
        Render the docstring sections that follow the subject

        Member groups are not part of this result.

        Returns
        -------
        :
            The rendered sections, or `None` when no section has content.
        """
        return None if not self.docstring_sections else Blocks(self.docstring_sections)

    def render_docstring_section(self, el: AnyDocstringSection) -> BlockContent:
        """
        Render one docstring section with the method for its kind

        Parameters
        ----------
        el
            The prepared section to render.

        Returns
        -------
        :
            The section content, or `None` to omit it. A section kind without a method
            is omitted with a warning.

        Notes
        -----
        Override the method for one section kind to change only that kind. Dispatch
        matches the section's exact class, so a subclass of a supported section type
        has no method.
        """
        name = SECTION_METHOD.get(type(el))
        method = getattr(self, name, None) if name else None
        return method(el) if method else self._unhandled_section(el)

    def _unhandled_section(self, el: AnyDocstringSection) -> None:
        """
        Discard a section this renderer has no method for, and say so

        Parameters
        ----------
        el
            The section without a method.
        """
        name = el.title or el.kind.value
        _log.warning(
            "%s: no renderer for the %s docstring section, so it is omitted.",
            self.obj.path,
            name,
        )
        return None

    def _suppress_section(self, el: AnyDocstringSection) -> None:
        """
        Omit a hand-written member summary that automatic groups would duplicate

        Parameters
        ----------
        el
            The member summary section.
        """
        return None

    def render_functions_section(self, el: gf.DocstringSectionFunctions) -> None:
        """
        Omit hand-written `Functions` and `Methods` summaries

        Griffe parses both headings as the same section kind. The member groups list
        the functions and methods instead. Override this method to keep the
        hand-written list; the other member-summary sections stay omitted.

        Parameters
        ----------
        el
            The `Functions` or `Methods` section.
        """
        return self._suppress_section(el)

    def render_classes_section(self, el: gf.DocstringSectionClasses) -> None:
        """
        Omit a hand-written `Classes` summary

        The member groups list the nested classes instead. Override this method to keep
        the hand-written list; the other member-summary sections stay omitted.

        Parameters
        ----------
        el
            The `Classes` section.
        """
        return self._suppress_section(el)

    def render_modules_section(self, el: gf.DocstringSectionModules) -> None:
        """
        Omit a hand-written `Modules` summary

        Override this method to keep the hand-written list; the other member-summary
        sections stay omitted.

        Parameters
        ----------
        el
            The `Modules` section.
        """
        return self._suppress_section(el)

    def render_type_aliases_section(self, el: gf.DocstringSectionTypeAliases) -> None:
        """
        Omit a hand-written `Type Aliases` summary

        The member groups list the type aliases instead. Override this method to keep
        the hand-written list; the other member-summary sections stay omitted.

        Parameters
        ----------
        el
            The `Type Aliases` section.
        """
        return self._suppress_section(el)

    def render_text_section(self, el: gf.DocstringSectionText) -> BlockContent:
        """
        Render a `Text` section

        Parameters
        ----------
        el
            The `Text` section.

        Returns
        -------
        :
            The text as written in the docstring.
        """
        return el.value

    def render_examples_section(self, el: gf.DocstringSectionExamples) -> BlockContent:
        """
        Render an `Examples` section

        Parameters
        ----------
        el
            The `Examples` section.

        Returns
        -------
        :
            The code fragments as Python code blocks and the prose fragments as written.
        """
        return Blocks([self._render_example_fragment(c) for c in el.value])

    def _render_example_fragment(self, fragment: object) -> BlockContent:
        """
        Render one code or prose fragment of an `Examples` section

        Parameters
        ----------
        fragment
            A fragment of the section's value.

        Returns
        -------
        :
            A Python code block for code, the text for prose, or an empty string for
            anything else.
        """
        el = transform(fragment)
        if isinstance(el, ExampleCode):
            return CodeBlock(el.value, Attr(classes=["python"]))
        if isinstance(el, ExampleText):
            return el.value
        return ""

    def render_deprecated_section(self, el: gf.DocstringSectionDeprecated) -> BlockContent:
        """
        Render a `Deprecated` section

        Parameters
        ----------
        el
            The `Deprecated` section.

        Returns
        -------
        :
            A `doc-deprecated` division that labels the description with the version
            that deprecated the object.
        """
        label = translate_versioned(
            "deprecated_since_version", self.settings.lang, el.value.version
        )
        content = Div(
            Inlines(
                [
                    Span(
                        f"{label}:",
                        Attr(classes=["versionmodified", "deprecated"]),
                    ),
                    el.value.description.strip(),
                ]
            ),
            Attr(classes=["doc-deprecated"]),
        )
        return str(content)

    def render_admonition_section(self, el: gf.DocstringSectionAdmonition) -> BlockContent:
        """
        Render the descriptive content of an additional numpydoc section

        Parameters
        ----------
        el
            The additional section.

        Returns
        -------
        :
            The section's description.
        """
        return el.value.description

    def render_warnings_section(self, el: DocstringSectionWarnings) -> BlockContent:
        """
        Render a `Warnings` section

        Parameters
        ----------
        el
            The `Warnings` section.

        Returns
        -------
        :
            The text as written in the docstring.
        """
        return el.value

    def render_notes_section(self, el: DocstringSectionNotes) -> BlockContent:
        """
        Render a `Notes` section

        Parameters
        ----------
        el
            The `Notes` section.

        Returns
        -------
        :
            The text as written in the docstring.
        """
        return el.value

    def render_see_also_section(self, el: DocstringSectionSeeAlso) -> BlockContent:
        """
        Render a `See Also` section

        Parameters
        ----------
        el
            The `See Also` section.

        Returns
        -------
        :
            A definition list with one item per reference: the name as an interlink and
            its description.
        """
        content = format_see_also(el.value)
        items: list[DefinitionItem] = []
        for line in content.split("\n"):
            if not line.strip():
                continue
            term, *desc = line.split(":")
            items.append((term, ":".join(desc)))
        return DefinitionList(items)

    def render_definition_items(self, el: DocstringSectionWithDefinitions) -> BlockContent:
        """
        Render a section's definitions with their names, annotations, defaults and descriptions

        Parameters, attributes and type parameters share the same declaration markup.
        Consecutive unnamed return, yield or receive items with the same annotation
        merge into one definition. The merge works on copies, so rendering again leaves
        the prepared items unchanged.

        Parameters
        ----------
        el
            The prepared section.

        Returns
        -------
        :
            The definitions as a definition list, or `None` when the section has no items.
        """

        def render_section_item(el: DocstringDefinitionType) -> DefinitionItem:
            """
            Render a single definition in a section

            Parameters
            ----------
            el
                The definition.

            Returns
            -------
            :
                The declaration as an HTML code element, so that cross references in its
                annotation resolve, and the description.
            """
            name = getattr(el, "name", None) or ""
            default = getattr(el, "default", None)
            annotation = el.annotation

            # Parameter of kind *args or **kwargs have no default values
            if isinstance(el, gf.DocstringParameter) and "*" in el.name:
                default = None

            term = self.render_variable_definition(name, annotation, default)

            # Annotations are expressed in html so that contained interlink
            # references can be processed. Pandoc does not process any markup
            # within backquotes `...`, but it does if the markup is within
            # html code tags.
            desc = el.description or ""
            return Code(str(term)).html, desc

        # For Returns/Yields/Receives, merge consecutive unnamed items that
        # share the same annotation (griffe splits continuation paragraphs
        # into separate DocstringReturn objects, each repeating the type).
        items_to_render = list(el.value)
        if isinstance(
            el, (gf.DocstringSectionReturns, gf.DocstringSectionYields, gf.DocstringSectionReceives)
        ):
            items_to_render = [copy(item) for item in items_to_render]
            items_to_render = cast(
                "list[gf.DocstringReturn | gf.DocstringYield | gf.DocstringReceive]",
                items_to_render,
            )
            merged: list[gf.DocstringReturn | gf.DocstringYield | gf.DocstringReceive] = []
            for item in items_to_render:
                name = getattr(item, "name", None) or ""
                ann = getattr(item, "annotation", None)
                if (
                    not name
                    and merged
                    and not (getattr(merged[-1], "name", None) or "")
                    and getattr(merged[-1], "annotation", None) == ann
                ):
                    # Merge description into the previous item
                    prev = merged[-1]
                    prev_desc = prev.description or ""
                    cur_desc = item.description or ""
                    sep = "\n\n" if prev_desc else ""
                    prev.description = prev_desc + sep + cur_desc
                else:
                    merged.append(item)
            items_to_render = merged

        items = [render_section_item(item) for item in items_to_render]
        if not items:
            return None
        return Div(DefinitionList(items), Attr(classes=["doc-definition-items"]))

    @property
    def summary_name(self) -> str:
        """
        The authored name shown in this object's summary row

        Function and method names end in parentheses. Override this property to change
        the summary label without changing headings, link targets or inventory entries.
        """
        name = self.doc.name
        if self.kind == "function":
            name += "()"
        return name

    def render_summary(self) -> Sequence[DefinitionItem]:
        """
        Render one summary row that links `summary_name` and shows the subject

        Contained members link to their own documentation on the same page. Other
        objects link to `page_path`, with their published fragment when one is set.

        Returns
        -------
        :
            The summary row, or an empty sequence to omit it; the object stays in the
            reference.
        """
        # Standalone snippets use the heading ID derived by Quarto.
        anchor = self.doc.name if self.contained and not self.page_path else self.doc.anchor
        page_path = "" if self.contained else self.page_path or ""
        link = Link(
            markdown_escape(self.summary_name),
            f"{page_path}#{anchor}" if anchor else page_path,
            attr=Attr(classes=[f"doc-{self.kind_slug}", "doc-label", f"doc-label-{self.label}"]),
        )
        return [(str(link), self.docstring_subject)]

    def render_usage_source(self) -> BlockContent:
        """
        Render the Usage label and the source link, or `None` when neither applies

        The Usage label appears only with a signature. The source link appears whenever
        one is available, even without a signature.

        Returns
        -------
        :
            The label and link that apply, or `None` when neither applies.
        """
        source = self.source_link
        usage = translate("usage", self.settings.lang) if self.signature is not None else None
        if usage is None and source is None:
            return None
        return Div(
            [usage, source],
            attr=Attr(classes=["doc-usage-source"]),
        )

    @cached_property
    def source_link(self) -> Link | None:
        """
        The link to the object's source, or `None` without one

        A link needs a repository, a usable source path and a starting line. An
        object from an installed stub links only when the repository has a copy of
        the stub.
        """
        return source_link(self.obj, self.settings.source_links, self.settings.lang)
