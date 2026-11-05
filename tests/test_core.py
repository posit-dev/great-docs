# pyright: reportPrivateUsage=false
"""Tests for great_docs.core (GreatDocs class)."""

from __future__ import annotations

import importlib
import io
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import griffe
import pytest
import yaml

from great_docs import GreatDocs
from great_docs._build import freeze, site
from great_docs._cliref import click as cli_click
from great_docs._cliref import render as cli_render
from great_docs._contribution import Contribution, NavbarLink, Sidebar
from great_docs._mcpref import build as mcp_build
from great_docs._reference import block as reference_block
from great_docs._reference.discovery import (
    categorise_references,
    discover_exports,
    empty_categories,
)
from great_docs._reference.exports import Exports
from great_docs._utils import QUARTO_YML_HEADER
from great_docs._website.seo import robots
from tests.support import (
    StubRemote,
    custom_pages_step,
    discover_user_guide,
    freeze_cache_step,
    make_exports,
    make_project,
    make_run,
    mock_config,
)


def _make_gd(tmp_path: Path) -> GreatDocs:
    """Create a GreatDocs instance in a temp directory with minimal config."""
    (tmp_path / "great-docs.yml").write_text("module: mypkg\n", encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def _put_on_github(root: Path) -> None:
    """
    Declare the project's repository as `acme/mypkg` on GitHub in its `pyproject.toml`

    Parameters
    ----------
    root
        The project directory.
    """
    (root / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\n\n[project.urls]\n'
        'Repository = "https://github.com/acme/mypkg"\n',
        encoding="utf-8",
    )


def _patch_cfg(monkeypatch, gd, name, value):
    """Patch a Config property on the class so the instance returns *value*."""
    monkeypatch.setattr(type(gd._config), name, property(lambda self: value))


class TestFindCommand:
    """
    Command discovery with configured names and fallback searches
    """

    def test_no_cli_module_auto_discovers(self, tmp_path):
        """
        Return `None` when no candidate CLI module can be imported
        """
        real_import = importlib.import_module

        def fail_import(name, *args, **kwargs):
            if name in ("mypkg.cli", "mypkg.__main__", "mypkg.main"):
                raise ModuleNotFoundError(f"No module named {name!r}", name=name)
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=fail_import):
            result = cli_click.find_command("mypkg", tmp_path, cli_module=None, cli_name=None)
        assert result is None

    def test_auto_discovers_module_with_click_obj(self, tmp_path):
        """
        Find a candidate module containing a Click command
        """
        fake_mod = types.ModuleType("mypkg.cli")
        fake_cmd = click.Command("test")
        fake_mod.cli = fake_cmd

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command("mypkg", tmp_path, cli_module=None, cli_name=None)
        assert result.command is fake_cmd

    def test_explicit_cli_module_import_fails(self, tmp_path):
        """
        Return `None` when the configured CLI module cannot be imported
        """
        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.custom_cli":
                raise ImportError("no such module")
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.custom_cli", cli_name=None
            )
        assert result is None

    def test_explicit_cli_name_found(self, tmp_path):
        """
        Find the command named by `cli.name`
        """
        fake_mod = types.ModuleType("mypkg.custom_cli")
        fake_cmd = click.Command("mycmd")
        fake_mod.mycmd = fake_cmd

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.custom_cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.custom_cli", cli_name="mycmd"
            )
        assert result.command is fake_cmd

    def test_common_attr_names_found(self, tmp_path):
        """
        Find a command under a conventional attribute name
        """
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_group = click.Group("main")
        fake_mod.main = fake_group

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.cli_mod", cli_name=None
            )
        assert result.command is fake_group

    def test_scan_all_attrs_fallback(self, tmp_path):
        """
        Find a command under a non-standard public attribute name
        """
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_cmd = click.Command("hidden_cmd")
        fake_mod.my_special_command = fake_cmd

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.cli_mod", cli_name=None
            )
        assert result.command is fake_cmd

    def test_no_click_obj_found_returns_none(self, tmp_path):
        """
        Return `None` when the module contains no command
        """
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_mod.something = "not a click command"

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.cli_mod", cli_name=None
            )
        assert result is None

    @pytest.mark.parametrize("candidate", ["console", "commands"])
    def test_finds_command_in_late_candidate_module(self, tmp_path, candidate):
        """
        Find a command in `console` or `commands`, matching reference page discovery
        """
        fake_mod = types.ModuleType(f"mypkg.{candidate}")
        fake_cmd = click.Command("tool")
        fake_mod.cli = fake_cmd

        def mock_import(name, *args, **kwargs):
            if name == f"mypkg.{candidate}":
                return fake_mod
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command("mypkg", tmp_path, cli_module=None, cli_name=None)
        assert result.command is fake_cmd

    def test_candidate_that_exits_on_import_is_skipped(self, tmp_path):
        """
        Skip a `__main__` that runs its command on import and search the next candidate
        """
        fake_mod = types.ModuleType("mypkg.main")
        fake_cmd = click.Command("tool")
        fake_mod.cli = fake_cmd

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.__main__":
                # An unguarded `cli()` makes Click parse the build's argv and exit.
                raise SystemExit(2)
            if name == "mypkg.main":
                return fake_mod
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command("mypkg", tmp_path, cli_module=None, cli_name=None)
        assert result.command is fake_cmd

    @pytest.mark.parametrize(
        "error",
        [
            ModuleNotFoundError("No module named 'requests'", name="requests"),
            ImportError("cannot import name 'run' from 'mypkg.core'"),
            SyntaxError("invalid syntax"),
        ],
    )
    def test_candidate_that_fails_on_import_raises(self, tmp_path, error):
        """
        Name the failing candidate in `ImportError` and preserve the original cause
        """
        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli":
                raise error
            return real_import(name, *args, **kwargs)

        with (
            patch("importlib.import_module", side_effect=mock_import),
            pytest.raises(ImportError, match="mypkg.cli") as raised,
        ):
            cli_click.find_command("mypkg", tmp_path, cli_module=None, cli_name=None)
        assert raised.value.__cause__ is error

    def test_configured_module_that_exits_on_import_finds_none(self, tmp_path):
        """
        Report a configured CLI module that exits on import instead of ending the build
        """
        lines: list[str] = []

        def mock_import(name, *args, **kwargs):
            raise SystemExit(2)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.__main__", cli_name=None, report=lines.append
            )
        assert result is None
        assert lines == [
            "Could not import CLI module mypkg.__main__: "
            "importing mypkg.__main__ exited with status 2"
        ]

    def test_cli_name_naming_a_non_command_finds_none(self, tmp_path):
        """
        Return no command when `cli.name` names a non-command despite another command in the module
        """
        fake_mod = types.ModuleType("mypkg.custom_cli")
        fake_mod.helper = "not a command"
        fake_mod.cli = click.Command("other")

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.custom_cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = cli_click.find_command(
                "mypkg", tmp_path, cli_module="mypkg.custom_cli", cli_name="helper"
            )
        assert result is None


def _make_root_project(tmp_path: Path, config: str = "") -> GreatDocs:
    """
    Create a root-layout project for the package `mypkgxyz`

    Declare the package in `pyproject.toml` and write `config` to `great-docs.yml`.
    The build directory is `<root>/great-docs`.

    Parameters
    ----------
    tmp_path :
        The directory in which to create the project.
    config :
        The contents of `great-docs.yml`.

    Returns
    -------
    :
        The project configured for a package-root build.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "mypkgxyz"\nversion = "1.0"\n', encoding="utf-8"
    )
    package = tmp_path / "mypkgxyz"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "great-docs.yml").write_text(config, encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def _build_mcp_candidates(gd: GreatDocs, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Run a site build and return the attempted MCP server module imports

    Stub Quarto and stop the build at the first step after MCP discovery.

    Parameters
    ----------
    gd :
        The project to build.
    monkeypatch :
        The fixture that stubs Quarto and stops the build.

    Returns
    -------
    :
        The attempted imports ending in `mcp`, `mcp_server` or `server`, in order.
    """

    # BaseException bypasses the build's `except Exception` handlers so the build stops.
    class McpStepPassed(BaseException):
        pass

    imported: list[str] = []
    real_import = importlib.import_module

    def record_import(name: str, package: str | None = None) -> types.ModuleType:
        imported.append(name)
        return real_import(name, package)

    def stop_build(*args: object, **kwargs: object) -> None:
        raise McpStepPassed

    monkeypatch.setattr("great_docs._build.quarto.ensure_installed", lambda: None)
    monkeypatch.setattr(importlib, "import_module", record_import)
    # The user guide is the first step after MCP discovery.
    monkeypatch.setattr("great_docs._build.content.user_guide", stop_build)
    with pytest.raises(McpStepPassed):
        gd.build(refresh=False)

    server_modules = {"mcp", "mcp_server", "server"}
    return [name for name in imported if name.rpartition(".")[2] in server_modules]


class TestDiscoverMcpServer:
    """MCP server selection from configuration and the documented package"""

    def test_build_tries_only_the_documented_package(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A root-layout build tries only the documented package's server modules"""
        gd = _make_root_project(tmp_path)

        candidates = _build_mcp_candidates(gd, monkeypatch)

        assert candidates == ["mypkgxyz.mcp", "mypkgxyz.mcp_server", "mypkgxyz.server"]
        assert not (gd.build_dir / "reference" / "mcp").exists()

    def test_build_tries_configured_module_without_package_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """`module:` names the package to search when no package name is detected"""
        for package in ("mypkgxyz", "helpers"):
            (tmp_path / package).mkdir()
            (tmp_path / package / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "great-docs.yml").write_text("module: mypkgxyz\n", encoding="utf-8")
        gd = GreatDocs(project_path=str(tmp_path))
        # Two package directories and no `pyproject.toml` leave the package name undetected.
        assert make_project(gd).name is None

        candidates = _build_mcp_candidates(gd, monkeypatch)

        assert candidates == ["mypkgxyz.mcp", "mypkgxyz.mcp_server", "mypkgxyz.server"]

    @pytest.mark.parametrize("module", ["mcp", "mcp_server", "server"])
    def test_finds_server_module_in_package(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str
    ):
        """Each conventional server module in the package is discovered and introspected"""
        gd = _make_root_project(tmp_path)
        (tmp_path / "mypkgxyz" / f"{module}.py").write_text("", encoding="utf-8")
        monkeypatch.syspath_prepend(str(tmp_path))
        server_info: dict[str, object] = {"name": "mypkgxyz", "tools": []}

        with (
            patch.dict(sys.modules),
            patch(
                "great_docs._mcpref.reference.discover_mcp_server", return_value=server_info
            ) as discover,
        ):
            result = mcp_build.discover_server(gd._config, "mypkgxyz")

        assert result == server_info
        discover.assert_called_once_with(module_path=f"mypkgxyz.{module}", server_var=None)

    def test_configured_module_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """`mcp.module` takes precedence over conventional server modules"""
        gd = _make_root_project(tmp_path, "mcp:\n  module: elsewhere.tools\n")
        (tmp_path / "mypkgxyz" / "mcp.py").write_text("", encoding="utf-8")
        monkeypatch.syspath_prepend(str(tmp_path))

        with (
            patch.dict(sys.modules),
            patch(
                "great_docs._mcpref.reference.discover_mcp_server", return_value=None
            ) as discover,
        ):
            mcp_build.discover_server(gd._config, "mypkgxyz")

        discover.assert_called_once_with(module_path="elsewhere.tools", server_var=None)

    def test_without_package_reports_no_server(self, tmp_path: Path):
        """With no package and no `mcp.module`, discovery introspects nothing and returns `None`"""
        gd = _make_root_project(tmp_path)

        with patch("great_docs._mcpref.reference.discover_mcp_server") as discover:
            result = mcp_build.discover_server(gd._config, None)

        assert result is None
        discover.assert_not_called()


class TestBuildMcpReference:
    def test_passes_metadata_and_language(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        gd = _make_gd(tmp_path)
        gd._config._config["site"]["lang"] = "fr"
        gd._config._config["site_url"] = "https://example.org"
        pages: dict[str, object] = {}
        manifest: dict[str, object] = {}

        def fake_pages(**kwargs):
            pages.update(kwargs)
            return ["reference/mcp/tool.qmd"]

        def fake_manifest(**kwargs):
            manifest.update(kwargs)

        monkeypatch.setattr("great_docs._mcpref.reference.generate_mcp_reference_pages", fake_pages)
        monkeypatch.setattr("great_docs._mcpref.reference.generate_mcp_manifest", fake_manifest)
        server = {"name": "test", "tools": []}

        files = mcp_build.build_mcp_reference(
            gd._config, server, gd.build_dir, "mypkg", "https://github.com/owner/repo"
        )

        assert files == ["reference/mcp/tool.qmd"]
        assert pages["language"] == "fr"
        assert manifest["package_name"] == "mypkg"
        assert manifest["repo_url"] == "https://github.com/owner/repo"
        assert manifest["site_url"] == "https://example.org"
        assert manifest["server_info"] == server


class TestMcpContribution:
    def test_index_link_precedes_the_pages(self):
        contribution = mcp_build.contribution(mock_config(lang="en"), ["reference/mcp/tool.qmd"])

        assert contribution == Contribution(
            sidebars=(
                Sidebar(
                    id="mcp-reference",
                    title="MCP Reference",
                    contents=(
                        {"text": "MCP Index", "href": "reference/mcp/index.qmd"},
                        "reference/mcp/tool.qmd",
                    ),
                ),
            )
        )

    def test_translated_site_labels_the_index_with_the_title(self):
        (sidebar,) = mcp_build.contribution(mock_config(lang="fr"), []).sidebars

        assert sidebar.title == "Référence MCP"
        assert sidebar.contents == ({"text": "Référence MCP", "href": "reference/mcp/index.qmd"},)


class TestCliContribution:
    def test_sidebar_and_reference_link(self):
        items = [{"text": "CLI Index", "href": "reference/cli/index.qmd"}, "reference/cli/app.qmd"]

        contribution = cli_render.contribution(mock_config(lang="en"), items)

        assert contribution == Contribution(
            navbar=(NavbarLink("Reference", "reference/cli/index.qmd"),),
            sidebars=(Sidebar("cli-reference", "CLI Reference", tuple(items)),),
        )

    def test_configured_title_names_the_sidebar(self):
        config = mock_config(lang="fr", cli_title="Commandes")

        (sidebar,) = cli_render.contribution(config, ["reference/cli/app.qmd"]).sidebars

        assert sidebar.title == "Commandes"


class TestDiscoverExportsValidation:
    """Export validation for unresolved aliases and external re-exports"""

    def _setup(self, tmp_path, monkeypatch):
        """Set up a GreatDocs instance with mocked griffe package."""
        gd = _make_gd(tmp_path)
        return gd

    def _make_mock_pkg(self, members_dict, exports=None):
        """Build a mock griffe package with controlled members."""
        pkg = MagicMock()
        pkg.path = "mypkg"
        pkg.members = members_dict
        pkg.exports = exports
        return pkg

    def test_not_found_in_pkg_members(self, tmp_path, monkeypatch):
        """Verify that undefined names are excluded from discovered exports"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        good_obj = MagicMock()
        good_obj.kind = griffe.Kind.FUNCTION
        good_obj.members = {}
        good_obj.is_alias = False
        pkg = self._make_mock_pkg(
            {"good_func": good_obj},
            exports=["good_func", "MissingClass"],
        )
        result = discover_exports(pkg, gd._config, report=print)
        assert result is not None
        assert "good_func" in result
        assert "MissingClass" not in result

    def test_cyclic_alias_on_kind(self, tmp_path, monkeypatch):
        """Verify that a cyclic alias is excluded during kind lookup"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = self._make_mock_pkg({"BadAlias": obj}, exports=["BadAlias"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_alias_resolution_error_on_kind(self, tmp_path, monkeypatch):
        """Verify that an unresolved alias is excluded during kind lookup"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.AliasResolutionError(MagicMock()))
        )
        pkg = self._make_mock_pkg({"Unresolvable": obj}, exports=["Unresolvable"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_key_error_on_kind(self, tmp_path, monkeypatch):
        """Verify that an object missing from the static model is excluded"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(KeyError("missing")))
        pkg = self._make_mock_pkg({"RustObj": obj}, exports=["RustObj"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_unexpected_error_on_kind_propagates(self, tmp_path, monkeypatch):
        """Verify that unexpected errors reading an object kind propagate"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(RuntimeError("oops")))
        pkg = self._make_mock_pkg({"Broken": obj}, exports=["Broken"])
        with pytest.raises(RuntimeError, match="oops"):
            discover_exports(pkg, gd._config, report=print)

    def test_module_kind_passes_without_members_check(self, tmp_path, monkeypatch):
        """Verify that module exports are retained without resolving their members"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.MODULE
        obj.is_alias = False
        pkg = self._make_mock_pkg({"submod": obj}, exports=["submod"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result is not None
        assert "submod" in result

    def test_cyclic_alias_on_members_access(self, tmp_path, monkeypatch):
        """Verify that a cycle during member lookup excludes the export"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.CLASS
        type(obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = self._make_mock_pkg({"CyclicClass": obj}, exports=["CyclicClass"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_alias_resolution_error_on_members_access(self, tmp_path, monkeypatch):
        """Verify that an alias failure during member lookup excludes the export"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.CLASS
        type(obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.AliasResolutionError(MagicMock()))
        )
        pkg = self._make_mock_pkg({"Unresolvable": obj}, exports=["Unresolvable"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_unexpected_error_on_members_access_propagates(self, tmp_path, monkeypatch):
        """Verify that unexpected errors reading members propagate"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.CLASS
        type(obj).members = property(lambda s: (_ for _ in ()).throw(TypeError("bad")))
        pkg = self._make_mock_pkg({"BadClass": obj}, exports=["BadClass"])
        with pytest.raises(TypeError, match="bad"):
            discover_exports(pkg, gd._config, report=print)

    def test_external_re_export_excluded(self, tmp_path, monkeypatch):
        """Verify that aliases to external packages are excluded"""
        gd = self._setup(tmp_path, monkeypatch)
        import griffe

        obj = MagicMock(spec=griffe.Alias)
        obj.kind = griffe.Kind.CLASS
        obj.members = {}
        obj.canonical_path = "other_package.SomeClass"
        pkg = self._make_mock_pkg({"SomeClass": obj}, exports=["SomeClass"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result == []

    def test_internal_alias_passes(self, tmp_path, monkeypatch):
        """Verify that aliases within the package are retained"""
        gd = self._setup(tmp_path, monkeypatch)
        import griffe

        obj = MagicMock(spec=griffe.Alias)
        obj.kind = griffe.Kind.CLASS
        obj.members = {}
        obj.canonical_path = "mypkg.internal.MyClass"
        pkg = self._make_mock_pkg({"MyClass": obj}, exports=["MyClass"])
        result = discover_exports(pkg, gd._config, report=print)
        assert result is not None
        assert "MyClass" in result


class TestCategoriseReferences:
    """Reference classification and missing-name handling"""

    def _setup(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        return gd

    def test_non_dict_section_skipped(self, tmp_path, monkeypatch):
        """Verify that reference sections other than dictionaries are ignored"""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        result = categorise_references(pkg, ["not_a_dict", {"contents": []}])
        assert result["other"] == []

    def test_classifies_function(self, tmp_path, monkeypatch):
        """Verify that functions are grouped under `functions`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"my_func": obj}
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "function")
        result = categorise_references(pkg, [{"contents": ["my_func"]}])
        assert "my_func" in result["functions"]

    def test_classifies_async_function(self, tmp_path, monkeypatch):
        """Verify that asynchronous functions are grouped under `async_functions`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = {"async"}
        pkg = MagicMock()
        pkg.members = {"afunc": obj}
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "async")
        result = categorise_references(pkg, [{"contents": ["afunc"]}])
        assert "afunc" in result["async_functions"]

    def test_classifies_class_as_dataclass(self, tmp_path, monkeypatch):
        """Verify that dataclasses are grouped under `dataclasses`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.CLASS
        obj.members = {"__init__": MagicMock()}
        obj.members["__init__"].kind.value = "function"
        pkg = MagicMock()
        pkg.members = {"MyDC": obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "dataclass")
        result = categorise_references(pkg, [{"contents": ["MyDC"]}])
        assert "MyDC" in result["dataclasses"]

    def test_classifies_attribute_as_constant(self, tmp_path, monkeypatch):
        """Verify that ordinary attributes are grouped under `constants`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.ATTRIBUTE
        obj.labels = set()
        obj.annotation = None
        pkg = MagicMock()
        pkg.members = {"MY_CONST": obj}
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "constant")
        result = categorise_references(pkg, [{"contents": ["MY_CONST"]}])
        assert "MY_CONST" in result["constants"]

    def test_classifies_type_alias(self, tmp_path, monkeypatch):
        """Verify that type aliases are grouped under `type_aliases`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.TYPE_ALIAS
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"MyAlias": obj}
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "typealias")
        result = categorise_references(pkg, [{"contents": ["MyAlias"]}])
        assert "MyAlias" in result["type_aliases"]

    def test_cyclic_alias_on_kind_goes_to_other(self, tmp_path, monkeypatch):
        """Verify that configured cyclic aliases are grouped under `other`"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = MagicMock()
        pkg.members = {"CyclicThing": obj}
        result = categorise_references(pkg, [{"contents": ["CyclicThing"]}])
        assert "CyclicThing" in result["other"]

    def test_unexpected_error_on_kind_propagates(self, tmp_path, monkeypatch):
        """Verify that unexpected errors reading an object kind propagate"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))
        pkg = MagicMock()
        pkg.members = {"BrokenObj": obj}
        with pytest.raises(ValueError, match="bad"):
            categorise_references(pkg, [{"contents": ["BrokenObj"]}])

    def test_missing_name_with_installed_package_raises(self, tmp_path, monkeypatch):
        """Verify that an installed package missing a configured name raises `BuildError`"""
        import pytest

        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr("importlib.metadata.version", lambda name: "1.2.3")
        from great_docs import BuildError

        with pytest.raises(BuildError, match="not found"):
            categorise_references(pkg, [{"contents": ["Missing"]}])

    def test_missing_name_uninstalled_package_goes_to_other(self, tmp_path, monkeypatch):
        """Verify that missing names are grouped under `other` for an uninstalled package"""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(
            "importlib.metadata.version",
            lambda name: (_ for _ in ()).throw(importlib.metadata.PackageNotFoundError(name)),
        )
        result = categorise_references(pkg, [{"contents": ["Missing"]}])
        assert "Missing" in result["other"]

    def test_class_method_counting(self, tmp_path, monkeypatch):
        """Verify that public methods contribute to the class method count"""
        gd = self._setup(tmp_path, monkeypatch)

        method_obj = MagicMock()
        method_obj.kind = griffe.Kind.FUNCTION

        private_obj = MagicMock()
        private_obj.kind = griffe.Kind.FUNCTION

        prop_obj = MagicMock()
        prop_obj.kind = griffe.Kind.ATTRIBUTE
        prop_obj.labels = {"property"}

        cls_obj = MagicMock()
        cls_obj.kind = griffe.Kind.CLASS
        cls_obj.members = {
            "do_stuff": method_obj,
            "_private": private_obj,
            "value": prop_obj,
        }

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 2
        assert "do_stuff" in result["class_method_names"]["MyClass"]
        assert "value" in result["class_method_names"]["MyClass"]
        assert "_private" not in result["class_method_names"]["MyClass"]

    def test_class_member_cyclic_alias_skipped(self, tmp_path, monkeypatch):
        """Verify that class members with cyclic aliases are excluded"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        cls_obj = MagicMock()
        cls_obj.kind = griffe.Kind.CLASS
        cls_obj.members = {"bad_member": bad_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_module_kind_expands_members(self, tmp_path, monkeypatch):
        """Verify that listed modules expand to qualified member names"""
        gd = self._setup(tmp_path, monkeypatch)

        sub_class = MagicMock()
        sub_class.kind = griffe.Kind.CLASS
        sub_func = MagicMock()
        sub_func.kind = griffe.Kind.FUNCTION
        sub_attr = MagicMock()
        sub_attr.kind = griffe.Kind.ATTRIBUTE

        mod_obj = MagicMock()
        mod_obj.kind = griffe.Kind.MODULE
        mod_obj.members = {
            "SubClass": sub_class,
            "sub_func": sub_func,
            "CONST": sub_attr,
            "_private": MagicMock(),
        }

        anchor_cls = MagicMock()
        anchor_cls.kind = griffe.Kind.CLASS
        anchor_cls.members = {}
        anchor_cls.labels = set()
        anchor_cls.bases = []

        pkg = MagicMock()
        pkg.members = {"AClass": anchor_cls, "mymod": mod_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["AClass", "mymod"]}])
        assert "mymod.SubClass" in result["classes"]
        assert "mymod.sub_func" in result["functions"]
        assert "mymod.CONST" in result["constants"]

    def test_module_expansion_without_top_level_class(self, tmp_path, monkeypatch):
        """Verify that a listed module contributes its classes and subsequent members"""
        gd = self._setup(tmp_path, monkeypatch)

        def _member(kind):
            m = MagicMock()
            m.kind = griffe.Kind(kind)
            return m

        mod_obj = MagicMock()
        mod_obj.kind = griffe.Kind.MODULE
        # Dict order is the order the expansion visits the members in.
        mod_obj.members = {
            "AFunc": _member("function"),
            "BDataclass": _member("class"),
            "CPlain": _member("class"),
            "DFunc": _member("function"),
            "E_CONST": _member("attribute"),
        }

        pkg = MagicMock()
        pkg.members = {"mymod": mod_obj}
        monkeypatch.setattr(
            "great_docs._reference.discovery.class_kind",
            lambda o: "dataclass" if o is mod_obj.members["BDataclass"] else "class",
        )
        result = categorise_references(pkg, [{"contents": ["mymod"]}])
        assert "mymod.BDataclass" in result["dataclasses"]
        assert "mymod.CPlain" in result["classes"]
        assert "mymod.AFunc" in result["functions"]
        assert "mymod.DFunc" in result["functions"]
        assert "mymod.E_CONST" in result["constants"]

    def test_module_member_cyclic_alias_skipped(self, tmp_path, monkeypatch):
        """Verify that module members with cyclic aliases are excluded"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        mod_obj = MagicMock()
        mod_obj.kind = griffe.Kind.MODULE
        mod_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"mymod": mod_obj}
        result = categorise_references(pkg, [{"contents": ["mymod"]}])
        assert "mymod.broken" not in result.get("other", [])

    def test_module_members_iteration_raises(self, tmp_path, monkeypatch):
        """Verify that an unresolved module contributes no members"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        mod_obj = MagicMock()
        mod_obj.kind = griffe.Kind.MODULE
        type(mod_obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        pkg = MagicMock()
        pkg.members = {"mymod": mod_obj}
        result = categorise_references(pkg, [{"contents": ["mymod"]}])
        assert "mymod" not in result.get("classes", [])

    def test_dict_item_in_contents(self, tmp_path, monkeypatch):
        """Verify that reference dictionaries identify objects through `name`"""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"named_func": obj}
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "function")
        result = categorise_references(pkg, [{"contents": [{"name": "named_func"}]}])
        assert "named_func" in result["functions"]

    def test_class_property_member_counted(self, tmp_path, monkeypatch):
        """Verify that properties contribute to the class method count"""
        gd = self._setup(tmp_path, monkeypatch)

        prop_member = MagicMock()
        prop_member.kind = griffe.Kind.ATTRIBUTE
        prop_member.labels = {"property"}

        cls_obj = MagicMock()
        cls_obj.kind = griffe.Kind.CLASS
        cls_obj.members = {"name": prop_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 1
        assert "name" in result["class_method_names"]["MyClass"]

    def test_class_init_dunder_skipped(self, tmp_path, monkeypatch):
        """Verify that constructors are excluded from the class method count"""
        gd = self._setup(tmp_path, monkeypatch)

        init_member = MagicMock()
        init_member.kind = griffe.Kind.FUNCTION

        public_method = MagicMock()
        public_method.kind = griffe.Kind.FUNCTION

        cls_obj = MagicMock()
        cls_obj.kind = griffe.Kind.CLASS
        cls_obj.members = {"__init__": init_member, "run": public_method}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 1
        assert "run" in result["class_method_names"]["MyClass"]
        assert "__init__" not in result["class_method_names"]["MyClass"]

    def test_class_members_outer_cyclic_alias(self, tmp_path, monkeypatch):
        """Verify that a cycle while listing class members yields no methods"""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        class _BadItems(dict):
            def items(self):
                raise griffe.CyclicAliasError(["x", "y"])

        cls_obj = MagicMock()
        cls_obj.kind = griffe.Kind.CLASS
        cls_obj.members = _BadItems()

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_typevar_attribute(self, tmp_path, monkeypatch):
        """Verify that type variables are grouped under `type_aliases`"""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind = griffe.Kind.ATTRIBUTE
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"T": obj}
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "typevar")
        result = categorise_references(pkg, [{"contents": ["T"]}])
        assert "T" in result["type_aliases"]

    def test_other_kind_goes_to_other(self, tmp_path, monkeypatch):
        """Verify that unclassified objects are grouped under `other`"""
        gd = self._setup(tmp_path, monkeypatch)

        anchor = MagicMock()
        anchor.kind = griffe.Kind.CLASS
        anchor.members = {}

        obj = MagicMock()
        obj.kind = griffe.Kind.ALIAS

        pkg = MagicMock()
        pkg.members = {"AClass": anchor, "weird": obj}
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(pkg, [{"contents": ["AClass", "weird"]}])

        assert "weird" in result["other"]


# ---------------------------------------------------------------------------
# Parse Click help parts
# ---------------------------------------------------------------------------


class TestParseHelpParts:
    def test_empty_help(self):
        desc, examples = cli_click.parse_help_parts("")
        assert desc == ""
        assert examples == []

    def test_none_help(self):
        desc, examples = cli_click.parse_help_parts(None)
        assert desc == ""

    def test_description_only(self):
        desc, examples = cli_click.parse_help_parts("Build the docs site.")
        assert desc == "Build the docs site."
        assert examples == []

    def test_with_examples_block(self):
        help_text = (
            "Build the site.\n\nExamples:\n    great-docs build\n    great-docs build --watch\n"
        )
        desc, examples = cli_click.parse_help_parts(help_text)
        assert desc == "Build the site."
        assert "great-docs build" in examples[0]
        assert len(examples) == 2

    def test_backspace_marker_stripped(self):
        help_text = "Some text\n\x08\nMore text"
        desc, examples = cli_click.parse_help_parts(help_text)
        assert "\x08" not in desc
        assert "Some text" in desc

    def test_collapses_blank_lines(self):
        help_text = "Line one\n\n\n\nLine two"
        desc, _ = cli_click.parse_help_parts(help_text)
        assert "\n\n\n" not in desc

    def test_examples_dedented_4_spaces(self):
        help_text = "Desc\n\nExamples:\n    cmd --flag\n"
        _, examples = cli_click.parse_help_parts(help_text)
        assert examples[0] == "cmd --flag"

    def test_examples_dedented_2_spaces(self):
        help_text = "Desc\n\nExamples:\n  cmd --flag\n"
        _, examples = cli_click.parse_help_parts(help_text)
        assert examples[0] == "cmd --flag"

    def test_examples_trailing_blanks_trimmed(self):
        help_text = "Desc\n\nExamples:\n    cmd\n    \n"
        _, examples = cli_click.parse_help_parts(help_text)
        assert not examples[-1].strip() == ""


# ---------------------------------------------------------------------------
# Backtick CLI prose
# ---------------------------------------------------------------------------


class TestBacktickProse:
    def test_empty_returns_empty(self):
        assert cli_render.backtick_prose("", set()) == ""

    def test_wraps_single_quoted_text(self):
        result = cli_render.backtick_prose("Use 'great-docs/' for output", set())
        assert "`great-docs/`" in result

    def test_wraps_known_option(self):
        result = cli_render.backtick_prose("Use --watch for live reload", {"--watch"})
        assert "`--watch`" in result

    def test_avoids_possessives(self):
        result = cli_render.backtick_prose("The package's config", set())
        assert "`" not in result

    def test_already_backticked_not_doubled(self):
        result = cli_render.backtick_prose("Use `--watch` now", {"--watch"})
        assert result.count("`--watch`") == 1


# ---------------------------------------------------------------------------
# Empty categories
# ---------------------------------------------------------------------------


class TestEmptyCategories:
    def test_all_keys_present(self):
        cats = empty_categories()
        assert "classes" in cats
        assert "functions" in cats
        assert "constants" in cats
        assert "type_aliases" in cats
        assert cats["cyclic_alias_count"] == 0

    def test_returns_fresh_instance(self):
        a = empty_categories()
        b = empty_categories()
        a["classes"].append("X")
        assert b["classes"] == []


# ---------------------------------------------------------------------------
# Extract Click option / argument
# ---------------------------------------------------------------------------


class TestExtractOption:
    def test_basic_option(self):
        param = MagicMock()
        param.name = "verbose"
        param.opts = ["--verbose"]
        param.secondary_opts = ["-v"]
        param.type.name = "bool"
        param.default = None
        param.help = "Enable verbose output"
        param.required = False
        param.is_flag = True
        param.multiple = False
        param.envvar = None
        param.is_eager = False
        param.hidden = False
        param.show_default = False
        result = cli_click.extract_option(param)
        assert result["name_display"] == "-v, --verbose"
        assert result["help"] == "Enable verbose output"
        assert result["is_flag"] is True

    def test_help_option_skipped(self):
        param = MagicMock()
        param.name = "help"
        assert cli_click.extract_option(param) is None

    def test_type_name_uppercased(self):
        param = MagicMock()
        param.name = "port"
        param.opts = ["--port"]
        param.secondary_opts = []
        param.type.name = "int"
        param.default = 3000
        param.help = ""
        param.required = False
        param.is_flag = False
        param.multiple = False
        param.envvar = None
        param.is_eager = False
        param.hidden = False
        param.show_default = True
        result = cli_click.extract_option(param)
        assert result["type"] == "INT"
        assert result["default"] == 3000

    def test_sentinel_default_normalized(self):
        param = MagicMock()
        param.name = "output"
        param.opts = ["--output"]
        param.secondary_opts = []
        param.type.name = "text"
        sentinel = MagicMock()
        sentinel.__class__.__name__ = "Sentinel"
        param.default = sentinel
        param.help = ""
        param.required = False
        param.is_flag = False
        param.multiple = False
        param.envvar = None
        param.is_eager = False
        param.hidden = False
        result = cli_click.extract_option(param)
        assert result["default"] is None

    def test_choice_values_extracted(self):
        param = click.Option(["--format"], type=click.Choice(["json", "yaml"]))
        result = cli_click.extract_option(param)
        assert result["choices"] == ["json", "yaml"]

    def test_deprecation_message_extracted(self):
        param = click.Option(["--old"], help="Old behaviour.", deprecated="Use --new instead.")
        result = cli_click.extract_option(param)
        assert result["deprecated"] == "Use --new instead."
        # Removing Click's appended notice prevents the page from showing it twice.
        assert result["help"] == "Old behaviour."


class TestExtractArgument:
    def test_basic_argument(self):
        param = MagicMock()
        param.name = "path"
        param.human_readable_name = "PATH"
        param.type.name = "TEXT"
        param.required = True
        param.nargs = 1
        result = cli_click.extract_argument(param)
        assert result["name"] == "path"
        assert result["type"] is None
        assert result["required"] is True

    def test_non_text_type_uppercased(self):
        param = MagicMock()
        param.name = "count"
        param.human_readable_name = "COUNT"
        param.type.name = "int"
        param.required = False
        param.nargs = -1
        result = cli_click.extract_argument(param)
        assert result["type"] == "INT"
        assert result["nargs"] == -1


# ---------------------------------------------------------------------------
# Command pages with variadic arguments, hidden options, environment variables and defaults
# ---------------------------------------------------------------------------


class TestCommandPage:
    def _make_cli_info(self, **overrides):
        base = {
            "name": "mycli",
            "short_help": "A test CLI.",
            "description": "A test CLI for testing.",
            "options": [],
            "arguments": [],
            "commands": [],
        }
        base.update(overrides)
        return base

    def test_nargs_minus1_gets_ellipsis(self):
        cli_info = self._make_cli_info(
            arguments=[{"name": "FILES", "name_display": "FILES", "required": True, "nargs": -1}]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "FILES..." in result

    def test_hidden_option_skipped(self):
        cli_info = self._make_cli_info(
            options=[
                {"name": "--verbose", "name_display": "--verbose", "hidden": True, "help": "debug"},
                {
                    "name": "--output",
                    "name_display": "--output",
                    "hidden": False,
                    "help": "output file",
                },
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "output" in result
        assert "verbose" not in result

    def test_option_with_type_and_default(self):
        cli_info = self._make_cli_info(
            options=[
                {
                    "name": "--count",
                    "name_display": "--count",
                    "type": "INT",
                    "default": "5",
                    "is_flag": False,
                    "help": "Number of items",
                }
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "INT" in result
        assert "5" in result

    def test_required_option(self):
        cli_info = self._make_cli_info(
            options=[
                {
                    "name": "--name",
                    "name_display": "--name",
                    "required": True,
                    "help": "Your name",
                }
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "**Required.**" in result

    def test_envvar_option(self):
        cli_info = self._make_cli_info(
            options=[
                {
                    "name": "--token",
                    "name_display": "--token",
                    "envvar": "MY_TOKEN",
                    "help": "API token",
                }
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "`MY_TOKEN`" in result

    def test_envvar_list_joined(self):
        cli_info = self._make_cli_info(
            options=[
                {
                    "name": "--token",
                    "name_display": "--token",
                    "envvar": ["TOKEN_A", "TOKEN_B"],
                    "help": "API token",
                }
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert "TOKEN_A, TOKEN_B" in result

    def test_choice_values_shown_as_type(self):
        cli_info = self._make_cli_info(
            options=[
                {"names": ["--format"], "type": "CHOICE", "choices": ["json", "yaml"]},
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert '<span class="doc-parameter-annotation">[json|yaml]</span>' in result

    def test_deprecated_option_marked_with_message(self):
        cli_info = self._make_cli_info(
            options=[
                {
                    "names": ["--old"],
                    "name_display": "--old",
                    "deprecated": "Use --new instead.",
                    "help": "Old behaviour.",
                },
            ]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert ":   **Deprecated.** Use --new instead.\\\n    Old behaviour." in result

    def test_deprecated_command_gets_warning_callout(self):
        cli_info = self._make_cli_info(deprecated="Use `mycli run` instead.")
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert '::: {.callout-warning title="Deprecated"}\nUse `mycli run` instead.\n:::' in result

    def test_argument_help_rendered(self):
        cli_info = self._make_cli_info(
            arguments=[{"name": "input", "required": True, "help": "The file to read."}]
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert ":   Required. The file to read." in result

    def test_parameter_markup_characters_escaped(self):
        # A clap option's name carries its value name, as in `--config <PATH>`.
        cli_info = self._make_cli_info(
            arguments=[{"name": "src", "name_display": "<src>", "type": "<T>"}],
            options=[
                {
                    "name_display": "-c, --config <PATH>",
                    "type": "A&B",
                    "default": "<stdin>",
                    "is_flag": False,
                }
            ],
        )
        result = cli_render.command_page(mock_config(lang="en"), cli_info, is_main=True)
        assert '<span class="doc-parameter-name">&lt;SRC&gt;</span>' in result
        assert '<span class="doc-parameter-annotation">&lt;T&gt;</span>' in result
        assert "-c, &#45;&#45;config &lt;PATH&gt;</span>" in result
        assert '<span class="doc-parameter-annotation">A&amp;B</span>' in result
        assert '<span class="doc-parameter-default">&lt;stdin&gt;</span>' in result

    def test_index_title_with_quotes_is_valid_yaml(self):
        config = mock_config(lang="en", cli_title='The "gd" tool')
        page = cli_render.index_page(config, self._make_cli_info(), "mycli")
        front_matter = page.split("---\n")[1]
        assert yaml.safe_load(front_matter)["title"] == 'The "gd" tool'

    def test_pages_written_as_utf8_whatever_the_locale(self, tmp_path, monkeypatch):
        # Stand in for a locale whose code page lacks `•`, such as cp1252 on Windows.
        monkeypatch.setattr(io, "text_encoding", lambda encoding, stacklevel=2: encoding or "ascii")
        sub = self._make_cli_info(
            name="sub", full_path="mycli sub", short_help="Run • fast.", description="Run • fast."
        )
        cli_info = self._make_cli_info(description="Root • tool.", commands=[sub])
        cli_render.write_pages(mock_config(lang="en"), tmp_path, cli_info, report=lambda _: None)
        cli_dir = tmp_path / "reference" / "cli"
        assert "Run • fast." in (cli_dir / "index.qmd").read_text(encoding="utf-8")
        assert "Root • tool." in (cli_dir / "mycli.qmd").read_text(encoding="utf-8")
        assert "Run • fast." in (cli_dir / "sub.qmd").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Labelled sidebar links
# ---------------------------------------------------------------------------


class TestCountPages:
    def test_string_items_counted(self):
        assert cli_render.count_pages(["a.qmd", "b.qmd"]) == 2

    def test_dict_with_href_counted_as_one(self):
        items = [{"text": "Index", "href": "index.qmd"}]
        assert cli_render.count_pages(items) == 1

    def test_nested_contents(self):
        items = [{"contents": ["a.qmd", "b.qmd"]}]
        assert cli_render.count_pages(items) == 2


# ---------------------------------------------------------------------------
# Crawler rules, sitemap references and AI context file references
# ---------------------------------------------------------------------------


class TestRobotsWrite:
    def _setup_gd(self, tmp_path, monkeypatch, **config_overrides):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        site_dir = gd.build_dir / "_site"
        site_dir.mkdir()
        _patch_cfg(monkeypatch, gd, "robots_enabled", True)
        _patch_cfg(monkeypatch, gd, "robots_allow_all", True)
        _patch_cfg(monkeypatch, gd, "robots_disallow", [])
        _patch_cfg(monkeypatch, gd, "robots_crawl_delay", None)
        _patch_cfg(monkeypatch, gd, "robots_extra_rules", [])
        _patch_cfg(monkeypatch, gd, "sitemap_enabled", False)
        for k, v in config_overrides.items():
            _patch_cfg(monkeypatch, gd, k, v)
        return gd, site_dir

    def test_basic_robots_txt(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch)
        robots.write(site_dir, gd._config, None, report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "Allow: /" in content

    def test_no_site_dir_skips(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "robots_enabled", True)
        site_dir = gd.build_dir / "_site"
        robots.write(site_dir, gd._config, None, report=print)
        assert not (site_dir / "robots.txt").exists()

    def test_disallow_rules(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(
            tmp_path, monkeypatch, robots_disallow=["/private/", "/admin/"]
        )
        robots.write(site_dir, gd._config, None, report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "Disallow: /private/" in content
        assert "Disallow: /admin/" in content

    def test_extra_rules(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(
            tmp_path,
            monkeypatch,
            robots_extra_rules=["User-agent: GPTBot", "Disallow: /"],
        )
        robots.write(site_dir, gd._config, None, report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "User-agent: GPTBot" in content

    def test_sitemap_reference(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch, sitemap_enabled=True)
        robots.write(site_dir, gd._config, "https://example.com/", report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "Sitemap: https://example.com/sitemap.xml" in content

    def test_llms_txt_references(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch)
        (site_dir / "llms.txt").write_text("llms content", encoding="utf-8")
        (site_dir / "llms-full.txt").write_text("full content", encoding="utf-8")
        robots.write(site_dir, gd._config, "https://example.com/", report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "Llms-txt: https://example.com/llms.txt" in content
        assert "Llms-txt: https://example.com/llms-full.txt" in content

    def test_llms_txt_only_one(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch)
        (site_dir / "llms.txt").write_text("llms content", encoding="utf-8")
        robots.write(site_dir, gd._config, "https://example.com/", report=print)
        content = (site_dir / "robots.txt").read_text()
        assert "Llms-txt: https://example.com/llms.txt" in content
        assert "llms-full.txt" not in content


class TestCanonicalIntegration:
    """`GreatDocs` supplies the repository and build directory to the canonical code."""

    def test_base_url_falls_back_to_the_github_pages_address(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _put_on_github(tmp_path)
        assert (
            site.identity(gd._config, gd.layout, make_project(gd)).base_url
            == "https://acme.github.io/mypkg/"
        )

    def test_raw_custom_page_gets_a_canonical_link(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        _put_on_github(tmp_path)
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        custom_pages_step(gd, discover_user_guide(gd))

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert (
            '<link rel="canonical" href="https://acme.github.io/mypkg/custom/widget.html">' in page
        )

    def test_raw_custom_reference_page_gets_structured_data(self, tmp_path):
        (tmp_path / "great-docs.yml").write_text(
            "module: mypkg\ndisplay_name: Pkg\ncustom_pages:\n  - dir: custom\n    output: reference\n",
            encoding="utf-8",
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "demo.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        custom_pages_step(gd, discover_user_guide(gd))

        page = (gd.build_dir / "reference" / "demo.html").read_text(encoding="utf-8")
        assert page.count('<script type="application/ld+json">') == 1
        assert '"name": "demo - Pkg"' in page

    @pytest.mark.parametrize("seo", ["true", "false"])
    def test_raw_custom_page_gets_social_cards(self, tmp_path, monkeypatch, seo):
        (tmp_path / "great-docs.yml").write_text(
            f"module: mypkg\ndisplay_name: Pkg\nseo:\n  enabled: {seo}\n", encoding="utf-8"
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        _put_on_github(tmp_path)
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head><title>Widget Lab</title></head></html>",
            encoding="utf-8",
        )

        custom_pages_step(gd, discover_user_guide(gd))

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert page.count('<meta property="og:title" content="Widget Lab">') == 1
        assert '<meta property="og:site_name" content="Pkg">' in page
        assert (
            '<meta property="og:url" content="https://acme.github.io/mypkg/custom/widget.html">'
            in page
        )
        assert '<meta name="twitter:card" content="summary">' in page

    def test_raw_custom_page_gets_the_translation_bundle(self, tmp_path):
        (tmp_path / "great-docs.yml").write_text(
            "module: mypkg\nsite:\n  lang: fr\n", encoding="utf-8"
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        custom_pages_step(gd, discover_user_guide(gd))

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert page.count('<meta name="gd-i18n"') == 1


class TestPageDescriptions:
    """`GreatDocs` writes a search description into each page before rendering."""

    LONG = "This page explains how the package adds numbers together."

    def _gd(self, tmp_path: Path, monkeypatch, *, default: str | None = "Site default"):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        _patch_cfg(monkeypatch, gd, "seo_default_description", default)
        return gd

    def test_pages_get_their_opening_paragraph_or_the_default(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        prose = gd.build_dir / "guide.qmd"
        prose.write_text(f"---\ntitle: Guide\n---\n\n{self.LONG}\n", encoding="utf-8")
        code = gd.build_dir / "code.qmd"
        code.write_text("```python\nx = 1\n```\n", encoding="utf-8")

        freeze_cache_step(gd)

        assert f"description-meta: {self.LONG}" in prose.read_text(encoding="utf-8")
        assert "description-meta: Site default" in code.read_text(encoding="utf-8")

    def test_nothing_is_written_when_seo_and_social_cards_are_disabled(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "seo_enabled", False)
        _patch_cfg(monkeypatch, gd, "social_cards_enabled", False)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"{self.LONG}\n", encoding="utf-8")

        freeze_cache_step(gd)

        assert "description-meta" not in page.read_text(encoding="utf-8")

    def test_versioned_sites_are_described_per_version(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "has_versions", True)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"{self.LONG}\n", encoding="utf-8")

        freeze_cache_step(gd)

        assert "description-meta" not in page.read_text(encoding="utf-8")

    def test_versioned_sites_are_described_when_watching(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "has_versions", True)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"---\nscale-to-fit: [.wide]\n---\n\n{self.LONG}\n", encoding="utf-8")

        freeze_cache_step(gd, watch=True)

        content = page.read_text(encoding="utf-8")
        assert "description-meta" in content
        assert "gd-scale-to-fit-page" in content

    def test_default_falls_back_to_the_package_description(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch, default=None)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\ndescription = "From `pyproject`"\n', encoding="utf-8"
        )

        assert site.default_description(gd._config, make_project(gd)) == "From pyproject"

    def test_raw_custom_page_gets_the_default(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch, default="Tom & Jerry")
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        custom_pages_step(gd, discover_user_guide(gd))

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert page.count('<meta name="description" content="Tom &amp; Jerry">') == 1


# ---------------------------------------------------------------------------
# Freeze cache merging and JavaScript newlines
# ---------------------------------------------------------------------------


def _historical_cache(root: Path, name: str) -> Path:
    """
    Create an empty freeze cache in a recognised historical build directory

    Parameters
    ----------
    root
        The project root containing root-layout build directories.
    name
        The build directory's name.

    Returns
    -------
    :
        The build's freeze cache directory.
    """
    build = root / name
    build.mkdir()
    (build / "_quarto.yml").write_text(QUARTO_YML_HEADER, encoding="utf-8")
    cache = build / "_freeze"
    cache.mkdir()
    return cache


class TestSaveFreezeCache:
    def test_no_freeze_sources_returns_none(self, tmp_path):
        gd = _make_gd(tmp_path)
        assert freeze.save(gd.layout) is None

    def test_merges_freeze_caches(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (_historical_cache(tmp_path, "great-docs-v1") / "page1.json").write_text('{"v": 1}')
        (_historical_cache(tmp_path, "great-docs-v2") / "page1.json").write_text('{"v": 2}')

        assert freeze.save(gd.layout) == 1
        merged = tmp_path / "_freeze" / "page1.json"
        assert '"v": 2' in merged.read_text()

    def test_js_newline_appended(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (_historical_cache(tmp_path, "great-docs-v1") / "chunk.js").write_bytes(b"var x = 1;")

        freeze.save(gd.layout)
        merged_js = tmp_path / "_freeze" / "chunk.js"
        assert merged_js.read_bytes().endswith(b"\n")


def test_constructing_a_project_runs_no_git(tmp_path: Path):
    """
    Create a project without running `git`
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

    with patch("subprocess.run") as run:
        GreatDocs(project_path=str(tmp_path))

    run.assert_not_called()
