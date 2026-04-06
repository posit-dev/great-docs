"""Tests for the API Evolution Insights module (_api_diff)."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._api_diff import (
    ApiDiff,
    ApiSnapshot,
    CallEdge,
    DependencyGraph,
    InheritanceEdge,
    ParameterChange,
    ParameterInfo,
    SymbolChange,
    SymbolHistory,
    SymbolHistoryEntry,
    SymbolInfo,
    _EVOLUTION_TABLE_CSS,
    _annotation_str,
    _augment_params_with_separators,
    _describe_param_change,
    _detect_package_name,
    _diff_parameters,
    _diff_symbol,
    _escape_html,
    _extract_bases,
    _extract_decorators,
    _extract_package_at_tag,
    _extract_parameters,
    _filter_tag_range,
    _mermaid_id,
    _parameter_kind_str,
    _parse_marker_attrs,
    _symbol_change_to_dict,
    api_diff,
    build_dependency_graph,
    build_timeline,
    diff_snapshots,
    evolution_table,
    evolution_table_html,
    evolution_table_text,
    evolution_table_to_dict,
    format_signature,
    list_version_tags,
    process_evolution_markers,
    process_evolution_markers_in_file,
    render_evolution_table,
    render_evolution_table_from_dict,
    snapshot_at_tag,
    snapshot_from_griffe,
    symbol_history,
    timeline_to_mermaid,
)


def test_parameter_info_defaults():
    p = ParameterInfo(name="x")

    assert p.name == "x"
    assert p.annotation is None
    assert p.default is None
    assert p.kind == "POSITIONAL_OR_KEYWORD"


def test_parameter_info_full():
    p = ParameterInfo(name="y", annotation="int", default="5", kind="KEYWORD_ONLY")

    assert p.annotation == "int"
    assert p.default == "5"
    assert p.kind == "KEYWORD_ONLY"


def test_symbol_info_defaults():
    s = SymbolInfo(name="foo", kind="function")

    assert s.name == "foo"
    assert s.parameters == []
    assert s.bases == []
    assert s.decorators == []
    assert s.is_async is False
    assert s.return_annotation is None


def test_class_with_bases():
    s = SymbolInfo(name="Bar", kind="class", bases=["Base", "Mixin"])

    assert s.bases == ["Base", "Mixin"]


def test_api_snapshot_empty():
    snap = ApiSnapshot(version="v1.0", package_name="pkg")

    assert snap.symbol_count == 0
    assert snap.class_count == 0
    assert snap.function_count == 0


def test_counts():
    snap = ApiSnapshot(
        version="v1.0",
        package_name="pkg",
        symbols={
            "Foo": SymbolInfo(name="Foo", kind="class"),
            "Bar": SymbolInfo(name="Bar", kind="class"),
            "baz": SymbolInfo(name="baz", kind="function"),
            "QUX": SymbolInfo(name="QUX", kind="attribute"),
        },
    )

    assert snap.symbol_count == 4
    assert snap.class_count == 2
    assert snap.function_count == 1


def _make_diff() -> ApiDiff:
    return ApiDiff(
        old_version="v1",
        new_version="v2",
        package_name="pkg",
        added=[SymbolChange(symbol="new_fn", change_type="added")],
        removed=[SymbolChange(symbol="old_fn", change_type="removed", is_breaking=True)],
        changed=[
            SymbolChange(symbol="changed_fn", change_type="changed", is_breaking=True),
            SymbolChange(symbol="tweaked_fn", change_type="changed", is_breaking=False),
        ],
    )


def test_breaking_changes():
    diff = _make_diff()

    assert len(diff.breaking_changes) == 2
    names = {c.symbol for c in diff.breaking_changes}
    assert names == {"old_fn", "changed_fn"}


def test_has_breaking_changes():
    diff = _make_diff()

    assert diff.has_breaking_changes is True


def test_no_breaking():
    diff = ApiDiff(old_version="v1", new_version="v2", package_name="pkg")

    assert diff.has_breaking_changes is False


def test_to_dict():
    diff = _make_diff()
    d = diff.to_dict()

    assert d["old_version"] == "v1"
    assert d["new_version"] == "v2"
    assert d["summary"]["added"] == 1
    assert d["summary"]["removed"] == 1
    assert d["summary"]["changed"] == 2
    assert d["summary"]["breaking"] == 2


def test_api_diff_to_dict_roundtrip_json():
    diff = _make_diff()
    serialized = json.dumps(diff.to_dict())
    loaded = json.loads(serialized)

    assert loaded["package_name"] == "pkg"


def test_dots():
    assert _mermaid_id("pkg.module.Class") == "pkg_module_Class"


def test_hyphens():
    assert _mermaid_id("my-package") == "my_package"


def test_mermaid_id_plain():
    assert _mermaid_id("foo") == "foo"


def test_minimal():
    sc = SymbolChange(symbol="x", change_type="added")
    d = _symbol_change_to_dict(sc)

    assert d["symbol"] == "x"
    assert d["change_type"] == "added"
    assert d["is_breaking"] is False
    assert "details" not in d
    assert "parameter_changes" not in d
    assert "migration_hint" not in d


def test_symbol_change_to_dict_full():
    sc = SymbolChange(
        symbol="y",
        change_type="changed",
        details=["Type changed"],
        parameter_changes=[ParameterChange(parameter="a", change_type="removed", is_breaking=True)],
        is_breaking=True,
        migration_hint="Use z instead.",
    )
    d = _symbol_change_to_dict(sc)

    assert d["details"] == ["Type changed"]
    assert len(d["parameter_changes"]) == 1
    assert d["parameter_changes"][0]["parameter"] == "a"
    assert d["migration_hint"] == "Use z instead."


@pytest.mark.parametrize(
    "change_type, expected_substr",
    [
        ("added", "New parameter"),
        ("removed", "Removed parameter"),
        ("retyped", "type:"),
        ("default_changed", "default:"),
        ("kind_changed", "kind:"),
        ("reordered", "reordered"),
    ],
)
def test_descriptions(change_type, expected_substr):
    pc = ParameterChange(
        parameter="x",
        change_type=change_type,
        old_value="old",
        new_value="new",
    )
    desc = _describe_param_change(pc)

    assert expected_substr in desc


def test_breaking_prefix():
    pc = ParameterChange(parameter="x", change_type="removed", is_breaking=True)
    desc = _describe_param_change(pc)

    assert desc.startswith("⚠ ")


def test_no_changes():
    params = [ParameterInfo(name="x", annotation="int", default="0")]
    changes = _diff_parameters(params, list(params))

    assert changes == []


def test_diff_parameters_added():
    old = [ParameterInfo(name="x")]
    new = [ParameterInfo(name="x"), ParameterInfo(name="y", default="None")]
    changes = _diff_parameters(old, new)

    added = [c for c in changes if c.change_type == "added"]
    assert len(added) == 1
    assert added[0].parameter == "y"
    assert added[0].is_breaking is False  # has default


def test_added_no_default_is_breaking():
    old = [ParameterInfo(name="x")]
    new = [ParameterInfo(name="x"), ParameterInfo(name="y")]
    changes = _diff_parameters(old, new)

    added = [c for c in changes if c.change_type == "added"]
    assert added[0].is_breaking is True


def test_removed_is_breaking():
    old = [ParameterInfo(name="x"), ParameterInfo(name="y")]
    new = [ParameterInfo(name="x")]
    changes = _diff_parameters(old, new)

    removed = [c for c in changes if c.change_type == "removed"]
    assert len(removed) == 1
    assert removed[0].parameter == "y"
    assert removed[0].is_breaking is True


def test_retyped():
    old = [ParameterInfo(name="x", annotation="int")]
    new = [ParameterInfo(name="x", annotation="float")]
    changes = _diff_parameters(old, new)

    retyped = [c for c in changes if c.change_type == "retyped"]
    assert len(retyped) == 1
    assert retyped[0].old_value == "int"
    assert retyped[0].new_value == "float"


def test_default_changed():
    old = [ParameterInfo(name="x", default="0")]
    new = [ParameterInfo(name="x", default="1")]
    changes = _diff_parameters(old, new)

    dc = [c for c in changes if c.change_type == "default_changed"]
    assert len(dc) == 1


def test_kind_changed_is_breaking():
    old = [ParameterInfo(name="x", kind="POSITIONAL_OR_KEYWORD")]
    new = [ParameterInfo(name="x", kind="KEYWORD_ONLY")]
    changes = _diff_parameters(old, new)

    kc = [c for c in changes if c.change_type == "kind_changed"]
    assert len(kc) == 1
    assert kc[0].is_breaking is True


def test_reorder_is_breaking():
    old = [ParameterInfo(name="a"), ParameterInfo(name="b")]
    new = [ParameterInfo(name="b"), ParameterInfo(name="a")]
    changes = _diff_parameters(old, new)

    reorder = [c for c in changes if c.change_type == "reordered"]
    assert len(reorder) == 1
    assert reorder[0].is_breaking is True


def test_no_change():
    sym = SymbolInfo(name="foo", kind="function")
    result = _diff_symbol("foo", sym, sym)

    assert result is None


def test_kind_changed():
    old = SymbolInfo(name="foo", kind="function")
    new = SymbolInfo(name="foo", kind="class")
    result = _diff_symbol("foo", old, new)

    assert result is not None
    assert result.is_breaking is True
    assert "Kind changed" in result.details[0]


def test_async_changed():
    old = SymbolInfo(name="foo", kind="function", is_async=False)
    new = SymbolInfo(name="foo", kind="function", is_async=True)
    result = _diff_symbol("foo", old, new)

    assert result is not None
    assert result.is_breaking is True
    assert "async" in result.details[0].lower()


def test_return_type_changed():
    old = SymbolInfo(name="foo", kind="function", return_annotation="int")
    new = SymbolInfo(name="foo", kind="function", return_annotation="str")
    result = _diff_symbol("foo", old, new)

    assert result is not None
    assert "Return type" in result.details[0]


def test_base_removed_is_breaking():
    old = SymbolInfo(name="Foo", kind="class", bases=["Base"])
    new = SymbolInfo(name="Foo", kind="class", bases=[])
    result = _diff_symbol("Foo", old, new)

    assert result is not None
    assert result.is_breaking is True


def test_base_added():
    old = SymbolInfo(name="Foo", kind="class", bases=[])
    new = SymbolInfo(name="Foo", kind="class", bases=["Mixin"])
    result = _diff_symbol("Foo", old, new)

    assert result is not None
    assert "Added base" in result.details[0]


def test_decorator_changed():
    old = SymbolInfo(name="foo", kind="function", decorators=["staticmethod"])
    new = SymbolInfo(name="foo", kind="function", decorators=["classmethod"])
    result = _diff_symbol("foo", old, new)

    assert result is not None
    assert any("decorator" in d.lower() for d in result.details)


def test_parameter_changes_propagated():
    old = SymbolInfo(
        name="foo",
        kind="function",
        parameters=[ParameterInfo(name="x")],
    )
    new = SymbolInfo(name="foo", kind="function", parameters=[])
    result = _diff_symbol("foo", old, new)

    assert result is not None
    assert len(result.parameter_changes) > 0
    assert result.is_breaking is True


def _snap(version: str, symbols: dict[str, SymbolInfo]) -> ApiSnapshot:
    return ApiSnapshot(version=version, package_name="pkg", symbols=symbols)


def test_empty_to_empty():
    diff = diff_snapshots(_snap("v1", {}), _snap("v2", {}))

    assert diff.added == []
    assert diff.removed == []
    assert diff.changed == []


def test_diff_snapshots_added():
    new_symbols = {"foo": SymbolInfo(name="foo", kind="function")}
    diff = diff_snapshots(_snap("v1", {}), _snap("v2", new_symbols))

    assert len(diff.added) == 1
    assert diff.added[0].symbol == "foo"
    assert diff.added[0].change_type == "added"


def test_removed():
    old_symbols = {"foo": SymbolInfo(name="foo", kind="function")}
    diff = diff_snapshots(_snap("v1", old_symbols), _snap("v2", {}))

    assert len(diff.removed) == 1
    assert diff.removed[0].is_breaking is True


def test_changed():
    old_symbols = {"foo": SymbolInfo(name="foo", kind="function", return_annotation="int")}
    new_symbols = {"foo": SymbolInfo(name="foo", kind="function", return_annotation="str")}
    diff = diff_snapshots(_snap("v1", old_symbols), _snap("v2", new_symbols))

    assert len(diff.changed) == 1
    assert diff.changed[0].symbol == "foo"


def test_mixed():
    old_symbols = {
        "kept": SymbolInfo(name="kept", kind="function"),
        "removed_fn": SymbolInfo(name="removed_fn", kind="function"),
    }
    new_symbols = {
        "kept": SymbolInfo(name="kept", kind="function"),
        "new_fn": SymbolInfo(name="new_fn", kind="function"),
    }
    diff = diff_snapshots(_snap("v1", old_symbols), _snap("v2", new_symbols))

    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert len(diff.changed) == 0  # 'kept' is identical


def test_mermaid_empty():
    g = DependencyGraph()
    m = g.to_mermaid()

    assert m.startswith("graph TD")


def test_mermaid_with_nodes():
    g = DependencyGraph(
        nodes={"Foo": "class", "bar": "function"},
        inheritance=[InheritanceEdge(child="Foo", parent="bar")],
    )
    m = g.to_mermaid()

    assert "Foo" in m
    assert "bar" in m
    assert "-->" in m


def test_mermaid_call_edge():
    g = DependencyGraph(
        nodes={"fn_a": "function", "fn_b": "function"},
        calls=[CallEdge(caller="fn_a", callee="fn_b")],
    )
    m = g.to_mermaid()

    assert "-.->" in m


def test_inheritance_detected():
    snap = ApiSnapshot(
        version="v1",
        package_name="pkg",
        symbols={
            "Base": SymbolInfo(name="Base", kind="class"),
            "Child": SymbolInfo(name="Child", kind="class", bases=["Base"]),
        },
    )
    graph = build_dependency_graph(snap)

    assert len(graph.inheritance) == 1
    assert graph.inheritance[0].child == "Child"
    assert graph.inheritance[0].parent == "Base"


def test_external_base_excluded():
    snap = ApiSnapshot(
        version="v1",
        package_name="pkg",
        symbols={
            "MyError": SymbolInfo(name="MyError", kind="class", bases=["Exception"]),
        },
    )
    graph = build_dependency_graph(snap)

    # Exception is not in the snapshot, so no inheritance edge
    assert len(graph.inheritance) == 0


def test_all_symbols_become_nodes():
    snap = ApiSnapshot(
        version="v1",
        package_name="pkg",
        symbols={
            "Cls": SymbolInfo(name="Cls", kind="class"),
            "fn": SymbolInfo(name="fn", kind="function"),
        },
    )
    graph = build_dependency_graph(snap)

    assert "Cls" in graph.nodes
    assert "fn" in graph.nodes
    assert graph.nodes["Cls"] == "class"
    assert graph.nodes["fn"] == "function"


def test_basic():
    tl = [
        {"version": "v1.0", "symbols": 10, "classes": 3, "functions": 7},
        {"version": "v2.0", "symbols": 15, "classes": 5, "functions": 10},
    ]
    m = timeline_to_mermaid(tl)

    assert "xychart-beta" in m
    assert '"v1.0"' in m
    assert '"v2.0"' in m
    assert "10" in m
    assert "15" in m


def test_timeline_to_mermaid_empty():
    m = timeline_to_mermaid([])

    assert "xychart-beta" in m


@patch("great_docs._api_diff.subprocess.run")
def test_parses_tags(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="v0.1.0\nv0.2.0\nv1.0.0\nnot-a-version\nrelease-candidate\n",
    )
    tags = list_version_tags(Path("/fake"))

    assert tags == ["v0.1.0", "v0.2.0", "v1.0.0"]


@patch("great_docs._api_diff.subprocess.run")
def test_handles_no_v_prefix(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0\n2.0\n")
    tags = list_version_tags(Path("/fake"))

    assert tags == ["1.0.0", "2.0"]


@patch("great_docs._api_diff.subprocess.run")
def test_handles_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    tags = list_version_tags(Path("/fake"))

    assert tags == []


@patch("great_docs._api_diff.subprocess.run")
def test_handles_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
    tags = list_version_tags(Path("/fake"))

    assert tags == []


def test_detects_from_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent("""\
            [project]
            name = "my-package"
        """)
    )
    result = _detect_package_name(tmp_path)

    assert result == "my_package"


def test_no_pyproject(tmp_path):
    result = _detect_package_name(tmp_path)

    assert result is None


def test_malformed_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("not valid toml [[")
    result = _detect_package_name(tmp_path)

    assert result is None


def test_snapshot_of_real_package():
    """Snapshot the great_docs package itself as a smoke test."""
    snap = snapshot_from_griffe("great_docs", version="test")

    assert snap.version == "test"
    assert snap.package_name == "great_docs"
    assert snap.symbol_count > 0
    # Known exports
    assert "GreatDocs" in snap.symbols or "Config" in snap.symbols


def test_snapshot_includes_parameters():
    snap = snapshot_from_griffe("great_docs", version="test")

    # Find a function or class with parameters
    has_params = any(
        len(info.parameters) > 0
        for info in snap.symbols.values()
        if info.kind in ("function", "class")
    )
    assert has_params


def test_snapshot_nonexistent_package():
    with pytest.raises(Exception):
        snapshot_from_griffe("nonexistent_pkg_abc123", version="test")


def test_simple_function():
    info = SymbolInfo(name="foo", kind="function")

    assert format_signature(info) == "def foo()"


def test_function_with_params():
    info = SymbolInfo(
        name="bar",
        kind="function",
        parameters=[
            ParameterInfo(name="x", annotation="int"),
            ParameterInfo(name="y", annotation="str", default="'hello'"),
        ],
        return_annotation="bool",
    )
    sig = format_signature(info)

    assert sig == "def bar(x: int, y: str = 'hello') -> bool"


def test_async_function():
    info = SymbolInfo(name="fetch", kind="function", is_async=True)

    assert format_signature(info) == "async def fetch()"


def test_class():
    info = SymbolInfo(
        name="MyClass",
        kind="class",
        parameters=[ParameterInfo(name="config", annotation="dict")],
        bases=["Base"],
    )
    sig = format_signature(info)

    assert sig == "class MyClass(Base)(config: dict)"


def test_class_no_bases():
    info = SymbolInfo(name="Simple", kind="class")

    assert format_signature(info) == "class Simple()"


def test_attribute():
    info = SymbolInfo(name="VERSION", kind="attribute", return_annotation="str")

    assert format_signature(info) == "VERSION: str"


def test_attribute_no_annotation():
    info = SymbolInfo(name="FLAG", kind="attribute")

    assert format_signature(info) == "FLAG"


def test_module():
    info = SymbolInfo(name="submod", kind="module")

    assert format_signature(info) == "submod"


def _entry(
    version: str,
    present: bool = True,
    sig: str | None = "def foo()",
    change: SymbolChange | None = None,
) -> SymbolHistoryEntry:
    return SymbolHistoryEntry(
        version=version,
        present=present,
        signature=sig if present else None,
        symbol_info=SymbolInfo(name="foo", kind="function") if present else None,
        change=change,
    )


def test_changed_entries_first_present():
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[
            _entry("v1"),
            _entry("v2"),
            _entry("v3"),
        ],
    )
    changed = hist.changed_entries

    # Only the first entry (first appearance) should be included
    assert len(changed) == 1
    assert changed[0].version == "v1"


def test_changed_entries_with_change():
    diff_change = SymbolChange(symbol="foo", change_type="changed", details=["retyped"])
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[
            _entry("v1"),
            _entry("v2", change=diff_change),
            _entry("v3"),
        ],
    )
    changed = hist.changed_entries

    assert len(changed) == 2
    assert changed[0].version == "v1"
    assert changed[1].version == "v2"


def test_changed_entries_removal():
    removal = SymbolChange(symbol="foo", change_type="removed", is_breaking=True)
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[
            _entry("v1"),
            _entry("v2", present=False, sig=None, change=removal),
        ],
    )
    changed = hist.changed_entries

    assert len(changed) == 2
    assert changed[1].present is False


def test_changed_entries_reappearance():
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[
            _entry("v1"),
            _entry("v2", present=False, sig=None),
            _entry("v3"),  # reappeared
        ],
    )
    changed = hist.changed_entries

    # v1 (first), v2 (disappeared), v3 (reappeared)
    assert len(changed) == 3


def test_to_dict_all():
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[_entry("v1"), _entry("v2")],
    )
    d = hist.to_dict()

    assert d["symbol"] == "foo"
    assert d["package"] == "pkg"
    assert len(d["versions"]) == 2


def test_to_dict_changes_only():
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[_entry("v1"), _entry("v2"), _entry("v3")],
    )
    d = hist.to_dict(changes_only=True)

    # Only v1 (first appearance) should be in the output
    assert len(d["versions"]) == 1
    assert d["versions"][0]["version"] == "v1"


def test_symbol_history_to_dict_roundtrip_json():
    hist = SymbolHistory(
        symbol_name="foo",
        package_name="pkg",
        entries=[_entry("v1")],
    )
    serialized = json.dumps(hist.to_dict())
    loaded = json.loads(serialized)

    assert loaded["symbol"] == "foo"


@patch("great_docs._api_diff.list_version_tags")
@patch("great_docs._api_diff.snapshot_at_tag")
def test_tracks_across_versions(mock_snap, mock_tags):
    mock_tags.return_value = ["v1", "v2", "v3"]

    def make_snap(root, tag, pkg):
        sym_v1 = SymbolInfo(
            name="foo",
            kind="function",
            parameters=[ParameterInfo(name="x", annotation="int")],
        )
        sym_v2 = SymbolInfo(
            name="foo",
            kind="function",
            parameters=[
                ParameterInfo(name="x", annotation="int"),
                ParameterInfo(name="y", annotation="str", default="None"),
            ],
        )
        syms = {
            "v1": {"foo": sym_v1},
            "v2": {"foo": sym_v2},
            "v3": {"foo": sym_v2},
        }
        return ApiSnapshot(version=tag, package_name="pkg", symbols=syms.get(tag, {}))

    mock_snap.side_effect = make_snap

    hist = symbol_history(Path("/fake"), "foo", package_name="pkg")

    assert hist is not None
    assert len(hist.entries) == 3
    assert hist.entries[0].present is True
    assert hist.entries[1].change is not None  # parameter added
    assert hist.entries[2].change is None  # unchanged from v2


@patch("great_docs._api_diff.list_version_tags")
@patch("great_docs._api_diff.snapshot_at_tag")
def test_symbol_not_present(mock_snap, mock_tags):
    mock_tags.return_value = ["v1", "v2"]

    def make_snap(root, tag, pkg):
        return ApiSnapshot(version=tag, package_name="pkg", symbols={})

    mock_snap.side_effect = make_snap

    hist = symbol_history(Path("/fake"), "missing", package_name="pkg")

    assert hist is not None
    assert all(not e.present for e in hist.entries)


@patch("great_docs._api_diff.list_version_tags")
@patch("great_docs._api_diff.snapshot_at_tag")
def test_symbol_added_later(mock_snap, mock_tags):
    mock_tags.return_value = ["v1", "v2"]

    def make_snap(root, tag, pkg):
        if tag == "v2":
            return ApiSnapshot(
                version=tag,
                package_name="pkg",
                symbols={"foo": SymbolInfo(name="foo", kind="function")},
            )
        return ApiSnapshot(version=tag, package_name="pkg", symbols={})

    mock_snap.side_effect = make_snap

    hist = symbol_history(Path("/fake"), "foo", package_name="pkg")

    assert hist is not None
    assert hist.entries[0].present is False
    assert hist.entries[1].present is True
    assert hist.entries[1].change is not None
    assert hist.entries[1].change.change_type == "added"


@patch("great_docs._api_diff.list_version_tags")
@patch("great_docs._api_diff.snapshot_at_tag")
def test_symbol_removed(mock_snap, mock_tags):
    mock_tags.return_value = ["v1", "v2"]

    def make_snap(root, tag, pkg):
        if tag == "v1":
            return ApiSnapshot(
                version=tag,
                package_name="pkg",
                symbols={"foo": SymbolInfo(name="foo", kind="function")},
            )
        return ApiSnapshot(version=tag, package_name="pkg", symbols={})

    mock_snap.side_effect = make_snap

    hist = symbol_history(Path("/fake"), "foo", package_name="pkg")

    assert hist is not None
    assert hist.entries[0].present is True
    assert hist.entries[1].present is False
    assert hist.entries[1].change is not None
    assert hist.entries[1].change.change_type == "removed"
    assert hist.entries[1].change.is_breaking is True


def test_returns_none_without_package(tmp_path):
    result = symbol_history(tmp_path, "foo")

    assert result is None


def test_help_text():
    from click.testing import CliRunner

    from great_docs.cli import api_diff_cmd

    runner = CliRunner()
    result = runner.invoke(api_diff_cmd, ["--help"])

    assert result.exit_code == 0
    assert "Compare the public API" in result.output
    assert "OLD_VERSION" in result.output
    assert "NEW_VERSION" in result.output
    assert "--json" in result.output
    assert "--graph" in result.output
    assert "--timeline" in result.output
    assert "--symbol" in result.output
    assert "--changes-only" in result.output


def test_registered_in_cli():
    from great_docs.cli import cli

    # The command should be registered under the name "api-diff"
    assert "api-diff" in cli.commands


def test_help_includes_table_html():
    from click.testing import CliRunner

    from great_docs.cli import api_diff_cmd

    runner = CliRunner()
    result = runner.invoke(api_diff_cmd, ["--help"])

    assert "--table" in result.output
    assert "--html" in result.output


def _make_history() -> SymbolHistory:
    """A small 3-version history with parameter changes."""
    sym_v1 = SymbolInfo(
        name="build",
        kind="function",
        parameters=[
            ParameterInfo(name="src", annotation="str"),
            ParameterInfo(name="verbose", annotation="bool", default="False"),
        ],
        return_annotation="None",
    )
    sym_v2 = SymbolInfo(
        name="build",
        kind="function",
        parameters=[
            ParameterInfo(name="src", annotation="Path"),
            ParameterInfo(name="verbose", annotation="bool", default="False"),
            ParameterInfo(name="watch", annotation="bool", default="False"),
        ],
        return_annotation="None",
    )
    sym_v3 = SymbolInfo(
        name="build",
        kind="function",
        parameters=[
            ParameterInfo(name="src", annotation="Path"),
            ParameterInfo(name="watch", annotation="bool", default="True"),
        ],
        return_annotation="int",
    )

    return SymbolHistory(
        symbol_name="build",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature=format_signature(sym_v1),
                symbol_info=sym_v1,
                change=None,
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=True,
                signature=format_signature(sym_v2),
                symbol_info=sym_v2,
                change=SymbolChange(symbol="build", change_type="changed"),
            ),
            SymbolHistoryEntry(
                version="v3.0",
                present=True,
                signature=format_signature(sym_v3),
                symbol_info=sym_v3,
                change=SymbolChange(symbol="build", change_type="changed"),
            ),
        ],
    )


def test_rows_structure():
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Header + 3 param slots (max params across versions) + return row
    assert len(rows) == 5
    # Header has 3 version columns
    assert [v for _, v in rows[0]] == ["v1.0", "v2.0", "v3.0"]


def test_positional_layout():
    """Each row is a positional slot, not a named parameter."""
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Slot 0: src in all versions that have it
    slot0 = rows[1]
    assert slot0[0][0] == "src"  # v1.0 param name
    assert slot0[1][0] == "src"  # v2.0 param name
    assert slot0[2][0] == "src"  # v3.0 param name


def test_parameter_name_in_cell():
    """Each cell contains the parameter name, not just type info."""
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Slot 1: verbose in v1/v2, watch in v3
    slot1 = rows[2]
    assert slot1[0][0] == "verbose"  # v1.0
    assert slot1[1][0] == "verbose"  # v2.0
    assert slot1[2][0] == "watch"  # v3.0 — different param at position 1


def test_type_and_default_in_cell():
    """Line 2 of each cell shows type = default."""
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Slot 1, v1.0 = verbose: bool = False
    slot1_v1 = rows[2][0]
    assert slot1_v1 == ("verbose", "bool = False")


def test_absent_slot_shows_dash():
    """Slots beyond a version's param count show em-dash."""
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Slot 2 (3rd param): only v2.0 has 3 params
    slot2 = rows[3]
    assert slot2[0] == ("\u2014", "")  # v1.0 — only 2 params
    assert slot2[1][0] == "watch"  # v2.0 — has 3rd param
    assert slot2[2] == ("\u2014", "")  # v3.0 — only 2 params


def test_return_row():
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    ret_row = rows[-1]
    assert ret_row[0] == ("Returns:", "None")  # v1.0
    assert ret_row[2] == ("Returns:", "int")  # v3.0


def test_changes_only_filters():
    hist = _make_history()
    rows_all = evolution_table(hist, changes_only=False)
    rows_changed = evolution_table(hist, changes_only=True)

    # All 3 versions vs. changed only (v1.0 = first, v2.0 + v3.0 = changed)
    assert len(rows_all[0]) == 3  # 3 version columns
    assert len(rows_changed[0]) == 3  # all 3 had changes


def test_evolution_table_empty_history():
    hist = SymbolHistory(symbol_name="x", package_name="pkg")
    rows = evolution_table(hist)

    assert rows == []


def test_no_params_no_return():
    """Symbol with no parameters and no return type."""
    sym = SymbolInfo(name="noop", kind="function")
    hist = SymbolHistory(
        symbol_name="noop",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def noop()",
                symbol_info=sym,
            )
        ],
    )
    rows = evolution_table(hist, changes_only=False)

    # Header only — no param slots, no return row
    assert len(rows) == 1
    assert rows[0] == [("", "v1")]


def test_type_only_no_default():
    """Cell with type annotation but no default."""
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    # Slot 0, v1.0 = src: str (no default)
    slot0_v1 = rows[1][0]
    assert slot0_v1 == ("src", "str")


def test_contains_header_separator():
    hist = _make_history()
    text = evolution_table_text(hist, changes_only=False)

    lines = text.split("\n")
    assert len(lines) > 2
    # Second line should be a separator (dashes and box-drawing chars)
    assert "\u2500" in lines[1]


def test_version_labels_in_header():
    hist = _make_history()
    text = evolution_table_text(hist, changes_only=False)

    lines = text.split("\n")
    assert "v1.0" in lines[0]
    assert "v2.0" in lines[0]
    assert "v3.0" in lines[0]


def test_two_line_cells():
    """Each parameter slot produces two text lines."""
    hist = _make_history()
    text = evolution_table_text(hist, changes_only=False)

    # The param name and type line should both appear
    assert "verbose" in text
    assert "bool = False" in text


def test_evolution_table_text_empty():
    hist = SymbolHistory(symbol_name="x", package_name="pkg")

    assert evolution_table_text(hist) == "(no data)"


def test_produces_table():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False)

    assert "<table" in html
    assert "</table>" in html
    assert "gd-evolution-table" in html


def test_header_cells():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False)

    assert "<th>v1.0</th>" in html
    assert "<th>v2.0</th>" in html
    assert "<th>v3.0</th>" in html


def test_name_and_type_spans():
    """Each cell has separate spans for name and type."""
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False)

    assert 'class="gd-evo-name"' in html
    assert 'class="gd-evo-type"' in html


def test_absent_class():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False)

    assert 'class="gd-evo-absent"' in html


def test_disclosure_wrapping():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False, disclosure=True)

    assert "<details" in html
    assert "<summary>" in html
    assert "Signature evolution for build" in html
    assert "</details>" in html


def test_evolution_table_html_custom_summary():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False, disclosure=True, summary_text="History")

    assert "<summary>History</summary>" in html


def test_evolution_table_html_empty():
    hist = SymbolHistory(symbol_name="x", package_name="pkg")
    html = evolution_table_html(hist)

    assert "no evolution data" in html


def test_html_escaping():
    sym = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[
            ParameterInfo(name="x", annotation="dict<str, int>"),
        ],
    )
    hist = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def fn(x: dict<str, int>)",
                symbol_info=sym,
            )
        ],
    )
    html = evolution_table_html(hist, changes_only=False)

    assert "<str" not in html  # angle brackets must be escaped
    assert "&lt;str" in html


def test_ampersand():
    assert _escape_html("a & b") == "a &amp; b"


def test_angle_brackets():
    assert _escape_html("<div>") == "&lt;div&gt;"


def test_quotes():
    assert _escape_html('x="y"') == "x=&quot;y&quot;"


def test_escape_html_plain():
    assert _escape_html("hello") == "hello"


def test_structure():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    assert d["symbol"] == "build"
    assert d["package"] == "pkg"
    assert d["versions"] == ["v1.0", "v2.0", "v3.0"]
    assert isinstance(d["slots"], list)


def test_slot_positions():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    for i, slot in enumerate(d["slots"]):
        assert slot["position"] == i


def test_cells_parallel_to_versions():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    for slot in d["slots"]:
        assert len(slot["cells"]) == len(d["versions"])


def test_cell_content():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    # Slot 0 = src in all versions
    slot0 = d["slots"][0]
    assert slot0["cells"][0]["name"] == "src"
    assert slot0["cells"][0]["type"] == "str"
    assert slot0["cells"][0]["default"] is None


def test_null_cell_for_absent_slot():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    # Slot 2 (3rd param) — doesn't exist in v1.0 or v3.0
    slot2 = d["slots"][2]
    assert slot2["cells"][0] is None  # v1.0
    assert slot2["cells"][1] is not None  # v2.0
    assert slot2["cells"][2] is None  # v3.0


def test_cell_with_default():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    # Slot 1 = verbose in v1.0 with default
    slot1 = d["slots"][1]
    assert slot1["cells"][0]["name"] == "verbose"
    assert slot1["cells"][0]["type"] == "bool"
    assert slot1["cells"][0]["default"] == "False"


def test_returns():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    assert "returns" in d
    assert d["returns"][0] == "None"
    assert d["returns"][2] == "int"


def test_evolution_table_to_dict_empty_history():
    hist = SymbolHistory(symbol_name="x", package_name="pkg")
    d = evolution_table_to_dict(hist)

    assert d["versions"] == []
    assert d["slots"] == []


def test_no_return_type_omitted():
    """When no version has a return annotation, 'returns' key is absent."""
    sym = SymbolInfo(
        name="noop",
        kind="function",
        parameters=[ParameterInfo(name="x")],
    )
    hist = SymbolHistory(
        symbol_name="noop",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def noop(x)",
                symbol_info=sym,
            )
        ],
    )
    d = evolution_table_to_dict(hist, changes_only=False)

    assert "returns" not in d


def test_roundtrip_json():
    hist = _make_history()
    d = evolution_table_to_dict(hist, changes_only=False)
    serialized = json.dumps(d)
    loaded = json.loads(serialized)

    assert loaded["symbol"] == "build"
    assert len(loaded["slots"]) == len(d["slots"])


def test_matches_demo_json_structure():
    """Verify our output matches the documented JSON spec."""
    demo_path = Path(__file__).parent.parent / "great_docs" / "assets" / "api-evolution-demo.json"
    demo = json.loads(demo_path.read_text())

    # Check the demo file follows the spec
    assert "symbol" in demo
    assert "package" in demo
    assert "versions" in demo
    assert "slots" in demo
    assert isinstance(demo["slots"], list)
    for slot in demo["slots"]:
        assert "position" in slot
        assert "cells" in slot or "separator" in slot
        if "cells" in slot:
            assert len(slot["cells"]) == len(demo["versions"])
            for cell in slot["cells"]:
                if cell is not None:
                    assert "name" in cell
                    assert "type" in cell
                    assert "default" in cell


def test_no_keyword_only():
    """Params with no KEYWORD_ONLY kind are returned unchanged."""
    params = [
        ParameterInfo(name="a", kind="POSITIONAL_OR_KEYWORD"),
        ParameterInfo(name="b", kind="POSITIONAL_OR_KEYWORD"),
    ]
    assert _augment_params_with_separators(params) is params


def test_inserts_star():
    """A '*' entry is inserted before the first KEYWORD_ONLY param."""
    params = [
        ParameterInfo(name="a", kind="POSITIONAL_OR_KEYWORD"),
        ParameterInfo(name="b", kind="KEYWORD_ONLY"),
        ParameterInfo(name="c", kind="KEYWORD_ONLY"),
    ]
    result = _augment_params_with_separators(params)
    assert len(result) == 4
    assert result[1].name == "*"
    assert result[1].kind == "KEYWORD_ONLY_SEPARATOR"
    assert result[2].name == "b"
    assert result[3].name == "c"


def test_no_star_when_var_positional():
    """*args already serves as the separator — no extra '*' inserted."""
    params = [
        ParameterInfo(name="a", kind="POSITIONAL_OR_KEYWORD"),
        ParameterInfo(name="args", kind="VAR_POSITIONAL"),
        ParameterInfo(name="b", kind="KEYWORD_ONLY"),
    ]
    assert _augment_params_with_separators(params) is params


def test_all_keyword_only():
    """'*' is inserted at position 0 when all params are keyword-only."""
    params = [
        ParameterInfo(name="x", kind="KEYWORD_ONLY"),
    ]
    result = _augment_params_with_separators(params)
    assert len(result) == 2
    assert result[0].name == "*"
    assert result[1].name == "x"


def test_empty_list():
    result = _augment_params_with_separators([])
    assert result == []


def _make_kw_history():
    """Build a 2-version history where v2 introduces keyword-only params."""
    sym_v1 = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[
            ParameterInfo(name="a", annotation="int", kind="POSITIONAL_OR_KEYWORD"),
            ParameterInfo(name="b", annotation="str", kind="POSITIONAL_OR_KEYWORD"),
        ],
    )
    sym_v2 = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[
            ParameterInfo(name="a", annotation="int", kind="POSITIONAL_OR_KEYWORD"),
            ParameterInfo(name="b", annotation="str", kind="KEYWORD_ONLY"),
            ParameterInfo(name="c", annotation="bool", kind="KEYWORD_ONLY"),
        ],
    )
    return SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1", present=True, signature="def fn(a, b)", symbol_info=sym_v1
            ),
            SymbolHistoryEntry(
                version="v2",
                present=True,
                signature="def fn(a, *, b, c)",
                symbol_info=sym_v2,
                change=SymbolChange(symbol="fn", change_type="changed"),
            ),
        ],
    )


def test_star_row_in_table():
    hist = _make_kw_history()
    rows = evolution_table(hist, changes_only=False)

    # v1 has 2 params, v2 has 3 + star = 4, so max_params=4
    # Row structure: header, slot0, slot1(star in v2), slot2, slot3
    star_cells = [cell for row in rows[1:] for cell in row if cell[0] == "*"]
    assert len(star_cells) > 0
    assert star_cells[0] == ("*", "")


def test_star_separator_in_html():
    hist = _make_kw_history()
    html = evolution_table_html(hist, changes_only=False)

    assert 'class="gd-evo-separator"' in html
    assert ">*</td>" in html


def test_star_in_dict():
    hist = _make_kw_history()
    d = evolution_table_to_dict(hist, changes_only=False)

    separators = [s for s in d["slots"] if "separator" in s]
    assert len(separators) == 1
    assert separators[0]["separator"] == "*"


def test_returns_label_in_table():
    hist = _make_history()
    rows = evolution_table(hist, changes_only=False)

    ret_row = rows[-1]
    for label, _ in ret_row:
        assert label == "Returns:"


def test_returns_label_in_html():
    hist = _make_history()
    html = evolution_table_html(hist, changes_only=False)

    assert 'class="gd-evo-return-label"' in html
    assert ">Returns:</span>" in html
    # Old label should NOT appear
    assert "(return)" not in html


def test_date_in_history_entry():
    entry = SymbolHistoryEntry(version="v1", present=True, date="2024-06-15")
    assert entry.date == "2024-06-15"


def test_date_tooltip_in_html():
    sym = SymbolInfo(name="fn", kind="function", parameters=[])
    hist = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
                date="2024-01-15",
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
                date="2024-06-20",
                change=SymbolChange(symbol="fn", change_type="changed"),
            ),
        ],
    )
    html = evolution_table_html(hist, changes_only=False)

    assert 'title="2024-01-15"' in html
    assert 'title="2024-06-20"' in html


def test_no_tooltip_when_no_date():
    sym = SymbolInfo(name="fn", kind="function", parameters=[])
    hist = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(version="v1", present=True, signature="def fn()", symbol_info=sym),
        ],
    )
    html = evolution_table_html(hist, changes_only=False)

    assert "title=" not in html


def test_no_bounds():
    tags = ["v1", "v2", "v3"]
    assert _filter_tag_range(tags, None, None) is tags


def test_old_only():
    tags = ["v1", "v2", "v3", "v4"]
    assert _filter_tag_range(tags, "v2", None) == ["v2", "v3", "v4"]


def test_new_only():
    tags = ["v1", "v2", "v3", "v4"]
    assert _filter_tag_range(tags, None, "v3") == ["v1", "v2", "v3"]


def test_both_bounds():
    tags = ["v1", "v2", "v3", "v4"]
    assert _filter_tag_range(tags, "v2", "v3") == ["v2", "v3"]


def test_missing_old_returns_all():
    tags = ["v1", "v2"]
    assert _filter_tag_range(tags, "v99", None) == ["v1", "v2"]


def test_missing_new_returns_all():
    tags = ["v1", "v2"]
    assert _filter_tag_range(tags, None, "v99") == ["v1", "v2"]


@patch("great_docs._api_diff.list_version_tags")
def test_no_tags(mock_tags):
    mock_tags.return_value = []
    result = render_evolution_table("/fake", "build")

    assert "no version tags" in result
    assert result.startswith("<!--")


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags")
def test_no_history(mock_tags, mock_hist):
    mock_tags.return_value = ["v1", "v2"]
    mock_hist.return_value = None
    result = render_evolution_table("/fake", "build")

    assert "no evolution data" in result


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags")
def test_returns_css_and_table(mock_tags, mock_hist):
    mock_tags.return_value = ["v1", "v2"]
    sym = SymbolInfo(
        name="build",
        kind="function",
        parameters=[
            ParameterInfo(name="src", annotation="str"),
        ],
        return_annotation="None",
    )
    mock_hist.return_value = SymbolHistory(
        symbol_name="build",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def build(src: str) -> None",
                symbol_info=sym,
            ),
        ],
    )
    result = render_evolution_table("/fake", "build")

    assert "<style>" in result
    assert "gd-evolution-table" in result
    assert "<table" in result
    assert "<details" not in result  # disclosure=False by default


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags")
def test_include_css_false(mock_tags, mock_hist):
    mock_tags.return_value = ["v1"]
    sym = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[ParameterInfo(name="x")],
    )
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
            ),
        ],
    )
    result = render_evolution_table("/fake", "fn", include_css=False)

    assert "<style>" not in result
    assert "<table" in result or "<details" in result


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags")
def test_disclosure_false(mock_tags, mock_hist):
    mock_tags.return_value = ["v1"]
    sym = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[ParameterInfo(name="x")],
    )
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
            ),
        ],
    )
    result = render_evolution_table("/fake", "fn", disclosure=False)

    assert "<details" not in result
    assert "<table" in result


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags")
def test_tag_range_filtering(mock_tags, mock_hist):
    mock_tags.return_value = ["v1", "v2", "v3", "v4"]
    sym = SymbolInfo(
        name="fn",
        kind="function",
        parameters=[ParameterInfo(name="x")],
    )
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v2",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
            ),
        ],
    )
    render_evolution_table("/fake", "fn", old_version="v2", new_version="v3")

    # symbol_history should have been called with filtered tags
    _, kwargs = mock_hist.call_args
    assert kwargs["tags"] == ["v2", "v3"]


def test_css_constant_has_all_classes():
    """The embedded CSS block covers all classes used by the renderer."""
    for cls in (
        "gd-evolution-table",
        "gd-evo-name",
        "gd-evo-type",
        "gd-evo-absent",
        "gd-evo-separator",
        "gd-evo-return-label",
        "gd-evolution-disclosure",
    ):
        assert cls in _EVOLUTION_TABLE_CSS, f"{cls} missing from CSS"


def test_double_quoted():
    assert _parse_marker_attrs('symbol="build"') == {"symbol": "build"}


def test_single_quoted():
    assert _parse_marker_attrs("symbol='build'") == {"symbol": "build"}


def test_unquoted():
    assert _parse_marker_attrs("symbol=build") == {"symbol": "build"}


def test_multiple():
    result = _parse_marker_attrs('symbol="build" old_version="v1.0" changes_only="false"')
    assert result == {
        "symbol": "build",
        "old_version": "v1.0",
        "changes_only": "false",
    }


def test_parse_marker_attrs_empty():
    assert _parse_marker_attrs("") == {}


def test_whitespace_around_equals():
    assert _parse_marker_attrs('symbol = "build"') == {"symbol": "build"}


@patch("great_docs._api_diff.render_evolution_table")
def test_replaces_marker(mock_render):
    mock_render.return_value = "<table>mock</table>"
    content = 'Before\n<!-- %evolution symbol="build" -->\nAfter'
    result = process_evolution_markers(content, "/fake")

    assert "<table>mock</table>" in result
    assert "Before" in result
    assert "After" in result
    assert "<!-- %evolution" not in result


@patch("great_docs._api_diff.render_evolution_table")
def test_passes_attributes(mock_render):
    mock_render.return_value = "<table/>"
    content = '<!-- %evolution symbol="build" old_version="v1" new_version="v2" changes_only="false" disclosure="false" css="false" -->'
    process_evolution_markers(content, "/fake")

    _, kwargs = mock_render.call_args
    assert kwargs["old_version"] == "v1"
    assert kwargs["new_version"] == "v2"
    assert kwargs["changes_only"] is False
    assert kwargs["disclosure"] is False
    assert kwargs["include_css"] is False


def test_missing_symbol_gives_error():
    content = '<!-- %evolution old_version="v1" -->'
    result = process_evolution_markers(content, "/fake")

    assert "missing symbol" in result
    assert result.startswith("<!--")


@patch("great_docs._api_diff.render_evolution_table")
def test_multiple_markers(mock_render):
    mock_render.side_effect = ["<table>A</table>", "<table>B</table>"]
    content = '<!-- %evolution symbol="foo" -->\n<!-- %evolution symbol="bar" -->'
    result = process_evolution_markers(content, "/fake")

    assert "<table>A</table>" in result
    assert "<table>B</table>" in result
    assert mock_render.call_count == 2


@patch("great_docs._api_diff.render_evolution_table")
def test_no_markers_returns_unchanged(mock_render):
    content = "No markers here."
    result = process_evolution_markers(content, "/fake")

    assert result == content
    mock_render.assert_not_called()


@patch("great_docs._api_diff.render_evolution_table")
def test_exception_gives_error_comment(mock_render):
    mock_render.side_effect = RuntimeError("boom")
    content = '<!-- %evolution symbol="build" -->'
    result = process_evolution_markers(content, "/fake")

    assert "error for build" in result
    assert "boom" in result
    assert result.startswith("<!--")


@patch("great_docs._api_diff.render_evolution_table")
def test_summary_attr(mock_render):
    mock_render.return_value = "<table/>"
    content = '<!-- %evolution symbol="build" summary="Build history" -->'
    process_evolution_markers(content, "/fake")

    _, kwargs = mock_render.call_args
    assert kwargs["summary_text"] == "Build history"


@patch("great_docs._api_diff.render_evolution_table")
def test_package_attr_overrides_argument(mock_render):
    mock_render.return_value = "<table/>"
    content = '<!-- %evolution symbol="fn" package="other_pkg" -->'
    process_evolution_markers(content, "/fake", package="default_pkg")

    _, kwargs = mock_render.call_args
    assert kwargs["package"] == "other_pkg"


@patch("great_docs._api_diff.render_evolution_table")
def test_reads_and_processes(mock_render, tmp_path):
    mock_render.return_value = "<table>result</table>"
    qmd = tmp_path / "test.qmd"
    qmd.write_text('# Title\n<!-- %evolution symbol="build" -->\n')

    result = process_evolution_markers_in_file(qmd, "/fake")

    assert "<table>result</table>" in result
    # File should NOT be modified (in_place=False)
    assert "<!-- %evolution" in qmd.read_text()


@patch("great_docs._api_diff.render_evolution_table")
def test_in_place(mock_render, tmp_path):
    mock_render.return_value = "<table>replaced</table>"
    qmd = tmp_path / "test.qmd"
    qmd.write_text('# Title\n<!-- %evolution symbol="build" -->\n')

    process_evolution_markers_in_file(qmd, "/fake", in_place=True)

    written = qmd.read_text()
    assert "<table>replaced</table>" in written
    assert "<!-- %evolution symbol" not in written


@patch("great_docs._api_diff.render_evolution_table")
def test_no_markers_skips_write(mock_render, tmp_path):
    qmd = tmp_path / "test.qmd"
    qmd.write_text("No markers.")
    original_mtime = qmd.stat().st_mtime

    process_evolution_markers_in_file(qmd, "/fake", in_place=True)

    # File unchanged — should not be rewritten
    assert qmd.stat().st_mtime == original_mtime
    mock_render.assert_not_called()


def _ext_dir():
    return Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "evolution"


def test_extension_yml_exists():
    assert (_ext_dir() / "_extension.yml").exists()


def test_lua_filter_exists():
    assert (_ext_dir() / "evolution.lua").exists()


def test_python_bridge_exists():
    assert (_ext_dir() / "_evolution_shortcode.py").exists()


def test_extension_yml_declares_shortcode():
    import yaml

    ext_yml = _ext_dir() / "_extension.yml"
    with open(ext_yml) as f:
        data = yaml.safe_load(f)
    assert "contributes" in data
    assert "shortcodes" in data["contributes"]
    assert "evolution.lua" in data["contributes"]["shortcodes"]


def test_lua_defines_evolution_function():
    lua_src = (_ext_dir() / "evolution.lua").read_text()
    # Must return a table with an "evolution" key
    assert '["evolution"]' in lua_src
    assert "function(args, kwargs)" in lua_src


def test_python_bridge_parses_args():
    """The bridge script can parse its arguments without errors."""
    import subprocess
    import sys

    bridge = _ext_dir() / "_evolution_shortcode.py"
    # --help should succeed (validates argparse setup)
    result = subprocess.run(
        [sys.executable, str(bridge), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "symbol" in result.stdout.lower()


def _base_data() -> dict:
    return {
        "symbol": "build",
        "versions": ["v1.0", "v2.0"],
        "slots": [
            {
                "position": 0,
                "cells": [
                    {"name": "path", "type": "str", "default": None},
                    {"name": "path", "type": "str | Path", "default": None},
                ],
            },
        ],
    }


def test_basic_rendering():
    html = render_evolution_table_from_dict(_base_data())
    assert "gd-evolution-table" in html
    assert "v1.0" in html
    assert "v2.0" in html
    assert "path" in html


def test_empty_versions_returns_comment():
    data = {"symbol": "build", "versions": []}
    result = render_evolution_table_from_dict(data)
    assert result == "<!-- no evolution data -->"


def test_missing_versions_key():
    data = {"symbol": "build"}
    result = render_evolution_table_from_dict(data)
    assert result == "<!-- no evolution data -->"


def test_includes_css_by_default():
    html = render_evolution_table_from_dict(_base_data())
    assert "gd-evolution-table" in html
    assert "<style>" in html


def test_css_excluded():
    html = render_evolution_table_from_dict(_base_data(), include_css=False)
    assert "<style>" not in html
    assert "gd-evolution-table" in html


def test_disclosure_wrapper():
    html = render_evolution_table_from_dict(_base_data(), disclosure=True)
    assert "<details" in html
    assert "<summary>" in html


def test_no_disclosure():
    html = render_evolution_table_from_dict(_base_data())
    assert "<details" not in html


def test_render_from_dict_custom_summary():
    html = render_evolution_table_from_dict(_base_data(), disclosure=True, summary_text="My Title")
    assert "My Title" in html


def test_null_cells_render_absent():
    data = {
        "symbol": "f",
        "versions": ["v1", "v2"],
        "slots": [
            {"position": 0, "cells": [{"name": "x", "type": "int", "default": None}, None]},
        ],
    }
    html = render_evolution_table_from_dict(data)
    assert "gd-evo-absent" in html
    assert "\u2014" in html


def test_separator_slot():
    data = {
        "symbol": "f",
        "versions": ["v1", "v2"],
        "slots": [
            {
                "position": 0,
                "cells": [
                    {"name": "x", "type": "int", "default": None},
                    {"name": "x", "type": "int", "default": None},
                ],
            },
            {"position": 1, "separator": "*"},
        ],
    }
    html = render_evolution_table_from_dict(data)
    assert "gd-evo-separator" in html


def test_returns_row():
    data = _base_data()
    data["returns"] = ["None", "int"]
    html = render_evolution_table_from_dict(data)
    assert "gd-evo-return-label" in html
    assert "Returns:" in html
    assert "int" in html


def test_dates_as_tooltips():
    data = _base_data()
    data["dates"] = ["2024-01-01", "2024-06-15"]
    html = render_evolution_table_from_dict(data)
    assert 'title="2024-01-01"' in html
    assert 'title="2024-06-15"' in html


def test_dates_partial():
    data = _base_data()
    data["dates"] = ["2024-01-01"]
    html = render_evolution_table_from_dict(data)
    assert 'title="2024-01-01"' in html
    # v2.0 has no date, no title attr
    assert html.count("title=") == 1


def test_default_values_shown():
    data = {
        "symbol": "f",
        "versions": ["v1"],
        "slots": [
            {"position": 0, "cells": [{"name": "x", "type": "int", "default": "42"}]},
        ],
    }
    html = render_evolution_table_from_dict(data)
    assert "= 42" in html


def test_roundtrip_with_demo_json():
    """The demo JSON file renders successfully."""
    demo = Path(__file__).parent.parent / "great_docs" / "assets" / "api-evolution-demo.json"
    if not demo.exists():
        pytest.skip("demo JSON not found")
    data = json.loads(demo.read_text())
    html = render_evolution_table_from_dict(data)
    assert "gd-evolution-table" in html
    assert data["versions"][0] in html


def test_annotation_str_none():
    """Returns None for None annotation."""
    assert _annotation_str(None) is None


def test_annotation_str_string():
    """Returns string for string annotation."""
    assert _annotation_str("int") == "int"


def test_annotation_str_exception():
    """Returns None when str() raises."""

    class BadObj:
        def __str__(self):
            raise ValueError("cannot convert")

    assert _annotation_str(BadObj()) is None


def test_parameter_kind_str_missing():
    """Returns default when .kind.name raises."""

    class BadParam:
        kind = None

    assert _parameter_kind_str(BadParam()) == "POSITIONAL_OR_KEYWORD"


def test_extract_parameters_exception():
    """Returns empty list when parameters iteration fails."""

    class BadObj:
        @property
        def parameters(self):
            raise AttributeError("no params")

    assert _extract_parameters(BadObj()) == []


def test_extract_bases_exception():
    """Returns empty list when bases iteration fails."""

    class BadObj:
        @property
        def bases(self):
            raise TypeError("no bases")

    assert _extract_bases(BadObj()) == []


def test_extract_decorators_exception():
    """Returns empty list when decorators iteration fails."""

    class BadObj:
        @property
        def decorators(self):
            raise RuntimeError("no decorators")

    assert _extract_decorators(BadObj()) == []


def test_describe_param_change_retyped():
    """Describes retyped parameter."""
    pc = ParameterChange(
        parameter="x",
        change_type="retyped",
        old_value="str",
        new_value="int",
    )
    desc = _describe_param_change(pc)
    assert "type" in desc
    assert "str" in desc
    assert "int" in desc


def test_describe_param_change_default_changed():
    """Describes default change."""
    pc = ParameterChange(
        parameter="x",
        change_type="default_changed",
        old_value="None",
        new_value="0",
    )
    desc = _describe_param_change(pc)
    assert "default" in desc


def test_describe_param_change_kind_changed():
    """Describes kind change."""
    pc = ParameterChange(
        parameter="x",
        change_type="kind_changed",
        old_value="POSITIONAL_OR_KEYWORD",
        new_value="KEYWORD_ONLY",
    )
    desc = _describe_param_change(pc)
    assert "kind" in desc


def test_describe_param_change_reordered():
    """Describes reordered parameters."""
    pc = ParameterChange(
        parameter="*",
        change_type="reordered",
        old_value="a, b",
        new_value="b, a",
    )
    desc = _describe_param_change(pc)
    assert "reordered" in desc.lower()


def test_describe_param_change_unknown():
    """Describes unknown change type (fallback case)."""
    pc = ParameterChange(
        parameter="x",
        change_type="custom_change",
    )
    desc = _describe_param_change(pc)
    assert "custom_change" in desc


def test_describe_param_change_breaking_prefix():
    """Breaking changes get warning prefix."""
    pc = ParameterChange(
        parameter="x",
        change_type="removed",
        is_breaking=True,
    )
    desc = _describe_param_change(pc)
    assert desc.startswith("⚠")


def test_diff_symbol_async_added():
    """Detects function becoming async."""
    old = SymbolInfo(name="f", kind="function", is_async=False)
    new = SymbolInfo(name="f", kind="function", is_async=True)
    change = _diff_symbol("f", old, new)
    assert change is not None
    assert change.is_breaking
    assert any("async" in d.lower() for d in change.details)


def test_diff_symbol_async_removed():
    """Detects function becoming non-async."""
    old = SymbolInfo(name="f", kind="function", is_async=True)
    new = SymbolInfo(name="f", kind="function", is_async=False)
    change = _diff_symbol("f", old, new)
    assert change is not None
    assert change.is_breaking
    assert any("no longer async" in d.lower() for d in change.details)


def test_detect_package_name_from_pyproject(tmp_path):
    """Reads package name from pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-package"\n')
    assert _detect_package_name(tmp_path) == "my_package"


def test_detect_package_name_no_pyproject(tmp_path):
    """Returns None when pyproject.toml doesn't exist."""
    assert _detect_package_name(tmp_path) is None


def test_detect_package_name_no_project_name(tmp_path):
    """Returns None when [project].name is missing."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    assert _detect_package_name(tmp_path) is None


def test_detect_package_name_invalid_toml(tmp_path):
    """Returns None on invalid TOML."""
    (tmp_path / "pyproject.toml").write_text("not valid toml {{{")
    assert _detect_package_name(tmp_path) is None


@patch("great_docs._api_diff.subprocess.run")
def test_list_version_tags_success(mock_run):
    """Returns sorted version tags."""
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="v0.1.0\nv1.0.0\nv1.1.0\nsome-tag\nrelease-2\n",
    )
    tags = list_version_tags(Path("/project"))
    assert tags == ["v0.1.0", "v1.0.0", "v1.1.0"]


@patch("great_docs._api_diff.subprocess.run")
def test_list_version_tags_failure(mock_run):
    """Returns empty list on git failure."""
    mock_run.return_value = MagicMock(returncode=128, stdout="")
    assert list_version_tags(Path("/project")) == []


@patch("great_docs._api_diff.subprocess.run")
def test_list_version_tags_timeout(mock_run):
    """Returns empty list on timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=10)
    assert list_version_tags(Path("/project")) == []


@patch("great_docs._api_diff.subprocess.run")
def test_extract_package_at_tag_not_found(mock_run):
    """Returns None when package dir not in git tree."""
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    result = _extract_package_at_tag(Path("/project"), "v1.0", "mypkg")
    assert result is None


@patch("great_docs._api_diff.subprocess.run")
def test_extract_package_at_tag_archive_fails(mock_run):
    """Returns None when git archive fails."""

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        if "ls-tree" in cmd:
            mock.returncode = 0
            mock.stdout = "mypkg/\n"
            return mock
        # archive fails
        mock.returncode = 1
        mock.stdout = b""
        return mock

    mock_run.side_effect = fake_run
    result = _extract_package_at_tag(Path("/project"), "v1.0", "mypkg")
    assert result is None


@patch("great_docs._api_diff._extract_package_at_tag", return_value=None)
def test_snapshot_at_tag_extraction_fails(mock_extract):
    """Returns None when extraction fails."""
    result = snapshot_at_tag(Path("/project"), "v1.0", "mypkg")
    assert result is None


@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_build_timeline_success(mock_tags, mock_snap):
    """Builds timeline entries for each tag."""
    snap1 = ApiSnapshot(
        version="v1.0",
        package_name="pkg",
        symbols={"f": SymbolInfo(name="f", kind="function")},
    )
    snap2 = ApiSnapshot(
        version="v2.0",
        package_name="pkg",
        symbols={
            "f": SymbolInfo(name="f", kind="function"),
            "C": SymbolInfo(name="C", kind="class"),
        },
    )
    mock_snap.side_effect = [snap1, snap2]
    timeline = build_timeline(Path("/project"), "pkg")
    assert len(timeline) == 2
    assert timeline[0]["version"] == "v1.0"
    assert timeline[0]["symbols"] == 1
    assert timeline[1]["symbols"] == 2
    assert timeline[1]["classes"] == 1


@patch("great_docs._api_diff.snapshot_at_tag", return_value=None)
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0"])
def test_build_timeline_skip_failed(mock_tags, mock_snap):
    """Skips tags where snapshot fails."""
    timeline = build_timeline(Path("/project"), "pkg")
    assert timeline == []


@patch("great_docs._api_diff._detect_package_name", return_value=None)
def test_api_diff_no_package_name(mock_detect):
    """Returns None when package name not detected."""
    result = api_diff(Path("/project"), "v1.0", "v2.0")
    assert result is None


@patch("great_docs._api_diff.snapshot_at_tag", return_value=None)
@patch("great_docs._api_diff.snapshot_from_griffe")
def test_api_diff_head_version(mock_griffe, mock_tag):
    """Uses snapshot_from_griffe for HEAD version."""
    mock_griffe.return_value = ApiSnapshot(version="HEAD", package_name="pkg", symbols={})
    result = api_diff(Path("/project"), "v1.0", "HEAD", package_name="pkg")
    mock_griffe.assert_called_once()
    # old_snap is None so returns None
    assert result is None


@patch("great_docs._api_diff.diff_snapshots")
@patch("great_docs._api_diff.snapshot_at_tag")
def test_api_diff_success(mock_tag, mock_diff):
    """Successfully diffs two versions."""
    snap = ApiSnapshot(version="v1.0", package_name="pkg", symbols={})
    mock_tag.return_value = snap
    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
        changed=[],
        added=[],
        removed=[],
    )
    result = api_diff(Path("/project"), "v1.0", "v2.0", package_name="pkg")
    assert result is not None
    assert result.old_version == "v1.0"


def test_snapshot_from_griffe_no_exports():
    """Falls back to public members when no __all__ or exports."""
    mock_pkg = MagicMock()
    mock_pkg.exports = None
    mock_member = MagicMock()
    mock_member.kind.value = "function"
    mock_member.is_async = False
    mock_member.parameters = []
    mock_member.annotation = None
    mock_member.returns = None
    mock_member.decorators = []
    members_dict = {"public_fn": mock_member, "_private": MagicMock()}
    mock_pkg.members = members_dict

    with patch("griffe.load", return_value=mock_pkg):
        snap = snapshot_from_griffe("mypkg", "v1.0")
    assert "public_fn" in snap.symbols
    assert "_private" not in snap.symbols
