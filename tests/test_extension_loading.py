"""
Verify that each reference loads its extension lazily from current source

Closing the reference releases the project modules the extension imported.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from great_docs import Config
from great_docs._apiref._customisation import Extension, ExtensionError
from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference
from great_docs.config import ConfigError
from great_docs.hooks._docstring_parsed import REGISTRY as PARSED_HOOKS
from great_docs.hooks._object_resolved import REGISTRY as OBJECT_HOOKS
from great_docs.hooks._registry import HookRegistry
from great_docs.rendering import ClassRenderer, Renderers


def make_source(tmp_path: Path, code: str) -> _ExtensionSource:
    """Write a configured entry with explicit original documentation roots"""
    entry = tmp_path / "extension.py"
    entry.write_text(code, encoding="utf-8")
    return _ExtensionSource(entry, tmp_path, tmp_path / "docs")


def owned_modules() -> set[str]:
    """List operation-owned module names for cleanup assertions"""
    return {name for name in sys.modules if name.startswith("_great_docs_extension_")}


@pytest.mark.parametrize("value", [0, False, [], {}, "", " ", "extension.txt"])
def test_invalid_extension_path_is_rejected_without_import(tmp_path: Path, value: object) -> None:
    config_path = tmp_path / "great-docs.yml"
    config_path.write_text(f"api_reference_extension: {json.dumps(value)}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="api_reference_extension"):
        Config(tmp_path)


@pytest.mark.parametrize("absolute", [False, True])
def test_entry_path_uses_selected_configuration_root(tmp_path: Path, absolute: bool) -> None:
    config_dir = tmp_path / "configuration"
    config_dir.mkdir()
    entry = config_dir / "extension.py"
    entry.write_text("raise AssertionError('must stay lazy')\n", encoding="utf-8")
    configured = str(entry) if absolute else "extension.py"
    config_path = config_dir / "site.yml"
    config_path.write_text(f"api_reference_extension: {json.dumps(configured)}\n", encoding="utf-8")
    config = Config(tmp_path, config_path=config_path)
    assert config.api_reference_extension == entry
    source = _ExtensionSource.make(config, tmp_path / "docs")
    assert source == _ExtensionSource(entry, config_dir, tmp_path / "docs")


def test_null_extension_source_is_absent(tmp_path: Path) -> None:
    config = Config(tmp_path)
    assert config.api_reference_extension is None
    assert _ExtensionSource.make(config, tmp_path / "docs") is None


def test_sections_and_unused_close_do_not_load_configured_python(tmp_path: Path) -> None:
    marker = tmp_path / "loaded"
    source = make_source(tmp_path, f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
    before = owned_modules()
    reference = APIReference(
        {"package": "example", "sections": [{"contents": ["Example"]}]},
        extension_source=source,
    )
    assert reference.sections[0].contents[0].name == "Example"
    reference.close()
    reference.close()
    assert not marker.exists()
    assert owned_modules() == before


def test_setup_runs_once_and_selects_renderers(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        "from great_docs.rendering import ClassRenderer, Renderers\n"
        "class CustomClass(ClassRenderer):\n    pass\n"
        "def setup(extension):\n"
        "    extension.cache['calls'] = extension.cache.get('calls', 0) + 1\n"
        "    extension.set_renderers(Renderers(classes=CustomClass))\n",
    )
    reference = APIReference({"package": "example", "sections": []}, extension_source=source)
    before = owned_modules()
    extension = reference.extension
    renderers = reference.renderers
    assert reference.renderers is renderers is extension.renderers
    assert extension.cache["calls"] == 1
    assert issubclass(renderers.classes, ClassRenderer)
    assert renderers.classes is not ClassRenderer
    assert extension.settings is reference.settings
    assert extension.config_root == tmp_path
    assert extension.source_root == tmp_path / "docs"
    assert owned_modules() > before
    reference.close()
    assert owned_modules() == before


def test_relative_helpers_refresh_same_size_edits(tmp_path: Path) -> None:
    helper = tmp_path / "helper.py"
    helper.write_text("VALUE = 'first'\n", encoding="utf-8")
    timestamp = helper.stat().st_mtime_ns
    source = make_source(
        tmp_path,
        "from .helper import VALUE\ndef setup(extension):\n    extension.cache['value'] = VALUE\n",
    )
    first = APIReference({"package": "example"}, extension_source=source)
    first_extension = first.extension
    first_extension.load()
    assert first_extension.cache["value"] == "first"
    first.close()
    helper.write_text("VALUE = 'other'\n", encoding="utf-8")
    os.utime(helper, ns=(timestamp, timestamp))
    second = APIReference({"package": "example"}, extension_source=source)
    second.extension.load()
    assert second.extension.cache["value"] == "other"
    assert second.extension.cache is not first_extension.cache
    second.close()


def test_late_relative_imports_and_dataclass_inspection_work_until_close(tmp_path: Path) -> None:
    helper = tmp_path / "helper.py"
    helper.write_text(
        "from dataclasses import dataclass\n@dataclass\nclass Value:\n    text: str = 'current'\n",
        encoding="utf-8",
    )
    source = make_source(
        tmp_path,
        "def read():\n    from .helper import Value\n    return Value()\n"
        "def setup(extension):\n    extension.cache['read'] = read\n",
    )
    before = owned_modules()
    reference = APIReference({"package": "example"}, extension_source=source)
    extension = reference.extension
    extension.load()
    callback = extension.cache["read"]
    assert callable(callback)
    value = callback()
    assert value.text == "current"
    assert type(value).__module__ in sys.modules
    assert extension.imported_paths == frozenset([source.entry_path, helper])
    reference.close()
    assert owned_modules() == before
    assert extension.imported_paths == frozenset([source.entry_path, helper])


def test_closing_extension_preserves_installed_package_cache(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        "import json\ndef setup(extension):\n    extension.cache['json'] = json\n",
    )
    reference = APIReference({"package": "example"}, extension_source=source)
    reference.extension.load()
    assert reference.extension.cache["json"] is json
    reference.close()
    assert sys.modules["json"] is json


@pytest.mark.parametrize(
    "code, cause, phase",
    [
        ("def invalid(\n", SyntaxError, "load"),
        ("value = 1\n", TypeError, "setup"),
        ("setup = 2\n", TypeError, "setup"),
        ("def setup(extension):\n    raise ValueError('broken setup')\n", ValueError, "setup"),
        ("from .missing import value\n", ModuleNotFoundError, "load"),
    ],
)
def test_failed_extension_releases_imports_with_actual_phase(
    tmp_path: Path, code: str, cause: type[Exception], phase: str
) -> None:
    source = make_source(tmp_path, code)
    before = owned_modules()
    finders = list(sys.meta_path)
    reference = APIReference({"package": "example"}, extension_source=source)
    with pytest.raises(ExtensionError, match=rf"extension.py: {phase}:") as error:
        reference.extension.load()
    assert isinstance(error.value.__cause__, cause)
    assert str(error.value).count(f": {phase}:") == 1
    assert owned_modules() == before
    assert sys.meta_path == finders
    with pytest.raises(RuntimeError, match="extension is closed"):
        reference.extension.load()
    reference.close()


def test_partial_helper_failure_cleans_modules_and_finder(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text("raise ValueError('broken helper')\n", encoding="utf-8")
    source = make_source(tmp_path, "from .helper import VALUE\n")
    before = owned_modules()
    finders = list(sys.meta_path)
    extension = Extension(Settings(), source)
    with pytest.raises(ExtensionError, match="extension.py: load:") as error:
        extension.load()
    assert isinstance(error.value.__cause__, ValueError)
    assert extension.imported_paths == frozenset([source.entry_path, tmp_path / "helper.py"])
    assert owned_modules() == before
    assert sys.meta_path == finders
    extension.close()


def test_missing_entry_is_a_lazy_load_error(tmp_path: Path) -> None:
    source = _ExtensionSource(tmp_path / "missing.py", tmp_path, tmp_path)
    reference = APIReference({"package": "example"}, extension_source=source)
    assert reference.sections == []
    with pytest.raises(ExtensionError, match="missing.py: load:") as error:
        _ = reference.resolved
    assert isinstance(error.value.__cause__, FileNotFoundError)
    reference.close()


@pytest.mark.parametrize("during_import", [False, True])
def test_global_template_mutation_is_rejected_and_restored(
    tmp_path: Path, during_import: bool
) -> None:
    register = "on_object_resolved(lambda obj: obj)"
    code = "from great_docs.hooks import on_object_resolved\n"
    code += (
        register + "\ndef setup(extension):\n    pass\n"
        if during_import
        else ("def setup(extension):\n    " + register + "\n")
    )
    source = make_source(tmp_path, code)
    object_snapshot = OBJECT_HOOKS.snapshot()
    parsed_snapshot = PARSED_HOOKS.snapshot()
    reference = APIReference({"package": "example"}, extension_source=source)
    with pytest.raises(ExtensionError, match="supplied extension"):
        reference.extension.load()
    assert OBJECT_HOOKS.snapshot() == object_snapshot
    assert PARSED_HOOKS.snapshot() == parsed_snapshot
    reference.close()


def test_setup_failure_restores_global_templates(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        "from great_docs.hooks import on_object_resolved\n"
        "def setup(extension):\n"
        "    on_object_resolved(lambda obj: obj)\n"
        "    raise ValueError('original cause')\n",
    )
    before = OBJECT_HOOKS.snapshot()
    reference = APIReference({"package": "example"}, extension_source=source)
    with pytest.raises(ExtensionError) as error:
        reference.extension.load()
    assert isinstance(error.value.__cause__, ValueError)
    assert OBJECT_HOOKS.snapshot() == before
    reference.close()


def test_registration_freezes_after_setup(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        "def setup(extension):\n"
        "    extension.on_object_resolved(lambda obj: obj)\n"
        "    @extension.on_docstring_parsed(priority=2)\n"
        "    def parsed(obj, sections):\n        return sections\n"
        "    extension.cache['decorator'] = extension.on_object_resolved(priority=2)\n",
    )
    reference = APIReference({"package": "example"}, extension_source=source)
    extension = reference.extension
    extension.load()
    for operation in [
        lambda: extension.on_object_resolved(lambda obj: obj),
        lambda: extension.on_docstring_parsed(lambda obj, sections: sections),
        lambda: extension.set_renderers(Renderers()),
        lambda: extension.watch("input.txt"),
    ]:
        with pytest.raises(RuntimeError, match="registration is closed"):
            operation()
    decorator = extension.cache["decorator"]
    assert callable(decorator)
    with pytest.raises(RuntimeError, match="registration is closed"):
        decorator(lambda obj: obj)
    reference.close()


def test_watch_declarations_keep_entry_relative_missing_paths(tmp_path: Path) -> None:
    source = make_source(
        tmp_path,
        "def setup(extension):\n"
        "    extension.watch('missing.txt')\n"
        "    extension.watch('data/*.txt')\n",
    )
    reference = APIReference({"package": "example"}, extension_source=source)
    reference.extension.load()
    assert reference.extension.declared_inputs == (
        tmp_path / "missing.txt",
        tmp_path / "data/*.txt",
    )
    reference.close()


def test_error_context_names_callback_phase_and_owner_releases_imports(tmp_path: Path) -> None:
    source = make_source(tmp_path, "def setup(extension):\n    pass\n")
    before = owned_modules()
    reference = APIReference({"package": "example"}, extension_source=source)
    extension = reference.extension
    extension.load()
    with pytest.raises(ExtensionError, match="body for example.run: original") as error:
        with extension.error_context("body", "example.run"):
            raise ValueError("original")
    assert isinstance(error.value.__cause__, ValueError)
    assert ": setup" not in str(error.value)
    assert owned_modules() > before
    reference.close()
    assert owned_modules() == before


def test_hook_snapshots_share_callback_state_and_keep_priority_order() -> None:
    calls: list[str] = []
    registry = HookRegistry()

    def first() -> None:
        calls.append("first")

    def second() -> None:
        calls.append("second")

    def early() -> None:
        calls.append("early")

    registry.register(first)
    snapshot = registry.snapshot()
    fork = registry.copy()
    registry.register(second)
    fork.register(early, priority=-1)
    fork.register(second)
    assert list(fork) == [early, first, second]
    for callback in fork:
        callback()
    assert calls == ["early", "first", "second"]
    registry.restore(snapshot)
    assert list(registry) == [first]


def test_programmatic_owner_has_no_implicit_project_roots() -> None:
    extension = Extension(Settings())
    assert extension.source_root is None
    assert extension.config_root is None
    with pytest.raises(ValueError, match="configured entry"):
        extension.watch("relative.txt")
    extension.close()
