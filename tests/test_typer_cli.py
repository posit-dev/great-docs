# pyright: reportPrivateUsage=false
"""
Typer command conversion, discovery and extraction

Typer vendors its own copy of Click. Its converted commands are not instances of the
top-level Click classes, so discovery and extraction must inspect their attributes. These
tests cover conversion, page extraction and API snapshots.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from great_docs._cliref import click as cli_click

typer = pytest.importorskip("typer")


def _sample_app() -> "typer.Typer":
    """A Typer app with two top-level commands and a nested sub-app."""
    app = typer.Typer(help="Root help.")

    @app.command()
    def greet(name: str, count: int = 1, loud: bool = False):
        """Greet NAME."""

    @app.command()
    def version():
        """Show the version."""

    db = typer.Typer(help="Database commands.")
    app.add_typer(db, name="db")

    @db.command()
    def migrate(revision: str = "head"):
        """Run migrations."""

    return app


# ---------------------------------------------------------------------------
# Typer helpers
# ---------------------------------------------------------------------------


class TestTyperHelpers:
    def test_is_typer_app_true(self):
        from great_docs._cliref.click import is_typer_app

        assert is_typer_app(typer.Typer()) is True

    def test_is_typer_app_false_for_other_objects(self):
        from great_docs._cliref.click import is_typer_app

        assert is_typer_app(click.Command("x")) is False
        assert is_typer_app("not an app") is False

    def test_to_click_command_converts_typer_app(self):
        from great_docs._cliref.click import is_cli_group, to_click_command

        cmd = to_click_command(_sample_app())

        assert cmd is not None

        # The converted top-level command is a group with the registered commands.
        assert is_cli_group(cmd)
        assert set(cmd.commands) == {"greet", "version", "db"}

    def test_to_click_command_passthrough_for_click(self):
        from great_docs._cliref.click import to_click_command

        c = click.Command("x")

        assert to_click_command(c) is c

        g = click.Group("g")

        assert to_click_command(g) is g

    def test_to_click_command_returns_none_for_non_cli(self):
        from great_docs._cliref.click import to_click_command

        assert to_click_command("nope") is None
        assert to_click_command(object()) is None
        assert to_click_command(None) is None

    def test_is_typer_app_false_when_typer_not_installed(self, monkeypatch):
        """Graceful degradation: no Typer installed -> not a Typer app (no raise)."""
        from great_docs._cliref.click import is_typer_app

        # A None entry in sys.modules makes `import typer` raise ImportError.
        monkeypatch.setitem(sys.modules, "typer", None)

        assert is_typer_app(object()) is False

    def test_to_click_command_returns_none_when_typer_not_installed(self, monkeypatch):
        """A non-Click object cannot be coerced when Typer is unavailable."""
        from great_docs._cliref.click import to_click_command

        monkeypatch.setitem(sys.modules, "typer", None)

        # Click is still importable, so this reaches (and survives) the failed
        # Typer import before returning None.
        assert to_click_command(object()) is None

    def test_is_cli_command(self):
        from great_docs._cliref.click import is_cli_command

        assert is_cli_command(_sample_app()) is True
        assert is_cli_command(click.Command("x")) is True
        assert is_cli_command(42) is False

    def test_is_cli_group_leaf_vs_group(self):
        from great_docs._cliref.click import is_cli_group, to_click_command

        # A single-command Typer app converts to a leaf command (no subcommands).
        leaf_app = typer.Typer()

        @leaf_app.command()
        def only(name: str):
            """Just one command."""

        leaf = to_click_command(leaf_app)

        assert is_cli_group(leaf) is False

        group = to_click_command(_sample_app())

        assert is_cli_group(group) is True

    def test_param_kind_classifies_typer_params(self):
        from great_docs._cliref.click import param_kind, to_click_command

        cmd = to_click_command(_sample_app())
        greet = cmd.commands["greet"]
        kinds = {p.name: param_kind(p) for p in greet.params}

        assert kinds["name"] == "argument"
        assert kinds["count"] == "option"
        assert kinds["loud"] == "option"


# ---------------------------------------------------------------------------
# Discovery and extraction
# ---------------------------------------------------------------------------


class TestTyperDiscovery:
    def _patch_typer_module(self, monkeypatch):
        """Return a fake `mypkg.cli` module exposing a Typer `app`."""
        fake_mod = types.ModuleType("mypkg.cli")
        fake_mod.app = _sample_app()
        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        return fake_mod, mock_import

    def test_find_command_returns_converted_typer(self, tmp_path, monkeypatch):
        _fake, mock_import = self._patch_typer_module(monkeypatch)

        with patch("importlib.import_module", side_effect=mock_import):
            found = cli_click.find_command("mypkg", tmp_path, cli_module="mypkg.cli", cli_name=None)

        assert found is not None
        obj = found.command

        # Converted object is introspectable as a Click-style group.
        assert hasattr(obj, "commands")
        assert set(obj.commands) == {"greet", "version", "db"}

    def test_discover_extracts_typer_tree(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cli_click, "entry_point_name", lambda _root, _target: "mytool")
        _fake, mock_import = self._patch_typer_module(monkeypatch)

        with patch("importlib.import_module", side_effect=mock_import):
            info = cli_click.discover(
                "mypkg",
                tmp_path,
                cli_module="mypkg.cli",
                cli_name=None,
                display_name="mypkg",
                report=print,
            )

        assert info is not None
        assert info["is_group"] is True
        assert info["entry_point_name"] == "mytool"

        names = {c["name"] for c in info["commands"]}

        assert names == {"greet", "version", "db"}

        greet = next(c for c in info["commands"] if c["name"] == "greet")

        assert [a["name"] for a in greet["arguments"]] == ["name"]

        opt_names = {o["name_display"] for o in greet["options"]}

        assert "--count" in opt_names

        # The boolean flag carries no value-type (regression: Typer reports
        # the type name "boolean", which must not leak through as a type). Typer
        # renders a bool option as a `--loud/--no-loud` pair.
        loud = next(o for o in greet["options"] if "--loud" in o["names"])

        assert loud["is_flag"] is True
        assert loud["type"] is None

        # Nested sub-app becomes a nested group with its own subcommands.
        db = next(c for c in info["commands"] if c["name"] == "db")

        assert db["is_group"] is True
        assert [c["name"] for c in db["commands"]] == ["migrate"]


# ---------------------------------------------------------------------------
# API-diff CLI snapshots
# ---------------------------------------------------------------------------


class TestTyperSnapshot:
    def test_extract_snapshot_accepts_typer_app(self):
        snap = cli_click.extract_snapshot(_sample_app())

        assert snap is not None
        assert snap.is_group is True

        sub_names = {c.name for c in snap.subcommands}

        assert sub_names == {"greet", "version", "db"}

        db = next(c for c in snap.subcommands if c.name == "db")

        assert db.is_group is True
        assert {c.name for c in db.subcommands} == {"migrate"}

    def test_extract_snapshot_rejects_non_cli(self):
        assert cli_click.extract_snapshot("not a cli") is None
