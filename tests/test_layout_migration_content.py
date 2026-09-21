import io
from pathlib import Path

import pytest
from yaml12 import read_yaml

from great_docs._layout_migration.content import (
    ContentDirectory,
    _locate,
    rewrite_config,
    rewrite_document,
)
from great_docs._layout_migration.model import MigrationError, Move


def test_rebase_preserves_yaml_comment(tmp_path: Path) -> None:
    original = "# Shared citations\nbibliography: refs.bib  # Keep here\n"
    assert rewrite_config(original, (), tmp_path, tmp_path / "docs") == (
        "# Shared citations\nbibliography: ../refs.bib  # Keep here\n"
    )


@pytest.mark.parametrize("destination", ["docs", "website/reference"])
def test_config_changes_only_path_spans(tmp_path: Path, destination: str) -> None:
    text = (
        "# Citations café\r\nbibliography: ['refs.bib', \"other.bib\"] # Keep\r\n"
        "csl: 'style.csl'\r\nuser_guide: guides\r\n"
        "sections: [{dir: essays, title: Essays}]\r\n"
        "custom_pages: [{dir: pages, output: info}]\r\n"
        "site: {css: [theme.css, 'https://example.org/style.css'], toc: true}\r\n"
        "source: {path: src/pkg}\r\nrepo: https://example.org/repo\r\n"
    )
    dest = tmp_path / destination
    moves = tuple(Move(tmp_path / name, dest / name) for name in ("guides", "essays", "pages"))
    result = rewrite_config(text, moves, tmp_path, dest)
    prefix = "../" * len(Path(destination).parts)
    expected = text
    for path in ("refs.bib", "other.bib", "style.csl", "theme.css"):
        expected = expected.replace(path, prefix + path)
    assert result == expected


def test_config_preserves_guide_ordering_and_url_fields(tmp_path: Path) -> None:
    text = (
        "user_guide:\n  - title: Start\n    contents:\n      - href: intro.qmd\n"
        "logo: {light: logo.svg, href: ../home, show_title: false}\n"
        "hero: {logo: false}\nfavicon: https://example.org/icon.png\n"
        "custom_pages: false\nsite_url: https://example.org\n"
        "announcement: {url: local.html}\nrobots: {disallow: [/secret]}\n"
    )
    assert rewrite_config(text, (), tmp_path, tmp_path / "docs") == text.replace(
        "light: logo.svg", "light: ../logo.svg"
    )


@pytest.mark.parametrize(
    "field",
    [
        "pre_render: script.py",
        "freeze: {pre_render: [script.py]}",
        "include_in_header: [{file: script.py}, {text: literal}]",
        "skill: {file: script.py, extra_body: script.py, skills: [{file: script.py}]}",
        "favicon: {icon: script.py, apple_touch: script.py, og_image: script.py}",
        "hero: {logo: {dark: script.py}}",
        "social_cards: {image: script.py}",
        "authors: [{name: Ada, image: script.py}]",
        "team_author: {image: script.py}",
        "custom_pages: [script.py, {dir: script.py, output: keep}]",
    ],
)
def test_all_documented_path_forms(tmp_path: Path, field: str) -> None:
    assert rewrite_config(field, (), tmp_path, tmp_path / "docs") == field.replace(
        "script.py", "../script.py"
    )


@pytest.mark.parametrize(
    "text",
    [
        "bibliography: &refs refs.bib\nother: *refs\n",
        "other: &refs refs.bib\nbibliography: *refs\n",
        "site: &style {css: theme.css}\nother: *style\n",
        "bibliography: !!str refs.bib\n",
        "bibliography: |\n  refs.bib\n",
        "bibliography: refs.bib\nbibliography: other.bib\n",
        "? [complex, key]\n: value\n",
        "bibliography: refs.bib\n---\ncsl: style.csl\n",
    ],
)
def test_rejects_unsafe_yaml_spans(tmp_path: Path, text: str) -> None:
    with pytest.raises(MigrationError):
        rewrite_config(text, (), tmp_path, tmp_path / "docs")


def test_replacement_quotes_yaml_indicators(tmp_path: Path) -> None:
    dest = tmp_path / "docs"
    moves = (Move(tmp_path / "refs.bib", dest / "x: #refs.bib"),)
    result = rewrite_config("bibliography: refs.bib # End\n", moves, tmp_path, dest)
    assert read_yaml(io.StringIO(result)) == {"bibliography": "x: #refs.bib"}
    assert result.endswith(" # End\n")


def test_markdown_preserves_examples_titles_and_fragments(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (tmp_path / "image name.png").write_bytes(b"image")
    (guide / "next.qmd").write_text("# Next\n")
    path = guide / "page.qmd"
    text = (
        "![A](<../image name.png?size=2#top> 'Title')\r\n"
        "[Next](next.qmd#part) and [web](https://example.org) and [here](#part)\r\n"
        '[image]: ../image%20name.png "Caption"\r\n'
        "`[example](../missing.png)`\r\n"
        "~~~markdown\r\n![sample](../missing.png)\r\n~~~\r\n"
        "\r\n    ![indented](../missing.png)\r\n"
    )
    result, inputs, follow_up, blockers = rewrite_document(
        text, path, (Move(guide, tmp_path / "docs/user_guide"),)
    )
    assert result == text.replace("../image", "../../image")
    assert tmp_path / "image name.png" in inputs
    assert not follow_up
    assert not blockers


def test_static_html_and_unrecognised_dynamic_references(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    (tmp_path / "logo.svg").write_text("<svg/>")
    text = '<img src="logo.svg#x">\n{{< include extra.qmd >}}\n```{python}\nopen("x")\n```\n'
    result, inputs, follow_up, blockers = rewrite_document(
        text, page, (Move(page, tmp_path / "docs/index.qmd"),)
    )
    assert result.startswith('<img src="../logo.svg#x">')
    assert tmp_path / "logo.svg" in inputs
    assert any("dynamic" in message.lower() for message in follow_up)
    assert any("include" in message.lower() for message in blockers)


def test_include_reference_inside_fenced_example_is_not_a_blocker(tmp_path: Path) -> None:
    text = (
        "Use the include shortcode like this:\n\n"
        "```markdown{shortcodes=false}\n{{< include src/mypackage/examples/demo.py >}}\n```\n"
    )
    _, _, follow_up, blockers = rewrite_document(
        text, tmp_path / "index.qmd", (Move(tmp_path / "index.qmd", tmp_path / "docs/index.qmd"),)
    )
    assert not follow_up
    assert not blockers


def test_include_reference_inside_raw_html_fence_is_still_checked(tmp_path: Path) -> None:
    text = "```{=html}\n{{< include missing.qmd >}}\n```\n"
    _, _, _, blockers = rewrite_document(
        text, tmp_path / "index.qmd", (Move(tmp_path / "index.qmd", tmp_path / "docs/index.qmd"),)
    )
    assert any("missing.qmd" in message for message in blockers)


def test_include_reference_to_untouched_file_is_rewritten_not_blocked(tmp_path: Path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n")
    guide = tmp_path / "user_guide"
    guide.mkdir()
    page = guide / "page.qmd"
    page.write_text("{{< include ../CONTRIBUTING.md >}}\n")
    result, inputs, _, blockers = rewrite_document(
        page.read_text(), page, (Move(guide, tmp_path / "docs/user_guide"),)
    )
    assert not blockers
    assert tmp_path / "CONTRIBUTING.md" in inputs
    assert result == "{{< include ../../CONTRIBUTING.md >}}\n"


def test_broken_static_target_blocks(tmp_path: Path) -> None:
    page = tmp_path / "index.md"
    _, _, _, blockers = rewrite_document(
        "![Missing](missing.png)", page, (Move(page, tmp_path / "docs/index.md"),)
    )
    assert any("missing.png" in message for message in blockers)


def test_moved_link_target_is_rebased_for_retained_page(tmp_path: Path) -> None:
    guide = tmp_path / "guide"
    guide.mkdir()
    (guide / "page.md").write_text("# Page")
    result, _, _, blockers = rewrite_document(
        "[Page](guide/page.md)", tmp_path / "README.md", (Move(guide, tmp_path / "docs/guide"),)
    )
    assert result == "[Page](docs/guide/page.md)"
    assert not blockers


def test_config_paths_are_literal_filesystem_names(tmp_path: Path) -> None:
    text = "bibliography: 'refs#part%20one.bib'\n"
    assert rewrite_config(text, (), tmp_path, tmp_path / "docs") == (
        "bibliography: '../refs#part%20one.bib'\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "# Configuration\n",
        "---\nmodule: sample\n...\n",
        "module: sample\nhero: {}\n",
        "hero: null # Auto\n",
        "hero:\n  tagline: Simple\nmodule: sample\n",
    ],
)
def test_implicit_input_insertions_preserve_other_yaml(tmp_path: Path, text: str) -> None:
    from great_docs._layout_migration.content import set_config_values

    expected = read_yaml(io.StringIO(text)) or {}
    hero = expected.get("hero") or {}
    hero["logo"] = {"light": "logo.svg", "dark": "logo.svg"}
    expected["hero"] = hero
    result = set_config_values(text, {("hero", "logo"): {"light": "logo.svg", "dark": "logo.svg"}})
    assert read_yaml(io.StringIO(result)) == expected
    if "# Auto" in text:
        assert "# Auto" in result


def test_link_to_html_resolves_a_moved_quarto_source(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "next.qmd").write_text("# Next")
    result, _, _, blockers = rewrite_document(
        "[Next](user_guide/next.html#part)",
        tmp_path / "README.md",
        (Move(guide, tmp_path / "docs/user_guide"),),
    )
    assert result == "[Next](docs/user_guide/next.html#part)"
    assert not blockers


@pytest.mark.parametrize(
    "reference",
    [
        "reference/sample.api.html",
        "reference/sample.api.qmd",
        "../reference/sample.api.qmd",
        "../../reference/sample.api.html",
    ],
)
def test_generated_reference_page_keeps_published_identity(tmp_path: Path, reference: str) -> None:
    page = tmp_path / "user_guide/page.qmd"
    text = f"[API]({reference}?view=full#usage)"
    result, inputs, _, blockers = rewrite_document(
        text, page, (Move(page.parent, tmp_path / "docs/user_guide"),)
    )
    assert result == text
    assert not inputs
    assert not blockers


@pytest.mark.parametrize(
    "reference",
    [
        "reference/missing.png",
        "elsewhere/missing.html",
        "elsewhere/missing.qmd",
        "images/reference/missing.html",
    ],
)
def test_generated_page_recognition_keeps_missing_input_checks(
    tmp_path: Path, reference: str
) -> None:
    page = tmp_path / "index.qmd"
    _, _, _, blockers = rewrite_document(
        f"[Missing]({reference})", page, (Move(page, tmp_path / "docs/index.qmd"),)
    )
    assert any(reference in message for message in blockers)


def test_numeric_prefix_reference_resolves_across_the_move(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "00-introduction.qmd").write_text("[Install](installation.qmd)")
    (guide / "01-installation.qmd").write_text("# Installation")
    content_directories = (ContentDirectory(guide, "user-guide", True),)
    result, inputs, _, blockers = rewrite_document(
        (guide / "00-introduction.qmd").read_text(),
        guide / "00-introduction.qmd",
        (Move(guide, tmp_path / "docs/user_guide"),),
        content_directories=content_directories,
    )
    assert not blockers
    assert guide / "01-installation.qmd" in inputs
    assert result == "[Install](installation.qmd)"


def test_explicit_user_guide_ordering_does_not_strip_prefixes(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "00-introduction.qmd").write_text("[Install](installation.qmd)")
    (guide / "01-installation.qmd").write_text("# Installation")
    content_directories = (ContentDirectory(guide, "user-guide", False),)
    _, _, _, blockers = rewrite_document(
        (guide / "00-introduction.qmd").read_text(),
        guide / "00-introduction.qmd",
        (Move(guide, tmp_path / "docs/user_guide"),),
        content_directories=content_directories,
    )
    assert any("installation.qmd" in message for message in blockers)


def test_renamed_directory_html_reference_resolves(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "11-theming.qmd").write_text("# Theming")
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "06-choose-gradient-theme.qmd").write_text("[Theming](../user-guide/theming.html)")
    content_directories = (ContentDirectory(guide, "user-guide", True),)
    result, inputs, _, blockers = rewrite_document(
        (recipes / "06-choose-gradient-theme.qmd").read_text(),
        recipes / "06-choose-gradient-theme.qmd",
        (
            Move(guide, tmp_path / "docs/user_guide"),
            Move(recipes, tmp_path / "docs/recipes"),
        ),
        content_directories=content_directories,
    )
    assert not blockers
    assert guide / "11-theming.qmd" in inputs
    assert result == "[Theming](../user-guide/theming.html)"


def test_numeric_prefix_reference_resolves_across_nested_directories(tmp_path: Path) -> None:
    guide = tmp_path / "user_guide"
    (guide / "02-advanced").mkdir(parents=True)
    (guide / "02-advanced/03-tips.qmd").write_text("# Tips")
    page = guide / "00-intro.qmd"
    page.write_text("[Tips](advanced/tips.qmd)")
    content_directories = (ContentDirectory(guide, "user-guide", True),)
    result, inputs, _, blockers = rewrite_document(
        page.read_text(),
        page,
        (Move(guide, tmp_path / "docs/user_guide"),),
        content_directories=content_directories,
    )
    assert not blockers
    assert guide / "02-advanced/03-tips.qmd" in inputs
    assert result == "[Tips](advanced/tips.qmd)"


def test_locate_finds_the_first_line() -> None:
    assert _locate("first\nsecond\n", 2) == (1, "first")


def test_locate_finds_a_middle_line() -> None:
    text = "first\nsecond\nthird\n"
    assert _locate(text, text.index("second") + 3) == (2, "second")


def test_locate_finds_the_last_line_without_a_trailing_newline() -> None:
    text = "first\nsecond"
    assert _locate(text, text.index("second")) == (2, "second")


def test_locate_handles_crlf_line_endings() -> None:
    text = "first\r\nsecond\r\n"
    assert _locate(text, text.index("second")) == (2, "second\r")


def test_dynamic_reference_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = "before\n![Chart](${base}/chart.png)\n"
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(
        n
        for n in follow_up
        if n.category == "Dynamic References to Review" and "reference" in n.lower()
    )
    assert note.path == page
    assert note.line == 2
    assert note.snippet == "![Chart](${base}/chart.png)"


def test_unsupported_html_reference_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = 'before\n<img src="a.png" srcset="a.png 1x, b.png 2x">\n'
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in follow_up if n.category == "HTML Attributes to Update Manually")
    assert note.path == page
    assert note.line == 2
    assert "srcset" in note.snippet


def test_plain_style_attribute_is_not_flagged(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = 'before\n<div style="color: red; font-weight: bold;">text</div>\n'
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    assert not any(n.category == "HTML Attributes to Update Manually" for n in follow_up)


def test_style_with_url_is_flagged(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = 'before\n<div style="background: url(bg.png);">text</div>\n'
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in follow_up if n.category == "HTML Attributes to Update Manually")
    assert "url(bg.png)" in note.snippet


def test_dynamic_code_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = 'text\n```{python}\nopen("x")\n```\n'
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in follow_up if n.category == "Code Blocks to Verify")
    assert note.line == 2
    assert note.snippet == "```{python}"


def test_shortcode_note_has_a_category_and_first_occurrence_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = "intro\n{{< video demo.mp4 >}}\n"
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in follow_up if n.category == "Shortcodes to Check")
    assert note.line == 2
    assert note.snippet == "{{< video demo.mp4 >}}"


def test_non_file_shortcode_is_not_flagged(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = "intro\n{{< meta title >}}\n{{< kbd Ctrl-C >}}\n{{< pagebreak >}}\n"
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    assert not any(n.category == "Shortcodes to Check" for n in follow_up)


def test_include_shortcode_alone_does_not_duplicate_into_generic_review(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = "intro\n{{< include extra.qmd >}}\n"
    (page.parent / "extra.qmd").write_text("# Extra\n")
    _, _, follow_up, _ = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    assert not any(n.category == "Shortcodes to Check" for n in follow_up)


def test_include_reference_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    text = "notes\n{{< include missing.qmd >}}\n"
    _, _, _, blockers = rewrite_document(
        text, tmp_path / "index.qmd", (Move(tmp_path / "index.qmd", tmp_path / "docs/index.qmd"),)
    )
    note = next(n for n in blockers if n.category == "Includes That Can't Be Auto-Updated")
    assert note.line == 2
    assert note.snippet == "{{< include missing.qmd >}}"


def test_frontmatter_reference_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    text = "---\ntitle: Home\nimage: cover.png\n---\n# Home\n"
    _, _, _, blockers = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in blockers if n.category == "Frontmatter Fields to Update Manually")
    assert note.line == 3
    assert note.snippet == "image: cover.png"


def test_broken_reference_note_has_a_category_and_excerpt(tmp_path: Path) -> None:
    page = tmp_path / "index.qmd"
    (tmp_path / "other.qmd").write_text("# Other\n")
    (tmp_path / "other.md").write_text("# Other\n")
    text = "see\n[Other](other.html)\n"
    _, _, _, blockers = rewrite_document(text, page, (Move(page, tmp_path / "docs/index.qmd"),))
    note = next(n for n in blockers if n.category == "Broken References to Fix")
    assert note.line == 2
    assert note.snippet == "[Other](other.html)"
