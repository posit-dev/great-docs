"""
Verify the text export of prepared objects and of a build's prepared reference

The text export uses prepared signatures and docstrings with the built-in
renderers. A build reuses its prepared reference and stops if the export fails.
"""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import griffe as gf
import pytest

from great_docs import GreatDocs
from great_docs._apiref._export import object_text, signature_text
from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.content import Doc
from great_docs._build import generated, reference
from great_docs._build.pipeline import Run
from great_docs._build.steps import BuildError, Outcome
from great_docs._project.layout import Layout
from great_docs._website import quarto_yml
from great_docs._website.ai_agents import llms_txt
from great_docs.extensions import Extension, ExtensionError
from great_docs.rendering import FunctionRenderer, Renderers
from tests.support import (
    MakeReference,
    StubRemote,
    WriteExtension,
    stubbed_build,
    write_config,
    write_pyproject,
)

PACKAGE = "prepared_export_example"


def test_signature_retains_parameter_kinds_without_synthetic_variadic_defaults():
    source = (
        "def example(a: int = 1, /, *args: str, b: bool = True, **kwargs: float) -> str:\n"
        "    pass\n"
    )
    with gf.temporary_visited_package("example", {"__init__.py": source}) as module:
        text = signature_text(module["example"])
    assert text == "example(a: int = 1, /, *args: str, b: bool = True, **kwargs: float) -> str"
    compile(f"def {text}:\n    pass\n", "<exported-signature>", "exec")


def test_signature_accepts_replacement_parameters_without_explicit_kinds():
    obj = gf.Function("run", parameters=gf.Parameters(gf.Parameter("value", annotation="int")))
    assert signature_text(obj) == "run(value: int)"


@pytest.mark.skipif(sys.version_info < (3, 13), reason="PEP 696 defaults require Python 3.13")
def test_signature_retains_type_parameter_bounds_constraints_and_defaults():
    source = (
        "type Alias[T: int = int, S: (str, bytes) = str] = tuple[T, S]\n"
        "def make[T: int](value: T) -> list[T]:\n    pass\n"
    )
    with gf.temporary_visited_package("example", {"__init__.py": source}) as module:
        assert signature_text(module["Alias"]) == (
            "type Alias[T: int = int, S: (str, bytes) = str] = tuple[T, S]"
        )
        assert signature_text(module["make"]) == "make[T: int](value: T) -> list[T]"


def test_signatures_retain_overloads_and_constructor_exclusions():
    source = '''
from typing import overload

@overload
def choose(value: int, *, strict: bool = True) -> int: ...
@overload
def choose(value: str, *, strict: bool = True) -> str: ...
def choose(value, *, strict=True):
    """Choose a value"""

class Example:
    """Create an example

    %nodoc_param hidden

    Parameters
    ----------
    value : int
        The retained input.
    hidden
        The excluded input.
    """

    def __new__(cls, value: int = 7, hidden=None):
        return super().__new__(cls)

    def __init__(self):
        pass
'''
    extension = Extension(Settings())
    try:
        with gf.temporary_visited_package(
            "example", {"__init__.py": source}, docstring_parser=gf.Parser.numpy
        ) as module:
            choose = extension.prepare(module["choose"])
            example = extension.prepare(module["Example"])
        assert choose is not None and example is not None
        assert signature_text(choose).splitlines() == [
            "choose(value: int, *, strict: bool = True) -> int",
            "choose(value: str, *, strict: bool = True) -> str",
        ]
        assert signature_text(example) == "Example(value: int = 7)"
        text = object_text(Doc.from_griffe("Example", example), extension.settings)
        assert "The retained input." in text
        assert "hidden" not in text
        assert "The excluded input." not in text
    finally:
        extension.close()


def test_export_uses_prepared_sections_without_presentation_or_repeated_hooks():
    extension = Extension(Settings())
    calls: list[str] = []

    class BrokenPresentation(FunctionRenderer):
        def render_docstring_body(self) -> None:
            raise AssertionError("Selected presentation must not affect the text export")

    extension.set_renderers(Renderers(functions=BrokenPresentation))

    @extension.on_object_resolved
    def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        calls.append(obj.path)
        return obj

    @extension.on_docstring_parsed
    def sections(
        obj: gf.Object | gf.Alias, parsed: list[gf.DocstringSection]
    ) -> list[gf.DocstringSection]:
        return [gf.DocstringSectionText("Prepared summary\n\nPrepared section markup")]

    try:
        obj = gf.Function("run", docstring=gf.Docstring("Raw summary"))
        prepared = extension.prepare(obj)
        assert prepared is not None
        node = Doc.from_griffe("run", prepared)
        first = object_text(node, extension.settings)
        second = object_text(node, extension.settings)
        assert first == second
        assert "Prepared summary" in first
        assert "Prepared section markup" in first
        assert "Raw summary" not in first
        assert calls == ["run"]
    finally:
        extension.close()


def test_undocumented_class_retains_signature_without_unselected_constructor_body(
    tmp_path: Path, make_reference: MakeReference
):
    ref = make_reference(
        {"package": PACKAGE, "sections": [{"contents": [{"name": "Example", "members": []}]}]},
        package_files={
            "__init__.py": '''
                class Example:
                    def __init__(self, value: int = 7):
                        """An unselected constructor description"""
            '''
        },
    )
    write_pyproject(tmp_path, PACKAGE)
    write_config(tmp_path)
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir()
    path = llms_txt.write_full(layout, ref, cli=None, user_guide=None, report=lambda _: None)
    text = path.read_text()
    assert "Example(value: int = 7)" in text
    assert "An unselected constructor description" not in text


def test_build_exports_prepared_documentation_without_repeating_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_extension: WriteExtension
):
    write_pyproject(tmp_path, PACKAGE)
    package = tmp_path / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text(
        dedent('''
            def document(visible: int, hidden: str = "private-default") -> str:
                """Original runtime subject

                Parameters
                ----------
                visible
                    Visible description.
                hidden
                    Hidden description.
                """

            def excluded():
                """Excluded object description"""
        ''')
    )
    write_extension(
        """
        from pathlib import Path
        import griffe as gf
        from great_docs.extensions import Extension
        from great_docs.pandoc.blocks import BlockContent, Blocks, Para
        from great_docs.rendering import FunctionRenderer, Renderers

        def record(name: str) -> None:
            with Path(__file__).with_name('events.txt').open('a') as stream:
                stream.write(name + '\\n')

        class Presentation(FunctionRenderer):
            def render_signature(self) -> BlockContent:
                return None

            @property
            def summary_name(self) -> str:
                return 'PRESENTATION_LABEL'

            def render_docstring_body(self) -> BlockContent:
                record('body:' + self.context.authored_name)
                return Blocks([super().render_docstring_body(), Para('PRESENTATION_ONLY_NOTE')])

        def setup(extension: Extension) -> None:
            record('setup')
            extension.set_renderers(Renderers(functions=Presentation))

            @extension.on_object_resolved(priority=-200)
            def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
                record('prepare:' + obj.name)
                if obj.name == 'excluded':
                    return None
                if obj.name == 'document' and obj.docstring is not None:
                    obj.docstring.value = obj.docstring.value.replace('Original runtime subject', 'Prepared subject')
                    obj.docstring.value += '\\n\\nPREPARED_NOTE\\n\\n%nodoc_param hidden'
                return obj
        """
    )
    write_config(tmp_path, {"api_reference_extension": "extension.py", "dynamic": False})
    docs = GreatDocs(str(tmp_path))
    docs._remote = StubRemote()
    docs.layout.build_dir.mkdir()
    quarto_yml.write(
        docs.layout.build_dir,
        {
            "api-reference": {
                "package": PACKAGE,
                "dynamic": False,
                "sections": [{"title": "API", "contents": ["document", "excluded"]}],
            }
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    with stubbed_build(api_reference=True):
        docs.build(refresh=False)

    page = (docs.layout.build_dir / "reference" / "document.qmd").read_text()
    full = (docs.layout.build_dir / "llms-full.txt").read_text()
    index = (docs.layout.build_dir / "llms.txt").read_text()
    assert "PRESENTATION_ONLY_NOTE" in page
    assert "doc-signature" not in page
    for text in (full, index):
        assert "Prepared subject" in text
        assert "PRESENTATION_ONLY_NOTE" not in text
        assert "PRESENTATION_LABEL" not in text
        assert "Original runtime subject" not in text
        assert "excluded" not in text
    assert "PREPARED_NOTE" in full
    assert "document(" in full
    assert "visible" in full
    assert "hidden" not in full
    assert "private-default" not in full
    events = (tmp_path / "events.txt").read_text().splitlines()
    assert events.count("setup") == 1
    assert events.count("prepare:document") == 1
    assert events.count("prepare:excluded") == 1
    assert events.count("body:document") == 1


def test_configured_export_failure_stops_the_build_and_releases_its_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    write_config(tmp_path)
    docs = GreatDocs(str(tmp_path))
    docs.layout.build_dir.mkdir()
    quarto_yml.write_initial(docs.layout.build_dir)
    active = MagicMock(spec=APIReference)

    def install(run: Run, *args: object, **kwargs: object) -> tuple[Outcome, APIReference]:
        run.api_reference = active
        return "API reference generated", active

    with (
        stubbed_build(),
        patch.object(reference, "api", autospec=True, side_effect=install),
        patch.object(
            generated, "llms_txt", autospec=True, side_effect=ExtensionError("export failed")
        ),
        pytest.raises(BuildError) as failure,
    ):
        docs.build(refresh=False)
    assert isinstance(failure.value.__cause__, ExtensionError)
    active.close.assert_called_once_with()
    assert "llms.txt generation had issues" not in capsys.readouterr().out
