"""
Tests for `render_signature`

Covers the non-callable kinds (`TypedDict`, `Enum`) that must render without
an empty call bracket, both base-class spellings each accepts, the
re-export that documents one under a package's own name, the `@dataclass`
precedence that overrides both, and the inline markup the `plain` style
writes.
"""

from __future__ import annotations

import textwrap

import griffe as gf
import pytest

from great_docs._apiref import _globals
from great_docs._apiref._tools import _render


def _rendered(source: str, name: str) -> str:
    """Render the named object of a source snippet to qmd"""
    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}
    ) as package:
        return _render(package[name])


def _rendered_reexport(source: str, name: str) -> str:
    """Render an object through the package name that re-exports it"""
    modules = {
        "__init__.py": f"from ._defs import {name}\n",
        "_defs.py": textwrap.dedent(source),
    }
    with gf.temporary_visited_package("package", modules) as package:
        return _render(package[name])


@pytest.fixture
def highlight_style():
    """Set the highlight style for one test and restore it afterwards"""
    original = _globals.SETTINGS.callable_signatures.style

    def apply(style: str) -> None:
        _globals.SETTINGS.callable_signatures.style = style

    yield apply
    _globals.SETTINGS.callable_signatures.style = original


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


def test_reexported_typeddict_signature_has_no_brackets():
    """Render a re-exported TypedDict without call brackets"""
    source = '''
    from typing import TypedDict

    class Point(TypedDict):
        """A point."""

        x: int
    '''

    qmd = _rendered_reexport(source, "Point")

    assert "Point()" not in qmd
    assert "Point" in qmd


def test_reexported_enum_signature_has_no_brackets():
    """Render a re-exported enum without call brackets"""
    source = '''
    from enum import Enum

    class Colour(Enum):
        """A colour."""

        RED = 1
    '''

    qmd = _rendered_reexport(source, "Colour")

    assert "Colour()" not in qmd


def test_reexported_class_keeps_its_brackets():
    """Render call brackets for a re-exported ordinary class"""
    source = '''
    class Widget:
        """A widget."""

        def __init__(self):
            pass
    '''

    qmd = _rendered_reexport(source, "Widget")

    assert "Widget()" in qmd


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


def test_plain_style_emits_inline_markup(highlight_style):
    """The `plain` style writes the signature as inline markup"""
    highlight_style("plain")
    source = '''
    def connect(host, port=8080):
        """Connect to a host."""
    '''

    qmd = _rendered(source, "connect")

    # At the qmd stage a class still reads as a pandoc span (`[text]{.class}`)
    # rather than literal HTML; Quarto converts it to `<span class="...">`
    # only once it renders the page, the same way DocTypeAlias's signature
    # already does (see tests/renderer/test_type_aliases.py).
    assert "sourceCode" not in qmd
    assert "[connect]{.sig-name}" in qmd
    assert "[host]{.doc-parameter-name}" in qmd


def test_plain_style_keeps_the_line_breaks(highlight_style):
    """Indentation survives inside a code element that has no pre"""
    highlight_style("plain")
    source = '''
    def connect(host, port=8080):
        """Connect to a host."""
    '''

    qmd = _rendered(source, "connect")

    assert "<br>" in qmd
    assert "&nbsp;" in qmd


def test_plain_style_highlights_a_numeric_default(highlight_style):
    """A literal default gets the same class the highlighted style gives it"""
    highlight_style("plain")
    source = '''
    def connect(host, port=8080):
        """Connect to a host."""
    '''

    qmd = _rendered(source, "connect")

    assert "[8080]{.dv}" in qmd


def test_plain_style_keeps_a_same_named_parameter_distinct(highlight_style):
    """A parameter that shares the callable's own name is not swallowed by it"""
    highlight_style("plain")
    source = '''
    def host(host):
        """A parameter that shadows the function's own name."""
    '''

    qmd = _rendered(source, "host")

    assert "[host]{.sig-name}([host]{.doc-parameter-name})" in qmd


def test_plain_style_keeps_parameters_distinct_when_a_default_contains_another(
    highlight_style,
):
    """A string default that spells out another parameter is not confused with it"""
    highlight_style("plain")
    source = '''
    def f(x="a=1", a=1):
        """A string default that looks like the next parameter."""
    '''

    qmd = _rendered(source, "f")

    # `x`'s own default is highlighted once, not swallowed into `a`'s markup
    # and not doubly wrapped by re-matching the quotes it already carries.
    assert "[x]{.doc-parameter-name}=[&quot;a=1&quot;]{.st}" in qmd
    # `a`'s default is still marked up in its own right, not left plain
    # because an earlier default happened to contain its literal text.
    assert "[a]{.doc-parameter-name}=[1]{.dv}" in qmd


def test_plain_style_marks_a_typeddict_name(highlight_style):
    """A kind that is never called still names itself the way a callable does"""
    highlight_style("plain")
    source = '''
    from typing import TypedDict

    class Point(TypedDict):
        """A point."""

        x: int
    '''

    qmd = _rendered(source, "Point")

    assert "[Point]{.sig-name}" in qmd


def test_plain_style_marks_an_enum_name(highlight_style):
    """An enum's name is marked the same way a TypedDict's is"""
    highlight_style("plain")
    source = '''
    from enum import Enum

    class Colour(Enum):
        """A colour."""

        RED = 1
    '''

    qmd = _rendered(source, "Colour")

    assert "[Colour]{.sig-name}" in qmd


_OVERLOADED = '''
from typing import overload

@overload
def convert(value: int, base: int) -> str: ...
@overload
def convert(value: str, base: int) -> str: ...
def convert(value, base):
    """Convert a value."""
'''


def test_plain_style_writes_overloads_as_inline_markup(highlight_style):
    """An overloaded function follows the style the settings ask for"""
    highlight_style("plain")

    qmd = _rendered(_OVERLOADED, "convert")

    assert "sourceCode" not in qmd
    assert "```python" not in qmd
    assert qmd.count("[convert]{.sig-name}") == 2
    assert "[value]{.doc-parameter-name}" in qmd


def test_plain_style_keeps_the_overload_return_annotations(highlight_style):
    """Each variant keeps the return type that distinguishes it"""
    highlight_style("plain")

    qmd = _rendered(_OVERLOADED, "convert")

    assert qmd.count(") -&gt; str") == 2


def test_highlighted_style_writes_overloads_as_a_code_block(highlight_style):
    """The default style is unchanged: one code block, one line per variant"""
    highlight_style("highlighted")

    qmd = _rendered(_OVERLOADED, "convert")

    assert "```python" in qmd
    # One `convert(` opening a signature line per variant. The count is taken
    # over the line openings so the page title, which also spells `convert(`,
    # is not counted.
    assert qmd.count("\nconvert(") == 2


def test_plain_style_escapes_a_default_that_looks_like_html(highlight_style):
    """A string default cannot open an html tag"""
    highlight_style("plain")
    source = '''
    def h(a="<b>", c=1):
        """Take a default that looks like a tag."""
    '''

    qmd = _rendered(source, "h")

    assert "<b>" not in qmd
    assert "&lt;b&gt;" in qmd
    assert "[c]{.doc-parameter-name}=[1]{.dv}" in qmd


def test_plain_style_escapes_a_default_that_looks_like_a_span(highlight_style):
    """A string default cannot become a pandoc span"""
    highlight_style("plain")
    source = '''
    def h(a="[x]{.y}"):
        """Take a default that looks like a span."""
    '''

    qmd = _rendered(source, "h")

    assert "[x]{.y}" not in qmd
    assert r"\[x\]\{.y\}" in qmd


def test_plain_style_escapes_the_variadic_prefixes(highlight_style):
    """The asterisks of `*args` and `**kwargs` stay asterisks, not emphasis"""
    highlight_style("plain")
    source = '''
    def g(*args, **kwargs):
        """Take variadic arguments."""
    '''

    qmd = _rendered(source, "g")

    assert r"\*[args]{.doc-parameter-name}" in qmd
    assert r"\*\*[kwargs]{.doc-parameter-name}" in qmd
