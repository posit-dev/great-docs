import pytest

from great_docs import hooks
from great_docs.hooks import _object_resolved


@pytest.fixture
def clean_hooks():
    """Snapshot and restore the object_resolved handler list around a test"""
    saved = list(_object_resolved._OBJECT_RESOLVED_HOOKS)
    _object_resolved._OBJECT_RESOLVED_HOOKS[:] = []
    yield
    _object_resolved._OBJECT_RESOLVED_HOOKS[:] = saved


def test_only_on_object_resolved_is_exported():
    assert hooks.__all__ == ["on_object_resolved"]


def test_emit_object_resolved_threads_object_through_handlers(clean_hooks):
    seen: list[str] = []

    @hooks.on_object_resolved
    def annotate(obj):
        seen.append(obj)
        return f"{obj}!"

    assert _object_resolved.emit_object_resolved("X") == "X!"
    assert seen == ["X"]


def test_emit_object_resolved_none_skips_and_short_circuits(clean_hooks):
    calls: list[str] = []

    @hooks.on_object_resolved
    def drop(obj):
        calls.append("drop")
        return None

    @hooks.on_object_resolved
    def never(obj):
        calls.append("never")
        return obj

    assert _object_resolved.emit_object_resolved("X") is None
    assert calls == ["drop"]


def test_on_object_resolved_returns_the_handler(clean_hooks):
    def h(obj):
        return obj

    assert hooks.on_object_resolved(h) is h


def test_emit_object_resolved_with_no_handlers_is_identity(clean_hooks):
    sentinel = object()
    assert _object_resolved.emit_object_resolved(sentinel) is sentinel
