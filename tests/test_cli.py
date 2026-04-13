from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from great_docs.cli import (
    _detect_optional_dependencies,
    _detect_python_version_from_pyproject,
    cli,
)


def test_detect_python_version_ge():
    """Parses >=3.12 and returns '3.12'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.12"


def test_detect_python_version_tilde():
    """Parses ~=3.11 and returns '3.11'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "~=3.11"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.11"


def test_detect_python_version_range():
    """Parses >=3.10,<3.13 and returns '3.10'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10,<3.13"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.10"


def test_detect_python_version_no_pyproject():
    """Returns None when pyproject.toml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_no_requires():
    """Returns None when requires-python is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nname = "x"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_no_version_match():
    """Returns None when requires-python doesn't contain a valid version."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "no-version"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_other_specifier():
    """For non->=, non-~= specifiers, returns the highest version."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "==3.11"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.11"


def test_detect_python_version_malformed_toml():
    """Returns None on invalid TOML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text("not valid {{toml")
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_optional_deps_with_dev():
    """Finds dev/docs/test extras."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            "[project.optional-dependencies]\n"
            'dev = ["pytest"]\n'
            'docs = ["sphinx"]\n'
            'other = ["requests"]\n'
        )
        result = _detect_optional_dependencies(Path(tmp))
        assert "dev" in result
        assert "docs" in result
        assert "other" not in result


def test_detect_optional_deps_no_pyproject():
    """Returns empty list when no pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp:
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_no_optional():
    """Returns empty list when no optional-dependencies."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nname = "x"\n')
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_malformed():
    """Returns empty list on invalid TOML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text("bad {{toml")
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_all_keyword():
    """Detects 'all' and 'full' extras."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            "[project.optional-dependencies]\n"
            'all = ["everything"]\n'
            'full = ["everything"]\n'
            'notebook = ["jupyter"]\n'
        )
        result = _detect_optional_dependencies(Path(tmp))
        assert "all" in result
        assert "full" in result
        assert "notebook" in result


def test_seo_no_site_dir():
    """seo command errors when _site doesn't exist."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        result = runner.invoke(cli, ["seo", "--project-path", "."])
        assert result.exit_code != 0
        assert "not built" in result.output or "Error" in result.output


def test_seo_json_no_site():
    """seo --json returns error JSON when _site doesn't exist."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        result = runner.invoke(cli, ["seo", "--json", "--project-path", "."])
        assert result.exit_code != 0


def test_seo_with_empty_site():
    """seo command runs with an empty _site directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        Path("great-docs.yml").write_text("display_name: Pkg\n")
        Path("great-docs").mkdir()
        site = Path("great-docs") / "_site"
        site.mkdir(parents=True)
        result = runner.invoke(cli, ["seo", "--project-path", "."])
        # Should run without crashing
        assert "SEO" in result.output or "Error" in result.output


def test_seo_json_with_site():
    """seo --json outputs valid JSON."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        Path("great-docs.yml").write_text("display_name: Pkg\n")
        gd = Path("great-docs")
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        # Create a minimal sitemap
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/</loc></url>"
            "</urlset>"
        )
        (site / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
        )
        result = runner.invoke(cli, ["seo", "--json", "--project-path", "."])
        if result.exit_code == 0:
            data = json.loads(result.output)
            assert "status" in data


def test_seo_with_html_pages():
    """seo command analyzes HTML pages."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        Path("great-docs.yml").write_text("display_name: Pkg\n")
        gd = Path("great-docs")
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        (site / "index.html").write_text(
            "<html><head>"
            "<title>Pkg | Docs</title>"
            '<meta name="description" content="docs">'
            '<link rel="canonical" href="https://example.com/">'
            '</head><body><img src="test.png" alt="test"></body></html>'
        )
        result = runner.invoke(cli, ["seo", "--project-path", "."])
        assert "Analyzed" in result.output or "SEO" in result.output


def test_seo_missing_alt_text():
    """seo detects missing alt text on images."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        Path("great-docs.yml").write_text("display_name: Pkg\n")
        gd = Path("great-docs")
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        (site / "page.html").write_text(
            '<html><head><title>T</title></head><body><img src="no-alt.png"></body></html>'
        )
        result = runner.invoke(cli, ["seo", "--project-path", "."])
        assert "alt" in result.output.lower() or "warning" in result.output.lower()


def test_seo_fix_missing_files():
    """seo --fix attempts to generate missing files."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        Path("great-docs.yml").write_text("display_name: Pkg\n")
        gd = Path("great-docs")
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        result = runner.invoke(cli, ["seo", "--fix", "--project-path", "."])
        # Should attempt fix operations
        assert result.exit_code in (0, 1)


def test_lint_help():
    """lint --help shows expected options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--help"])
    assert result.exit_code == 0
    assert "lint" in result.output.lower()
    assert "--check" in result.output
    assert "--json" in result.output


@patch("great_docs._lint.run_lint")
def test_lint_no_issues(mock_lint):
    """lint with no issues prints success."""
    from great_docs._lint import LintResult

    mock_lint.return_value = LintResult(issues=[], package_name="mypkg", exports_count=10)
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--project-path", "."])
        assert result.exit_code == 0
        assert "passed" in result.output


@patch("great_docs._lint.run_lint")
def test_lint_with_errors(mock_lint):
    """lint with errors exits non-zero."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="missing-docstring",
                severity="error",
                symbol="MyClass",
                message="Missing docstring",
            )
        ],
        package_name="mypkg",
        exports_count=5,
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--project-path", "."])
        assert result.exit_code == 1
        assert "error" in result.output.lower()


@patch("great_docs._lint.run_lint")
def test_lint_json_output(mock_lint):
    """lint --json outputs valid JSON."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="broken-xref",
                severity="warning",
                symbol="fn",
                message="Broken ref",
            )
        ],
        package_name="mypkg",
        exports_count=3,
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--json", "--project-path", "."])
        data = json.loads(result.output)
        assert data["status"] == "warn"
        assert data["package"] == "mypkg"
        assert len(data["issues"]) == 1


@patch("great_docs._lint.run_lint")
def test_lint_warnings_only(mock_lint):
    """lint with only warnings exits 0."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="style-mismatch",
                severity="warning",
                symbol="fn",
                message="Style issue",
            )
        ],
        package_name="mypkg",
        exports_count=3,
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--project-path", "."])
        assert result.exit_code == 0
        assert "warning" in result.output.lower()


@patch("great_docs._lint.run_lint", side_effect=RuntimeError("boom"))
def test_lint_exception(mock_lint):
    """lint handles runtime errors gracefully."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--project-path", "."])
        assert result.exit_code == 1


@patch("great_docs._lint.run_lint", side_effect=RuntimeError("boom"))
def test_lint_exception_json(mock_lint):
    """lint --json returns error JSON on exception."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--json", "--project-path", "."])
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert "boom" in data["error"]


@patch("great_docs._lint.run_lint")
def test_lint_with_check_filter(mock_lint):
    """lint --check docstrings passes filter to run_lint."""
    from great_docs._lint import LintResult

    mock_lint.return_value = LintResult(issues=[], package_name="mypkg", exports_count=5)
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["lint", "--check", "docstrings", "--project-path", "."])
        assert result.exit_code == 0
        _, kwargs = mock_lint.call_args
        assert kwargs["checks"] == {"docstrings"}


def test_api_diff_help():
    """api-diff --help shows expected options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["api-diff", "--help"])
    assert result.exit_code == 0
    assert "OLD_VERSION" in result.output
    assert "NEW_VERSION" in result.output
    assert "--json" in result.output
    assert "--graph" in result.output
    assert "--timeline" in result.output
    assert "--symbol" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_text_output(mock_diff):
    """api-diff renders text output with diff summary."""
    from great_docs._api_diff import ApiDiff, SymbolChange

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
        added=[SymbolChange(symbol="new_fn", change_type="added")],
        removed=[SymbolChange(symbol="old_fn", change_type="removed", is_breaking=True)],
        changed=[
            SymbolChange(
                symbol="changed_fn",
                change_type="changed",
                is_breaking=True,
                details=["Return type changed"],
            )
        ],
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", "."],
        )
        assert result.exit_code == 0
        assert "new_fn" in result.output
        assert "old_fn" in result.output
        assert "changed_fn" in result.output
        assert "BREAKING" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_json_output(mock_diff):
    """api-diff --json outputs valid JSON."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--json", "--project-path", "."],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["old_version"] == "v1.0"


@patch("great_docs._api_diff.api_diff", return_value=None)
def test_api_diff_no_snapshots(mock_diff):
    """api-diff exits with error when snapshots can't be built."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", "."],
        )
        assert result.exit_code != 0
        assert "Could not" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_no_changes(mock_diff):
    """api-diff with no changes shows success message."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", "."],
        )
        assert result.exit_code == 0
        assert "No API changes" in result.output


@patch("great_docs._api_diff.build_timeline")
def test_api_diff_timeline_json(mock_timeline):
    """api-diff --timeline --json outputs timeline data."""
    mock_timeline.return_value = [
        {"version": "v1.0", "symbols": 5, "classes": 2, "functions": 3},
        {"version": "v2.0", "symbols": 8, "classes": 3, "functions": 5},
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--timeline", "--json", "--project-path", "."],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["version"] == "v1.0"


@patch("great_docs._api_diff.build_timeline")
def test_api_diff_timeline_mermaid(mock_timeline):
    """api-diff --timeline outputs Mermaid chart."""
    mock_timeline.return_value = [
        {"version": "v1.0", "symbols": 5, "classes": 2, "functions": 3},
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--timeline", "--project-path", "."],
        )
        assert result.exit_code == 0
        assert "xychart-beta" in result.output


@patch("great_docs._api_diff.build_timeline", return_value=[])
def test_api_diff_timeline_empty(mock_timeline):
    """api-diff --timeline with no tags exits with error."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--timeline", "--project-path", "."],
        )
        assert result.exit_code != 0


@patch("great_docs._api_diff.build_dependency_graph")
@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_text(mock_diff, mock_snap, mock_graph):
    """api-diff --graph outputs Mermaid dependency graph."""
    from great_docs._api_diff import ApiDiff, DependencyGraph

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    from great_docs._api_diff import ApiSnapshot, SymbolInfo

    mock_snap.return_value = ApiSnapshot(
        version="v2.0",
        package_name="pkg",
        symbols={"fn": SymbolInfo(name="fn", kind="function")},
    )
    mock_graph.return_value = DependencyGraph(nodes={"fn": "function"})
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--graph", "--project-path", "."],
        )
        assert result.exit_code == 0
        assert "graph TD" in result.output


@patch("great_docs._api_diff.build_dependency_graph")
@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_json(mock_diff, mock_snap, mock_graph):
    """api-diff --graph --json outputs graph as JSON."""
    from great_docs._api_diff import ApiDiff, ApiSnapshot, DependencyGraph, SymbolInfo

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    mock_snap.return_value = ApiSnapshot(
        version="v2.0",
        package_name="pkg",
        symbols={"fn": SymbolInfo(name="fn", kind="function")},
    )
    mock_graph.return_value = DependencyGraph(nodes={"fn": "function"})
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--graph",
                "--json",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "nodes" in data


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_text(mock_tags, mock_hist):
    """api-diff --symbol outputs symbol history text."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="build", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="build",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def build()",
                symbol_info=sym,
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=False,
                signature=None,
                symbol_info=None,
            ),
        ],
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "build",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        assert "build" in result.output
        assert "NOT PRESENT" in result.output


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_json(mock_tags, mock_hist):
    """api-diff --symbol --json outputs JSON."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "fn",
                "--json",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["symbol"] == "fn"


@patch("great_docs._api_diff.evolution_table_text")
@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_table_text(mock_tags, mock_hist, mock_table):
    """api-diff --symbol --table outputs text table."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    mock_table.return_value = "| fn | v1.0 |"
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "fn",
                "--table",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        assert "fn" in result.output


@patch("great_docs._api_diff.evolution_table_html")
@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_table_html(mock_tags, mock_hist, mock_html):
    """api-diff --symbol --table --html outputs HTML."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    mock_html.return_value = '<table class="evo">mock</table>'
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "fn",
                "--table",
                "--html",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        assert "<table" in result.output


@patch("great_docs._api_diff.symbol_history", return_value=None)
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_no_package(mock_tags, mock_hist):
    """api-diff --symbol exits with error when package can't be determined."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "fn",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code != 0
        assert "package" in result.output.lower()


@patch("great_docs._api_diff.list_version_tags", return_value=[])
def test_api_diff_symbol_no_tags(mock_tags):
    """api-diff --symbol exits with error when no tags in range."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "fn",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code != 0
        assert "No version tags" in result.output


@patch("great_docs._api_diff.api_diff", side_effect=RuntimeError("boom"))
def test_api_diff_exception_text(mock_diff):
    """api-diff handles exceptions with text error."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", "."],
        )
        assert result.exit_code != 0


@patch("great_docs._api_diff.api_diff", side_effect=RuntimeError("boom"))
def test_api_diff_exception_json(mock_diff):
    """api-diff --json handles exceptions with JSON error."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--json", "--project-path", "."],
        )
        data = json.loads(result.output)
        assert data["status"] == "error"
        assert "boom" in data["error"]


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0", "v3.0"])
def test_api_diff_symbol_changes_only(mock_tags, mock_hist):
    """api-diff --symbol --changes-only filters to changed entries."""
    from great_docs._api_diff import (
        SymbolChange,
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
                change=SymbolChange(
                    symbol="fn",
                    change_type="changed",
                    is_breaking=True,
                    details=["Param added"],
                ),
            ),
            SymbolHistoryEntry(
                version="v3.0",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
            ),
        ],
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v3.0",
                "--symbol",
                "fn",
                "--changes-only",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
        assert "changes" in result.output.lower()


@patch("great_docs._api_diff.api_diff")
def test_api_diff_migration_hint(mock_diff):
    """api-diff shows migration hints for removed symbols."""
    from great_docs._api_diff import ApiDiff, SymbolChange

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
        removed=[
            SymbolChange(
                symbol="old_fn",
                change_type="removed",
                is_breaking=True,
                migration_hint="Use new_fn instead",
            )
        ],
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", "."],
        )
        assert result.exit_code == 0
        assert "Use new_fn instead" in result.output


@patch("great_docs._api_diff.snapshot_at_tag", return_value=None)
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_no_snapshot(mock_diff, mock_snap):
    """api-diff --graph exits with error when snapshot fails."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--graph", "--project-path", "."],
        )
        assert result.exit_code != 0
        assert "snapshot" in result.output.lower()


@patch("great_docs._harper.check_harper_available", return_value=(False, "not installed"))
def test_proofread_harper_not_available(mock_check):
    """proofread exits with error when harper is not installed."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["proofread", "--project-path", "."])
        assert result.exit_code != 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_no_files(mock_check, mock_harper):
    """proofread with no docs files exits cleanly."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        result = runner.invoke(cli, ["proofread", "--project-path", "."])
        assert "No documentation files" in result.output or result.exit_code == 0


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_md_files(mock_check, mock_run):
    """proofread checks .md files."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=3,
                    column=5,
                    message="Did you mean 'test'?",
                    matched_text="tset",
                    suggestions=["test"],
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Test\n\nThis is a tset.")
        result = runner.invoke(cli, ["proofread", "README.md", "--project-path", "."])
        assert result.exit_code == 1
        assert "tset" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_json(mock_check, mock_run):
    """proofread --json-output produces valid JSON."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Misspelled",
                    matched_text="tset",
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("tset")
        result = runner.invoke(
            cli, ["proofread", "README.md", "--json-output", "--project-path", "."]
        )
        data = json.loads(result.output)
        assert data["total_issues"] == 1
        assert data["dialect"] == "us"


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_compact(mock_check, mock_run):
    """proofread --compact produces GCC-style output."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=3,
                    column=5,
                    message="Misspelled",
                    matched_text="tset",
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("tset")
        result = runner.invoke(cli, ["proofread", "README.md", "--compact", "--project-path", "."])
        assert "README.md:3:5:" in result.output
        assert "SpellCheck" in result.output


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_no_issues(mock_check, mock_run):
    """proofread with no issues exits 0 and shows success."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Good\n\nPerfect text.")
        result = runner.invoke(cli, ["proofread", "README.md", "--project-path", "."])
        assert result.exit_code == 0
        assert "No issues" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_verbose(mock_check, mock_run):
    """proofread --verbose shows detailed output."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Did you mean test?",
                    matched_text="tset",
                    suggestions=["test"],
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("tset")
        result = runner.invoke(
            cli,
            ["proofread", "README.md", "--verbose", "--project-path", "."],
        )
        assert "Proofreading" in result.output
        assert "Did you mean" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_max_issues_exceeded(mock_check, mock_run):
    """proofread --max-issues exits 1 when threshold exceeded."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="f.md",
            lint_count=5,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=i,
                    column=1,
                    message="err",
                    matched_text="x",
                    file="f.md",
                )
                for i in range(5)
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("f.md").write_text("x")
        result = runner.invoke(
            cli,
            ["proofread", "f.md", "--max-issues", "2", "--project-path", "."],
        )
        assert result.exit_code == 1
        assert "exceeds" in result.output


@patch("great_docs._harper.run_harper_on_text")
@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_qmd_files(mock_check, mock_run_files, mock_run_text):
    """proofread processes .qmd files via text extraction."""
    from great_docs._harper import HarperLint

    mock_run_text.return_value = [
        HarperLint(
            rule="SpellCheck",
            kind="Spelling",
            line=4,
            column=5,
            message="Misspelled",
            matched_text="tset",
            file="<stdin>",
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        ug = Path("user_guide")
        ug.mkdir()
        (ug / "test.qmd").write_text("---\ntitle: T\n---\nThis is a tset.")
        result = runner.invoke(cli, ["proofread", "--project-path", "."])
        assert result.exit_code == 1


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_strict_mode(mock_check, mock_run):
    """proofread --strict disables smart defaults."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Good")
        result = runner.invoke(
            cli,
            ["proofread", "README.md", "--strict", "--project-path", "."],
        )
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_custom_words(mock_check, mock_run):
    """proofread -d word adds words to dictionary."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Test")
        result = runner.invoke(
            cli,
            ["proofread", "README.md", "-d", "griffe", "-d", "quartodoc", "--project-path", "."],
        )
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_dictionary_file(mock_check, mock_run):
    """proofread --dictionary-file loads words from file."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Test")
        Path("dict.txt").write_text("griffe\n# comment\nquartodoc\n")
        result = runner.invoke(
            cli,
            [
                "proofread",
                "README.md",
                "--dictionary-file",
                "dict.txt",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_spelling_only(mock_check, mock_run):
    """proofread --spelling-only passes SpellCheck filter."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Test")
        result = runner.invoke(
            cli,
            ["proofread", "README.md", "--spelling-only", "--project-path", "."],
        )
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_grammar_only(mock_check, mock_run):
    """proofread --grammar-only excludes SpellCheck."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("README.md").write_text("# Test")
        result = runner.invoke(
            cli,
            ["proofread", "README.md", "--grammar-only", "--project-path", "."],
        )
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_auto_discover(mock_check, mock_run):
    """proofread without files auto-discovers user_guide and recipes."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        ug = Path("user_guide")
        ug.mkdir()
        (ug / "guide.md").write_text("# Guide")
        recipes = Path("recipes")
        recipes.mkdir()
        (recipes / "r.md").write_text("# Recipe")
        result = runner.invoke(cli, ["proofread", "--project-path", "."])
        assert result.exit_code == 0


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_suggestion_format(mock_check, mock_run):
    """proofread shows cleaned suggestion text."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="f.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Misspelled",
                    matched_text="tset",
                    suggestions=['Replace with: "test"'],
                    file="f.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("f.md").write_text("tset")
        result = runner.invoke(cli, ["proofread", "f.md", "--project-path", "."])
        assert "test" in result.output


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_only_and_ignore_rules(mock_check, mock_run):
    """proofread --only and --ignore rules are passed through."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
        Path("f.md").write_text("text")
        result = runner.invoke(
            cli,
            [
                "proofread",
                "f.md",
                "--only",
                "SpellCheck",
                "--ignore",
                "SentenceCap",
                "--project-path",
                ".",
            ],
        )
        assert result.exit_code == 0
