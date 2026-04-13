# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path

from great_docs.config import Config
from great_docs.core import GreatDocs


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_config(tmp_path: Path, yaml_text: str) -> Config:
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    return Config(tmp_path)


def _make_qmd(
    path: Path,
    title: str,
    status: str | None = None,
    extra: str = "",
) -> None:
    """Write a minimal .qmd file with optional status in frontmatter."""
    fm_lines = [f'title: "{title}"']
    if status is not None:
        fm_lines.append(f"status: {status}")
    if extra:
        fm_lines.append(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(fm_lines) + "\n---\n\nSome content.\n",
        encoding="utf-8",
    )


def _bootstrap_project(tmp_path: Path, yaml_text: str = "") -> GreatDocs:
    """Create a minimal project with great-docs.yml and return a GreatDocs instance."""
    (tmp_path / "great-docs.yml").write_text(yaml_text or "page_status:\n  enabled: true\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text('"""Test package."""\n__all__ = []\n')
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir(exist_ok=True)
    return GreatDocs(project_path=tmp_path)


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestPageStatusConfig:
    def test_disabled_by_default(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.page_status_enabled is False

    def test_enabled_dict(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n")
        assert cfg.page_status_enabled is True

    def test_enabled_shorthand(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status: true\n")
        assert cfg.page_status_enabled is True

    def test_disabled_shorthand(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status: false\n")
        assert cfg.page_status_enabled is False

    def test_show_in_sidebar_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n")
        assert cfg.page_status_show_in_sidebar is True

    def test_show_in_sidebar_disabled(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n  show_in_sidebar: false\n")
        assert cfg.page_status_show_in_sidebar is False

    def test_show_on_pages_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n")
        assert cfg.page_status_show_on_pages is True

    def test_show_on_pages_disabled(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n  show_on_pages: false\n")
        assert cfg.page_status_show_on_pages is False

    def test_not_enabled_disables_subordinates(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.page_status_show_in_sidebar is False
        assert cfg.page_status_show_on_pages is False

    def test_default_definitions(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "page_status:\n  enabled: true\n")
        defs = cfg.page_status_definitions
        assert "new" in defs
        assert "deprecated" in defs
        assert "beta" in defs
        assert "updated" in defs
        assert "experimental" in defs
        assert defs["new"]["label"] == "New"
        assert defs["deprecated"]["icon"] == "triangle-alert"

    def test_shorthand_true_preserves_default_definitions(self, tmp_path: Path):
        """Regression: `page_status: true` must not replace definitions with bool."""
        cfg = _make_config(tmp_path, "page_status: true\n")
        defs = cfg.page_status_definitions
        assert isinstance(defs, dict)
        assert len(defs) >= 5
        assert "new" in defs
        assert "experimental" in defs
        assert defs["new"]["label"] == "New"

    def test_custom_definitions_merge(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "page_status:\n  enabled: true\n  statuses:\n"
            "    draft:\n      label: Draft\n      icon: pencil\n"
            "      color: '#999999'\n      description: Work in progress\n",
        )
        defs = cfg.page_status_definitions
        # Custom status is present
        assert "draft" in defs
        assert defs["draft"]["label"] == "Draft"
        # Built-in statuses are still there (deep merge from defaults)
        assert "new" in defs


# ── Core Status Collection Tests ─────────────────────────────────────────────


class TestCollectPageStatuses:
    def test_collect_from_user_guide(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "intro.qmd", "Introduction", status="new")
        _make_qmd(ug_dir / "advanced.qmd", "Advanced Usage", status="deprecated")

        result = gd._collect_page_statuses()

        assert result["user-guide/intro.qmd"] == "new"
        assert result["user-guide/advanced.qmd"] == "deprecated"

    def test_collect_from_recipes(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        recipes_dir = gd.project_path / "recipes"
        _make_qmd(recipes_dir / "recipe1.qmd", "Easy Recipe", status="beta")

        result = gd._collect_page_statuses()

        assert result["recipes/recipe1.qmd"] == "beta"

    def test_unknown_status_warns(self, tmp_path: Path, capsys):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "A Page", status="nonexistent")

        result = gd._collect_page_statuses()

        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Unknown page status 'nonexistent'" in captured.out

    def test_no_status_pages(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "No Status")

        result = gd._collect_page_statuses()
        assert len(result) == 0

    def test_no_qmd_files(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        result = gd._collect_page_statuses()
        assert len(result) == 0

    def test_case_insensitive_status(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "A Page", status="New")

        result = gd._collect_page_statuses()

        assert result["user-guide/page.qmd"] == "new"

    def test_custom_section_scanned(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "page_status:\n  enabled: true\nsections:\n  - title: Tutorials\n    dir: tutorials\n",
        )
        tut_dir = gd.project_path / "tutorials"
        _make_qmd(tut_dir / "first.qmd", "First Tutorial", status="new")

        result = gd._collect_page_statuses()

        assert result["tutorials/first.qmd"] == "new"


# ── JSON Generation Tests ───────────────────────────────────────────────────


class TestGenerateStatusJson:
    def test_generates_json_file(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        status_map = {"user-guide/intro.qmd": "new"}

        gd._generate_status_json(status_map)

        json_path = gd.project_path / "_page_status.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["page_statuses"] == {"user-guide/intro.qmd": "new"}
        assert "new" in data["definitions"]
        assert data["definitions"]["new"]["label"] == "New"
        assert data["show_in_sidebar"] is True
        assert data["show_on_pages"] is True

    def test_definitions_include_all_statuses(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        status_map = {"user-guide/intro.qmd": "new"}

        gd._generate_status_json(status_map)

        json_path = gd.project_path / "_page_status.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        # All built-in statuses should be in definitions
        for key in ("new", "updated", "beta", "deprecated", "experimental"):
            assert key in data["definitions"]


# ── Process Page Statuses Integration Tests ──────────────────────────────────


class TestProcessPageStatuses:
    def test_no_pages_returns_false(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        result = gd._process_page_statuses()
        assert result is False

    def test_with_pages_returns_true(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "intro.qmd", "Intro", status="new")

        result = gd._process_page_statuses()
        assert result is True

        # Verify JSON file was created
        json_path = gd.project_path / "_page_status.json"
        assert json_path.exists()


# ── Asset Correctness Tests ─────────────────────────────────────────────────


class TestStatusBadgeAssets:
    """Verify the SCSS and JS assets contain correct selectors and logic."""

    def test_scss_sidebar_flex_uses_compound_selector(self):
        """Regression: .sidebar-navigation is ON #quarto-sidebar, not inside it.

        #quarto-sidebar.sidebar-navigation (compound) must be used, NOT
        #quarto-sidebar .sidebar-navigation (descendant).
        """
        scss_path = Path(__file__).parent.parent / "great_docs" / "assets" / "great-docs.scss"
        content = scss_path.read_text(encoding="utf-8")
        assert "#quarto-sidebar.sidebar-navigation .sidebar-item .sidebar-link" in content
        assert "#quarto-sidebar .sidebar-navigation .sidebar-item .sidebar-link" not in content

    def test_js_uses_url_api_for_href_parsing(self):
        """Regression: browsers resolve getAttribute('href') to absolute URLs.

        The JS must use new URL() to extract the pathname for matching.
        """
        js_path = Path(__file__).parent.parent / "great_docs" / "assets" / "page-status-badges.js"
        content = js_path.read_text(encoding="utf-8")
        assert "new URL(href, window.location.href)" in content

    def test_js_progressive_subpath_matching(self):
        """Regression: subdirectory deployments add a prefix to the pathname.

        e.g. /great-docs/user-guide/foo.qmd must match key user-guide/foo.qmd.
        The JS must try progressively shorter subpaths.
        """
        js_path = Path(__file__).parent.parent / "great_docs" / "assets" / "page-status-badges.js"
        content = js_path.read_text(encoding="utf-8")
        assert "segments.slice(i).join" in content
