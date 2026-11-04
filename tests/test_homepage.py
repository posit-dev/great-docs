import shutil
import subprocess
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from typing import NoReturn

import pytest

from great_docs import GreatDocs
from great_docs._layout import Layout
from great_docs._website.homepage import landing, page, readme, source
from great_docs._website.homepage.readme import Badge
from great_docs._yaml import split_front_matter
from tests.support import homepage_hero, homepage_margin, write_config


def _write(root: Path, *names: str) -> None:
    """
    Create files with placeholder content

    Parameters
    ----------
    root
        The directory to create the files in.
    *names
        The file paths, relative to `root`.
    """
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(f"{name}\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("present", "chosen"),
    [
        (["README.rst"], "README.rst"),
        (["README.rst", "README.md"], "README.md"),
        (["README.md", "index.md"], "index.md"),
        (["README.md", "index.md", "index.qmd"], "index.qmd"),
    ],
)
def test_find_prefers_index_pages_then_readmes(tmp_path: Path, present: list[str], chosen: str):
    _write(tmp_path, "great-docs.yml", *present)

    found = source.find(Layout.make(tmp_path))

    assert found[0] == tmp_path / chosen
    assert sorted(path.name for path in found) == sorted(present)


def test_find_returns_nothing_without_a_source(tmp_path: Path):
    _write(tmp_path, "great-docs.yml")

    assert source.find(Layout.make(tmp_path)) == []


def test_find_falls_back_to_the_package_readme(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "docs/great-docs.yml", "README.md")

    assert source.find(Layout.make(tmp_path)) == [tmp_path / "README.md"]


def test_find_prefers_the_source_directory_to_the_package_root(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "docs/great-docs.yml", "README.md", "docs/index.md")

    found = source.find(Layout.make(tmp_path))

    assert found == [tmp_path / "docs/index.md", tmp_path / "README.md"]


def test_read_separates_title_description_and_options(tmp_path: Path):
    page = tmp_path / "index.qmd"
    _ = page.write_text(
        "---\ntitle: Home\ndescription: About it\nexecute:\n  echo: false\n---\n\n\n# Body\n",
        encoding="utf-8",
    )

    authored = source.read(page, report=print)

    assert authored.title == "Home"
    assert authored.description == {"description": "About it"}
    assert authored.options == {"execute": {"echo": False}}
    assert authored.body == "# Body\n"


def test_read_converts_restructured_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    page = tmp_path / "README.rst"
    _ = page.write_text("Title\n=====\n", encoding="utf-8")

    def convert(path: Path, *, report: Callable[[str], None]) -> str:
        return "# Title\n"

    monkeypatch.setattr(source, "rst_to_markdown", convert)

    assert source.read(page, report=print).body == "# Title\n"


@pytest.mark.skipif(
    not shutil.which("quarto") and not shutil.which("pandoc"), reason="needs pandoc"
)
def test_rst_to_markdown_converts_with_pandoc(tmp_path: Path):
    page = tmp_path / "README.rst"
    _ = page.write_text("Title\n=====\n\nParagraph text.\n\n- Item 1\n", encoding="utf-8")

    markdown = source.rst_to_markdown(page, report=print)

    assert "# Title" in markdown
    assert "Paragraph text" in markdown
    assert "Item 1" in markdown


def _reject(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    """
    Simulate a pandoc run that rejects its input

    Returns
    -------
    :
        A result with exit status 1 and an error message on standard error.
    """
    return subprocess.CompletedProcess([], 1, stdout="", stderr="bad input")


def _fail(*_args: object, **_kwargs: object) -> NoReturn:
    """
    Simulate a pandoc executable that cannot start

    Raises
    ------
    OSError
        Always.
    """
    raise OSError("pandoc crashed")


@pytest.mark.parametrize(
    ("which", "run", "warning"),
    [
        (None, None, "pandoc not found"),
        ("pandoc", _reject, "pandoc conversion failed: bad input"),
        ("quarto", _fail, "pandoc conversion error: pandoc crashed"),
    ],
)
def test_rst_to_markdown_falls_back_to_the_raw_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str | None, run: object, warning: str
):
    page = tmp_path / "README.rst"
    _ = page.write_text("Hello\n=====", encoding="utf-8")

    def find_executable(cmd: str) -> str | None:
        return f"/bin/{cmd}" if cmd == which else None

    monkeypatch.setattr(shutil, "which", find_executable)
    if run is not None:
        monkeypatch.setattr(subprocess, "run", run)
    reported: list[str] = []

    assert source.rst_to_markdown(page, report=reported.append) == "Hello\n====="
    assert warning in reported[0]


def test_landing_page_shows_name_description_and_install():
    page = landing.markdown(
        "fancy-lib", "Fancy things", has_api_reference=False, has_user_guide=False
    )

    assert page.startswith("## fancy-lib\n\nFancy things\n")
    assert "pip install fancy-lib" in page
    assert "Get Started" not in page


def test_landing_page_without_a_name_or_description():
    page = landing.markdown(None, "", has_api_reference=False, has_user_guide=False)

    assert page.startswith("## Package\n\n### Installation")


@pytest.mark.parametrize(("api", "guide"), [(True, False), (False, True), (True, True)])
def test_landing_page_links_the_sections_the_site_has(api: bool, guide: bool):
    page = landing.markdown("pkg", "", has_api_reference=api, has_user_guide=guide)

    assert "### Get Started" in page
    assert ("reference/index.qmd" in page) == api
    assert ("user-guide/index.qmd" in page) == guide


def test_extract_takes_badges_after_the_heading():
    markdown = (
        "# My Package\n"
        "\n"
        "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org/p)\n"
        "[![Cov](https://codecov.io/badge.svg)](https://cov.com)\n"
        "\n"
        "[![Docs](https://readthedocs.org/b.svg)](https://docs)\n"
        "\n"
        "Some body text.\n"
    )

    elements = readme.extract_hero_elements(markdown)

    assert [badge.alt for badge in elements.badges] == ["PyPI", "Cov", "Docs"]
    assert elements.badges[0] == Badge(
        alt="PyPI", img="https://img.shields.io/badge/pypi-v1-blue", url="https://pypi.org/p"
    )
    assert elements.body == "# My Package\n\nSome body text.\n"
    assert elements.logo_url is None
    assert elements.tagline is None


def test_extract_takes_the_whole_centred_block():
    markdown = (
        "> Install via pip.\n"
        "\n"
        '<div align="center">\n'
        '<a href="https://example.com/"><img src="https://example.com/logo.svg"/></a>\n'
        "_A cool tagline_\n"
        "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org)\n"
        "[![CI](https://github.com/u/p/actions/workflows/t.yml/badge.svg)](https://github.com/ci)\n"
        "</div>\n"
        "\n"
        "\n"
        "\n"
        "Body text after.\n"
    )

    elements = readme.extract_hero_elements(markdown)

    assert [badge.alt for badge in elements.badges] == ["PyPI", "CI"]
    assert elements.logo_url == "https://example.com/logo.svg"
    assert elements.tagline == "A cool tagline"
    assert elements.body == "> Install via pip.\n\nBody text after.\n"


def test_extract_takes_a_centred_block_with_a_nested_div():
    markdown = (
        '<div align="center">\n'
        "<div>\n"
        '<img src="https://example.com/logo.svg">\n'
        "</div>\n"
        "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org)\n"
        "</div>\n"
        "\n"
        "Body text.\n"
    )

    elements = readme.extract_hero_elements(markdown)

    assert [badge.alt for badge in elements.badges] == ["PyPI"]
    assert elements.logo_url == "https://example.com/logo.svg"
    assert elements.body == "\nBody text.\n"


@pytest.mark.parametrize(
    "markdown",
    [
        "# Title\n\nJust text, no badges.\n",
        '<div align="center">\n<img src="hero.png">\n</div>\n\nBody text.\n',
        "# Title\n\n[![Logo](https://example.com/logo.png)](https://example.com)\n",
    ],
)
def test_extract_leaves_a_readme_without_known_badges(markdown: str):
    elements = readme.extract_hero_elements(markdown)

    assert elements.badges == []
    assert elements.body == markdown
    assert elements.logo_url is None


def test_extract_leaves_a_centred_block_that_never_closes():
    markdown = (
        '<div align="center">\n'
        '<img src="https://example.com/banner.png">\n'
        "</div>\n"
        "\n"
        "Intro paragraph.\n"
        "\n"
        '<div align="center">\n'
        "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org)\n"
        "\n"
        "## Usage\n"
    )

    elements = readme.extract_hero_elements(markdown)

    assert elements.badges == []
    assert elements.body == markdown


def test_bump_heading_levels_outside_code():
    markdown = (
        "# H1\n## H2\n###### H6\n"
        "```python\n#| echo: false\n# comment\n```\n"
        "~~~\n# tilde\n```\n# still code\n~~~\n"
        "### After"
    )

    assert readme.bump_heading_levels(markdown) == (
        "## H1\n### H2\n####### H6\n"
        "```python\n#| echo: false\n# comment\n```\n"
        "~~~\n# tilde\n```\n# still code\n~~~\n"
        "#### After"
    )


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("# MyPkg\n\nBody", "Body"),
        ("\n# mypkg  \n\nBody", "Body"),
        ("# Other\n\nBody", "# Other\n\nBody"),
        ("Intro\n\n# mypkg\n\nBody", "Intro\n\n# mypkg\n\nBody"),
    ],
)
def test_strip_duplicate_title(markdown: str, expected: str):
    assert readme.strip_duplicate_title(markdown, " MyPkg ") == expected


class _Markup(HTMLParser):
    """The text and start-tag attributes of an HTML fragment, with references decoded"""

    def __init__(self, fragment: str) -> None:
        super().__init__()
        self.texts: list[str] = []
        self.attrs: list[dict[str, str | None]] = []
        self.feed(fragment)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attrs.append(dict(attrs))

    def handle_data(self, data: str) -> None:
        self.texts.append(data)


def test_hero_shows_markup_characters_as_written(tmp_path: Path):
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    logo = {"light": "https://cdn.example/logo.svg?a=1&b=2", "alt": 'The "Logo"'}
    badge = {
        "alt": 'say "hi"',
        "img": "https://img.example/b.svg?a=1&b=2",
        "url": 'https://example.com/?q="x"&r=<y>',
    }
    hero = {"name": 'Tom & "Jerry"', "tagline": "x < y & z", "logo": logo, "badges": [badge]}
    _ = write_config(tmp_path, {"hero": hero})

    html, _ = homepage_hero(GreatDocs(project_path=tmp_path))
    markup = _Markup(html)

    assert {'Tom & "Jerry"', "x < y & z"} <= set(markup.texts)
    assert any(attrs.get("src") == logo["light"] for attrs in markup.attrs)
    assert any(attrs.get("alt") == logo["alt"] for attrs in markup.attrs)
    assert {"href": badge["url"]} in markup.attrs
    assert {"alt": badge["alt"], "src": badge["img"]} in markup.attrs


def test_sidebar_shows_markup_characters_as_written(tmp_path: Path):
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    author = {
        "name": "Ada <Lovelace>",
        "role": 'R&D "lead"',
        "affiliation": "Lab <1>",
        "homepage": 'https://ada.example/?a="b"&c=<d>',
    }
    funding = {"name": "Fund & <Co>", "roles": ["<Sponsor>"], "ror": 'https://ror.org/"x"'}
    _ = write_config(tmp_path, {"authors": [author], "funding": funding})

    markup = _Markup(homepage_margin(GreatDocs(project_path=tmp_path)))

    texts = {author["name"], author["role"], author["affiliation"], funding["name"], "<Sponsor>"}
    assert texts <= set(markup.texts)
    assert {"href": author["homepage"], "title": "Website"} in markup.attrs
    assert {"href": funding["ror"], "title": "Research Organization Registry"} in markup.attrs


def test_blended_homepage_keeps_front_matter_whose_title_contains_three_dashes(tmp_path: Path):
    """Preserve the front matter and body when a title contains `---`"""
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    docs = GreatDocs(project_path=tmp_path)
    docs.build_dir.mkdir()
    content = "---\ntitle: A---B\ndescription: Guide\n---\n\n# A---B\n\nWelcome.\n"

    index_qmd = page.write_blended(
        docs._config,
        docs.layout,
        docs.build_dir,
        content,
        metadata={},
        package_name="pkg",
        pages=docs._page_map(None),
        page_authors=[],
    )

    front_matter, body = split_front_matter(index_qmd.read_text(encoding="utf-8"))
    assert front_matter.data == {"title": "A---B", "description": "Guide", "toc": False}
    assert body.lstrip().startswith("Welcome.")
