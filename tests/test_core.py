# pyright: reportPrivateUsage=false
"""Tests for great_docs.core (GreatDocs class)."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import griffe
import pytest

from great_docs import GreatDocs
from great_docs._build import freeze
from great_docs._mcpref import build as mcp_build
from great_docs._reference import block as reference_block
from great_docs._reference.discovery import (
    categorise_references,
    discover_exports,
    empty_categories,
)
from great_docs._utils import QUARTO_YML_HEADER
from great_docs._website import quarto_yml as quarto_yml_file
from great_docs._website.seo import robots
from tests.support import StubRemote, make_run


def _make_gd(tmp_path: Path) -> GreatDocs:
    """Create a GreatDocs instance in a temp directory with minimal config."""
    (tmp_path / "great-docs.yml").write_text("module: mypkg\n", encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def _patch_cfg(monkeypatch, gd, name, value):
    """Patch a Config property on the class so the instance returns *value*."""
    monkeypatch.setattr(type(gd._config), name, property(lambda self: value))


class TestFindClickCliObj:
    """Cover all branches of _find_click_cli_obj."""

    def test_cli_not_enabled_returns_none(self, tmp_path, monkeypatch):
        """cli_enabled=False returns None."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"cli_enabled": False})
        assert gd._find_click_cli_obj("mypkg") is None

    def test_click_not_installed_returns_none(self, tmp_path, monkeypatch):
        """ImportError on click returns None."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"cli_enabled": True})

        import sys

        click_mod = sys.modules.pop("click", None)
        click_testing = sys.modules.pop("click.testing", None)
        click_keys = [k for k in sys.modules if k.startswith("click")]
        hidden = {k: sys.modules.pop(k) for k in click_keys}
        try:
            with patch("builtins.__import__", side_effect=ImportError("no click")):
                result = gd._find_click_cli_obj("mypkg")
            assert result is None
        finally:
            if click_mod:
                sys.modules["click"] = click_mod
            if click_testing:
                sys.modules["click.testing"] = click_testing
            sys.modules.update(hidden)

    def test_no_cli_module_auto_discovers(self, tmp_path, monkeypatch):
        """auto-discovers CLI module from common names."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"cli_enabled": True})

        real_import = importlib.import_module

        def fail_import(name, *args, **kwargs):
            if name in ("mypkg.cli", "mypkg.__main__", "mypkg.main"):
                raise ImportError(f"no module {name}")
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=fail_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is None

    def test_auto_discovers_module_with_click_obj(self, tmp_path, monkeypatch):
        """finds a module with a Click command."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"cli_enabled": True})

        fake_mod = types.ModuleType("mypkg.cli")
        fake_cmd = click.Command("test")
        fake_mod.cli = fake_cmd

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is fake_cmd

    def test_explicit_cli_module_import_fails(self, tmp_path, monkeypatch):
        """explicit cli_module can't be imported returns None."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"cli_enabled": True, "cli_module": "mypkg.custom_cli"},
        )

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.custom_cli":
                raise ImportError("no such module")
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is None

    def test_explicit_cli_name_found(self, tmp_path, monkeypatch):
        """metadata has cli_name and it's found."""
        gd = _make_gd(tmp_path)
        fake_mod = types.ModuleType("mypkg.custom_cli")
        fake_cmd = click.Command("mycmd")
        fake_mod.mycmd = fake_cmd

        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"cli_enabled": True, "cli_module": "mypkg.custom_cli", "cli_name": "mycmd"},
        )

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.custom_cli":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is fake_cmd

    def test_common_attr_names_found(self, tmp_path, monkeypatch):
        """finds click obj via common attr names (cli/main/app)."""
        gd = _make_gd(tmp_path)
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_group = click.Group("main")
        fake_mod.main = fake_group

        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"cli_enabled": True, "cli_module": "mypkg.cli_mod"},
        )

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is fake_group

    def test_scan_all_attrs_fallback(self, tmp_path, monkeypatch):
        """scans all module attrs to find click command."""
        gd = _make_gd(tmp_path)
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_cmd = click.Command("hidden_cmd")
        fake_mod.my_special_command = fake_cmd

        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"cli_enabled": True, "cli_module": "mypkg.cli_mod"},
        )

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
        assert result is fake_cmd

    def test_no_click_obj_found_returns_none(self, tmp_path, monkeypatch):
        """no Click object found at all returns None."""
        gd = _make_gd(tmp_path)
        fake_mod = types.ModuleType("mypkg.cli_mod")
        fake_mod.something = "not a click command"

        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"cli_enabled": True, "cli_module": "mypkg.cli_mod"},
        )

        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.cli_mod":
                return fake_mod
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = gd._find_click_cli_obj("mypkg")
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

    def stop_build(has_api_reference: bool) -> None:
        raise McpStepPassed

    monkeypatch.setattr("great_docs._build.quarto.ensure_installed", lambda: None)
    monkeypatch.setattr(importlib, "import_module", record_import)
    # The user guide is the first step after MCP discovery.
    monkeypatch.setattr(gd, "_process_user_guide", stop_build)
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
        assert gd._detect_package_name() is None

        def no_terminal(prompt: str) -> str:
            raise EOFError

        # Closed standard input keeps the package-name prompt from blocking the test.
        monkeypatch.setattr("builtins.input", no_terminal)
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


class TestUpdateSidebarWithMcp:
    """Cover _update_sidebar_with_mcp branching."""

    def test_empty_mcp_files_returns_early(self, tmp_path):
        """empty list returns immediately."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text("website:\n  sidebar: []\n", encoding="utf-8")
        gd._update_sidebar_with_mcp([])
        content = quarto_yml.read_text()
        assert "mcp-reference" not in content

    def test_no_quarto_yml_returns_early(self, tmp_path):
        """no _quarto.yml returns."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        gd._update_sidebar_with_mcp(["reference/mcp/tools.qmd"])

    def test_adds_mcp_section_to_sidebar(self, tmp_path, monkeypatch):
        """creates MCP section in sidebar and writes."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n  sidebar:\n    - id: api-reference\n      contents: []\n",
            encoding="utf-8",
        )

        mcp_files = ["reference/mcp/tools.qmd", "reference/mcp/resources.qmd"]
        gd._update_sidebar_with_mcp(mcp_files)

        sidebar = quarto_yml_file.read(gd.build_dir)["website"]["sidebar"]
        mcp_section = next(s for s in sidebar if s.get("id") == "mcp-reference")
        assert "MCP Reference" in mcp_section["title"]

    def test_sidebar_uses_site_language(self, tmp_path: Path):
        (tmp_path / "great-docs.yml").write_text(
            "module: mypkg\nsite:\n  lang: fr\n", encoding="utf-8"
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text("website:\n  sidebar: []\n", encoding="utf-8")

        gd._update_sidebar_with_mcp(["reference/mcp/tool.qmd"])

        sections = quarto_yml_file.read(gd.build_dir)["website"]["sidebar"]
        section = next(item for item in sections if item.get("id") == "mcp-reference")
        assert section["title"] == "Référence MCP"

    def test_updates_existing_mcp_section(self, tmp_path, monkeypatch):
        """existing mcp-reference section gets updated."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n  sidebar:\n    - id: mcp-reference\n      title: MCP Reference\n      contents:\n        - old.qmd\n",
            encoding="utf-8",
        )

        new_files = ["new-tools.qmd"]
        gd._update_sidebar_with_mcp(new_files)

        sidebar = quarto_yml_file.read(gd.build_dir)["website"]["sidebar"]
        mcp_section = next(s for s in sidebar if s.get("id") == "mcp-reference")
        assert mcp_section["contents"] == new_files

    def test_creates_website_and_sidebar_keys(self, tmp_path, monkeypatch):
        """creates website.sidebar when absent."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n", encoding="utf-8")

        gd._update_sidebar_with_mcp(["tool.qmd"])

        assert "sidebar" in quarto_yml_file.read(gd.build_dir)["website"]


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


class TestRemoveMcpFromRefSections:
    """Cover _remove_mcp_from_ref_sections branching."""

    def test_no_quarto_yml_returns_early(self, tmp_path):
        """No _quarto.yml file returns immediately."""
        gd = _make_gd(tmp_path)
        gd.build_dir = tmp_path / "subdir"
        gd.build_dir.mkdir()
        gd._remove_mcp_from_ref_sections()

    def test_no_ref_sections_script_no_update(self, tmp_path, monkeypatch):
        """include-in-header has no data-gd-ref-sections so no write happens."""
        gd = _make_gd(tmp_path)
        gd.build_dir = tmp_path
        quarto_yml = tmp_path / "_quarto.yml"
        quarto_yml.write_text(
            "format:\n  html:\n    include-in-header:\n      - text: 'unrelated'\n",
            encoding="utf-8",
        )
        before = quarto_yml.read_text(encoding="utf-8")
        gd._remove_mcp_from_ref_sections()
        assert quarto_yml.read_text(encoding="utf-8") == before

    def test_removes_mcp_from_multi_section_list(self, tmp_path, monkeypatch):
        """Sections 'api,cli,mcp' becomes 'api,cli', script kept."""
        gd = _make_gd(tmp_path)
        gd.build_dir = tmp_path
        quarto_yml = tmp_path / "_quarto.yml"
        script_text = (
            "<script>document.body.setAttribute('data-gd-ref-sections','api,cli,mcp')</script>"
        )
        quarto_yml.write_text(
            f'format:\n  html:\n    include-in-header:\n      - text: "{script_text}"\n'
            f"    include-after-body:\n      - text: 'other.js'\n",
            encoding="utf-8",
        )
        gd._remove_mcp_from_ref_sections()
        written = quarto_yml_file.read(gd.build_dir)
        header_items = written["format"]["html"]["include-in-header"]
        assert "api,cli" in header_items[0]["text"]
        assert "mcp" not in header_items[0]["text"]

    def test_removes_script_entirely_when_only_api_remains(self, tmp_path, monkeypatch):
        """Sections 'api,mcp' with only 'api' remaining removes script entirely."""
        gd = _make_gd(tmp_path)
        gd.build_dir = tmp_path
        quarto_yml = tmp_path / "_quarto.yml"
        ref_script = "<script>document.body.setAttribute('data-gd-ref-sections','api,mcp')</script>"
        switcher_script = "<script src='reference-switcher.js'></script>"
        quarto_yml.write_text(
            f'format:\n  html:\n    include-in-header:\n      - text: "{ref_script}"\n'
            f'    include-after-body:\n      - text: "{switcher_script}"\n',
            encoding="utf-8",
        )
        gd._remove_mcp_from_ref_sections()
        written = quarto_yml_file.read(gd.build_dir)
        header_items = written["format"]["html"]["include-in-header"]
        assert len(header_items) == 0
        after_body = written["format"]["html"]["include-after-body"]
        assert all("reference-switcher" not in e.get("text", "") for e in after_body)


class TestDiscoverExportsValidation:
    """Export validation for unresolved aliases and external re-exports"""

    def _setup(self, tmp_path, monkeypatch):
        """Set up a GreatDocs instance with mocked griffe package."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {})
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
        assert result == []

    def test_key_error_on_kind(self, tmp_path, monkeypatch):
        """Verify that an object missing from the static model is excluded"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(KeyError("missing")))
        pkg = self._make_mock_pkg({"RustObj": obj}, exports=["RustObj"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = discover_exports(gd._get_griffe_package("mypkg"), gd._config, report=print)
        assert result is not None
        assert "MyClass" in result


class TestCategoriseReferences:
    """Reference classification and missing-name handling"""

    def _setup(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        return gd

    def test_griffe_load_failure_keeps_listed_names(self, tmp_path, monkeypatch):
        """Verify that a load failure preserves configured reference sections"""
        gd = self._setup(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "reference", [{"title": "API", "contents": ["Foo"]}])
        monkeypatch.setattr(
            gd, "_get_griffe_package", lambda name: (_ for _ in ()).throw(ImportError("fail"))
        )
        result = gd._create_api_sections_with_config("mypkg")
        assert result == [{"title": "API", "desc": "", "contents": ["Foo"]}]

    def test_non_dict_section_skipped(self, tmp_path, monkeypatch):
        """Verify that reference sections other than dictionaries are ignored"""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = categorise_references(
            gd._get_griffe_package("mypkg"), ["not_a_dict", {"contents": []}]
        )
        assert result["other"] == []

    def test_classifies_function(self, tmp_path, monkeypatch):
        """Verify that functions are grouped under `functions`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"my_func": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "function")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["my_func"]}])
        assert "my_func" in result["functions"]

    def test_classifies_async_function(self, tmp_path, monkeypatch):
        """Verify that asynchronous functions are grouped under `async_functions`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = {"async"}
        pkg = MagicMock()
        pkg.members = {"afunc": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "async")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["afunc"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "dataclass")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyDC"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "constant")
        result = categorise_references(
            gd._get_griffe_package("mypkg"), [{"contents": ["MY_CONST"]}]
        )
        assert "MY_CONST" in result["constants"]

    def test_classifies_type_alias(self, tmp_path, monkeypatch):
        """Verify that type aliases are grouped under `type_aliases`"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind = griffe.Kind.TYPE_ALIAS
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"MyAlias": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "typealias")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyAlias"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = categorise_references(
            gd._get_griffe_package("mypkg"), [{"contents": ["CyclicThing"]}]
        )
        assert "CyclicThing" in result["other"]

    def test_unexpected_error_on_kind_propagates(self, tmp_path, monkeypatch):
        """Verify that unexpected errors reading an object kind propagate"""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))
        pkg = MagicMock()
        pkg.members = {"BrokenObj": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        with pytest.raises(ValueError, match="bad"):
            categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["BrokenObj"]}])

    def test_missing_name_with_installed_package_raises(self, tmp_path, monkeypatch):
        """Verify that an installed package missing a configured name raises `BuildError`"""
        import pytest

        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("importlib.metadata.version", lambda name: "1.2.3")
        from great_docs import BuildError

        with pytest.raises(BuildError, match="not found"):
            categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["Missing"]}])

    def test_missing_name_uninstalled_package_goes_to_other(self, tmp_path, monkeypatch):
        """Verify that missing names are grouped under `other` for an uninstalled package"""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(
            "importlib.metadata.version",
            lambda name: (_ for _ in ()).throw(importlib.metadata.PackageNotFoundError(name)),
        )
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["Missing"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyClass"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyClass"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(
            gd._get_griffe_package("mypkg"), [{"contents": ["AClass", "mymod"]}]
        )
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(
            "great_docs._reference.discovery.class_kind",
            lambda o: "dataclass" if o is mod_obj.members["BDataclass"] else "class",
        )
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["mymod"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["mymod"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["mymod"]}])
        assert "mymod" not in result.get("classes", [])

    def test_dict_item_in_contents(self, tmp_path, monkeypatch):
        """Verify that reference dictionaries identify objects through `name`"""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind = griffe.Kind.FUNCTION
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"named_func": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.function_kind", lambda o: "function")
        result = categorise_references(
            gd._get_griffe_package("mypkg"), [{"contents": [{"name": "named_func"}]}]
        )
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyClass"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyClass"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_typevar_attribute(self, tmp_path, monkeypatch):
        """Verify that type variables are grouped under `type_aliases`"""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind = griffe.Kind.ATTRIBUTE
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"T": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.attribute_kind", lambda o: "typevar")
        result = categorise_references(gd._get_griffe_package("mypkg"), [{"contents": ["T"]}])
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
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("great_docs._reference.discovery.class_kind", lambda o: "class")
        result = categorise_references(
            gd._get_griffe_package("mypkg"), [{"contents": ["AClass", "weird"]}]
        )

        assert "weird" in result["other"]


# ---------------------------------------------------------------------------
# Parse Click help parts
# ---------------------------------------------------------------------------


class TestParseClickHelpParts:
    def test_empty_help(self):
        desc, examples = GreatDocs._parse_click_help_parts("")
        assert desc == ""
        assert examples == []

    def test_none_help(self):
        desc, examples = GreatDocs._parse_click_help_parts(None)
        assert desc == ""

    def test_description_only(self):
        desc, examples = GreatDocs._parse_click_help_parts("Build the docs site.")
        assert desc == "Build the docs site."
        assert examples == []

    def test_with_examples_block(self):
        help_text = (
            "Build the site.\n\nExamples:\n    great-docs build\n    great-docs build --watch\n"
        )
        desc, examples = GreatDocs._parse_click_help_parts(help_text)
        assert desc == "Build the site."
        assert "great-docs build" in examples[0]
        assert len(examples) == 2

    def test_backspace_marker_stripped(self):
        help_text = "Some text\n\x08\nMore text"
        desc, examples = GreatDocs._parse_click_help_parts(help_text)
        assert "\x08" not in desc
        assert "Some text" in desc

    def test_collapses_blank_lines(self):
        help_text = "Line one\n\n\n\nLine two"
        desc, _ = GreatDocs._parse_click_help_parts(help_text)
        assert "\n\n\n" not in desc

    def test_examples_dedented_4_spaces(self):
        help_text = "Desc\n\nExamples:\n    cmd --flag\n"
        _, examples = GreatDocs._parse_click_help_parts(help_text)
        assert examples[0] == "cmd --flag"

    def test_examples_dedented_2_spaces(self):
        help_text = "Desc\n\nExamples:\n  cmd --flag\n"
        _, examples = GreatDocs._parse_click_help_parts(help_text)
        assert examples[0] == "cmd --flag"

    def test_examples_trailing_blanks_trimmed(self):
        help_text = "Desc\n\nExamples:\n    cmd\n    \n"
        _, examples = GreatDocs._parse_click_help_parts(help_text)
        assert not examples[-1].strip() == ""


# ---------------------------------------------------------------------------
# Backtick CLI prose
# ---------------------------------------------------------------------------


class TestBacktickCliProse:
    def test_empty_returns_empty(self):
        assert GreatDocs._backtick_cli_prose("", set()) == ""

    def test_wraps_single_quoted_text(self):
        result = GreatDocs._backtick_cli_prose("Use 'great-docs/' for output", set())
        assert "`great-docs/`" in result

    def test_wraps_known_option(self):
        result = GreatDocs._backtick_cli_prose("Use --watch for live reload", {"--watch"})
        assert "`--watch`" in result

    def test_avoids_possessives(self):
        result = GreatDocs._backtick_cli_prose("The package's config", set())
        assert "`" not in result

    def test_already_backticked_not_doubled(self):
        result = GreatDocs._backtick_cli_prose("Use `--watch` now", {"--watch"})
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


class TestExtractClickOption:
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
        result = GreatDocs._extract_click_option(param)
        assert result["name_display"] == "-v, --verbose"
        assert result["help"] == "Enable verbose output"
        assert result["is_flag"] is True

    def test_help_option_skipped(self):
        param = MagicMock()
        param.name = "help"
        assert GreatDocs._extract_click_option(param) is None

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
        result = GreatDocs._extract_click_option(param)
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
        result = GreatDocs._extract_click_option(param)
        assert result["default"] is None


class TestExtractClickArgument:
    def test_basic_argument(self):
        param = MagicMock()
        param.name = "path"
        param.human_readable_name = "PATH"
        param.type.name = "TEXT"
        param.required = True
        param.nargs = 1
        result = GreatDocs._extract_click_argument(param)
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
        result = GreatDocs._extract_click_argument(param)
        assert result["type"] == "INT"
        assert result["nargs"] == -1


# ---------------------------------------------------------------------------
# _get_package_exports – cache hit path
# ---------------------------------------------------------------------------


class TestGetPackageExportsCacheHit:
    def test_returns_cached_exports(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd._cached_package_name = "mypkg"
        gd._cached_exports = ["Foo", "Bar"]
        result = gd._get_package_exports("mypkg")
        assert result == ["Foo", "Bar"]

    def test_cache_miss_triggers_discovery(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd._cached_package_name = None
        gd._cached_exports = None
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: MagicMock())
        monkeypatch.setattr(
            "great_docs.core.discovery.discover_exports", lambda package, config, report: ["X"]
        )
        result = gd._get_package_exports("mypkg")
        assert result == ["X"]
        assert gd._cached_package_name == "mypkg"
        assert gd._cached_exports == ["X"]

    def test_fallback_to_parse_when_discover_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd._cached_package_name = None
        gd._cached_exports = None
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: MagicMock())
        monkeypatch.setattr(
            "great_docs.core.discovery.discover_exports", lambda package, config, report: None
        )
        monkeypatch.setattr(gd, "_find_package_init", lambda name: tmp_path / "__init__.py")
        monkeypatch.setattr(
            "great_docs.core.discovery.parse_dunder_all", lambda init_file, config, report: ["Y"]
        )
        result = gd._get_package_exports("mypkg")
        assert result == ["Y"]


# ---------------------------------------------------------------------------
# _generate_cli_command_page – edge cases (nargs, hidden, bullets, envvar, default)
# ---------------------------------------------------------------------------


class TestGenerateCliCommandPage:
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

    def test_nargs_minus1_gets_ellipsis(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
        cli_info = self._make_cli_info(
            arguments=[{"name": "FILES", "name_display": "FILES", "required": True, "nargs": -1}]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "FILES..." in result

    def test_hidden_option_skipped(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
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
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "output" in result
        assert "verbose" not in result

    def test_option_with_type_and_default(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
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
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "INT" in result
        assert "5" in result

    def test_required_option(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
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
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "**Required.**" in result

    def test_envvar_option(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
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
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "`MY_TOKEN`" in result

    def test_envvar_list_joined(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "lang", "en")
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
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "TOKEN_A, TOKEN_B" in result


# ---------------------------------------------------------------------------
# _count_cli_sidebar_items – dict with href
# ---------------------------------------------------------------------------


class TestCountCliSidebarItems:
    def test_string_items_counted(self):
        assert GreatDocs._count_cli_sidebar_items(["a.qmd", "b.qmd"]) == 2

    def test_dict_with_href_counted_as_one(self):
        items = [{"text": "Index", "href": "index.qmd"}]
        assert GreatDocs._count_cli_sidebar_items(items) == 1

    def test_nested_contents(self):
        items = [{"contents": ["a.qmd", "b.qmd"]}]
        assert GreatDocs._count_cli_sidebar_items(items) == 2


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
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("acme", "mypkg", None))
        assert gd._get_canonical_base_url() == "https://acme.github.io/mypkg/"

    def test_raw_custom_page_gets_a_canonical_link(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: "https://docs.example.com/pkg/")
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        gd._process_custom_pages()

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert (
            '<link rel="canonical" href="https://docs.example.com/pkg/custom/widget.html">' in page
        )

    def test_raw_custom_reference_page_gets_structured_data(self, tmp_path):
        (tmp_path / "great-docs.yml").write_text(
            "module: mypkg\ncustom_pages:\n  - dir: custom\n    output: reference\n",
            encoding="utf-8",
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  title: Pkg\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "demo.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        gd._process_custom_pages()

        page = (gd.build_dir / "reference" / "demo.html").read_text(encoding="utf-8")
        assert page.count('<script type="application/ld+json">') == 1
        assert '"name": "demo - Pkg"' in page

    @pytest.mark.parametrize("seo", ["true", "false"])
    def test_raw_custom_page_gets_social_cards(self, tmp_path, monkeypatch, seo):
        (tmp_path / "great-docs.yml").write_text(
            f"module: mypkg\nseo:\n  enabled: {seo}\n", encoding="utf-8"
        )
        gd = GreatDocs(project_path=str(tmp_path))
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        (gd.build_dir / "_quarto.yml").write_text(
            "website:\n  title: Pkg\n  sidebar: []\n  navbar:\n    left: []\n", encoding="utf-8"
        )
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: "https://docs.example.com/pkg/")
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head><title>Widget Lab</title></head></html>",
            encoding="utf-8",
        )

        gd._process_custom_pages()

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert page.count('<meta property="og:title" content="Widget Lab">') == 1
        assert '<meta property="og:site_name" content="Pkg">' in page
        assert (
            '<meta property="og:url" content="https://docs.example.com/pkg/custom/widget.html">'
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

        gd._process_custom_pages()

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
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {})
        return gd

    def test_pages_get_their_opening_paragraph_or_the_default(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        prose = gd.build_dir / "guide.qmd"
        prose.write_text(f"---\ntitle: Guide\n---\n\n{self.LONG}\n", encoding="utf-8")
        code = gd.build_dir / "code.qmd"
        code.write_text("```python\nx = 1\n```\n", encoding="utf-8")

        gd._step_freeze_cache(make_run())

        assert f"description-meta: {self.LONG}" in prose.read_text(encoding="utf-8")
        assert "description-meta: Site default" in code.read_text(encoding="utf-8")

    def test_nothing_is_written_when_seo_and_social_cards_are_disabled(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "seo_enabled", False)
        _patch_cfg(monkeypatch, gd, "social_cards_enabled", False)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"{self.LONG}\n", encoding="utf-8")

        gd._step_freeze_cache(make_run())

        assert "description-meta" not in page.read_text(encoding="utf-8")

    def test_versioned_sites_are_described_per_version(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "has_versions", True)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"{self.LONG}\n", encoding="utf-8")

        gd._step_freeze_cache(make_run())

        assert "description-meta" not in page.read_text(encoding="utf-8")

    def test_versioned_sites_are_described_when_watching(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "has_versions", True)
        page = gd.build_dir / "guide.qmd"
        page.write_text(f"---\nscale-to-fit: [.wide]\n---\n\n{self.LONG}\n", encoding="utf-8")

        gd._step_freeze_cache(make_run(watch=True))

        content = page.read_text(encoding="utf-8")
        assert "description-meta" in content
        assert "gd-scale-to-fit-page" in content

    def test_default_falls_back_to_the_package_description(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch, default=None)
        monkeypatch.setattr(
            gd, "_get_package_metadata", lambda: {"description": "From `pyproject`"}
        )

        assert gd._default_description() == "From pyproject"

    def test_raw_custom_page_gets_the_default(self, tmp_path, monkeypatch):
        gd = self._gd(tmp_path, monkeypatch, default="Tom & Jerry")
        custom = tmp_path / "custom"
        custom.mkdir()
        (custom / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><head></head></html>", encoding="utf-8"
        )

        gd._process_custom_pages()

        page = (gd.build_dir / "custom" / "widget.html").read_text(encoding="utf-8")
        assert page.count('<meta name="description" content="Tom &amp; Jerry">') == 1


# ---------------------------------------------------------------------------
# _inject_version_selector – full function coverage
# ---------------------------------------------------------------------------


class TestInjectVersionSelector:
    def test_basic_injection(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources: []\nformat:\n  html:\n    include-in-header: []\n    include-after-body: []\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0"), MagicMock(tag="v2.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {"versions": [{"tag": "v1.0"}, {"tag": "v2.0"}]},
        )
        _patch_cfg(monkeypatch, gd, "versions", [{"tag": "v1.0"}, {"tag": "v2.0"}])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector()
        content = quarto_yml.read_text()
        assert "gd-version-map" in content
        assert "version-selector.js" in content

    def test_string_header_converted_to_list(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources: []\nformat:\n  html:\n    include-in-header: old-header.html\n    include-after-body: []\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector()
        content = quarto_yml.read_text()
        assert "gd-version-map" in content

    def test_string_after_body_converted_to_list(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources: []\nformat:\n  html:\n    include-in-header: []\n    include-after-body: old-body.html\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector()
        content = quarto_yml.read_text()
        assert "version-selector" in content

    def test_warning_banner_disabled(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources: []\nformat:\n  html:\n    include-in-header: []\n    include-after-body: []\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", False)
        gd._inject_version_selector()
        content = quarto_yml.read_text()
        assert "gd-version-warning-banner" in content

    def test_inserts_before_navbar_widgets(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources: []\nformat:\n  html:\n    include-in-header: []\n    include-after-body:\n      - text: '<script src=\"navbar-widgets.js\"></script>'\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector()
        content = quarto_yml.read_text()
        assert "version-selector" in content

    def test_resources_list_not_duplicated(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  resources:\n    - version-selector.js\nformat:\n  html:\n    include-in-header: []\n    include-after-body: []\n",
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versions.model.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versions.model.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector()


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


# ---------------------------------------------------------------------------
# _create_api_sections_from_config – include_inherited
# ---------------------------------------------------------------------------


class TestCreateApiSectionsFromConfig:
    def test_no_reference_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", None)
        assert gd._create_api_sections_with_config("mypkg") is None

    def test_include_inherited_on_explicit_members(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "MyClass", "members": ["method_a"], "include_inherited": True},
                    ],
                }
            ],
        )
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: MagicMock())
        monkeypatch.setattr(
            "great_docs.core.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = gd._create_api_sections_with_config("mypkg")
        assert result is not None
        found = False
        for section in result:
            for item in section.get("contents", []):
                if isinstance(item, dict) and item.get("name") == "MyClass":
                    assert item.get("include_inherited") is True
                    found = True
        assert found

    def test_include_inherited_on_default_entry(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "MyClass", "include_inherited": True},
                    ],
                }
            ],
        )
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: MagicMock())
        monkeypatch.setattr(
            "great_docs.core.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = gd._create_api_sections_with_config("mypkg")
        found = False
        for section in result:
            for item in section.get("contents", []):
                if isinstance(item, dict) and item.get("include_inherited") is True:
                    found = True
        assert found

    def test_plain_string_when_no_include_inherited(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(
            monkeypatch,
            gd,
            "reference",
            [
                {
                    "title": "Funcs",
                    "contents": [
                        {"name": "my_func"},
                    ],
                }
            ],
        )
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: MagicMock())
        monkeypatch.setattr(
            "great_docs.core.discovery.categorise_references",
            lambda package, reference: empty_categories(),
        )
        result = gd._create_api_sections_with_config("mypkg")
        for section in result:
            for item in section.get("contents", []):
                if item == "my_func":
                    return
        raise AssertionError("Expected plain string 'my_func' in contents")


# ---------------------------------------------------------------------------
# Discover package exports at most once per build
# ---------------------------------------------------------------------------


class TestStepApiReferenceConfig:
    def test_skips_discovery_when_already_done(self, tmp_path):
        gd = _make_gd(tmp_path)
        with patch.object(reference_block, "refresh") as refresh:
            gd._step_api_reference_config(make_run(api_discovery_done=True), refresh=True)
        refresh.assert_not_called()
