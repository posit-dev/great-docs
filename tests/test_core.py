# pyright: reportPrivateUsage=false
"""Tests for great_docs.core (GreatDocs class)."""

from __future__ import annotations

import importlib
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import requests

from great_docs import GreatDocs


def _make_gd(tmp_path: Path) -> GreatDocs:
    """Create a GreatDocs instance in a temp directory with minimal config."""
    (tmp_path / "great-docs.yml").write_text("module: mypkg\n", encoding="utf-8")
    return GreatDocs(project_path=str(tmp_path))


def _patch_cfg(monkeypatch, gd, name, value):
    """Patch a Config property on the class so the instance returns *value*."""
    monkeypatch.setattr(type(gd._config), name, property(lambda self: value))


class TestFetchGithubRepoStats:
    """Cover _fetch_github_repo_stats auth header and response paths."""

    def test_success_with_token(self, tmp_path, monkeypatch):
        """Token is used and success data returned."""
        gd = _make_gd(tmp_path)
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"stargazers_count": 42, "forks_count": 7}

        monkeypatch.setattr(requests, "get", lambda *a, **kw: mock_resp)

        result = gd._fetch_github_repo_stats("posit-dev", "great-docs")
        assert result == {"stars": 42, "forks": 7}

    def test_request_exception_returns_empty(self, tmp_path, monkeypatch):
        """RequestException is swallowed, returns {}."""
        gd = _make_gd(tmp_path)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        def raise_exc(*a, **kw):
            raise requests.RequestException("network error")

        monkeypatch.setattr(requests, "get", raise_exc)

        result = gd._fetch_github_repo_stats("owner", "repo")
        assert result == {}

    def test_non_200_returns_empty(self, tmp_path, monkeypatch):
        """Non-200 status code returns empty dict."""
        gd = _make_gd(tmp_path)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        monkeypatch.setattr(requests, "get", lambda *a, **kw: mock_resp)

        result = gd._fetch_github_repo_stats("owner", "repo")
        assert result == {}


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


class TestDiscoverMcpServer:
    """Cover the auto-discovery path in _discover_mcp_server."""

    def test_no_mcp_module_all_imports_fail(self, tmp_path, monkeypatch):
        """no module configured, all candidates fail returns None."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(type(gd._config), "mcp_module", property(lambda self: None))

        real_import = importlib.import_module

        def fail_import(name, *args, **kwargs):
            if name.startswith("mypkg."):
                raise ImportError(f"no {name}")
            return real_import(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=fail_import):
            result = gd._discover_mcp_server()
        assert result is None

    def test_auto_discovers_mcp_module(self, tmp_path, monkeypatch):
        """finds a candidate MCP module successfully."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(type(gd._config), "mcp_module", property(lambda self: None))

        fake_mcp_mod = types.ModuleType("mypkg.mcp")
        real_import = importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "mypkg.mcp":
                return fake_mcp_mod
            if name.startswith("mypkg."):
                raise ImportError(f"no {name}")
            return real_import(name, *args, **kwargs)

        fake_discovery_result = {"name": "test-server", "tools": []}

        with patch("importlib.import_module", side_effect=mock_import):
            with patch(
                "great_docs._mcp_docs.discover_mcp_server",
                return_value=fake_discovery_result,
            ) as mock_discover:
                result = gd._discover_mcp_server()

        assert result == fake_discovery_result
        mock_discover.assert_called_once()


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

        written = {}

        def fake_write(path, config):
            written["config"] = config

        monkeypatch.setattr(gd, "_write_quarto_yml", fake_write)

        mcp_files = ["reference/mcp/tools.qmd", "reference/mcp/resources.qmd"]
        gd._update_sidebar_with_mcp(mcp_files)

        assert "config" in written
        sidebar = written["config"]["website"]["sidebar"]
        mcp_section = next(s for s in sidebar if s.get("id") == "mcp-reference")
        assert "MCP Reference" in mcp_section["title"]

    def test_updates_existing_mcp_section(self, tmp_path, monkeypatch):
        """existing mcp-reference section gets updated."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n  sidebar:\n    - id: mcp-reference\n      title: MCP Reference\n      contents:\n        - old.qmd\n",
            encoding="utf-8",
        )

        written = {}

        def fake_write(path, config):
            written["config"] = config

        monkeypatch.setattr(gd, "_write_quarto_yml", fake_write)

        new_files = ["new-tools.qmd"]
        gd._update_sidebar_with_mcp(new_files)

        sidebar = written["config"]["website"]["sidebar"]
        mcp_section = next(s for s in sidebar if s.get("id") == "mcp-reference")
        assert mcp_section["contents"] == new_files

    def test_creates_website_and_sidebar_keys(self, tmp_path, monkeypatch):
        """creates website.sidebar when absent."""
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n", encoding="utf-8")

        written = {}

        def fake_write(path, config):
            written["config"] = config

        monkeypatch.setattr(gd, "_write_quarto_yml", fake_write)

        gd._update_sidebar_with_mcp(["tool.qmd"])

        assert "website" in written["config"]
        assert "sidebar" in written["config"]["website"]


class TestGenerateMcpManifest:
    """Cover _generate_mcp_manifest orchestration."""

    def test_calls_generate_mcp_manifest(self, tmp_path, monkeypatch):
        """Gathers metadata and calls generate_mcp_manifest."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_detect_package_name", lambda: "mypkg")
        monkeypatch.setattr(
            gd,
            "_get_github_repo_info",
            lambda: ("posit-dev", "mypkg", "https://github.com/posit-dev/mypkg"),
        )
        gd._config._config["site_url"] = "https://mypkg.readthedocs.io"

        called_with = {}

        def fake_gen(**kwargs):
            called_with.update(kwargs)

        with patch("great_docs.core.generate_mcp_manifest", create=True):
            monkeypatch.setattr("great_docs._mcp_docs.generate_mcp_manifest", fake_gen)
            gd._generate_mcp_manifest({"name": "test", "tools": []})

        assert called_with["package_name"] == "mypkg"
        assert called_with["repo_url"] == "https://github.com/posit-dev/mypkg"
        assert called_with["site_url"] == "https://mypkg.readthedocs.io"
        assert called_with["server_info"] == {"name": "test", "tools": []}


class TestReorderNavbar:
    """Cover _reorder_navbar edge case."""

    def test_empty_navbar_left_returns_early(self, tmp_path, monkeypatch):
        """Navbar left is empty returns early."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(
            type(gd._config), "navbar_order", property(lambda self: ["Reference", "API"])
        )
        config = {"website": {"navbar": {"left": []}}}
        gd._reorder_navbar(config)

        assert config["website"]["navbar"]["left"] == []


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
        written = []
        monkeypatch.setattr(gd, "_write_quarto_yml", lambda p, c: written.append(c))
        gd._remove_mcp_from_ref_sections()
        assert written == []

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
        written = []
        monkeypatch.setattr(gd, "_write_quarto_yml", lambda p, c: written.append(c))
        gd._remove_mcp_from_ref_sections()
        assert len(written) == 1
        header_items = written[0]["format"]["html"]["include-in-header"]
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
        written = []
        monkeypatch.setattr(gd, "_write_quarto_yml", lambda p, c: written.append(c))
        gd._remove_mcp_from_ref_sections()
        assert len(written) == 1
        header_items = written[0]["format"]["html"]["include-in-header"]
        assert len(header_items) == 0
        after_body = written[0]["format"]["html"]["include-after-body"]
        assert all("reference-switcher" not in e.get("text", "") for e in after_body)


class TestDiscoverPackageExportsValidation:
    """Cover the griffe export validation block inside _discover_package_exports."""

    def _setup(self, tmp_path, monkeypatch):
        """Set up a GreatDocs instance with mocked griffe package."""
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {})
        return gd

    def _make_mock_pkg(self, members_dict, exports=None):
        """Build a mock griffe package with controlled members."""
        pkg = MagicMock()
        pkg.members = members_dict
        pkg.exports = exports
        return pkg

    def test_not_found_in_pkg_members(self, tmp_path, monkeypatch):
        """Name not in pkg.members is excluded from safe_exports."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        good_obj = MagicMock()
        good_obj.kind.value = "function"
        good_obj.members = {}
        good_obj.is_alias = False
        pkg = self._make_mock_pkg(
            {"good_func": good_obj},
            exports=["good_func", "MissingClass"],
        )
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert "good_func" in result
        assert "MissingClass" not in result

    def test_cyclic_alias_on_kind(self, tmp_path, monkeypatch):
        """CyclicAliasError on obj.kind excludes the export."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = self._make_mock_pkg({"BadAlias": obj}, exports=["BadAlias"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_alias_resolution_error_on_kind(self, tmp_path, monkeypatch):
        """AliasResolutionError on obj.kind excludes the export."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.AliasResolutionError(MagicMock()))
        )
        pkg = self._make_mock_pkg({"Unresolvable": obj}, exports=["Unresolvable"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_key_error_on_kind(self, tmp_path, monkeypatch):
        """KeyError on obj.kind excludes the export (likely Rust/PyO3)."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(KeyError("missing")))
        pkg = self._make_mock_pkg({"RustObj": obj}, exports=["RustObj"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_generic_exception_on_kind(self, tmp_path, monkeypatch):
        """Generic Exception on obj.kind excludes the export."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(RuntimeError("oops")))
        pkg = self._make_mock_pkg({"Broken": obj}, exports=["Broken"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_module_kind_passes_without_members_check(self, tmp_path, monkeypatch):
        """Module kind passes directly to safe_exports."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "module"
        obj.is_alias = False
        pkg = self._make_mock_pkg({"submod": obj}, exports=["submod"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert "submod" in result

    def test_cyclic_alias_on_members_access(self, tmp_path, monkeypatch):
        """CyclicAliasError accessing .members excludes the export."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        type(obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = self._make_mock_pkg({"CyclicClass": obj}, exports=["CyclicClass"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_alias_resolution_error_on_members_access(self, tmp_path, monkeypatch):
        """AliasResolutionError accessing .members excludes the export."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        type(obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.AliasResolutionError(MagicMock()))
        )
        pkg = self._make_mock_pkg({"Unresolvable": obj}, exports=["Unresolvable"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_generic_exception_on_members_access(self, tmp_path, monkeypatch):
        """Generic Exception accessing .members excludes the export."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        type(obj).members = property(lambda s: (_ for _ in ()).throw(TypeError("bad")))
        pkg = self._make_mock_pkg({"BadClass": obj}, exports=["BadClass"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_external_re_export_excluded(self, tmp_path, monkeypatch):
        """Alias pointing to external package is excluded as re-export."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        obj.members = {}
        obj.is_alias = True
        obj.canonical_path = "other_package.SomeClass"
        pkg = self._make_mock_pkg({"SomeClass": obj}, exports=["SomeClass"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert result == []

    def test_internal_alias_passes(self, tmp_path, monkeypatch):
        """Alias pointing inside the package passes."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        obj.members = {}
        obj.is_alias = True
        obj.canonical_path = "mypkg.internal.MyClass"
        pkg = self._make_mock_pkg({"MyClass": obj}, exports=["MyClass"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert "MyClass" in result

    def test_canonical_path_raises_still_passes(self, tmp_path, monkeypatch):
        """Exception on canonical_path means the alias still passes."""
        gd = self._setup(tmp_path, monkeypatch)

        class _FakeAlias:
            class kind:
                value = "function"

            members = {}
            is_alias = True

            @property
            def canonical_path(self):
                raise AttributeError("oops")

        obj = _FakeAlias()
        pkg = self._make_mock_pkg({"myfn": obj}, exports=["myfn"])
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._discover_package_exports("mypkg")
        assert "myfn" in result


class TestCategorizeReferencedObjects:
    """Cover _categorize_referenced_objects classification logic."""

    def _setup(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        return gd

    def test_griffe_load_fails_returns_empty(self, tmp_path, monkeypatch):
        """Exception from _get_griffe_package returns empty categories."""
        gd = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(
            gd, "_get_griffe_package", lambda name: (_ for _ in ()).throw(RuntimeError("fail"))
        )
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["Foo"]}])
        assert result["classes"] == []
        assert result["functions"] == []

    def test_non_dict_section_skipped(self, tmp_path, monkeypatch):
        """Non-dict entries in reference_config are skipped."""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", ["not_a_dict", {"contents": []}])
        assert result["other"] == []

    def test_classifies_function(self, tmp_path, monkeypatch):
        """Function kind is categorized into 'functions'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "function"
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"my_func": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_function", lambda o: "function")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["my_func"]}])
        assert "my_func" in result["functions"]

    def test_classifies_async_function(self, tmp_path, monkeypatch):
        """Async function is categorized into 'async_functions'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "function"
        obj.labels = {"async"}
        pkg = MagicMock()
        pkg.members = {"afunc": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_function", lambda o: "async")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["afunc"]}])
        assert "afunc" in result["async_functions"]

    def test_classifies_class_as_dataclass(self, tmp_path, monkeypatch):
        """Class sub-classified as dataclass goes to 'dataclasses'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "class"
        obj.members = {"__init__": MagicMock()}
        obj.members["__init__"].kind.value = "function"
        pkg = MagicMock()
        pkg.members = {"MyDC": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "dataclass")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyDC"]}])
        assert "MyDC" in result["dataclasses"]

    def test_classifies_attribute_as_constant(self, tmp_path, monkeypatch):
        """Attribute kind goes to 'constants'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "attribute"
        obj.labels = set()
        obj.annotation = None
        pkg = MagicMock()
        pkg.members = {"MY_CONST": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_attribute", lambda o: "constant")
        monkeypatch.setattr(gd, "_extract_constant_metadata", lambda o, n, c: None)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MY_CONST"]}])
        assert "MY_CONST" in result["constants"]

    def test_classifies_type_alias(self, tmp_path, monkeypatch):
        """Type alias attribute goes to 'type_aliases'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        obj.kind.value = "type alias"
        obj.labels = set()
        pkg = MagicMock()
        pkg.members = {"MyAlias": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_attribute", lambda o: "type_alias")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyAlias"]}])
        assert "MyAlias" in result["type_aliases"]

    def test_cyclic_alias_on_kind_goes_to_other(self, tmp_path, monkeypatch):
        """CyclicAliasError on obj.kind goes to 'other'."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )
        pkg = MagicMock()
        pkg.members = {"CyclicThing": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["CyclicThing"]}])
        assert "CyclicThing" in result["other"]

    def test_generic_exception_on_kind_goes_to_other(self, tmp_path, monkeypatch):
        """Generic Exception on obj.kind goes to 'other'."""
        gd = self._setup(tmp_path, monkeypatch)
        obj = MagicMock()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))
        pkg = MagicMock()
        pkg.members = {"BrokenObj": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["BrokenObj"]}])
        assert "BrokenObj" in result["other"]

    def test_missing_name_with_installed_package_raises(self, tmp_path, monkeypatch):
        """Missing name + installed package raises SystemExit."""
        import pytest

        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr("importlib.metadata.version", lambda name: "1.2.3")
        with pytest.raises(SystemExit, match="not found"):
            gd._categorize_referenced_objects("mypkg", [{"contents": ["Missing"]}])

    def test_missing_name_uninstalled_package_goes_to_other(self, tmp_path, monkeypatch):
        """Missing name + uninstalled package falls to 'other'."""
        gd = self._setup(tmp_path, monkeypatch)
        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(
            "importlib.metadata.version",
            lambda name: (_ for _ in ()).throw(Exception("not installed")),
        )
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["Missing"]}])
        assert "Missing" in result["other"]

    def test_class_method_counting(self, tmp_path, monkeypatch):
        """Class with public methods populates class_methods count."""
        gd = self._setup(tmp_path, monkeypatch)

        method_obj = MagicMock()
        method_obj.kind.value = "function"

        private_obj = MagicMock()
        private_obj.kind.value = "function"

        prop_obj = MagicMock()
        prop_obj.kind.value = "attribute"
        prop_obj.labels = {"property"}

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {
            "do_stuff": method_obj,
            "_private": private_obj,
            "value": prop_obj,
        }

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 2
        assert "do_stuff" in result["class_method_names"]["MyClass"]
        assert "value" in result["class_method_names"]["MyClass"]
        assert "_private" not in result["class_method_names"]["MyClass"]

    def test_class_member_cyclic_alias_skipped(self, tmp_path, monkeypatch):
        """CyclicAliasError on member.kind skips the member."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"bad_member": bad_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_class_member_generic_exception_skipped(self, tmp_path, monkeypatch):
        """Generic Exception on member.kind skips the member."""
        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(lambda s: (_ for _ in ()).throw(TypeError("oops")))

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_module_kind_expands_members(self, tmp_path, monkeypatch):
        """Module kind expands members into qualified names."""
        gd = self._setup(tmp_path, monkeypatch)

        sub_class = MagicMock()
        sub_class.kind.value = "class"
        sub_func = MagicMock()
        sub_func.kind.value = "function"
        sub_attr = MagicMock()
        sub_attr.kind.value = "attribute"

        mod_obj = MagicMock()
        mod_obj.kind.value = "module"
        mod_obj.members = {
            "SubClass": sub_class,
            "sub_func": sub_func,
            "CONST": sub_attr,
            "_private": MagicMock(),
        }

        anchor_cls = MagicMock()
        anchor_cls.kind.value = "class"
        anchor_cls.members = {}
        anchor_cls.labels = set()
        anchor_cls.bases = []

        pkg = MagicMock()
        pkg.members = {"AClass": anchor_cls, "mymod": mod_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["AClass", "mymod"]}])
        assert "mymod.SubClass" in result["classes"]
        assert "mymod.sub_func" in result["functions"]
        assert "mymod.CONST" in result["constants"]

    def test_module_member_cyclic_alias_skipped(self, tmp_path, monkeypatch):
        """CyclicAliasError on module member's kind skips it."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        mod_obj = MagicMock()
        mod_obj.kind.value = "module"
        mod_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"mymod": mod_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["mymod"]}])
        assert "mymod.broken" not in result.get("other", [])

    def test_module_members_iteration_raises(self, tmp_path, monkeypatch):
        """Exception iterating module.members is caught by outer except."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        mod_obj = MagicMock()
        mod_obj.kind.value = "module"
        type(mod_obj).members = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        pkg = MagicMock()
        pkg.members = {"mymod": mod_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["mymod"]}])
        assert "mymod" not in result.get("classes", [])

    def test_qualified_method_ref_classifies_method(self, tmp_path, monkeypatch):
        """'ClassName.method_name' is classified as method."""
        gd = self._setup(tmp_path, monkeypatch)

        method_member = MagicMock()
        method_member.kind.value = "function"
        method_member.labels = set()

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"do_thing": method_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        monkeypatch.setattr(gd, "_sub_classify_function", lambda o: "function")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.do_thing"]}])
        assert result["class_member_types"]["MyClass.do_thing"] == "method"

    def test_qualified_method_ref_classmethod(self, tmp_path, monkeypatch):
        """'ClassName.cls_method' is classified as classmethod."""
        gd = self._setup(tmp_path, monkeypatch)

        method_member = MagicMock()
        method_member.kind.value = "function"
        method_member.labels = {"classmethod"}

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"from_config": method_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        monkeypatch.setattr(gd, "_sub_classify_function", lambda o: "classmethod")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.from_config"]}])
        assert result["class_member_types"]["MyClass.from_config"] == "classmethod"

    def test_qualified_method_ref_attribute_property(self, tmp_path, monkeypatch):
        """'ClassName.prop' with attribute kind + property label is classified as 'property'."""
        gd = self._setup(tmp_path, monkeypatch)

        attr_member = MagicMock()
        attr_member.kind.value = "attribute"
        attr_member.labels = {"property"}

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"name": attr_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.name"]}])
        assert result["class_member_types"]["MyClass.name"] == "property"

    def test_qualified_method_ref_attribute_non_property(self, tmp_path, monkeypatch):
        """'ClassName.field' with attribute kind + no property label is classified as 'attribute'."""
        gd = self._setup(tmp_path, monkeypatch)

        attr_member = MagicMock()
        attr_member.kind.value = "attribute"
        attr_member.labels = set()

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"field": attr_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.field"]}])
        assert result["class_member_types"]["MyClass.field"] == "attribute"

    def test_qualified_method_ref_unknown_kind_defaults_method(self, tmp_path, monkeypatch):
        """'ClassName.thing' with unexpected kind defaults to 'method'."""
        gd = self._setup(tmp_path, monkeypatch)

        weird_member = MagicMock()
        weird_member.kind.value = "module"

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"thing": weird_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.thing"]}])
        assert result["class_member_types"]["MyClass.thing"] == "method"

    def test_qualified_method_ref_cyclic_alias_defaults_method(self, tmp_path, monkeypatch):
        """CyclicAliasError resolving method defaults to 'method'."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(
            lambda s: (_ for _ in ()).throw(griffe.CyclicAliasError(["x", "y"]))
        )

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.broken"]}])
        assert result["class_member_types"]["MyClass.broken"] == "method"

    def test_qualified_method_ref_generic_exception_defaults_method(self, tmp_path, monkeypatch):
        """Generic Exception resolving method defaults to 'method'."""
        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(lambda s: (_ for _ in ()).throw(RuntimeError("fail")))

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.broken"]}])
        assert result["class_member_types"]["MyClass.broken"] == "method"

    def test_qualified_method_not_in_class_members(self, tmp_path, monkeypatch):
        """Method name not in class.members defaults to 'method'."""
        gd = self._setup(tmp_path, monkeypatch)

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects(
            "mypkg", [{"contents": ["MyClass.missing_method"]}]
        )
        assert result["class_member_types"]["MyClass.missing_method"] == "method"

    def test_qualified_method_class_not_in_pkg(self, tmp_path, monkeypatch):
        """Class not in pkg.members means method ref is skipped."""
        gd = self._setup(tmp_path, monkeypatch)

        pkg = MagicMock()
        pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["Ghost.method"]}])
        assert "Ghost.method" not in result.get("class_member_types", {})

    def test_qualified_method_class_not_actually_class(self, tmp_path, monkeypatch):
        """Class name resolves to non-class so ref is skipped."""
        gd = self._setup(tmp_path, monkeypatch)

        not_a_class = MagicMock()
        not_a_class.kind.value = "function"

        pkg = MagicMock()
        pkg.members = {"NotClass": not_a_class}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["NotClass.method"]}])
        assert "NotClass.method" not in result.get("class_member_types", {})

    def test_qualified_method_class_kind_raises(self, tmp_path, monkeypatch):
        """Exception checking class kind means ref is skipped."""
        gd = self._setup(tmp_path, monkeypatch)

        bad_obj = MagicMock()
        type(bad_obj).kind = property(lambda s: (_ for _ in ()).throw(RuntimeError("fail")))

        pkg = MagicMock()
        pkg.members = {"Bad": bad_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["Bad.method"]}])
        assert "Bad.method" not in result.get("class_member_types", {})

    def test_attribute_labels_raises_defaults_to_set(self, tmp_path, monkeypatch):
        """Exception accessing member.labels defaults to empty set."""
        gd = self._setup(tmp_path, monkeypatch)

        class _FakeMemberBadLabels:
            class kind:
                value = "attribute"

            @property
            def labels(self):
                raise AttributeError("no labels")

        attr_member = _FakeMemberBadLabels()

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"broken_attr": attr_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass.broken_attr"]}])
        assert result["class_member_types"]["MyClass.broken_attr"] == "attribute"

    def test_dict_item_in_contents(self, tmp_path, monkeypatch):
        """Dict item with 'name' key in contents is recognized."""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind.value = "function"
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"named_func": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_function", lambda o: "function")
        result = gd._categorize_referenced_objects(
            "mypkg", [{"contents": [{"name": "named_func"}]}]
        )
        assert "named_func" in result["functions"]

    def test_class_property_member_counted(self, tmp_path, monkeypatch):
        """@property attribute counted as method."""
        gd = self._setup(tmp_path, monkeypatch)

        prop_member = MagicMock()
        prop_member.kind.value = "attribute"
        prop_member.labels = {"property"}

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"name": prop_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 1
        assert "name" in result["class_method_names"]["MyClass"]

    def test_class_init_dunder_skipped(self, tmp_path, monkeypatch):
        """__init__ dunder is skipped in method count."""
        gd = self._setup(tmp_path, monkeypatch)

        init_member = MagicMock()
        init_member.kind.value = "function"

        public_method = MagicMock()
        public_method.kind.value = "function"

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"__init__": init_member, "run": public_method}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 1
        assert "run" in result["class_method_names"]["MyClass"]
        assert "__init__" not in result["class_method_names"]["MyClass"]

    def test_class_property_labels_raises(self, tmp_path, monkeypatch):
        """Exception accessing member.labels for property check passes."""
        gd = self._setup(tmp_path, monkeypatch)

        attr_member = MagicMock()
        attr_member.kind.value = "attribute"
        type(attr_member).labels = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("no labels"))
        )

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = {"prop": attr_member}

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_class_members_outer_cyclic_alias(self, tmp_path, monkeypatch):
        """CyclicAliasError iterating class members is caught by outer except."""
        import griffe

        gd = self._setup(tmp_path, monkeypatch)

        class _BadItems(dict):
            def items(self):
                raise griffe.CyclicAliasError(["x", "y"])

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        cls_obj.members = _BadItems()

        pkg = MagicMock()
        pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["MyClass"]}])
        assert result["class_methods"]["MyClass"] == 0

    def test_typevar_attribute(self, tmp_path, monkeypatch):
        """TypeVar attribute goes to type_aliases."""
        gd = self._setup(tmp_path, monkeypatch)

        obj = MagicMock()
        obj.kind.value = "attribute"
        obj.labels = set()

        pkg = MagicMock()
        pkg.members = {"T": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_attribute", lambda o: "typevar")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["T"]}])
        assert "T" in result["type_aliases"]

    def test_module_member_generic_exception_skipped(self, tmp_path, monkeypatch):
        """Generic Exception on module member's kind skips it."""
        gd = self._setup(tmp_path, monkeypatch)

        bad_member = MagicMock()
        type(bad_member).kind = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))

        anchor = MagicMock()
        anchor.kind.value = "class"
        anchor.members = {}

        mod_obj = MagicMock()
        mod_obj.kind.value = "module"
        mod_obj.members = {"broken": bad_member}

        pkg = MagicMock()
        pkg.members = {"AClass": anchor, "mymod": mod_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["AClass", "mymod"]}])
        assert "mymod.broken" not in result.get("functions", [])

    def test_module_members_outer_exception(self, tmp_path, monkeypatch):
        """Generic Exception iterating module members is caught by outer except."""
        gd = self._setup(tmp_path, monkeypatch)

        class _BadItems(dict):
            def items(self):
                raise TypeError("bad iteration")

        anchor = MagicMock()
        anchor.kind.value = "class"
        anchor.members = {}

        mod_obj = MagicMock()
        mod_obj.kind.value = "module"
        mod_obj.members = _BadItems()

        pkg = MagicMock()
        pkg.members = {"AClass": anchor, "mymod": mod_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["AClass", "mymod"]}])
        assert "mymod" not in result.get("classes", [])

    def test_other_kind_goes_to_other(self, tmp_path, monkeypatch):
        """Unknown kind value goes to 'other'."""
        gd = self._setup(tmp_path, monkeypatch)

        anchor = MagicMock()
        anchor.kind.value = "class"
        anchor.members = {}

        obj = MagicMock()
        obj.kind.value = "alias"

        pkg = MagicMock()
        pkg.members = {"AClass": anchor, "weird": obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda name: pkg)
        monkeypatch.setattr(gd, "_sub_classify_class", lambda o: "class")
        result = gd._categorize_referenced_objects("mypkg", [{"contents": ["AClass", "weird"]}])

        assert "weird" in result["other"]


# ---------------------------------------------------------------------------
# Module-level utility functions
# ---------------------------------------------------------------------------


class TestMigrateLegacyGitignore:
    def test_migrates_bare_entry(self):
        from great_docs.core import _migrate_legacy_gitignore_entry

        content = "node_modules/\ngreat-docs/\n.env\n"
        result = _migrate_legacy_gitignore_entry(content)
        assert "/great-docs/\n" in result
        assert "\ngreat-docs/\n" not in result

    def test_preserves_already_anchored(self):
        from great_docs.core import _migrate_legacy_gitignore_entry

        content = "/great-docs/\n"
        result = _migrate_legacy_gitignore_entry(content)
        assert result == content

    def test_no_entry_returns_unchanged(self):
        from great_docs.core import _migrate_legacy_gitignore_entry

        content = "*.pyc\n__pycache__/\n"
        result = _migrate_legacy_gitignore_entry(content)
        assert result is content


class TestGitignoreHasEntry:
    def test_exact_match(self):
        from great_docs.core import _gitignore_has_entry

        assert _gitignore_has_entry("/great-docs/\n.env\n", "/great-docs/")

    def test_no_match(self):
        from great_docs.core import _gitignore_has_entry

        assert not _gitignore_has_entry("*.pyc\n", "/great-docs/")

    def test_negated_entry_not_matched(self):
        from great_docs.core import _gitignore_has_entry

        assert not _gitignore_has_entry("!/great-docs/skills/\n", "/great-docs/")


# ---------------------------------------------------------------------------
# Linkify GitHub references
# ---------------------------------------------------------------------------


class TestLinkifyGithubReferences:
    def test_bare_issue_number(self):
        result = GreatDocs._linkify_github_references("Fixed #42", "owner", "repo")
        assert "[#42](https://github.com/owner/repo/issues/42)" in result

    def test_gh_issue_keyword(self):
        result = GreatDocs._linkify_github_references("gh issue #7", "owner", "repo")
        assert "[#7](https://github.com/owner/repo/issues/7)" in result

    def test_gh_pr_keyword(self):
        result = GreatDocs._linkify_github_references("gh PR #99", "owner", "repo")
        assert "[#99](https://github.com/owner/repo/issues/99)" in result

    def test_at_username(self):
        result = GreatDocs._linkify_github_references("Thanks @alice", "o", "r")
        assert "[@alice](https://github.com/alice)" in result

    def test_backslash_escapes_removed(self):
        result = GreatDocs._linkify_github_references(r"\#123 by \@bob", "o", "r")
        assert "[#123]" in result
        assert "[@bob]" in result

    def test_compare_url_linked(self):
        url = "https://github.com/owner/repo/compare/v1.0...v2.0"
        result = GreatDocs._linkify_github_references(f"Full Changelog: {url}", "owner", "repo")
        assert f"[{url}]({url})" in result

    def test_already_linked_not_doubled(self):
        text = "[#10](https://github.com/owner/repo/issues/10)"
        result = GreatDocs._linkify_github_references(text, "owner", "repo")
        assert result.count("[#10]") == 1


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
# Bump heading levels
# ---------------------------------------------------------------------------


class TestBumpHeadingLevels:
    def test_h1_becomes_h2(self):
        result = GreatDocs._bump_heading_levels("# Title\n\nParagraph")
        assert result.startswith("## Title")

    def test_h3_becomes_h4(self):
        result = GreatDocs._bump_heading_levels("### Section")
        assert result == "#### Section"

    def test_headings_in_fenced_block_untouched(self):
        content = "```python\n# this is a comment\n```"
        result = GreatDocs._bump_heading_levels(content)
        assert "## this is a comment" not in result
        assert "# this is a comment" in result

    def test_tilde_fence_respected(self):
        content = "~~~\n# comment\n~~~"
        result = GreatDocs._bump_heading_levels(content)
        assert "# comment" in result
        assert "## comment" not in result

    def test_mixed_content(self):
        content = "# Top\n\n```\n# inside\n```\n\n## Below"
        result = GreatDocs._bump_heading_levels(content)
        assert "## Top" in result
        assert "# inside" in result
        assert "### Below" in result


# ---------------------------------------------------------------------------
# Sub-classify class / function / attribute
# ---------------------------------------------------------------------------


class TestSubClassifyClass:
    def test_dataclass(self):
        obj = MagicMock()
        obj.labels = {"dataclass"}
        assert GreatDocs._sub_classify_class(obj) == "dataclass"

    def test_enum_via_bases(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "enum.IntEnum"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "enum"

    def test_exception_via_bases(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "ValueError"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "exception"

    def test_namedtuple(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "NamedTuple"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "namedtuple"

    def test_typeddict(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "TypedDict"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "typeddict"

    def test_protocol(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "Protocol"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "protocol"

    def test_abc_via_bases(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "ABC"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "abc"

    def test_abc_via_decorator(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "object"
        obj.bases = [base]
        dec = MagicMock()
        dec.value = "abstractmethod"
        obj.decorators = [dec]
        assert GreatDocs._sub_classify_class(obj) == "abc"

    def test_plain_class_fallback(self):
        obj = MagicMock()
        obj.labels = set()
        base = MagicMock()
        base.__str__ = lambda s: "object"
        obj.bases = [base]
        obj.decorators = []
        assert GreatDocs._sub_classify_class(obj) == "class"


class TestSubClassifyFunction:
    def test_async(self):
        obj = MagicMock()
        obj.labels = {"async"}
        assert GreatDocs._sub_classify_function(obj) == "async"

    def test_classmethod(self):
        obj = MagicMock()
        obj.labels = {"classmethod"}
        assert GreatDocs._sub_classify_function(obj) == "classmethod"

    def test_staticmethod(self):
        obj = MagicMock()
        obj.labels = {"staticmethod"}
        assert GreatDocs._sub_classify_function(obj) == "staticmethod"

    def test_property(self):
        obj = MagicMock()
        obj.labels = {"property"}
        assert GreatDocs._sub_classify_function(obj) == "property"

    def test_plain_function(self):
        obj = MagicMock()
        obj.labels = set()
        assert GreatDocs._sub_classify_function(obj) == "function"

    def test_labels_raises_falls_back(self):
        obj = MagicMock()
        type(obj).labels = property(lambda s: (_ for _ in ()).throw(Exception()))
        assert GreatDocs._sub_classify_function(obj) == "function"


class TestSubClassifyAttribute:
    def test_type_alias_via_kind(self):
        obj = MagicMock()
        obj.labels = set()
        obj.kind.value = "type alias"
        assert GreatDocs._sub_classify_attribute(obj) == "type_alias"

    def test_typevar_via_annotation(self):
        obj = MagicMock()
        obj.labels = set()
        obj.kind.value = "attribute"
        obj.annotation = "TypeVar('T')"
        assert GreatDocs._sub_classify_attribute(obj) == "typevar"

    def test_paramspec_via_annotation(self):
        obj = MagicMock()
        obj.labels = set()
        obj.kind.value = "attribute"
        obj.annotation = "ParamSpec('P')"
        assert GreatDocs._sub_classify_attribute(obj) == "typevar"

    def test_constant_fallback(self):
        obj = MagicMock()
        obj.labels = set()
        obj.kind.value = "attribute"
        obj.annotation = None
        assert GreatDocs._sub_classify_attribute(obj) == "constant"

    def test_kind_raises_falls_through(self):
        obj = MagicMock()
        obj.labels = set()
        type(obj).kind = property(lambda s: (_ for _ in ()).throw(Exception()))
        obj.annotation = None
        assert GreatDocs._sub_classify_attribute(obj) == "constant"


# ---------------------------------------------------------------------------
# Extract constant metadata
# ---------------------------------------------------------------------------


class TestExtractConstantMetadata:
    def test_stores_value_and_annotation(self):
        obj = MagicMock()
        obj.value = "42"
        obj.annotation = "int"
        categories = {"constant_metadata": {}}
        GreatDocs._extract_constant_metadata(obj, "MY_CONST", categories)
        assert categories["constant_metadata"]["MY_CONST"]["value"] == "42"
        assert categories["constant_metadata"]["MY_CONST"]["annotation"] == "int"

    def test_skips_long_value(self):
        obj = MagicMock()
        obj.value = "x" * 201
        obj.annotation = None
        categories = {"constant_metadata": {}}
        GreatDocs._extract_constant_metadata(obj, "BIG", categories)
        assert "BIG" not in categories["constant_metadata"]

    def test_none_value_skipped(self):
        obj = MagicMock()
        obj.value = None
        obj.annotation = "str"
        categories = {"constant_metadata": {}}
        GreatDocs._extract_constant_metadata(obj, "X", categories)
        assert "value" not in categories["constant_metadata"]["X"]
        assert categories["constant_metadata"]["X"]["annotation"] == "str"

    def test_value_exception_graceful(self):
        obj = MagicMock()
        type(obj).value = property(lambda s: (_ for _ in ()).throw(Exception()))
        obj.annotation = None
        categories = {"constant_metadata": {}}
        GreatDocs._extract_constant_metadata(obj, "BAD", categories)
        assert "BAD" not in categories["constant_metadata"]


# ---------------------------------------------------------------------------
# Empty categories
# ---------------------------------------------------------------------------


class TestEmptyCategories:
    def test_all_keys_present(self):
        cats = GreatDocs._empty_categories()
        assert "classes" in cats
        assert "functions" in cats
        assert "constants" in cats
        assert "type_aliases" in cats
        assert "constant_metadata" in cats
        assert cats["cyclic_alias_count"] == 0

    def test_returns_fresh_instance(self):
        a = GreatDocs._empty_categories()
        b = GreatDocs._empty_categories()
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
# Tag utilities
# ---------------------------------------------------------------------------


class TestSplitTagParts:
    def test_simple_slash(self):
        assert GreatDocs._split_tag_parts("A/B/C") == ["A", "B", "C"]

    def test_escaped_slash_preserved(self):
        assert GreatDocs._split_tag_parts(r"AI\/LLM") == ["AI/LLM"]

    def test_mixed_escaped_and_real(self):
        parts = GreatDocs._split_tag_parts(r"AI\/ML/Frameworks")
        assert parts == ["AI/ML", "Frameworks"]

    def test_empty_parts_stripped(self):
        assert GreatDocs._split_tag_parts("A//B") == ["A", "B"]


class TestTagSlug:
    def test_basic(self):
        assert GreatDocs._tag_slug("User Guide") == "user-guide"

    def test_special_chars(self):
        assert GreatDocs._tag_slug("AI/ML & Data!") == "ai-ml-data"

    def test_escaped_slash(self):
        assert GreatDocs._tag_slug(r"AI\/LLM") == "ai-llm"


class TestTagTooltip:
    def test_empty_pages(self):
        assert GreatDocs._tag_tooltip([]) == ""

    def test_single_page_with_section(self):
        pages = [{"title": "Intro", "section": "Guide"}]
        result = GreatDocs._tag_tooltip(pages)
        assert "1" in result
        assert "Guide" in result

    def test_multiple_pages_no_section(self):
        pages = [{"title": "A"}, {"title": "B"}]
        result = GreatDocs._tag_tooltip(pages)
        assert "2" in result


class TestTagHeadingPill:
    def test_simple_pill(self):
        result = GreatDocs._tag_heading_pill("Basics", "<svg/>")
        assert "gd-tag-pill" in result
        assert "Basics" in result
        assert "<svg/>" in result

    def test_segmented_pill_with_parent(self):
        result = GreatDocs._tag_heading_pill("Child", "", parent="Parent", parent_icon="<i/>")
        assert "gd-tag-pill-segmented" in result
        assert "Parent" in result
        assert "Child" in result
        assert "<i/>" in result

    def test_tooltip_attribute(self):
        result = GreatDocs._tag_heading_pill("Tag", "", tooltip="5 pages")
        assert 'data-tippy-content="5 pages"' in result


class TestGetTagIconHtml:
    def test_no_icon_returns_empty(self):
        result = GreatDocs._get_tag_icon_html("Unknown", {})
        assert result == ""

    def test_icon_found_returns_svg_span(self):
        with patch("great_docs._icons.get_icon_svg", return_value="<svg>ok</svg>"):
            result = GreatDocs._get_tag_icon_html("Guide", {"Guide": "book"})
        assert "<svg>ok</svg>" in result
        assert "margin-right" in result

    def test_svg_returns_empty_when_icon_missing(self):
        with patch("great_docs._icons.get_icon_svg", return_value=None):
            result = GreatDocs._get_tag_icon_html("X", {"X": "missing-icon"})
        assert result == ""


# ---------------------------------------------------------------------------
# HTML escape and derive page title
# ---------------------------------------------------------------------------


class TestHtmlEscape:
    def test_escapes_angle_brackets(self):
        assert "&lt;" in GreatDocs._html_escape("<script>")
        assert "&amp;" in GreatDocs._html_escape("A & B")

    def test_escapes_quotes(self):
        assert "&quot;" in GreatDocs._html_escape('"hello"')


class TestDerivePageTitle:
    def test_converts_hyphens_and_underscores(self, tmp_path):
        gd = _make_gd(tmp_path)
        assert gd._derive_page_title(Path("user-guide_intro.qmd")) == "User Guide Intro"


# ---------------------------------------------------------------------------
# Strip frontmatter
# ---------------------------------------------------------------------------


class TestStripFrontmatter:
    def test_removes_frontmatter(self, tmp_path):
        gd = _make_gd(tmp_path)
        content = "---\ntitle: Hello\n---\nBody text"
        assert gd._strip_frontmatter(content) == "Body text"

    def test_no_frontmatter_unchanged(self, tmp_path):
        gd = _make_gd(tmp_path)
        content = "Just body text"
        assert gd._strip_frontmatter(content) == content

    def test_incomplete_frontmatter_unchanged(self, tmp_path):
        gd = _make_gd(tmp_path)
        content = "---\ntitle: Hello\nNo closing"
        assert gd._strip_frontmatter(content) == content


# ---------------------------------------------------------------------------
# Detect install extras
# ---------------------------------------------------------------------------


class TestDetectInstallExtras:
    def test_finds_dev_and_docs(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project.optional-dependencies]\ndev = ["pytest"]\ndocs = ["sphinx"]\n',
            encoding="utf-8",
        )
        result = GreatDocs._detect_install_extras(tmp_path)
        assert "dev" in result
        assert "docs" in result

    def test_no_pyproject_returns_empty(self, tmp_path):
        assert GreatDocs._detect_install_extras(tmp_path) == ""

    def test_no_optional_deps_returns_empty(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'pkg'\n", encoding="utf-8")
        assert GreatDocs._detect_install_extras(tmp_path) == ""

    def test_invalid_toml_returns_empty(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("{{{{invalid", encoding="utf-8")
        assert GreatDocs._detect_install_extras(tmp_path) == ""


# ---------------------------------------------------------------------------
# Inspect repo git needs
# ---------------------------------------------------------------------------


class TestInspectRepoGitNeeds:
    def test_no_config_returns_none(self, tmp_path):
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "none"

    def test_versions_returns_full(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("versions:\n  - v1.0\n  - v2.0\n", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "full"

    def test_show_dates_returns_full(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("show_dates: true\n", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "full"

    def test_show_dates_in_site_returns_full(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("site:\n  show_dates: true\n", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "full"

    def test_source_without_branch_returns_tags(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("source:\n  repository: https://github.com/org/repo\n", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "tags"

    def test_source_with_branch_returns_none(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("source:\n  branch: main\n", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "none"

    def test_invalid_yaml_returns_none(self, tmp_path):
        cfg = tmp_path / "great-docs.yml"
        cfg.write_text("{{invalid yaml", encoding="utf-8")
        assert GreatDocs._inspect_repo_git_needs(tmp_path) == "none"


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
        monkeypatch.setattr(gd, "_discover_package_exports", lambda p: ["X"])
        result = gd._get_package_exports("mypkg")
        assert result == ["X"]
        assert gd._cached_package_name == "mypkg"
        assert gd._cached_exports == ["X"]

    def test_fallback_to_parse_when_discover_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd._cached_package_name = None
        gd._cached_exports = None
        monkeypatch.setattr(gd, "_discover_package_exports", lambda p: None)
        monkeypatch.setattr(gd, "_parse_package_exports", lambda p: ["Y"])
        result = gd._get_package_exports("mypkg")
        assert result == ["Y"]


# ---------------------------------------------------------------------------
# _add_tags_to_navbar – all branches
# ---------------------------------------------------------------------------


class TestAddTagsToNavbar:

    def test_no_quarto_yml_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        gd._add_tags_to_navbar()

    def test_no_navbar_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        quarto = gd.build_dir / "_quarto.yml"
        quarto.write_text("website:\n  title: Test\n", encoding="utf-8")
        gd._add_tags_to_navbar()

    def test_no_left_key_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        quarto = gd.build_dir / "_quarto.yml"
        quarto.write_text("website:\n  navbar:\n    right:\n      - icon: github\n", encoding="utf-8")
        gd._add_tags_to_navbar()

    def test_already_present_skips(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        quarto = gd.build_dir / "_quarto.yml"
        quarto.write_text(
            "website:\n  navbar:\n    left:\n      - text: Site Tags\n        href: tags/index.qmd\n",
            encoding="utf-8",
        )
        gd._add_tags_to_navbar()
        content = quarto.read_text(encoding="utf-8")
        assert content.count("Site Tags") == 1

    def test_adds_tags_link(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        quarto = gd.build_dir / "_quarto.yml"
        quarto.write_text(
            "website:\n  navbar:\n    left:\n      - text: Reference\n        href: reference/index.qmd\n",
            encoding="utf-8",
        )
        gd._add_tags_to_navbar()
        content = quarto.read_text(encoding="utf-8")
        assert "Tags" in content


# ---------------------------------------------------------------------------
# _update_navbar_github_link – widget vs icon, replace vs append
# ---------------------------------------------------------------------------


class TestUpdateNavbarGithubLink:

    @staticmethod
    def _wrap(navbar):
        return {"website": {"navbar": navbar}}

    def test_no_repo_url_returns_early(self, tmp_path):
        gd = _make_gd(tmp_path)
        navbar = {"right": []}
        gd._update_navbar_github_link(self._wrap(navbar), None, None, None, "icon")
        assert navbar["right"] == []

    def test_icon_style_appends(self, tmp_path):
        gd = _make_gd(tmp_path)
        navbar = {"right": []}
        gd._update_navbar_github_link(self._wrap(navbar), "owner", "repo", "https://github.com/o/r", "icon")
        assert navbar["right"] == [{"icon": "github", "href": "https://github.com/o/r"}]

    def test_widget_style_with_stats(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_fetch_github_repo_stats", lambda o, r: {"stars": 100, "forks": 20})
        navbar = {"right": []}
        gd._update_navbar_github_link(self._wrap(navbar), "owner", "repo", "https://github.com/o/r", "widget")
        assert len(navbar["right"]) == 1
        assert "github-widget" in str(navbar["right"][0])
        assert 'data-stars="100"' in str(navbar["right"][0])

    def test_widget_style_no_stats(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_fetch_github_repo_stats", lambda o, r: None)
        navbar = {"right": []}
        gd._update_navbar_github_link(self._wrap(navbar), "owner", "repo", "https://github.com/o/r", "widget")
        assert "github-widget" in str(navbar["right"][0])
        assert "data-stars" not in str(navbar["right"][0])

    def test_replaces_existing_icon_entry(self, tmp_path):
        gd = _make_gd(tmp_path)
        navbar = {"right": [{"icon": "github", "href": "old"}]}
        gd._update_navbar_github_link(self._wrap(navbar), "o", "r", "https://new.com", "icon")
        assert navbar["right"] == [{"icon": "github", "href": "https://new.com"}]

    def test_replaces_existing_widget_entry(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_fetch_github_repo_stats", lambda o, r: None)
        navbar = {"right": [{"text": '<div id="github-widget"></div>'}]}
        gd._update_navbar_github_link(self._wrap(navbar), "o", "r", "https://x.com", "widget")
        assert len(navbar["right"]) == 1

    def test_creates_right_list_if_missing(self, tmp_path):
        gd = _make_gd(tmp_path)
        navbar = {}
        gd._update_navbar_github_link(self._wrap(navbar), "o", "r", "https://github.com/o/r", "icon")
        assert "right" in navbar
        assert navbar["right"] == [{"icon": "github", "href": "https://github.com/o/r"}]


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
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            arguments=[{"name": "FILES", "name_display": "FILES", "required": True, "nargs": -1}]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "FILES..." in result

    def test_hidden_option_skipped(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            options=[
                {"name": "--verbose", "name_display": "--verbose", "hidden": True, "help": "debug"},
                {"name": "--output", "name_display": "--output", "hidden": False, "help": "output file"},
            ]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "output" in result
        assert "verbose" not in result

    def test_option_with_type_and_default(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            options=[{
                "name": "--count",
                "name_display": "--count",
                "type": "INT",
                "default": "5",
                "is_flag": False,
                "help": "Number of items",
            }]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "INT" in result
        assert "5" in result

    def test_required_option(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            options=[{
                "name": "--name",
                "name_display": "--name",
                "required": True,
                "help": "Your name",
            }]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "**Required.**" in result

    def test_envvar_option(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            options=[{
                "name": "--token",
                "name_display": "--token",
                "envvar": "MY_TOKEN",
                "help": "API token",
            }]
        )
        result = gd._generate_cli_command_page(cli_info, is_main=True)
        assert "`MY_TOKEN`" in result

    def test_envvar_list_joined(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        cli_info = self._make_cli_info(
            options=[{
                "name": "--token",
                "name_display": "--token",
                "envvar": ["TOKEN_A", "TOKEN_B"],
                "help": "API token",
            }]
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
# _write_object_types_json – basic, member_types fallback, constant_metadata
# ---------------------------------------------------------------------------


class TestWriteObjectTypesJson:

    def test_writes_object_types(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        gd._suppress_artifact_writes = False
        categories = {
            "classes": ["MyClass"],
            "functions": ["my_func"],
            "class_method_names": {"MyClass": ["method_a"]},
            "class_member_types": {},
        }
        gd._write_object_types_json(categories)
        import json
        types_path = gd.build_dir / "_object_types.json"
        assert types_path.exists()
        data = json.loads(types_path.read_text())
        assert data["MyClass"] == "class"
        assert data["my_func"] == "function"
        assert data["MyClass.method_a"] == "method"

    def test_member_types_fallback(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        gd._suppress_artifact_writes = False
        categories = {
            "classes": ["Foo"],
            "class_method_names": {"Foo": ["bar"]},
            "class_member_types": {"Foo.bar": "property", "Foo.baz": "attribute"},
        }
        gd._write_object_types_json(categories)
        import json
        data = json.loads((gd.build_dir / "_object_types.json").read_text())
        assert data["Foo.bar"] == "property"
        assert data["Foo.baz"] == "attribute"

    def test_constant_metadata_sidecar(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        gd._suppress_artifact_writes = False
        categories = {
            "constants": ["MY_CONST"],
            "class_method_names": {},
            "class_member_types": {},
            "constant_metadata": {"MY_CONST": {"value": "42", "annotation": "int"}},
        }
        gd._write_object_types_json(categories)
        import json
        values_path = gd.build_dir / "_constant_values.json"
        assert values_path.exists()
        data = json.loads(values_path.read_text())
        assert data["MY_CONST"]["value"] == "42"

    def test_suppressed_writes_nothing(self, tmp_path):
        gd = _make_gd(tmp_path)
        gd._suppress_artifact_writes = True
        gd._write_object_types_json({"classes": ["X"], "class_method_names": {}, "class_member_types": {}})
        assert not (gd.build_dir / "_object_types.json").exists()


# ---------------------------------------------------------------------------
# _generate_package_info_page – early returns and marker branch
# ---------------------------------------------------------------------------


class TestGeneratePackageInfoPage:

    def test_disabled_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "package_info_page", False)
        assert gd._generate_package_info_page() is None

    def test_not_python_project_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "package_info_page", True)
        _patch_cfg(monkeypatch, gd, "is_python_project", False)
        assert gd._generate_package_info_page() is None

    def test_no_deps_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "package_info_page", True)
        _patch_cfg(monkeypatch, gd, "is_python_project", True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {"dependencies": [], "optional_dependencies_full": {}, "requires_python": ""},
        )
        assert gd._generate_package_info_page() is None

    def test_generates_page_with_optional_markers(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "package_info_page", True)
        _patch_cfg(monkeypatch, gd, "is_python_project", True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {
                "dependencies": [{"name": "click", "specifier": ">=8.0"}],
                "optional_dependencies_full": {
                    "dev": [
                        {"name": "pytest", "specifier": ">=7.0", "marker": 'python_version>="3.9"'},
                    ]
                },
                "requires_python": ">=3.9",
            },
        )
        monkeypatch.setattr(gd, "_fetch_pypi_dates", lambda names: {})
        result = gd._generate_package_info_page()
        assert result == "package-info.qmd"
        content = (gd.build_dir / "package-info.qmd").read_text()
        assert "click" in content
        assert "pytest" in content

    def test_empty_optional_group(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "package_info_page", True)
        _patch_cfg(monkeypatch, gd, "is_python_project", True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        monkeypatch.setattr(
            gd,
            "_get_package_metadata",
            lambda: {
                "dependencies": [{"name": "click", "specifier": ">=8.0"}],
                "optional_dependencies_full": {"empty": []},
                "requires_python": "",
            },
        )
        monkeypatch.setattr(gd, "_fetch_pypi_dates", lambda names: {})
        result = gd._generate_package_info_page()
        assert result == "package-info.qmd"
        content = (gd.build_dir / "package-info.qmd").read_text()
        assert "No dependencies declared" in content


# ---------------------------------------------------------------------------
# _generate_robots_txt – llms.txt and sitemap branches
# ---------------------------------------------------------------------------


class TestGenerateRobotsTxt:

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
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: None)
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "Allow: /" in content

    def test_no_site_dir_skips(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "robots_enabled", True)
        gd._generate_robots_txt()
        assert not (gd.build_dir / "_site" / "robots.txt").exists()

    def test_disallow_rules(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch, robots_disallow=["/private/", "/admin/"])
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: None)
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "Disallow: /private/" in content
        assert "Disallow: /admin/" in content

    def test_extra_rules(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(
            tmp_path, monkeypatch,
            robots_extra_rules=["User-agent: GPTBot", "Disallow: /"],
        )
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: None)
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "User-agent: GPTBot" in content

    def test_sitemap_reference(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch, sitemap_enabled=True)
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: "https://example.com/")
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "Sitemap: https://example.com/sitemap.xml" in content

    def test_llms_txt_references(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch)
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: "https://example.com/")
        (site_dir / "llms.txt").write_text("llms content", encoding="utf-8")
        (site_dir / "llms-full.txt").write_text("full content", encoding="utf-8")
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "Llms-txt: https://example.com/llms.txt" in content
        assert "Llms-txt: https://example.com/llms-full.txt" in content

    def test_llms_txt_only_one(self, tmp_path, monkeypatch):
        gd, site_dir = self._setup_gd(tmp_path, monkeypatch)
        monkeypatch.setattr(gd, "_get_canonical_base_url", lambda: "https://example.com/")
        (site_dir / "llms.txt").write_text("llms content", encoding="utf-8")
        gd._generate_robots_txt()
        content = (site_dir / "robots.txt").read_text()
        assert "Llms-txt: https://example.com/llms.txt" in content
        assert "llms-full.txt" not in content


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
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {"versions": [{"tag": "v1.0"}, {"tag": "v2.0"}]},
        )
        _patch_cfg(monkeypatch, gd, "versions", [{"tag": "v1.0"}, {"tag": "v2.0"}])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector(quarto_yml)
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
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector(quarto_yml)
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
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector(quarto_yml)
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
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", False)
        gd._inject_version_selector(quarto_yml)
        content = quarto_yml.read_text()
        assert "gd-version-warning-banner" in content

    def test_inserts_before_navbar_widgets(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = gd.build_dir / "_quarto.yml"
        quarto_yml.write_text(
            'project:\n  resources: []\nformat:\n  html:\n    include-in-header: []\n    include-after-body:\n      - text: \'<script src="navbar-widgets.js"></script>\'\n',
            encoding="utf-8",
        )
        mock_versions = [MagicMock(tag="v1.0")]
        monkeypatch.setattr(
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector(quarto_yml)
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
            "great_docs._versioning.parse_versions_config",
            lambda v: mock_versions,
        )
        monkeypatch.setattr(
            "great_docs._versioning.build_version_map",
            lambda versions, pages: {},
        )
        _patch_cfg(monkeypatch, gd, "versions", [])
        _patch_cfg(monkeypatch, gd, "version_warning_banner", True)
        gd._inject_version_selector(quarto_yml)


# ---------------------------------------------------------------------------
# _persist_freeze_cache – merge and JS newline
# ---------------------------------------------------------------------------


class TestPersistFreezeCache:

    def test_no_freeze_sources_returns_none(self, tmp_path):
        gd = _make_gd(tmp_path)
        result = gd._persist_freeze_cache()
        assert result is None

    def test_merges_freeze_caches(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(
            "great_docs.core.is_great_docs_build_dir",
            lambda d: d.name.startswith("great-docs-"),
        )

        v1_freeze = tmp_path / "great-docs-v1" / "_freeze" / "page1.json"
        v1_freeze.parent.mkdir(parents=True)
        v1_freeze.write_text('{"v": 1}', encoding="utf-8")

        v2_freeze = tmp_path / "great-docs-v2" / "_freeze" / "page1.json"
        v2_freeze.parent.mkdir(parents=True)
        v2_freeze.write_text('{"v": 2}', encoding="utf-8")

        result = gd._persist_freeze_cache()
        assert result is not None
        merged = tmp_path / "_freeze" / "page1.json"
        assert merged.exists()
        assert '"v": 2' in merged.read_text()

    def test_js_newline_appended(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(
            "great_docs.core.is_great_docs_build_dir",
            lambda d: d.name.startswith("great-docs-"),
        )

        freeze_dir = tmp_path / "great-docs-v1" / "_freeze"
        js_file = freeze_dir / "chunk.js"
        js_file.parent.mkdir(parents=True)
        js_file.write_bytes(b"var x = 1;")

        gd._persist_freeze_cache()
        merged_js = tmp_path / "_freeze" / "chunk.js"
        assert merged_js.read_bytes().endswith(b"\n")


# ---------------------------------------------------------------------------
# _generate_source_links_json – _make_github_url branches, class methods
# ---------------------------------------------------------------------------


class TestGenerateSourceLinksJson:

    def test_disabled_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": False})
        gd._generate_source_links_json("mypkg")
        assert not (gd.build_dir / "_source_links.json").exists()

    def test_no_github_info_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: (None, None, None))
        gd._generate_source_links_json("mypkg")
        assert not (gd.build_dir / "_source_links.json").exists()

    def test_no_exports_returns_early(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("owner", "repo", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: None)
        gd._generate_source_links_json("mypkg")
        assert not (gd.build_dir / "_source_links.json").exists()

    def test_writes_source_links(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("owner", "repo", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["MyFunc"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: tmp_path / "src" / "mypkg")
        monkeypatch.setattr(
            gd,
            "_get_source_location",
            lambda pkg, name: {"file": "module.py", "start_line": 10, "end_line": 20},
        )
        mock_pkg = MagicMock()
        mock_pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda p: mock_pkg)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "MyFunc" in data
        assert "#L10-L20" in data["MyFunc"]["url"]

    def test_single_line_anchor(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("o", "r", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["F"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: tmp_path)
        monkeypatch.setattr(
            gd,
            "_get_source_location",
            lambda pkg, name: {"file": "f.py", "start_line": 5, "end_line": 5},
        )
        mock_pkg = MagicMock()
        mock_pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda p: mock_pkg)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "#L5" in data["F"]["url"]
        assert "#L5-L" not in data["F"]["url"]

    def test_source_path_override(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            gd, "_get_package_metadata",
            lambda: {"source_link_enabled": True, "source_link_path": "src/mypkg"},
        )
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("o", "r", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["F"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: tmp_path)
        monkeypatch.setattr(
            gd,
            "_get_source_location",
            lambda pkg, name: {"file": "/abs/path/module.py", "start_line": 1, "end_line": 1},
        )
        mock_pkg = MagicMock()
        mock_pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda p: mock_pkg)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "src/mypkg/module.py" in data["F"]["url"]

    def test_absolute_filepath_relative_to_root(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        pkg_root = tmp_path / "src" / "mypkg"
        pkg_root.mkdir(parents=True)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("o", "r", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["F"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: pkg_root)
        monkeypatch.setattr(
            gd,
            "_get_source_location",
            lambda pkg, name: {"file": str(pkg_root / "core.py"), "start_line": 1, "end_line": 1},
        )
        mock_pkg = MagicMock()
        mock_pkg.members = {}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda p: mock_pkg)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "core.py" in data["F"]["url"]

    def test_griffe_exception_sets_pkg_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("o", "r", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["F"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: tmp_path)
        monkeypatch.setattr(
            gd,
            "_get_source_location",
            lambda pkg, name: {"file": "f.py", "start_line": 1, "end_line": 1},
        )

        def raise_err(p):
            raise RuntimeError("griffe failed")

        monkeypatch.setattr(gd, "_get_griffe_package", raise_err)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "F" in data

    def test_class_methods_included(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(gd, "_get_package_metadata", lambda: {"source_link_enabled": True})
        monkeypatch.setattr(gd, "_get_github_repo_info", lambda: ("o", "r", "https://github.com/o/r"))
        monkeypatch.setattr(gd, "_detect_git_ref", lambda: "main")
        monkeypatch.setattr(gd, "_get_package_exports", lambda p: ["MyClass"])
        monkeypatch.setattr(gd, "_find_package_root", lambda: tmp_path)

        cls_obj = MagicMock()
        cls_obj.kind.value = "class"
        method_member = MagicMock()
        method_member.kind.value = "method"
        cls_obj.members = {"__init__": MagicMock(), "do_stuff": method_member, "_private": MagicMock()}
        cls_obj.members["__init__"].kind.value = "function"
        cls_obj.members["_private"].kind.value = "function"

        mock_pkg = MagicMock()
        mock_pkg.members = {"MyClass": cls_obj}
        monkeypatch.setattr(gd, "_get_griffe_package", lambda p: mock_pkg)

        call_count = {"n": 0}

        def fake_source_loc(pkg, name):
            call_count["n"] += 1
            return {"file": "mod.py", "start_line": call_count["n"], "end_line": call_count["n"] + 5}

        monkeypatch.setattr(gd, "_get_source_location", fake_source_loc)
        gd._generate_source_links_json("mypkg")
        import json
        data = json.loads((gd.build_dir / "_source_links.json").read_text())
        assert "MyClass" in data
        assert "MyClass.do_stuff" in data
        assert "MyClass._private" not in data


# ---------------------------------------------------------------------------
# _generate_tags_json – shadow tags, tag-location override, icon resolution
# ---------------------------------------------------------------------------


class TestGenerateTagsJson:

    def _setup_gd(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd.build_dir.mkdir(parents=True, exist_ok=True)
        _patch_cfg(monkeypatch, gd, "language", "en")
        _patch_cfg(monkeypatch, gd, "tags_shadow", {"internal"})
        _patch_cfg(monkeypatch, gd, "sections", [])
        _patch_cfg(monkeypatch, gd, "tags_icons", {})
        _patch_cfg(monkeypatch, gd, "tags_hierarchical", False)
        _patch_cfg(monkeypatch, gd, "tags_location", "bottom")
        return gd

    def test_writes_tags_json(self, tmp_path, monkeypatch):
        gd = self._setup_gd(tmp_path, monkeypatch)
        tag_index = {"mytag": [{"title": "Page 1", "href": "page1.qmd", "section": "Guide"}]}
        gd._generate_tags_json(tag_index)
        import json
        data = json.loads((gd.build_dir / "_tags.json").read_text())
        assert "page_tags" in data
        assert "tag_meta" in data
        assert data["tag_meta"]["mytag"]["count"] == 1

    def test_shadow_tag_scanned(self, tmp_path, monkeypatch):
        gd = self._setup_gd(tmp_path, monkeypatch)
        ug_dir = gd.build_dir / "user-guide"
        ug_dir.mkdir()
        qmd = ug_dir / "page.qmd"
        qmd.write_text("---\ntags:\n  - internal\ntitle: Secret\n---\nbody\n", encoding="utf-8")
        tag_index = {}
        gd._generate_tags_json(tag_index)
        import json
        data = json.loads((gd.build_dir / "_tags.json").read_text())
        assert "internal" in data["shadow"]

    def test_tag_location_override(self, tmp_path, monkeypatch):
        gd = self._setup_gd(tmp_path, monkeypatch)
        ug_dir = gd.build_dir / "user-guide"
        ug_dir.mkdir()
        qmd = ug_dir / "page.qmd"
        qmd.write_text("---\ntags:\n  - visible\ntag-location: top\ntitle: P\n---\nbody\n", encoding="utf-8")
        tag_index = {"visible": [{"title": "P", "href": "user-guide/page.qmd", "section": "UG"}]}
        gd._generate_tags_json(tag_index)
        import json
        data = json.loads((gd.build_dir / "_tags.json").read_text())
        assert data["page_tag_locations"].get("user-guide/page.qmd") == "top"

    def test_icon_resolution(self, tmp_path, monkeypatch):
        gd = self._setup_gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "tags_icons", {"mytag": "star"})
        monkeypatch.setattr("great_docs._icons.get_icon_svg", lambda name, **kw: "<svg>star</svg>")
        tag_index = {"mytag": [{"title": "P", "href": "p.qmd", "section": "S"}]}
        gd._generate_tags_json(tag_index)
        import json
        data = json.loads((gd.build_dir / "_tags.json").read_text())
        assert data["icons"]["mytag"] == "<svg>star</svg>"

    def test_unknown_icon_warns(self, tmp_path, monkeypatch, capsys):
        gd = self._setup_gd(tmp_path, monkeypatch)
        _patch_cfg(monkeypatch, gd, "tags_icons", {"bad": "nonexistent"})
        monkeypatch.setattr("great_docs._icons.get_icon_svg", lambda name, **kw: None)
        tag_index = {}
        gd._generate_tags_json(tag_index)
        captured = capsys.readouterr()
        assert "Unknown tag icon" in captured.out


# ---------------------------------------------------------------------------
# _create_api_sections_from_config – include_inherited
# ---------------------------------------------------------------------------


class TestCreateApiSectionsFromConfig:

    def test_no_reference_returns_none(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", None)
        assert gd._create_api_sections_from_config("mypkg") is None

    def test_include_inherited_on_explicit_members(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", [
            {
                "title": "Classes",
                "contents": [
                    {"name": "MyClass", "members": ["method_a"], "include_inherited": True},
                ],
            }
        ])
        monkeypatch.setattr(
            gd, "_categorize_referenced_objects",
            lambda pkg, ref: {"classes": [], "functions": []},
        )
        result = gd._create_api_sections_from_config("mypkg")
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
        _patch_cfg(monkeypatch, gd, "reference", [
            {
                "title": "Classes",
                "contents": [
                    {"name": "MyClass", "include_inherited": True},
                ],
            }
        ])
        monkeypatch.setattr(
            gd, "_categorize_referenced_objects",
            lambda pkg, ref: {"classes": [], "functions": []},
        )
        result = gd._create_api_sections_from_config("mypkg")
        found = False
        for section in result:
            for item in section.get("contents", []):
                if isinstance(item, dict) and item.get("include_inherited") is True:
                    found = True
        assert found

    def test_plain_string_when_no_include_inherited(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        _patch_cfg(monkeypatch, gd, "reference", [
            {
                "title": "Funcs",
                "contents": [
                    {"name": "my_func"},
                ],
            }
        ])
        monkeypatch.setattr(
            gd, "_categorize_referenced_objects",
            lambda pkg, ref: {"classes": [], "functions": []},
        )
        result = gd._create_api_sections_from_config("mypkg")
        for section in result:
            for item in section.get("contents", []):
                if item == "my_func":
                    return
        raise AssertionError("Expected plain string 'my_func' in contents")


# ---------------------------------------------------------------------------
# _refresh_api_reference_config – early return when already configured
# ---------------------------------------------------------------------------


class TestRefreshApiReferenceConfig:

    def test_skips_when_already_done(self, tmp_path, monkeypatch):
        gd = _make_gd(tmp_path)
        gd._api_discovery_done = True
        gd._refresh_api_reference_config()
        assert not (gd.build_dir / "_quarto.yml").exists()
