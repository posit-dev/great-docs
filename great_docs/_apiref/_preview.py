"""
Debug previewer that prints a griffe/docstring object as an indented tree

Development tooling only — nothing in the render pipeline uses it.
"""

from __future__ import annotations

import warnings
from dataclasses import fields as dc_fields

import griffe as gf

from ._docstring_sections import ExampleCode, ExampleText, transform
from ._walkable import MISSING, Walkable


def fields(el: object) -> list[str] | list[int] | None:
    """List the relevant fields for an object, for preview purposes"""

    # dataclass types (ExampleCode, ExampleText)
    if isinstance(el, (ExampleCode, ExampleText)):
        return [field.name for field in dc_fields(el)]

    # griffe types (most specific first)
    if isinstance(el, gf.Function):
        return ["name", "annotation", "parameters", "docstring"]

    if isinstance(el, gf.Attribute):
        return ["name", "annotation"]

    if isinstance(el, gf.Docstring):
        return ["parser", "parsed"]

    if isinstance(el, gf.Parameter):
        return ["annotation", "kind", "name", "default"]

    # docstring types
    if isinstance(el, gf.DocstringParameter):
        return ["annotation", "default", "description", "name", "value"]

    if isinstance(el, gf.DocstringNamedElement):
        return ["name", "annotation", "description"]

    if isinstance(el, gf.DocstringElement):
        return ["annotation", "description"]

    if isinstance(el, gf.DocstringSection):
        return ["kind", "title", "value"]

    # Alias (must come before Object since Alias also has Object-like behavior)
    if isinstance(el, gf.Alias):
        try:
            return fields(el.target)
        except gf.AliasResolutionError:
            warnings.warn(
                f"Could not resolve Alias target `{el.target_path}`."
                " This often occurs because the module was not loaded."
            )
            return ["name", "target_path"]

    if isinstance(el, gf.Object):
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

    # node dataclass models
    if isinstance(el, Walkable):
        field_defaults = {f.name: f.default for f in dc_fields(el)}
        return [
            k for k, v in el._iter_fields() if field_defaults.get(k) is not v and v is not MISSING
        ]

    if isinstance(el, dict):
        return list(el.keys())

    if isinstance(el, (list, gf.Parameters)):
        return list(range(len(el)))

    return None


class Formatter:
    n_spaces = 3
    icon_block = "█─"
    icon_pipe = "├─"
    icon_endpipe = "└─"
    icon_connector = "│ "
    string_truncate_mark = " ..."

    def __init__(
        self, string_max_length: int = 50, max_depth: int = 999, compact: bool = False
    ) -> None:
        self.string_max_length = string_max_length
        self.max_depth = max_depth
        self.compact = compact

    def format(self, call: object, depth: int = 0, pad: int = 0) -> str:
        """Format `call` as a tree diagram, with boxes for nodes"""

        call = transform(call)

        current_fields = fields(call)

        if current_fields is None:
            str_repr = repr(call)
            if len(str_repr) > self.string_max_length:
                return str_repr[: self.string_max_length] + self.string_truncate_mark

            return str_repr

        call_str = self.icon_block + call.__class__.__name__

        if depth >= self.max_depth:
            return call_str + self.string_truncate_mark

        fields_str = []
        for name in current_fields:
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

    def get_field(self, obj: object, k: str | int) -> object:
        if isinstance(obj, (dict, list, gf.Parameters)):
            return obj[k]

        return getattr(obj, k)

    def fmt_pipe(self, x: str, is_final: bool = False, pad: int = 0) -> str:
        if not is_final:
            connector = self.icon_connector
            prefix = self.icon_pipe
        else:
            connector = "  "
            prefix = self.icon_endpipe

        connector = "\n" + " " * pad + connector
        prefix = "\n" + " " * pad + prefix
        return prefix + connector.join(x.splitlines())


def preview(
    ast: "gf.Object | gf.Docstring | object",
    max_depth: int = 999,
    compact: bool = False,
    as_string: bool = False,
) -> str | None:
    """Print a friendly representation of a griffe object, or return it as a string"""

    res = Formatter(max_depth=max_depth, compact=compact).format(ast)

    if as_string:
        return res

    print(res)
