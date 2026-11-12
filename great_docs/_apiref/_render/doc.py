from __future__ import annotations

import logging
import re
from copy import copy
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs._apiref._render._label import get_label
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
from ._section_dispatch import SECTION_METHOD
from .base import RenderBase

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

# Directories that hold installed packages, rather than a repository's own files.
_INSTALL_DIRS = frozenset({"site-packages", "dist-packages"})

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
class __RenderDoc(RenderBase):
    """
    Render a `content.Doc` object
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
    as listed in the great_docs._apiref yaml section. e.g

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
        # The node field is too general. It is typed to include all
        # classes of documentable objects. And for nodes.Doc objects,
        # the core object is a griffe object contained within.
        # For convenience, we create attributes with narrower types
        # using cast instead of TypeAlias so that subclasses can
        # create narrower types.
        self.doc = cast("content.Doc", self.node)
        """Doc Object"""

        self.obj = self.doc.obj
        """Griffe object (or alias)"""

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
        """
        A label for the object
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
                    f"doc-{self.kind_slug}",
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
        Create a code snippet that declares a variable

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
    def _docstring_sections(self) -> list[gf.DocstringSection]:
        """
        Transform the parsed sections used to render the docstring
        """
        if not self.obj.docstring:
            return []
        return transform_sections(self.obj.docstring.parsed)

    @cached_property
    def docstring_subject(self) -> str | None:
        """
        Select the leading prose line used as the docstring subject
        """
        sections = self._docstring_sections
        if not sections or not isinstance(sections[0], gf.DocstringSectionText):
            return None

        lines = sections[0].value.splitlines()
        if not lines:
            return None
        first_line = lines[0]
        if first_line == "$$" or first_line.startswith(":::"):
            return None
        return first_line

    def render_docstring_subject(self) -> BlockContent:
        """
        Render the subject of the docstring
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

        sections = list(self._docstring_sections)

        # Remove the docstring subject from the top of the docstring
        if self.docstring_subject:
            # The sections are cached value that we have to be careful not modify.
            # We modify a copy of first section and we create a new list
            first_section = copy(sections[0])
            first_section.value = "\n".join(first_section.value.splitlines()[1:])
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
        Rendered sections of the docstring.

        Each section is produced by parsing the docstring into titled sections
        and wrapping the section content in markup-generating blocks.
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
        Render the docstring of the Doc object
        """
        return None if not self.docstring_sections else Blocks(self.docstring_sections)

    def render_docstring_section(self, el: AnyDocstringSection) -> BlockContent:
        """
        Render a section of a docstring

        Parameters
        ----------
        el :
            The section to render

        Returns
        -------
        :
            The rendered section, or `None` when this renderer has no method
            for it.

        Notes
        -----
        To render a given type of section differently, override the method
        that `SECTION_METHOD` names for it. Defining that method on a subclass
        confines the change to that subclass.
        """
        name = SECTION_METHOD.get(type(el))
        method = getattr(self, name, None) if name else None
        return method(el) if method else self._unhandled_section(el)

    def _unhandled_section(self, el: AnyDocstringSection) -> None:
        """
        Discard a section this renderer has no method for, and say so
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
        Drop a hand-written summary of members that great-docs generates itself
        """
        return None

    def render_functions_section(self, el: gf.DocstringSectionFunctions) -> None:
        """
        Drop a hand-written `Functions` section

        numpydoc's `Methods` section is also parsed by griffe into a
        `DocstringSectionFunctions`, so this method covers both `Methods` and
        `Functions`. great-docs lists the real functions or methods from the
        object's members, so a hand-written list would duplicate that and
        risk going stale.
        """
        return self._suppress_section(el)

    def render_classes_section(self, el: gf.DocstringSectionClasses) -> None:
        """
        Drop a hand-written `Classes` section

        great-docs generates the list of nested classes from the object's
        real members, so a hand-written summary would duplicate it and risk
        contradicting it.
        """
        return self._suppress_section(el)

    def render_modules_section(self, el: gf.DocstringSectionModules) -> None:
        """
        Drop a hand-written `Modules` section

        great-docs generates the list of submodules from the package's real
        members, so a hand-written summary would duplicate it and risk
        contradicting it.
        """
        return self._suppress_section(el)

    def render_type_aliases_section(self, el: gf.DocstringSectionTypeAliases) -> None:
        """
        Drop a hand-written `Type Aliases` section

        great-docs generates the list of type aliases from the module's real
        members, so a hand-written summary would duplicate it and risk
        contradicting it.
        """
        return self._suppress_section(el)

    def render_text_section(self, el: gf.DocstringSectionText) -> BlockContent:
        """Render a `Text` section"""
        return el.value

    def render_examples_section(self, el: gf.DocstringSectionExamples) -> BlockContent:
        """Render an `Examples` section"""
        return Blocks([self._render_example_fragment(c) for c in el.value])

    def _render_example_fragment(self, fragment: object) -> BlockContent:
        """
        Render one code or prose fragment of an `Examples` section
        """
        el = transform(fragment)
        if isinstance(el, ExampleCode):
            return CodeBlock(el.value, Attr(classes=["python"]))
        if isinstance(el, ExampleText):
            return el.value
        return ""

    def render_deprecated_section(self, el: gf.DocstringSectionDeprecated) -> BlockContent:
        """Render a `Deprecated` section"""
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
        """Render an unofficial numpydoc section"""
        return el.value.description

    def render_warnings_section(self, el: DocstringSectionWarnings) -> BlockContent:
        """Render a `Warnings` section"""
        return el.value

    def render_notes_section(self, el: DocstringSectionNotes) -> BlockContent:
        """Render a `Notes` section"""
        return el.value

    def render_see_also_section(self, el: DocstringSectionSeeAlso) -> BlockContent:
        """Render a `See Also` section"""
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
        Render a section whose value is a list of definitions

        The definitions differ in what they describe — a parameter, an
        attribute, a type parameter — but each renders as a term built from
        name, annotation and default, followed by a description.
        """

        def render_section_item(el: DocstringDefinitionType) -> DefinitionItem:
            """
            Render a single definition in a section
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
            items_to_render = cast(
                "list[gf.DocstringReturn | gf.DocstringYield | gf.DocstringReceive]",
                items_to_render,
            )
            merged: list[gf.DocstringReturn | gf.DocstringYield | gf.DocstringReceive] = []
            merged = []
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
            f"{self.page_path}#{anchor}" if anchor else self.page_path,
            attr=Attr(classes=[f"doc-{self.kind_slug}", "doc-label", f"doc-label-{self.label}"]),
        )
        return [(str(link), self.docstring_subject)]

    def render_usage_source(self) -> BlockContent:
        """
        Render a row with usage and source
        """
        source = self.source_link if self.show_source_link else None
        return Div(
            [translate("usage", self.settings.lang), source],
            attr=Attr(classes=["doc-usage-source"]),
        )

    @cached_property
    def source_link(self) -> Link | None:
        """
        Build a link to the object's source code

        Returns
        -------
        :
            The source link, or `None` when no repository URL or source path is
            available, the file is a compiled extension, or the starting line
            is unknown.
        """
        links = self.settings.source_links
        if not links.repo_url:
            return None
        rel_str = self._source_relative_path()
        if rel_str is None:
            return None
        # Suppress source links for compiled extensions (PyO3, Cython,
        # pybind11, C extensions). The file path points at a binary
        # artifact and `lineno` is None, producing broken `#LNone` anchors.
        if rel_str.endswith((".so", ".pyd", ".dylib", ".abi3.so")):
            return None
        start, end = self.obj.lineno, self.obj.endlineno
        if start is None:
            return None
        anchor = f"#L{start}-L{end}" if end is not None and start != end else f"#L{start}"
        url = f"{links.repo_url}/blob/{links.ref}/{rel_str}{anchor}"
        return Link(
            translate("source", self.settings.lang),
            url,
            attr=Attr(attributes={"target": "_blank", "rel": "noopener"}),
        )

    def _source_relative_path(self) -> str | None:
        """
        Resolve the object's source path for a repository link

        Griffe's `relative_package_filepath` is relative to the package's parent
        directory, a Griffe search path. For `src/` and other non-flat layouts,
        it drops the leading directory, producing GitHub blob URLs that return
        404. Resolve the path in this order to preserve the repository layout:

        1. Honour an explicit `source.path` override for monorepos.
        2. Compute the path relative to the repository root from the object's
           absolute file path, preserving directories such as `src/`.
        3. Fall back to Griffe's package-parent-relative path when the override
           and repository root cannot resolve a path.

        Objects that only a stub declares, such as the classes and functions
        of a PyO3 or other compiled extension, take their line numbers from the
        `.pyi` file but report the module's `.py` file. They link to the stub
        instead. An installed stub, outside the repository, links to the
        repository's copy, and to nothing when there is none.

        Returns
        -------
        :
            The source path, or `None` when no path can be determined.
        """
        # Griffe raises `ValueError` for objects without a parent module, such
        # as synthetic objects. A `getattr` default only handles missing attributes.
        try:
            filepath = self.obj.filepath
        except (ValueError, AttributeError):
            filepath = None

        # A namespace package can span several directories and has no single
        # source file. Use Griffe's package-relative path in step 3.
        if isinstance(filepath, list):
            filepath = None

        links = self.settings.source_links

        if filepath is not None and Path(filepath).suffix == ".py" and _declared_in_stub(self.obj):
            stub = Path(filepath).with_suffix(".pyi")
            if stub.is_file():
                filepath = stub
        if filepath is not None and Path(filepath).suffix == ".pyi":
            return self._stub_relative_path(Path(filepath))

        # 1. Explicit override for monorepos: `<source.path>/<filename>`.
        if links.path and filepath is not None:
            return f"{links.path}/{Path(filepath).name}"

        # 2. Path relative to the repository root, preserving the real layout.
        if links.package_root and filepath is not None:
            try:
                rel = Path(filepath).resolve().relative_to(links.package_root.resolve())
                return rel.as_posix()
            except (ValueError, OSError):
                pass

        # 3. Legacy fallback: griffe's package-parent-relative path.
        try:
            return Path(self.obj.relative_package_filepath).as_posix()
        except (ValueError, AttributeError):
            return None

    def _stub_relative_path(self, stub: Path) -> str | None:
        """
        Resolve a stub file's path for a repository link

        A stub inside the repository keeps its path. An installed stub,
        including one in a virtual environment within the repository, is
        looked up in the repository under its package-relative path, also
        within `src/` and `python/`. A package's `__init__.pyi` is also looked
        up as `<package>.pyi`, where maturin keeps the stub of a Rust-only
        project.

        Parameters
        ----------
        stub
            The absolute path of the stub file.

        Returns
        -------
        :
            The stub's path relative to the repository root, or `None` when the
            repository has no copy of an installed stub.
        """
        links = self.settings.source_links
        if links.path:
            return f"{links.path}/{stub.name}"

        try:
            rel = Path(self.obj.relative_package_filepath).with_suffix(".pyi")
        except (ValueError, AttributeError):
            rel = None

        if links.package_root is None:
            return rel.as_posix() if rel else None

        root = links.package_root.resolve()
        try:
            inside = stub.resolve().relative_to(root)
        except (ValueError, OSError):
            inside = None
        # A virtual environment within the repository holds installed copies.
        if inside is not None and not _INSTALL_DIRS.intersection(inside.parts):
            return inside.as_posix()

        if rel is None:
            return None
        names = [rel]
        if rel.name == "__init__.pyi" and rel.parent != Path():
            names.append(rel.parent.with_suffix(".pyi"))
        for name in names:
            for candidate in (name, "src" / name, "python" / name):
                if (root / candidate).is_file():
                    return candidate.as_posix()
        return None


def _declared_in_stub(obj: gf.Object | gf.Alias) -> bool:
    """
    Whether an object comes from a stub that griffe merged into its module

    Griffe marks the objects a stub adds to a module as not available at
    runtime, so an object declared in a stub, or a member of a class that
    is, reports the `.py` module file but has the stub's line numbers.
    Objects inside `if TYPE_CHECKING:` are also marked, so callers check that
    the stub file exists.
    """
    current: gf.Object | None
    try:
        current = obj.final_target if isinstance(obj, gf.Alias) else obj
    except (gf.AliasResolutionError, gf.CyclicAliasError):
        return False
    while current is not None and not getattr(current, "is_module", True):
        if getattr(current, "runtime", True) is False:
            return True
        current = getattr(current, "parent", None)
    return False


class RenderDoc(__RenderDoc):
    """
    Extension point for the rendering of all objects that have docstrings

    These are modules, classes, functions and attributes.
    """
