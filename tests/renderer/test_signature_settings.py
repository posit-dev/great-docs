import textwrap

import pytest

from great_docs._apiref._signature import make_call_signature_text
from great_docs._apiref import _globals
from great_docs._apiref._tools import _render
from great_docs._apiref._settings import CallableSignatures, Settings, active_settings


def test_the_renderer_reads_the_name_the_user_typed():
    """The settings keep the shape the configuration has"""
    from great_docs._apiref import _globals
    from great_docs._apiref._settings import CallableSignatures, active_settings

    before = (
        _globals.SETTINGS.callable_signatures.style,
        _globals.SETTINGS.callable_signatures.wrap,
    )
    settings = Settings(callable_signatures=CallableSignatures(style="plain", wrap="width"))

    with active_settings(settings):
        assert _globals.SETTINGS.callable_signatures.style == "plain"
        assert _globals.SETTINGS.callable_signatures.wrap == "width"

    assert (
        _globals.SETTINGS.callable_signatures.style,
        _globals.SETTINGS.callable_signatures.wrap,
    ) == before


def test_settings_read_the_api_reference_block():
    """Both keys come from the generated api-reference block"""
    settings = Settings.make(
        {
            "package": "pkg",
            "callable_signatures": {"style": "plain", "wrap": "width"},
        }
    )

    assert settings.callable_signatures.style == "plain"
    assert settings.callable_signatures.wrap == "width"


def test_applying_settings_reaches_the_render_side():
    """The renderer reads the style from module state, not from Settings"""
    settings = Settings(callable_signatures=CallableSignatures(style="plain", wrap="width"))

    with active_settings(settings):
        assert _globals.SETTINGS.callable_signatures.style == "plain"
        assert _globals.SETTINGS.callable_signatures.wrap == "width"


def test_settings_are_put_back_afterwards():
    """One reference's settings do not govern whatever is rendered next"""
    original = _globals.SETTINGS.callable_signatures
    settings = Settings(callable_signatures=CallableSignatures(style="plain", wrap="width"))

    with active_settings(settings):
        pass

    assert _globals.SETTINGS.callable_signatures.style == original.style
    assert _globals.SETTINGS.callable_signatures.wrap == original.wrap


def test_settings_are_put_back_after_a_failure():
    """A build that raises still leaves the state as it found it"""
    original = _globals.SETTINGS.callable_signatures
    settings = Settings(callable_signatures=CallableSignatures(style="plain"))

    with pytest.raises(RuntimeError), active_settings(settings):
        raise RuntimeError("the build failed")

    assert _globals.SETTINGS.callable_signatures.style == original.style
    assert _globals.SETTINGS.callable_signatures.wrap == original.wrap


@pytest.fixture
def wrap_style():
    """Set the wrap style for one test and restore it afterwards"""
    original = _globals.SETTINGS.callable_signatures.wrap

    def apply(style: str) -> None:
        _globals.SETTINGS.callable_signatures.wrap = style

    yield apply
    _globals.SETTINGS.callable_signatures.wrap = original


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


def test_a_lone_parameter_does_not_wrap(wrap_style):
    """There is nothing to wrap a single parameter against"""
    wrap_style("per_parameter")

    assert make_call_signature_text("connect", ["host"]) == "connect(host)"


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

    original = _globals.SETTINGS.callable_signatures
    APIReference(
        {
            "api-reference": {
                "package": "tinypkg",
                "source_dir": "../src",
                "callable_signatures": {"style": "plain", "wrap": "width"},
                "sections": [{"title": "All", "desc": "", "contents": ["add"]}],
            }
        }
    ).build()

    # The settings were live for the build itself: the page carries the
    # inline markup of the `plain` style on one line, as `width` asks.
    page = (site / "reference" / "add.qmd").read_text()
    assert "<code>[add]{.sig-name}([a]{.doc-parameter-name}," in page
    assert _globals.SETTINGS.callable_signatures.style == original.style
    assert _globals.SETTINGS.callable_signatures.wrap == original.wrap
