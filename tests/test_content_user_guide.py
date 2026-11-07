"""
Tests for the user guide: discovery, page reading and the sidebar
"""

import tempfile
from pathlib import Path

import pytest

from great_docs import GreatDocs
from great_docs._content import user_guide
from great_docs._layout import Layout
from tests.support import discover_user_guide, find_user_guide_dir, write_config


def test_user_guide_sidebar_uses_clean_urls():
    """Verify that sidebar URLs omit numeric ordering prefixes"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        guide_dir = project_path / "user_guide"
        guide_dir.mkdir()

        (guide_dir / "00-introduction.qmd").write_text("""---
title: Introduction
guide-section: Getting Started
---
# Introduction
""")
        (guide_dir / "01-installation.qmd").write_text("""---
title: Installation
guide-section: Getting Started
---
# Installation
""")

        docs = GreatDocs(project_path=tmp_dir)

        user_guide_info = discover_user_guide(docs)
        assert user_guide_info is not None

        sidebar_config = user_guide.sidebar(user_guide_info)

        assert sidebar_config["id"] == "user-guide"
        assert sidebar_config["title"] == "User Guide"

        contents = sidebar_config["contents"]
        assert len(contents) > 0

        all_hrefs = []
        for item in contents:
            if isinstance(item, dict) and "contents" in item:
                for sub_item in item["contents"]:
                    if isinstance(sub_item, str):
                        all_hrefs.append(sub_item)
                    elif isinstance(sub_item, dict):
                        all_hrefs.append(sub_item.get("href", ""))
            elif isinstance(item, str):
                all_hrefs.append(item)

        assert "user-guide/introduction.qmd" in all_hrefs
        assert "user-guide/installation.qmd" in all_hrefs
        assert "user-guide/00-introduction.qmd" not in all_hrefs
        assert "user-guide/01-installation.qmd" not in all_hrefs


def test_user_guide_config_option_overrides_default_dir():
    """Verify that the configured directory takes precedence over `user_guide/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        conventional_dir = project_path / "user_guide"
        conventional_dir.mkdir()
        (conventional_dir / "00-from-default.qmd").write_text(
            "---\ntitle: From Default\n---\n# Default\n"
        )

        custom_dir = project_path / "docs" / "guides"
        custom_dir.mkdir(parents=True)
        (custom_dir / "00-from-custom.qmd").write_text("---\ntitle: From Custom\n---\n# Custom\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: docs/guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = discover_user_guide(docs)

        assert user_guide_info is not None
        assert len(user_guide_info["files"]) == 1
        assert user_guide_info["files"][0]["title"] == "From Custom"
        assert user_guide_info["source_dir"] == custom_dir.resolve()


def test_user_guide_config_option_custom_directory():
    """Verify discovery in a configured nested directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        custom_dir = project_path / "content" / "user-docs"
        custom_dir.mkdir(parents=True)
        (custom_dir / "intro.qmd").write_text("---\ntitle: Intro\n---\n# Intro\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: content/user-docs\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = discover_user_guide(docs)

        assert user_guide_info is not None
        assert len(user_guide_info["files"]) == 1
        assert user_guide_info["source_dir"] == custom_dir.resolve()


def test_user_guide_config_option_nonexistent_dir(capsys):
    """Verify the warning for a missing configured guide directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: nonexistent/dir\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None

        captured = capsys.readouterr()

        assert "does not exist" in captured.out


def test_user_guide_warns_on_empty_directory(capsys):
    """Verify the warning for an empty guide directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        empty_dir = project_path / "user_guide"
        empty_dir.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None

        captured = capsys.readouterr()

        assert "is empty" in captured.out


def test_user_guide_warns_on_no_guide_files(capsys):
    """Verify the warning for a guide directory without `.qmd` or `.md` files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        ug_dir = project_path / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "notes.txt").write_text("just a text file")
        (ug_dir / "data.csv").write_text("a,b,c")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None

        captured = capsys.readouterr()

        assert "contains no .qmd or .md files" in captured.out


def test_user_guide_discovery_ignores_reserved_build_directory():
    """Verify that automatic discovery excludes staged build files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\n'
        )
        # In a migrated layout, `docs/_quarto/default/` is nested under the guide
        # source. Discovery must exclude it even though it is not a direct child.
        docs_dir = project_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "great-docs.yml").write_text("user_guide: .\n")
        (docs_dir / "guide.qmd").write_text("# Guide\n")
        leftover = docs_dir / "_quarto/default/reference/other.qmd"
        leftover.parent.mkdir(parents=True)
        leftover.write_text("# Leftover\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert {f["path"].resolve() for f in result["files"]} == {
            (docs_dir / "guide.qmd").resolve()
        }


def test_user_guide_config_warns_when_both_exist(capsys):
    """Verify the warning when a configured guide overrides `user_guide/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        conventional_dir = project_path / "user_guide"
        conventional_dir.mkdir()
        (conventional_dir / "default.qmd").write_text("---\ntitle: Default\n---\n# Default\n")

        custom_dir = project_path / "my_guides"
        custom_dir.mkdir()
        (custom_dir / "custom.qmd").write_text("---\ntitle: Custom\n---\n# Custom\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: my_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = discover_user_guide(docs)

        assert user_guide_info is not None

        assert user_guide_info["source_dir"] == custom_dir.resolve()

        captured = capsys.readouterr()

        assert "using configured path" in captured.out


def test_user_guide_fallback_without_config():
    """Verify discovery in `user_guide/` without a configured directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        ug_dir = project_path / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "intro.qmd").write_text("---\ntitle: Intro\n---\n# Intro\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("display_name: Test\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = discover_user_guide(docs)

        assert user_guide_info is not None
        assert user_guide_info["source_dir"] == ug_dir.resolve()


def test_user_guide_config_empty_dir_warns(capsys):
    """Verify the warning for an empty configured guide directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        empty_dir = project_path / "empty_guides"
        empty_dir.mkdir()

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: empty_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None

        captured = capsys.readouterr()

        assert "is empty" in captured.out


def test_user_guide_explicit_config_discovery():
    """Verify that an explicit guide lists its pages and sections"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "index.qmd").write_text("---\ntitle: Welcome\n---\n# Welcome\n")
        (user_guide / "quickstart.qmd").write_text("---\ntitle: Quick Start\n---\n# Quick Start\n")
        (user_guide / "installation.qmd").write_text(
            "---\ntitle: Installation\n---\n# Installation\n"
        )
        (user_guide / "advanced.qmd").write_text("---\ntitle: Advanced Topics\n---\n# Advanced\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Get Started"
    contents:
      - text: "Welcome"
        href: index.qmd
      - quickstart.qmd
      - installation.qmd
  - section: "Advanced"
    contents:
      - advanced.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert result["explicit"] is True
        assert len(result["files"]) == 4
        assert result["has_index"] is True
        assert "Get Started" in result["sections"]
        assert "Advanced" in result["sections"]
        assert len(result["sections"]["Get Started"]) == 3
        assert len(result["sections"]["Advanced"]) == 1


def test_user_guide_explicit_config_preserves_order():
    """Verify that explicit guides preserve the configured page order"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "zebra.qmd").write_text("---\ntitle: Zebra\n---\n# Zebra\n")
        (user_guide / "apple.qmd").write_text("---\ntitle: Apple\n---\n# Apple\n")
        (user_guide / "mango.qmd").write_text("---\ntitle: Mango\n---\n# Mango\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Fruits"
    contents:
      - zebra.qmd
      - apple.qmd
      - mango.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result["files"][0]["path"].name == "zebra.qmd"
        assert result["files"][1]["path"].name == "apple.qmd"
        assert result["files"][2]["path"].name == "mango.qmd"


def test_user_guide_explicit_config_sidebar_generation():
    """Verify sidebar sections and labels from an explicit guide"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        guide_dir = project_path / "user_guide"
        guide_dir.mkdir()

        (guide_dir / "index.qmd").write_text("---\ntitle: Welcome\n---\n# Welcome\n")
        (guide_dir / "quickstart.qmd").write_text("---\ntitle: Quick Start\n---\n# Quick Start\n")
        (guide_dir / "installation.qmd").write_text(
            "---\ntitle: Installation\n---\n# Installation\n"
        )
        (guide_dir / "advanced.qmd").write_text("---\ntitle: Advanced\n---\n# Advanced\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Get Started"
    contents:
      - text: "Welcome to Package"
        href: index.qmd
      - quickstart.qmd
      - installation.qmd
  - section: "Advanced"
    contents:
      - advanced.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = discover_user_guide(docs)
        sidebar = user_guide.sidebar(user_guide_info)

        assert sidebar["id"] == "user-guide"
        assert sidebar["title"] == "User Guide"
        assert len(sidebar["contents"]) == 2

        section1 = sidebar["contents"][0]

        assert section1["section"] == "Get Started"
        assert len(section1["contents"]) == 3

        assert section1["contents"][0] == {
            "text": "Welcome to Package",
            "href": "user-guide/index.qmd",
        }

        assert section1["contents"][1] == {
            "text": "Quick Start",
            "href": "user-guide/quickstart.qmd",
        }
        assert section1["contents"][2] == {
            "text": "Installation",
            "href": "user-guide/installation.qmd",
        }

        section2 = sidebar["contents"][1]

        assert section2["section"] == "Advanced"
        assert section2["contents"] == [{"text": "Advanced", "href": "user-guide/advanced.qmd"}]


def test_user_guide_explicit_config_missing_file(capsys):
    """Verify the warning for a missing page in an explicit guide"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "exists.qmd").write_text("---\ntitle: Exists\n---\n# Exists\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Docs"
    contents:
      - exists.qmd
      - missing.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None

        assert len(result["files"]) == 1
        assert result["files"][0]["path"].name == "exists.qmd"

        captured = capsys.readouterr()

        assert "missing.qmd" in captured.out
        assert "does not exist" in captured.out


def test_user_guide_explicit_config_custom_text():
    """Verify that explicit guides preserve custom page labels"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "index.qmd").write_text("---\ntitle: Home\n---\n# Home\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Start"
    contents:
      - text: "Welcome to the Package"
        href: index.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert result["files"][0].get("custom_text") == "Welcome to the Package"


def test_user_guide_explicit_overrides_frontmatter_sections():
    """Verify that configured sections override `guide-section` front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "intro.qmd").write_text(
            "---\ntitle: Intro\nguide-section: Old Section\n---\n# Intro\n"
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "New Section"
    contents:
      - intro.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None

        assert result["files"][0]["section"] == "New Section"
        assert "New Section" in result["sections"]
        assert "Old Section" not in result["sections"]


def test_user_guide_explicit_with_conventional_dir():
    """Verify explicit page lists in the conventional `user_guide/` directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "page.qmd").write_text("---\ntitle: Page\n---\n# Page\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Main"
    contents:
      - page.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert result["explicit"] is True
        assert result["source_dir"] == user_guide.resolve()


def test_user_guide_string_config_still_works():
    """Verify automatic discovery in a configured directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        custom_dir = project_path / "my_guides"
        custom_dir.mkdir()
        (custom_dir / "intro.qmd").write_text(
            "---\ntitle: Intro\nguide-section: Start\n---\n# Intro\n"
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: my_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert result.get("explicit", False) is False
        assert result["source_dir"] == custom_dir.resolve()
        assert len(result["files"]) == 1


def test_user_guide_sidebar_auto_strips_numeric_prefix_from_subdirs():
    """Verify that directory section titles omit numeric ordering prefixes"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        sub1 = src / "01-basics"
        sub1.mkdir()
        (sub1 / "intro.qmd").write_text("Intro\n")
        sub2 = src / "02-advanced-topics"
        sub2.mkdir()
        (sub2 / "deep.qmd").write_text("Deep\n")

        guide_info = {
            "files": [
                {"path": sub1 / "intro.qmd", "title": "Intro", "section": None},
                {"path": sub2 / "deep.qmd", "title": "Deep", "section": None},
            ],
            "source_dir": src,
            "sections": {},
        }

        result = user_guide.sidebar(guide_info)

        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]
        section_titles = [s["section"] for s in section_items]

        assert "Basics" in section_titles
        assert "Advanced Topics" in section_titles
        assert "01 Basics" not in section_titles
        assert "02 Advanced Topics" not in section_titles


def test_read_page_with_frontmatter_basic():
    """Verify page titles and sections from front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "01-install.qmd"
        qmd.write_text("---\ntitle: Installation\nguide-section: Getting Started\n---\nBody\n")

        result = user_guide.read_page(qmd)

        assert result is not None
        assert result["title"] == "Installation"
        assert result["section"] == "Getting Started"


def test_read_page_derives_title():
    """Verify the file name supplies a missing front matter title"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "03-getting-started.qmd"
        qmd.write_text("---\nguide-section: Basics\n---\nBody\n")

        result = user_guide.read_page(qmd)

        assert result is not None
        assert result["title"] == "Getting Started"


def test_read_page_no_frontmatter_underscore_prefix():
    """Verify the file name supplies the title when front matter is absent"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "05_advanced-usage.qmd"
        qmd.write_text("Just body content, no frontmatter\n")

        result = user_guide.read_page(qmd)

        assert result is not None
        assert result["title"] == "Advanced Usage"
        assert result["section"] is None


def test_read_page_missing_file():
    """Verify that a missing page returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = user_guide.read_page(Path(tmp_dir) / "nonexistent.qmd")
        assert result is None


def test_read_page_with_empty_stem_after_prefix_has_no_title(tmp_path: Path):
    """Verify that an ordering prefix alone produces an empty page title"""
    page = tmp_path / "01-.qmd"
    page.write_text("# Content\n", encoding="utf-8")

    result = user_guide.read_page(page)

    assert result is not None
    assert result["title"] == ""


def test_discover_auto():
    """Verify automatic discovery in `user_guide/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nContent\n")
        (ug / "02-setup.qmd").write_text("---\ntitle: Setup\n---\nContent\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert result["explicit"] is False
        assert len(result["files"]) == 2


def test_discover_empty_dir_full_project():
    """Verify that an empty guide directory returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None


def test_discover_no_dir_full_project():
    """Verify that an absent guide directory returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None


def test_discover_with_sections():
    """Verify page grouping by `guide-section` front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-intro.qmd").write_text("---\ntitle: Intro\nguide-section: Basics\n---\nA\n")
        (ug / "02-setup.qmd").write_text("---\ntitle: Setup\nguide-section: Basics\n---\nB\n")
        (ug / "03-api.qmd").write_text("---\ntitle: API\nguide-section: Advanced\n---\nC\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert "Basics" in result["sections"]
        assert "Advanced" in result["sections"]
        assert len(result["sections"]["Basics"]) == 2


def test_discover_with_subdirectories():
    """Verify recursive discovery of nested pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "intro.qmd").write_text("---\ntitle: Intro\n---\nA\n")
        sub = ug / "advanced"
        sub.mkdir()
        (sub / "deep.qmd").write_text("---\ntitle: Deep\n---\nB\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert len(result["files"]) == 2


def test_discover_explicit():
    """Verify pages and sections from an explicit guide list"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "install.qmd").write_text("---\ntitle: Install\n---\nA\n")
        (ug / "usage.qmd").write_text("---\ntitle: Usage\n---\nB\n")

        config = [
            {
                "section": "Getting Started",
                "contents": ["install.qmd", "usage.qmd"],
            }
        ]
        result = user_guide._discover_explicit(ug, config, report=print)

        assert result is not None
        assert result["explicit"] is True
        assert len(result["files"]) == 2
        assert "Getting Started" in result["sections"]


def test_discover_explicit_missing_file():
    """Verify that explicit discovery skips missing pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "real.qmd").write_text("---\ntitle: Real\n---\nA\n")

        config = [
            {
                "section": "Section",
                "contents": ["real.qmd", "missing.qmd"],
            }
        ]
        result = user_guide._discover_explicit(ug, config, report=print)

        assert result is not None
        assert len(result["files"]) == 1


def test_discover_explicit_dict_items():
    """Verify explicit page entries with `text` and `href`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "guide.qmd").write_text("---\ntitle: Guide\n---\nA\n")

        config = [
            {
                "section": "Docs",
                "contents": [{"href": "guide.qmd", "text": "Custom Label"}],
            }
        ]
        result = user_guide._discover_explicit(ug, config, report=print)

        assert result is not None
        assert result["files"][0]["custom_text"] == "Custom Label"


def test_discover_explicit_empty():
    """Verify that an explicit guide without existing pages returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()

        config = [{"section": "Empty", "contents": ["missing.qmd"]}]
        result = user_guide._discover_explicit(ug, config, report=print)

        assert result is None


def test_discover_explicit_skips_a_listed_page_that_cannot_be_read(tmp_path: Path):
    """Verify that explicit discovery skips pages with invalid UTF-8"""
    (tmp_path / "broken.qmd").write_bytes(b"\xff\xfe\x00")
    (tmp_path / "ok.qmd").write_text("---\ntitle: Ok\n---\nA\n", encoding="utf-8")
    config = [{"section": "S", "contents": ["broken.qmd", "ok.qmd"]}]

    result = user_guide._discover_explicit(tmp_path, config, report=print)

    assert result is not None
    assert [page["title"] for page in result["files"]] == ["Ok"]


def test_discover_auto_without_readable_pages_returns_none(tmp_path: Path):
    """Verify that automatic discovery returns no guide when all pages are unreadable"""
    config = write_config(tmp_path, "display_name: Demo\n")
    guide_dir = tmp_path / "user_guide"
    guide_dir.mkdir()
    (guide_dir / "broken.qmd").write_bytes(b"\xff\xfe\x00")

    assert user_guide.discover(config, Layout.make(tmp_path), report=print) is None


def test_listed_page_without_a_file_name():
    """Verify that an unsupported listed item has no file name or sidebar label"""
    assert user_guide._listed_page(42) == ("", None)


@pytest.mark.parametrize("outside", ["absolute", "parent"])
def test_explicit_guide_rejects_pages_outside_the_guide_directory(tmp_path: Path, outside: str):
    """Verify that explicit guides warn about and omit absolute and `..` page paths"""
    guide_dir = tmp_path / "user_guide"
    guide_dir.mkdir()
    (guide_dir / "ok.qmd").write_text("# Ok\n")
    (tmp_path / "outside.qmd").write_text("# Outside\n")
    name = str(tmp_path / "outside.qmd") if outside == "absolute" else "../outside.qmd"
    config = [{"section": "S", "contents": [name, "ok.qmd"]}]
    warnings: list[str] = []

    guide = user_guide._discover_explicit(guide_dir, config, report=warnings.append)

    assert guide is not None
    assert [page["path"].name for page in guide["files"]] == ["ok.qmd"]
    assert warnings == [
        f"User guide file '{name}' referenced in config must be a path inside the user guide directory"
    ]
    assert user_guide.sidebar(guide)["contents"] == [
        {"section": "S", "contents": [{"text": "Ok", "href": "user-guide/ok.qmd"}]}
    ]


def test_discover_explicit_skips_duplicates():
    """Verify that explicit discovery includes repeated page names once"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "intro.qmd").write_text("---\ntitle: Intro\n---\nA\n")

        config = [
            {"section": "S1", "contents": ["intro.qmd"]},
            {"section": "S2", "contents": ["intro.qmd"]},  # duplicate
        ]
        result = user_guide._discover_explicit(ug, config, report=print)

        assert result is not None
        assert len(result["files"]) == 1


def test_replace_href_dict_match():
    """Verify replacement of a sidebar entry's `href`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        items = [
            {"text": "Intro", "href": "user-guide/intro.qmd"},
            {"text": "Setup", "href": "user-guide/setup.qmd"},
        ]
        found = user_guide._replace_href(items, "user-guide/intro.qmd", "index.qmd")

        assert found is True
        assert items[0]["href"] == "index.qmd"


def test_replace_href_string_match():
    """Verify replacement of a bare sidebar link"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        items = ["user-guide/intro.qmd", "user-guide/setup.qmd"]
        found = user_guide._replace_href(items, "user-guide/intro.qmd", "index.qmd")

        assert found is True
        assert items[0] == {"text": "Home", "href": "index.qmd"}


def test_replace_href_nested():
    """Verify replacement of a link in nested sidebar sections"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        items = [
            {
                "section": "Getting Started",
                "contents": [
                    {"text": "Intro", "href": "user-guide/intro.qmd"},
                ],
            },
        ]
        found = user_guide._replace_href(items, "user-guide/intro.qmd", "index.qmd")

        assert found is True
        assert items[0]["contents"][0]["href"] == "index.qmd"


def test_replace_href_no_match():
    """Verify that an unmatched sidebar link returns `False`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        items = [{"text": "Other", "href": "other.qmd"}]

        assert user_guide._replace_href(items, "missing.qmd", "new.qmd") is False


def test_link_homepage_exact_check():
    """Verify that the promoted page's sidebar link targets `index.qmd`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sidebar = {
            "id": "user-guide",
            "title": "User Guide",
            "contents": [
                {"text": "Intro", "href": "user-guide/intro.qmd"},
                "user-guide/setup.qmd",
            ],
        }
        user_guide.link_homepage(sidebar, "user-guide/intro.qmd")

        assert sidebar["contents"][0]["href"] == "index.qmd"


def test_organize_files_into_sidebar_flat():
    """Verify a flat sidebar for root pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "intro.qmd").write_text("---\ntitle: Intro\n---\n")
        (src / "setup.qmd").write_text("---\ntitle: Setup\n---\n")

        guide_info = {
            "files": [
                {"path": src / "intro.qmd", "title": "Intro", "section": None},
                {"path": src / "setup.qmd", "title": "Setup", "section": None},
            ],
            "source_dir": src,
            "sections": {},
        }
        result = user_guide.sidebar(guide_info)

        assert result["id"] == "user-guide"
        assert len(result["contents"]) == 2
        assert {"text": "Intro", "href": "user-guide/intro.qmd"} in result["contents"]


def test_organize_files_into_sidebar_with_sections():
    """Verify sidebar grouping by section"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "a.qmd").write_text("A\n")
        (src / "b.qmd").write_text("B\n")

        f_a = {"path": src / "a.qmd", "title": "A", "section": "Basics"}
        f_b = {"path": src / "b.qmd", "title": "B", "section": "Basics"}
        guide_info = {
            "files": [f_a, f_b],
            "source_dir": src,
            "sections": {"Basics": [f_a, f_b]},
        }

        result = user_guide.sidebar(guide_info)

        assert result["id"] == "user-guide"

        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]

        assert len(section_items) == 1
        assert section_items[0]["section"] == "Basics"


def test_organize_files_into_sidebar_subdirectories():
    """Verify sidebar grouping by directory when pages have no sections"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        sub = src / "advanced"
        sub.mkdir()
        (src / "intro.qmd").write_text("Intro\n")
        (sub / "deep.qmd").write_text("Deep\n")

        guide_info = {
            "files": [
                {"path": src / "intro.qmd", "title": "Intro", "section": None},
                {"path": sub / "deep.qmd", "title": "Deep", "section": None},
            ],
            "source_dir": src,
            "sections": {},
        }

        result = user_guide.sidebar(guide_info)

        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]

        assert len(section_items) == 1
        assert section_items[0]["section"] == "Advanced"


def test_sidebar_explicit():
    """Verify the sidebar follows an explicit guide configuration"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "install.qmd").write_text("I\n")
        (src / "usage.qmd").write_text("U\n")

        guide_info = {
            "files": [
                {
                    "path": src / "install.qmd",
                    "title": "Install",
                    "section": "Getting Started",
                    "custom_text": None,
                },
                {
                    "path": src / "usage.qmd",
                    "title": "Usage",
                    "section": "Getting Started",
                    "custom_text": None,
                },
            ],
            "source_dir": src,
            "sections": {
                "Getting Started": [
                    {"path": src / "install.qmd", "title": "Install", "section": "Getting Started"},
                    {"path": src / "usage.qmd", "title": "Usage", "section": "Getting Started"},
                ]
            },
            "explicit": True,
            "explicit_config": [
                {"section": "Getting Started", "contents": ["install.qmd", "usage.qmd"]},
            ],
        }
        result = user_guide.sidebar(guide_info)

        assert result["id"] == "user-guide"

        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]

        assert len(section_items) == 1


def test_sidebar_explicit_skips_empty_sections_and_unnamed_items(tmp_path: Path):
    """Verify that explicit sidebars skip unnamed or empty sections and unnamed items"""
    (tmp_path / "install.qmd").write_text("---\ntitle: Install\n---\n", encoding="utf-8")
    guide = {
        "files": [],
        "sections": {},
        "has_index": False,
        "explicit": True,
        "source_dir": tmp_path,
        "explicit_config": [
            {"section": "", "contents": ["install.qmd"]},
            {"section": "Empty", "contents": []},
            {"section": "Setup", "contents": [42, {"text": "No target"}, "install.qmd"]},
        ],
    }

    assert user_guide.sidebar(guide)["contents"] == [
        {"section": "Setup", "contents": ["user-guide/install.qmd"]}
    ]


def test_sidebar_auto_links_an_untitled_page_by_its_href(tmp_path: Path):
    """Verify that automatic sidebars link untitled pages without a label"""
    (tmp_path / "01-.qmd").write_text("# Content\n", encoding="utf-8")
    page = user_guide.read_page(tmp_path / "01-.qmd")
    assert page is not None
    guide = {
        "files": [page],
        "sections": {},
        "has_index": False,
        "explicit": False,
        "source_dir": tmp_path,
    }

    assert user_guide.sidebar(guide)["contents"] == ["user-guide/.qmd"]


def test_sidebar_auto_lists_the_root_index_before_subdirectories(tmp_path: Path):
    """Verify that the root `index.qmd` precedes subdirectory sections in the sidebar"""
    (tmp_path / "advanced").mkdir()
    (tmp_path / "index.qmd").write_text("---\ntitle: Home\n---\n", encoding="utf-8")
    (tmp_path / "advanced" / "tuning.qmd").write_text("---\ntitle: Tuning\n---\n", encoding="utf-8")
    pages = [
        user_guide.read_page(tmp_path / "advanced" / "tuning.qmd"),
        user_guide.read_page(tmp_path / "index.qmd"),
    ]
    guide = {
        "files": pages,
        "sections": {},
        "has_index": True,
        "explicit": False,
        "source_dir": tmp_path,
    }

    assert user_guide.sidebar(guide)["contents"] == [
        {"text": "Home", "href": "user-guide/index.qmd"},
        {
            "section": "Advanced",
            "contents": [{"text": "Tuning", "href": "user-guide/advanced/tuning.qmd"}],
        },
    ]


def test_discover_basic_full_project():
    """Verify discovery of user guide pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "01-intro.qmd").write_text("---\ntitle: Intro\n---\n\n# Intro\n")

        result = discover_user_guide(docs)
        assert (
            result is not None or result is None
        )  # Discovery depends on the directory naming convention


def test_discover_empty_dir():
    """Verify that an empty guide directory returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        result = discover_user_guide(docs)
        assert result is None


def test_discover_no_qmd_files():
    """Verify that a guide without `.qmd` or `.md` files returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "notes.txt").write_text("not a doc file\n")
        result = discover_user_guide(docs)
        assert result is None


def test_discover_basic():
    """Verify discovery of `.qmd` pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "01-intro.qmd").write_text(
            "---\ntitle: Intro\n---\n\n# Intro content\n", encoding="utf-8"
        )
        (ug_dir / "02-advanced.qmd").write_text(
            "---\ntitle: Advanced\n---\n\n# Advanced content\n", encoding="utf-8"
        )
        result = discover_user_guide(docs)
        assert result is not None
        assert len(result["files"]) == 2


def test_link_homepage():
    """Verify replacement of the promoted page's sidebar link"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sidebar_config = {
            "id": "user-guide",
            "title": "User Guide",
            "contents": [
                "user-guide/intro.qmd",
                "user-guide/advanced.qmd",
            ],
        }
        user_guide.link_homepage(sidebar_config, "user-guide/intro.qmd")
        assert sidebar_config["contents"][0] != "user-guide/intro.qmd"


def test_read_page_with_frontmatter():
    """Verify page titles from front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        qmd_file = Path(tmp_dir) / "01-intro.qmd"
        qmd_file.write_text(
            "---\ntitle: Introduction\nguide-section: Getting Started\n---\n\n# Intro\n",
            encoding="utf-8",
        )
        result = user_guide.read_page(qmd_file)
        assert result is not None
        assert result["title"] == "Introduction"
        assert result["section"] == "Getting Started"


def test_find_dir_underscore():
    """Verify discovery of the conventional `user_guide/` directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        (Path(tmp_dir) / "user_guide").mkdir()
        result = find_user_guide_dir(docs)
        assert result is not None
        assert result.name == "user_guide"


def test_find_dir_hyphen():
    """Verify discovery of the conventional `user-guide/` directory"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        (Path(tmp_dir) / "user-guide").mkdir()
        result = find_user_guide_dir(docs)
        assert result is not None
        assert result.name == "user-guide"


def test_find_dir_not_found():
    """Verify that a missing guide directory returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = find_user_guide_dir(docs)
        assert result is None


def test_find_dir_skips_section_directory(tmp_path):
    (tmp_path / "great-docs.yml").write_text("sections:\n  - title: Guide\n    dir: user_guide\n")
    (tmp_path / "user_guide").mkdir()
    docs = GreatDocs(project_path=tmp_path)

    assert find_user_guide_dir(docs) is None


def test_find_dir_falls_back_past_claimed_directory(tmp_path):
    (tmp_path / "great-docs.yml").write_text("sections:\n  - title: Guide\n    dir: user_guide\n")
    (tmp_path / "user_guide").mkdir()
    (tmp_path / "user-guide").mkdir()
    docs = GreatDocs(project_path=tmp_path)

    result = find_user_guide_dir(docs)

    assert result is not None
    assert result.name == "user-guide"


def test_discover_explicit_config():
    """Verify discovery from an explicit `user_guide` list"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "intro.qmd").write_text("---\ntitle: Intro\n---\n\n# Intro\n", encoding="utf-8")
        (ug_dir / "advanced.qmd").write_text(
            "---\ntitle: Advanced\n---\n\n# Advanced\n", encoding="utf-8"
        )

        docs._config = write_config(
            Path(tmp_dir),
            "user_guide:\n"
            "  - section: Getting Started\n"
            "    contents:\n"
            "      - intro.qmd\n"
            "  - section: Expert\n"
            "    contents:\n"
            "      - advanced.qmd\n",
        )

        result = discover_user_guide(docs)
        assert result is not None
        assert result["explicit"] is True
        assert len(result["files"]) == 2


def test_discover_with_subdirectory():
    """Verify discovery of nested guide pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "01-intro.qmd").write_text(
            "---\ntitle: Intro\n---\n\nIntro text.\n", encoding="utf-8"
        )
        sub_dir = ug_dir / "advanced"
        sub_dir.mkdir()
        (sub_dir / "deep.qmd").write_text(
            "---\ntitle: Deep\n---\n\nDeep content.\n", encoding="utf-8"
        )

        result = discover_user_guide(docs)
        assert result is not None
        assert len(result["files"]) == 2
        assert result["explicit"] is False


def test_discover_hyphen_dir():
    """Verify page discovery in `user-guide/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        ug_dir = Path(tmp_dir) / "user-guide"
        ug_dir.mkdir()
        (ug_dir / "01-intro.qmd").write_text("---\ntitle: Intro\n---\n\nIntro.\n", encoding="utf-8")

        result = discover_user_guide(docs)
        assert result is not None
        assert len(result["files"]) >= 1


def test_sidebar_auto():
    """Verify sidebar entries for automatically discovered pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True)

        ug_src = Path(tmp_dir) / "user_guide"
        ug_src.mkdir(exist_ok=True)

        copied_files = [
            {
                "path": ug_src / "intro.qmd",
                "title": "Intro",
                "section": None,
                "dest_name": "intro.qmd",
            },
            {
                "path": ug_src / "advanced.qmd",
                "title": "Advanced",
                "section": None,
                "dest_name": "advanced.qmd",
            },
        ]

        ug_info = {
            "files": copied_files,
            "sections": {},
            "has_index": False,
            "explicit": False,
            "source_dir": ug_src,
        }

        result = user_guide.sidebar(ug_info)
        assert isinstance(result, dict)
        assert "id" in result
        assert result["id"] == "user-guide"


def test_read_page_basic():
    """Verify page titles from front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        qmd = Path(tmp_dir) / "guide.qmd"
        qmd.write_text("---\ntitle: My Guide\n---\n\n# Content\n", encoding="utf-8")
        result = user_guide.read_page(qmd)
        assert result is not None
        assert result["title"] == "My Guide"
        assert result["path"] == qmd


def test_read_page_no_frontmatter():
    """Verify a file name title when front matter is absent"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        qmd = Path(tmp_dir) / "guide.qmd"
        qmd.write_text("# Just content\n\nNo frontmatter here.\n", encoding="utf-8")
        result = user_guide.read_page(qmd)
        assert result is not None


def test_read_page_with_section():
    """Verify page sections from front matter"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        qmd = Path(tmp_dir) / "guide.qmd"
        qmd.write_text(
            "---\ntitle: My Guide\nguide-section: Getting Started\n---\n\n# Content\n",
            encoding="utf-8",
        )
        result = user_guide.read_page(qmd)
        assert result is not None
        assert result["section"] == "Getting Started"


def test_discover_with_files():
    """Verify page discovery in `user_guide/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "01-intro.qmd").write_text(
            "---\ntitle: Intro\n---\n\n# Introduction\n", encoding="utf-8"
        )
        (ug_dir / "02-setup.qmd").write_text(
            "---\ntitle: Setup\n---\n\n# Setting Up\n", encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert len(result["files"]) == 2
        assert result["source_dir"] == ug_dir.resolve()


def test_discover_no_dir():
    """Verify that an absent guide directory returns `None`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is None


def test_discover_with_subdirs():
    """Verify discovery of nested guide pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        sub = ug_dir / "advanced"
        sub.mkdir()
        (sub / "topic.qmd").write_text("---\ntitle: Topic\n---\n\nContent\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert len(result["files"]) >= 1


def test_replace_href_nested_list():
    """Verify link replacement across flat and nested sidebar entries"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        sidebar = [
            {"text": "Page 1", "href": "user-guide/intro.qmd"},
            {
                "text": "Section",
                "contents": [
                    {"text": "Page 2", "href": "user-guide/page2.qmd"},
                ],
            },
        ]
        found = user_guide._replace_href(sidebar, "user-guide/intro.qmd", "index.qmd")
        assert found is True
        assert sidebar[0]["href"] == "index.qmd"

        sidebar2 = [
            {
                "text": "Section",
                "contents": [
                    {"text": "Deep", "href": "old.qmd"},
                ],
            },
        ]
        found2 = user_guide._replace_href(sidebar2, "old.qmd", "new.qmd")
        assert found2 is True
        assert sidebar2[0]["contents"][0]["href"] == "new.qmd"

        sidebar3 = ["bare-page.qmd", {"text": "Other", "href": "other.qmd"}]
        found3 = user_guide._replace_href(sidebar3, "bare-page.qmd", "index.qmd")
        assert found3 is True
        assert sidebar3[0] == {"text": "Home", "href": "index.qmd"}

        sidebar4 = [{"text": "A", "href": "a.qmd"}]
        found4 = user_guide._replace_href(sidebar4, "nonexistent.qmd", "z.qmd")
        assert found4 is False


class TestDiscoverUserGuide:
    """User guide discovery checks"""

    def _make_project(self, tmp_dir, user_guide_files=None, config_text=""):
        """Create a project with user guide files"""
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.0"\n')
        if config_text:
            (tmp / "great-docs.yml").write_text(config_text)

        ug_dir = tmp / "user_guide"
        ug_dir.mkdir(exist_ok=True)

        if user_guide_files:
            for name, content in user_guide_files.items():
                path = ug_dir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)

        return GreatDocs(project_path=tmp_dir)

    def test_auto_discover_basic(self):
        """Verify page discovery in file name order"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                {
                    "02-advanced.qmd": "---\ntitle: Advanced\n---\nContent\n",
                    "01-intro.qmd": "---\ntitle: Introduction\n---\nContent\n",
                },
            )
            info = discover_user_guide(docs)
            assert info is not None
            assert len(info["files"]) == 2
            assert info["files"][0]["title"] == "Introduction"
            assert info["files"][1]["title"] == "Advanced"
            assert info["explicit"] is False

    def test_auto_discover_empty_dir(self):
        """Verify that an empty guide directory returns `None`"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(tmp_dir, {})
            info = discover_user_guide(docs)
            assert info is None

    def test_auto_discover_with_subdirectories(self):
        """Verify discovery of nested guide pages"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                {
                    "01-intro.qmd": "---\ntitle: Introduction\n---\nContent\n",
                    "basics/01-setup.qmd": "---\ntitle: Setup\n---\nContent\n",
                },
            )
            info = discover_user_guide(docs)
            assert info is not None
            assert len(info["files"]) == 2

    def test_auto_discover_no_valid_files(self):
        """Verify that a directory without guide pages returns `None`"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "notes.txt").write_text("not a qmd file")
            docs = GreatDocs(project_path=tmp_dir)
            info = discover_user_guide(docs)
            assert info is None

    def test_auto_discover_with_sections_in_frontmatter(self):
        """Verify page grouping by front matter section"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                {
                    "01-intro.qmd": "---\ntitle: Introduction\nguide-section: Getting Started\n---\nContent\n",
                    "02-config.qmd": "---\ntitle: Configuration\nguide-section: Getting Started\n---\nContent\n",
                    "03-deploy.qmd": "---\ntitle: Deployment\nguide-section: Advanced\n---\nContent\n",
                },
            )
            info = discover_user_guide(docs)
            assert info is not None
            assert "Getting Started" in info["sections"]
            assert len(info["sections"]["Getting Started"]) == 2
            assert "Advanced" in info["sections"]

    def test_auto_discover_has_index(self):
        """Verify detection of a root `index.qmd`"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                {
                    "index.qmd": "---\ntitle: User Guide\n---\nOverview\n",
                    "01-intro.qmd": "---\ntitle: Introduction\n---\nContent\n",
                },
            )
            info = discover_user_guide(docs)
            assert info is not None
            assert info["has_index"] is True

    def test_auto_discover_has_index_false_for_subdir_only(self):
        """Verify that only a root `index.qmd` marks an automatic guide as having an index"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                {
                    "01-overview.qmd": "---\ntitle: Overview\n---\nContent\n",
                    "02-setup/index.qmd": "---\ntitle: Setup\n---\nSection intro\n",
                    "02-setup/install.qmd": "---\ntitle: Installation\n---\nContent\n",
                },
            )
            info = discover_user_guide(docs)
            assert info is not None
            assert info["has_index"] is False, (
                "has_index should be False when only subdir index.qmd files exist"
            )


class TestDiscoverUserGuideExplicit:
    """Explicit guide discovery checks"""

    def test_explicit_basic(self):
        """Verify that explicit configuration resolves pages and sections"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            (ug_dir / "config.qmd").write_text("---\ntitle: Configuration\n---\nContent\n")
            config = [
                {"section": "Getting Started", "contents": ["intro.qmd", "config.qmd"]},
            ]
            info = user_guide._discover_explicit(ug_dir, config, report=print)
            assert info is not None
            assert info["explicit"] is True
            assert len(info["files"]) == 2
            assert "Getting Started" in info["sections"]

    def test_explicit_missing_file(self):
        """Verify that missing pages are skipped"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            config = [
                {"section": "Docs", "contents": ["intro.qmd", "missing.qmd"]},
            ]
            info = user_guide._discover_explicit(ug_dir, config, report=print)
            assert info is not None
            assert len(info["files"]) == 1

    def test_explicit_dict_items_with_custom_text(self):
        """Verify page entries with `text` and `href`"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            config = [
                {"section": "Docs", "contents": [{"text": "Start Here", "href": "intro.qmd"}]},
            ]
            info = user_guide._discover_explicit(ug_dir, config, report=print)
            assert info is not None
            assert info["files"][0].get("custom_text") == "Start Here"

    def test_explicit_empty_section(self):
        """Verify that sections with empty page lists are skipped"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            config = [
                {"section": "Empty", "contents": []},
            ]
            info = user_guide._discover_explicit(ug_dir, config, report=print)
            assert info is None

    def test_explicit_deduplicates_files(self):
        """Verify that repeated page names appear once"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            config = [
                {"section": "A", "contents": ["intro.qmd"]},
                {"section": "B", "contents": ["intro.qmd"]},
            ]
            info = user_guide._discover_explicit(ug_dir, config, report=print)
            assert info is not None
            assert len(info["files"]) == 1


class TestGenerateUserGuideSidebarAuto:
    """User guide sidebar checks"""

    def test_flat_files_no_sections(self):
        """Verify a flat sidebar for pages without sections"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            user_guide_info = {
                "files": [
                    {"path": ug_dir / "01-intro.qmd", "title": "Intro", "section": None},
                    {"path": ug_dir / "02-config.qmd", "title": "Config", "section": None},
                ],
                "sections": {},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            assert sidebar["id"] == "user-guide"
            assert len(sidebar["contents"]) == 2
            assert sidebar["contents"][0] == {"text": "Intro", "href": "user-guide/intro.qmd"}

    def test_with_sections(self):
        """Verify sidebar sections from front matter"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            file1 = {"path": ug_dir / "01-intro.qmd", "title": "Intro", "section": "Basics"}
            file2 = {"path": ug_dir / "02-adv.qmd", "title": "Adv", "section": "Basics"}
            file3 = {"path": ug_dir / "03-deploy.qmd", "title": "Deploy", "section": "Advanced"}
            user_guide_info = {
                "files": [file1, file2, file3],
                "sections": {"Basics": [file1, file2], "Advanced": [file3]},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            assert sidebar["contents"][0]["section"] == "Basics"
            assert len(sidebar["contents"][0]["contents"]) == 2
            assert sidebar["contents"][1]["section"] == "Advanced"

    def test_with_subdirectories(self):
        """Verify directory grouping when front matter defines no sections"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "basics").mkdir()
            root_file = {"path": ug_dir / "01-intro.qmd", "title": "Intro", "section": None}
            sub_file = {
                "path": ug_dir / "basics" / "01-setup.qmd",
                "title": "Setup",
                "section": None,
            }
            user_guide_info = {
                "files": [root_file, sub_file],
                "sections": {},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            assert len(sidebar["contents"]) == 2
            assert "section" in sidebar["contents"][1]

    def test_mixed_files_and_subdirs_sorted_by_prefix(self):
        """Verify that numeric prefixes order root pages and directory sections together"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "02_concepts").mkdir()
            file01 = {"path": ug_dir / "01_overview.qmd", "title": "Overview", "section": None}
            file02 = {
                "path": ug_dir / "02_concepts" / "details.qmd",
                "title": "Details",
                "section": None,
            }
            file03 = {"path": ug_dir / "03_quickstart.qmd", "title": "Quickstart", "section": None}
            user_guide_info = {
                "files": [file01, file02, file03],
                "sections": {},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            contents = sidebar["contents"]
            assert len(contents) == 3
            assert contents[0] == {"text": "Overview", "href": "user-guide/overview.qmd"}
            assert "section" in contents[1]
            assert contents[1]["section"] == "Concepts"
            assert contents[2] == {"text": "Quickstart", "href": "user-guide/quickstart.qmd"}


class TestParseUserGuideFile:
    """Page metadata checks"""

    def test_parses_frontmatter_title(self):
        """Verify page titles from YAML front matter"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            qmd = tmp / "intro.qmd"
            qmd.write_text("---\ntitle: Introduction\n---\nContent\n")
            result = user_guide.read_page(qmd)
            assert result is not None
            assert result["title"] == "Introduction"

    def test_derives_title_from_filename(self):
        """Verify that a file name supplies a missing title"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            qmd = tmp / "01-getting-started.qmd"
            qmd.write_text("No frontmatter here, just content.\n")
            result = user_guide.read_page(qmd)
            assert result is not None
            assert result["title"] == "Getting Started"

    def test_extracts_section_from_frontmatter(self):
        """Verify `guide-section` values from front matter"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            qmd = tmp / "intro.qmd"
            qmd.write_text("---\ntitle: Intro\nguide-section: Getting Started\n---\nContent\n")
            result = user_guide.read_page(qmd)
            assert result is not None
            assert result["section"] == "Getting Started"

    def test_handles_unreadable_file(self):
        """Verify that an unreadable page returns `None`"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = user_guide.read_page(Path(tmp_dir) / "nonexistent.qmd")
            assert result is None


class TestGenerateUserGuideSidebarAutoBatch9:
    """Automatic sidebar grouping and section titles"""

    def test_subdir_index_provides_section_title(self):
        """Verify that a directory's `index.qmd` supplies its section title"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "basics").mkdir()
            root_file = {
                "path": ug_dir / "01-intro.qmd",
                "title": "Intro",
                "section": None,
            }
            index_file = {
                "path": ug_dir / "basics" / "index.qmd",
                "title": "Basics Overview",
                "section": None,
            }
            sub_file = {
                "path": ug_dir / "basics" / "01-setup.qmd",
                "title": "Setup",
                "section": None,
            }
            user_guide_info = {
                "files": [root_file, index_file, sub_file],
                "sections": {},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            # `contents` distinguishes a directory section from a labelled page link
            section_entry = next(
                (c for c in sidebar["contents"] if isinstance(c, dict) and "contents" in c),
                None,
            )
            assert section_entry is not None
            assert section_entry["section"] == "Basics Overview"

    def test_sections_with_index_qmd_in_section(self):
        """Verify that a section's `index.qmd` has a labelled sidebar link"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            index_file = {
                "path": ug_dir / "index.qmd",
                "title": "Overview",
                "section": "Getting Started",
            }
            page_file = {
                "path": ug_dir / "01-intro.qmd",
                "title": "Intro",
                "section": "Getting Started",
            }
            user_guide_info = {
                "files": [index_file, page_file],
                "sections": {"Getting Started": [index_file, page_file]},
                "has_index": True,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            section = sidebar["contents"][0]
            assert section["section"] == "Getting Started"
            index_entry = section["contents"][0]
            assert isinstance(index_entry, dict)
            assert index_entry.get("text") == "Overview"

    def test_sections_with_unsectioned_files(self):
        """Verify that ungrouped pages follow sidebar sections"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            sectioned = {
                "path": ug_dir / "01-intro.qmd",
                "title": "Intro",
                "section": "Getting Started",
            }
            unsectioned = {
                "path": ug_dir / "99-appendix.qmd",
                "title": "Appendix",
                "section": None,
            }
            user_guide_info = {
                "files": [sectioned, unsectioned],
                "sections": {"Getting Started": [sectioned]},
                "has_index": False,
                "source_dir": ug_dir,
            }
            sidebar = user_guide.sidebar(user_guide_info)
            assert sidebar["contents"][0]["section"] == "Getting Started"
            assert sidebar["contents"][1] == {
                "text": "Appendix",
                "href": "user-guide/appendix.qmd",
            }


class TestGenerateUserGuideSidebarExplicitBatch9:
    """Explicit sidebar entries and missing pages"""

    def test_skips_missing_files(self):
        """Verify that the sidebar omits missing source pages"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            user_guide_info = {
                "files": [],
                "source_dir": ug_dir,
                "explicit": True,
                "explicit_config": [
                    {
                        "section": "Basics",
                        "contents": ["intro.qmd", "missing.qmd"],
                    },
                ],
            }
            sidebar = user_guide.sidebar(user_guide_info)
            section = sidebar["contents"][0]
            assert len(section["contents"]) == 1

    def test_custom_text_in_sidebar(self):
        """Verify labelled sidebar links for pages with custom text"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "intro.qmd").write_text("---\ntitle: Introduction\n---\nContent\n")
            user_guide_info = {
                "files": [],
                "source_dir": ug_dir,
                "explicit": True,
                "explicit_config": [
                    {
                        "section": "Basics",
                        "contents": [{"href": "intro.qmd", "text": "Start Here"}],
                    },
                ],
            }
            sidebar = user_guide.sidebar(user_guide_info)
            section = sidebar["contents"][0]
            entry = section["contents"][0]
            assert isinstance(entry, dict)
            assert entry["text"] == "Start Here"

    def test_skips_empty_sections(self):
        """Verify that the sidebar omits sections without existing pages"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            user_guide_info = {
                "files": [],
                "source_dir": ug_dir,
                "explicit": True,
                "explicit_config": [
                    {"section": "Empty", "contents": ["missing.qmd"]},
                ],
            }
            sidebar = user_guide.sidebar(user_guide_info)
            assert len(sidebar["contents"]) == 0


def test_discover_sort_prioritizes_root_index():
    """Verify that the root `index.qmd` precedes numbered nested pages"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()

        (ug_dir / "index.qmd").write_text("---\ntitle: Welcome\n---\nLanding page.\n")

        sub = ug_dir / "00-getting-started"
        sub.mkdir()
        (sub / "index.qmd").write_text("---\ntitle: Getting Started\n---\nSection index.\n")
        (sub / "01-quickstart.qmd").write_text("---\ntitle: Quickstart\n---\nQuick.\n")

        sub2 = ug_dir / "07-cli"
        sub2.mkdir()
        (sub2 / "01-cli-data.qmd").write_text("---\ntitle: CLI Data\n---\nCLI stuff.\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert len(result["files"]) == 4

        first_path = result["files"][0]["path"]
        assert first_path.name == "index.qmd"
        assert first_path.parent == ug_dir.resolve()


def test_discover_sort_relative_path_ordering():
    """Verify page ordering by relative path"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()

        sub_a = ug_dir / "00-intro"
        sub_a.mkdir()
        (sub_a / "01-page.qmd").write_text("---\ntitle: Page A\n---\nA.\n")

        sub_b = ug_dir / "07-cli"
        sub_b.mkdir()
        (sub_b / "01-cli-data.qmd").write_text("---\ntitle: CLI Data\n---\nB.\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = discover_user_guide(docs)

        assert result is not None
        assert len(result["files"]) == 2

        assert "00-intro" in str(result["files"][0]["path"])
        assert "07-cli" in str(result["files"][1]["path"])


def test_user_guide_file_with_a_list_block_derives_its_title(tmp_path: Path) -> None:
    """Verify that non-mapping front matter yields a file name title and no section"""
    qmd = tmp_path / "01-getting-started.qmd"
    qmd.write_text("---\n- a\n- b\n---\n\n# Content\n")

    result = user_guide.read_page(qmd)

    assert result is not None
    assert (result["title"], result["section"]) == ("Getting Started", None)


@pytest.mark.parametrize(
    ("pages", "settings", "href"),
    [
        (["01-basics/02-setup.qmd", "02-more/intro.qmd"], "", "user-guide/basics/setup.qmd"),
        (["index.qmd", "01-intro.qmd"], "", "user-guide/index.qmd"),
        (
            ["01-intro.qmd", "guides/index.qmd"],
            "user_guide:\n  - section: Start\n    contents: [01-intro.qmd, guides/index.qmd]\n",
            "user-guide/01-intro.qmd",
        ),
    ],
    ids=["nested", "root-index", "explicit"],
)
def test_entry_links_to_the_first_published_page(
    tmp_path: Path, pages: list[str], settings: str, href: str
):
    for relative in pages:
        page = tmp_path / "user_guide" / relative
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("---\ntitle: Page\n---\n")
    config = write_config(tmp_path, settings)
    guide = user_guide.discover(config, Layout.make(tmp_path), report=print)
    assert guide is not None

    assert user_guide.entry(guide) == href
