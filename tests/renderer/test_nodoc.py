from types import SimpleNamespace

from great_docs._builtin._directives import exclude_nodoc


def _obj(doc: str | None) -> SimpleNamespace:
    """Build a minimal stand-in for a griffe object exposing a docstring"""
    docstring = SimpleNamespace(value=doc) if doc is not None else None
    return SimpleNamespace(docstring=docstring)


def test_object_tagged_nodoc_is_skipped():
    assert exclude_nodoc(_obj("Internal.\n\n%nodoc\n")) is None


def test_plain_object_passes_through_unchanged():
    obj = _obj("A normal docstring.")
    assert exclude_nodoc(obj) is obj


def test_object_without_docstring_passes_through():
    obj = _obj(None)
    assert exclude_nodoc(obj) is obj


def test_exclude_nodoc_registers_on_import():
    # exclude_nodoc registered via this module's top-level import (the decorator).
    from great_docs.hooks import _object_resolved

    assert exclude_nodoc in _object_resolved._OBJECT_RESOLVED_HOOKS
