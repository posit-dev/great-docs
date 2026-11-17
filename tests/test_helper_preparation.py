"""Verify shared preparation, settings and lifetime in public rendering helpers"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import griffe as gf
import pytest

from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref._settings import Settings
from great_docs._apiref._tools import render_code_variable, render_type_object
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.introspect import DEFAULT_OPTIONS
from great_docs.hooks._object_resolved import REGISTRY as OBJECT_HOOKS


def make_reference(tmp_path: Path, setup: str, **settings: object) -> APIReference:
    """Create a configured operation for helper-only documentation"""
    entry = tmp_path / "extension.py"
    entry.write_text(setup, encoding="utf-8")
    return APIReference(
        {"package": "example", "sections": [], **settings},
        extension_source=_ExtensionSource(entry, tmp_path, tmp_path),
    )


def test_helper_uses_reference_parser_defaults_and_presentation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(DEFAULT_OPTIONS, "google", {"warn_missing_types": False})
    reference = make_reference(
        tmp_path,
        "def setup(extension):\n"
        "    @extension.on_docstring_parsed\n"
        "    def parsed(obj, sections):\n"
        "        extension.cache['options'] = dict(obj.docstring.parser_options)\n"
        "        extension.cache['parser'] = obj.docstring.parser\n"
        "        return sections\n",
        parser="google",
        callable_signatures={"style": "plain"},
    )
    source = '''
def run(value):
    """Run the helper

    Args:
        value (int): A Google-style parameter.
    """
'''
    try:
        rendered = render_code_variable(source, "run", customisation=reference)
        assert "A Google-style parameter." in rendered
        assert "[run]{.sig-name}" in rendered
        assert "```pythonsignature" not in rendered
        assert reference.extension.cache["parser"] == "google"
        assert reference.extension.cache["options"]["warn_missing_types"] is False
    finally:
        reference.close()


@pytest.mark.parametrize("helper", ["source", "import"])
def test_conflicting_settings_fail_before_setup(tmp_path: Path, helper: str) -> None:
    reference = make_reference(tmp_path, "raise AssertionError('setup must stay lazy')\n")
    try:
        with pytest.raises(ValueError, match="settings conflict"):
            if helper == "source":
                render_code_variable(
                    "value = 1\n", "value", Settings(parser="google"), customisation=reference
                )
            else:
                render_type_object(
                    "not_importable.VALUE", Settings(parser="google"), customisation=reference
                )
    finally:
        reference.close()


def test_equal_settings_reuse_reference_and_leave_it_open(tmp_path: Path) -> None:
    before = {name for name in sys.modules if name.startswith("_great_docs_extension_")}
    reference = make_reference(
        tmp_path,
        "def setup(extension):\n"
        "    extension.cache['setups'] = extension.cache.get('setups', 0) + 1\n",
    )
    try:
        first = render_code_variable("value = 1\n", "value", Settings(), customisation=reference)
        second = render_code_variable("value = 2\n", "value", customisation=reference)
        assert "1" in first
        assert "2" in second
        assert reference.extension.cache["setups"] == 1
        assert {name for name in sys.modules if name.startswith("_great_docs_extension_")} > before
    finally:
        reference.close()
    assert {name for name in sys.modules if name.startswith("_great_docs_extension_")} == before


def test_distinct_snippets_do_not_share_an_exclusion(tmp_path: Path) -> None:
    reference = make_reference(
        tmp_path,
        "def setup(extension):\n"
        "    @extension.on_object_resolved\n"
        "    def transform(obj):\n"
        "        extension.cache['objects'] = extension.cache.get('objects', 0) + 1\n"
        "        return None if getattr(obj, 'value', None) == '1' else obj\n",
    )
    try:
        assert render_code_variable("value = 1\n", "value", customisation=reference) == ""
        assert "2" in render_code_variable("value = 2\n", "value", customisation=reference)
        assert reference.extension.cache["objects"] == 2
    finally:
        reference.close()


def test_standalone_helper_uses_template_preparation() -> None:
    snapshot = OBJECT_HOOKS.snapshot()

    @OBJECT_HOOKS.register
    def transform(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        if obj.docstring is not None:
            obj.docstring.value = "Prepared helper documentation"
        return obj

    try:
        rendered = render_code_variable('def run():\n    """Original documentation"""\n', "run")
        assert "Prepared helper documentation" in rendered
        assert "Original documentation" not in rendered
    finally:
        OBJECT_HOOKS.restore(snapshot)


def test_dynamic_helpers_share_dotted_and_type_object_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package_name = "helper_dynamic_paths"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("from ._defs import Example as Alias\n", encoding="utf-8")
    (package / "_defs.py").write_text(
        'class Example:\n    """Original helper documentation"""\n', encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module(package_name)
    reference = make_reference(
        tmp_path,
        "def setup(extension):\n"
        "    @extension.on_object_resolved\n"
        "    def transform(obj):\n"
        "        extension.cache['objects'] = extension.cache.get('objects', 0) + 1\n"
        "        obj.docstring.value = 'Prepared dynamic documentation'\n"
        "        return obj\n",
        dynamic=True,
    )
    try:
        dotted = render_type_object(f"{package_name}.Alias", customisation=reference)
        typed = render_type_object(module.Alias, customisation=reference)
        assert "Prepared dynamic documentation" in dotted
        assert "Prepared dynamic documentation" in typed
        assert reference.extension.cache["objects"] == 1
    finally:
        reference.close()
        for name in list(sys.modules):
            if name == package_name or name.startswith(package_name + "."):
                del sys.modules[name]
