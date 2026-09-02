import textwrap

import pytest

from great_docs._apiref._format import make_call_signature_text
from great_docs._apiref._globals import SIGNATURE_STYLE, SignatureStyle
from great_docs._apiref._tools import _render
from great_docs._apiref.api_reference import Settings, apply_signature_settings


def test_settings_default_to_todays_rendering():
    """The defaults reproduce what sites already publish"""
    settings = Settings()

    assert settings.call_signature_highlight_style == "pygments"
    assert settings.call_signature_wrap_style == "per_parameter"


def test_settings_read_the_api_reference_block():
    """Both keys come from the generated api-reference block"""
    settings = Settings.make(
        {
            "package": "pkg",
            "call_signature_highlight_style": "spans",
            "call_signature_wrap_style": "width",
        }
    )

    assert settings.call_signature_highlight_style == "spans"
    assert settings.call_signature_wrap_style == "width"


def test_applying_settings_reaches_the_render_side():
    """The renderer reads the style from module state, not from Settings"""
    original = SignatureStyle(SIGNATURE_STYLE.highlight, SIGNATURE_STYLE.wrap)
    try:
        apply_signature_settings(
            Settings(
                call_signature_highlight_style="spans",
                call_signature_wrap_style="width",
            )
        )
        assert SIGNATURE_STYLE.highlight == "spans"
        assert SIGNATURE_STYLE.wrap == "width"
    finally:
        SIGNATURE_STYLE.highlight = original.highlight
        SIGNATURE_STYLE.wrap = original.wrap


@pytest.fixture
def wrap_style():
    """Set the wrap style for one test and restore it afterwards"""
    original = SIGNATURE_STYLE.wrap

    def apply(style: str) -> None:
        SIGNATURE_STYLE.wrap = style

    yield apply
    SIGNATURE_STYLE.wrap = original


def test_builder_follows_the_per_parameter_style(wrap_style):
    """Every parameter takes its own line, however short the signature"""
    wrap_style("per_parameter")

    result = make_call_signature_text("connect", ["host", "port=8080"])

    assert result == "connect(\n    host,\n    port=8080,\n)"


def test_builder_follows_the_width_style(wrap_style):
    """A short signature stays on one line"""
    wrap_style("width")

    result = make_call_signature_text("connect", ["host", "port=8080"])

    assert result == "connect(host, port=8080)"


def test_overload_variants_follow_the_wrap_style(wrap_style):
    """Each @overload variant wraps like any other signature"""
    import griffe as gf

    wrap_style("per_parameter")
    source = '''
    from typing import overload

    @overload
    def convert(value: int, base: int) -> str: ...
    @overload
    def convert(value: str, base: int) -> str: ...
    def convert(value, base):
        """Convert a value."""
    '''
    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}
    ) as package:
        qmd = _render(package["convert"])

    assert "convert(\n    value" in qmd
