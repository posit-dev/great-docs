"""
Tests for custom page source discovery
"""

from pathlib import Path

from great_docs._content import custom_pages
from great_docs._content.pages import PageMap
from great_docs._project.layout import Layout
from great_docs._yaml import YamlMapping
from tests.support import write_config


def test_custom_page_sources_skip_section_directory(tmp_path: Path):
    config = write_config(tmp_path, "sections:\n  - title: Pages\n    dir: custom\n")
    (tmp_path / "custom").mkdir()

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=print) == []


def test_custom_page_sources_skip_a_missing_default_directory_silently(tmp_path: Path):
    config = write_config(tmp_path, "display_name: Demo\n")
    warnings: list[str] = []

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=warnings.append) == []
    assert warnings == []


def test_custom_page_sources_warn_about_a_missing_configured_directory(tmp_path: Path):
    config = write_config(tmp_path, "custom_pages: custom\n")
    warnings: list[str] = []

    assert custom_pages.find_sources(config, Layout.make(tmp_path), report=warnings.append) == []
    assert warnings == ["Custom pages directory 'custom' not found, skipping"]


def test_navbar_link_needs_a_label_in_a_mapping():
    """Verify that an empty navbar label or unsupported value requests no link"""
    assert custom_pages.navbar_link(YamlMapping({"navbar": {"text": ""}}), "Page", "p.qmd") is None
    assert custom_pages.navbar_link(YamlMapping({"navbar": 3}), "Page", "p.qmd") is None


def test_publish_reports_an_unsupported_layout_and_publishes_a_passthrough_page(tmp_path: Path):
    """Verify that an unsupported `layout` is reported and the page uses passthrough"""
    config = write_config(tmp_path, "display_name: Demo\n")
    layout = Layout.make(tmp_path)
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom" / "page.html").write_text(
        "---\nlayout: weird\n---\n<p>Hi</p>\n", encoding="utf-8"
    )
    warnings: list[str] = []

    published = custom_pages.publish(
        custom_pages.find_sources(config, layout, report=print),
        config=config,
        layout=layout,
        pages=PageMap.make(config, layout, None, []),
        head=custom_pages.RawPageHead(None, None, None, "", None),
        add_dates=lambda content, _: content,
        report=warnings.append,
    )

    assert warnings == [
        "Unsupported custom page layout 'weird' in custom/page.html; defaulting to passthrough"
    ]
    assert published.pages == 1
    assert published.render_excludes == []
    assert (layout.build_dir / "custom" / "page.qmd").exists()
