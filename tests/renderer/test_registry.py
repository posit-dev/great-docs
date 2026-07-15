import pytest

from great_docs.hooks._registry import HookRegistry


def test_bare_register_adds_the_hook():
    reg: HookRegistry = HookRegistry()

    @reg.register
    def h(x):
        return x

    assert h in reg
    assert list(reg) == [h]
    assert reg.register(h) is h  # returns the hook (decorator contract)


def test_iter_sorts_low_priority_first():
    reg: HookRegistry = HookRegistry()

    @reg.register(priority=100)
    def late(x):
        return x

    @reg.register(priority=-100)
    def early(x):
        return x

    @reg.register  # default 0, registered last
    def mid(x):
        return x

    assert list(reg) == [early, mid, late]


def test_equal_priority_keeps_registration_order():
    reg: HookRegistry = HookRegistry()

    @reg.register(priority=5)
    def first(x):
        return x

    @reg.register(priority=5)
    def second(x):
        return x

    assert list(reg) == [first, second]


def test_priority_is_keyword_only():
    reg: HookRegistry = HookRegistry()
    with pytest.raises(TypeError):
        reg.register(lambda x: x, 100)  # positional priority rejected


def test_register_invalidates_run_order_cache():
    reg: HookRegistry = HookRegistry()

    @reg.register(priority=10)
    def a(x):
        return x

    assert list(reg) == [a]

    @reg.register(priority=-10)
    def b(x):
        return x

    assert list(reg) == [b, a]  # cache rebuilt after the new registration


def test_clear_drops_all_handlers():
    reg: HookRegistry = HookRegistry()

    @reg.register(priority=3)
    def a(x):
        return x

    assert len(reg) == 1
    reg.clear()
    assert len(reg) == 0
    assert list(reg) == []
