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
from great_docs.config import ConfigError
from great_docs.hooks._docstring_parsed import REGISTRY as PARSED_HOOKS
from great_docs.hooks._object_resolved import REGISTRY as OBJECT_HOOKS
from great_docs.hooks._registry import HookRegistry
from great_docs.rendering import ClassRenderer, Renderers
from tests.support import MakeReference, WriteExtension


def owned_modules() -> set[str]:
    """
    List the project modules that extensions have imported

    Returns
    -------
    :
        The names in `sys.modules` under the extensions' private namespace.
    """
    return {name for name in sys.modules if name.startswith("_great_docs_extension_")}


@pytest.mark.parametrize("value", [0, False, [], {}, "", " ", "extension.txt"])
def test_invalid_extension_path_is_rejected_without_import(tmp_path: Path, value: object):
    config_path = tmp_path / "great-docs.yml"
    config_path.write_text(f"api_reference_extension: {json.dumps(value)}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="api_reference_extension"):
        Config(tmp_path)


@pytest.mark.parametrize("absolute", [False, True])
def test_entry_path_uses_selected_configuration_root(tmp_path: Path, absolute: bool):
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


def test_null_extension_source_is_absent(tmp_path: Path):
    config = Config(tmp_path)
    assert config.api_reference_extension is None
    assert _ExtensionSource.make(config, tmp_path / "docs") is None


def test_sections_and_unused_close_do_not_load_configured_python(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    marker = tmp_path / "loaded"
    source = write_extension(
        f"""
        from pathlib import Path
        Path({str(marker)!r}).touch()
        """
    )
    before = owned_modules()
    reference = make_reference(
        {"package": "example", "sections": [{"contents": ["Example"]}]}, source
    )
    assert reference.sections[0].contents[0].name == "Example"
    reference.close()
    reference.close()
    assert not marker.exists()
    assert owned_modules() == before


def test_setup_runs_once_and_selects_renderers(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        from great_docs.rendering import ClassRenderer, Renderers

        class CustomClass(ClassRenderer):
            pass

        def setup(extension):
            extension.cache['calls'] = extension.cache.get('calls', 0) + 1
            extension.set_renderers(Renderers(classes=CustomClass))
        """,
        source_root=tmp_path / "docs",
    )
    reference = make_reference({"package": "example", "sections": []}, source)
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


def test_relative_helpers_refresh_same_size_edits(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    helper = tmp_path / "helper.py"
    helper.write_text("VALUE = 'first'\n", encoding="utf-8")
    timestamp = helper.stat().st_mtime_ns
    source = write_extension(
        """
        from .helper import VALUE

        def setup(extension):
            extension.cache['value'] = VALUE
        """
    )
    first = make_reference({"package": "example"}, source)
    first_extension = first.extension
    first_extension.load()
    assert first_extension.cache["value"] == "first"
    first.close()
    helper.write_text("VALUE = 'other'\n", encoding="utf-8")
    os.utime(helper, ns=(timestamp, timestamp))
    second = make_reference({"package": "example"}, source)
    second.extension.load()
    assert second.extension.cache["value"] == "other"
    assert second.extension.cache is not first_extension.cache


def test_late_relative_imports_and_dataclass_inspection_work_until_close(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    helper = tmp_path / "helper.py"
    helper.write_text(
        "from dataclasses import dataclass\n@dataclass\nclass Value:\n    text: str = 'current'\n",
        encoding="utf-8",
    )
    source = write_extension(
        """
        def read():
            from .helper import Value
            return Value()

        def setup(extension):
            extension.cache['read'] = read
        """
    )
    before = owned_modules()
    reference = make_reference({"package": "example"}, source)
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


def test_closing_extension_preserves_installed_package_cache(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        import json

        def setup(extension):
            extension.cache['json'] = json
        """
    )
    reference = make_reference({"package": "example"}, source)
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
    write_extension: WriteExtension,
    make_reference: MakeReference,
    code: str,
    cause: type[Exception],
    phase: str,
):
    source = write_extension(code)
    before = owned_modules()
    finders = list(sys.meta_path)
    reference = make_reference({"package": "example"}, source)
    with pytest.raises(ExtensionError, match=rf"extension.py: {phase}:") as error:
        reference.extension.load()
    assert isinstance(error.value.__cause__, cause)
    assert str(error.value).count(f": {phase}:") == 1
    assert owned_modules() == before
    assert sys.meta_path == finders
    with pytest.raises(RuntimeError, match="extension is closed"):
        reference.extension.load()


def test_partial_helper_failure_cleans_modules_and_finder(
    tmp_path: Path, write_extension: WriteExtension
):
    (tmp_path / "helper.py").write_text("raise ValueError('broken helper')\n", encoding="utf-8")
    source = write_extension("from .helper import VALUE\n")
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


def test_missing_entry_is_a_lazy_load_error(tmp_path: Path, make_reference: MakeReference):
    source = _ExtensionSource(tmp_path / "missing.py", tmp_path, tmp_path)
    reference = make_reference({"package": "example"}, source)
    assert reference.sections == []
    with pytest.raises(ExtensionError, match="missing.py: load:") as error:
        _ = reference.resolved
    assert isinstance(error.value.__cause__, FileNotFoundError)


@pytest.mark.parametrize("during_import", [False, True])
def test_global_template_mutation_is_rejected_and_restored(
    write_extension: WriteExtension, make_reference: MakeReference, during_import: bool
):
    if during_import:
        setup = """
            from great_docs.hooks import on_object_resolved

            on_object_resolved(lambda obj: obj)

            def setup(extension):
                pass
        """
    else:
        setup = """
            from great_docs.hooks import on_object_resolved

            def setup(extension):
                on_object_resolved(lambda obj: obj)
        """
    source = write_extension(setup)
    object_snapshot = OBJECT_HOOKS.snapshot()
    parsed_snapshot = PARSED_HOOKS.snapshot()
    reference = make_reference({"package": "example"}, source)
    with pytest.raises(ExtensionError, match="supplied extension"):
        reference.extension.load()
    assert OBJECT_HOOKS.snapshot() == object_snapshot
    assert PARSED_HOOKS.snapshot() == parsed_snapshot


def test_setup_failure_restores_global_templates(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        from great_docs.hooks import on_object_resolved

        def setup(extension):
            on_object_resolved(lambda obj: obj)
            raise ValueError('original cause')
        """
    )
    before = OBJECT_HOOKS.snapshot()
    reference = make_reference({"package": "example"}, source)
    with pytest.raises(ExtensionError) as error:
        reference.extension.load()
    assert isinstance(error.value.__cause__, ValueError)
    assert OBJECT_HOOKS.snapshot() == before


def test_registration_freezes_after_setup(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        def setup(extension):
            extension.on_object_resolved(lambda obj: obj)

            @extension.on_docstring_parsed(priority=2)
            def parsed(obj, sections):
                return sections

            extension.cache['decorator'] = extension.on_object_resolved(priority=2)
        """
    )
    reference = make_reference({"package": "example"}, source)
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


def test_watch_declarations_keep_entry_relative_missing_paths(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        def setup(extension):
            extension.watch('missing.txt')
            extension.watch('data/*.txt')
        """
    )
    reference = make_reference({"package": "example"}, source)
    reference.extension.load()
    assert reference.extension.declared_inputs == (
        tmp_path / "missing.txt",
        tmp_path / "data/*.txt",
    )


def test_hook_snapshots_share_callback_state_and_keep_priority_order():
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


def test_programmatic_owner_has_no_implicit_project_roots():
    extension = Extension(Settings())
    assert extension.source_root is None
    assert extension.config_root is None
    with pytest.raises(ValueError, match="configured entry"):
        extension.watch("relative.txt")
    extension.close()
