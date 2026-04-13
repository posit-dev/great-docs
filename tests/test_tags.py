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


def _make_qmd(path: Path, title: str, tags: list[str] | None = None, extra: str = "") -> None:
    """Write a minimal .qmd file with optional tags in frontmatter."""
    fm_lines = [f'title: "{title}"']
    if tags is not None:
        tag_list = ", ".join(f'"{t}"' for t in tags)
        fm_lines.append(f"tags: [{tag_list}]")
    if extra:
        fm_lines.append(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(fm_lines) + "\n---\n\nSome content.\n",
        encoding="utf-8",
    )


def _bootstrap_project(tmp_path: Path, yaml_text: str = "") -> GreatDocs:
    """Create a minimal project with great-docs.yml and return a GreatDocs instance."""
    (tmp_path / "great-docs.yml").write_text(yaml_text or "tags:\n  enabled: true\n")
    # Create a minimal pyproject.toml so GreatDocs can detect the project
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
    # Create a minimal package
    pkg_dir = tmp_path / "test_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text('"""Test package."""\n__all__ = []\n')
    # Create the build directory (normally done by _prepare_build_directory)
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir(exist_ok=True)
    return GreatDocs(project_path=tmp_path)


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestTagsConfig:
    def test_tags_disabled_by_default(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.tags_enabled is False

    def test_tags_enabled_true(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_enabled is True

    def test_tags_enabled_shorthand(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags: true\n")
        assert cfg.tags_enabled is True

    def test_tags_enabled_false_shorthand(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags: false\n")
        assert cfg.tags_enabled is False

    def test_tags_index_page_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_index_page is True

    def test_tags_index_page_disabled(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n  index_page: false\n")
        assert cfg.tags_index_page is False

    def test_tags_show_on_pages_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_show_on_pages is True

    def test_tags_hierarchical_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_hierarchical is True

    def test_tags_icons_empty(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_icons == {}

    def test_tags_icons_custom(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "tags:\n  enabled: true\n  icons:\n    Python: code\n    Tutorial: book-open\n",
        )
        assert cfg.tags_icons == {"Python": "code", "Tutorial": "book-open"}

    def test_tags_shadow_empty(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_shadow == []

    def test_tags_shadow_custom(self, tmp_path: Path):
        cfg = _make_config(
            tmp_path,
            "tags:\n  enabled: true\n  shadow:\n    - internal\n    - draft\n",
        )
        assert cfg.tags_shadow == ["internal", "draft"]

    def test_tags_scoped_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_scoped is False

    def test_tags_location_default(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_location == "top"

    def test_tags_location_bottom(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n  location: bottom\n")
        assert cfg.tags_location == "bottom"

    def test_tags_location_top_explicit(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n  location: top\n")
        assert cfg.tags_location == "top"

    def test_tags_location_invalid_falls_back_to_top(self, tmp_path: Path):
        cfg = _make_config(tmp_path, "tags:\n  enabled: true\n  location: middle\n")
        assert cfg.tags_location == "top"

    def test_tags_not_enabled_disables_subordinates(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.tags_index_page is False
        assert cfg.tags_show_on_pages is False


# ── Core Tag Collection Tests ────────────────────────────────────────────────


class TestCollectPageTags:
    def test_collect_from_user_guide(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "intro.qmd", "Introduction", tags=["Getting Started", "Python"])
        _make_qmd(ug_dir / "advanced.qmd", "Advanced Usage", tags=["Python", "API"])

        result = gd._collect_page_tags()

        assert "Getting Started" in result
        assert "Python" in result
        assert "API" in result
        assert len(result["Python"]) == 2
        assert len(result["Getting Started"]) == 1

    def test_collect_from_recipes(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        recipes_dir = gd.project_path / "recipes"
        _make_qmd(recipes_dir / "recipe1.qmd", "Easy Recipe", tags=["Beginner"])

        result = gd._collect_page_tags()

        assert "Beginner" in result
        assert result["Beginner"][0]["title"] == "Easy Recipe"
        assert result["Beginner"][0]["section"] == "Recipes"

    def test_shadow_tags_excluded(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\n  shadow:\n    - internal\n",
        )
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "A Page", tags=["Python", "internal"])

        result = gd._collect_page_tags()

        assert "Python" in result
        assert "internal" not in result

    def test_skips_index_qmd(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "index.qmd", "Index", tags=["ShouldSkip"])
        _make_qmd(ug_dir / "intro.qmd", "Intro", tags=["Keep"])

        result = gd._collect_page_tags()

        assert "ShouldSkip" not in result
        assert "Keep" in result

    def test_empty_tags_list(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "No Tags")  # no tags kwarg

        result = gd._collect_page_tags()
        assert len(result) == 0

    def test_no_qmd_files(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        result = gd._collect_page_tags()
        assert len(result) == 0

    def test_custom_section_does_not_duplicate_recipes(self, tmp_path: Path):
        """A custom section whose slug matches 'recipes' must not double-count pages."""
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\nsections:\n  - title: Recipes\n    dir: recipes\n",
        )
        recipes_dir = gd.project_path / "recipes"
        _make_qmd(recipes_dir / "recipe1.qmd", "My Recipe", tags=["Cooking"])

        result = gd._collect_page_tags()

        assert "Cooking" in result
        assert len(result["Cooking"]) == 1, (
            "Recipe page should appear exactly once even when a custom section "
            "overlaps the built-in recipes directory"
        )


# ── Tag Hierarchy Tests ──────────────────────────────────────────────────────


class TestBuildTagHierarchy:
    def test_flat_tags(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        tag_index = {
            "Python": [{"title": "P1", "href": "p1.qmd", "section": "UG"}],
            "Testing": [{"title": "T1", "href": "t1.qmd", "section": "UG"}],
        }
        tree = gd._build_tag_hierarchy(tag_index)

        assert "Python" in tree
        assert "Testing" in tree
        assert tree["Python"]["__pages__"] == tag_index["Python"]

    def test_hierarchical_tags(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        pages = [{"title": "P1", "href": "p1.qmd", "section": "UG"}]
        tag_index = {"Python/Testing": pages}
        tree = gd._build_tag_hierarchy(tag_index)

        assert "Python" in tree
        assert "Testing" in tree["Python"]
        assert tree["Python"]["Testing"]["__pages__"] == pages

    def test_hierarchical_disabled(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\n  hierarchical: false\n",
        )
        pages = [{"title": "P1", "href": "p1.qmd", "section": "UG"}]
        tag_index = {"Python/Testing": pages}
        tree = gd._build_tag_hierarchy(tag_index)

        # Treated as a single flat key
        assert "Python/Testing" in tree
        assert "Python" not in tree

    def test_escaped_slash_stays_flat(self, tmp_path: Path):
        """A backslash-escaped slash should NOT create hierarchy."""
        gd = _bootstrap_project(tmp_path)
        pages = [{"title": "P1", "href": "p1.qmd", "section": "UG"}]
        tag_index = {"AI\\/LLM": pages}
        tree = gd._build_tag_hierarchy(tag_index)

        # "AI/LLM" is a single flat node (slash unescaped in display)
        assert "AI/LLM" in tree
        assert "AI" not in tree
        assert tree["AI/LLM"]["__pages__"] == pages

    def test_mixed_escaped_and_hierarchical(self, tmp_path: Path):
        """Escaped slashes and real hierarchy separators can coexist."""
        gd = _bootstrap_project(tmp_path)
        pages = [{"title": "P1", "href": "p1.qmd", "section": "UG"}]
        # "Tools/CI\/CD" → parent "Tools", child "CI/CD"
        tag_index = {"Tools/CI\\/CD": pages}
        tree = gd._build_tag_hierarchy(tag_index)

        assert "Tools" in tree
        assert "CI/CD" in tree["Tools"]
        assert tree["Tools"]["CI/CD"]["__pages__"] == pages


class TestSplitTagParts:
    def test_simple_split(self):
        assert GreatDocs._split_tag_parts("Python/Testing") == ["Python", "Testing"]

    def test_escaped_slash_no_split(self):
        assert GreatDocs._split_tag_parts("AI\\/LLM") == ["AI/LLM"]

    def test_mixed_escaped_and_real(self):
        assert GreatDocs._split_tag_parts("Tools/CI\\/CD") == ["Tools", "CI/CD"]

    def test_no_slash(self):
        assert GreatDocs._split_tag_parts("Python") == ["Python"]


# ── Tags Index Page Generation Tests ─────────────────────────────────────────


class TestGenerateTagsIndexPage:
    def test_generates_index(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        tag_index = {
            "Python": [{"title": "Intro", "href": "user-guide/intro.qmd", "section": "User Guide"}],
        }
        result = gd._generate_tags_index_page(tag_index)

        assert result == "tags/index.qmd"
        index_path = gd.project_path / "tags" / "index.qmd"
        assert index_path.exists()

        content = index_path.read_text(encoding="utf-8")
        assert "Python" in content
        assert "Intro" in content
        assert 'title: "Tags"' in content

    def test_hierarchical_headings(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        tag_index = {
            "Python/Testing": [
                {"title": "Test Page", "href": "user-guide/test.qmd", "section": "User Guide"}
            ],
            "Python/API": [
                {"title": "API Page", "href": "user-guide/api.qmd", "section": "User Guide"}
            ],
        }
        gd._generate_tags_index_page(tag_index)

        content = (gd.project_path / "tags" / "index.qmd").read_text(encoding="utf-8")
        # Should have a parent "Python" heading and children
        assert "Python" in content
        assert "Testing" in content
        assert "API" in content


# ── Tags JSON Generation Tests ───────────────────────────────────────────────


class TestGenerateTagsJson:
    def test_writes_json(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        tag_index = {
            "Python": [{"title": "Intro", "href": "user-guide/intro.qmd", "section": "User Guide"}],
        }
        gd._generate_tags_json(tag_index)

        json_path = gd.project_path / "_tags.json"
        assert json_path.exists()

        data = json.loads(json_path.read_text())
        assert "page_tags" in data
        assert "user-guide/intro.qmd" in data["page_tags"]
        assert "Python" in data["page_tags"]["user-guide/intro.qmd"]

    def test_shadow_tags_not_in_page_tags(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\n  shadow:\n    - internal\n",
        )
        tag_index = {
            "Python": [{"title": "Intro", "href": "user-guide/intro.qmd", "section": "User Guide"}],
        }
        gd._generate_tags_json(tag_index)

        data = json.loads((gd.project_path / "_tags.json").read_text())
        assert "internal" in data["shadow"]

    def test_default_location_in_json(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path, "tags:\n  enabled: true\n  location: bottom\n")
        tag_index = {
            "Python": [{"title": "Intro", "href": "user-guide/intro.qmd", "section": "User Guide"}],
        }
        gd._generate_tags_json(tag_index)

        data = json.loads((gd.project_path / "_tags.json").read_text())
        assert data["default_location"] == "bottom"

    def test_default_location_top_in_json(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        tag_index = {
            "Python": [{"title": "Intro", "href": "user-guide/intro.qmd", "section": "User Guide"}],
        }
        gd._generate_tags_json(tag_index)

        data = json.loads((gd.project_path / "_tags.json").read_text())
        assert data["default_location"] == "top"

    def test_per_page_tag_location_in_json(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(
            ug_dir / "intro.qmd", "Introduction", tags=["Python"], extra="tag-location: bottom"
        )
        _make_qmd(ug_dir / "advanced.qmd", "Advanced", tags=["Python"])

        tag_index = gd._collect_page_tags()
        gd._generate_tags_json(tag_index)

        data = json.loads((gd.project_path / "_tags.json").read_text())
        assert data["page_tag_locations"]["user-guide/intro.qmd"] == "bottom"
        assert "user-guide/advanced.qmd" not in data["page_tag_locations"]

    def test_per_page_tag_location_invalid_ignored(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "Page", tags=["Python"], extra="tag-location: middle")

        tag_index = gd._collect_page_tags()
        gd._generate_tags_json(tag_index)

        data = json.loads((gd.project_path / "_tags.json").read_text())
        assert "user-guide/page.qmd" not in data["page_tag_locations"]


# ── Tag Slug Tests ───────────────────────────────────────────────────────────


class TestTagSlug:
    def test_simple(self):
        assert GreatDocs._tag_slug("Python") == "python"

    def test_spaces(self):
        assert GreatDocs._tag_slug("Getting Started") == "getting-started"

    def test_hierarchical(self):
        assert GreatDocs._tag_slug("Python/Testing") == "python-testing"

    def test_special_chars(self):
        assert GreatDocs._tag_slug("C++ & More!") == "c-more"


# ── Tag Icon HTML Tests ─────────────────────────────────────────────────────


class TestGetTagIconHtml:
    def test_no_icon(self):
        result = GreatDocs._get_tag_icon_html("Python", {})
        assert result == ""

    def test_with_icon(self):
        result = GreatDocs._get_tag_icon_html("Python", {"Python": "code"})
        assert "<svg " in result
        assert "gd-tag-icon-svg" in result


# ── Process Tags Integration Test ────────────────────────────────────────────


class TestProcessTags:
    def test_process_tags_returns_true_with_tags(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "Page", tags=["Python"])

        result = gd._process_tags()
        assert result is True
        assert (gd.project_path / "tags" / "index.qmd").exists()
        assert (gd.project_path / "_tags.json").exists()

    def test_process_tags_returns_false_without_tags(self, tmp_path: Path):
        gd = _bootstrap_project(tmp_path)
        result = gd._process_tags()
        assert result is False

    def test_process_tags_no_index_page(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\n  index_page: false\n",
        )
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "Page", tags=["Python"])

        gd._process_tags()
        assert not (gd.project_path / "tags" / "index.qmd").exists()
        assert (gd.project_path / "_tags.json").exists()

    def test_process_tags_no_show_on_pages(self, tmp_path: Path):
        gd = _bootstrap_project(
            tmp_path,
            "tags:\n  enabled: true\n  show_on_pages: false\n",
        )
        ug_dir = gd.project_path / "user-guide"
        _make_qmd(ug_dir / "page.qmd", "Page", tags=["Python"])

        gd._process_tags()
        assert (gd.project_path / "tags" / "index.qmd").exists()
        assert not (gd.project_path / "_tags.json").exists()
