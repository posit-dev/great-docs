from datetime import timedelta

import requests

from great_docs._interlinks import (
    Source,
    load_source,
    resolve_aliases,
    sources_from_config,
)
from great_docs._sphinx_inventory import Inventory, InventoryEntry, encode
from great_docs.config import Config


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


def test_a_project_declaring_no_sources_links_only_within_itself(tmp_path):
    """The lookup is strict, so an option missing from the defaults raises."""
    (tmp_path / "great-docs.yml").write_text("module: demo\n")

    cfg = Config(tmp_path)

    assert cfg.interlinks_sources == {}


DEMO = Inventory(
    "numpy",
    "2.0",
    (InventoryEntry("numpy.ndarray", "py", "class", 1, "ndarray.html", "numpy.ndarray"),),
)


def test_source_location_honours_the_override():
    src = Source.from_config(
        "numpy", {"url": "https://numpy.org/", "inv": "/tmp/numpy.inv", "aliases": ["np"]}
    )
    assert src.location == "/tmp/numpy.inv"
    assert src.aliases == ("np",)


def test_sources_from_config_skips_an_entry_with_no_url():
    assert sources_from_config({"broken": {"aliases": ["b"]}}) == []


def test_load_source_reads_a_local_inventory(tmp_path):
    path = tmp_path / "numpy.inv"
    path.write_bytes(encode(DEMO))
    src = Source.from_config("numpy", {"url": "https://numpy.org/", "inv": str(path)})

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is not None and inv.entries[0].name == "numpy.ndarray"
    assert note == ""


def test_load_source_downloads_and_caches(tmp_path, monkeypatch):
    calls = []

    class _Response:
        content = encode(DEMO)

        def raise_for_status(self):
            return None

    def _get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(requests, "get", _get)
    cache = tmp_path / "cache"
    src = Source.from_config("numpy", {"url": "https://numpy.org/doc/stable/"})

    first, _ = load_source(src, cache)
    second, _ = load_source(src, cache)

    assert first == second
    # One call, at the URL derived from the source, so the second load was cached.
    assert calls == ["https://numpy.org/doc/stable/objects.inv"]


def test_load_source_falls_back_to_a_stale_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "numpy.inv").write_bytes(encode(DEMO))

    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)
    src = Source.from_config("numpy", {"url": "https://numpy.org/doc/stable/"})

    inv, note = load_source(src, cache, max_age=timedelta(seconds=0))

    assert inv is not None
    assert "cached" in note


def test_load_source_reports_a_source_it_cannot_read(tmp_path, monkeypatch):
    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)
    src = Source.from_config("numpy", {"url": "https://numpy.org/doc/stable/"})

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is None
    assert "numpy" in note
