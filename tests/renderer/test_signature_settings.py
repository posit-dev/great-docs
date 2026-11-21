import re
import textwrap
from pathlib import Path

import griffe as gf

from great_docs._apiref._rendering import APIPageRenderer
from great_docs._apiref._settings import CallableSignatures, Settings
from great_docs._apiref._signature import make_call_signature_text
from great_docs._apiref._tools import _render
from great_docs._apiref.api_reference import APIReference
from great_docs.extensions import Extension
from tests.support import reference_from_options, write_config


def test_settings_read_the_documentation_config(tmp_path: Path) -> None:
    config = write_config(tmp_path, {"callable_signatures": {"style": "plain", "wrap": "width"}})
    settings = Settings.make(config)

    assert settings.callable_signatures.style == "plain"
    assert settings.callable_signatures.wrap == "width"


def test_builder_follows_the_per_parameter_style():
    """Every parameter takes its own line, however short the signature"""
    result = make_call_signature_text("connect", ["host", "port=8080"], "per_parameter")

    assert result == "connect(\n    host,\n    port=8080,\n)"


def test_builder_follows_the_width_style():
    """A short signature stays on one line"""
    result = make_call_signature_text("connect", ["host", "port=8080"], "width")

    assert result == "connect(host, port=8080)"


def test_a_lone_parameter_does_not_wrap():
    """There is nothing to wrap a single parameter against"""
    assert make_call_signature_text("connect", ["host"], "per_parameter") == "connect(host)"


def test_overload_variants_follow_the_wrap_style():
    """Each @overload variant wraps like any other signature"""
    source = '''
    from typing import overload

    @overload
    def convert(value: int, base: int) -> str: ...
    @overload
    def convert(value: str, base: int) -> str: ...
    def convert(value, base):
        """Convert a value."""
    '''
    settings = Settings(callable_signatures=CallableSignatures(wrap="per_parameter"))
    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}
    ) as package:
        qmd = _render(package["convert"], settings)

    assert "convert(\n    value" in qmd


def _write_tiny_package(root: Path) -> None:
    """Write a package with one documented function under `root/src`"""
    package = root / "src" / "tinypkg"
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


def _reference(style: str) -> APIReference:
    """Create an API reference for `tinypkg` with the selected signature style"""
    return reference_from_options(
        {
            "package": "tinypkg",
            "source_dir": "../src",
            "callable_signatures": {"style": style, "wrap": "width"},
            "sections": [{"title": "All", "desc": "", "contents": ["add"]}],
        }
    )


def test_a_build_writes_its_pages_in_its_own_signature_style(tmp_path, monkeypatch):
    """The pages a build writes carry the signature style of its reference"""
    _write_tiny_package(tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    # `APIReference.build` resolves its paths from the working directory.
    monkeypatch.chdir(site)

    _reference("plain").build()

    page = (site / "reference" / "add.qmd").read_text()
    assert "<code>[add]{.sig-name}([a]{.doc-parameter-name}," in page


def test_references_render_with_their_own_settings_when_interleaved(tmp_path, monkeypatch):
    """Two references in one process each render with their own settings"""
    _write_tiny_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))

    def render(ref: APIReference) -> str:
        return str(APIPageRenderer(ref.manifest.pages[0], extension=Extension(ref.settings)))

    plain, highlighted = _reference("plain"), _reference("highlighted")

    before = render(plain)
    highlighted_page = render(highlighted)
    # Resolving another reference with default settings must preserve the
    # first reference's render settings.
    assert reference_from_options({"package": "tinypkg"}).documented_symbols == ["add"]
    after = render(plain)

    assert "[add]{.sig-name}" in before
    assert "```pythonsignature" not in before
    assert "```pythonsignature" in highlighted_page
    assert after == before


def _signature(source: str, name: str, renderer_type: type | None = None) -> str:
    """Return the rendered signature of the named callable in `source`"""
    from great_docs._apiref import content
    from great_docs._apiref._rendering import Renderers

    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}
    ) as package:
        obj = package[name]
    doc = content.Doc.from_griffe(obj.name, obj)
    qmd = str(Renderers(functions=renderer_type).make(doc))
    signature = qmd.split(".doc-signature", 1)[1]
    return re.search(r"```\w+\n(.*?)```", signature, re.S).group(1)


def test_an_annotation_shows_double_quoted_strings():
    """A `Literal` annotation quotes its strings the way defaults are quoted"""
    source = """
    from typing import Literal

    def pick(mode: Literal['fast', 'slow']): ...
    """

    from great_docs._apiref._format import repr_obj
    from great_docs.rendering import FunctionRenderer

    class AnnotatedFunction(FunctionRenderer):
        def render_signature_parameter(self, el: gf.Parameter) -> str:
            return f"{el.name}: {repr_obj(el.annotation)}"

    sig = _signature(source, "pick", AnnotatedFunction)

    assert 'Literal["fast", "slow"]' in sig


def test_an_overload_shows_double_quoted_strings():
    """An `@overload` variant's annotation, default and return type use double quotes"""
    source = """
    from typing import Literal, overload

    @overload
    def pick(mode: Literal['a'] = 'a') -> Literal['b']: ...
    @overload
    def pick(mode: int) -> int: ...
    def pick(mode='a'): ...
    """

    sig = _signature(source, "pick")

    assert 'pick(mode: Literal["a"] = "a") -> Literal["b"]' in sig


def test_a_prefixed_string_default_shows_double_quotes():
    """A bytes string default keeps its prefix and takes double quotes"""
    sig = _signature("def read(data=b'raw'): ...", "read")

    assert 'read(data=b"raw")' in sig


def test_a_string_holding_a_quote_or_backslash_keeps_its_quotes():
    """Rewriting the quotes would change or break such a string"""
    source = """
    def say(greeting='say "hi"', path='a\\\\b'): ...
    """

    sig = _signature(source, "say")

    assert """greeting='say "hi"'""" in sig
    assert "path='a\\\\b'" in sig
