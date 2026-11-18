"""Verify preparation and settings in the public rendering helpers"""

from __future__ import annotations

import griffe as gf
import pytest

from great_docs._apiref._settings import CallableSignatures, Settings
from great_docs._apiref._tools import render_code_variable
from great_docs._apiref.introspect import DEFAULT_OPTIONS
from great_docs.hooks._object_resolved import REGISTRY as OBJECT_HOOKS


def test_helper_applies_parser_defaults_and_presentation_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setitem(DEFAULT_OPTIONS, "google", {"warn_missing_types": False})
    snapshot = OBJECT_HOOKS.snapshot()
    seen: dict[str, object] = {}

    @OBJECT_HOOKS.register
    def record(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        assert obj.docstring is not None
        seen["parser"] = obj.docstring.parser
        seen["options"] = dict(obj.docstring.parser_options)
        return obj

    source = '''
def run(value):
    """Run the helper

    Args:
        value (int): A Google-style parameter.
    """
'''
    settings = Settings(parser="google", callable_signatures=CallableSignatures(style="plain"))
    try:
        rendered = render_code_variable(source, "run", settings)
    finally:
        OBJECT_HOOKS.restore(snapshot)
    assert "A Google-style parameter." in rendered
    assert "[run]{.sig-name}" in rendered
    assert "```pythonsignature" not in rendered
    assert seen["parser"] == "google"
    assert seen["options"] == {"warn_missing_types": False}


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
