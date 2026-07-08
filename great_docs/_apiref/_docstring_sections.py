"""
great-docs extensions to griffe's docstring model

Docstring sections for documenting dataclasses (the `DC` prefix), plus
patched section types (See Also / Notes / Warnings) and example-block
values that griffe does not model on its own; for everything griffe
already provides, import `griffe` directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Type

import griffe as gf

__all__ = (
    "DCDocstringSection",
    "DCDocstringSectionInitParameters",
    "DCDocstringSectionKind",
    "DCDocstringSectionParameterAttributes",
    "DocstringSectionKindPatched",
    "DocstringSectionNotes",
    "DocstringSectionSeeAlso",
    "DocstringSectionWarnings",
    "ExampleCode",
    "ExampleText",
    "transform",
    "tuple_to_data",
)


class DCDocstringSectionKind(str, Enum):
    """
    Enumeration of the docstring section kinds specific to dataclasses
    """

    init_parameters = "init parameters"
    """Init only parameters of a dataclass"""

    parameter_attributes = "parameter attributes"
    """Parameters and at the same time attributes of a dataclass"""


class DCDocstringSection:
    """
    A docstring section specific to dataclasses
    """

    kind: DCDocstringSectionKind  # pragma: no cover
    """The section kind."""

    def __init__(self, value: list[gf.DocstringParameter], title: str):
        self.value = value
        self.title = title

    def __bool__(self) -> bool:
        """Whether this section has a true-ish value."""
        return bool(self.value)


class DCDocstringSectionParameterAttributes(DCDocstringSection):
    """
    A parameter attributes section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.parameter_attributes


class DCDocstringSectionInitParameters(DCDocstringSection):
    """
    An init parameters section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.init_parameters


def transform(el: object) -> object:
    """Cast `el` to a more specific docstring element, falling back to `el` itself"""

    if isinstance(el, tuple):
        try:
            return tuple_to_data(el)
        except ValueError:
            pass

    elif isinstance(el, list) and len(el) and isinstance(el[0], gf.DocstringSection):
        return _DocstringSectionPatched.transform_all(el)

    return el


# Patch DocstringSection ------------------------------------------------------


class DocstringSectionKindPatched(Enum):
    see_also = "see also"
    notes = "notes"
    warnings = "warnings"


class _DocstringSectionPatched(gf.DocstringSection):
    _registry: "dict[str, Type[_DocstringSectionPatched]]" = {}

    def __init__(self, value: str, title: "str | None" = None) -> None:
        super().__init__(title)
        self.value = value

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        if cls.kind.value in cls._registry:
            raise KeyError(f"A section for kind {cls.kind} already exists")

        cls._registry[cls.kind.value] = cls

    @staticmethod
    def split_sections(text: str) -> list[tuple[str, str]]:
        """Split text into (title, body) tuples for all numpydoc style sections"""
        comp = re.compile(r"^([\S \t]+)\n-+$\n?", re.MULTILINE)

        current_match = comp.search(text)
        current_pos = 0

        results = []
        while current_match is not None:
            if current_pos == 0 and current_match.start() > 0:
                results.append(("", text[: current_match.start()]))

            next_pos = current_pos + current_match.end()
            substr = text[next_pos:]
            next_match = comp.search(substr)

            title = current_match.groups()[0]
            body = substr if next_match is None else substr[: next_match.start()]

            results.append((title, body))

            current_match, current_pos = next_match, next_pos

        return results

    @classmethod
    def transform(cls, el: gf.DocstringSection) -> list[gf.DocstringSection]:
        """Cast `el` to a more specific `DocstringSection` type, when possible"""

        if not isinstance(el, (gf.DocstringSectionText, gf.DocstringSectionAdmonition)):
            return [el]

        results = []

        if isinstance(el, gf.DocstringSectionText):
            splits = cls.split_sections(el.value)
            for title, body in splits:
                sub_cls = cls._registry.get(title.lower(), gf.DocstringSectionText)
                results.append(sub_cls(body, title))
        elif isinstance(el, gf.DocstringSectionAdmonition):
            sub_cls = cls._registry.get(el.title.lower(), None)
            if sub_cls:
                results.append(sub_cls(el.value.contents, el.title))
            else:
                results.append(el)

        return results or [el]

    @classmethod
    def transform_all(cls, el: list[gf.DocstringSection]) -> list[gf.DocstringSection]:
        return [section for item in el for section in cls.transform(item)]


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


def tuple_to_data(el: "tuple[gf.DocstringSectionKind, str]") -> ExampleCode | ExampleText:
    """Build an `ExampleCode` or `ExampleText` from the example-section tuple"""
    assert len(el) == 2

    kind, value = el
    if kind.value == "examples":
        return ExampleCode(value)
    elif kind.value == "text":
        return ExampleText(value)

    raise ValueError(f"Unsupported first element in tuple: {kind}")
