from __future__ import annotations

import dataclasses as _dc_mod
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Type

from ._griffe import AliasResolutionError
from ._griffe import dataclasses as dc
from ._griffe import docstrings as ds
from .layout import _Base as LayoutBase


def transform(el):
    """Return a more specific docstring element, or simply return the original one."""

    if isinstance(el, tuple):
        try:
            return tuple_to_data(el)
        except ValueError:
            pass

    elif isinstance(el, list) and len(el) and isinstance(el[0], ds.DocstringSection):
        return _DocstringSectionPatched.transform_all(el)

    return el


# Patch DocstringSection ------------------------------------------------------


class DocstringSectionKindPatched(Enum):
    see_also = "see also"
    notes = "notes"
    warnings = "warnings"


class _DocstringSectionPatched(ds.DocstringSection):
    _registry: "dict[str, Type[_DocstringSectionPatched]]" = {}

    def __init__(self, value: str, title: "str | None" = None):
        super().__init__(title)
        self.value = value

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if cls.kind.value in cls._registry:
            raise KeyError(f"A section for kind {cls.kind} already exists")

        cls._registry[cls.kind.value] = cls

    @staticmethod
    def split_sections(text) -> list[tuple[str, str]]:
        """Return tuples of (title, body) for all numpydoc style sections in the text."""
        import re

        comp = re.compile(r"^([\S \t]+)\n-+$\n?", re.MULTILINE)

        crnt_match = comp.search(text)
        crnt_pos = 0

        results = []
        while crnt_match is not None:
            if crnt_pos == 0 and crnt_match.start() > 0:
                results.append(("", text[: crnt_match.start()]))

            next_pos = crnt_pos + crnt_match.end()
            substr = text[next_pos:]
            next_match = comp.search(substr)

            title = crnt_match.groups()[0]
            body = substr if next_match is None else substr[: next_match.start()]

            results.append((title, body))

            crnt_match, crnt_pos = next_match, next_pos

        return results

    @classmethod
    def transform(cls, el: ds.DocstringSection) -> list[ds.DocstringSection]:
        """Attempt to cast DocstringSection element to more specific section type."""

        if not isinstance(el, (ds.DocstringSectionText, ds.DocstringSectionAdmonition)):
            return [el]

        results = []

        if isinstance(el, ds.DocstringSectionText):
            splits = cls.split_sections(el.value)
            for title, body in splits:
                sub_cls = cls._registry.get(title.lower(), ds.DocstringSectionText)
                results.append(sub_cls(body, title))
        elif isinstance(el, ds.DocstringSectionAdmonition):
            sub_cls = cls._registry.get(el.title.lower(), None)
            if sub_cls:
                results.append(sub_cls(el.value.contents, el.title))
            else:
                results.append(el)

        return results or [el]

    @classmethod
    def transform_all(cls, el: list[ds.DocstringSection]) -> list[ds.DocstringSection]:
        return sum(map(cls.transform, el), [])


class DocstringSectionSeeAlso(_DocstringSectionPatched):
    kind = DocstringSectionKindPatched.see_also


class DocstringSectionNotes(_DocstringSectionPatched):
    kind = DocstringSectionKindPatched.notes


class DocstringSectionWarnings(_DocstringSectionPatched):
    kind = DocstringSectionKindPatched.warnings


# Patch Example elements ------------------------------------------------------


@dataclass
class ExampleCode:
    value: str


@dataclass
class ExampleText:
    value: str


def tuple_to_data(el: "tuple[ds.DocstringSectionKind, str]"):
    """Re-format funky tuple setup in example section to be a class."""
    assert len(el) == 2

    kind, value = el
    if kind.value == "examples":
        return ExampleCode(value)
    elif kind.value == "text":
        return ExampleText(value)

    raise ValueError(f"Unsupported first element in tuple: {kind}")


# Tree previewer ==============================================================


def fields(el):
    """Return the relevant fields for an object, for preview purposes.

    Replaces plum dispatch with isinstance-based dispatch.
    """

    # dataclass types (ExampleCode, ExampleText)
    if isinstance(el, (ExampleCode, ExampleText)):
        from dataclasses import fields as _fields

        return [field.name for field in _fields(el)]

    # griffe types (most specific first)
    if isinstance(el, dc.Function):
        return ["name", "annotation", "parameters", "docstring"]

    if isinstance(el, dc.Attribute):
        return ["name", "annotation"]

    if isinstance(el, dc.Docstring):
        return ["parser", "parsed"]

    if isinstance(el, dc.Parameter):
        return ["annotation", "kind", "name", "default"]

    # docstring types
    if isinstance(el, ds.DocstringParameter):
        return ["annotation", "default", "description", "name", "value"]

    if isinstance(el, ds.DocstringNamedElement):
        return ["name", "annotation", "description"]

    if isinstance(el, ds.DocstringElement):
        return ["annotation", "description"]

    if isinstance(el, ds.DocstringSection):
        return ["kind", "title", "value"]

    # Alias (must come before Object since Alias also has Object-like behavior)
    if isinstance(el, dc.ObjectAliasMixin) and isinstance(el, dc.Alias):
        try:
            return fields(el.target)
        except AliasResolutionError:
            warnings.warn(
                f"Could not resolve Alias target `{el.target_path}`."
                " This often occurs because the module was not loaded."
            )
            return ["name", "target_path"]

    if isinstance(el, dc.Object):
        options = [
            "name",
            "canonical_path",
            "classes",
            "parameters",
            "members",
            "functions",
            "docstring",
        ]
        return [opt for opt in options if hasattr(el, opt)]

    # layout dataclass models
    if isinstance(el, LayoutBase):
        from .layout import MISSING

        field_defaults = {f.name: f.default for f in _dc_mod.fields(el)}
        return [
            k
            for k, v in el._iter_fields()
            if field_defaults.get(k) is not v and not isinstance(v, MISSING)
        ]

    if isinstance(el, dict):
        return list(el.keys())

    if isinstance(el, (list, dc.Parameters)):
        return list(range(len(el)))

    return None


class Formatter:
    n_spaces = 3
    icon_block = "█─"
    icon_pipe = "├─"
    icon_endpipe = "└─"
    icon_connector = "│ "
    string_truncate_mark = " ..."

    def __init__(self, string_max_length: int = 50, max_depth=999, compact=False):
        self.string_max_length = string_max_length
        self.max_depth = max_depth
        self.compact = compact

    def format(self, call, depth=0, pad=0):
        """Return a nice tree, with boxes for nodes."""

        call = transform(call)

        crnt_fields = fields(call)

        if crnt_fields is None:
            str_repr = repr(call)
            if len(str_repr) > self.string_max_length:
                return str_repr[: self.string_max_length] + self.string_truncate_mark

            return str_repr

        call_str = self.icon_block + call.__class__.__name__

        if depth >= self.max_depth:
            return call_str + self.string_truncate_mark

        fields_str = []
        for name in crnt_fields:
            val = self.get_field(call, name)

            if self.compact:
                sub_pad = pad
                linebreak = "\n" if fields(val) else ""
            else:
                sub_pad = len(str(name)) + self.n_spaces
                linebreak = ""

            formatted_val = self.format(val, depth + 1, pad=sub_pad)
            fields_str.append(f"{name} = {linebreak}{formatted_val}")

        padded = []
        for ii, entry in enumerate(fields_str):
            is_final = ii == len(fields_str) - 1

            chunk = self.fmt_pipe(entry, is_final=is_final, pad=pad)
            padded.append(chunk)

        return "".join([call_str, *padded])

    def get_field(self, obj, k):
        if isinstance(obj, (dict, list, dc.Parameters)):
            return obj[k]

        return getattr(obj, k)

    def fmt_pipe(self, x, is_final=False, pad=0):
        if not is_final:
            connector = self.icon_connector if not is_final else "  "
            prefix = self.icon_pipe
        else:
            connector = "  "
            prefix = self.icon_endpipe

        connector = "\n" + " " * pad + connector
        prefix = "\n" + " " * pad + prefix
        return prefix + connector.join(x.splitlines())


def preview(
    ast: "dc.Object | ds.Docstring | object",
    max_depth=999,
    compact=False,
    as_string: bool = False,
):
    """Print a friendly representation of a griffe object."""

    res = Formatter(max_depth=max_depth, compact=compact).format(ast)

    if as_string:
        return res

    print(res)
