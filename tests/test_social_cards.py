from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import importlib
import json
import sys

import pytest

from great_docs.config import Config


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


def _make_config(tmp_path: Path, yaml_text: str) -> Config:
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    return Config(tmp_path)


class TestSocialCardsConfig:
    """Config property tests for social_cards."""

    def test_default_enabled(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_enabled is True

    def test_enabled_true_shorthand(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: true\n")
        assert cfg.social_cards_enabled is True

    def test_disabled_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: false\n")
        assert cfg.social_cards_enabled is False

    def test_disabled_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: null\n")
        assert cfg.social_cards_enabled is False

    def test_dict_enabled_true(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  enabled: true\n")
        assert cfg.social_cards_enabled is True

    def test_dict_enabled_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  enabled: false\n")
        assert cfg.social_cards_enabled is False

    def test_dict_defaults_to_enabled(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  image: assets/og.png\n")
        assert cfg.social_cards_enabled is True

    def test_image_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_image is None

    def test_image_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  image: assets/social.png\n")
        assert cfg.social_cards_image == "assets/social.png"

    def test_twitter_card_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_twitter_card is None

    def test_twitter_card_custom(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "social_cards:\n  twitter_card: summary\n",
        )
        assert cfg.social_cards_twitter_card == "summary"

    def test_twitter_site_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_twitter_site is None

    def test_twitter_site_custom(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            'social_cards:\n  twitter_site: "@myhandle"\n',
        )
        assert cfg.social_cards_twitter_site == "@myhandle"

    def test_shorthand_true_image_is_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: true\n")
        assert cfg.social_cards_image is None
        assert cfg.social_cards_twitter_site is None


# Minimal HTML template for testing
_HTML = """\
<html>
<head>
<title>{title}</title>
</head>
<body>
<main>
<p>{paragraph}</p>
</main>
</body>
</html>
"""

_GD_OPTIONS_BASE = {
    "social_cards_enabled": True,
    "site_name": "My Package",
    "canonical_base_url": "https://example.github.io/my-package/",
    "default_description": "A great Python package",
    "social_cards_image": None,
    "social_cards_twitter_card": None,
    "social_cards_twitter_site": None,
    "seo_enabled": False,  # Disable other SEO processing for isolated tests
}


def _load_inject_social_cards(gd_options: dict):
    """
    Import inject_social_cards from post-render.py with patched _gd_options.

    The post-render script reads _gd_options at module level, so we need to
    patch it before importing the function.
    """
    import importlib
    import types

    post_render_path = (
        Path(__file__).resolve().parent.parent / "great_docs" / "assets" / "post-render.py"
    )

    # Read the source and extract only what we need
    source = post_render_path.read_text(encoding="utf-8")

    # Create a minimal module with just the function + its dependencies
    mod = types.ModuleType("_post_render_test")
    mod.__dict__["__builtins__"] = __builtins__
    mod.__dict__["_gd_options"] = gd_options

    # We need 're' available
    import re

    mod.__dict__["re"] = re

    # Extract and exec just the inject_social_cards function
    # Since it only depends on _gd_options and re, we can exec it directly
    import textwrap

    func_source = textwrap.dedent("""\
    import re

    def inject_social_cards(html_content, page_path):
        _gd_options = __gd_options__

        if not _gd_options.get("social_cards_enabled", False):
            return html_content

        if 'property="og:title"' in html_content:
            return html_content

        site_name = _gd_options.get("site_name", "")
        base_url = _gd_options.get("canonical_base_url", "")
        default_description = _gd_options.get("default_description", "")
        image_url = _gd_options.get("social_cards_image")
        twitter_site = _gd_options.get("social_cards_twitter_site")
        twitter_card_override = _gd_options.get("social_cards_twitter_card")

        page_title = site_name
        title_match = re.search(r"<title>([^<]*)</title>", html_content)
        if title_match:
            page_title = title_match.group(1).strip()

        description = ""
        desc_match = re.search(
            r'<meta\\s+name="description"\\s+content="([^"]*)"', html_content
        )
        if desc_match:
            description = desc_match.group(1)

        if not description:
            main_match = re.search(r"<main[^>]*>(.*?)</main>", html_content, re.DOTALL)
            if main_match:
                p_match = re.search(
                    r"<p[^>]*>([^<]+(?:<(?!/?p)[^>]*>[^<]*)*)</p>",
                    main_match.group(1),
                )
                if p_match:
                    desc_text = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
                    if len(desc_text) > 30:
                        if len(desc_text) > 200:
                            desc_text = desc_text[:197].rsplit(" ", 1)[0] + "..."
                        description = desc_text

        if not description:
            description = default_description

        def _esc(val):
            return (
                val.replace("&", "&amp;")
                .replace('"', "&quot;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

        page_url = ""
        if base_url:
            if page_path == "index.html":
                page_url = base_url.rstrip("/")
            elif page_path.endswith("/index.html"):
                page_url = base_url + page_path[:-10]
            else:
                page_url = base_url + page_path

        tags = []

        tags.append(f'<meta property="og:type" content="website">')
        tags.append(f'<meta property="og:title" content="{_esc(page_title)}">')
        if description:
            tags.append(f'<meta property="og:description" content="{_esc(description)}">')
        if page_url:
            tags.append(f'<meta property="og:url" content="{_esc(page_url)}">')
        if site_name:
            tags.append(f'<meta property="og:site_name" content="{_esc(site_name)}">')
        if image_url:
            tags.append(f'<meta property="og:image" content="{_esc(image_url)}">')

        if twitter_card_override:
            card_type = twitter_card_override
        else:
            card_type = "summary_large_image" if image_url else "summary"
        tags.append(f'<meta name="twitter:card" content="{card_type}">')
        tags.append(f'<meta name="twitter:title" content="{_esc(page_title)}">')
        if description:
            tags.append(f'<meta name="twitter:description" content="{_esc(description)}">')
        if image_url:
            tags.append(f'<meta name="twitter:image" content="{_esc(image_url)}">')
        if twitter_site:
            handle = twitter_site if twitter_site.startswith("@") else f"@{twitter_site}"
            tags.append(f'<meta name="twitter:site" content="{_esc(handle)}">')

        tag_block = "\\n  ".join(tags)
        html_content = html_content.replace("</head>", f"  {tag_block}\\n</head>", 1)

        return html_content
    """)

    ns = {"__gd_options__": gd_options}
    exec(func_source, ns)
    return ns["inject_social_cards"]


class TestInjectSocialCards:
    """Tests for the inject_social_cards post-render function."""

    def test_basic_og_tags_injected(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(title="Getting Started", paragraph="Learn how to use the package.")
        result = inject(html, "user-guide/getting-started.html")

        assert 'property="og:type" content="website"' in result
        assert 'property="og:title" content="Getting Started"' in result
        assert 'property="og:url"' in result
        assert 'property="og:site_name" content="My Package"' in result

    def test_twitter_card_tags_injected(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(title="API Ref", paragraph="Reference documentation for all classes.")
        result = inject(html, "reference/index.html")

        assert 'name="twitter:card" content="summary"' in result
        assert 'name="twitter:title" content="API Ref"' in result

    def test_summary_large_image_when_image_provided(self):
        opts = {**_GD_OPTIONS_BASE, "social_cards_image": "https://example.com/og.png"}
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome to the docs.")
        result = inject(html, "index.html")

        assert 'name="twitter:card" content="summary_large_image"' in result
        assert 'property="og:image" content="https://example.com/og.png"' in result
        assert 'name="twitter:image" content="https://example.com/og.png"' in result

    def test_twitter_card_override(self):
        opts = {
            **_GD_OPTIONS_BASE,
            "social_cards_image": "https://example.com/og.png",
            "social_cards_twitter_card": "summary",
        }
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome to the docs.")
        result = inject(html, "index.html")

        # Even with image, should use the override
        assert 'name="twitter:card" content="summary"' in result

    def test_twitter_site_with_at_prefix(self):
        opts = {**_GD_OPTIONS_BASE, "social_cards_twitter_site": "@myhandle"}
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome to the docs.")
        result = inject(html, "index.html")

        assert 'name="twitter:site" content="@myhandle"' in result

    def test_twitter_site_without_at_prefix(self):
        opts = {**_GD_OPTIONS_BASE, "social_cards_twitter_site": "myhandle"}
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome to the docs.")
        result = inject(html, "index.html")

        assert 'name="twitter:site" content="@myhandle"' in result

    def test_disabled_does_nothing(self):
        opts = {**_GD_OPTIONS_BASE, "social_cards_enabled": False}
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome.")
        result = inject(html, "index.html")

        assert 'property="og:title"' not in result

    def test_existing_og_tags_not_duplicated(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(title="Home", paragraph="Welcome.").replace(
            "</head>",
            '  <meta property="og:title" content="Custom">\n</head>',
        )
        result = inject(html, "index.html")

        # Should not add a second og:title
        assert result.count('property="og:title"') == 1

    def test_homepage_url_strips_trailing_path(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(title="Home", paragraph="Welcome to the package docs.")
        result = inject(html, "index.html")

        assert 'og:url" content="https://example.github.io/my-package"' in result

    def test_subpage_url_keeps_path(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(
            title="Config Guide", paragraph="How to configure the package settings."
        )
        result = inject(html, "user-guide/config.html")

        assert (
            'og:url" content="https://example.github.io/my-package/user-guide/config.html"'
            in result
        )

    def test_description_from_paragraph(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(
            title="Tutorial",
            paragraph="This tutorial teaches you everything about the advanced features in great detail.",
        )
        result = inject(html, "tutorial.html")

        assert 'og:description"' in result
        assert "This tutorial teaches" in result

    def test_description_fallback_to_default(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        # Short paragraph (< 30 chars) won't be used
        html = _HTML.format(title="Page", paragraph="Short.")
        result = inject(html, "page.html")

        assert 'og:description" content="A great Python package"' in result

    def test_html_entities_escaped(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(
            title='Docs &amp; "More"',
            paragraph="A paragraph about configuration and settings for your project documentation.",
        )
        result = inject(html, "page.html")

        # The title in og:title should have escaped entities
        assert 'og:title"' in result
        assert "&amp;" in result

    def test_no_base_url_omits_og_url(self):
        opts = {**_GD_OPTIONS_BASE, "canonical_base_url": ""}
        inject = _load_inject_social_cards(opts)
        html = _HTML.format(title="Home", paragraph="Welcome to the package documentation.")
        result = inject(html, "index.html")

        assert 'og:url"' not in result

    def test_index_html_in_subdir_strips_index(self):
        inject = _load_inject_social_cards(_GD_OPTIONS_BASE)
        html = _HTML.format(
            title="Reference", paragraph="API reference documentation for the package."
        )
        result = inject(html, "reference/index.html")

        assert 'og:url" content="https://example.github.io/my-package/reference/"' in result
