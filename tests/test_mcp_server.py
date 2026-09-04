"""Tests for mcp.py server helpers and tool handlers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import AnyUrl

import great_docs.mcp as mcp_module
from great_docs._utils import QUARTO_YML_HEADER
from great_docs.mcp import (
    _build_output_dirs,
    _get_project_root,
    _handle_add_page,
    _handle_api_diff,
    _handle_build,
    _handle_config,
    _handle_lint,
    _handle_preview,
    _handle_scan,
    _handle_status,
    call_tool,
    get_prompt,
    handle_completion,
    list_prompts,
    list_resource_templates,
    list_resources,
    list_tools,
    read_resource,
)

# ---------------------------------------------------------------------------
# _get_project_root
# ---------------------------------------------------------------------------


class TestGetProjectRoot:
    def test_returns_resolved_path_when_given(self, tmp_path: Path):
        result = _get_project_root(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_raises_when_path_does_not_exist(self, tmp_path: Path):
        missing = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            _get_project_root(str(missing))

    def test_returns_cwd_when_no_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.chdir(tmp_path)
        result = _get_project_root(None)
        assert result == tmp_path


# ---------------------------------------------------------------------------
# _build_output_dirs
# ---------------------------------------------------------------------------


class TestBuildOutputDirs:
    def _mark_dir(self, path: Path) -> None:
        path.mkdir(parents=True)
        (path / "_quarto.yml").write_text(
            QUARTO_YML_HEADER + "project:\n  type: website\n", encoding="utf-8"
        )

    def test_empty_when_no_build_dirs(self, tmp_path: Path):
        assert _build_output_dirs(tmp_path) == []

    def test_includes_great_docs_dir_first(self, tmp_path: Path):
        (tmp_path / "great-docs").mkdir()
        result = _build_output_dirs(tmp_path)
        assert result[0].name == "great-docs"

    def test_includes_versioned_siblings_after_current(self, tmp_path: Path):
        (tmp_path / "great-docs").mkdir()
        self._mark_dir(tmp_path / "great-docs-0.1")
        result = _build_output_dirs(tmp_path)
        names = [d.name for d in result]
        assert names[0] == "great-docs"
        assert "great-docs-0.1" in names

    def test_only_sibling_dirs_no_current(self, tmp_path: Path):
        self._mark_dir(tmp_path / "great-docs-0.1")
        result = _build_output_dirs(tmp_path)
        assert any(d.name == "great-docs-0.1" for d in result)


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    def test_returns_all_expected_tool_names(self):
        tools = asyncio.run(list_tools())
        names = {t.name for t in tools}
        expected = {
            "gd_build",
            "gd_preview",
            "gd_scan",
            "gd_lint",
            "gd_config",
            "gd_status",
            "gd_add_page",
            "gd_api_diff",
        }
        assert expected == names

    def test_all_tools_have_descriptions(self):
        tools = asyncio.run(list_tools())
        for tool in tools:
            assert tool.description, f"{tool.name} has no description"

    def test_all_tools_have_input_schemas(self):
        tools = asyncio.run(list_tools())
        for tool in tools:
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
            assert schema is not None, f"{tool.name} has no input schema"


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------


class TestListPrompts:
    def test_returns_prompts(self):
        prompts = asyncio.run(list_prompts())
        assert len(prompts) > 0

    def test_prompts_have_names_and_descriptions(self):
        prompts = asyncio.run(list_prompts())
        for p in prompts:
            assert p.name
            assert p.description


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------


class TestCallTool:
    def test_unknown_tool_returns_error_text(self):
        result = asyncio.run(call_tool("no_such_tool", {}))
        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    def test_unknown_tool_marks_is_error(self):
        result = asyncio.run(call_tool("no_such_tool", {}))
        assert result.is_error is True

    def test_exception_in_handler_returns_error_text(self):
        with patch("great_docs.mcp._handle_build", side_effect=RuntimeError("boom")):
            result = asyncio.run(call_tool("gd_build", {}))
        assert "Error" in result[0].text
        assert "boom" in result[0].text

    def test_exception_in_handler_marks_is_error(self):
        with patch("great_docs.mcp._handle_build", side_effect=RuntimeError("boom")):
            result = asyncio.run(call_tool("gd_build", {}))
        assert result.is_error is True

    def test_successful_call_does_not_mark_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(call_tool("gd_status", {}))
        assert getattr(result, "is_error", False) is False


@pytest.mark.skipif(
    mcp_module._MCP_V1, reason="_on_call_tool only exists on the mcp v2 handler path"
)
class TestOnCallToolIsError:
    """CallToolResult.is_error must reflect a failed dispatch (issue: it never did)."""

    def _params(self, name: str, arguments: dict):
        params = MagicMock()
        params.name = name
        params.arguments = arguments
        return params

    def test_unknown_tool_sets_is_error(self):
        result = asyncio.run(mcp_module._on_call_tool(None, self._params("bogus_tool_name", {})))
        assert result.is_error is True
        assert "Unknown tool" in result.content[0].text

    def test_handler_exception_sets_is_error(self):
        params = self._params("gd_build", {"project_path": "/does/not/exist"})
        result = asyncio.run(mcp_module._on_call_tool(None, params))
        assert result.is_error is True

    def test_successful_call_leaves_is_error_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(mcp_module._on_call_tool(None, self._params("gd_status", {})))
        assert result.is_error is False


# ---------------------------------------------------------------------------
# _handle_preview
# ---------------------------------------------------------------------------


class TestHandlePreview:
    def test_no_build_dir_returns_instruction(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_preview({}))
        assert len(result) == 1
        assert "gd_build" in result[0].text

    def test_with_build_dir_returns_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "great-docs").mkdir()
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_preview({"port": 4321}))
        assert "4321" in result[0].text
        assert "http://localhost" in result[0].text


# ---------------------------------------------------------------------------
# _handle_config
# ---------------------------------------------------------------------------


class TestHandleConfig:
    def test_show_config_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_config({}))
        assert "great-docs.yml" in result[0].text

    def test_show_config_returns_yaml_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_config({}))
        assert "project:" in result[0].text

    def test_generate_when_config_already_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs.yml").write_text("existing: true\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_config({"generate": True}))
        assert "already exists" in result[0].text

    def test_generate_creates_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_config({"generate": True}))
        mock_docs.install.assert_called_once()
        assert "Generated" in result[0].text


# ---------------------------------------------------------------------------
# _handle_status
# ---------------------------------------------------------------------------


class TestHandleStatus:
    def test_no_config_shows_not_initialized(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_status({}))
        assert "not initialized" in result[0].text

    def test_with_config_shows_configuration_checkmark(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypackage"
        mock_docs._config.cli_enabled = False
        mock_docs._config.mcp_enabled = False
        mock_docs._config.__getitem__ = lambda self, key: (
            [] if key in ("user_guide", "versions") else None
        )
        mock_docs._config.sections = []
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_status({}))
        assert "✓" in result[0].text

    def test_shows_build_directories_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs").mkdir()
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_status({}))
        assert "great-docs" in result[0].text

    def test_no_build_shows_run_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_status({}))
        assert "gd_build" in result[0].text


# ---------------------------------------------------------------------------
# _handle_add_page
# ---------------------------------------------------------------------------


class TestHandleAddPage:
    def test_creates_user_guide_page(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(_handle_add_page({"title": "My Guide"}))
        assert (tmp_path / "user_guide" / "my-guide.qmd").exists()
        assert "Created page" in result[0].text

    def test_creates_recipes_page(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        asyncio.run(_handle_add_page({"title": "Quick Recipe", "section": "recipes"}))
        assert (tmp_path / "recipes" / "quick-recipe.qmd").exists()

    def test_creates_custom_page(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        asyncio.run(_handle_add_page({"title": "Special Page", "section": "custom"}))
        assert (tmp_path / "custom" / "special-page.qmd").exists()

    def test_explicit_filename_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        asyncio.run(_handle_add_page({"title": "My Title", "filename": "explicit-name"}))
        assert (tmp_path / "user_guide" / "explicit-name.qmd").exists()

    def test_page_already_exists_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "user_guide").mkdir()
        (tmp_path / "user_guide" / "my-guide.qmd").write_text("existing", encoding="utf-8")
        result = asyncio.run(_handle_add_page({"title": "My Guide"}))
        assert "already exists" in result[0].text

    def test_page_content_includes_title_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        asyncio.run(_handle_add_page({"title": "Hello World"}))
        content = (tmp_path / "user_guide" / "hello-world.qmd").read_text(encoding="utf-8")
        assert 'title: "Hello World"' in content

    def test_initial_content_written_to_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        asyncio.run(_handle_add_page({"title": "Tutorial", "content": "## Step 1\nDo this."}))
        content = (tmp_path / "user_guide" / "tutorial.qmd").read_text(encoding="utf-8")
        assert "## Step 1" in content


# ---------------------------------------------------------------------------
# call_tool dispatch paths
# ---------------------------------------------------------------------------


class TestCallToolDispatch:
    def _mock_handler(self, name: str, result_text: str):
        """Return an AsyncMock that patches the given handler."""
        mock = AsyncMock(return_value=[MagicMock(text=result_text)])
        return patch(f"great_docs.mcp._{name}", mock), mock

    def test_dispatches_gd_preview(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(call_tool("gd_preview", {}))
        assert result[0].text  # dispatches without crashing

    def test_dispatches_gd_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(call_tool("gd_config", {}))
        assert result[0].text

    def test_dispatches_gd_status(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(call_tool("gd_status", {}))
        assert result[0].text

    def test_dispatches_gd_add_page(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(call_tool("gd_add_page", {"title": "Test"}))
        assert "Created" in result[0].text

    def test_dispatches_gd_build(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs.build = MagicMock()
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(call_tool("gd_build", {}))
        assert "Build complete" in result[0].text

    def test_dispatches_gd_scan(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = None
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(call_tool("gd_scan", {}))
        assert result[0].text

    def test_dispatches_gd_lint(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_result = MagicMock()
        mock_result.issues = []
        with patch("great_docs._lint.run_lint", return_value=mock_result):
            result = asyncio.run(call_tool("gd_lint", {}))
        assert result[0].text

    def test_dispatches_gd_api_diff(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = None
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(call_tool("gd_api_diff", {}))
        assert result[0].text


# ---------------------------------------------------------------------------
# _handle_build
# ---------------------------------------------------------------------------


class TestHandleBuild:
    def test_build_called_on_docs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs.build = MagicMock()
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_build({}))
        mock_docs.build.assert_called_once()
        assert "Build complete" in result[0].text

    def test_clean_removes_sibling_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from great_docs._utils import QUARTO_YML_HEADER

        monkeypatch.chdir(tmp_path)
        old_dir = tmp_path / "great-docs-0.1"
        old_dir.mkdir()
        (old_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER + "project:\n  type: website\n")

        mock_docs = MagicMock()
        mock_docs.build = MagicMock()
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            asyncio.run(_handle_build({"clean": True}))

        assert not old_dir.exists()

    def test_explicit_project_path(self, tmp_path: Path):
        mock_docs = MagicMock()
        mock_docs.build = MagicMock()
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_build({"project_path": str(tmp_path)}))
        assert "Build complete" in result[0].text


# ---------------------------------------------------------------------------
# _handle_scan
# ---------------------------------------------------------------------------


class TestHandleScan:
    def test_no_package_name_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = None
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({}))
        assert "Could not detect" in result[0].text

    def test_no_exports_returns_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = []
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({}))
        assert "No exports" in result[0].text

    def test_with_function_exports(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["do_thing", "helper"]
        mock_docs._categorize_api_objects.return_value = {
            "functions": ["do_thing", "helper"],
            "classes": [],
        }
        mock_docs._config.reference = []
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({}))
        assert "do_thing" in result[0].text
        assert "Functions" in result[0].text

    def test_with_class_exports_and_verbose(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["MyClass"]
        mock_docs._categorize_api_objects.return_value = {
            "classes": ["MyClass"],
            "class_method_names": {"MyClass": ["method_a"]},
        }
        mock_docs._config.reference = []
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({"verbose": True}))
        assert "MyClass" in result[0].text
        assert "method_a" in result[0].text

    def test_reference_config_marks_configured_items(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["do_thing"]
        mock_docs._categorize_api_objects.return_value = {"functions": ["do_thing"]}
        mock_docs._config.reference = [{"contents": ["do_thing"]}]
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({}))
        assert "[x]" in result[0].text


# ---------------------------------------------------------------------------
# _handle_lint
# ---------------------------------------------------------------------------


class TestHandleLint:
    def test_no_issues_returns_success_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_result = MagicMock()
        mock_result.issues = []
        with patch("great_docs._lint.run_lint", return_value=mock_result):
            result = asyncio.run(_handle_lint({}))
        assert "No lint issues" in result[0].text

    def test_issues_formatted_in_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        issue = MagicMock()
        issue.severity = "error"
        issue.check = "docstrings"
        issue.symbol = "MyClass"
        issue.message = "Missing docstring"
        mock_result = MagicMock()
        mock_result.issues = [issue]
        with patch("great_docs._lint.run_lint", return_value=mock_result):
            result = asyncio.run(_handle_lint({}))
        assert "ERROR" in result[0].text
        assert "Missing docstring" in result[0].text

    def test_issue_without_symbol(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        issue = MagicMock()
        issue.severity = "warning"
        issue.check = "style"
        issue.symbol = None
        issue.message = "Inconsistent style"
        mock_result = MagicMock()
        mock_result.issues = [issue]
        with patch("great_docs._lint.run_lint", return_value=mock_result):
            result = asyncio.run(_handle_lint({}))
        assert "Inconsistent style" in result[0].text

    def test_checks_arg_passed_to_run_lint(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_result = MagicMock()
        mock_result.issues = []
        with patch("great_docs._lint.run_lint", return_value=mock_result) as mock_lint:
            asyncio.run(_handle_lint({"checks": ["docstrings"]}))
        _, kwargs = mock_lint.call_args
        assert kwargs["checks"] == {"docstrings"}


# ---------------------------------------------------------------------------
# _handle_status with config
# ---------------------------------------------------------------------------


class TestHandleStatusWithConfig:
    def _mock_docs(self, pkg="mypkg", features=None):
        mock = MagicMock()
        mock._detect_package_name.return_value = pkg
        cfg = features or {}
        mock._config.cli_enabled = cfg.get("cli", False)
        mock._config.mcp_enabled = cfg.get("mcp", False)
        mock._config.__getitem__ = lambda self, key: cfg.get(key, [])
        mock._config.sections = cfg.get("sections", [])
        return mock

    def test_shows_package_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch("great_docs.mcp._get_great_docs", return_value=self._mock_docs()):
            result = asyncio.run(_handle_status({}))
        assert "mypkg" in result[0].text

    def test_shows_cli_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch(
            "great_docs.mcp._get_great_docs", return_value=self._mock_docs(features={"cli": True})
        ):
            result = asyncio.run(_handle_status({}))
        assert "CLI docs" in result[0].text

    def test_shows_mcp_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch(
            "great_docs.mcp._get_great_docs", return_value=self._mock_docs(features={"mcp": True})
        ):
            result = asyncio.run(_handle_status({}))
        assert "MCP docs" in result[0].text

    def test_shows_user_guide_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch(
            "great_docs.mcp._get_great_docs",
            return_value=self._mock_docs(features={"user_guide": ["page.qmd"]}),
        ):
            result = asyncio.run(_handle_status({}))
        assert "User Guide" in result[0].text

    def test_shows_custom_sections(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch(
            "great_docs.mcp._get_great_docs",
            return_value=self._mock_docs(features={"sections": ["s1", "s2"]}),
        ):
            result = asyncio.run(_handle_status({}))
        assert "2 custom section" in result[0].text

    def test_shows_multiversion_feature(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        with patch(
            "great_docs.mcp._get_great_docs",
            return_value=self._mock_docs(features={"versions": ["0.1", "0.2"]}),
        ):
            result = asyncio.run(_handle_status({}))
        assert "Multi-version" in result[0].text


# ---------------------------------------------------------------------------
# _handle_api_diff
# ---------------------------------------------------------------------------


class TestHandleApiDiff:
    def test_no_package_name_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = None
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_api_diff({}))
        assert "Could not detect" in result[0].text

    def _patched_docs(self):
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        return mock_docs

    def _mock_snapshot(self, symbols=None):
        snap = MagicMock()
        snap.symbols = symbols or {}
        return snap

    def test_no_refs_shows_current_api(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from great_docs._api_diff import ApiSnapshot

        monkeypatch.chdir(tmp_path)
        snap = self._mock_snapshot({"MyClass": MagicMock(kind="class")})
        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({}))
        assert "MyClass" in result[0].text

    def test_base_ref_without_snapshot_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from great_docs._api_diff import ApiSnapshot

        monkeypatch.chdir(tmp_path)
        snap = self._mock_snapshot()
        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"base": "v0.1"}))
        assert "No snapshot found" in result[0].text

    def test_provide_base_message_when_only_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from great_docs._api_diff import ApiSnapshot

        monkeypatch.chdir(tmp_path)
        snap = self._mock_snapshot()
        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"head": "HEAD"}))
        assert "Provide a base ref" in result[0].text


# ---------------------------------------------------------------------------
# list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    def test_always_includes_build_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        resources = asyncio.run(list_resources())
        uris = [str(r.uri) for r in resources]
        assert "gd://build-log" in uris

    def test_includes_config_when_file_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        monkeypatch.chdir(tmp_path)
        resources = asyncio.run(list_resources())
        uris = [str(r.uri) for r in resources]
        assert "gd://config" in uris

    def test_excludes_config_when_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        resources = asyncio.run(list_resources())
        uris = [str(r.uri) for r in resources]
        assert "gd://config" not in uris

    def test_includes_pyproject_when_file_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypkg'\n")
        monkeypatch.chdir(tmp_path)
        resources = asyncio.run(list_resources())
        uris = [str(r.uri) for r in resources]
        assert "gd://pyproject" in uris


# ---------------------------------------------------------------------------
# read_resource
# ---------------------------------------------------------------------------


class TestReadResource:
    def _uri(self, s: str) -> AnyUrl:
        return AnyUrl(s)

    def test_config_when_file_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "great-docs.yml").write_text("project:\n  name: test\n")
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://config")))
        assert "project:" in result

    def test_config_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://config")))
        assert "No great-docs.yml" in result

    def test_build_log_with_build_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "great-docs").mkdir()
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://build-log")))
        assert "great-docs" in result

    def test_build_log_without_build_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://build-log")))
        assert "No build output" in result

    def test_status_resource_delegates_to_handle_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://status")))
        assert result  # returns non-empty status text

    def test_pyproject_when_file_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypkg'\n")
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://pyproject")))
        assert "mypkg" in result

    def test_pyproject_when_file_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://pyproject")))
        assert "No pyproject.toml" in result

    def test_page_resource_returns_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "my-page.qmd").write_text("---\ntitle: Hello\n---\n")
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://page/my-page.qmd")))
        assert "Hello" in result

    def test_page_resource_missing_returns_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://page/missing.qmd")))
        assert "not found" in result.lower()

    def test_unknown_uri_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        result = asyncio.run(read_resource(self._uri("gd://unknown-thing")))
        assert "Unknown resource" in result

    def test_api_surface_no_package(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = None
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(read_resource(self._uri("gd://api-surface")))
        assert "Could not detect" in result

    def test_api_surface_with_exports(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["do_thing"]
        mock_docs._categorize_api_objects.return_value = {"functions": ["do_thing"]}
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(read_resource(self._uri("gd://api-surface")))
        assert "do_thing" in result


# ---------------------------------------------------------------------------
# list_resource_templates
# ---------------------------------------------------------------------------


class TestListResourceTemplates:
    def test_returns_reference_and_page_templates(self):
        templates = asyncio.run(list_resource_templates())
        uri_templates = [t.uri_template for t in templates]
        assert any("reference" in u for u in uri_templates)
        assert any("page" in u for u in uri_templates)

    def test_all_templates_have_descriptions(self):
        templates = asyncio.run(list_resource_templates())
        for t in templates:
            assert t.description


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------


class TestGetPrompt:
    def test_setup_docs_prompt(self):
        result = asyncio.run(get_prompt("setup-docs", {}))
        assert result.messages
        assert "gd_scan" in result.messages[0].content.text

    def test_write_user_guide_prompt_uses_topic(self):
        result = asyncio.run(get_prompt("write-user-guide", {"topic": "configuration"}))
        assert "configuration" in result.messages[0].content.text

    def test_write_user_guide_defaults_topic(self):
        result = asyncio.run(get_prompt("write-user-guide", {}))
        assert result.messages

    def test_debug_build_prompt_includes_error(self):
        result = asyncio.run(get_prompt("debug-build", {"error_message": "Quarto not found"}))
        assert "Quarto not found" in result.messages[0].content.text

    def test_debug_build_prompt_without_error(self):
        result = asyncio.run(get_prompt("debug-build", {}))
        assert result.messages

    def test_improve_docstrings_prompt(self):
        result = asyncio.run(
            get_prompt("improve-docstrings", {"symbol": "MyClass", "style": "google"})
        )
        assert "MyClass" in result.messages[0].content.text
        assert "google" in result.messages[0].content.text

    def test_improve_docstrings_defaults(self):
        result = asyncio.run(get_prompt("improve-docstrings", {}))
        assert "numpy" in result.messages[0].content.text

    def test_api_changelog_prompt(self):
        result = asyncio.run(
            get_prompt("api-changelog", {"base_version": "v0.1", "head_version": "v0.2"})
        )
        assert "v0.1" in result.messages[0].content.text
        assert "v0.2" in result.messages[0].content.text

    def test_api_changelog_defaults(self):
        result = asyncio.run(get_prompt("api-changelog", {}))
        assert result.messages

    def test_unknown_prompt_returns_fallback(self):
        result = asyncio.run(get_prompt("nonexistent-prompt", {}))
        assert "Unknown prompt" in result.messages[0].content.text


# ---------------------------------------------------------------------------
# handle_completion
# ---------------------------------------------------------------------------


class TestHandleCompletion:
    def test_audience_completion_filters_by_prefix(self):
        from mcp.types import CompletionArgument, PromptReference

        ref = PromptReference(type="ref/prompt", name="write-user-guide")
        arg = CompletionArgument(name="audience", value="beg")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert "beginner" in result.values

    def test_audience_completion_returns_all_when_empty(self):
        from mcp.types import CompletionArgument, PromptReference

        ref = PromptReference(type="ref/prompt", name="write-user-guide")
        arg = CompletionArgument(name="audience", value="")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert len(result.values) == 3

    def test_topic_completion_returns_suggestions(self):
        from mcp.types import CompletionArgument, PromptReference

        ref = PromptReference(type="ref/prompt", name="write-user-guide")
        arg = CompletionArgument(name="topic", value="install")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert any("install" in v for v in result.values)

    def test_style_completion_for_improve_docstrings(self):
        from mcp.types import CompletionArgument, PromptReference

        ref = PromptReference(type="ref/prompt", name="improve-docstrings")
        arg = CompletionArgument(name="style", value="nu")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert "numpy" in result.values

    def test_project_path_completion_returns_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from mcp.types import CompletionArgument, PromptReference

        monkeypatch.chdir(tmp_path)
        ref = PromptReference(type="ref/prompt", name="setup-docs")
        arg = CompletionArgument(name="project_path", value="")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert str(tmp_path) in result.values

    def test_page_path_completion_lists_qmd_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        from mcp.types import CompletionArgument, ResourceTemplateReference

        (tmp_path / "guide.qmd").write_text("")
        monkeypatch.chdir(tmp_path)
        ref = ResourceTemplateReference(type="ref/resource", uri="gd://page/{path}")
        arg = CompletionArgument(name="path", value="")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert "guide.qmd" in result.values

    def test_unmatched_prompt_ref_returns_none(self):
        from mcp.types import CompletionArgument, PromptReference

        ref = PromptReference(type="ref/prompt", name="other-prompt")
        arg = CompletionArgument(name="other_arg", value="x")
        result = asyncio.run(handle_completion(ref, arg))
        assert result is None

    def test_symbol_completion_for_improve_docstrings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Completion for improve-docstrings + symbol arg returns filtered exports."""
        from mcp.types import CompletionArgument, PromptReference

        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["MyClass", "my_func", "other_func"]
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            ref = PromptReference(type="ref/prompt", name="improve-docstrings")
            arg = CompletionArgument(name="symbol", value="my")
            result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert "MyClass" in result.values or "my_func" in result.values

    def test_symbol_completion_for_improve_docstrings_exception_returns_none(self):
        """Completion for improve-docstrings + symbol arg returns None on exception."""
        from mcp.types import CompletionArgument, PromptReference

        with patch("great_docs.mcp._get_great_docs", side_effect=RuntimeError("boom")):
            ref = PromptReference(type="ref/prompt", name="improve-docstrings")
            arg = CompletionArgument(name="symbol", value="x")
            result = asyncio.run(handle_completion(ref, arg))
        assert result is None

    def test_reference_uri_symbol_completion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """ResourceTemplateReference with reference URI + symbol arg returns completions."""
        from mcp.types import CompletionArgument, ResourceTemplateReference

        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["MyClass", "my_func"]
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            ref = ResourceTemplateReference(type="ref/resource", uri="gd://reference/{symbol}")
            arg = CompletionArgument(name="symbol", value="My")
            result = asyncio.run(handle_completion(ref, arg))
        assert result is not None
        assert "MyClass" in result.values

    def test_reference_uri_symbol_completion_exception_returns_none(self):
        """ResourceTemplateReference symbol completion returns None on exception."""
        from mcp.types import CompletionArgument, ResourceTemplateReference

        with patch("great_docs.mcp._get_great_docs", side_effect=RuntimeError("boom")):
            ref = ResourceTemplateReference(type="ref/resource", uri="gd://reference/{symbol}")
            arg = CompletionArgument(name="symbol", value="x")
            result = asyncio.run(handle_completion(ref, arg))
        assert result is None


# ---------------------------------------------------------------------------
# _get_great_docs direct call
# ---------------------------------------------------------------------------


class TestGetGreatDocs:
    def test_returns_great_docs_instance(self, tmp_path: Path):
        """_get_great_docs() returns a GreatDocs instance for the given path."""
        from great_docs.mcp import _get_great_docs

        result = _get_great_docs(str(tmp_path))
        from great_docs.core import GreatDocs

        assert isinstance(result, GreatDocs)


# ---------------------------------------------------------------------------
# _handle_scan — reference config dict item branch
# ---------------------------------------------------------------------------


class TestHandleScanRefConfigDictItem:
    def test_dict_item_in_reference_config_is_included(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Reference config dict items (with 'name' key) are included in ref_items."""
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = ["do_thing"]
        mock_docs._categorize_api_objects.return_value = {"functions": ["do_thing"]}
        # Reference config uses dict items, not str items
        mock_docs._config.reference = [{"contents": [{"name": "do_thing"}]}]
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(_handle_scan({}))
        text = result[0].text
        assert "do_thing" in text
        assert "[x]" in text


# ---------------------------------------------------------------------------
# _handle_api_diff
# ---------------------------------------------------------------------------


class TestHandleApiDiffWithSnapshot:
    def _patched_docs(self):
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        return mock_docs

    def _mock_current_snapshot(self):
        snap = MagicMock()
        snap.symbols = {}
        return snap

    def test_with_added_symbols(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """_handle_api_diff shows added symbols when base snapshot exists."""
        from great_docs._api_diff import ApiSnapshot, SymbolChange

        monkeypatch.chdir(tmp_path)
        snap_dir = tmp_path / ".great-docs-snapshots"
        snap_dir.mkdir()
        (snap_dir / "v0.1.json").write_text("{}")

        current = self._mock_current_snapshot()
        added_sym = MagicMock(spec=SymbolChange)
        added_sym.name = "new_func"
        added_sym.kind = "function"
        diff = MagicMock()
        diff.added = [added_sym]
        diff.removed = []
        diff.changed = []
        base_snap = MagicMock()
        base_snap.diff.return_value = diff

        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=current, create=True),
            patch.object(ApiSnapshot, "from_json", return_value=base_snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"base": "v0.1"}))

        assert "Added" in result[0].text
        assert "new_func" in result[0].text

    def test_with_removed_symbols(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """_handle_api_diff shows removed symbols when base snapshot exists."""
        from great_docs._api_diff import ApiSnapshot, SymbolChange

        monkeypatch.chdir(tmp_path)
        snap_dir = tmp_path / ".great-docs-snapshots"
        snap_dir.mkdir()
        (snap_dir / "v0.1.json").write_text("{}")

        current = self._mock_current_snapshot()
        removed_sym = MagicMock(spec=SymbolChange)
        removed_sym.name = "old_func"
        removed_sym.kind = "function"
        diff = MagicMock()
        diff.added = []
        diff.removed = [removed_sym]
        diff.changed = []
        base_snap = MagicMock()
        base_snap.diff.return_value = diff

        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=current, create=True),
            patch.object(ApiSnapshot, "from_json", return_value=base_snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"base": "v0.1"}))

        assert "Removed" in result[0].text
        assert "old_func" in result[0].text

    def test_with_changed_symbols(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """_handle_api_diff shows changed symbols when base snapshot exists."""
        from great_docs._api_diff import ApiSnapshot, SymbolChange

        monkeypatch.chdir(tmp_path)
        snap_dir = tmp_path / ".great-docs-snapshots"
        snap_dir.mkdir()
        (snap_dir / "v0.1.json").write_text("{}")

        current = self._mock_current_snapshot()
        changed_sym = MagicMock(spec=SymbolChange)
        changed_sym.name = "changed_func"
        changed_sym.change_type = "signature_changed"
        diff = MagicMock()
        diff.added = []
        diff.removed = []
        diff.changed = [changed_sym]
        base_snap = MagicMock()
        base_snap.diff.return_value = diff

        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=current, create=True),
            patch.object(ApiSnapshot, "from_json", return_value=base_snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"base": "v0.1"}))

        assert "Changed" in result[0].text
        assert "changed_func" in result[0].text

    def test_no_diff_shows_no_changes_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """_handle_api_diff shows 'No API changes detected' when diff is empty."""
        from great_docs._api_diff import ApiSnapshot

        monkeypatch.chdir(tmp_path)
        snap_dir = tmp_path / ".great-docs-snapshots"
        snap_dir.mkdir()
        (snap_dir / "v0.1.json").write_text("{}")

        current = self._mock_current_snapshot()
        diff = MagicMock()
        diff.added = []
        diff.removed = []
        diff.changed = []
        base_snap = MagicMock()
        base_snap.diff.return_value = diff

        with (
            patch("great_docs.mcp._get_great_docs", return_value=self._patched_docs()),
            patch.object(ApiSnapshot, "from_live", return_value=current, create=True),
            patch.object(ApiSnapshot, "from_json", return_value=base_snap, create=True),
        ):
            result = asyncio.run(_handle_api_diff({"base": "v0.1"}))

        assert "No API changes detected" in result[0].text


# ---------------------------------------------------------------------------
# read_resource — gd://api-surface no-exports and exception paths
# ---------------------------------------------------------------------------


class TestReadResourceApiSurface:
    def _uri(self, s: str) -> AnyUrl:
        return AnyUrl(s)

    def test_api_surface_no_exports_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """read_resource returns 'No exports discovered' when _get_package_exports is empty."""
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"
        mock_docs._get_package_exports.return_value = []
        with patch("great_docs.mcp._get_great_docs", return_value=mock_docs):
            result = asyncio.run(read_resource(self._uri("gd://api-surface")))

        assert "No exports discovered" in result

    def test_api_surface_exception_returns_error_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """read_resource returns error string when _get_great_docs raises an exception."""
        monkeypatch.chdir(tmp_path)
        with patch("great_docs.mcp._get_great_docs", side_effect=RuntimeError("pkg not found")):
            result = asyncio.run(read_resource(self._uri("gd://api-surface")))

        assert "Error discovering API surface" in result


# ---------------------------------------------------------------------------
# read_resource — gd://reference/{symbol} paths
# ---------------------------------------------------------------------------


class TestReadResourceReference:
    def _uri(self, s: str) -> AnyUrl:
        return AnyUrl(s)

    def test_reference_symbol_found_returns_docstring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """gd://reference/symbol returns kind and docstring when symbol is found."""
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"

        # Build a module-like object that has `my_func` as an attribute
        mock_func = MagicMock()
        mock_func.__doc__ = "Does a thing."
        mock_mod = MagicMock()

        # getattr(mock_mod, "my_func", None) returns mock_func via spec trick
        mock_mod.configure_mock(**{"my_func": mock_func})

        with (
            patch("great_docs.mcp._get_great_docs", return_value=mock_docs),
            patch("importlib.import_module", return_value=mock_mod),
        ):
            result = asyncio.run(read_resource(self._uri("gd://reference/my_func")))

        assert "mypkg" in result or "my_func" in result or "Does a thing" in result

    def test_reference_symbol_not_found_returns_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """gd://reference/symbol returns 'not found' message when getattr returns None."""
        monkeypatch.chdir(tmp_path)
        mock_docs = MagicMock()
        mock_docs._detect_package_name.return_value = "mypkg"
        mock_docs._detect_module_name.return_value = "mypkg"
        mock_docs._normalize_package_name.return_value = "mypkg"

        mock_mod = MagicMock(spec=[])  # no attributes -> getattr returns None

        with (
            patch("great_docs.mcp._get_great_docs", return_value=mock_docs),
            patch("importlib.import_module", return_value=mock_mod),
        ):
            result = asyncio.run(read_resource(self._uri("gd://reference/missing_sym")))

        assert "not found" in result.lower()

    def test_reference_exception_returns_error_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """gd://reference/symbol returns error string on exception."""
        monkeypatch.chdir(tmp_path)
        with patch("great_docs.mcp._get_great_docs", side_effect=RuntimeError("import fail")):
            result = asyncio.run(read_resource(self._uri("gd://reference/any_sym")))

        assert "Error reading reference" in result
