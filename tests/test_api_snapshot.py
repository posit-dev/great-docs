from __future__ import annotations

import json
from pathlib import Path

from great_docs._api_diff import (
    ApiDiff,
    ApiSnapshot,
    CliChange,
    CliCommandInfo,
    CliOptionInfo,
    ParameterInfo,
    SymbolInfo,
    _import_cli_from_source,
    compute_version_badges,
    diff_snapshots,
    inject_badges_into_qmd,
    load_snapshots_for_annotations,
    render_badge_html,
    snapshot_cli_from_click,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_symbol(name: str, kind: str = "function", **kwargs) -> SymbolInfo:
    return SymbolInfo(name=name, kind=kind, **kwargs)


def _make_snapshot(version: str, symbols: dict[str, SymbolInfo] | None = None) -> ApiSnapshot:
    return ApiSnapshot(
        version=version,
        package_name="test_pkg",
        symbols=symbols or {},
    )


# ---------------------------------------------------------------------------
# ParameterInfo serialization
# ---------------------------------------------------------------------------


class TestParameterInfoSerialization:
    def test_roundtrip(self):
        p = ParameterInfo(name="x", annotation="int", default="0", kind="POSITIONAL_OR_KEYWORD")
        d = p.to_dict()
        assert d["name"] == "x"
        assert d["annotation"] == "int"
        assert d["default"] == "0"
        assert d["kind"] == "POSITIONAL_OR_KEYWORD"
        restored = ParameterInfo.from_dict(d)
        assert restored == p

    def test_minimal_roundtrip(self):
        p = ParameterInfo(name="y")
        d = p.to_dict()
        assert "annotation" not in d
        assert "default" not in d
        restored = ParameterInfo.from_dict(d)
        assert restored.name == "y"
        assert restored.annotation is None
        assert restored.default is None


# ---------------------------------------------------------------------------
# SymbolInfo serialization
# ---------------------------------------------------------------------------


class TestSymbolInfoSerialization:
    def test_roundtrip_function(self):
        sym = SymbolInfo(
            name="foo",
            kind="function",
            parameters=[
                ParameterInfo(name="x", annotation="int"),
                ParameterInfo(name="y", annotation="str", default="''"),
            ],
            return_annotation="bool",
            is_async=True,
            decorators=["@cache"],
        )
        d = sym.to_dict()
        assert d["name"] == "foo"
        assert d["kind"] == "function"
        assert d["is_async"] is True
        assert len(d["parameters"]) == 2
        assert d["return_annotation"] == "bool"
        assert d["decorators"] == ["@cache"]

        restored = SymbolInfo.from_dict(d)
        assert restored == sym

    def test_roundtrip_class(self):
        sym = SymbolInfo(
            name="Bar",
            kind="class",
            bases=["Base", "Mixin"],
        )
        d = sym.to_dict()
        assert d["bases"] == ["Base", "Mixin"]
        assert "parameters" not in d  # empty list omitted
        assert "is_async" not in d  # False omitted

        restored = SymbolInfo.from_dict(d)
        assert restored == sym

    def test_minimal(self):
        sym = SymbolInfo(name="x", kind="attribute")
        d = sym.to_dict()
        assert d == {"name": "x", "kind": "attribute"}
        restored = SymbolInfo.from_dict(d)
        assert restored == sym


# ---------------------------------------------------------------------------
# ApiSnapshot serialization
# ---------------------------------------------------------------------------


class TestApiSnapshotSerialization:
    def test_roundtrip(self):
        snap = _make_snapshot(
            "v1.0",
            {
                "foo": _make_symbol("foo", parameters=[ParameterInfo(name="x", annotation="int")]),
                "Bar": _make_symbol("Bar", kind="class", bases=["Base"]),
            },
        )
        d = snap.to_dict()
        assert d["version"] == "v1.0"
        assert d["package_name"] == "test_pkg"
        assert "foo" in d["symbols"]
        assert "Bar" in d["symbols"]

        restored = ApiSnapshot.from_dict(d)
        assert restored.version == snap.version
        assert restored.package_name == snap.package_name
        assert set(restored.symbols.keys()) == set(snap.symbols.keys())
        assert restored.symbols["foo"] == snap.symbols["foo"]
        assert restored.symbols["Bar"] == snap.symbols["Bar"]

    def test_empty_snapshot(self):
        snap = _make_snapshot("v0.0")
        d = snap.to_dict()
        assert d["symbols"] == {}
        restored = ApiSnapshot.from_dict(d)
        assert restored.symbol_count == 0

    def test_save_and_load(self, tmp_path: Path):
        snap = _make_snapshot(
            "v2.0",
            {"baz": _make_symbol("baz", return_annotation="str")},
        )
        out = tmp_path / "snapshots" / "v2.0.json"
        snap.save(out)

        assert out.exists()
        # Verify it's valid JSON
        data = json.loads(out.read_text())
        assert data["version"] == "v2.0"

        loaded = ApiSnapshot.load(out)
        assert loaded.version == "v2.0"
        assert loaded.symbols["baz"].return_annotation == "str"

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        snap = _make_snapshot("v1.0")
        out = tmp_path / "deep" / "nested" / "snap.json"
        snap.save(out)
        assert out.exists()


# ---------------------------------------------------------------------------
# Version badges
# ---------------------------------------------------------------------------


class TestComputeVersionBadges:
    def test_new_symbol(self):
        prev = _make_snapshot("v0.1", {"foo": _make_symbol("foo")})
        curr = _make_snapshot(
            "v0.2",
            {
                "foo": _make_symbol("foo"),
                "bar": _make_symbol("bar"),
            },
        )
        badges = compute_version_badges(curr, prev)
        assert "bar" in badges
        assert badges["bar"]["badge"] == "new"
        assert badges["bar"]["version"] == "v0.2"
        assert "foo" not in badges  # unchanged

    def test_changed_symbol(self):
        prev = _make_snapshot(
            "v0.1",
            {
                "foo": _make_symbol("foo", parameters=[ParameterInfo(name="x")]),
            },
        )
        curr = _make_snapshot(
            "v0.2",
            {
                "foo": _make_symbol(
                    "foo",
                    parameters=[ParameterInfo(name="x"), ParameterInfo(name="y")],
                ),
            },
        )
        badges = compute_version_badges(curr, prev)
        assert "foo" in badges
        assert badges["foo"]["badge"] == "changed"

    def test_deprecated_symbol(self):
        curr = _make_snapshot(
            "v0.3",
            {
                "old_func": _make_symbol("old_func", decorators=["@deprecated"]),
            },
        )
        badges = compute_version_badges(curr, None)
        assert "old_func" in badges
        assert badges["old_func"]["badge"] == "deprecated"

    def test_deprecated_overrides_changed(self):
        prev = _make_snapshot(
            "v0.1",
            {
                "foo": _make_symbol("foo", parameters=[ParameterInfo(name="x")]),
            },
        )
        curr = _make_snapshot(
            "v0.2",
            {
                "foo": _make_symbol(
                    "foo",
                    parameters=[ParameterInfo(name="y")],
                    decorators=["@deprecated"],
                ),
            },
        )
        badges = compute_version_badges(curr, prev)
        assert badges["foo"]["badge"] == "deprecated"

    def test_no_previous_returns_only_deprecations(self):
        curr = _make_snapshot(
            "v0.1",
            {
                "foo": _make_symbol("foo"),
                "bar": _make_symbol("bar"),
            },
        )
        badges = compute_version_badges(curr, None)
        # No badges for normal symbols in first version
        assert "foo" not in badges
        assert "bar" not in badges

    def test_empty_when_unchanged(self):
        snap = _make_snapshot("v0.1", {"foo": _make_symbol("foo")})
        badges = compute_version_badges(snap, snap)
        assert badges == {}


# ---------------------------------------------------------------------------
# Badge rendering
# ---------------------------------------------------------------------------


class TestRenderBadgeHtml:
    def test_new_badge(self):
        html = render_badge_html({"badge": "new", "version": "0.3"})
        assert "gd-badge-new" in html
        assert "New in 0.3" in html

    def test_changed_badge(self):
        html = render_badge_html({"badge": "changed", "version": "0.3"})
        assert "gd-badge-changed" in html
        assert "Changed in 0.3" in html

    def test_deprecated_badge(self):
        html = render_badge_html({"badge": "deprecated", "version": "0.3"})
        assert "gd-badge-deprecated" in html
        assert "Deprecated in 0.3" in html

    def test_html_escaping(self):
        html = render_badge_html({"badge": "new", "version": '<script>"xss"</script>'})
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# QMD injection
# ---------------------------------------------------------------------------


class TestInjectBadgesIntoQmd:
    def test_injects_after_heading(self):
        content = "## foo\n\nSome docs."
        badges = {"foo": {"badge": "new", "version": "0.3"}}
        result = inject_badges_into_qmd(content, badges)
        lines = result.split("\n")
        assert lines[0] == "## foo"
        assert "gd-badge-new" in lines[1]
        assert lines[2] == ""

    def test_qualified_name_heading(self):
        content = "### pkg.submod.Bar\n\nClass docs."
        badges = {"Bar": {"badge": "changed", "version": "0.2"}}
        result = inject_badges_into_qmd(content, badges)
        assert "gd-badge-changed" in result

    def test_heading_with_quarto_classes(self):
        content = "## foo { .doc-heading }\n\nDocs."
        badges = {"foo": {"badge": "new", "version": "0.3"}}
        result = inject_badges_into_qmd(content, badges)
        assert "gd-badge-new" in result

    def test_no_badges_returns_unchanged(self):
        content = "## foo\n\nSome docs."
        result = inject_badges_into_qmd(content, {})
        assert result == content

    def test_non_matching_headings_unchanged(self):
        content = "## Introduction\n\n## Getting Started\n"
        badges = {"foo": {"badge": "new", "version": "0.3"}}
        result = inject_badges_into_qmd(content, badges)
        assert result == content


# ---------------------------------------------------------------------------
# Snapshot loading
# ---------------------------------------------------------------------------


class TestLoadSnapshotsForAnnotations:
    def test_loads_both(self, tmp_path: Path):
        snap1 = _make_snapshot("v0.1", {"foo": _make_symbol("foo")})
        snap2 = _make_snapshot("v0.2", {"foo": _make_symbol("foo"), "bar": _make_symbol("bar")})
        snap1.save(tmp_path / "v0.1.json")
        snap2.save(tmp_path / "v0.2.json")

        curr, prev = load_snapshots_for_annotations(tmp_path, "v0.2", "v0.1")
        assert curr is not None
        assert prev is not None
        assert curr.version == "v0.2"
        assert prev.version == "v0.1"

    def test_missing_previous(self, tmp_path: Path):
        snap = _make_snapshot("v0.1")
        snap.save(tmp_path / "v0.1.json")

        curr, prev = load_snapshots_for_annotations(tmp_path, "v0.1", "v0.0")
        assert curr is not None
        assert prev is None

    def test_no_previous_version(self, tmp_path: Path):
        snap = _make_snapshot("v0.1")
        snap.save(tmp_path / "v0.1.json")

        curr, prev = load_snapshots_for_annotations(tmp_path, "v0.1", None)
        assert curr is not None
        assert prev is None

    def test_missing_both(self, tmp_path: Path):
        curr, prev = load_snapshots_for_annotations(tmp_path, "v1.0", "v0.9")
        assert curr is None
        assert prev is None


# ---------------------------------------------------------------------------
# CliOptionInfo serialization
# ---------------------------------------------------------------------------


class TestCliOptionInfoSerialization:
    def test_roundtrip(self):
        opt = CliOptionInfo(
            name="--verbose",
            type="option",
            is_flag=True,
            required=False,
            default=None,
            help="Enable verbose output",
        )
        d = opt.to_dict()
        assert d["name"] == "--verbose"
        assert d["type"] == "option"
        assert d["is_flag"] is True
        restored = CliOptionInfo.from_dict(d)
        assert restored == opt

    def test_argument_roundtrip(self):
        arg = CliOptionInfo(name="path", type="argument", required=True)
        d = arg.to_dict()
        restored = CliOptionInfo.from_dict(d)
        assert restored == arg
        assert restored.is_flag is False


# ---------------------------------------------------------------------------
# CliCommandInfo serialization
# ---------------------------------------------------------------------------


class TestCliCommandInfoSerialization:
    def test_roundtrip_simple_command(self):
        cmd = CliCommandInfo(
            name="build",
            help="Build the docs",
            options=[
                CliOptionInfo(name="--clean", type="option", is_flag=True),
            ],
        )
        d = cmd.to_dict()
        assert d["name"] == "build"
        assert len(d["options"]) == 1
        restored = CliCommandInfo.from_dict(d)
        assert restored == cmd

    def test_roundtrip_nested_group(self):
        group = CliCommandInfo(
            name="cli",
            help="My CLI",
            is_group=True,
            subcommands=[
                CliCommandInfo(
                    name="build",
                    help="Build the docs",
                    options=[CliOptionInfo(name="--clean", type="option", is_flag=True)],
                ),
                CliCommandInfo(name="serve", help="Serve locally"),
            ],
        )
        d = group.to_dict()
        assert d["is_group"] is True
        assert len(d["subcommands"]) == 2
        restored = CliCommandInfo.from_dict(d)
        assert restored == group

    def test_all_command_paths(self):
        group = CliCommandInfo(
            name="app",
            is_group=True,
            subcommands=[
                CliCommandInfo(name="build"),
                CliCommandInfo(
                    name="check",
                    is_group=True,
                    subcommands=[CliCommandInfo(name="links")],
                ),
            ],
        )
        paths = group.all_command_paths()
        assert "app" in paths
        assert "app build" in paths
        assert "app check" in paths
        assert "app check links" in paths


# ---------------------------------------------------------------------------
# ApiSnapshot with CLI
# ---------------------------------------------------------------------------


class TestApiSnapshotWithCli:
    def test_roundtrip(self, tmp_path: Path):
        cli = CliCommandInfo(
            name="myapp",
            help="My app",
            is_group=True,
            subcommands=[CliCommandInfo(name="run", help="Run it")],
        )
        snap = ApiSnapshot(
            version="v1.0",
            package_name="test_pkg",
            symbols={},
            cli_commands=cli,
        )
        snap.save(tmp_path / "v1.json")
        loaded = ApiSnapshot.load(tmp_path / "v1.json")
        assert loaded.cli_commands is not None
        assert loaded.cli_commands.name == "myapp"
        assert len(loaded.cli_commands.subcommands) == 1

    def test_cli_command_count(self):
        cli = CliCommandInfo(
            name="myapp",
            is_group=True,
            subcommands=[
                CliCommandInfo(name="a"),
                CliCommandInfo(name="b"),
            ],
        )
        snap = ApiSnapshot(version="v1.0", package_name="pkg", symbols={}, cli_commands=cli)
        assert snap.cli_command_count == 3  # myapp + a + b

    def test_cli_command_count_none(self):
        snap = _make_snapshot("v1.0")
        assert snap.cli_command_count == 0


# ---------------------------------------------------------------------------
# CLI diffing
# ---------------------------------------------------------------------------


def _make_cli_group(*subcmds: CliCommandInfo, name: str = "app") -> CliCommandInfo:
    return CliCommandInfo(name=name, is_group=True, subcommands=list(subcmds))


class TestCliDiffing:
    def test_added_command(self):
        old = _make_snapshot("v1")
        old.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        new = _make_snapshot("v2")
        new.cli_commands = _make_cli_group(
            CliCommandInfo(name="build"),
            CliCommandInfo(name="serve"),
        )

        diff = diff_snapshots(old, new)
        assert len(diff.cli_changes) == 1
        assert diff.cli_changes[0].command == "app serve"
        assert diff.cli_changes[0].change_type == "added"

    def test_removed_command(self):
        old = _make_snapshot("v1")
        old.cli_commands = _make_cli_group(
            CliCommandInfo(name="build"),
            CliCommandInfo(name="serve"),
        )

        new = _make_snapshot("v2")
        new.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        diff = diff_snapshots(old, new)
        assert len(diff.cli_changes) == 1
        assert diff.cli_changes[0].command == "app serve"
        assert diff.cli_changes[0].change_type == "removed"
        assert diff.cli_changes[0].is_breaking is True

    def test_changed_option(self):
        old = _make_snapshot("v1")
        old.cli_commands = _make_cli_group(
            CliCommandInfo(
                name="build",
                options=[CliOptionInfo(name="--clean", type="option", is_flag=True)],
            )
        )

        new = _make_snapshot("v2")
        new.cli_commands = _make_cli_group(
            CliCommandInfo(
                name="build",
                options=[
                    CliOptionInfo(name="--clean", type="option", is_flag=False, required=True)
                ],
            )
        )

        diff = diff_snapshots(old, new)
        assert len(diff.cli_changes) == 1
        c = diff.cli_changes[0]
        assert c.command == "app build"
        assert c.change_type == "changed"
        assert c.is_breaking is True
        assert any("flag" in d for d in c.details)
        assert any("required" in d for d in c.details)

    def test_no_cli_changes(self):
        old = _make_snapshot("v1")
        old.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        new = _make_snapshot("v2")
        new.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        diff = diff_snapshots(old, new)
        assert diff.cli_changes == []

    def test_both_none(self):
        diff = diff_snapshots(_make_snapshot("v1"), _make_snapshot("v2"))
        assert diff.cli_changes == []

    def test_cli_appears(self):
        old = _make_snapshot("v1")
        new = _make_snapshot("v2")
        new.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        diff = diff_snapshots(old, new)
        assert len(diff.cli_changes) == 2  # app group + build
        assert all(c.change_type == "added" for c in diff.cli_changes)

    def test_cli_removed_entirely(self):
        old = _make_snapshot("v1")
        old.cli_commands = _make_cli_group(CliCommandInfo(name="build"))

        new = _make_snapshot("v2")
        diff = diff_snapshots(old, new)
        assert len(diff.cli_changes) == 2
        assert all(c.change_type == "removed" for c in diff.cli_changes)
        assert all(c.is_breaking for c in diff.cli_changes)


# ---------------------------------------------------------------------------
# snapshot_cli_from_click
# ---------------------------------------------------------------------------


class TestSnapshotCliFromClick:
    def test_simple_command(self):
        import click

        @click.command()
        @click.option("--name", "-n", help="Your name", required=True)
        @click.option("--verbose", is_flag=True)
        @click.argument("path")
        def hello(name, verbose, path):
            """Say hello."""

        result = snapshot_cli_from_click(hello)
        assert result is not None
        assert result.name == "hello"
        assert result.help == "Say hello."
        assert not result.is_group
        opts = {o.name: o for o in result.options}
        assert "--name" in opts
        assert opts["--name"].required is True
        assert "--verbose" in opts
        assert opts["--verbose"].is_flag is True
        assert "path" in opts
        assert opts["path"].type == "argument"

    def test_group(self):
        import click

        @click.group()
        def cli():
            """My CLI."""

        @cli.command()
        @click.option("--all", is_flag=True)
        def build(all):
            """Build."""

        @cli.command()
        def serve():
            """Serve."""

        result = snapshot_cli_from_click(cli)
        assert result is not None
        assert result.is_group
        assert len(result.subcommands) == 2
        names = {s.name for s in result.subcommands}
        assert names == {"build", "serve"}

    def test_non_click_returns_none(self):
        result = snapshot_cli_from_click("not a click object")
        assert result is None


# ---------------------------------------------------------------------------
# _import_cli_from_source
# ---------------------------------------------------------------------------


class TestImportCliFromSource:
    def test_import_from_extracted_source(self, tmp_path: Path):
        """Simulate an extracted package with a Click CLI module."""
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "cli.py").write_text(
            "import click\n"
            "\n"
            "@click.group()\n"
            "def cli():\n"
            '    """My CLI."""\n'
            "\n"
            "@cli.command()\n"
            '@click.option("--verbose", is_flag=True)\n'
            "def build(verbose):\n"
            '    """Build it."""\n'
        )

        result = _import_cli_from_source(tmp_path, "mypkg.cli")
        assert result is not None
        assert result.name == "cli"
        assert result.is_group
        assert len(result.subcommands) == 1
        assert result.subcommands[0].name == "build"

    def test_import_missing_module(self, tmp_path: Path):
        result = _import_cli_from_source(tmp_path, "nonexistent.cli")
        assert result is None

    def test_no_click_command_in_module(self, tmp_path: Path):
        pkg_dir = tmp_path / "noclickcli"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "cli.py").write_text("x = 42\n")

        result = _import_cli_from_source(tmp_path, "noclickcli.cli")
        assert result is None

    def test_sys_path_cleaned_up(self, tmp_path: Path):
        """Verify sys.path is restored after import."""
        import sys

        original_path = list(sys.path)
        _import_cli_from_source(tmp_path, "nonexistent.cli")
        assert str(tmp_path) not in sys.path
        assert len(sys.path) == len(original_path)
