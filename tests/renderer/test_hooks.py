import pytest

from great_docs import hooks
from great_docs.hooks import _object_resolved


@pytest.fixture
def clean_hooks():
    """Save and restore the object_resolved registry entries around a test"""
    reg = _object_resolved.REGISTRY
    saved = list(reg._entries)
    saved_seq = reg._sequence
    reg.clear()
    yield
    reg._entries[:] = saved
    reg._sequence = saved_seq
    reg._ordered = None


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


def test_bare_decorator_registers_the_hook(clean_hooks):
    @hooks.on_object_resolved
    def h(obj):
        return obj

    assert h in _object_resolved.REGISTRY
    assert list(_object_resolved.REGISTRY) == [h]


def test_priority_orders_emit_low_to_high(clean_hooks):
    order: list[str] = []

    @hooks.on_object_resolved(priority=100)
    def late(obj):
        order.append("late")
        return obj

    @hooks.on_object_resolved(priority=-100)
    def early(obj):
        order.append("early")
        return obj

    @hooks.on_object_resolved
    def mid(obj):
        order.append("mid")
        return obj

    _object_resolved.emit_object_resolved("X")
    assert order == ["early", "mid", "late"]


def test_low_priority_none_short_circuits_before_high(clean_hooks):
    calls: list[str] = []

    @hooks.on_object_resolved(priority=100)
    def never(obj):
        calls.append("never")
        return obj

    @hooks.on_object_resolved(priority=-100)
    def drop(obj):
        calls.append("drop")
        return None

    assert _object_resolved.emit_object_resolved("X") is None
    assert calls == ["drop"]
