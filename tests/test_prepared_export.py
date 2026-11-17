"""Verify prepared callable facts and standalone semantic-export ownership"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import griffe as gf
import pytest

from great_docs._apiref._customisation import Extension, ExtensionError
from great_docs._apiref._export import object_text, signature_text
from great_docs._apiref._settings import Settings
from great_docs._apiref.content import Doc
from great_docs._project.layout import Layout
from great_docs._website.ai_agents import llms_txt
from great_docs.rendering import FunctionRenderer, Renderers
from tests.support import write_config, write_pyproject


def test_signature_retains_parameter_kinds_without_synthetic_variadic_defaults() -> None:
    source = (
        "def example(a: int = 1, /, *args: str, b: bool = True, **kwargs: float) -> str:\n"
        "    pass\n"
    )
    with gf.temporary_visited_package("example", {"__init__.py": source}) as module:
        text = signature_text(module["example"])
    assert text == "example(a: int = 1, /, *args: str, b: bool = True, **kwargs: float) -> str"
    compile(f"def {text}:\n    pass\n", "<exported-signature>", "exec")


def test_signature_accepts_replacement_parameters_without_explicit_kinds() -> None:
    obj = gf.Function("run", parameters=gf.Parameters(gf.Parameter("value", annotation="int")))
    assert signature_text(obj) == "run(value: int)"


@pytest.mark.skipif(sys.version_info < (3, 13), reason="PEP 696 defaults require Python 3.13")
def test_signature_retains_type_parameter_bounds_constraints_and_defaults() -> None:
    source = (
        "type Alias[T: int = int, S: (str, bytes) = str] = tuple[T, S]\n"
        "def make[T: int](value: T) -> list[T]:\n    pass\n"
    )
    with gf.temporary_visited_package("example", {"__init__.py": source}) as module:
        assert signature_text(module["Alias"]) == (
            "type Alias[T: int = int, S: (str, bytes) = str] = tuple[T, S]"
        )
        assert signature_text(module["make"]) == "make[T: int](value: T) -> list[T]"


def test_signatures_retain_overloads_and_constructor_exclusions() -> None:
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


def test_export_uses_prepared_sections_without_presentation_or_repeated_hooks() -> None:
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


@pytest.fixture
def standalone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Layout]:
    """Own an importable package and explicit standalone-export configuration"""
    name = "standalone_export_example"
    write_pyproject(tmp_path, name)
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text('def public():\n    """Original subject"""\n')
    write_config(tmp_path, {"api_reference_extension": "extension.py"})
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir()
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, name, raising=False)
    try:
        yield layout
    finally:
        for module in list(sys.modules):
            if module == name or module.startswith(name + "."):
                del sys.modules[module]


def test_standalone_export_loads_selected_setup_and_releases_owned_imports(
    standalone: Layout,
) -> None:
    root = standalone.source_dir
    (root / "helper.py").write_text("TOKEN = 'Prepared standalone subject'\n")
    (root / "extension.py").write_text(
        "from pathlib import Path\n"
        "from .helper import TOKEN\n"
        "def setup(extension):\n"
        "    with Path(__file__).with_name('setups.txt').open('a') as stream:\n"
        "        stream.write('setup\\n')\n"
        "    @extension.on_object_resolved\n"
        "    def transform(obj):\n"
        "        if obj.docstring is not None:\n"
        "            obj.docstring.value = TOKEN\n"
        "        return obj\n"
    )
    before = {name for name in sys.modules if name.startswith("_great_docs_extension_")}
    path = llms_txt.write_full(
        standalone,
        {"package": "standalone_export_example", "sections": [{"contents": ["missing", "public"]}]},
        cli=None,
        user_guide=None,
        report=lambda _: None,
    )
    assert path is not None
    assert "Prepared standalone subject" in path.read_text()
    assert "missing" not in path.read_text()
    assert (root / "setups.txt").read_text() == "setup\n"
    assert {name for name in sys.modules if name.startswith("_great_docs_extension_")} == before


def test_standalone_export_propagates_configured_hook_failure_and_closes(
    standalone: Layout,
) -> None:
    (standalone.source_dir / "extension.py").write_text(
        "def setup(extension):\n"
        "    @extension.on_object_resolved\n"
        "    def transform(obj):\n"
        "        raise ImportError('configured semantic failure')\n"
    )
    before = {name for name in sys.modules if name.startswith("_great_docs_extension_")}
    with pytest.raises(ExtensionError, match="object_resolved") as failure:
        llms_txt.write_full(
            standalone,
            {"package": "standalone_export_example", "sections": [{"contents": ["public"]}]},
            cli=None,
            user_guide=None,
            report=lambda _: None,
        )
    assert isinstance(failure.value.__cause__, ImportError)
    assert {name for name in sys.modules if name.startswith("_great_docs_extension_")} == before


def test_undocumented_class_retains_signature_without_unselected_constructor_body(
    standalone: Layout,
) -> None:
    (standalone.source_dir / "standalone_export_example/__init__.py").write_text(
        "class Example:\n"
        "    def __init__(self, value: int = 7):\n"
        '        """An unselected constructor description"""\n'
    )
    (standalone.source_dir / "extension.py").write_text("def setup(extension):\n    pass\n")
    path = llms_txt.write_full(
        standalone,
        {
            "package": "standalone_export_example",
            "sections": [{"contents": [{"name": "Example", "members": []}]}],
        },
        cli=None,
        user_guide=None,
        report=lambda _: None,
    )
    assert path is not None
    text = path.read_text()
    assert "Example(value: int = 7)" in text
    assert "An unselected constructor description" not in text


@pytest.mark.parametrize("explicit", [False, True])
def test_standalone_setup_observes_selected_settings_and_explicit_precedence(
    standalone: Layout, explicit: bool
) -> None:
    write_config(
        standalone.source_dir,
        {"api_reference_extension": "extension.py", "parser": "google", "dynamic": False},
    )
    (standalone.source_dir / "extension.py").write_text(
        "from pathlib import Path\n"
        "def setup(extension):\n"
        "    Path(__file__).with_name('settings.txt').write_text(\n"
        "        f'{extension.settings.parser} {extension.settings.dynamic}'\n"
        "    )\n"
    )
    block = {"package": "standalone_export_example", "sections": [{"contents": ["public"]}]}
    if explicit:
        block.update({"parser": "numpy", "dynamic": True})
    path = llms_txt.write_full(standalone, block, cli=None, user_guide=None, report=lambda _: None)
    assert path is not None
    assert (standalone.source_dir / "settings.txt").read_text() == (
        "numpy True" if explicit else "google False"
    )
