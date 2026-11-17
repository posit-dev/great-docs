"""Verify shared semantics across acquisition order and member eligibility"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import permutations
from pathlib import Path
from textwrap import dedent

import pytest

from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref._tools import render_type_object
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.typing_information import TypeInformation
from tests.support import write_config


@contextmanager
def reference_from_source(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    extension: str,
    contents: list[str],
    *,
    dynamic: bool = False,
) -> Iterator[APIReference]:
    """Own a temporary package, configured extension and shared reference"""
    name = "preparation_order_example"
    package = root / name
    package.mkdir()
    for path, source in files.items():
        target = package / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dedent(source))
    (root / "extension.py").write_text(dedent(extension))
    config = write_config(root, {"api_reference_extension": "extension.py", "dynamic": dynamic})
    monkeypatch.syspath_prepend(str(root))
    before = {
        key: value
        for key, value in sys.modules.items()
        if key == name or key.startswith(name + ".")
    }
    for key in before:
        del sys.modules[key]
    ref = APIReference(
        {"package": name, "dynamic": dynamic, "sections": [{"title": "API", "contents": contents}]},
        extension_source=_ExtensionSource.make(config, root),
    )
    try:
        yield ref
    finally:
        ref.close()
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
        sys.modules.update(before)


@pytest.mark.parametrize("order", list(permutations(["helper", "page", "typing"])))
@pytest.mark.parametrize("dynamic", [False, True])
def test_consumers_share_preparation_regardless_of_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: tuple[str, ...], dynamic: bool
) -> None:
    files = {
        "__init__.py": "from .types import Document\nfrom .types import Document as Alias\n",
        "types.py": '''
            from typing import Protocol

            class Document(Protocol):
                """Original subject"""

                def render(self, text: str = "default") -> str:
                    """Render subject"""

            Document.__doc__ = "Runtime subject"
            Document.render.__doc__ = "Runtime render subject"
        ''',
    }
    extension = """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            calls: list[str] = []
            seen: dict[str, str | None] = {}
            extension.cache["calls"] = calls
            extension.cache["seen"] = seen

            @extension.on_object_resolved
            def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                calls.append(obj.path)
                seen[obj.path] = obj.docstring.value if obj.docstring is not None else None
                if obj.name == "Document":
                    obj.docstring = gf.Docstring("Prepared subject\\n\\nPREPARED_DOCUMENT_BODY", parent=obj)
                return obj
    """
    with reference_from_source(
        tmp_path, monkeypatch, files, extension, ["Document", "Alias"], dynamic=dynamic
    ) as ref:
        outputs: dict[str, str] = {}
        for consumer in order:
            if consumer == "helper":
                outputs[consumer] = render_type_object(f"{ref.package}:Alias", customisation=ref)
            elif consumer == "page":
                outputs[consumer] = str(
                    ref.renderers.make(ref.resolved[0].contents[0], settings=ref.settings)
                )
            else:
                outputs[consumer] = str(TypeInformation(f"{ref.package}.types", ref))
        assert all("PREPARED_DOCUMENT_BODY" in output for output in outputs.values())
        assert all("Original subject" not in output for output in outputs.values())
        calls = ref.extension.cache["calls"]
        assert isinstance(calls, list)
        assert calls.count(f"{ref.package}.types.Document") == 1
        assert calls.count(f"{ref.package}.types.Document.render") == 1
        seen = ref.extension.cache["seen"]
        assert isinstance(seen, dict)
        assert seen[f"{ref.package}.types.Document"] == (
            "Runtime subject" if dynamic else "Original subject"
        )
        assert seen[f"{ref.package}.types.Document.render"] == (
            "Runtime render subject" if dynamic else "Render subject"
        )
        assert {"Document", "Alias", "Document.render", "Alias.render"} <= set(
            ref.documented_symbols
        )


def test_object_hooks_run_before_documented_dunder_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {"__init__.py": "class Container:\n    def __iter__(self):\n        pass\n"}
    extension = """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            @extension.on_object_resolved
            def document(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                if obj.name == "__iter__":
                    obj.docstring = gf.Docstring("Iterate over the contents", parent=obj)
                return obj
    """
    with reference_from_source(tmp_path, monkeypatch, files, extension, ["Container"]) as ref:
        assert "Container.__iter__" in ref.documented_symbols


def test_hook_added_parameter_directive_affects_helpers_and_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {
        "__init__.py": '''
        def call(visible: int, hidden: str = "secret"):
            """Call subject

            Parameters
            ----------
            visible
                Visible parameter.
            hidden
                Hidden parameter.
            """
    '''
    }
    extension = """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            @extension.on_object_resolved(priority=-200)
            def exclude_parameter(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                if obj.name == "call" and obj.docstring is not None:
                    obj.docstring.value += "\\n\\n%nodoc_param hidden"
                return obj
    """
    with reference_from_source(tmp_path, monkeypatch, files, extension, ["call"]) as ref:
        helper = render_type_object(f"{ref.package}:call", customisation=ref)
        page = str(ref.renderers.make(ref.resolved[0].contents[0], settings=ref.settings))
        for output in (helper, page):
            assert "visible" in output
            assert "hidden" not in output
            assert "%nodoc_param" not in output


def test_unselected_imports_do_not_require_optional_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {
        "__init__.py": "",
        "module.py": '''
            from unavailable_optional_dependency import External

            def visible():
                """Visible function"""
        ''',
    }
    extension = "from great_docs.extensions import Extension\ndef setup(extension: Extension) -> None:\n    pass\n"
    with reference_from_source(tmp_path, monkeypatch, files, extension, ["module"]) as ref:
        assert "module.visible" in ref.documented_symbols
        assert "module.External" not in ref.documented_symbols
