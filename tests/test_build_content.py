"""
Tests for the build steps that publish authored content
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from yaml12 import format_yaml, read_yaml, write_yaml

from great_docs import GreatDocs
from great_docs._build import content
from great_docs._build.steps import Outcome, Skipped
from great_docs._contribution import Contribution, NavbarLink
from great_docs._utils import QUARTO_YML_HEADER
from great_docs._website.quarto_yml import apply as apply_contribution
from great_docs._website.quarto_yml import edit as edit_quarto_yml
from great_docs._website.quarto_yml import read as read_quarto_yml
from great_docs._website.quarto_yml import write as write_quarto_yml
from great_docs._website.quarto_yml import write_initial as write_initial_quarto_yml
from great_docs._yaml import split_front_matter
from tests.support import (
    StubRemote,
    apply_contributions,
    custom_pages_step,
    discover_user_guide,
    make_project,
    make_run,
    prepare_build_directory,
    sections_step,
    update_quarto_config,
    write_config,
)

if TYPE_CHECKING:
    from great_docs._content.user_guide import UserGuide

NAVBAR_WITH_REFERENCE = {
    "website": {
        "navbar": {"left": [{"text": "Reference", "href": "reference/index.qmd"}]},
        "sidebar": [],
    }
}


def _write_files(root: Path, files: dict[str, str]) -> None:
    """
    Write text files below a directory

    Parameters
    ----------
    root
        The directory.
    files
        The text of each file, by path relative to `root`.
    """
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _project(
    root: Path, files: dict[str, str], quarto_config: dict[str, Any] | None = None
) -> GreatDocs:
    """
    Create a project with a build directory and, optionally, its `_quarto.yml`

    Parameters
    ----------
    root
        The project directory.
    files
        The project's files, by path relative to `root`.
    quarto_config
        The build directory's `_quarto.yml`, or `None` for none.

    Returns
    -------
    :
        The project.
    """
    _write_files(root, files)
    docs = GreatDocs(project_path=str(root))
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    if quarto_config is not None:
        write_quarto_yml(docs.build_dir, quarto_config)
    return docs


def _write_section_project(project_path: Path, dir_name: str) -> Path:
    (project_path / "great-docs.yml").write_text(
        f"sections:\n  - title: Examples\n    dir: {dir_name}\n"
    )
    build_dir = project_path / "great-docs"
    build_dir.mkdir()
    (build_dir / "_quarto.yml").write_text(
        "website:\n"
        "  navbar:\n"
        "    left:\n"
        "      - text: Home\n"
        "        href: index.qmd\n"
        "  sidebar: []\n"
    )
    return build_dir


def _user_guide(docs: GreatDocs, guide: UserGuide | None) -> Outcome:
    """
    Run the user guide step and apply its navigation without writing a fallback homepage

    Parameters
    ----------
    docs
        The project.
    guide
        The discovered user guide, or `None` when it has no pages.

    Returns
    -------
    :
        The step's outcome.
    """
    run = make_run(docs, user_guide=guide)
    outcome = content.user_guide(
        run, docs._config, docs.layout, page_authors=run.page_authors, remote=StubRemote()
    )
    apply_contributions(docs, run)
    return outcome


def _publish(docs: GreatDocs, guide: UserGuide) -> list[str]:
    """
    Publish a project's user guide pages

    Parameters
    ----------
    docs
        The project.
    guide
        The user guide.

    Returns
    -------
    :
        The copied page paths relative to the build directory.
    """
    return content._publish_guide_pages(
        docs._config, docs.layout, guide, page_authors=make_run(docs).page_authors
    )


def _promote(docs: GreatDocs, guide: UserGuide) -> str | None:
    """
    Promote a project's first user guide page to the homepage

    Parameters
    ----------
    docs
        The project.
    guide
        The user guide.

    Returns
    -------
    :
        The promoted page's former path, or `None` when no page was promoted.
    """
    return content._promote_first_page(
        docs._config,
        docs.layout,
        make_project(docs),
        guide,
        page_authors=make_run(docs).page_authors,
        api_block=None,
    )


def _add_navigation(
    docs: GreatDocs, guide: UserGuide, blended_first_page: str | None = None
) -> None:
    """
    Apply the user guide's sidebar and navbar link to the project's `_quarto.yml`

    Parameters
    ----------
    docs
        The project.
    guide
        The user guide.
    blended_first_page
        The promoted page's former path, or `None` when no page was promoted.
    """
    contribution = content._guide_navigation(docs._config, guide, blended_first_page)
    with edit_quarto_yml(docs.build_dir) as quarto_config:
        apply_contribution(quarto_config, contribution, docs._config)


def _assets(docs: GreatDocs) -> Outcome:
    """
    Run the assets step for a project without updating `_quarto.yml`

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The step's outcome.
    """
    with patch("great_docs._build.site.update_quarto_config"):
        return content.assets(make_run(docs), docs._config, docs.layout, remote=StubRemote())


# ---------------------------------------------------------------------------
# Page map
# ---------------------------------------------------------------------------


def test_links_into_a_guide_directory_without_guide_pages_are_not_rewritten(tmp_path: Path):
    """
    Verify that links to unpublished guide pages keep their source paths
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "user_guide").mkdir()
    draft = tmp_path / "user_guide" / "draft.qmd"
    draft.write_text("# Draft\n")
    write_config(tmp_path, "user_guide:\n  - section: Start\n    contents: [missing.qmd]\n")
    docs = GreatDocs(project_path=str(tmp_path))
    guide = discover_user_guide(docs)
    assert guide is None

    assert content.page_map(docs._config, docs.layout, guide).destination(draft.resolve()) is None


# ---------------------------------------------------------------------------
# User guide step
# ---------------------------------------------------------------------------


def test_the_user_guide_step_skips_a_project_without_a_guide(tmp_path: Path):
    docs = _project(tmp_path, {"pyproject.toml": '[project]\nname = "mypkg"\n'})

    assert _user_guide(docs, discover_user_guide(docs)) == Skipped("no user guide found")


def test_a_user_guide_homepage_without_guide_pages_falls_back_to_the_readme(tmp_path: Path, capsys):
    docs = _project(
        tmp_path, {"great-docs.yml": "homepage: user_guide\n", "README.md": "# Demo\n\nHello\n"}
    )

    run = make_run(docs, user_guide=discover_user_guide(docs))
    outcome = content.user_guide(
        run, docs._config, docs.layout, page_authors=run.page_authors, remote=StubRemote()
    )

    assert outcome == Skipped("no user guide found")
    assert "Hello" in (docs.build_dir / "index.qmd").read_text(encoding="utf-8")
    assert "falling back to index mode" in capsys.readouterr().out


def test_a_user_guide_homepage_writes_the_project_pages_but_not_the_readme(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "great-docs.yml": "homepage: user_guide\n",
            "README.md": "# Demo\n",
            "LICENSE": "MIT License\n",
        },
    )

    content.homepage(
        make_run(docs), docs._config, docs.layout, page_authors=[], remote=StubRemote()
    )

    assert (docs.build_dir / "license.qmd").is_file()
    assert not (docs.build_dir / "index.qmd").exists()


def test_the_user_guide_step_publishes_pages_with_a_sidebar_and_navbar_link(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "mypkg"\n',
            "user_guide/01-a.qmd": "---\ntitle: A\nguide-section: Basics\n---\nA\n",
            "user_guide/02-b.qmd": "---\ntitle: B\nguide-section: Advanced\n---\nB\n",
        },
        NAVBAR_WITH_REFERENCE,
    )

    assert _user_guide(docs, discover_user_guide(docs)) == "User Guide configured"

    assert (docs.build_dir / "user-guide" / "a.qmd").exists()
    website = read_quarto_yml(docs.build_dir)["website"]
    guide_sidebar = next(s for s in website["sidebar"] if s.get("id") == "user-guide")
    sections = [c["section"] for c in guide_sidebar["contents"] if "section" in c]
    assert sections == ["Basics", "Advanced"]
    assert [item["text"] for item in website["navbar"]["left"]] == ["User Guide", "Reference"]


def test_a_user_guide_homepage_promotes_the_first_page(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "mypkg"\n',
            "great-docs.yml": "homepage: user_guide\n",
            "user_guide/01-intro.qmd": "---\ntitle: Intro\n---\n\nWelcome.\n",
            "user_guide/02-next.qmd": "---\ntitle: Next\n---\n\nMore.\n",
        },
        NAVBAR_WITH_REFERENCE,
    )

    assert _user_guide(docs, discover_user_guide(docs)) == "User Guide configured"

    assert "Welcome." in (docs.build_dir / "index.qmd").read_text()
    assert not (docs.build_dir / "user-guide" / "intro.qmd").exists()
    website = read_quarto_yml(docs.build_dir)["website"]
    guide_sidebar = next(s for s in website["sidebar"] if s.get("id") == "user-guide")
    hrefs = [
        entry if isinstance(entry, str) else entry["href"] for entry in guide_sidebar["contents"]
    ]
    assert hrefs[0] == "index.qmd"
    assert "user-guide/intro.qmd" not in hrefs
    # The promoted homepage replaces the guide's navbar link
    assert [item["text"] for item in website["navbar"]["left"]] == ["Reference"]


# ---------------------------------------------------------------------------
# Publishing the user guide
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("settings", "published", "unpublished"),
    [
        ("", ["intro.qmd", "installation.qmd"], ["01-intro.qmd", "02-installation.qmd"]),
        (
            "user_guide:\n  - section: Basics\n    contents:\n"
            "      - 01-intro.qmd\n      - 02-installation.qmd\n",
            ["01-intro.qmd", "02-installation.qmd"],
            ["intro.qmd", "installation.qmd"],
        ),
    ],
    ids=["auto", "explicit"],
)
def test_published_guide_pages_drop_numeric_prefixes_only_in_auto_mode(
    tmp_path: Path, settings: str, published: list[str], unpublished: list[str]
):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "test"\nversion = "0.1.0"',
            "great-docs.yml": settings,
            "user_guide/01-intro.qmd": "---\ntitle: Intro\n---\n# Intro\n",
            "user_guide/02-installation.qmd": "---\ntitle: Installation\n---\n# Installation\n",
        },
    )
    guide = discover_user_guide(docs)
    assert guide is not None

    copied_files = _publish(docs, guide)

    target = docs.build_dir / "user-guide"
    assert copied_files == [f"user-guide/{name}" for name in published]
    assert all((target / name).exists() for name in published)
    assert not any((target / name).exists() for name in unpublished)


def test_published_guide_keeps_nested_pages_of_either_extension(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "test"\nversion = "0.1.0"',
            "user_guide/intro.qmd": "---\ntitle: Intro QMD\n---\n\n# Intro\n",
            "user_guide/setup.md": "---\ntitle: Setup MD\n---\n\n# Setup\n",
            "user_guide/01-section1/overview.qmd": "---\ntitle: Overview\n---\n\n# Overview\n",
            "user_guide/01-section1/details.md": "---\ntitle: Details\n---\n\n# Details\n",
            "user_guide/01-section1/topic1/deep.qmd": "---\ntitle: Deep\n---\n\n# Deep\n",
            "user_guide/01-section1/topic1/deep-notes.md": "---\ntitle: Notes\n---\n\n# Notes\n",
        },
    )
    guide = discover_user_guide(docs)
    assert guide is not None

    copied_files = _publish(docs, guide)

    assert sorted(copied_files) == [
        "user-guide/intro.qmd",
        "user-guide/section1/details.md",
        "user-guide/section1/overview.qmd",
        "user-guide/section1/topic1/deep-notes.md",
        "user-guide/section1/topic1/deep.qmd",
        "user-guide/setup.md",
    ]
    assert all((docs.build_dir / path).exists() for path in copied_files)


def test_published_guide_pages_expand_code_includes(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "test"\nversion = "0.1.0"',
            "examples/sample.py": "x = 1\n",
            "user_guide/01-tutorial.qmd": (
                "---\ntitle: Tutorial\n---\n\n{{< include examples/sample.py >}}\n"
            ),
        },
    )
    guide = discover_user_guide(docs)
    assert guide is not None

    _publish(docs, guide)

    built_content = (docs.build_dir / "user-guide" / "tutorial.qmd").read_text(encoding="utf-8")
    assert "```python" in built_content
    assert "x = 1" in built_content
    assert "{{< include" not in built_content


def test_underscore_dir_copied_as_assets_with_qmd():
    """
    Verify that underscore-prefixed directories remain assets even with `.qmd` files
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()
        (user_guide / "01-tutorial.qmd").write_text(
            '---\ntitle: Tutorial\n---\n\n{{< include _includes/example.qmd lang="markdown" >}}\n'
        )

        includes = user_guide / "_includes"
        includes.mkdir()
        (includes / "example.qmd").write_text("```python\nprint('hello')\n```\n")

        docs = GreatDocs(project_path=tmp_dir)
        ug_info = discover_user_guide(docs)
        assert ug_info is not None

        _publish(docs, ug_info)

        copied_includes = docs.build_dir / "user-guide" / "_includes"
        assert copied_includes.exists(), "_includes dir was not copied"
        assert (copied_includes / "example.qmd").exists()

        built = docs.build_dir / "user-guide" / "tutorial.qmd"
        built_content = built.read_text(encoding="utf-8")
        assert "```markdown" in built_content
        assert "print('hello')" in built_content


def test_published_guide_replaces_its_asset_directories(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "mypkg"\n',
            "user_guide/01-intro.qmd": "---\ntitle: Intro\n---\nContent\n",
            "user_guide/images/logo.png": "PNG",
            "great-docs/user-guide/images/stale.png": "old",
        },
    )
    guide = discover_user_guide(docs)
    assert guide is not None

    _publish(docs, guide)

    images = docs.build_dir / "user-guide" / "images"
    assert (images / "logo.png").read_text() == "PNG"
    assert not (images / "stale.png").exists()


@pytest.mark.parametrize(
    ("explicit", "subdir"),
    [(False, "advanced"), (True, "02-advanced")],
)
def test_publish_user_guide_copies_directory_metadata(explicit, subdir):
    """
    Verify that directory metadata follows page paths in automatic and explicit modes
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        src = tmp / "user_guide"
        advanced = src / "02-advanced"
        advanced.mkdir(parents=True)
        (src / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nC\n")
        (src / "_metadata.yml").write_text("toc: false\n")
        (advanced / "01-page.qmd").write_text("---\ntitle: Page\n---\nC\n")
        (advanced / "_metadata.yaml").write_text("number-sections: true\n")

        guide_info = {
            "files": [
                {"path": src / "01-intro.qmd", "title": "Intro", "section": None},
                {"path": advanced / "01-page.qmd", "title": "Page", "section": None},
            ],
            "source_dir": src,
            "explicit": explicit,
        }
        _publish(docs, guide_info)

        target = docs.build_dir / "user-guide"
        assert (target / "_metadata.yml").read_text() == "toc: false\n"
        assert (target / subdir / "_metadata.yaml").read_text() == "number-sections: true\n"


def test_user_guide_asset_copy_skips_the_staged_quarto_project():
    """
    Keep the staged Quarto project out of copied guide assets
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\n'
        )
        docs_dir = project_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "great-docs.yml").write_text("user_guide: .\nreference: false\n")
        (docs_dir / "guide.qmd").write_text("---\ntitle: Guide\n---\n\n![Chart](images/c.png)\n")
        (docs_dir / "images").mkdir()
        (docs_dir / "images/c.png").write_bytes(b"chart")
        # A previous build's staged Quarto project sits beside the source pages. Its leading
        # underscore makes it look like an asset directory, but copying it into its own
        # descendant would recurse until the path grew too long.
        stale = docs_dir / "_quarto/default/reference/other.qmd"
        stale.parent.mkdir(parents=True)
        stale.write_text("# Leftover\n")
        (docs_dir / "_quarto/default/_quarto.yml").write_text(QUARTO_YML_HEADER + "project: {}\n")

        docs = GreatDocs(project_path=tmp_dir)
        prepare_build_directory(docs, make_run(docs))
        _publish(docs, discover_user_guide(docs))

        assert (docs.build_dir / "user-guide/images/c.png").read_bytes() == b"chart"
        assert not list(docs.build_dir.rglob("_quarto"))


def test_publish_user_guide_adds_breadcrumbs():
    """
    Verify that guide publication sets `bread-crumbs: false`
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir()

        ug_src = Path(tmp_dir) / "user_guide"
        ug_src.mkdir()
        (ug_src / "01-guide.qmd").write_text(
            "---\ntitle: My Guide\n---\n\n# Content\n", encoding="utf-8"
        )

        ug_info = {
            "files": [{"path": ug_src / "01-guide.qmd", "title": "My Guide"}],
            "sections": [],
            "source_dir": ug_src,
            "explicit": False,
        }
        copied = _publish(docs, ug_info)
        assert len(copied) == 1

        dest_file = build_dir / "user-guide" / "guide.qmd"
        assert dest_file.exists()
        page_text = dest_file.read_text()
        assert "bread-crumbs: false" in page_text


# ---------------------------------------------------------------------------
# Blended homepage
# ---------------------------------------------------------------------------


def _blended_project(root: Path, published: dict[str, str], settings: str = "") -> GreatDocs:
    """
    Create a project whose published guide pages are already in the build directory

    Parameters
    ----------
    root
        The project directory.
    published
        The text of each published page, by path below `user-guide/`.
    settings
        The project's `great-docs.yml`.

    Returns
    -------
    :
        The project.
    """
    return _project(
        root,
        {
            "pyproject.toml": '[project]\nname = "mypkg"\nversion = "1.0"\n',
            "great-docs.yml": settings,
            **{f"great-docs/user-guide/{name}": text for name, text in published.items()},
        },
    )


def test_blending_promotes_the_first_guide_page_to_the_homepage(tmp_path: Path):
    docs = _blended_project(
        tmp_path,
        {"introduction.qmd": "---\ntitle: Introduction\n---\n\n# Introduction\n\nWelcome."},
        "display_name: My Package\nhomepage: user_guide\n",
    )
    guide = {
        "files": [{"path": tmp_path / "user_guide" / "01-introduction.qmd", "title": "Intro"}],
        "source_dir": tmp_path / "user_guide",
        "explicit": False,
    }

    first_page = _promote(docs, guide)

    homepage = (docs.build_dir / "index.qmd").read_text(encoding="utf-8")
    assert first_page == "user-guide/introduction.qmd"
    assert "title: Introduction" in homepage
    assert "Welcome." in homepage
    # Companion formats use this marker to omit the homepage sidebar.
    assert "::: {.gd-meta-sidebar .gd-homepage-sidebar}" in homepage
    assert not (docs.build_dir / "user-guide" / "introduction.qmd").exists()


def test_blending_without_guide_pages_writes_no_homepage(tmp_path: Path):
    docs = _blended_project(tmp_path, {})

    assert _promote(docs, {"files": [], "source_dir": tmp_path, "explicit": False}) is None

    assert not (docs.build_dir / "index.qmd").exists()


def test_blending_skips_a_missing_first_page(tmp_path: Path, capsys):
    docs = _blended_project(tmp_path, {})
    guide = {
        "files": [{"path": tmp_path / "user_guide" / "intro.qmd", "title": "Intro"}],
        "source_dir": tmp_path / "user_guide",
        "explicit": False,
    }

    assert _promote(docs, guide) is None

    assert not (docs.build_dir / "index.qmd").exists()
    assert "not found for blended homepage" in capsys.readouterr().out


def test_blending_keeps_the_numeric_prefix_of_an_explicit_guide_page(tmp_path: Path):
    docs = _blended_project(
        tmp_path,
        {"01-intro.qmd": "---\ntitle: Intro\n---\n# Introduction\nHello world\n"},
        "homepage: user_guide\n",
    )
    guide = {
        "files": [{"path": tmp_path / "user_guide" / "01-intro.qmd", "title": "Intro"}],
        "source_dir": tmp_path / "user_guide",
        "explicit": True,
        "has_index": False,
    }

    assert _promote(docs, guide) == "user-guide/01-intro.qmd"

    assert "Hello world" in (docs.build_dir / "index.qmd").read_text()


def test_blending_keeps_front_matter_and_drops_the_title_heading(tmp_path: Path):
    docs = _blended_project(
        tmp_path,
        {"intro.qmd": "---\ntitle: My Title\n---\n# My Title\nBody text here.\n"},
        "homepage: user_guide\n",
    )
    guide = {
        "files": [{"path": tmp_path / "user_guide" / "intro.qmd", "title": "My Title"}],
        "source_dir": tmp_path / "user_guide",
        "explicit": False,
        "has_index": False,
    }

    _promote(docs, guide)

    homepage = (docs.build_dir / "index.qmd").read_text()
    assert "title: My Title" in homepage
    assert "# My Title" not in homepage
    assert "Body text here." in homepage


def test_blending_accepts_a_page_without_front_matter(tmp_path: Path):
    docs = _blended_project(
        tmp_path, {"plain.qmd": "Just plain content.\n"}, "homepage: user_guide\n"
    )
    guide = {
        "files": [{"path": tmp_path / "user_guide" / "plain.qmd", "title": "Plain"}],
        "source_dir": tmp_path / "user_guide",
        "explicit": False,
        "has_index": False,
    }

    _promote(docs, guide)

    assert "Just plain content." in (docs.build_dir / "index.qmd").read_text()


@pytest.mark.parametrize(
    ("sources", "published", "first_page"),
    [
        (
            ["index.qmd", "00-getting-started/01-quickstart.qmd"],
            {
                "index.qmd": "---\ntitle: Welcome\n---\n# Welcome\nThis is the landing page.\n",
                "getting-started/quickstart.qmd": "---\ntitle: Quickstart\n---\nQuick.\n",
            },
            "user-guide/index.qmd",
        ),
        (
            ["00-getting-started/01-intro.qmd"],
            {
                "getting-started/intro.qmd": (
                    "---\ntitle: Welcome\n---\n# Welcome\nThis is the landing page.\n"
                ),
            },
            "user-guide/getting-started/intro.qmd",
        ),
    ],
    ids=["root-index-first", "nested-page-first"],
)
def test_blending_promotes_a_first_page_from_any_directory(
    tmp_path: Path, sources: list[str], published: dict[str, str], first_page: str
):
    docs = _blended_project(tmp_path, published, "display_name: My Package\nhomepage: user_guide\n")
    guide = {
        "files": [{"path": tmp_path / "user_guide" / source} for source in sources],
        "source_dir": tmp_path / "user_guide",
        "explicit": False,
        "has_index": sources[0] == "index.qmd",
    }

    assert _promote(docs, guide) == first_page

    homepage = (docs.build_dir / "index.qmd").read_text()
    assert "title: Welcome" in homepage
    assert "This is the landing page." in homepage
    assert not (docs.build_dir / first_page).exists()


def test_user_guide_homepage_has_no_dates(tmp_path: Path):
    """
    Leave dates off the user guide page promoted to the homepage
    """
    files = {
        "pyproject.toml": '[project]\nname = "pkg"\nversion = "1.0"\n',
        "great-docs.yml": "show_dates: true\nhomepage: user_guide\n",
        "pkg/__init__.py": "",
        "user_guide/01-intro.qmd": "---\ntitle: Intro\nauthor: Ada\n---\n\nText\n",
        "user_guide/02-next.qmd": "---\ntitle: Next\nauthor: Ada\n---\n\nText\n",
    }
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    info = discover_user_guide(docs)

    _publish(docs, info)
    _promote(docs, info)

    homepage, _ = split_front_matter((docs.build_dir / "index.qmd").read_text())
    second, _ = split_front_matter((docs.build_dir / "user-guide/next.qmd").read_text())
    assert "gd-head-tags" not in homepage
    assert "gd-head-tags" in second


def test_blended_index_hero_fence_is_raw_html():
    """
    Verify that the blended homepage opens its hero block with a bare raw-HTML fence
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        Path(tmp_dir, "great-docs.yml").write_text(
            format_yaml({"hero": {"enabled": True, "name": "Pkg", "tagline": "Tagline"}}),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        ug_dir = gd_dir / "user-guide"
        ug_dir.mkdir(parents=True)
        (ug_dir / "introduction.qmd").write_text(
            '---\ntitle: "Introduction"\n---\n\n# Introduction\n\nWelcome.', encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        info = {
            "files": [{"path": Path(tmp_dir) / "user_guide" / "01-introduction.qmd"}],
            "source_dir": Path(tmp_dir) / "user_guide",
            "explicit": False,
        }
        _promote(docs, info)

        lines = (gd_dir / "index.qmd").read_text(encoding="utf-8").splitlines()

        assert "gd-hero" in "\n".join(lines)
        assert "```{=html}" in lines
        assert not any("pragma" in line for line in lines)


# ---------------------------------------------------------------------------
# User guide sidebar and navbar link
# ---------------------------------------------------------------------------


def _intro_guide(root: Path) -> UserGuide:
    """
    Describe a one-page automatic user guide whose page exists

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The user guide.
    """
    source_dir = root / "user_guide"
    _write_files(source_dir, {"intro.qmd": "---\ntitle: Intro\n---\nContent\n"})
    return {
        "files": [{"path": source_dir / "intro.qmd", "title": "Intro", "section": None}],
        "sections": {},
        "has_index": False,
        "source_dir": source_dir,
        "explicit": False,
    }


def test_the_guide_sidebar_and_navbar_link_are_added_before_the_reference(tmp_path: Path):
    docs = _project(
        tmp_path, {"pyproject.toml": '[project]\nname = "mypkg"\n'}, NAVBAR_WITH_REFERENCE
    )

    _add_navigation(docs, _intro_guide(tmp_path))

    website = read_quarto_yml(docs.build_dir)["website"]
    assert [s["id"] for s in website["sidebar"]] == ["user-guide"]
    assert website["navbar"]["left"] == [
        {"text": "User Guide", "href": "user-guide/intro.qmd"},
        {"text": "Reference", "href": "reference/index.qmd"},
    ]


def test_the_guide_sidebar_replaces_an_earlier_one(tmp_path: Path):
    docs = _project(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "mypkg"\n'},
        {
            "website": {
                "sidebar": [
                    {"id": "user-guide", "title": "Old", "contents": ["old.qmd"]},
                    {"id": "reference", "title": "Reference", "contents": []},
                ],
                "navbar": {"left": [{"text": "User Guide", "href": "user-guide/old.qmd"}]},
            }
        },
    )

    _add_navigation(docs, _intro_guide(tmp_path))

    sidebars = read_quarto_yml(docs.build_dir)["website"]["sidebar"]
    assert [s["id"] for s in sidebars] == ["reference", "user-guide"]
    assert "Old" not in str(sidebars[1])


def test_the_guide_sidebar_is_added_to_a_configuration_without_a_website(tmp_path: Path):
    docs = _project(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "mypkg"\n'},
        {"project": {"type": "website"}},
    )

    _add_navigation(docs, _intro_guide(tmp_path))

    sidebars = read_quarto_yml(docs.build_dir)["website"]["sidebar"]
    assert [s["id"] for s in sidebars] == ["user-guide"]


@pytest.mark.parametrize(
    ("relative", "explicit", "href"),
    [
        ("01-basics/02-setup.qmd", False, "user-guide/basics/setup.qmd"),
        ("01-intro.qmd", True, "user-guide/01-intro.qmd"),
    ],
    ids=["nested-auto", "explicit"],
)
def test_user_guide_navbar_link_targets_the_copied_first_page(
    tmp_path: Path, relative: str, explicit: bool, href: str
):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    navbar = {"left": [{"text": "Reference", "href": "reference/"}]}
    quarto_yml = docs.build_dir / "_quarto.yml"
    quarto_yml.write_text(format_yaml({"website": {"navbar": navbar}}), encoding="utf-8")
    page = tmp_path / "user_guide" / relative
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Page\n---\n")
    guide_info = {
        "files": [{"path": page, "title": "Page", "section": None}],
        "source_dir": tmp_path / "user_guide",
        "sections": {},
        "has_index": False,
        "explicit": explicit,
        "explicit_config": [{"section": "Start", "contents": [relative]}],
    }

    _add_navigation(docs, guide_info)

    left = read_quarto_yml(docs.build_dir)["website"]["navbar"]["left"]
    assert {"text": "User Guide", "href": href} in left


def test_user_guide_navbar_link_targets_an_explicit_guide_first_page(tmp_path: Path):
    """
    Verify that the navbar targets the configured first page before a nested index
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    for relative in ("01-intro.qmd", "guides/index.qmd"):
        page = tmp_path / "user_guide" / relative
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntitle: Page\n---\n")
    write_config(
        tmp_path,
        "user_guide:\n  - section: Start\n    contents: [01-intro.qmd, guides/index.qmd]\n",
    )
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    navbar = {"left": [{"text": "Reference", "href": "reference/index.qmd"}]}
    write_quarto_yml(docs.build_dir, {"website": {"navbar": navbar}})
    guide = discover_user_guide(docs)
    assert guide is not None

    _add_navigation(docs, guide)

    left = read_quarto_yml(docs.build_dir)["website"]["navbar"]["left"]
    assert left[0] == {"text": "User Guide", "href": "user-guide/01-intro.qmd"}


# ---------------------------------------------------------------------------
# Sections step
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("settings", "outcome", "warning"),
    [
        ("", Skipped("no sections configured"), None),
        ("sections: not-a-list\n", "No sections to process", "must be a list"),
        ("sections:\n  - just a string\n", "No sections to process", "must be a dict"),
        ("sections:\n  - title: NoDir\n", "No sections to process", "missing 'title' or 'dir'"),
        ("sections:\n  - dir: recipes\n", "No sections to process", "missing 'title' or 'dir'"),
        (
            "sections:\n  - title: Recipes\n    dir: nonexistent\n",
            "No sections to process",
            "directory 'nonexistent' not found",
        ),
        (
            "sections:\n  - title: Recipes\n    dir: recipes\n",
            "No sections to process",
            "has no .qmd/.md files",
        ),
    ],
    ids=["none", "not-a-list", "not-a-mapping", "no-dir", "no-title", "missing-dir", "no-pages"],
)
def test_the_sections_step_publishes_nothing_without_a_usable_section(
    tmp_path: Path, capsys, settings: str, outcome: Outcome, warning: str | None
):
    docs = _project(
        tmp_path,
        {"great-docs.yml": settings, "recipes/notes.txt": "not a page\n"},
        NAVBAR_WITH_REFERENCE,
    )

    assert sections_step(docs, discover_user_guide(docs)) == outcome

    assert not (docs.build_dir / "recipes").exists()
    out = capsys.readouterr().out
    assert warning is None or warning in out


def test_the_sections_step_ignores_entries_that_are_not_mappings(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "great-docs.yml": "sections:\n  - title: Recipes\n    dir: recipes\n",
            "recipes/01-basic.qmd": "---\ntitle: Basic\n---\nContent.\n",
        },
        NAVBAR_WITH_REFERENCE,
    )
    docs._config._config["sections"] = ["not_a_dict", {"title": "Recipes", "dir": "recipes"}]

    assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"


def test_process_sections_discovers_and_copies():
    """
    Verify that sections publish pages, an index and navigation
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        config_path = project_path / "great-docs.yml"
        config_path.write_text(
            "sections:\n  - title: Examples\n    dir: examples\n    index: true\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        examples_dir = project_path / "examples"
        examples_dir.mkdir()
        (examples_dir / "01-basic.qmd").write_text(
            '---\ntitle: "Basic Example"\ndescription: "A basic demo"\n---\n\nHello\n'
        )
        (examples_dir / "02-advanced.qmd").write_text(
            '---\ntitle: "Advanced Example"\n---\n\nAdvanced content\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        result = sections_step(docs, discover_user_guide(docs))

        assert result == "1 section(s) processed"

        dest = build_dir / "examples"

        assert dest.exists()
        assert (dest / "basic.qmd").exists()
        assert (dest / "advanced.qmd").exists()

        index = dest / "index.qmd"

        assert index.exists()

        index_text = index.read_text()

        assert "Examples" in index_text
        assert "Basic Example" in index_text
        assert "Advanced Example" in index_text

        with open(quarto_yml) as f:
            config = read_yaml(f)
        navbar_texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]

        assert "Examples" in navbar_texts

        sidebar_ids = [s.get("id") for s in config["website"]["sidebar"] if isinstance(s, dict)]

        assert "examples" in sidebar_ids


def test_process_sections_no_index_by_default():
    """
    Verify that sections link to their first page without generating an index by default
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        config_path = project_path / "great-docs.yml"
        config_path.write_text("sections:\n  - title: Examples\n    dir: examples\n")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        examples_dir = project_path / "examples"
        examples_dir.mkdir()
        (examples_dir / "01-basic.qmd").write_text(
            '---\ntitle: "Basic Example"\ndescription: "A basic demo"\n---\n\nHello\n'
        )
        (examples_dir / "02-advanced.qmd").write_text(
            '---\ntitle: "Advanced Example"\n---\n\nAdvanced content\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        result = sections_step(docs, discover_user_guide(docs))

        assert result == "1 section(s) processed"

        dest = build_dir / "examples"

        assert dest.exists()
        assert (dest / "basic.qmd").exists()
        assert (dest / "advanced.qmd").exists()

        index = dest / "index.qmd"

        assert not index.exists(), "index.qmd should NOT be generated by default"

        with open(quarto_yml) as f:
            config = read_yaml(f)
        examples_item = next(
            item
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict) and item.get("text") == "Examples"
        )

        assert examples_item["href"] == "examples/basic.qmd"

        sidebar = next(
            s
            for s in config["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "examples"
        )
        sidebar_hrefs = [c["href"] for c in sidebar["contents"] if isinstance(c, dict)]

        assert "examples/index.qmd" not in sidebar_hrefs


@pytest.mark.parametrize("kind", ["default", "blog"])
def test_a_section_keeps_its_own_index_page(tmp_path: Path, kind: str):
    docs = _project(
        tmp_path,
        {
            "great-docs.yml": f"sections:\n  - title: Demos\n    dir: demos\n    type: {kind}\n",
            "demos/index.qmd": '---\ntitle: "My Custom Index"\n---\n\nCustom gallery content\n',
            "demos/demo1.qmd": '---\ntitle: "Demo One"\ndate: 2024-01-01\n---\n\nDemo\n',
        },
        NAVBAR_WITH_REFERENCE,
    )

    assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"

    assert "Custom gallery content" in (docs.build_dir / "demos" / "index.qmd").read_text()


def test_a_blog_section_gets_a_generated_index(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "great-docs.yml": "sections:\n  - title: Blog\n    dir: blog\n    type: blog\n",
            "blog/post1.qmd": "---\ntitle: First Post\ndate: 2024-01-01\n---\nHello\n",
        },
        NAVBAR_WITH_REFERENCE,
    )

    assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"

    assert (docs.build_dir / "blog" / "index.qmd").exists()
    assert (docs.build_dir / "blog" / "post1.qmd").exists()


def test_a_section_with_only_an_index_page_links_to_it(tmp_path: Path):
    docs = _project(
        tmp_path,
        {
            "great-docs.yml": "sections:\n  - title: Tutorials\n    dir: tutorials\n",
            "tutorials/index.qmd": "---\ntitle: Tutorials\n---\nWelcome.\n",
        },
        {"project": {"type": "website"}, "website": {"navbar": {"left": []}}},
    )

    assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"

    left = read_quarto_yml(docs.build_dir)["website"]["navbar"]["left"]
    assert left == [{"text": "Tutorials", "href": "tutorials/index.qmd"}]


def test_process_sections_navbar_after():
    """
    Verify that `navbar_after` places a section link after the named item
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Tutorials\n    dir: tutorials\n    navbar_after: User Guide\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: User Guide\n"
            "        href: user-guide/index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        tut_dir = project_path / "tutorials"
        tut_dir.mkdir()
        (tut_dir / "intro.qmd").write_text('---\ntitle: "Intro"\n---\n\nIntro\n')

        docs = GreatDocs(project_path=tmp_dir)
        sections_step(docs, discover_user_guide(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]

        assert texts.index("Tutorials") == texts.index("User Guide") + 1
        assert texts.index("Tutorials") < texts.index("Reference")


def test_process_sections_default_navbar_before_reference():
    """
    Verify that section links precede Reference by default
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: User Guide\n"
            "        href: user-guide/index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "demo.qmd").write_text('---\ntitle: "Demo"\n---\n\nDemo\n')

        docs = GreatDocs(project_path=tmp_dir)
        sections_step(docs, discover_user_guide(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]

        assert texts.index("Examples") < texts.index("Reference")


def test_process_sections_multiple():
    """
    Verify that a build publishes every configured section
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n"
            "  - title: Examples\n"
            "    dir: examples\n"
            "  - title: Tutorials\n"
            "    dir: tutorials\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        for d in ("examples", "tutorials"):
            (project_path / d).mkdir()
            (project_path / d / "page.qmd").write_text(f'---\ntitle: "{d} page"\n---\n\n{d}\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = sections_step(docs, discover_user_guide(docs))

        assert result == "2 section(s) processed"

        with open(quarto_yml) as f:
            config = read_yaml(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]

        assert "Examples" in texts
        assert "Tutorials" in texts


def test_process_sections_idempotent():
    """
    Verify that repeated publication keeps one navbar link and sidebar per section
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')
        (ex_dir / "page2.qmd").write_text('---\ntitle: "Page 2"\n---\n\nMore\n')

        docs = GreatDocs(project_path=tmp_dir)
        sections_step(docs, discover_user_guide(docs))
        sections_step(docs, discover_user_guide(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)

        example_links = [
            item
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict) and item.get("text") == "Examples"
        ]

        assert len(example_links) == 1

        example_sidebars = [
            s
            for s in config["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "examples"
        ]

        assert len(example_sidebars) == 1


def test_process_sections_replaces_a_sidebar_with_the_same_id(tmp_path: Path):
    write_config(tmp_path, "sections:\n  - title: Recipes\n    dir: recipes\n")
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "new1.qmd").write_text("---\ntitle: New 1\n---\n")
    (tmp_path / "recipes" / "new2.qmd").write_text("---\ntitle: New 2\n---\n")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir()
    old = {"id": "recipes", "title": "Old", "contents": ["old.qmd"]}
    other = {"id": "other", "title": "Other", "contents": ["other.qmd"]}
    with open(docs.build_dir / "_quarto.yml", "w") as f:
        write_yaml({"website": {"sidebar": [old, other], "navbar": {"left": []}}}, f)

    sections_step(docs, discover_user_guide(docs))

    sidebar = read_quarto_yml(docs.build_dir)["website"]["sidebar"]
    assert [entry["title"] for entry in sidebar] == ["Other", "Recipes"]


def test_process_sections_finds_the_user_guide_once(tmp_path: Path, capsys):
    """
    Report a missing user guide once across multiple sections and links
    """
    write_config(
        tmp_path,
        "user_guide: missing_guide\n"
        "sections:\n"
        "  - title: Examples\n    dir: examples\n"
        "  - title: More\n    dir: more\n",
    )
    for name in ("examples", "more"):
        (tmp_path / name).mkdir()
        for index in range(3):
            (tmp_path / name / f"page{index}.qmd").write_text(
                "[One](page0.qmd) [Two](page1.qmd) [Three](page2.qmd)\n"
            )
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir()

    sections_step(docs, discover_user_guide(docs))

    assert capsys.readouterr().out.count("'missing_guide'") == 1


def test_process_sections_copies_asset_directories():
    """
    Verify that section publication copies asset directories and their contents
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')

        data_dir = ex_dir / "data"
        data_dir.mkdir()
        (data_dir / "game_revenue.parquet").write_bytes(b"fake-parquet-data")
        (data_dir / "scores.csv").write_text("a,b\n1,2\n")

        img_dir = ex_dir / "img"
        img_dir.mkdir()
        (img_dir / "diagram.png").write_bytes(b"fake-png")

        docs = GreatDocs(project_path=tmp_dir)
        result = sections_step(docs, discover_user_guide(docs))

        assert result == "1 section(s) processed"

        dest = build_dir / "examples"
        assert dest.exists()

        assert (dest / "data").is_dir()
        assert (dest / "data" / "game_revenue.parquet").exists()
        assert (dest / "data" / "scores.csv").exists()
        assert (dest / "img").is_dir()
        assert (dest / "img" / "diagram.png").exists()

        assert (dest / "data" / "game_revenue.parquet").read_bytes() == b"fake-parquet-data"
        assert (dest / "data" / "scores.csv").read_text() == "a,b\n1,2\n"


def test_process_sections_skips_dirs_with_qmd_files():
    """
    Verify that page directories publish their pages without copying other files as assets
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')

        # A directory containing a `.qmd` file is not copied as an asset directory,
        # but its `.qmd` files are still published as pages.
        sub_dir = ex_dir / "subpages"
        sub_dir.mkdir()
        (sub_dir / "nested.qmd").write_text('---\ntitle: "Nested"\n---\n\nNested\n')
        (sub_dir / "notes.txt").write_text("should not be asset-copied")

        assets_dir = ex_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "style.css").write_text("body { color: red; }\n")

        docs = GreatDocs(project_path=tmp_dir)
        sections_step(docs, discover_user_guide(docs))

        dest = build_dir / "examples"

        assert (dest / "assets").is_dir()
        assert (dest / "assets" / "style.css").exists()

        # Only the `.qmd` files in this directory are published; its other files
        # are not copied as assets.
        assert not (dest / "subpages" / "notes.txt").exists()


def test_process_sections_asset_dirs_refreshed_on_rebuild():
    """
    Verify that rebuilding replaces stale section assets
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')

        data_dir = ex_dir / "data"
        data_dir.mkdir()
        (data_dir / "old_file.txt").write_text("old")

        docs = GreatDocs(project_path=tmp_dir)
        sections_step(docs, discover_user_guide(docs))

        dest = build_dir / "examples"
        assert (dest / "data" / "old_file.txt").exists()

        (data_dir / "old_file.txt").unlink()
        (data_dir / "new_file.txt").write_text("new")

        sections_step(docs, discover_user_guide(docs))

        assert not (dest / "data" / "old_file.txt").exists()
        assert (dest / "data" / "new_file.txt").exists()
        assert (dest / "data" / "new_file.txt").read_text() == "new"


def test_process_sections_copies_directory_metadata():
    """
    Verify that section metadata follows pages into directories without numeric prefixes
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        build_dir = _write_section_project(project_path, "examples")

        topic = project_path / "examples" / "01-topic"
        topic.mkdir(parents=True)
        (topic.parent / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')
        (topic.parent / "_metadata.yml").write_text("toc: false\n")
        (topic / "01-sub.qmd").write_text('---\ntitle: "Sub"\n---\n\nContent\n')
        (topic / "_metadata.yml").write_text("number-sections: true\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"

        dest = build_dir / "examples"
        assert (dest / "_metadata.yml").read_text() == "toc: false\n"
        assert (dest / "topic" / "_metadata.yml").read_text() == "number-sections: true\n"


def test_directory_metadata_keeps_build_written_file(capsys):
    """
    Verify that existing build metadata is preserved and the skipped source is reported
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        build_dir = _write_section_project(project_path, "reference")
        (build_dir / "reference").mkdir()
        build_metadata = build_dir / "reference" / "_metadata.yml"
        build_metadata.write_text("date: 2026-01-01\n")

        section = project_path / "reference"
        section.mkdir()
        (section / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')
        (section / "_metadata.yml").write_text("toc: false\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert sections_step(docs, discover_user_guide(docs)) == "1 section(s) processed"

        assert build_metadata.read_text() == "date: 2026-01-01\n"
        assert "reference/_metadata.yml" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Custom pages step
# ---------------------------------------------------------------------------


def test_process_custom_pages_passthrough_and_raw():
    """
    Verify that passthrough HTML becomes a Quarto page and raw HTML stays unchanged
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)

        custom_dir = tmp / "custom"
        custom_dir.mkdir()
        (custom_dir / "landing.html").write_text(
            "---\n"
            'title: "Landing"\n'
            "layout: passthrough\n"
            "---\n"
            '<section class="hero">\n'
            "  <h1>Custom Hero</h1>\n"
            "</section>\n",
            encoding="utf-8",
        )
        (custom_dir / "widget.html").write_text(
            "---\nlayout: raw\n---\n<html><body>Widget</body></html>\n",
            encoding="utf-8",
        )
        (custom_dir / "app.js").write_text("console.log('custom');\n", encoding="utf-8")

        result = custom_pages_step(docs, discover_user_guide(docs))

        assert result == "2 custom page(s)"

        passthrough = docs.build_dir / "custom" / "landing.qmd"
        raw = docs.build_dir / "custom" / "widget.html"
        asset = docs.build_dir / "custom" / "app.js"

        assert passthrough.exists()
        assert raw.exists()
        assert asset.exists()

        passthrough_text = passthrough.read_text(encoding="utf-8")
        assert "title: Landing" in passthrough_text
        assert "layout:" not in passthrough_text
        assert "bread-crumbs: false" in passthrough_text
        assert "bread-crumbs: false\n---\n\n<section" in passthrough_text
        assert '<section class="hero">' in passthrough_text

        raw_text = raw.read_text(encoding="utf-8")
        assert raw_text == "<html><body>Widget</body></html>\n"

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        resources = config["project"]["resources"]
        render = config["project"]["render"]

        assert "custom/app.js" in resources
        assert "custom/widget.html" in resources
        assert "!custom/widget.html" in render
        # A recursive `**` overrides the `!` exclusions; use Quarto's default input globs.
        assert "**" not in render
        assert "*.qmd" in render


@pytest.mark.parametrize(
    "settings", ["", "custom_pages: false\n"], ids=["no-directory", "disabled"]
)
def test_the_custom_pages_step_skips_a_project_without_custom_pages(tmp_path: Path, settings: str):
    """
    Verify that `custom_pages: false` disables the conventional `custom/` directory
    """
    docs = _project(
        tmp_path,
        {"great-docs.yml": settings},
        {"website": {"sidebar": [], "navbar": {"left": []}}},
    )
    if settings:
        _write_files(tmp_path, {"custom/landing.html": "---\nlayout: passthrough\n---\n<p>L</p>\n"})

    assert custom_pages_step(docs, discover_user_guide(docs)) == Skipped("no custom pages")

    assert not (docs.build_dir / "custom").exists()


def test_process_custom_pages_respects_configured_output_prefix():
    """
    Verify that custom pages use their configured output URL prefix
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "great-docs.yml").write_text(
            "custom_pages:\n  dir: marketing\n  output: py\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)

        marketing_dir = tmp / "marketing"
        marketing_dir.mkdir()
        (marketing_dir / "landing.html").write_text(
            "---\n"
            'title: "Shiny for Python"\n'
            "layout: passthrough\n"
            "navbar: true\n"
            "---\n"
            "<section>Landing</section>\n",
            encoding="utf-8",
        )
        (marketing_dir / "app.js").write_text("console.log('marketing');\n", encoding="utf-8")

        result = custom_pages_step(docs, discover_user_guide(docs))

        assert result == "1 custom page(s)"
        assert (docs.build_dir / "py" / "landing.qmd").exists()
        assert (docs.build_dir / "py" / "app.js").exists()

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        resources = config["project"]["resources"]
        navbar_items = config["website"]["navbar"]["left"]
        landing = next(
            item
            for item in navbar_items
            if isinstance(item, dict) and item.get("text") == "Shiny for Python"
        )

        assert "py/app.js" in resources
        assert landing["href"] == "py/landing.qmd"


def test_process_custom_pages_supports_multiple_directories():
    """
    Verify that a build publishes custom pages from multiple source directories
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "great-docs.yml").write_text(
            "custom_pages:\n"
            "  - dir: marketing\n"
            "    output: py\n"
            "  - dir: playgrounds\n"
            "    output: demos\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml(
                {
                    "website": {
                        "sidebar": [],
                        "navbar": {"left": [{"text": "Guide", "href": "guide/index.qmd"}]},
                    }
                },
                f,
            )

        marketing_dir = tmp / "marketing"
        marketing_dir.mkdir()
        (marketing_dir / "landing.html").write_text(
            "---\nlayout: passthrough\nnavbar: true\n---\n<section>Landing</section>\n",
            encoding="utf-8",
        )

        playgrounds_dir = tmp / "playgrounds"
        playgrounds_dir.mkdir()
        (playgrounds_dir / "showcase.html").write_text(
            "---\nlayout: raw\nnavbar:\n  text: Showcase\n  after: Guide\n---\n"
            "<html><body>Showcase</body></html>\n",
            encoding="utf-8",
        )

        result = custom_pages_step(docs, discover_user_guide(docs))

        assert result == "2 custom page(s)"
        assert (docs.build_dir / "py" / "landing.qmd").exists()
        assert (docs.build_dir / "demos" / "showcase.html").exists()

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in items if isinstance(item, dict)]
        showcase = next(
            item for item in items if isinstance(item, dict) and item.get("text") == "Showcase"
        )

        assert showcase["href"] == "demos/showcase.html"
        assert texts == ["Guide", "Showcase", "Landing"]


def test_process_custom_pages_supports_nested_output_prefixes():
    """
    Verify that custom pages support nested output URL prefixes
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "great-docs.yml").write_text(
            "custom_pages:\n  dir: apps\n  output: products/python\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)

        apps_dir = tmp / "apps"
        apps_dir.mkdir()
        (apps_dir / "start.html").write_text(
            "---\n"
            'title: "Python Apps"\n'
            "layout: passthrough\n"
            "navbar: true\n"
            "---\n"
            "<section>Apps</section>\n",
            encoding="utf-8",
        )
        (apps_dir / "assets").mkdir()
        (apps_dir / "assets" / "widget.js").write_text("window.APPS = true;\n", encoding="utf-8")

        result = custom_pages_step(docs, discover_user_guide(docs))

        assert result == "1 custom page(s)"
        assert (docs.build_dir / "products" / "python" / "start.qmd").exists()
        assert (docs.build_dir / "products" / "python" / "assets" / "widget.js").exists()

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        resources = config["project"]["resources"]
        navbar_items = config["website"]["navbar"]["left"]
        page = next(
            item
            for item in navbar_items
            if isinstance(item, dict) and item.get("text") == "Python Apps"
        )

        assert "products/python/assets/widget.js" in resources
        assert page["href"] == "products/python/start.qmd"


def test_process_custom_pages_skips_missing_configured_directories():
    """
    Verify that missing custom page directories leave valid directories publishable
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "great-docs.yml").write_text(
            "custom_pages:\n"
            "  - dir: ghost-pages\n"
            "    output: ghost\n"
            "  - dir: playgrounds\n"
            "    output: demos\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)

        playgrounds_dir = tmp / "playgrounds"
        playgrounds_dir.mkdir()
        (playgrounds_dir / "widget.html").write_text(
            "---\nlayout: raw\nnavbar: Widget Lab\n---\n<html><body>Widget</body></html>\n",
            encoding="utf-8",
        )

        result = custom_pages_step(docs, discover_user_guide(docs))

        assert result == "1 custom page(s)"
        assert not (docs.build_dir / "ghost").exists()
        assert (docs.build_dir / "demos" / "widget.html").exists()

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        resources = config["project"]["resources"]
        assert "demos/widget.html" in resources
        assert all(not resource.startswith("ghost/") for resource in resources)


def test_process_custom_pages_ignores_frontmatter_after_leading_blank_lines():
    """
    Verify that leading blank lines prevent front matter parsing
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml(
                {
                    "website": {
                        "sidebar": [],
                        "navbar": {
                            "left": [
                                {"text": "Home", "href": "index.qmd"},
                                {"text": "Reference", "href": "reference/index.qmd"},
                            ]
                        },
                    }
                },
                f,
            )

        custom_dir = tmp / "custom"
        custom_dir.mkdir()
        (custom_dir / "landing.html").write_text(
            "\n\n---\n"
            'title: "Landing"\n'
            "layout: passthrough\n"
            "navbar: true\n"
            "---\n"
            "<section>Landing</section>\n",
            encoding="utf-8",
        )

        custom_pages_step(docs, discover_user_guide(docs))

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        items = config["website"]["navbar"]["left"]
        assert not any(isinstance(item, dict) and item.get("text") == "Landing" for item in items)


def test_process_custom_pages_adds_passthrough_navbar_link():
    """
    Verify that passthrough pages can use their titles as navbar labels
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml(
                {
                    "website": {
                        "sidebar": [],
                        "navbar": {
                            "left": [
                                {"text": "Home", "href": "index.qmd"},
                                {"text": "Reference", "href": "reference/index.qmd"},
                            ]
                        },
                    }
                },
                f,
            )

        custom_dir = tmp / "custom"
        custom_dir.mkdir()
        (custom_dir / "landing.html").write_text(
            "---\n"
            'title: "Shiny for Python"\n'
            "layout: passthrough\n"
            "navbar: true\n"
            "---\n"
            "<section>Landing</section>\n",
            encoding="utf-8",
        )

        custom_pages_step(docs, discover_user_guide(docs))

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in items if isinstance(item, dict)]
        landing = next(
            item
            for item in items
            if isinstance(item, dict) and item.get("text") == "Shiny for Python"
        )

        assert landing["href"] == "custom/landing.qmd"
        assert texts.index("Shiny for Python") < texts.index("Reference")


def test_process_custom_pages_adds_raw_navbar_link_with_custom_text():
    """
    Verify that raw pages can set navbar labels and placement in front matter
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with open(docs.build_dir / "_quarto.yml", "w") as f:
            write_yaml(
                {
                    "website": {
                        "sidebar": [],
                        "navbar": {
                            "left": [
                                {"text": "Guide", "href": "guide/index.qmd"},
                                {"text": "Reference", "href": "reference/index.qmd"},
                            ]
                        },
                    }
                },
                f,
            )

        custom_dir = tmp / "custom"
        custom_dir.mkdir()
        (custom_dir / "showcase.html").write_text(
            "---\n"
            "layout: raw\n"
            "navbar:\n"
            "  text: Showcase\n"
            "  after: Guide\n"
            "---\n"
            "<html><body>Showcase</body></html>\n",
            encoding="utf-8",
        )

        custom_pages_step(docs, discover_user_guide(docs))

        with open(docs.build_dir / "_quarto.yml") as f:
            config = read_yaml(f)

        items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in items if isinstance(item, dict)]
        showcase = next(
            item for item in items if isinstance(item, dict) and item.get("text") == "Showcase"
        )

        assert showcase["href"] == "custom/showcase.html"
        assert texts == ["Guide", "Showcase", "Reference"]


# ---------------------------------------------------------------------------
# Assets step
# ---------------------------------------------------------------------------


def test_the_assets_step_copies_the_assets_tree(tmp_path: Path, capsys):
    files = {
        "assets/image.png": "fake png content",
        "assets/images/icons/star.svg": "<svg>star</svg>",
        "assets/css/theme.css": "/* theme */",
    }
    docs = _project(tmp_path, {"pyproject.toml": '[project]\nname = "test"\n', **files})

    assert _assets(docs) == "Assets copied"

    for name, text in files.items():
        assert (docs.build_dir / name).read_text() == text
    assert "Copied 3 asset file(s) to great-docs/assets/" in capsys.readouterr().out


def test_the_assets_step_replaces_an_earlier_copy(tmp_path: Path):
    docs = _project(
        tmp_path,
        {"assets/new_file.txt": "new content", "great-docs/assets/old_file.txt": "old content"},
    )

    assert _assets(docs) == "Assets copied"

    assert not (docs.build_dir / "assets" / "old_file.txt").exists()
    assert (docs.build_dir / "assets" / "new_file.txt").read_text() == "new content"


@pytest.mark.parametrize("has_assets", [True, False])
def test_the_assets_step_completes_the_quarto_configuration(tmp_path: Path, has_assets: bool):
    """
    Register `assets/**` as a resource only when the project has an assets directory
    """
    docs = _project(tmp_path, {"pyproject.toml": '[project]\nname = "test"\n'})
    if has_assets:
        _write_files(tmp_path, {"assets/image.png": "fake image"})
    write_initial_quarto_yml(docs.build_dir)
    run = make_run(docs)
    update_quarto_config(docs, run)
    assert "assets/**" not in run.quarto_config["project"]["resources"]

    outcome = content.assets(run, docs._config, docs.layout, remote=docs._remote)

    assert outcome == ("Assets copied" if has_assets else Skipped("no assets directory"))
    resources = run.quarto_config["project"]["resources"]
    assert ("assets/**" in resources) is has_assets


def test_the_assets_step_adds_the_recorded_contributions_before_ordering_the_navbar(
    tmp_path: Path,
):
    """
    Add an earlier step's navbar link before applying `navbar_order`
    """
    docs = _project(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "test"\n',
            "great-docs.yml": "navbar_order: [Changelog]\n",
        },
    )
    write_initial_quarto_yml(docs.build_dir)
    run = make_run(docs)
    update_quarto_config(docs, run)
    run.quarto_config["website"]["navbar"]["left"] = [{"text": "Examples", "href": "ex.qmd"}]
    run.contributions.append(Contribution(navbar=(NavbarLink("Changelog", "changelog.qmd"),)))

    _ = content.assets(run, docs._config, docs.layout, remote=docs._remote)

    left = run.quarto_config["website"]["navbar"]["left"]
    assert [item["text"] for item in left] == ["Changelog", "Examples"]
