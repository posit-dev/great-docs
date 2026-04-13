from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from great_docs.config import Config, DEFAULT_CONFIG, create_default_config, load_config


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Return a temp directory usable as a project root."""
    return tmp_path


def _make_config(tmp_path: Path, yaml_text: str) -> Config:
    """Helper: write *yaml_text* to great-docs.yml and return a Config."""
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    return Config(tmp_path)


class TestConfigInit:
    def test_no_config_file_uses_defaults(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg._config == DEFAULT_CONFIG.copy()

    def test_loads_user_config(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "parser: google\n")
        assert cfg.parser == "google"

    def test_yaml_error_prints_warning(self, tmp_project: Path, capsys):
        """Covers lines 167-168 (YAMLError handler)."""
        (tmp_project / "great-docs.yml").write_text(
            "invalid: [\nunmatched bracket", encoding="utf-8"
        )
        cfg = Config(tmp_project)
        captured = capsys.readouterr()
        assert "Warning: Error parsing great-docs.yml" in captured.out
        # Falls back to defaults
        assert cfg.parser == "numpy"

    def test_generic_read_error_prints_warning(self, tmp_project: Path, capsys):
        """Covers lines 169-170 (generic Exception handler)."""
        (tmp_project / "great-docs.yml").write_text("parser: google\n")
        with patch("builtins.open", side_effect=PermissionError("denied")):
            cfg = Config(tmp_project)
        captured = capsys.readouterr()
        assert "Warning: Could not read great-docs.yml" in captured.out
        assert cfg.parser == "numpy"


class TestMergeConfig:
    def test_deep_merge_nested_dicts(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "source:\n  branch: develop\n")
        # branch overridden, other defaults preserved
        assert cfg.source_branch == "develop"
        assert cfg.source_enabled is True

    def test_scalar_replaces_default(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "parser: sphinx\n")
        assert cfg.parser == "sphinx"

    def test_new_key_in_user_config(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "custom_key: custom_value\n")
        assert cfg.get("custom_key") == "custom_value"


class TestGet:
    def test_simple_key(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.get("parser") == "numpy"

    def test_dot_notation(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.get("source.enabled") is True

    def test_missing_key_returns_default(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_missing_nested_key_returns_default(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.get("source.nonexistent", 42) == 42

    def test_traversal_through_non_dict_returns_default(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "parser: google\n")
        # parser is a string, not a dict — can't traverse further
        assert cfg.get("parser.sub", "nope") == "nope"


class TestScalarProperties:
    def test_exclude_default(self, tmp_project: Path):
        assert Config(tmp_project).exclude == []

    def test_exclude_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "exclude:\n  - Foo\n  - Bar\n")
        assert cfg.exclude == ["Foo", "Bar"]

    def test_repo_default(self, tmp_project: Path):
        assert Config(tmp_project).repo is None

    def test_repo_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "repo: https://github.com/owner/repo\n")
        assert cfg.repo == "https://github.com/owner/repo"

    def test_github_style_default(self, tmp_project: Path):
        assert Config(tmp_project).github_style == "widget"

    def test_github_style_icon(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "github_style: icon\n")
        assert cfg.github_style == "icon"

    def test_source_enabled_default(self, tmp_project: Path):
        assert Config(tmp_project).source_enabled is True

    def test_source_branch_default(self, tmp_project: Path):
        assert Config(tmp_project).source_branch is None

    def test_source_path_default(self, tmp_project: Path):
        assert Config(tmp_project).source_path is None

    def test_source_placement_default(self, tmp_project: Path):
        assert Config(tmp_project).source_placement == "usage"

    def test_sidebar_filter_enabled_default(self, tmp_project: Path):
        assert Config(tmp_project).sidebar_filter_enabled is True

    def test_sidebar_filter_min_items_default(self, tmp_project: Path):
        assert Config(tmp_project).sidebar_filter_min_items == 20

    def test_cli_enabled_default(self, tmp_project: Path):
        assert Config(tmp_project).cli_enabled is False

    def test_cli_module_default(self, tmp_project: Path):
        assert Config(tmp_project).cli_module is None

    def test_cli_name_default(self, tmp_project: Path):
        assert Config(tmp_project).cli_name is None

    def test_changelog_enabled_default(self, tmp_project: Path):
        assert Config(tmp_project).changelog_enabled is True

    def test_changelog_max_releases_default(self, tmp_project: Path):
        assert Config(tmp_project).changelog_max_releases == 50

    def test_sections_default(self, tmp_project: Path):
        assert Config(tmp_project).sections == []

    def test_custom_pages_default(self, tmp_project: Path):
        assert Config(tmp_project).custom_pages == [{"dir": "custom", "output": "custom"}]

    def test_custom_pages_false_disables_processing(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "custom_pages: false\n")
        assert cfg.custom_pages == []

    def test_custom_pages_string_uses_basename_for_output(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "custom_pages: marketing/pages\n")
        assert cfg.custom_pages == [{"dir": "marketing/pages", "output": "pages"}]

    def test_custom_pages_dict_supports_output_override(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "custom_pages:\n  dir: marketing\n  output: py\n",
        )
        assert cfg.custom_pages == [{"dir": "marketing", "output": "py"}]

    def test_custom_pages_list_normalizes_multiple_entries(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "custom_pages:\n  - marketing\n  - dir: playgrounds/raw\n    output: demos\n",
        )
        assert cfg.custom_pages == [
            {"dir": "marketing", "output": "marketing"},
            {"dir": "playgrounds/raw", "output": "demos"},
        ]

    def test_dark_mode_toggle_default(self, tmp_project: Path):
        assert Config(tmp_project).dark_mode_toggle is True

    def test_back_to_top_default(self, tmp_project: Path):
        assert Config(tmp_project).back_to_top is True

    def test_back_to_top_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "back_to_top: false\n")
        assert cfg.back_to_top is False

    def test_keyboard_nav_default(self, tmp_project: Path):
        assert Config(tmp_project).keyboard_nav is True

    def test_keyboard_nav_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "keyboard_nav: false\n")
        assert cfg.keyboard_nav is False

    def test_parser_default(self, tmp_project: Path):
        assert Config(tmp_project).parser == "numpy"

    def test_dynamic_default(self, tmp_project: Path):
        assert Config(tmp_project).dynamic is True

    def test_module_default(self, tmp_project: Path):
        assert Config(tmp_project).module is None

    def test_display_name_default(self, tmp_project: Path):
        assert Config(tmp_project).display_name is None

    def test_authors_default(self, tmp_project: Path):
        assert Config(tmp_project).authors == []

    def test_funding_default(self, tmp_project: Path):
        assert Config(tmp_project).funding is None

    def test_site_default(self, tmp_project: Path):
        assert Config(tmp_project).site == {
            "theme": "flatly",
            "toc": True,
            "toc-depth": 2,
            "language": "en",
            "show_dates": False,
            "date_format": "%B %d, %Y",
            "show_author": True,
            "show_security": True,
        }

    def test_jupyter_default(self, tmp_project: Path):
        assert Config(tmp_project).jupyter == "python3"

    def test_language_default(self, tmp_project: Path):
        assert Config(tmp_project).language == "en"

    def test_language_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "site:\n  language: fr\n")
        assert cfg.language == "fr"

    def test_attribution_default(self, tmp_project: Path):
        assert Config(tmp_project).attribution is True

    def test_attribution_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "attribution: false\n")
        assert cfg.attribution is False


class TestHomepage:
    def test_default(self, tmp_project: Path):
        assert Config(tmp_project).homepage == "index"

    def test_user_guide(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "homepage: user_guide\n")
        assert cfg.homepage == "user_guide"

    def test_invalid_value_falls_back(self, tmp_project: Path, capsys):
        """Covers lines 365-366 (invalid homepage value)."""
        cfg = _make_config(tmp_project, "homepage: bogus\n")
        assert cfg.homepage == "index"
        captured = capsys.readouterr()
        assert "Warning: Invalid homepage value" in captured.out


class TestUserGuide:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).user_guide is None

    def test_string(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "user_guide: docs/guides\n")
        assert cfg.user_guide == "docs/guides"
        assert cfg.user_guide_dir == "docs/guides"
        assert cfg.user_guide_is_explicit is False

    def test_list_explicit(self, tmp_project: Path):
        """Covers line 385 (user_guide_is_explicit True branch)."""
        cfg = _make_config(
            tmp_project,
            "user_guide:\n  - section: Get Started\n    contents:\n      - intro.qmd\n",
        )
        assert isinstance(cfg.user_guide, list)
        assert cfg.user_guide_is_explicit is True
        assert cfg.user_guide_dir is None


class TestReference:
    def test_default_empty_list(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.reference == []
        assert cfg.reference_enabled is True
        assert cfg.reference_title is None
        assert cfg.reference_desc is None

    def test_list_form(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "reference:\n  - title: Core\n    contents:\n      - MyClass\n",
        )
        assert len(cfg.reference) == 1
        assert cfg.reference[0]["title"] == "Core"

    def test_dict_form_with_sections(self, tmp_project: Path):
        """Covers lines 432-436 (dict form with embedded sections)."""
        cfg = _make_config(
            tmp_project,
            (
                "reference:\n"
                "  title: API Docs\n"
                "  desc: Full reference\n"
                "  sections:\n"
                "    - title: Core\n"
                "      contents:\n"
                "        - MyClass\n"
            ),
        )
        assert cfg.reference == [{"title": "Core", "contents": ["MyClass"]}]
        assert cfg.reference_title == "API Docs"  # line 447
        assert cfg.reference_desc == "Full reference"  # line 460

    def test_dict_form_without_sections_key(self, tmp_project: Path):
        """Dict form but no 'sections' key → empty list."""
        cfg = _make_config(
            tmp_project,
            "reference:\n  title: API Docs\n",
        )
        assert cfg.reference == []

    def test_reference_disabled(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "reference: false\n")
        assert cfg.reference_enabled is False
        assert cfg.reference == []


class TestMarkdownPages:
    def test_default_true(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.markdown_pages is True
        assert cfg.markdown_pages_widget is True

    def test_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "markdown_pages: false\n")
        assert cfg.markdown_pages is False
        assert cfg.markdown_pages_widget is False

    def test_dict_widget_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "markdown_pages:\n  widget: false\n")
        assert cfg.markdown_pages is True
        assert cfg.markdown_pages_widget is False

    def test_dict_enabled_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "markdown_pages:\n  enabled: false\n")
        assert cfg.markdown_pages is False
        assert cfg.markdown_pages_widget is False


class TestLogo:
    def test_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.logo is None
        assert cfg.logo_show_title is False

    def test_string(self, tmp_project: Path):
        """Covers line 503 (logo string → dict expansion)."""
        cfg = _make_config(tmp_project, "logo: assets/logo.svg\n")
        assert cfg.logo == {"light": "assets/logo.svg", "dark": "assets/logo.svg"}

    def test_dict(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "logo:\n  light: light.svg\n  dark: dark.svg\n  show_title: true\n",
        )
        assert cfg.logo == {"light": "light.svg", "dark": "dark.svg", "show_title": True}
        assert cfg.logo_show_title is True

    def test_unsupported_type_returns_none(self, tmp_project: Path):
        """Covers line 506 (logo fallback None for non-str/dict)."""
        cfg = _make_config(tmp_project, "logo: 123\n")
        assert cfg.logo is None


class TestHero:
    def test_default_no_logo(self, tmp_project: Path):
        """hero=None and no logo → hero disabled."""
        cfg = Config(tmp_project)
        assert cfg.hero_enabled is False
        assert cfg.hero_explicitly_disabled is False
        assert cfg.hero == {}

    def test_auto_enable_with_logo(self, tmp_project: Path):
        """hero=None + logo configured → hero auto-enabled."""
        cfg = _make_config(tmp_project, "logo: logo.svg\n")
        assert cfg.hero_enabled is True

    def test_hero_false(self, tmp_project: Path):
        """Covers line 525 (hero=False)."""
        cfg = _make_config(tmp_project, "hero: false\n")
        assert cfg.hero_enabled is False
        assert cfg.hero_explicitly_disabled is True

    def test_hero_true(self, tmp_project: Path):
        """Covers line 528 (hero=True → enabled)."""
        cfg = _make_config(tmp_project, "hero: true\n")
        assert cfg.hero_enabled is True

    def test_hero_dict_enabled(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "hero:\n  name: My Package\n")
        assert cfg.hero_enabled is True

    def test_hero_dict_explicitly_disabled(self, tmp_project: Path):
        """Covers line 540 (hero dict with enabled: false)."""
        cfg = _make_config(tmp_project, "hero:\n  enabled: false\n")
        assert cfg.hero_enabled is False
        assert cfg.hero_explicitly_disabled is True


class TestHeroLogo:
    def test_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.hero_logo is None

    def test_explicit_logo(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "hero:\n  logo: hero.svg\n")
        assert cfg.hero_logo == "hero.svg"

    def test_suppressed(self, tmp_project: Path):
        """Covers line 567 (hero logo = false)."""
        cfg = _make_config(tmp_project, "hero:\n  logo: false\n")
        assert cfg.hero_logo is False

    def test_hero_logo_height_default(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.hero_logo_height == "200px"

    def test_hero_logo_height_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "hero:\n  logo_height: 300px\n")
        assert cfg.hero_logo_height == "300px"


class TestHeroName:
    def test_default_fallback_to_display_name(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "display_name: My Pkg\n")
        assert cfg.hero_name == "My Pkg"

    def test_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "hero:\n  name: Custom Name\n")
        assert cfg.hero_name == "Custom Name"

    def test_suppressed(self, tmp_project: Path):
        """Covers line 587 (hero name = false → None)."""
        cfg = _make_config(tmp_project, "hero:\n  name: false\n")
        assert cfg.hero_name is None


class TestHeroTagline:
    def test_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.hero_tagline is None

    def test_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "hero:\n  tagline: A great package\n")
        assert cfg.hero_tagline == "A great package"

    def test_suppressed(self, tmp_project: Path):
        """Covers line 602 (hero tagline = false → None)."""
        cfg = _make_config(tmp_project, "hero:\n  tagline: false\n")
        assert cfg.hero_tagline is None


class TestHeroBadges:
    def test_default_auto(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.hero_badges == "auto"

    def test_explicit_list(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "hero:\n  badges:\n    - url: https://badge.svg\n",
        )
        assert cfg.hero_badges == [{"url": "https://badge.svg"}]

    def test_suppressed(self, tmp_project: Path):
        """Covers line 615 (hero badges = false → None)."""
        cfg = _make_config(tmp_project, "hero:\n  badges: false\n")
        assert cfg.hero_badges is None


class TestFavicon:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).favicon is None

    def test_string(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "favicon: favicon.ico\n")
        assert cfg.favicon == {"icon": "favicon.ico"}

    def test_dict(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "favicon:\n  icon: favicon.ico\n  apple_touch: apple.png\n",
        )
        assert cfg.favicon == {"icon": "favicon.ico", "apple_touch": "apple.png"}

    def test_unsupported_type_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "favicon: 42\n")
        assert cfg.favicon is None


class TestAnnouncement:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).announcement is None

    def test_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "announcement: false\n")
        assert cfg.announcement is None

    def test_string(self, tmp_project: Path):
        """Covers line 655 (announcement string → normalized dict)."""
        cfg = _make_config(tmp_project, "announcement: New release!\n")
        assert cfg.announcement == {
            "content": "New release!",
            "type": "info",
            "dismissable": True,
            "url": None,
            "style": None,
        }

    def test_dict_full(self, tmp_project: Path):
        """Covers line 659 (announcement dict)."""
        cfg = _make_config(
            tmp_project,
            (
                "announcement:\n"
                "  content: Big news\n"
                "  type: warning\n"
                "  dismissable: false\n"
                "  url: https://example.com\n"
                "  style: custom\n"
            ),
        )
        assert cfg.announcement == {
            "content": "Big news",
            "type": "warning",
            "dismissable": False,
            "url": "https://example.com",
            "style": "custom",
        }

    def test_dict_empty_content_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "announcement:\n  type: info\n")
        assert cfg.announcement is None

    def test_unsupported_type_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "announcement: 123\n")
        assert cfg.announcement is None


class TestIncludeInHeader:
    def test_default_empty(self, tmp_project: Path):
        assert Config(tmp_project).include_in_header == []

    def test_none_value(self, tmp_project: Path):
        """Covers line 678 (include_in_header: null → [])."""
        cfg = _make_config(tmp_project, "include_in_header: null\n")
        assert cfg.include_in_header == []

    def test_string(self, tmp_project: Path):
        """Covers line 680 (string → [{"text": ...}])."""
        cfg = _make_config(
            tmp_project,
            "include_in_header: '<script src=\"x.js\"></script>'\n",
        )
        assert cfg.include_in_header == [{"text": '<script src="x.js"></script>'}]

    def test_list_of_strings(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "include_in_header:\n  - '<script>1</script>'\n  - '<script>2</script>'\n",
        )
        assert cfg.include_in_header == [
            {"text": "<script>1</script>"},
            {"text": "<script>2</script>"},
        ]

    def test_list_of_dicts(self, tmp_project: Path):
        """Covers lines 686-687 (dict items in list)."""
        cfg = _make_config(
            tmp_project,
            "include_in_header:\n  - file: extra.html\n",
        )
        assert cfg.include_in_header == [{"file": "extra.html"}]

    def test_list_mixed(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "include_in_header:\n  - '<script>x</script>'\n  - file: extra.html\n",
        )
        assert cfg.include_in_header == [
            {"text": "<script>x</script>"},
            {"file": "extra.html"},
        ]

    def test_list_with_unsupported_item_type(self, tmp_project: Path):
        """Covers branch 686→683 (list item neither str nor dict is skipped)."""
        cfg = Config(tmp_project)
        cfg._config["include_in_header"] = ["<script>x</script>", 42, {"file": "a.html"}]
        assert cfg.include_in_header == [
            {"text": "<script>x</script>"},
            {"file": "a.html"},
        ]

    def test_unsupported_type_returns_empty(self, tmp_project: Path):
        """Covers line 689 (non-str/list/None → [])."""
        cfg = _make_config(tmp_project, "include_in_header: 42\n")
        assert cfg.include_in_header == []


class TestNavbarStyle:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).navbar_style is None

    def test_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "navbar_style: sky\n")
        assert cfg.navbar_style == "sky"


class TestNavbarColor:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).navbar_color is None

    def test_string(self, tmp_project: Path):
        """Covers line 720 (string → light+dark dict)."""
        cfg = _make_config(tmp_project, "navbar_color: '#336699'\n")
        assert cfg.navbar_color == {"light": "#336699", "dark": "#336699"}

    def test_dict(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "navbar_color:\n  light: '#fff'\n  dark: '#333'\n",
        )
        assert cfg.navbar_color == {"light": "#fff", "dark": "#333"}

    def test_dict_empty_returns_none(self, tmp_project: Path):
        """Covers line 728 (empty dict → None)."""
        cfg = _make_config(tmp_project, "navbar_color:\n  invalid_key: foo\n")
        assert cfg.navbar_color is None

    def test_overridden_by_navbar_style(self, tmp_project: Path):
        """navbar_style takes precedence → navbar_color returns None."""
        cfg = _make_config(
            tmp_project,
            "navbar_style: sky\nnavbar_color: '#336699'\n",
        )
        assert cfg.navbar_color is None

    def test_false_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "navbar_color: false\n")
        assert cfg.navbar_color is None

    def test_unsupported_type_returns_none(self, tmp_project: Path):
        """Covers line 728 (non-str/dict → None)."""
        cfg = Config(tmp_project)
        cfg._config["navbar_color"] = 42
        assert cfg.navbar_color is None


class TestContentStyle:
    def test_default_none(self, tmp_project: Path):
        assert Config(tmp_project).content_style is None

    def test_string(self, tmp_project: Path):
        """Covers line 741 (string → preset+pages dict)."""
        cfg = _make_config(tmp_project, "content_style: peach\n")
        assert cfg.content_style == {"preset": "peach", "pages": "all"}

    def test_dict_with_homepage(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "content_style:\n  preset: lilac\n  pages: homepage\n",
        )
        assert cfg.content_style == {"preset": "lilac", "pages": "homepage"}

    def test_dict_invalid_pages_falls_back(self, tmp_project: Path):
        """Covers line 744 (invalid pages value → 'all')."""
        cfg = _make_config(
            tmp_project,
            "content_style:\n  preset: sky\n  pages: invalid\n",
        )
        assert cfg.content_style == {"preset": "sky", "pages": "all"}

    def test_dict_missing_preset_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "content_style:\n  pages: all\n")
        assert cfg.content_style is None

    def test_false_returns_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "content_style: false\n")
        assert cfg.content_style is None

    def test_unsupported_type_returns_none(self, tmp_project: Path):
        """Covers line 746 (non-str/dict → None)."""
        cfg = _make_config(tmp_project, "content_style: 42\n")
        assert cfg.content_style is None


class TestExistsAndToDict:
    def test_exists_true(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "parser: google\n")
        assert cfg.exists() is True

    def test_exists_false(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.exists() is False

    def test_to_dict_returns_copy(self, tmp_project: Path):
        cfg = Config(tmp_project)
        d = cfg.to_dict()
        assert d == cfg._config
        assert d is not cfg._config  # must be a copy


class TestModuleFunctions:
    def test_load_config_str_path(self, tmp_project: Path):
        (tmp_project / "great-docs.yml").write_text("parser: sphinx\n")
        cfg = load_config(str(tmp_project))
        assert isinstance(cfg, Config)
        assert cfg.parser == "sphinx"

    def test_load_config_path_object(self, tmp_project: Path):
        cfg = load_config(tmp_project)
        assert isinstance(cfg, Config)

    def test_create_default_config_is_string(self):
        result = create_default_config()
        assert isinstance(result, str)
        assert "Great Docs Configuration" in result
        assert "parser:" in result


# ── custom_pages edge cases ────────────────────────────────────────────


def test_custom_pages_dict_no_output(tmp_path):
    """Dict entry with missing output falls back to dir name."""
    (tmp_path / "great-docs.yml").write_text("custom_pages:\n  - dir: my_pages\n")
    cfg = Config(tmp_path)
    result = cfg.custom_pages
    assert result == [{"dir": "my_pages", "output": "my_pages"}]


def test_custom_pages_dict_empty_output(tmp_path):
    """Dict entry with empty-string output falls back to dir name."""
    (tmp_path / "great-docs.yml").write_text('custom_pages:\n  - dir: my_pages\n    output: ""\n')
    cfg = Config(tmp_path)
    result = cfg.custom_pages
    assert result[0]["output"] == "my_pages"


# ── dark_mode_toggle ───────────────────────────────────────────────────


def test_dark_mode_toggle_false(tmp_path):
    """dark_mode_toggle returns False when explicitly disabled."""
    (tmp_path / "great-docs.yml").write_text("dark_mode_toggle: false\n")
    cfg = Config(tmp_path)
    assert cfg.dark_mode_toggle is False


# ── team_author ────────────────────────────────────────────────────────


def test_team_author_with_name(tmp_path):
    """team_author returns dict when configured with a name."""
    (tmp_path / "great-docs.yml").write_text(
        "team_author:\n  name: Team\n  image: avatar.png\n  url: https://team.dev\n"
    )
    cfg = Config(tmp_path)
    result = cfg.team_author
    assert result == {"name": "Team", "image": "avatar.png", "url": "https://team.dev"}


def test_team_author_missing_name(tmp_path):
    """team_author returns None when name is not set."""
    (tmp_path / "great-docs.yml").write_text("team_author:\n  image: avatar.png\n")
    cfg = Config(tmp_path)
    assert cfg.team_author is None


def test_team_author_none(tmp_path):
    """team_author returns None when not configured."""
    cfg = Config(tmp_path)
    assert cfg.team_author is None


# ── jupyter ────────────────────────────────────────────────────────────


def test_jupyter_custom_kernel(tmp_path):
    """jupyter returns custom kernel name when configured."""
    (tmp_path / "great-docs.yml").write_text("jupyter: ir\n")
    cfg = Config(tmp_path)
    assert cfg.jupyter == "ir"


# ── social_cards properties ────────────────────────────────────────────


def test_social_cards_image(tmp_path):
    """social_cards_image returns image path from dict config."""
    (tmp_path / "great-docs.yml").write_text("social_cards:\n  image: card.png\n")
    cfg = Config(tmp_path)
    assert cfg.social_cards_image == "card.png"


def test_social_cards_image_none(tmp_path):
    """social_cards_image returns None when not dict."""
    (tmp_path / "great-docs.yml").write_text("social_cards: true\n")
    cfg = Config(tmp_path)
    assert cfg.social_cards_image is None


def test_social_cards_twitter_card(tmp_path):
    """social_cards_twitter_card returns card type."""
    (tmp_path / "great-docs.yml").write_text("social_cards:\n  twitter_card: summary_large_image\n")
    cfg = Config(tmp_path)
    assert cfg.social_cards_twitter_card == "summary_large_image"


def test_social_cards_twitter_site(tmp_path):
    """social_cards_twitter_site returns handle."""
    (tmp_path / "great-docs.yml").write_text("social_cards:\n  twitter_site: '@myhandle'\n")
    cfg = Config(tmp_path)
    assert cfg.social_cards_twitter_site == "@myhandle"


# ── tags_index_page ───────────────────────────────────────────────────


def test_tags_index_page_true(tmp_path):
    """tags_index_page returns True when tags are enabled."""
    (tmp_path / "great-docs.yml").write_text("tags: true\n")
    cfg = Config(tmp_path)
    assert cfg.tags_index_page is True


def test_tags_index_page_false_when_disabled(tmp_path):
    """tags_index_page returns False when tags disabled."""
    cfg = Config(tmp_path)
    assert cfg.tags_index_page is False
