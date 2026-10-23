"""
Markdown companion pages and their alternate links in Quarto output
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_EXTENSION = (
    Path(__file__).parent.parent / "great_docs" / "assets" / "_extensions" / "markdown-pages"
)

pytestmark = pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")

_QUARTO_YML = """\
project:
  type: website
format:
  html:
    shift-heading-level-by: -1
{filters}website:
  title: EnvelopeSiteTitle
  navbar:
    left:
      - text: NavbarOnlyText
        href: index.qmd
"""

_GUIDE_PAGE = """\
---
title: Guide page
html-table-processing: none
---

::: {.callout-tip title="Mind the gap"}
Tip body.
:::

::: {.callout-note title="Added in version 2.0"}
:::

::: {.panel-tabset}
## First tab

First body.

## Second tab

Second body.
:::

Press `<kbd>Esc</kbd>`{=html} to cancel.

Term `<code>`{=html}[FAILURE]{.name}[=]{.op}[\"failure\"]{.value}`</code>`{=html} here.

```{=html}
<table><tr><th>Key</th><th>Value</th></tr><tr><td>a</td><td>1</td></tr></table>
```

<table data-quarto-disable-processing="true">
<tr><th>Inline</th><th>Table</th></tr>
<tr><td><code>x</code></td><td>2</td></tr>
</table>

+------+----------+
| Cell | Content  |
+======+==========+
| one  | - item a |
|      | - item b |
+------+----------+
| two  | ******** |
+------+----------+

::: {.cell-output-display}
```{=html}
<script>console.log(1)</script>
```
:::

See [page a](../reference/a.qmd) and [section b](../reference/b.html#part).

“Curly” and ‘single’ quotes, an en – dash and an em — dash.
"""

_PAGES = {
    "index.qmd": (
        '---\ntitle: ""\n---\n\n'
        "::: {.column-margin .gd-homepage-sidebar}\nSidebarOnlyText\n:::\n\nHome text.\n"
    ),
    "reference/a.qmd": "---\ntitle: Page *A*\n---\n\nA text.\n",
    "reference/b.qmd": "---\ntitle: Page B\n---\n\n## Part\n\nB text.\n",
    "guide/page.qmd": _GUIDE_PAGE,
    "guide/repeated.qmd": "---\ntitle: Repeated\n---\n\n# Repeated\n\nText.\n\n## Part\n",
    "guide/renamed.qmd": "---\ntitle: Front matter\n---\n\n# Body heading\n\nText.\n",
    "guide/draft.qmd": "---\ntitle: Draft\ndraft: true\n---\n\nDraft text.\n",
    "404.qmd": "---\ntitle: Not found\n---\n\nMissing.\n",
}

_COMPANIONS = [
    "index.md",
    "reference/a.md",
    "reference/b.md",
    "guide/page.md",
    "guide/repeated.md",
    "guide/renamed.md",
]

_ALTERNATE = re.compile(r'<link rel="alternate" type="text/markdown" href="([^"]*)">')


def _render_site(root: Path, *, with_filter: bool) -> Path:
    """
    Render the test website and return its output directory
    """
    root.mkdir(parents=True)
    filters = ""
    if with_filter:
        shutil.copytree(_EXTENSION, root / "_extensions" / "markdown-pages")
        filters = "filters:\n  - markdown-pages\n"
    (root / "_quarto.yml").write_text(_QUARTO_YML.format(filters=filters), encoding="utf-8")
    for name, text in _PAGES.items():
        page = root / name
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8")
    subprocess.run(["quarto", "render"], cwd=root, check=True, capture_output=True)
    return root / "_site"


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _render_site(tmp_path_factory.mktemp("with") / "proj", with_filter=True)


@pytest.fixture(scope="module")
def plain_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _render_site(tmp_path_factory.mktemp("without") / "proj", with_filter=False)


@pytest.fixture(scope="module")
def guide(site: Path) -> str:
    return (site / "guide" / "page.md").read_text(encoding="utf-8")


def test_every_rendered_page_has_a_companion(site: Path):
    # A full render cleans `_site`, so `reference/a` and `reference/b` include
    # the first page written into a fresh subdirectory
    assert sorted(p.relative_to(site).as_posix() for p in site.rglob("*.md")) == sorted(_COMPANIONS)


@pytest.mark.parametrize("companion", _COMPANIONS)
def test_page_links_to_its_companion_once(site: Path, companion: str):
    page = (site / companion).with_suffix(".html")
    assert _ALTERNATE.findall(page.read_text(encoding="utf-8")) == [Path(companion).name]


@pytest.mark.parametrize("page", ["404.html", "guide/draft.html"])
def test_excluded_pages_have_no_companion(site: Path, page: str):
    assert not (site / page).with_suffix(".md").exists()


@pytest.mark.parametrize("page", ["404.html", "guide/draft.html"])
def test_excluded_pages_have_no_alternate_link(site: Path, page: str):
    html = site / page
    if html.exists():
        assert _ALTERNATE.findall(html.read_text(encoding="utf-8")) == []


def test_companion_opens_with_the_page_title(guide: str):
    assert guide.startswith("# Guide page\n")


def test_page_title_keeps_inline_formatting(site: Path):
    assert (site / "reference/a.md").read_text(encoding="utf-8").startswith("# Page *A*\n")


def test_leading_heading_matching_the_title_is_not_repeated(site: Path):
    companion = (site / "guide/repeated.md").read_text(encoding="utf-8")
    assert companion.startswith("# Repeated\n\nText.\n\n## Part\n")


def test_leading_heading_replaces_the_title(site: Path):
    # `shift-heading-level-by: -1` makes the page heading the HTML title
    companion = (site / "guide/renamed.md").read_text(encoding="utf-8")
    assert companion.startswith("# Body heading\n\nText.")
    assert "Front matter" not in companion


def test_untitled_page_opens_with_its_content(site: Path):
    assert (site / "index.md").read_text(encoding="utf-8").startswith("Home text.")


def test_homepage_sidebar_is_dropped(site: Path):
    assert "SidebarOnlyText" not in (site / "index.md").read_text(encoding="utf-8")


def test_callout_keeps_its_title_and_body(guide: str):
    assert "> **Tip: Mind the gap**\n>\n> Tip body." in guide


def test_empty_callout_keeps_its_title(guide: str):
    assert "> **Note: Added in version 2.0**" in guide


def test_tabs_become_titled_sections(guide: str):
    assert "**First tab**\n\nFirst body.\n\n**Second tab**\n\nSecond body." in guide


def test_raw_html_inline_keeps_its_text(guide):
    # Shortcodes such as `keys` return a whole element as one raw inline
    assert "Press Esc to cancel." in guide


def test_raw_code_run_becomes_one_code_span(guide: str):
    assert 'Term `FAILURE="failure"` here.' in guide


def test_raw_html_table_becomes_a_pipe_table(guide: str):
    assert re.search(r"^\| Key +\| Value +\|$", guide, re.MULTILINE)
    assert re.search(r"^\| a +\| 1 +\|$", guide, re.MULTILINE)


def test_split_html_table_becomes_a_pipe_table(guide: str):
    # Markdown reads an HTML table written in a page as one raw block per tag
    assert re.search(r"^\| Inline +\| Table +\|$", guide, re.MULTILINE)
    assert re.search(r"^\| `x` +\| 2 +\|$", guide, re.MULTILINE)


def test_block_content_in_a_cell_keeps_a_pipe_table(guide: str):
    assert "[TABLE]" not in guide
    assert re.search(r"^\| one +\| item a item b +\|$", guide, re.MULTILINE)


def test_cell_with_only_removed_content_becomes_empty(guide: str):
    assert re.search(r"^\| two +\| +\|$", guide, re.MULTILINE)


def test_empty_cell_output_becomes_a_placeholder(guide: str):
    assert "*\\[Rich HTML output -- view on the documentation site\\]*" in guide
    assert "console.log" not in guide


def test_page_links_point_at_companions(guide: str):
    assert "[page a](../reference/a.md)" in guide
    assert "[section b](../reference/b.md#part)" in guide


def test_quotes_and_dashes_are_ascii(guide: str):
    assert "\"Curly\" and 'single' quotes, an en - dash and an em -- dash." in guide


def test_no_navigation_envelope_text(site: Path):
    for companion in _COMPANIONS:
        text = (site / companion).read_text(encoding="utf-8")
        assert "EnvelopeSiteTitle" not in text
        assert "NavbarOnlyText" not in text


def test_html_matches_a_render_without_the_filter(site: Path, plain_site: Path):
    pages = sorted(p.relative_to(plain_site) for p in plain_site.rglob("*.html"))
    assert pages == sorted(p.relative_to(site) for p in site.rglob("*.html"))
    for page in pages:
        with_filter = re.sub((_ALTERNATE.pattern + r"\n").encode(), b"", (site / page).read_bytes())
        assert with_filter == (plain_site / page).read_bytes(), page
