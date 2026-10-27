"""Tests for the bundled Quarto metadata partial used for page titles and translations"""

import shutil
import subprocess
from pathlib import Path

import pytest

import great_docs
from great_docs.core import GreatDocs

VENDORED = Path(great_docs.__file__).parent / "assets" / "metadata.html"

# `quarto --paths` returns roots that contain this relative path.
UPSTREAM_RELATIVE = Path("formats") / "html" / "pandoc" / "metadata.html"

HEAD_TAGS_LOOP = ["$for(gd-head-tags)$", "$gd-head-tags$", "$endfor$"]
# Removed as one block, since `$endif$` also closes Quarto's own conditionals.
ROBOTS_LINES = ["$if(robots)$", '<meta name="robots" content="$robots$" />', "$endif$"]
# Hide the page until theme-init.js reveals it (with a no-JS fallback).
PAGE_REVEAL_PREFIXES = (
    "<style>html:not(.theme-loaded)",
    "<noscript><style>html:not(.theme-loaded)",
)


def _quarto_partial() -> Path | None:
    """
    Locate the metadata partial of the installed Quarto

    Returns
    -------
    :
        Path to Quarto's installed copy, or `None` if Quarto is unavailable or
        does not report the file.
    """
    if shutil.which("quarto") is None:
        return None

    try:
        result = subprocess.run(
            ["quarto", "--paths"],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        candidate = Path(line.strip()) / UPSTREAM_RELATIVE
        if candidate.is_file():
            return candidate

    return None


def _without_title(content: str) -> list[str]:
    """
    Remove the title element from a metadata partial

    Parameters
    ----------
    content
        Contents of a metadata partial.

    Returns
    -------
    :
        Lines that do not contain `<title>`.
    """
    return [line for line in content.splitlines() if "<title>" not in line]


def _unmodified_lines(content: str) -> list[str]:
    """
    Return metadata lines unchanged by great-docs

    Parameters
    ----------
    content
        Contents of a metadata partial.

    Returns
    -------
    :
        Lines other than the title element, the robots tag, the page-reveal
        styles and the `gd-head-tags` loop.
    """
    content = content.replace("\n".join(ROBOTS_LINES) + "\n", "")
    return [
        line
        for line in _without_title(content)
        if line not in HEAD_TAGS_LOOP and not line.startswith(PAGE_REVEAL_PREFIXES)
    ]


def test_bundled_partial_contains_title_element():
    """Confirm that the bundled title element remains available for replacement"""
    assert "<title>" in VENDORED.read_text(encoding="utf-8")


@pytest.mark.skipif(
    _quarto_partial() is None,
    reason="Quarto metadata partial is unavailable",
)
def test_bundled_partial_matches_quarto_except_for_title_and_head_tags() -> None:
    """
    Keep the bundled metadata tags aligned with Quarto

    Exclude the title element, the robots tag, the page-reveal styles and the
    `gd-head-tags` loop, which great-docs replaces or adds.
    """
    upstream = _quarto_partial()
    assert upstream is not None

    assert _unmodified_lines(VENDORED.read_text(encoding="utf-8")) == _unmodified_lines(
        upstream.read_text(encoding="utf-8")
    ), f"Bundled metadata tags differ from {upstream}"


@pytest.mark.parametrize(
    ("template", "titled"),
    [
        ("{page_title} | {site_name}", "$pagetitle$ | $title-prefix$"),
        ("{site_name} - {page_title}", "$title-prefix$ - $pagetitle$"),
        ("Docs: {page_title}", "Docs: $pagetitle$"),
        ("{page_title}", "$pagetitle$"),
    ],
)
def test_title_line_applies_template_only_to_titled_pages(template: str, titled: str):
    """
    Preserve Quarto's title for untitled pages

    Quarto leaves `title-prefix` unset on untitled pages and uses the site
    name as `pagetitle`. The conditional therefore excludes surrounding
    template text from those pages.
    """
    line = GreatDocs._build_title_template_line(None, template)  # type: ignore[arg-type]

    assert line == f"<title>$if(title-prefix)${titled}$else$$pagetitle$$endif$</title>"


@pytest.mark.parametrize("template", ["{site_name}", "$pagetitle$", "{page_title} $ {site_name}"])
def test_title_line_rejects_missing_page_placeholder_or_dollar(template: str):
    """Reject templates that omit `{page_title}` or contain `$`"""
    assert GreatDocs._build_title_template_line(None, template) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("template", [None, False, 42, ["{page_title}"]])
def test_title_line_rejects_non_string_templates(template: object):
    """
    Handle non-string page-title templates

    YAML parses an empty `title_template:` as `None`. Treat every non-string
    value as unsupported so the build keeps Quarto's titles.
    """
    assert GreatDocs._build_title_template_line(None, template) is None  # type: ignore[arg-type]


def _write_partial(tmp_path: Path, yaml: str) -> tuple[GreatDocs, dict]:
    """
    Write the metadata partial for a project configured by `yaml`

    Parameters
    ----------
    tmp_path
        Project directory.
    yaml
        Contents of `great-docs.yml`.

    Returns
    -------
    :
        The project and its Quarto configuration, including any registered partial.
    """
    (tmp_path / "great-docs.yml").write_text(yaml, encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    config: dict = {"format": {"html": {}}}
    docs._write_metadata_partial(config)
    return docs, config


def test_partial_carries_translations_without_seo(tmp_path: Path):
    """Include translations when SEO is disabled"""
    docs, config = _write_partial(
        tmp_path, "site:\n  lang: fr\nseo:\n  enabled: false\nsocial_cards: false\n"
    )

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert config["format"]["html"]["template-partials"] == ["metadata.html"]
    assert '<meta name="gd-i18n" content="' in partial
    assert _without_title(partial)[:-1] == _without_title(VENDORED.read_text(encoding="utf-8"))
    assert "<title>$pagetitle$" in partial


def test_bundled_partial_registered_without_options(tmp_path: Path) -> None:
    """
    Register the bundled partial unchanged when no metadata option is on

    Pages can carry `gd-head-tags` on any site, so the loop must always reach
    the template.
    """
    docs, config = _write_partial(tmp_path, "seo:\n  enabled: false\nsocial_cards: false\n")

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert partial == VENDORED.read_text(encoding="utf-8")
    assert config["format"]["html"]["template-partials"] == ["metadata.html"]


def test_partial_carries_title_and_translations(tmp_path: Path):
    """Combine the title template with the translation bundle"""
    docs, _ = _write_partial(
        tmp_path, "site:\n  lang: fr\nseo:\n  title_template: '{site_name} - {page_title}'\n"
    )

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert "$title-prefix$ - $pagetitle$" in partial
    assert '<meta name="gd-i18n" content="' in partial


def test_partial_carries_og_type_without_seo(tmp_path: Path):
    """
    Include the Open Graph page type even when SEO is disabled
    """
    docs, config = _write_partial(tmp_path, "seo:\n  enabled: false\n")

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert config["format"]["html"]["template-partials"] == ["metadata.html"]
    assert partial.count('<meta property="og:type" content="website">') == 1


def test_partial_omits_og_type_without_social_cards(tmp_path: Path):
    """
    Omit the Open Graph page type when social cards are disabled
    """
    docs, _ = _write_partial(tmp_path, "social_cards: false\n")

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert "og:type" not in partial


def test_show_dates_registers_partial(tmp_path: Path) -> None:
    """
    Add the build time to the partial when SEO and social cards are disabled

    The page date tags come through the bundled `gd-head-tags` loop, which
    appears once.
    """
    docs, config = _write_partial(
        tmp_path, "show_dates: true\nseo:\n  enabled: false\nsocial_cards: false\n"
    )

    partial = (docs.build_dir / "metadata.html").read_text(encoding="utf-8")
    assert config["format"]["html"]["template-partials"] == ["metadata.html"]
    assert partial.count("$for(gd-head-tags)$") == 1
    assert partial.count('<meta name="gd-build-time" content="') == 1
