# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from great_docs._build.steps import Skipped
from great_docs._contribution import Contribution, NavbarLink
from great_docs._layout import Layout
from great_docs._utils import validate_build_dir
from great_docs._website import inline_data, page_scan, quarto_yml, tags
from great_docs.config import Config
from great_docs.core import GreatDocs
from tests.support import write_config

# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _project(tmp_path: Path, yaml_text: str = "tags: true\n") -> tuple[Config, Layout]:
    """
    Create a project and an empty build directory

    Parameters
    ----------
    tmp_path
        The project directory.
    yaml_text
        The contents of `great-docs.yml`.

    Returns
    -------
    :
        The project's configuration and directories.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n', encoding="utf-8")
    config = write_config(tmp_path, yaml_text)
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir()
    return config, layout


def _page(
    href: str, *page_tags: str, section: str = "User Guide", title: str = ""
) -> tags.TaggedPage:
    """
    Create a tagged page without shadow tags or a location override

    Parameters
    ----------
    href
        The page's source path relative to the build directory.
    *page_tags
        The visible tags, in order.
    section
        The section label shown beside the page.
    title
        The page title, falling back to `href` when empty.

    Returns
    -------
    :
        The page.
    """
    return tags.TaggedPage(
        href=href,
        title=title or href,
        section=section,
        tags=page_tags,
        shadowed=False,
        location=None,
    )


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestTagsConfig:
    def test_tags_disabled_by_default(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.tags_enabled is False

    def test_tags_enabled_true(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_enabled is True

    def test_tags_enabled_shorthand(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags: true\n")
        assert cfg.tags_enabled is True

    def test_tags_enabled_false_shorthand(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags: false\n")
        assert cfg.tags_enabled is False

    def test_tags_index_page_default(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_index_page is True

    def test_tags_index_page_disabled(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n  index_page: false\n")
        assert cfg.tags_index_page is False

    def test_tags_show_on_pages_default(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_show_on_pages is True

    def test_tags_hierarchical_default(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_hierarchical is True

    def test_tags_icons_empty(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_icons == {}

    def test_tags_icons_custom(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "tags:\n  enabled: true\n  icons:\n    Python: code\n    Tutorial: book-open\n",
        )
        assert cfg.tags_icons == {"Python": "code", "Tutorial": "book-open"}

    def test_tags_shadow_empty(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_shadow == []

    def test_tags_shadow_custom(self, tmp_path: Path):
        cfg = write_config(
            tmp_path,
            "tags:\n  enabled: true\n  shadow:\n    - internal\n    - draft\n",
        )
        assert cfg.tags_shadow == ["internal", "draft"]

    def test_tags_scoped_default(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_scoped is False

    def test_tags_location_default(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n")
        assert cfg.tags_location == "top"

    def test_tags_location_bottom(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n  location: bottom\n")
        assert cfg.tags_location == "bottom"

    def test_tags_location_top_explicit(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n  location: top\n")
        assert cfg.tags_location == "top"

    def test_tags_location_invalid_falls_back_to_top(self, tmp_path: Path):
        cfg = write_config(tmp_path, "tags:\n  enabled: true\n  location: middle\n")
        assert cfg.tags_location == "top"

    def test_tags_not_enabled_disables_subordinates(self, tmp_path: Path):
        cfg = Config(tmp_path)
        assert cfg.tags_index_page is False
        assert cfg.tags_show_on_pages is False


# ── Page scan ────────────────────────────────────────────────────────────────


class TestContentDirs:
    def test_built_in_dirs_then_sections(self, tmp_path: Path):
        """Scan built-in directories before custom sections"""
        config, layout = _project(tmp_path, "sections:\n  - title: Examples\n    dir: examples\n")
        for name in ("user-guide", "recipes", "reference", "examples"):
            (layout.build_dir / name).mkdir()

        dirs = page_scan.content_dirs(config, layout, reference=False)

        assert [(d.path.name, d.label) for d in dirs] == [
            ("user-guide", "User Guide"),
            ("recipes", "Recipes"),
            ("examples", "Examples"),
        ]

    def test_reference_on_request(self, tmp_path: Path):
        """Include reference pages when requested"""
        config, layout = _project(tmp_path)
        (layout.build_dir / "reference").mkdir()

        dirs = page_scan.content_dirs(config, layout, reference=True)

        assert [d.path.name for d in dirs] == ["reference"]

    def test_section_sharing_a_built_in_dir_is_listed_once(self, tmp_path: Path):
        """Keep the built-in label when a custom section shares its directory"""
        config, layout = _project(tmp_path, "sections:\n  - title: Cookbook\n    dir: recipes\n")
        (layout.build_dir / "recipes").mkdir()

        dirs = page_scan.content_dirs(config, layout, reference=False)

        assert [(d.path.name, d.label) for d in dirs] == [("recipes", "Recipes")]


class TestScan:
    def test_index_pages_on_request(self, tmp_path: Path):
        """Include index pages unless the scan excludes them"""
        _make_qmd(tmp_path / "guide" / "index.qmd", "Index")
        _make_qmd(tmp_path / "guide" / "intro.qmd", "Intro")
        dirs = [page_scan.ContentDir(tmp_path / "guide", "Guide")]

        with_index = page_scan.scan(dirs, tmp_path, skip_index=False)
        without_index = page_scan.scan(dirs, tmp_path, skip_index=True)

        assert [p.href for p in with_index] == ["guide/index.qmd", "guide/intro.qmd"]
        assert [p.href for p in without_index] == ["guide/intro.qmd"]

    def test_skips_pages_that_are_not_utf8(self, tmp_path: Path):
        """Skip pages with invalid UTF-8"""
        (tmp_path / "guide").mkdir()
        (tmp_path / "guide" / "latin1.qmd").write_bytes(b"---\ntitle: caf\xe9\n---\n")
        dirs = [page_scan.ContentDir(tmp_path / "guide", "Guide")]

        assert list(page_scan.scan(dirs, tmp_path, skip_index=True)) == []


# ── Collection ───────────────────────────────────────────────────────────────


class TestCollect:
    def test_groups_pages_by_tag_in_scan_order(self, tmp_path: Path):
        """Preserve scan order within each tag group"""
        config, layout = _project(tmp_path)
        ug_dir = layout.build_dir / "user-guide"
        _make_qmd(ug_dir / "intro.qmd", "Introduction", tags=["Getting Started", "Python"])
        _make_qmd(ug_dir / "advanced.qmd", "Advanced Usage", tags=["Python", "API"])

        groups = tags.group(tags.collect(config, layout))

        assert list(groups) == ["Python", "API", "Getting Started"]
        assert [p.title for p in groups["Python"]] == ["Advanced Usage", "Introduction"]

    def test_recipe_section_and_title_from_file_name(self, tmp_path: Path):
        """Use the recipe section label and derive a missing title from the file name"""
        config, layout = _project(tmp_path)
        (layout.build_dir / "recipes").mkdir()
        (layout.build_dir / "recipes" / "easy-recipe.qmd").write_text(
            "---\ntags: [Beginner]\n---\n", encoding="utf-8"
        )

        [page] = tags.collect(config, layout)

        assert (page.href, page.title, page.section, page.tags) == (
            "recipes/easy-recipe.qmd",
            "Easy Recipe",
            "Recipes",
            ("Beginner",),
        )

    def test_shadow_tags_are_hidden(self, tmp_path: Path):
        """Exclude shadow tags while recording that the page has one"""
        config, layout = _project(tmp_path, "tags:\n  enabled: true\n  shadow:\n    - internal\n")
        _make_qmd(
            layout.build_dir / "user-guide" / "page.qmd", "A Page", tags=["Python", "internal"]
        )

        [page] = tags.collect(config, layout)

        assert page.tags == ("Python",)
        assert page.shadowed

    def test_skips_index_and_untagged_pages(self, tmp_path: Path):
        """Exclude index pages and pages without tags from collection"""
        config, layout = _project(tmp_path)
        ug_dir = layout.build_dir / "user-guide"
        _make_qmd(ug_dir / "index.qmd", "Index", tags=["ShouldSkip"])
        _make_qmd(ug_dir / "untagged.qmd", "No Tags")

        assert tags.collect(config, layout) == []

    def test_custom_section_with_nested_dir(self, tmp_path: Path):
        """Retain the section label for pages in nested custom directories"""
        config, layout = _project(
            tmp_path,
            "tags:\n  enabled: true\nsections:\n  - title: Examples\n    dir: docs/examples\n",
        )
        _make_qmd(layout.build_dir / "docs" / "examples" / "one.qmd", "One", tags=["Demo"])

        [page] = tags.collect(config, layout)

        assert (page.href, page.section) == ("docs/examples/one.qmd", "Examples")

    def test_tag_location_override(self, tmp_path: Path):
        """Keep valid pill placement overrides and ignore invalid ones"""
        config, layout = _project(tmp_path)
        ug_dir = layout.build_dir / "user-guide"
        _make_qmd(ug_dir / "a.qmd", "A", tags=["Python"], extra="tag-location: bottom")
        _make_qmd(ug_dir / "b.qmd", "B", tags=["Python"], extra="tag-location: middle")

        assert [p.location for p in tags.collect(config, layout)] == ["bottom", None]


# ── Hierarchy ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("tag", "parts"),
    [
        ("Python", ["Python"]),
        ("AI/LLM/Chat", ["AI", "LLM", "Chat"]),
        (r"AI\/LLM", ["AI/LLM"]),
        (r"Tools/CI\/CD", ["Tools", "CI/CD"]),
        ("  Python  /  ML  ", ["Python", "ML"]),
        ("A//B", ["A", "B"]),
    ],
)
def test_split_tag(tag: str, parts: list[str]):
    """Split hierarchy levels while preserving escaped slashes"""
    assert tags.split_tag(tag) == parts


class TestHierarchy:
    def test_nests_slash_separated_tags(self, tmp_path: Path):
        """Place pages on the leaf nodes of slash-separated tags"""
        config, _ = _project(tmp_path)
        page = _page("p.qmd", "Python/Testing", "ML")

        root = tags.hierarchy({"Python/Testing": [page], "ML": [page]}, config)

        assert sorted(root.children) == ["ML", "Python"]
        assert root.children["Python"].pages == []
        assert root.children["Python"].children["Testing"].pages == [page]

    def test_escaped_slash_stays_flat(self, tmp_path: Path):
        config, _ = _project(tmp_path)

        root = tags.hierarchy({r"AI\/LLM": [_page("p.qmd", r"AI\/LLM")]}, config)

        assert list(root.children) == ["AI/LLM"]

    def test_flat_when_not_hierarchical(self, tmp_path: Path):
        """Keep slashes in tag names when hierarchy is disabled"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  hierarchical: false\n")

        root = tags.hierarchy({"Python/Testing": [_page("p.qmd", "Python/Testing")]}, config)

        assert list(root.children) == ["Python/Testing"]


# ── Index page ───────────────────────────────────────────────────────────────


class TestRenderIndex:
    def test_front_matter_and_page_links(self, tmp_path: Path):
        """Include front matter, page links, section badges and tooltips in the index"""
        config, _ = _project(tmp_path)
        page = _page("user-guide/intro.qmd", "Python", title="Intro")

        text = tags.render_index({"Python": [page]}, config)

        assert text.startswith('---\ntitle: "Site Tags"\n')
        assert (
            '<div class="gd-tag-page-link">[Intro](../user-guide/intro.qmd)'
            ' <span class="gd-tag-section">User Guide</span></div>'
        ) in text
        assert 'data-tippy-content="1 page in User Guide"' in text

    def test_page_without_section_has_no_badge(self, tmp_path: Path):
        """Render page links without a badge when the section is unnamed"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  hierarchical: false\n")

        text = tags.render_index({"Tag": [_page("page.qmd", "Tag", section="")]}, config)

        assert "gd-tag-page-link" in text
        assert "gd-tag-section" not in text

    def test_flat_listing_is_alphabetical(self, tmp_path: Path):
        """Sort flat tags alphabetically without distinguishing letter case"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  hierarchical: false\n")
        page = _page("p.qmd", "b", "A/C")

        text = tags.render_index({"b": [page], "A/C": [page]}, config)

        assert text.index(">A/C</span>") < text.index(">b</span>")
        assert "gd-tag-pill-segmented" not in text

    def test_nested_tag_is_a_segmented_pill_with_the_parent_icon(self, tmp_path: Path):
        """Show the parent icon in a nested pill and indent its page links"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  icons:\n    AI: code\n")

        text = tags.render_index({"AI/LLM": [_page("p.qmd", "AI/LLM")]}, config)

        child = text.split('class="gd-tag-heading gd-tag-indent-1">')[1]
        assert "gd-tag-pill-segmented" in child
        assert '<span class="gd-tag-pill-segment gd-tag-pill-parent"><span style=' in child
        assert '<div class="gd-tag-pages gd-tag-indent-1">' in text

    def test_parent_without_pages_has_no_tooltip_or_links(self, tmp_path: Path):
        """Omit tooltips and page links for parent tags without their own pages"""
        config, _ = _project(tmp_path)

        text = tags.render_index({"AI/LLM": [_page("p.qmd", "AI/LLM")]}, config)

        assert (
            '<div id="ai" class="gd-tag-heading"><span class="gd-tag-pill">AI</span></div>' in text
        )
        assert text.count('<div class="gd-tag-pages') == 1

    def test_every_heading_has_its_own_id(self, tmp_path: Path):
        """Give each heading a unique id, including parents without pages and non-ASCII tags"""
        config, _ = _project(tmp_path)
        groups = {name: [_page("p.qmd", name)] for name in ["AI/LLM", r"AI\/LLM", "Données"]}

        text = tags.render_index(groups, config)

        assert re.findall(r'<div id="([^"]*)" class="gd-tag-heading', text) == [
            "ai",
            "ai-llm",
            "ai-llm-2",
            "données",
        ]

    def test_tag_icon(self, tmp_path: Path):
        """Render the configured icon alongside the tag tooltip"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  icons:\n    Python: code\n")

        text = tags.render_index({"Python": [_page("p.qmd", "Python")]}, config)

        assert '<span class="gd-tag-pill" data-tippy-content="1 page in User Guide"><span' in text
        assert "gd-tag-icon-svg" in text

    def test_names_titles_and_sections_are_text(self, tmp_path: Path):
        """Escape HTML and Markdown punctuation in tag names, titles and section labels"""
        config, _ = _project(tmp_path)
        page = _page("p.qmd", "__init__", "A<b>&", section='Odd "S" <s>', title="See [x] <z>")

        text = tags.render_index({"__init__": [page], "A<b>&": [page]}, config)

        assert (
            '<span class="gd-tag-pill" data-tippy-content="1 page in Odd &quot;S&quot; &lt;s&gt;">'
            in text
        )
        assert ">A&lt;b&gt;&amp;</span>" in text
        assert r">\_\_init\_\_</span>" in text
        assert (
            r'[See \[x\] &lt;z&gt;](../p.qmd) <span class="gd-tag-section">Odd "S" &lt;s&gt;</span>'
            in text
        )

    def test_title_keeps_its_markdown(self, tmp_path: Path):
        """Preserve code and emphasis in page title links"""
        config, _ = _project(tmp_path)
        page = _page("p.qmd", "Python", title="Using `config` and *more*")

        text = tags.render_index({"Python": [page]}, config)

        assert "[Using `config` and *more*](../p.qmd)" in text

    def test_closing_bracket_in_title_keeps_the_link(self, tmp_path: Path):
        """Escape a closing bracket so it cannot end the page title link"""
        config, _ = _project(tmp_path)
        page = _page("p.qmd", "Python", title="Odd ] title")

        text = tags.render_index({"Python": [page]}, config)

        assert r"[Odd \] title](../p.qmd)" in text

    def test_code_span_in_title_is_left_as_written(self, tmp_path: Path):
        """Preserve literal code spans while escaping the surrounding title text"""
        config, _ = _project(tmp_path)
        page = _page("p.qmd", "Python", title="Index `a[0] < b` with [x] & <y>")

        text = tags.render_index({"Python": [page]}, config)

        assert r"[Index `a[0] < b` with \[x\] &amp; &lt;y&gt;](../p.qmd)" in text

    def test_nested_tag_names_are_text(self, tmp_path: Path):
        """Escape both segments of a nested tag pill"""
        config, _ = _project(tmp_path)

        text = tags.render_index({"<a>/b_c_": [_page("p.qmd", "<a>/b_c_")]}, config)

        assert r'gd-tag-pill-parent">&lt;a&gt;</span>' in text
        assert r'<span class="gd-tag-pill-segment">b\_c\_</span>' in text

    def test_unknown_icon_is_left_out(self, tmp_path: Path):
        """Render the tag without an icon when its configured icon is unknown"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  icons:\n    Python: no-such\n")

        text = tags.render_index({"Python": [_page("p.qmd", "Python")]}, config)

        assert "<svg" not in text


# ── Page data ────────────────────────────────────────────────────────────────


def _data(config: Config, pages: list[tags.TaggedPage]) -> tuple[dict[str, Any], list[str]]:
    """
    Build page data and collect reported warnings

    Parameters
    ----------
    config
        The configuration.
    pages
        The tagged pages.

    Returns
    -------
    :
        The page data and the warnings reported while building it.
    """
    reported: list[str] = []
    data = tags.page_data(pages, tags.group(pages), config, report=reported.append)
    return data, reported


class TestPageData:
    def test_tags_and_tooltip_counts(self, tmp_path: Path):
        """Include page tags, page counts, sections and translated tooltip templates"""
        config, _ = _project(tmp_path, "tags:\n  enabled: true\n  location: bottom\n")
        intro = _page("user-guide/intro.qmd", "Python", "API")
        recipe = _page("recipes/r.qmd", "Python", section="Recipes")

        data, _ = _data(config, [intro, recipe])

        assert data["page_tags"] == {
            "user-guide/intro.qmd": ["Python", "API"],
            "recipes/r.qmd": ["Python"],
        }
        assert data["tag_meta"]["Python"] == {"count": 2, "sections": ["Recipes", "User Guide"]}
        assert data["default_location"] == "bottom"
        assert data["hierarchical"] is True
        assert data["tooltip_templates"]["one"]

    def test_shadow_only_page_has_no_pills(self, tmp_path: Path):
        """Keep an empty tag list for pages that have only shadow tags"""
        config, _ = _project(tmp_path)
        hidden = tags.TaggedPage("hidden.qmd", "Hidden", "", (), shadowed=True, location=None)

        data, _ = _data(config, [_page("p.qmd", "Python"), hidden])

        assert data["page_tags"] == {"p.qmd": ["Python"], "hidden.qmd": []}

    def test_shadow_tags_keep_configured_order_without_duplicates(self, tmp_path: Path):
        """Deduplicate shadow tags while preserving their configured order"""
        configured = ["zeta", "alpha", "mu", "beta", "omega", "gamma", "pi", "delta", "kappa"]
        shadow = "".join(f"    - {tag}\n" for tag in [*configured, "alpha", "zeta"])
        config, _ = _project(tmp_path, f"tags:\n  enabled: true\n  shadow:\n{shadow}")

        data, _ = _data(config, [])

        assert data["shadow"] == configured

    def test_location_overrides(self, tmp_path: Path):
        """Record pill placement only for pages with an override"""
        config, _ = _project(tmp_path)
        page = tags.TaggedPage("a.qmd", "A", "", ("Python",), shadowed=False, location="top")

        data, _ = _data(config, [page, _page("b.qmd", "Python")])

        assert data["page_tag_locations"] == {"a.qmd": "top"}

    def test_icons_resolve_to_svg_and_unknown_icons_are_reported(self, tmp_path: Path):
        """Resolve known icons to SVG and report unknown icon names"""
        config, _ = _project(
            tmp_path, "tags:\n  enabled: true\n  icons:\n    Python: code\n    Bad: no-such\n"
        )

        data, reported = _data(config, [])

        assert list(data["icons"]) == ["Python"]
        assert "gd-tag-icon-svg" in data["icons"]["Python"]
        assert reported == ["Warning: Unknown tag icon 'no-such' for tag 'Bad'"]


# ── Pill links ───────────────────────────────────────────────────────────────

_PAGE_TAGS_JS = Path(__file__).resolve().parents[1] / "great_docs" / "assets" / "page-tags.js"

# Runs `page-tags.js` once for each page path with just enough of a DOM to render
# the pills, and prints the `href` of each pill
_PILL_HREFS_JS = r"""
const fs = require('fs');
const vm = require('vm');
const [scriptPath, dataJson, pathsJson] = process.argv.slice(1);
const source = fs.readFileSync(scriptPath, 'utf8');
const hrefs = {};
for (const pathname of JSON.parse(pathsJson)) {
  const pills = [];
  const element = (tag) => {
    const el = {
      classList: { add() {}, contains: () => false },
      setAttribute() {},
      appendChild() {},
    };
    if (tag === 'a') pills.push(el);
    return el;
  };
  const title = { nextElementSibling: null, nextSibling: null, parentNode: element('div') };
  const document = {
    readyState: 'complete',
    querySelector: (selector) => (selector.includes('h1') ? title : null),
    createElement: element,
  };
  const window = { __GD_TAGS_DATA__: JSON.parse(dataJson), location: { pathname } };
  vm.runInNewContext(source, { window, document });
  hrefs[pathname] = pills.map((pill) => pill.href);
}
process.stdout.write(JSON.stringify(hrefs));
"""


def _pill_hrefs(data: dict[str, Any], hrefs: list[str]) -> dict[str, list[str]]:
    """
    Render the tag pills of pages at the site root with `page-tags.js`

    Parameters
    ----------
    data
        The tag pill data.
    hrefs
        The pages' source paths, such as `p.qmd`.

    Returns
    -------
    :
        The link of each pill on each page, by the page's source path.
    """
    paths = ["/" + href.removesuffix(".qmd") + ".html" for href in hrefs]
    result = subprocess.run(
        ["node", "-e", _PILL_HREFS_JS, str(_PAGE_TAGS_JS), json.dumps(data), json.dumps(paths)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    by_path: dict[str, list[str]] = json.loads(result.stdout)
    return {href: by_path[path] for href, path in zip(hrefs, paths, strict=True)}


def _listed_pages(index: str) -> dict[str, list[str]]:
    """
    Find the pages listed under each heading of the index page

    Parameters
    ----------
    index
        The index page source.

    Returns
    -------
    :
        The link targets of the pages that follow each heading, by the heading's id.
    """
    listed: dict[str, list[str]] = {}
    current: list[str] = []
    for line in index.splitlines():
        if "gd-tag-heading" in line:
            match = re.search(r'\bid="([^"]*)"', line)
            current = listed.setdefault(match.group(1), []) if match else []
        elif link := re.search(r'gd-tag-page-link">\[.*\]\(([^)]*)\)', line):
            current.append(link.group(1))
    return listed


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize("hierarchical", [True, False])
def test_pill_links_to_the_heading_that_lists_its_page(tmp_path: Path, hierarchical: bool):
    """Link each tag pill to the index heading under which its page is listed"""
    config, _ = _project(
        tmp_path, f"tags:\n  enabled: true\n  hierarchical: {str(hierarchical).lower()}\n"
    )
    names = ["Python", "Python/Advanced", r"AI\/LLM", "AI/LLM", "Données", "日本語", "C++", "C"]
    pages = [_page(f"p{i}.qmd", name) for i, name in enumerate(names)]
    data, _ = _data(config, pages)
    listed = _listed_pages(tags.render_index(tags.group(pages), config))

    pill_hrefs = _pill_hrefs(data, [page.href for page in pages])

    for page in pages:
        [href] = pill_hrefs[page.href]
        target, _, fragment = href.partition("#")
        assert target == "tags/index.html"
        assert f"../{page.href}" in listed.get(fragment, []), (page.tags, href)


# ── Writing ──────────────────────────────────────────────────────────────────


class TestWrite:
    def test_writes_index_page_and_data(self, tmp_path: Path):
        """Write the index page and the same tag data returned to the caller"""
        config, layout = _project(tmp_path)
        _make_qmd(layout.build_dir / "user-guide" / "page.qmd", "Page", tags=["Python"])
        reported: list[str] = []

        output = tags.write(config, layout, report=reported.append)

        assert output is not None
        assert (layout.build_dir / "tags" / "index.qmd").exists()
        written = json.loads((layout.build_dir / "_tags.json").read_text(encoding="utf-8"))
        assert written == output.page_data
        assert reported == ["Created tags/index.qmd"]
        assert output.contribution == Contribution(
            navbar=(NavbarLink("Tags", "tags/index.qmd", before="reference/index.qmd"),)
        )

    def test_nothing_without_tagged_pages(self, tmp_path: Path):
        """Leave the build directory unchanged when no pages have tags"""
        config, layout = _project(tmp_path)
        _make_qmd(layout.build_dir / "user-guide" / "page.qmd", "Page")

        assert tags.write(config, layout, report=print) is None
        assert sorted(p.name for p in layout.build_dir.iterdir()) == ["user-guide"]

    def test_index_page_disabled(self, tmp_path: Path):
        """Write page data without creating a disabled index page"""
        config, layout = _project(tmp_path, "tags:\n  enabled: true\n  index_page: false\n")
        _make_qmd(layout.build_dir / "user-guide" / "page.qmd", "Page", tags=["Python"])

        output = tags.write(config, layout, report=print)

        assert output is not None
        assert output.page_data is not None
        assert not (layout.build_dir / "tags").exists()
        assert output.contribution == Contribution()

    def test_not_shown_on_pages(self, tmp_path: Path):
        """Write the index without page data when tag pills are disabled"""
        config, layout = _project(tmp_path, "tags:\n  enabled: true\n  show_on_pages: false\n")
        _make_qmd(layout.build_dir / "user-guide" / "page.qmd", "Page", tags=["Python"])

        output = tags.write(config, layout, report=print)

        assert output is not None
        assert output.page_data is None
        assert (layout.build_dir / "tags" / "index.qmd").exists()
        assert not (layout.build_dir / "_tags.json").exists()


# ── Inline data ──────────────────────────────────────────────────────────────


class TestInlineData:
    def test_inserts_before_the_reading_script(self):
        """Embed data before its consuming script and escape closing tag sequences"""
        entries: list[Any] = ["first.html", {"text": "page-tags.js"}]
        quarto_config: dict[str, Any] = {"format": {"html": {"include-after-body": entries}}}

        inline_data.add(quarto_config, "__GD_X__", {"svg": "</svg>"}, before="page-tags.js")

        assert entries == [
            "first.html",
            {"text": '<script>window.__GD_X__={"svg": "<\\/svg>"};</script>'},
            {"text": "page-tags.js"},
        ]

    def test_appends_and_wraps_a_single_entry(self):
        """Preserve a single include while appending data without a matching script"""
        quarto_config: dict[str, Any] = {"format": {"html": {"include-after-body": "only.html"}}}

        inline_data.add(quarto_config, "__GD_X__", {}, before="page-tags.js")

        assert quarto_config["format"]["html"]["include-after-body"] == [
            "only.html",
            {"text": "<script>window.__GD_X__={};</script>"},
        ]

    def test_keeps_an_earlier_assignment(self):
        """Keep the first assignment when the same global is added twice"""
        quarto_config: dict[str, Any] = {}

        inline_data.add(quarto_config, "__GD_X__", {"n": 1}, before="page-tags.js")
        inline_data.add(quarto_config, "__GD_X__", {"n": 2}, before="page-tags.js")

        assert quarto_config["format"]["html"]["include-after-body"] == [
            {"text": '<script>window.__GD_X__={"n": 1};</script>'}
        ]


# ── Build step ───────────────────────────────────────────────────────────────


REFERENCE = {"text": "Reference", "href": "reference/index.qmd"}


def _docs(tmp_path: Path, yaml_text: str = "tags: true\n") -> GreatDocs:
    """
    Create a project whose build directory has the initial Quarto configuration

    Parameters
    ----------
    tmp_path
        The project directory.
    yaml_text
        The contents of `great-docs.yml`.

    Returns
    -------
    :
        The project, with `page-tags.js` as its only after-body include and a Reference
        link in the left navbar.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n', encoding="utf-8")
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir()
    quarto_yml.write_initial(docs.build_dir)
    with quarto_yml.edit(docs.build_dir) as quarto_config:
        quarto_config["format"]["html"]["include-after-body"] = ["page-tags.js"]
        quarto_config["website"] = {"navbar": {"left": [REFERENCE]}}
    return docs


class TestStepTags:
    def test_embeds_the_page_data(self, tmp_path: Path):
        """Embed tag data before its script and preserve the generated configuration header"""
        docs = _docs(tmp_path)
        _make_qmd(docs.build_dir / "user-guide" / "page.qmd", "Page", tags=["Python"])

        assert docs._step_tags() == "Tags processed"

        entries = quarto_yml.read(docs.build_dir)["format"]["html"]["include-after-body"]
        assert entries[0]["text"].startswith("<script>window.__GD_TAGS_DATA__=")
        assert entries[1] == "page-tags.js"
        validate_build_dir(docs.build_dir)

    def test_links_the_index_page_before_reference(self, tmp_path: Path):
        """Insert one translated Tags link before Reference across repeated builds"""
        docs = _docs(tmp_path, "tags: true\nsite:\n  lang: fr\n")
        _make_qmd(docs.build_dir / "user-guide" / "page.qmd", "Page", tags=["Python"])

        _ = docs._step_tags()
        _ = docs._step_tags()

        left = quarto_yml.read(docs.build_dir)["website"]["navbar"]["left"]
        assert left == [{"text": "Étiquettes", "href": "tags/index.qmd"}, REFERENCE]

    def test_skips_without_tagged_pages(self, tmp_path: Path):
        """Report a skipped step when the project has no tagged pages"""
        assert _docs(tmp_path)._step_tags() == Skipped("no tagged pages found")

    def test_skips_when_disabled(self, tmp_path: Path):
        """Report a skipped step when tags are disabled"""
        assert _docs(tmp_path, "tags: false\n")._step_tags() == Skipped("tags not enabled")
