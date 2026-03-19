from __future__ import annotations

import re
import typing
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from . import _ast as qast
from . import layout
from ._ast import (
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
    ExampleCode,
    ExampleText,
)
from ._griffe import dataclasses as dc
from ._griffe import docstrings as ds
from ._griffe import expressions as expr
from ._rst_converters import (
    _convert_bold_section_headers,
    _convert_google_sections,
    _convert_rst_text,
    _convert_sphinx_fields,
    _fence_doctest_blocks,
    escape,
    sanitize,
)
from .pandoc.blocks import DefinitionList
from .pandoc.inlines import Attr, Code, Inlines, Span, Strong

if typing.TYPE_CHECKING:  # pragma: no cover
    pass


# utils -----------------------------------------------------------------------


_LIST_ITEM_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])\s")


def _ensure_blank_before_lists(text: str) -> str:
    """Ensure a blank line before the first markdown list item in each run.

    Pandoc Markdown requires a blank line before a list for it to be recognized as a list rather
    than continuation of a paragraph. This inserts a blank line before the first list item when the
    preceding line is non-blank, non-list text.
    """
    lines = text.split("\n")
    result: list[str] = []
    prev_was_list_or_blank = False
    for i, line in enumerate(lines):
        is_list = bool(_LIST_ITEM_RE.match(line))
        is_blank = line.strip() == ""
        # Insert blank line before first list item after prose text
        if is_list and not prev_was_list_or_blank and i > 0:
            result.append("")
        result.append(line)
        prev_was_list_or_blank = is_list or is_blank
    return "\n".join(result)


def convert_rst_link_to_md(rst: str) -> str:
    expr_pat = r"((:external(\+[a-zA-Z\._]+))?(:[a-zA-Z\._]+)?:[a-zA-Z\._]+:`~?[a-zA-Z\._]+`)"

    return re.sub(expr_pat, r"[](\1)", rst, flags=re.MULTILINE)


def _simple_table(rows: list[tuple], headers: list[str]) -> str:
    """Simple Markdown table without the tabulate dependency."""
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def _has_attr_section(el: dc.Docstring | None) -> bool:
    if el is None:
        return False

    return any([isinstance(x, ds.DocstringSectionAttributes) for x in el.parsed])


def _sanitize_title(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9-]+", "", title.replace(" ", "-"))


def _escape_dunders(name: str) -> str:
    """Escape ``__name__`` patterns so Pandoc does not interpret them as bold.

    ``__repr__`` → ``\\_\\_repr\\_\\_``
    """
    return re.sub(r"__(\w+)__", r"\_\_\1\_\_", name)


# Dataclass field introspection -----------------------------------------------
# Griffe's static analysis may miss some dataclass fields (e.g. str, list, dict
# fields).  This helper dynamically imports the class and uses
# dataclasses.fields() to discover ALL fields, then merges with descriptions
# from the docstring's Parameters section.


def _is_griffe_dataclass(obj: "dc.Object | dc.Alias") -> bool:
    """Check whether a griffe object is a dataclass."""
    try:
        return "dataclass" in obj.labels
    except Exception:
        return False


def _is_non_callable_class(obj: "dc.Object | dc.Alias") -> bool:
    """Check whether a griffe class is a non-callable type (Enum, TypedDict).

    Enums are accessed via members (e.g., ``Color.RED``), not called.
    TypedDicts are structural type definitions, not constructors.
    """
    try:
        labels = getattr(obj, "labels", set())
        if "enum" in labels:
            return True
    except Exception:
        pass
    try:
        bases = getattr(obj, "bases", [])
        base_names = {str(b).rsplit(".", 1)[-1] for b in bases}
        if base_names & {"TypedDict", "Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}:
            return True
    except Exception:
        pass
    return False


def _get_dataclass_field_names(obj: "dc.Object | dc.Alias") -> list[str] | None:
    """Dynamically import a class and return its dataclass field names.

    Returns None if the class cannot be imported or is not a dataclass.
    """
    import dataclasses as _dc
    import importlib

    path = obj.canonical_path if hasattr(obj, "canonical_path") else obj.path

    parts = path.rsplit(".", 1)
    if len(parts) != 2:
        return None

    module_path, class_name = parts

    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name, None)
        if cls is None or not _dc.is_dataclass(cls):
            return None
        return [f.name for f in _dc.fields(cls)]
    except Exception:
        return None


def _get_param_descriptions(obj: "dc.Object | dc.Alias") -> dict[str, str]:
    """Extract {param_name: description} from the docstring's Parameters section."""
    if obj.docstring is None:
        return {}

    descs: dict[str, str] = {}
    for section in obj.docstring.parsed:
        if isinstance(section, ds.DocstringSectionParameters):
            for param in section.value:
                descs[param.name] = param.description or ""
    return descs


# ParamRow -------------------------------------------------------------------


@dataclass
class ParamRow:
    name: str | None
    description: str
    annotation: str | None = None
    default: str | None = None

    def to_definition_list(self) -> tuple[str, str]:
        name = self.name
        anno = self.annotation
        desc = sanitize(self.description, allow_markdown=True, preserve_newlines=True)
        desc = _ensure_blank_before_lists(desc)
        default = sanitize(str(self.default), escape_quotes=True)

        part_name = Span(Strong(name), Attr(classes=["parameter-name"])) if name is not None else ""
        part_anno = Span(anno, Attr(classes=["parameter-annotation"])) if anno is not None else ""

        if self.default is not None:
            part_default_sep = Span(" = ", Attr(classes=["parameter-default-sep"]))
            part_default = Span(default, Attr(classes=["parameter-default"]))
        else:
            part_default_sep = ""
            part_default = ""

        part_desc = desc if desc is not None else ""

        anno_sep = Span(":", Attr(classes=["parameter-annotation-sep"]))

        param = Code(
            str(Inlines([part_name, anno_sep, part_anno, part_default_sep, part_default]))
        ).html
        return (param, part_desc)

    def to_tuple(
        self, style: Literal["parameters", "attributes", "returns"]
    ) -> tuple[str | None, str | None, str, str] | tuple[str | None, str | None, str]:
        name = self.name
        description = sanitize(self.description, allow_markdown=True)

        if style == "parameters":
            default = "_required_" if self.default is None else escape(self.default)
            return (name, self.annotation, description, default)
        elif style == "attributes":
            return (name, self.annotation, description)
        elif style == "returns":
            return (name, self.annotation, description)

        raise NotImplementedError(f"Unsupported table style: {style}")


# Renderer base ---------------------------------------------------------------


class Renderer:
    """Base renderer class."""

    style: str
    _registry: "dict[str, Renderer]" = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "style") and cls.style in cls._registry:  # pragma: no cover
            raise KeyError(f"A renderer for style {cls.style} already exists")

        if hasattr(cls, "style"):
            cls._registry[cls.style] = cls

    @classmethod
    def from_config(cls, cfg: "dict | Renderer | str") -> Renderer:
        if isinstance(cfg, Renderer):
            return cfg
        elif isinstance(cfg, str):
            style, cfg = cfg, {}
        elif isinstance(cfg, dict):
            style = cfg["style"]
            cfg = {k: v for k, v in cfg.items() if k != "style"}
        else:
            raise TypeError(type(cfg))

        if style.endswith(".py"):
            import importlib
            import os
            import sys

            sys.path.append(os.getcwd())

            try:
                mod = importlib.import_module(style.rsplit(".", 1)[0])
                return mod.Renderer(**cfg)
            finally:
                sys.path.pop()

        subclass = cls._registry[style]
        return subclass(**cfg)

    def render(self, el: object) -> str:
        raise NotImplementedError(f"render method does not support type: {type(el)}")

    def _pages_written(self, builder: object) -> None:  # pragma: no cover
        """Called after all the qmd pages have been rendered and written to disk."""
        ...


# MdRenderer ------------------------------------------------------------------


class MdRenderer(Renderer):
    """Render docstrings to markdown."""

    style = "markdown"

    def __init__(
        self,
        header_level: int = 1,
        show_signature: bool = True,
        show_signature_annotations: bool = False,
        display_name: str = "relative",
        hook_pre: object | None = None,
        render_interlinks: bool = False,
        table_style: str = "table",
    ) -> None:
        self.header_level = header_level
        self.show_signature = show_signature
        self.show_signature_annotations = show_signature_annotations
        self.display_name = display_name
        self.hook_pre = hook_pre
        self.render_interlinks = render_interlinks
        self.table_style = table_style

        self.crnt_header_level = self.header_level

    @contextmanager
    def _increment_header(self, n: int = 1):
        self.crnt_header_level += n
        try:
            yield
        finally:
            self.crnt_header_level -= n

    def _fetch_object_dispname(self, el: "dc.Alias | dc.Object") -> str:
        if self.display_name in {"name", "short"}:
            return el.name
        elif self.display_name == "relative":
            return ".".join(el.path.split(".")[1:])
        elif self.display_name == "full":
            return el.path
        elif self.display_name == "canonical":
            return el.canonical_path

        raise ValueError(f"Unsupported display_name: `{self.display_name}`")

    def _fetch_method_parameters(self, el: dc.Function) -> dc.Parameters:
        if (el.is_class or (el.parent and el.parent.is_class)) and len(el.parameters) > 0:
            if el.parameters[0].name in {"self", "cls"}:
                return dc.Parameters(*list(el.parameters)[1:])

        return el.parameters

    def _render_table(
        self,
        rows: list[ParamRow],
        headers: list[str],
        style: Literal["parameters", "attributes", "returns"],
    ) -> str:
        if self.table_style == "description-list":
            return str(DefinitionList([row.to_definition_list() for row in rows]))
        else:
            row_tuples = [row.to_tuple(style) for row in rows]
            return _simple_table(row_tuples, headers)

    # render_annotation -------------------------------------------------------

    def render_annotation(self, el: "str | expr.Expr | expr.ExprName | None") -> str:
        """Render a type annotation."""
        if el is None:
            return ""
        elif isinstance(el, str):
            return sanitize(el, escape_quotes=True)
        elif isinstance(el, expr.ExprName):
            if self.render_interlinks:
                return f"[{sanitize(el.name)}](`{el.canonical_path}`)"
            return sanitize(el.name)
        elif isinstance(el, expr.Expr):
            return "".join(self.render_annotation(x) for x in el)
        else:
            return sanitize(str(el), escape_quotes=True)

    # signature ---------------------------------------------------------------

    def signature(
        self, el: "layout.Doc | dc.Alias | dc.Class | dc.Function | dc.Module | dc.Attribute"
    ) -> str:
        """Return a string representation of an object's signature."""
        if isinstance(el, layout.Doc):
            return self._signature_doc(el)
        elif isinstance(el, dc.Alias):
            return self._signature_alias(el)
        elif isinstance(el, (dc.Class, dc.Function)):
            return self._signature_func_or_class(el)
        elif isinstance(el, (dc.Module, dc.Attribute)):
            return self._signature_module_or_attr(el)
        else:
            raise NotImplementedError(
                f"signature not supported for: {type(el)}"
            )  # pragma: no cover

    def _signature_doc(self, el: layout.Doc) -> str:
        orig = self.display_name
        self.display_name = el.signature_name
        res = self.signature(el.obj)
        self.display_name = orig
        return res

    def _signature_alias(self, el: dc.Alias, source: "dc.Object | None" = None) -> str:
        return self._signature_func_or_class(el.final_target, el)

    def _signature_func_or_class(
        self, el: "dc.Class | dc.Function | dc.Object", source: "dc.Object | dc.Alias | None" = None
    ) -> str:
        name = self._fetch_object_dispname(source or el)

        # For non-callable class types (Enum, TypedDict), emit just the name
        # without parentheses — they are not constructed by calling.
        if isinstance(el, dc.Class) and _is_non_callable_class(el):
            return f"```python\n{name}\n```"

        # Check for @overload variants (only on griffe Function objects)
        overloads = None
        if isinstance(el, dc.Function) and hasattr(el, "overloads"):
            try:
                ov_list = el.overloads
                if ov_list and isinstance(ov_list, list):
                    overloads = ov_list
            except Exception:  # pragma: no cover
                pass

        if overloads:
            return self._render_overload_signatures(name, overloads)

        pars = self._render_parameters(el) if hasattr(el, "parameters") else []

        flat_sig = f"{name}({', '.join(pars)})"
        if len(flat_sig) > 80:
            indented = [" " * 4 + par + "," for par in pars]
            sig = "\n".join([f"{name}(", *indented, ")"])
        else:
            sig = flat_sig

        return f"```python\n{sig}\n```"

    def _render_overload_signatures(self, name: str, overloads: list) -> str:
        """Render multiple ``@overload`` signatures as a single code block."""
        sig_lines = []
        for ov in overloads:
            if not hasattr(ov, "parameters"):
                continue
            params = []
            for p in ov.parameters:
                ann = str(p.annotation) if p.annotation else ""
                default = str(p.default) if p.default else ""
                if ann and default:
                    params.append(f"{p.name}: {ann} = {default}")
                elif ann:
                    params.append(f"{p.name}: {ann}")
                elif default:
                    params.append(f"{p.name}={default}")
                else:
                    params.append(p.name)
            ret = str(ov.returns) if ov.returns else ""
            sig = f"{name}({', '.join(params)})"
            if ret:
                sig += f" -> {ret}"
            sig_lines.append(sig)

        if not sig_lines:
            return f"```python\n{name}()\n```"

        return "```python\n" + "\n".join(sig_lines) + "\n```"

    def _signature_module_or_attr(
        self, el: "dc.Module | dc.Attribute", source: "dc.Object | dc.Alias | None" = None
    ) -> str:
        name = self._fetch_object_dispname(source or el)

        # For constants/attributes, include type annotation and value when
        # available so the QMD signature reads ``NAME: type = value`` instead
        # of the bare ``NAME`` that the renderer emits by default.
        parts = [name]
        try:
            if hasattr(el, "annotation") and el.annotation is not None:
                parts.append(f": {el.annotation}")
        except Exception:  # pragma: no cover
            pass
        try:
            if hasattr(el, "value") and el.value is not None:
                val = str(el.value)
                if len(val) <= 200:
                    parts.append(f" = {val}")
        except Exception:  # pragma: no cover
            pass

        sig = "".join(parts)
        return f"`{sig}`"

    # render_header -----------------------------------------------------------

    def render_header(self, el: "layout.Doc | ds.DocstringSection") -> str:
        """Render the header of a docstring, including any anchors."""
        if isinstance(el, layout.Doc):
            _str_dispname = _escape_dunders(el.name)
            _anchor_id = f"#{el.obj.path}"

            # Add () suffix for callable objects (functions, methods)
            _callable_kinds = {"function"}
            obj = el.obj
            _is_callable = isinstance(el, layout.DocFunction) or (
                hasattr(obj, "kind") and obj.kind.value in _callable_kinds
            )
            if _is_callable and not _str_dispname.endswith("()"):
                _str_dispname += "()"

            # Determine the object-type CSS class for type-badge styling
            _type_class = ""
            if hasattr(obj, "kind"):
                kind_val = obj.kind.value
                _type_class = f" .doc-type-{kind_val}"
                # Refine for special class subtypes
                if kind_val == "class" and hasattr(obj, "labels"):
                    labels = obj.labels
                    if "dataclass" in labels:
                        _type_class = " .doc-type-class"
                    elif "enum" in labels:
                        _type_class = " .doc-type-enum"

            _attr_block = f"{{ {_anchor_id}{_type_class} }}"
            return f"{'#' * self.crnt_header_level} {_str_dispname} {_attr_block}"
        elif isinstance(el, ds.DocstringSection):
            title = el.title or el.kind.value.title()
            anchor_part = _sanitize_title(title.lower())
            _classes = [".doc-section", f".doc-section-{anchor_part}"]
            _str_classes = " ".join(_classes)
            return f"{'#' * self.crnt_header_level} {title} {{{_str_classes}}}"
        else:
            raise NotImplementedError(f"render_header not supported for: {type(el)}")

    # render ------------------------------------------------------------------

    def render(self, el: object) -> "str | ParamRow | list":
        """Return a string representation of an object, or layout element.

        Dispatches based on the type of el.
        """
        # Simple types
        if isinstance(el, str):
            return el

        # Layout types (most specific first)
        if isinstance(el, layout.Interlaced):
            return self._render_interlaced(el)
        if isinstance(el, (layout.DocClass, layout.DocModule)):
            return self._render_doc_class_module(el)
        if isinstance(el, (layout.DocFunction, layout.DocAttribute)):
            return self._render_doc_func_attr(el)
        if isinstance(el, layout.Doc):
            raise NotImplementedError(f"Unsupported Doc type: {type(el)}")
        if isinstance(el, layout.Page):
            return self._render_page(el)
        if isinstance(el, layout.Section):
            return self._render_section(el)

        # AST patched types (must come before docstring section types)
        if isinstance(el, DocstringSectionWarnings):
            return _convert_rst_text(el.value)
        if isinstance(el, DocstringSectionSeeAlso):
            return convert_rst_link_to_md(el.value)
        if isinstance(el, DocstringSectionNotes):
            return _convert_rst_text(el.value)
        if isinstance(el, ExampleCode):
            return f"```python\n{el.value}\n```"
        if isinstance(el, ExampleText):
            return _fence_doctest_blocks(el.value)

        # Docstring section types
        if isinstance(el, ds.DocstringSectionText):
            return self._render_section_text(el)
        if isinstance(el, ds.DocstringSectionParameters):
            return self._render_section_parameters(el)
        if isinstance(el, ds.DocstringSectionAttributes):
            return self._render_section_attributes(el)
        if isinstance(el, ds.DocstringSectionAdmonition):
            return self._render_section_admonition(el)
        if isinstance(el, ds.DocstringSectionExamples):
            return self._render_section_examples(el)
        if isinstance(el, (ds.DocstringSectionReturns, ds.DocstringSectionRaises)):
            return self._render_section_returns_or_raises(el)

        # Docstring element types (return ParamRow)
        if isinstance(el, ds.DocstringParameter):
            return self._render_docstring_parameter(el)
        if isinstance(el, ds.DocstringReturn):
            return self._render_docstring_return(el)
        if isinstance(el, ds.DocstringRaise):
            return self._render_docstring_raise(el)
        if isinstance(el, ds.DocstringAttribute):
            return self._render_docstring_attribute(el)

        # Griffe types
        if isinstance(el, dc.Docstring):
            return self._render_docstring(el)
        if isinstance(el, dc.Parameters):
            return self._render_parameters(el)
        if isinstance(el, dc.Parameter):
            return self._render_parameter(el)
        if isinstance(el, (dc.Object, dc.Alias)):
            return self._render_object(el)

        # Unsupported types that should raise
        if isinstance(
            el,
            (
                ds.DocstringAdmonition,
                ds.DocstringDeprecated,
                ds.DocstringWarn,
                ds.DocstringYield,
                ds.DocstringReceive,
            ),
        ):
            raise NotImplementedError(f"{type(el)}")

        raise NotImplementedError(f"Unsupported type: {type(el)}")

    # --- Render implementations ---

    def _render_page(self, el: layout.Page) -> str:
        if el.summary:
            sum_ = el.summary
            header = [f"{'#' * self.crnt_header_level} {sum_.name}\n\n{sum_.desc}"]
        else:
            header = []

        result = map(self.render, el.contents)
        return "\n\n".join([*header, *result])

    def _render_section(self, el: layout.Section) -> str:
        section_top = f"{'#' * self.crnt_header_level} {el.title}\n\n{el.desc}"

        with self._increment_header():
            body = list(map(self.render, el.contents))

        return "\n\n".join([section_top, *body])

    def _render_interlaced(self, el: layout.Interlaced) -> str:
        for doc in el.contents:
            if not isinstance(doc, (layout.DocFunction, layout.DocAttribute)):
                raise NotImplementedError(
                    "Can only render Interlaced elements if all content elements"
                    " are function or attribute docs."
                    f" Found an element of type {type(doc)}, with name {doc.name}"
                )

        first_doc = el.contents[0]
        objs = [doc.obj for doc in el.contents]

        if first_doc.obj.docstring is None:
            raise ValueError("The first element of Interlaced must have a docstring.")

        str_title = self.render_header(first_doc)
        str_sig = "\n\n".join(map(self.signature, objs))
        str_body = []

        for section in qast.transform(first_doc.obj.docstring.parsed):
            title = section.title or section.kind.value
            body = self.render(section)

            if title != "text":
                header = f"{'#' * (self.crnt_header_level + 1)} {title.title()}"
                str_body.append("\n\n".join([header, body]))
            else:
                str_body.append(body)

        if self.show_signature:
            parts = [str_title, str_sig, *str_body]
        else:
            parts = [str_title, *str_body]

        return "\n\n".join(parts)

    def _render_doc_class_module(self, el: "layout.DocClass | layout.DocModule") -> str:
        title = self.render_header(el)

        attr_docs = []
        meth_docs = []
        class_docs = []

        if el.members:
            sub_header = "#" * (self.crnt_header_level + 1)
            raw_attrs = [x for x in el.members if x.obj.is_attribute]
            raw_meths = [x for x in el.members if x.obj.is_function]
            raw_classes = [x for x in el.members if x.obj.is_class]

            header = "| Name | Description |\n| --- | --- |"

            # For dataclasses, augment the member-based attribute list with any
            # fields that griffe missed during static analysis.  Dataclass
            # fields already appear in the Parameters section, so only
            # non-field attributes (e.g. properties) go into the Attributes
            # table.
            if (
                isinstance(el, layout.DocClass)
                and _is_griffe_dataclass(el.obj)
                and not _has_attr_section(el.obj.docstring)
            ):
                dc_field_names = _get_dataclass_field_names(el.obj)
                dc_field_set = set(dc_field_names) if dc_field_names else set()

                # Separate field attrs (already in Parameters) from non-field
                # attrs (properties, class vars, etc.) that belong in
                # Attributes.
                non_field_attrs = [x for x in raw_attrs if x.obj.name not in dc_field_set]

                if non_field_attrs:
                    _attrs_table = "\n".join(map(self.summarize, non_field_attrs))
                    attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                    attr_docs.append(attrs)
            elif raw_attrs and not _has_attr_section(el.obj.docstring):
                _attrs_table = "\n".join(map(self.summarize, raw_attrs))
                attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                attr_docs.append(attrs)

            if raw_classes:
                _summary_table = "\n".join(map(self.summarize, raw_classes))
                section_name = "Classes"
                objs = f"{sub_header} {section_name}\n\n{header}\n{_summary_table}"
                class_docs.append(objs)

                n_incr = 1 if el.flat else 2
                with self._increment_header(n_incr):
                    rendered = [self.render(x) for x in raw_classes if isinstance(x, layout.Doc)]
                    if rendered:
                        # Solid separator after summary table
                        class_docs.append("---")
                        # Dotted separators between member docs
                        class_docs.append("\n\n---\n\n".join(rendered))

            if raw_meths:
                _summary_table = "\n".join(map(self.summarize, raw_meths))
                section_name = "Methods" if isinstance(el, layout.DocClass) else "Functions"
                objs = f"{sub_header} {section_name}\n\n{header}\n{_summary_table}"
                meth_docs.append(objs)

                n_incr = 1 if el.flat else 2
                with self._increment_header(n_incr):
                    rendered = [self.render(x) for x in raw_meths if isinstance(x, layout.Doc)]
                    if rendered:
                        # Solid separator after summary table
                        meth_docs.append("---")
                        # Dotted separators between member docs
                        meth_docs.append("\n\n---\n\n".join(rendered))

        str_sig = self.signature(el)
        sig_part = [str_sig] if self.show_signature else []

        with self._increment_header():
            body = self.render(el.obj)

        return "\n\n".join([title, *sig_part, body, *attr_docs, *class_docs, *meth_docs])

    def _render_doc_func_attr(self, el: "layout.DocFunction | layout.DocAttribute") -> str:
        title = self.render_header(el)

        str_sig = self.signature(el)
        sig_part = [str_sig] if self.show_signature else []

        with self._increment_header():
            body = self.render(el.obj)

        return "\n\n".join([title, *sig_part, body])

    def _render_object(self, el: "dc.Object | dc.Alias") -> str:
        if el.docstring is None:
            return ""
        else:
            return self._render_docstring(el.docstring)

    def _render_docstring(self, el: dc.Docstring) -> str:
        str_body = []
        patched_sections = qast.transform(el.parsed)

        for section in patched_sections:
            title = section.title or section.kind.value
            body: str = self.render(section)

            if title != "text":
                header = self.render_header(section)
                str_body.append("\n\n".join([header, body]))
            else:
                str_body.append(body)

        parts = [*str_body]
        return "\n\n".join(parts)

    def _render_parameters(self, el: "dc.Parameters | dc.Object") -> list[str]:
        """Render dc.Parameters to list of strings."""
        if isinstance(el, dc.Parameters):
            params = el
        elif hasattr(el, "parameters"):
            params = self._fetch_method_parameters(el)
        else:
            return []

        try:
            kw_only = [par.kind for par in params].index(dc.ParameterKind.keyword_only)
        except ValueError:
            kw_only = None

        try:
            pos_only = max(
                [ii for ii, p in enumerate(params) if p.kind == dc.ParameterKind.positional_only]
            )
        except ValueError:
            pos_only = None

        pars = [self._render_parameter(p) for p in params]

        if (
            kw_only is not None
            and kw_only > 0
            and params[kw_only - 1].kind != dc.ParameterKind.var_positional
        ):
            pars.insert(kw_only, "*")

        if pos_only is not None:
            pars.insert(pos_only + 1, "/")

        return pars

    def _render_parameter(self, el: dc.Parameter) -> str:
        splats = {dc.ParameterKind.var_keyword, dc.ParameterKind.var_positional}
        has_default = el.default and el.kind not in splats

        if el.kind == dc.ParameterKind.var_keyword:
            glob = "**"
        elif el.kind == dc.ParameterKind.var_positional:
            glob = "*"
        else:
            glob = ""

        annotation = el.annotation
        name = el.name

        if self.show_signature_annotations:
            if annotation and has_default:
                res = f"{glob}{name}: {annotation} = {el.default}"
            elif annotation:
                res = f"{glob}{name}: {annotation}"
            else:
                res = f"{glob}{name}"
        elif has_default:
            res = f"{glob}{name}={el.default}"
        else:
            res = f"{glob}{name}"

        return res

    def _render_section_text(self, el: ds.DocstringSectionText) -> str:
        new_el = qast.transform(el)
        if isinstance(new_el, ds.DocstringSectionText):
            text = _convert_rst_text(el.value)
            # Fence unfenced >>> doctest blocks as ```python
            text = _fence_doctest_blocks(text)
            # Bold section headers (e.g. **Examples**::) → proper headings
            text = _convert_bold_section_headers(text, self.crnt_header_level)
            # Sphinx-style :param: / :returns: / :raises: → sections with tables
            text = _convert_sphinx_fields(text, self.crnt_header_level)
            # Google-style Args: / Returns: / Raises: → sections with tables
            text = _convert_google_sections(text, self.crnt_header_level)
            return text
        return self.render(new_el)

    def _render_section_parameters(self, el: ds.DocstringSectionParameters) -> str:
        rows: list[ParamRow] = [self._render_docstring_parameter(p) for p in el.value]
        header = ["Name", "Type", "Description", "Default"]
        return self._render_table(rows, header, "parameters")

    def _render_docstring_parameter(self, el: ds.DocstringParameter) -> ParamRow:
        annotation = self.render_annotation(el.annotation)
        return ParamRow(el.name, el.description, annotation=annotation, default=el.default)

    def _render_section_attributes(self, el: ds.DocstringSectionAttributes) -> str:
        header = ["Name", "Type", "Description"]
        rows = [self._render_docstring_attribute(a) for a in el.value]
        return self._render_table(rows, header, "attributes")

    def _render_docstring_attribute(self, el: ds.DocstringAttribute) -> ParamRow:
        return ParamRow(
            el.name,
            el.description or "",
            annotation=self.render_annotation(el.annotation),
        )

    def _render_section_admonition(self, el: ds.DocstringSectionAdmonition) -> str:
        kind = el.title.lower()
        if kind in ["notes", "warnings"]:
            return el.value.description
        elif kind == "see also":
            return convert_rst_link_to_md(el.value.description)
        return el.value.description

    def _render_section_examples(self, el: ds.DocstringSectionExamples) -> str:
        data = map(qast.transform, el.value)
        return "\n\n".join(list(map(self.render, data)))

    def _render_section_returns_or_raises(
        self, el: "ds.DocstringSectionReturns | ds.DocstringSectionRaises"
    ) -> str:
        rows = []
        for item in el.value:
            if isinstance(item, ds.DocstringRaise):
                rows.append(self._render_docstring_raise(item))
            else:
                rows.append(self._render_docstring_return(item))
        header = ["Name", "Type", "Description"]
        return self._render_table(rows, header, "returns")

    def _render_docstring_return(self, el: ds.DocstringReturn) -> ParamRow:
        return ParamRow(
            el.name,
            el.description,
            annotation=self.render_annotation(el.annotation),
        )

    def _render_docstring_raise(self, el: ds.DocstringRaise) -> ParamRow:
        return ParamRow(
            None,
            el.description,
            annotation=self.render_annotation(el.annotation),
        )

    # Summarize ===============================================================

    @staticmethod
    def _summary_row(link: str, description: str) -> str:
        return f"| {link} | {sanitize(description, allow_markdown=True)} |"

    def summarize(self, el: object, *args: object, **kwargs: object) -> str:
        """Produce a summary table."""
        if isinstance(el, layout.Layout):
            rendered_sections = list(map(self.summarize, el.sections))
            return "\n\n".join(rendered_sections)

        if isinstance(el, layout.Section):
            desc = f"\n\n{el.desc}" if el.desc is not None else ""
            if el.title is not None:
                header = f"## {el.title}{desc}"
            elif el.subtitle is not None:
                header = f"### {el.subtitle}{desc}"
            else:
                header = ""

            if el.contents:
                thead = "| | |\n| --- | --- |"

                rendered = []
                for child in el.contents:
                    rendered.append(self.summarize(child))

                str_func_table = "\n".join([thead, *rendered])
                return f"{header}\n\n{str_func_table}"

            return header

        if isinstance(el, layout.MemberPage):
            return self.summarize(el.contents[0], el.path, shorten=True)

        if isinstance(el, layout.Page):
            if el.summary is not None:
                return self._summary_row(f"[{el.summary.name}]({el.path}.qmd)", el.summary.desc)

            if len(el.contents) > 1 and not el.flatten:
                raise ValueError(
                    "Cannot summarize Page. Either set its `summary` attribute with name "
                    "and description details, or set `flatten` to True."
                )

            else:
                rows = [self.summarize(entry, el.path) for entry in el.contents]
                return "\n".join(rows)

        if isinstance(el, layout.Interlaced):
            rows = [self.summarize(doc, *args, **kwargs) for doc in el.contents]
            return "\n".join(rows)

        if isinstance(el, layout.Link):
            description = self.summarize(el.obj)
            return self._summary_row(f"[](`~{el.name}`)", description)

        if isinstance(el, layout.Doc):
            path = args[0] if args else kwargs.get("path", None)
            display_name = _escape_dunders(el.name)

            if path is None:
                link = f"[{display_name}](#{el.anchor})"
            else:
                link = f"[{display_name}]({path}.qmd#{el.anchor})"

            description = self.summarize(el.obj)
            return self._summary_row(link, description)

        if isinstance(el, (dc.Object, dc.Alias)):
            doc = el.docstring
            if doc is None:
                docstring_parts = []
            else:
                docstring_parts = doc.parsed

            if len(docstring_parts) and isinstance(docstring_parts[0], ds.DocstringSectionText):
                description = docstring_parts[0].value
                short = description.split("\n")[0]
                return short

            return ""

        raise NotImplementedError(f"Unsupported type: {type(el)}")
