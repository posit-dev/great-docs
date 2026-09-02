"""Tests for the shipped `great-docs.default.yml` single source of truth."""

import io
import re
from importlib import resources
from typing import Any

from great_docs.config import DEFAULT_CONFIG, create_default_config

# Verbatim snapshot of DEFAULT_CONFIG captured at the start of the config
# single-source migration. Guards faithful transcription of VALUES into
# great-docs.default.yml. Do NOT import DEFAULT_CONFIG for this constant --
# that would defeat the check.
FROZEN_DEFAULT_CONFIG: dict[str, Any] = {
    "module": None,
    "display_name": None,
    "project_type": "python",
    "parser": "numpy",
    "call_signature_highlight_style": "pygments",
    "call_signature_wrap_style": "per_parameter",
    "dynamic": True,
    "jupyter": "python3",
    "exclude": [],
    "auto_include": [],
    "no_auto_exclude": False,
    # Deliberately changed from the captured `True`: the project-type-dependent
    # default is now expressed as the `null` auto sentinel rather than inferred
    # from whether the key appears in the user's file. Behaviour is unchanged.
    "pypi": None,
    "repo": None,
    "github_style": "widget",
    "site_url": None,
    "source": {"enabled": True, "branch": None, "path": None, "placement": "usage"},
    "sidebar_filter": {"enabled": True, "min_items": 20},
    "marimo": {"enabled": False, "version": None},
    "cli": {
        "enabled": False,
        "module": None,
        "name": None,
        "title": None,
        "desc": None,
        "sections": [],
    },
    "go_cli": {"enabled": False},
    "rust_cli": {"enabled": False},
    "mcp": {"enabled": True, "module": None, "server_var": None, "name": None, "categories": {}},
    "dark_mode_toggle": True,
    "authors": [],
    "funding": None,
    "site": {"theme": "flatly", "toc": True, "toc-depth": 2, "html-math-method": "katex"},
    "language": "en",
    "show_dates": False,
    "date_format": "%B %d, %Y",
    "show_author": True,
    "show_security": True,
    "team_author": None,
    "changelog": {"enabled": True, "max_releases": 50},
    "sections": [],
    "custom_pages": None,
    "homepage": "index",
    "user_guide": None,
    "bibliography": [],
    "csl": None,
    "reference": [],
    "inline_methods": 5,
    "logo": {"light": None, "dark": None, "show_title": False},
    "favicon": None,
    "hero": {
        "enabled": None,
        "logo": None,
        "logo_height": "200px",
        "name": None,
        "tagline": None,
        "badges": "auto",
        "starfield": False,
    },
    "markdown_pages": {"enabled": True, "widget": True},
    "announcement": {
        "content": None,
        "type": "info",
        "dismissable": True,
        "url": None,
        "style": None,
        "position": "above-navbar",
    },
    "versions": [],
    "version_selector": {
        "enabled": True,
        "placement": "navbar-right",
        "show_eol": True,
        "warning_banner": True,
    },
    "version_aliases": {"latest": True, "stable": True, "dev": True},
    "new_is_old": None,
    "accent_color": None,
    "navbar_style": None,
    "navbar_color": None,
    "navbar_order": None,
    "content_style": {"preset": None, "pages": "all"},
    "scale_to_fit": None,
    "scale_to_fit_min_scale": None,
    "nav_icons": {},
    "keyboard_nav": True,
    "package_info_page": True,
    "back_to_top": True,
    "attribution": True,
    "include_in_header": [],
    "freeze": {"mode": "auto", "pre_render": []},
    "pre_render": [],
    "skill": {
        "enabled": True,
        "file": None,
        "well_known": True,
        "gotchas": [],
        "best_practices": [],
        "decision_table": [],
        "extra_body": None,
        "skills": [],
    },
    "social_cards": {"enabled": True, "image": None, "twitter_card": None, "twitter_site": None},
    "page_status": {
        "enabled": False,
        "show_in_sidebar": True,
        "show_on_pages": True,
        "statuses": {
            "new": {
                "label": "New",
                "icon": "sparkles",
                "color": "#10b981",
                "description": "Recently added",
            },
            "updated": {
                "label": "Updated",
                "icon": "refresh-cw",
                "color": "#3b82f6",
                "description": "Recently updated",
            },
            "beta": {
                "label": "Beta",
                "icon": "flask-conical",
                "color": "#f59e0b",
                "description": "Beta feature",
            },
            "deprecated": {
                "label": "Deprecated",
                "icon": "triangle-alert",
                "color": "#ef4444",
                "description": "May be removed in a future release",
            },
            "experimental": {
                "label": "Experimental",
                "icon": "beaker",
                "color": "#8b5cf6",
                "description": "API may change without notice",
            },
            "upcoming": {
                "label": "Upcoming",
                "icon": "rocket",
                "color": "#e63946",
                "description": "Coming in a future release",
            },
        },
    },
    "tags": {
        "enabled": False,
        "index_page": True,
        "show_on_pages": True,
        "hierarchical": True,
        "icons": {},
        "shadow": [],
        "scoped": False,
        "location": "top",
    },
    "seo": {
        "enabled": True,
        "sitemap": {
            "enabled": True,
            "changefreq": {
                "homepage": "weekly",
                "reference": "monthly",
                "user_guide": "monthly",
                "changelog": "weekly",
                "default": "monthly",
            },
            "priority": {
                "homepage": 1.0,
                "reference": 0.8,
                "user_guide": 0.9,
                "changelog": 0.6,
                "default": 0.5,
            },
        },
        "robots": {
            "enabled": True,
            "allow_all": True,
            "disallow": [],
            "crawl_delay": None,
            "extra_rules": [],
        },
        "canonical": {"enabled": True, "base_url": None},
        "title_template": "{page_title} | {site_name}",
        "structured_data": {"enabled": True, "type": "SoftwareSourceCode"},
        "default_description": None,
    },
}


def _default_config_text() -> str:
    return (
        resources.files("great_docs")
        .joinpath("assets", "great-docs.default.yml")
        .read_text(encoding="utf-8")
    )


def test_config_defaults_yaml_matches_frozen_defaults():
    assert DEFAULT_CONFIG == FROZEN_DEFAULT_CONFIG


def test_no_python_literal_examples_in_default_yaml():
    """Comments must show examples as YAML, never Python/JSON literals (C1)"""
    text = _default_config_text()
    bad = re.compile(r'#.*(: \{"|: \[\{|\bdict: \{|\blist\[|\bExample: \{)')
    offenders = [ln for ln in text.splitlines() if bad.search(ln)]
    assert not offenders, "Python-literal example comments found:\n" + "\n".join(offenders)


def test_config_defaults_yaml_is_packaged():
    resource = resources.files("great_docs").joinpath("assets", "great-docs.default.yml")
    assert resource.is_file()
    assert resource.read_text(encoding="utf-8").strip()


def test_every_top_level_key_has_a_comment():
    lines = _default_config_text().splitlines()
    for i, line in enumerate(lines):
        # Top-level key: no indentation, not a comment, not blank.
        if line and line[0] not in " #" and ":" in line:
            prev = lines[i - 1].strip() if i > 0 else ""
            assert prev.startswith("#"), f"undocumented top-level key: {line!r}"


def test_create_default_config_is_fully_commented():
    output = create_default_config()
    for line in output.splitlines():
        # No live mapping key at column 0 -- every real key must be commented.
        assert not re.match(r"^[A-Za-z0-9_-]+:", line), f"uncommented key: {line!r}"


def test_create_default_config_lists_every_top_level_key():
    output = create_default_config()
    for key in DEFAULT_CONFIG:
        assert f"# {key}:" in output, f"missing key in template: {key}"


def test_emitted_template_comments_out_exactly_the_source():
    # The template is great-docs.default.yml with every live value line
    # commented out and prose/blank lines untouched. Verifying this
    # line-by-line (rather than trying to invert the transform, which is
    # lossy for prose) confirms nothing is dropped or altered: the live
    # content the template would restore is exactly great-docs.default.yml,
    # which parses to DEFAULT_CONFIG.
    from yaml12 import read_yaml

    source = _default_config_text()
    assert read_yaml(io.StringIO(source)) == DEFAULT_CONFIG

    src_lines = source.splitlines()
    emt_lines = create_default_config().splitlines()
    assert len(src_lines) == len(emt_lines)
    # A live block is commented as one unit: its column-0 key and every
    # indented line under it (nested keys and interleaved prose) get a `# `
    # at column 0. Section headers and pure example blocks are left as-is.
    in_block = False
    for src, emt in zip(src_lines, emt_lines):
        if not src.strip():
            assert emt == src
            continue
        indented = src.lstrip(" ") != src
        if indented:
            assert emt == (f"# {src}" if in_block else src)
        elif src.lstrip(" ").startswith("#"):
            assert emt == src
            in_block = False
        else:
            assert emt == f"# {src}"
            in_block = True


def test_create_default_config_override_replaces_scalar():
    output = create_default_config({"parser": "parser: google"})
    assert "\nparser: google\n" in output
    # the default line is gone, other keys stay commented
    assert "# parser: numpy" not in output
    assert "# dynamic: true" in output


def test_create_default_config_override_multiline_block():
    ref = "reference:\n  - title: Classes\n    contents:\n      - Foo"
    output = create_default_config({"reference": ref})
    assert ref + "\n" in output
    assert "# reference: []" not in output


def test_create_default_config_override_swallows_block_body():
    # Overriding a block-valued key drops the old live body lines, so the
    # result parses with only the override's values under that key.
    import io

    from yaml12 import read_yaml

    output = create_default_config({"site": "site:\n  theme: cosmo"})
    assert "\nsite:\n  theme: cosmo\n" in output
    cfg = read_yaml(io.StringIO(output))
    assert cfg["site"] == {"theme": "cosmo"}


def test_create_default_config_no_args_still_fully_commented():
    output = create_default_config()
    for line in output.splitlines():
        assert not re.match(r"^[A-Za-z0-9_-]+:", line), f"uncommented: {line!r}"
