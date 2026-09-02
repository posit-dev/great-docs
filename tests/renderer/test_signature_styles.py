"""Tests for `render_signature` — covering the non-callable kinds
(`TypedDict`, `Enum`) that must render without an empty call bracket, both
base-class spellings each accepts, and the `@dataclass` precedence that
overrides both."""

from __future__ import annotations

import textwrap

import griffe as gf

from great_docs._apiref._tools import _render


def _rendered(source: str, name: str) -> str:
    """Render the named object of a source snippet to qmd"""
    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}
    ) as package:
        return _render(package[name])


def test_typeddict_signature_has_no_brackets():
    """A TypedDict is a structural type, not a constructor"""
    source = '''
    from typing import TypedDict

    class Point(TypedDict):
        """A point."""

        x: int
    '''

    qmd = _rendered(source, "Point")

    assert "Point()" not in qmd
    assert "Point" in qmd


def test_enum_signature_has_no_brackets():
    """An enum is reached through its members, not by calling it"""
    source = '''
    from enum import Enum

    class Colour(Enum):
        """A colour."""

        RED = 1
    '''

    qmd = _rendered(source, "Colour")

    assert "Colour()" not in qmd


def test_typeddict_signature_has_no_brackets_with_qualified_base():
    """A `typing.TypedDict` base, spelled out, is still recognised"""
    source = '''
    import typing

    class Point(typing.TypedDict):
        """A point."""

        x: int
    '''

    qmd = _rendered(source, "Point")

    assert "Point()" not in qmd


def test_enum_signature_has_no_brackets_with_qualified_base():
    """An `enum.Enum` base, spelled out, is still recognised"""
    source = '''
    import enum

    class Colour(enum.Enum):
        """A colour."""

        RED = 1
    '''

    qmd = _rendered(source, "Colour")

    assert "Colour()" not in qmd


def test_dataclass_typeddict_keeps_its_brackets():
    """A `@dataclass`-decorated `TypedDict` is a dataclass first"""
    source = '''
    from dataclasses import dataclass
    from typing import TypedDict

    @dataclass
    class Point(TypedDict):
        """A point."""

        x: int
    '''

    qmd = _rendered(source, "Point")

    # The dataclass constructor takes `x`, so the call brackets are not only
    # present but also carry the parameter — proof this took the ordinary
    # call-signature path rather than the bracket-less one.
    assert "Point(x)" in qmd


def test_dataclass_enum_keeps_its_brackets():
    """A `@dataclass`-decorated `Enum` is a dataclass first"""
    source = '''
    from dataclasses import dataclass
    from enum import Enum

    @dataclass
    class Colour(Enum):
        """A colour."""

        RED = 1
    '''

    qmd = _rendered(source, "Colour")

    assert "Colour()" in qmd


def test_ordinary_class_keeps_its_brackets():
    """A class that is called still shows that it is called"""
    source = '''
    class Widget:
        """A widget."""

        def __init__(self):
            pass
    '''

    qmd = _rendered(source, "Widget")

    assert "Widget()" in qmd
