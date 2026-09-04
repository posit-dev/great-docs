from great_docs._interlinks import resolve_aliases


def test_a_uniquely_claimed_alias_is_kept():
    res = resolve_aliases([("Thing", "demo.Thing")], taken=set())
    assert res.kept == {"Thing": "demo.Thing"}
    assert res.dropped == {}


def test_an_alias_claimed_twice_is_dropped_and_reported():
    res = resolve_aliases(
        [("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")], taken=set()
    )
    assert res.kept == {}
    assert res.dropped == {"Cache": ("demo.net.Cache", "demo.store.Cache")}


def test_one_object_claiming_an_alias_twice_is_not_a_collision():
    res = resolve_aliases([("Thing", "demo.Thing"), ("Thing", "demo.Thing")], taken=set())
    assert res.kept == {"Thing": "demo.Thing"}
    assert res.dropped == {}


def test_an_alias_that_is_already_a_real_name_is_skipped_quietly():
    """The real name wins, and the reference is not ambiguous."""
    res = resolve_aliases([("demo.Thing", "demo.pkg.Thing")], taken={"demo.Thing"})
    assert res.kept == {}
    assert res.dropped == {}
