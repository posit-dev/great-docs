from datetime import timedelta

import pytest
import requests

from great_docs._interlinks import (
    AliasClaims,
    Index,
    Source,
    build_index,
    build_project_index,
    load_source,
    resolve_aliases,
    root_modules,
    sources_from_config,
    write_index,
)
from great_docs._interlinks.sources import InventoryCache
from great_docs._sphinx_inventory import Inventory, InventoryEntry, encode
from great_docs.config import Config


class _Item:
    """Stand-in for the renderer's InventoryItem"""

    def __init__(self, alias: str, name: str) -> None:
        self.name = name
        self.aliases = (alias,)


def _item(alias: str, name: str) -> _Item:
    return _Item(alias, name)


def test_a_uniquely_claimed_alias_is_kept():
    res = resolve_aliases(AliasClaims(claimed=(("Thing", "demo.Thing"),), published=frozenset()))
    assert res.kept == {"Thing": "demo.Thing"}
    assert res.dropped == {}


def test_an_alias_claimed_twice_is_dropped_and_reported():
    res = resolve_aliases(
        AliasClaims(claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")))
    )
    assert res.kept == {}
    assert res.dropped == {"Cache": ("demo.net.Cache", "demo.store.Cache")}


def test_one_object_claiming_an_alias_twice_is_not_a_collision():
    res = resolve_aliases(AliasClaims(claimed=(("Thing", "demo.Thing"), ("Thing", "demo.Thing"))))
    assert res.kept == {"Thing": "demo.Thing"}
    assert res.dropped == {}


def test_class_qualified_aliases_disambiguate_a_shared_method_name():
    """`StoreCache.flush` and `NetCache.flush` each resolve even though `flush` alone is ambiguous."""
    claims = (
        ("flush", "demo.StoreCache.flush"),
        ("flush", "demo.NetCache.flush"),
        ("StoreCache.flush", "demo.StoreCache.flush"),
        ("NetCache.flush", "demo.NetCache.flush"),
    )
    res = resolve_aliases(AliasClaims(claimed=claims))
    assert res.dropped == {"flush": ("demo.NetCache.flush", "demo.StoreCache.flush")}
    assert res.kept == {
        "StoreCache.flush": "demo.StoreCache.flush",
        "NetCache.flush": "demo.NetCache.flush",
    }


def test_an_alias_that_is_already_a_real_name_is_skipped_quietly():
    """The real name wins, and the reference is not ambiguous."""
    res = resolve_aliases(
        AliasClaims(
            claimed=(("demo.Thing", "demo.pkg.Thing"),), published=frozenset({"demo.Thing"})
        )
    )
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


def test_a_sources_inventory_sits_beside_its_documentation():
    """Every project publishes it at the same place, so there is nothing to configure."""
    src = Source(name="numpy", url="https://numpy.org/doc/stable/", aliases=("np",))
    assert src.inventory_location == "https://numpy.org/doc/stable/objects.inv"
    assert src.aliases == ("np",)


def test_sources_from_config_rejects_an_entry_with_no_url():
    sources, notes = sources_from_config({"numpy": {"aliases": ["np"]}})

    assert sources == []
    assert len(notes) == 1
    assert "numpy" in notes[0]


def test_a_filesystem_url_needs_nothing_further():
    """One url answers both questions, whether it is served or on disk."""
    sources, notes = sources_from_config({"sibling": {"url": "/srv/docs/sibling"}})

    assert notes == []
    assert len(sources) == 1
    assert sources[0].inventory_location == "/srv/docs/sibling/objects.inv"
    assert sources[0].link_prefix == "/srv/docs/sibling"


def test_a_relative_url_is_reported_but_still_used():
    """One prefix serves every page depth, so a relative url cannot suit them all."""
    sources, notes = sources_from_config({"sibling": {"url": "../sibling/great-docs"}})

    assert len(sources) == 1
    assert len(notes) == 1
    assert "relative" in notes[0]
    assert "sibling" in notes[0]


def test_an_absolute_url_is_not_reported_as_relative():
    """A leading slash resolves from the site root, the same from every page."""
    _, notes = sources_from_config({"sibling": {"url": "/sibling/"}})

    assert notes == []


def test_a_served_url_answers_both_questions():
    sources, notes = sources_from_config({"numpy": {"url": "https://numpy.org/doc/stable/"}})

    assert notes == []
    assert sources[0].link_prefix == "https://numpy.org/doc/stable"
    assert sources[0].inventory_location == "https://numpy.org/doc/stable/objects.inv"


def test_load_source_reads_a_local_inventory(tmp_path):
    """A url may address a directory on disk, as a sibling project's build does."""
    (tmp_path / "numpy.inv").write_bytes(encode(DEMO))
    (tmp_path / "objects.inv").write_bytes(encode(DEMO))
    src = Source(name="numpy", url=str(tmp_path))

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is not None and inv.entries[0].name == "numpy.ndarray"
    assert note == ""


def test_load_source_reports_a_corrupt_local_inventory(tmp_path):
    (tmp_path / "objects.inv").write_bytes(b"not an inventory")
    src = Source(name="numpy", url=str(tmp_path))

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is None
    assert "numpy" in note


def test_load_source_reports_a_local_inventory_path_that_is_a_directory(tmp_path):
    """A directory at the inventory path (IsADirectoryError) is reported, not raised."""
    (tmp_path / "objects.inv").mkdir()
    src = Source(name="numpy", url=str(tmp_path))

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is None
    assert "numpy" in note


def test_load_source_reports_an_unreadable_cache_without_a_working_network(tmp_path, monkeypatch):
    """A cache that raises OSError on read is treated as unreadable, not fatal."""
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    # A directory where the cached inventory file should be: reading it raises
    # IsADirectoryError rather than decoding cleanly or cleanly missing.
    InventoryCache(cache).path_for(src).mkdir()

    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)

    inv, note = load_source(src, cache)

    assert inv is None
    assert "numpy" in note


def test_load_source_retains_a_download_when_caching_fails(tmp_path, monkeypatch):
    """A download that decodes fine is still returned when writing the cache fails."""
    cache = tmp_path / "cache"
    # A file occupies the cache directory's path, so mkdir() cannot create it.
    cache.write_bytes(b"not a directory")
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")

    class _Response:
        content = encode(DEMO)

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: _Response())

    inv, note = load_source(src, cache)

    assert inv is not None and inv.entries[0].name == "numpy.ndarray"
    assert "could not cache" in note


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
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")

    first, _ = load_source(src, cache)
    second, _ = load_source(src, cache)

    assert first == second
    # One call, at the URL derived from the source, so the second load was cached.
    assert calls == ["https://numpy.org/doc/stable/objects.inv"]


def test_load_source_falls_back_to_a_stale_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    InventoryCache(cache).path_for(src).write_bytes(encode(DEMO))

    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)

    inv, note = load_source(src, cache, max_age=timedelta(seconds=0))

    assert inv is not None
    assert "cached" in note


def test_load_source_falls_back_to_a_stale_cache_on_a_corrupt_download(tmp_path, monkeypatch):
    """Do not overwrite a valid cache with a corrupt successful response."""
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    good_cache = InventoryCache(cache).path_for(src)
    good_cache.write_bytes(encode(DEMO))

    class _Response:
        content = b"<html>not an inventory</html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: _Response())

    inv, note = load_source(src, cache, max_age=timedelta(seconds=0))

    assert inv is not None
    assert "cached" in note
    # Retain the valid cached copy after rejecting the corrupt download.
    assert good_cache.read_bytes() == encode(DEMO)


def test_load_source_redownloads_when_the_fresh_cache_is_corrupt(tmp_path, monkeypatch):
    """Refetch a fresh cache file that cannot be decoded."""
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    InventoryCache(cache).path_for(src).write_bytes(b"not an inventory")

    class _Response:
        content = encode(DEMO)

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: _Response())

    inv, note = load_source(src, cache)

    assert inv is not None and inv.entries[0].name == "numpy.ndarray"
    assert InventoryCache(cache).path_for(src).read_bytes() == encode(DEMO)


def test_load_source_reports_when_the_cache_and_the_download_are_both_unreadable(
    tmp_path, monkeypatch
):
    cache = tmp_path / "cache"
    cache.mkdir()
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    InventoryCache(cache).path_for(src).write_bytes(b"not an inventory")

    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)

    inv, note = load_source(src, cache)

    assert inv is None
    assert "numpy" in note


def test_load_source_reports_a_corrupt_download_with_no_cache_to_fall_back_on(
    tmp_path, monkeypatch
):
    class _Response:
        content = b"<html>not an inventory</html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(requests, "get", lambda url, **kwargs: _Response())
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is None
    assert "numpy" in note


def test_load_source_misses_the_cache_when_the_url_changes(tmp_path, monkeypatch):
    """Use a new cache entry when a source URL changes."""
    cache = tmp_path / "cache"
    old_src = Source(name="numpy", url="https://numpy.org/doc/1.0/")
    InventoryCache(cache).path_for(old_src).parent.mkdir(parents=True, exist_ok=True)
    InventoryCache(cache).path_for(old_src).write_bytes(encode(DEMO))

    calls = []

    class _Response:
        content = encode(DEMO)

        def raise_for_status(self):
            return None

    def _get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(requests, "get", _get)
    new_src = Source(name="numpy", url="https://numpy.org/doc/2.0/")

    load_source(new_src, cache)

    assert calls == ["https://numpy.org/doc/2.0/objects.inv"]


def test_load_source_reports_a_source_it_cannot_read(tmp_path, monkeypatch):
    def _get(url, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(requests, "get", _get)
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")

    inv, note = load_source(src, tmp_path / "cache")

    assert inv is None
    assert "numpy" in note


LOCAL = Inventory(
    "demo",
    "1.0",
    (
        InventoryEntry(
            "demo.Thing", "py", "class", 1, "reference/Thing.html#demo.Thing", "demo.Thing"
        ),
        InventoryEntry("demo.go", "py", "function", 1, "reference/go.html#demo.go", "demo.go"),
    ),
)


def test_root_modules_are_ordered_by_frequency():
    inv = Inventory(
        "x",
        "1",
        (
            InventoryEntry("sklearn.a", "py", "class", 1, "a.html", "sklearn.a"),
            InventoryEntry("sklearn.b", "py", "class", 1, "b.html", "sklearn.b"),
            InventoryEntry("other.c", "py", "class", 1, "c.html", "other.c"),
        ),
    )
    assert root_modules(inv) == ("sklearn", "other")


def test_root_modules_ignore_entries_outside_the_python_domain():
    inv = Inventory(
        "numpy",
        "1",
        (
            InventoryEntry("numpy.ndarray", "py", "class", 1, "ndarray.html", "-"),
            InventoryEntry("user/quickstart", "std", "doc", -1, "user/quickstart.html", "-"),
            InventoryEntry("user/absolute_beginners", "std", "doc", -1, "user/ab.html", "-"),
        ),
    )

    assert root_modules(inv) == ("numpy",)


def test_local_entries_are_marked_and_keep_their_uri():
    index = build_index(LOCAL, AliasClaims(), [])
    assert index.names["demo.Thing"][0].uri == "/reference/Thing.html#demo.Thing"
    assert index.names["demo.Thing"][0].is_local is True


def test_external_uris_are_prefixed_with_the_source_url():
    src = Source(name="numpy", url="https://numpy.org/doc/stable/")
    index = build_index(LOCAL, AliasClaims(), [(src, DEMO)])
    assert index.names["numpy.ndarray"][0].uri == "https://numpy.org/doc/stable/ndarray.html"
    assert index.names["numpy.ndarray"][0].is_local is False


def test_a_filesystem_url_prefixes_links_as_written():
    """A url on disk is the link prefix too, resolving relative to the reading page."""
    src = Source(name="sibling", url="../sibling/great-docs")
    index = build_index(LOCAL, AliasClaims(), [(src, DEMO)])
    assert index.names["numpy.ndarray"][0].uri == "../sibling/great-docs/ndarray.html"


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("ndarray.html", "https://numpy.org/doc/stable/ndarray.html"),
        ("api/ndarray.html", "https://numpy.org/doc/stable/api/ndarray.html"),
        ("/ndarray.html", "https://numpy.org/ndarray.html"),
        ("https://other.example/ndarray.html", "https://other.example/ndarray.html"),
    ],
)
def test_an_external_uri_is_joined_against_its_source(uri, expected):
    inv = Inventory("numpy", "1", (InventoryEntry("numpy.ndarray", "py", "class", 1, uri, "-"),))
    sources, _ = sources_from_config({"numpy": {"url": "https://numpy.org/doc/stable/"}})

    index = build_index(Inventory("mypkg", "1", ()), AliasClaims(), [(sources[0], inv)])

    assert index.names["numpy.ndarray"][0].uri == expected


def test_a_filesystem_source_is_read_and_linked_from_one_url(tmp_path):
    """The inventory is read from the directory and links are prefixed with it."""
    sibling_dir = tmp_path / "sibling"
    sibling_dir.mkdir()
    (sibling_dir / "objects.inv").write_bytes(encode(DEMO))

    project_dir = tmp_path / "myproj"
    project_dir.mkdir()
    (project_dir / "great-docs.yml").write_text(
        f"module: myproj\ninterlinks:\n  sources:\n    sibling:\n      url: {sibling_dir}\n"
    )

    index, notes = build_project_index(project_dir, Config(project_dir), "myproj", AliasClaims())

    assert index.names["numpy.ndarray"][0].uri == f"{sibling_dir}/ndarray.html"
    assert notes == []


def test_a_kept_alias_points_at_the_target_entry():
    index = build_index(LOCAL, AliasClaims(claimed=(("Thing", "demo.Thing"),)), [])
    assert index.names["Thing"] == index.names["demo.Thing"]


def test_an_ambiguous_alias_is_absent_and_reported():
    index = build_index(LOCAL, AliasClaims(claimed=(("T", "demo.Thing"), ("T", "demo.go"))), [])
    assert "T" not in index.names
    assert index.dropped["T"] == ("demo.Thing", "demo.go")


def test_a_local_claim_beats_an_external_name_of_the_same_spelling():
    """Prose in this project means this project's object."""
    local = Inventory(
        "mypkg", "1", (InventoryEntry("mypkg.store.Cache", "py", "class", 1, "r/Cache.html", "-"),)
    )
    external = Inventory("other", "1", (InventoryEntry("Cache", "py", "class", 1, "c.html", "-"),))
    source = Source(name="other", url="https://other.example/")

    index = build_index(
        local,
        AliasClaims.make([_item("Cache", "mypkg.store.Cache")]),
        [(source, external)],
    )

    assert index.names["Cache"][0].is_local is True
    assert index.names["Cache"][0].uri == "/r/Cache.html"
    assert index.names["Cache"][1].source == "other"
    assert index.dropped == {}


def test_an_ambiguous_claim_leaves_an_external_name_marked_but_present():
    """Mark a locally ambiguous short name even when an external target exists"""
    local = Inventory(
        "mypkg",
        "1",
        (
            InventoryEntry("mypkg.store.Cache", "py", "class", 1, "r/store.Cache.html", "-"),
            InventoryEntry("mypkg.net.Cache", "py", "class", 1, "r/net.Cache.html", "-"),
        ),
    )
    external = Inventory("other", "1", (InventoryEntry("Cache", "py", "class", 1, "c.html", "-"),))
    source = Source(name="other", url="https://other.example/")

    index = build_index(
        local,
        AliasClaims.make([_item("Cache", "mypkg.store.Cache"), _item("Cache", "mypkg.net.Cache")]),
        [(source, external)],
    )

    assert index.dropped["Cache"] == ("mypkg.net.Cache", "mypkg.store.Cache")
    assert index.names["Cache"][0].source == "other"


def test_an_alias_prefix_maps_to_the_sources_root_modules():
    src = Source(name="numpy", url="https://numpy.org/", aliases=("np",))
    index = build_index(LOCAL, AliasClaims(), [(src, DEMO)])
    assert index.prefixes["np"] == ("numpy",)


def test_a_local_entry_outranks_an_external_one_for_the_same_name():
    src = Source(name="other", url="https://other.example/")
    clash = Inventory(
        "other",
        "1",
        (InventoryEntry("demo.Thing", "py", "class", 1, "t.html", "demo.Thing"),),
    )
    index = build_index(LOCAL, AliasClaims(), [(src, clash)])
    assert index.names["demo.Thing"][0].is_local is True


def test_write_index_writes_a_loadable_lua_chunk(tmp_path):
    index = build_index(LOCAL, AliasClaims(claimed=(("Thing", "demo.Thing"),)), [])
    out = tmp_path / "index.lua"

    write_index(index, out)

    text = out.read_text()
    assert text.startswith("return {")
    assert '["demo.Thing"]' in text
    assert '["Thing"]' in text
    assert 'uri = "/reference/Thing.html#demo.Thing"' in text


def test_load_source_reads_a_relative_url_from_the_project_root(tmp_path):
    """A relative url belongs to the project, not to wherever the build runs."""
    (tmp_path / "sibling").mkdir()
    (tmp_path / "sibling" / "objects.inv").write_bytes(encode(DEMO))
    src = Source(name="extdemo", url="./sibling")

    inv, note = load_source(src, tmp_path / "cache", root=tmp_path)

    assert inv is not None
    assert note == ""


def test_the_cache_returns_none_for_a_file_that_is_a_directory(tmp_path):
    """A cache entry that is a directory is a miss, not a crash."""
    source = Source(name="numpy", url="https://numpy.org/doc/stable/")
    cache = InventoryCache(tmp_path)
    cache.path_for(source).mkdir(parents=True)

    assert cache.read(source) is None
    assert cache.is_fresh(source, timedelta(days=7)) is False


def test_the_cache_returns_none_for_a_truncated_entry(tmp_path):
    source = Source(name="numpy", url="https://numpy.org/doc/stable/")
    cache = InventoryCache(tmp_path)
    path = cache.path_for(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"# Sphinx inventory version 2\n# Project: x\n# Version: 1\n# z\nnot-zlib")

    assert cache.read(source) is None


def test_the_cache_returns_none_for_a_file_that_is_not_an_inventory(tmp_path):
    source = Source(name="numpy", url="https://numpy.org/doc/stable/")
    cache = InventoryCache(tmp_path)
    path = cache.path_for(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"hello")

    assert cache.read(source) is None


def test_the_cache_reports_a_directory_it_cannot_create(tmp_path):
    """Storing into an unusable directory returns a note rather than raising."""
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")

    source = Source(name="numpy", url="https://numpy.org/doc/stable/")
    note = InventoryCache(blocker / "interlinks").store(source, b"payload")

    assert note != ""


def test_function_parentheses_are_on_by_default():
    index = build_index(LOCAL, AliasClaims(), [])
    assert index.add_function_parentheses is True


def test_the_index_carries_the_parentheses_choice(tmp_path):
    """The filter knows only what the index tells it."""
    index = build_index(LOCAL, AliasClaims(), [], add_function_parentheses=False)
    out = tmp_path / "index.lua"

    write_index(index, out)

    assert "add_function_parentheses = false," in out.read_text()


def test_the_index_carries_the_role_synonyms(tmp_path):
    """The filter reads the role vocabulary rather than holding its own."""
    path = tmp_path / "index.lua"
    write_index(Index(), path)
    text = path.read_text(encoding="utf-8")

    assert '["meth"] = "method"' in text
    assert '["exc"] = "exception"' in text
    assert '["obj"] = ""' in text


def test_the_index_carries_the_callable_roles(tmp_path):
    """The filter reads which roles show a trailing `()` rather than holding its own."""
    path = tmp_path / "index.lua"
    write_index(Index(), path)
    text = path.read_text(encoding="utf-8")

    assert '["function"] = true' in text
    assert '["method"] = true' in text


def test_the_index_carries_the_ambiguous_names(tmp_path):
    """Write ambiguous short names for the filter to reject"""
    index = build_index(LOCAL, AliasClaims(claimed=(("T", "demo.Thing"), ("T", "demo.go"))), [])
    path = tmp_path / "index.lua"

    write_index(index, path)

    assert '["T"] = true' in path.read_text(encoding="utf-8")


def test_write_index_removes_a_stale_compiled_index(tmp_path):
    """A compiled index must never outlive the source it was compiled from."""
    path = tmp_path / "index.lua"
    compiled = tmp_path / "index.luac"
    compiled.write_bytes(b"stale")

    write_index(Index(), path)

    assert not compiled.exists()
