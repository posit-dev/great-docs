import textwrap

import pytest

from great_docs._apiref._format import make_call_signature_text
from great_docs._apiref._globals import SIGNATURE_STYLE, SignatureStyle
from great_docs._apiref._tools import _render
from great_docs._apiref.api_reference import Settings, signature_settings


def test_settings_default_to_todays_rendering():
    """The defaults reproduce what sites already publish"""
    settings = Settings()

    assert settings.callable_signatures_style == "highlighted"
    assert settings.callable_signatures_wrap == "per_parameter"


def test_settings_read_the_api_reference_block():
    """Both keys come from the generated api-reference block"""
    settings = Settings.make(
        {
            "package": "pkg",
            "callable_signatures_style": "plain",
            "callable_signatures_wrap": "width",
        }
    )

    assert settings.callable_signatures_style == "plain"
    assert settings.callable_signatures_wrap == "width"


def test_applying_settings_reaches_the_render_side():
    """The renderer reads the style from module state, not from Settings"""
    settings = Settings(
        callable_signatures_style="plain",
        callable_signatures_wrap="width",
    )

    with signature_settings(settings):
        assert SIGNATURE_STYLE.highlight == "plain"
        assert SIGNATURE_STYLE.wrap == "width"


def test_settings_are_put_back_afterwards():
    """One reference's settings do not govern whatever is rendered next"""
    original = SignatureStyle(SIGNATURE_STYLE.highlight, SIGNATURE_STYLE.wrap)
    settings = Settings(
        callable_signatures_style="plain",
        callable_signatures_wrap="width",
    )

    with signature_settings(settings):
        pass

    assert SIGNATURE_STYLE.highlight == original.highlight
    assert SIGNATURE_STYLE.wrap == original.wrap


def test_settings_are_put_back_after_a_failure():
    """A build that raises still leaves the state as it found it"""
    original = SignatureStyle(SIGNATURE_STYLE.highlight, SIGNATURE_STYLE.wrap)
    settings = Settings(callable_signatures_style="plain")

    with pytest.raises(RuntimeError), signature_settings(settings):
        raise RuntimeError("the build failed")

    assert SIGNATURE_STYLE.highlight == original.highlight
    assert SIGNATURE_STYLE.wrap == original.wrap


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


def test_a_build_leaves_the_module_state_as_it_found_it(tmp_path, monkeypatch):
    """A build with non-default settings does not govern whatever is built next"""
    from great_docs._apiref.api_reference import APIReference

    package = tmp_path / "src" / "tinypkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        textwrap.dedent(
            '''
            """A tiny package."""


            def add(a, b):
                """Add two numbers."""
                return a + b
            '''
        )
    )
    site = tmp_path / "site"
    site.mkdir()
    # `APIReference.build` resolves its paths from the working directory.
    monkeypatch.chdir(site)

    original = SignatureStyle(SIGNATURE_STYLE.highlight, SIGNATURE_STYLE.wrap)
    APIReference(
        {
            "api-reference": {
                "package": "tinypkg",
                "source_dir": "../src",
                "callable_signatures_style": "plain",
                "callable_signatures_wrap": "width",
                "sections": [{"title": "All", "desc": "", "contents": ["add"]}],
            }
        }
    ).build()

    # The settings were live for the build itself: the page carries the
    # inline markup of the `plain` style on one line, as `width` asks.
    page = (site / "reference" / "add.qmd").read_text()
    assert "<code>[add]{.sig-name}([a]{.doc-parameter-name}," in page
    assert SIGNATURE_STYLE.highlight == original.highlight
    assert SIGNATURE_STYLE.wrap == original.wrap
