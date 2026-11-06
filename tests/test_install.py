import shutil
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from yaml12 import parse_yaml, read_yaml

from great_docs import Config
from great_docs._install import format_authors_yaml, update_gitignore, write_initial_config
from great_docs._layout import Layout
from great_docs._project import Project
from great_docs._reference.exports import Exports
from tests.support import write_pyproject

# Every entry a package-root configuration needs
_ROOT_ENTRIES = (
    "/great-docs/\n/great-docs-*/\n.great-docs-build/\n.great-docs-cache/\n.great-docs/\n"
)


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    """Create a layout for a project configured at its package root"""
    return Layout.make(tmp_path)


@pytest.fixture
def docs_layout(tmp_path: Path) -> Layout:
    """Create a layout for a project configured in its `docs/` directory"""
    config_path = tmp_path / "docs" / "great-docs.yml"
    config_path.parent.mkdir()
    config_path.write_text("module: sample\n", encoding="utf-8")
    return Layout.make(tmp_path, config_path)


def test_creates_gitignore_with_anchored_entries(tmp_path: Path, layout: Layout):
    lines: list[str] = []

    update_gitignore(layout, report=lines.append)

    content = (tmp_path / ".gitignore").read_text()
    assert content.splitlines() == [
        "# Great Docs build directory (ephemeral, do not commit)",
        "/great-docs/",
        "",
        "# Great Docs versioned-build artifacts",
        *_ROOT_ENTRIES.splitlines()[1:],
    ]
    assert lines == ["✅ Created .gitignore to ignore Great Docs build output"]


def test_appends_to_existing_gitignore(tmp_path: Path, layout: Layout):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n")
    lines: list[str] = []

    update_gitignore(layout, report=lines.append)

    content = gitignore.read_text()
    assert content.startswith("__pycache__/\n")
    assert all(entry in content.splitlines() for entry in _ROOT_ENTRIES.splitlines())
    assert lines == ["✅ Updated .gitignore to ignore Great Docs build output"]


def test_appends_only_missing_versioning_entries(tmp_path: Path, layout: Layout):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("# Great Docs build directory\n/great-docs/\n")

    update_gitignore(layout, report=print)

    lines = gitignore.read_text().splitlines()
    assert lines.count("/great-docs/") == 1
    assert "/great-docs-*/" in lines


def test_leaves_complete_gitignore_untouched(tmp_path: Path, layout: Layout):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(_ROOT_ENTRIES)
    before = gitignore.stat().st_mtime_ns
    lines: list[str] = []

    update_gitignore(layout, report=lines.append, ask=lambda _: pytest.fail("asked"))

    assert gitignore.read_text() == _ROOT_ENTRIES
    assert gitignore.stat().st_mtime_ns == before
    assert lines == []


def test_anchors_legacy_unanchored_entry(tmp_path: Path, layout: Layout):
    """
    Anchor the legacy `great-docs/` build pattern to the project root

    Projects initialised by earlier releases retain a standalone `great-docs/` line until the
    next approved update.
    """
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("great-docs/\n" + _ROOT_ENTRIES.split("\n", 1)[1])
    lines: list[str] = []

    update_gitignore(layout, report=lines.append)

    assert gitignore.read_text() == _ROOT_ENTRIES
    assert lines == ["✅ Anchored the great-docs/ entry to the project root as /great-docs/"]


def test_migration_leaves_similar_lines(tmp_path: Path, layout: Layout):
    """
    Replace only the complete legacy `great-docs/` line

    Cache patterns, historical build patterns, and negations contain similar text but have
    separate meanings.
    """
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\ngreat-docs/\n.great-docs/\n!skills/great-docs/\n")

    update_gitignore(layout, report=print)

    lines = gitignore.read_text().splitlines()
    assert lines[:4] == ["*.pyc", "/great-docs/", ".great-docs/", "!skills/great-docs/"]
    assert lines.count("/great-docs/") == 1


def test_migration_is_idempotent(tmp_path: Path, layout: Layout):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("great-docs/\n")

    update_gitignore(layout, report=print)
    first_pass = gitignore.read_text()
    update_gitignore(layout, report=print)

    assert gitignore.read_text() == first_pass
    assert first_pass.splitlines().count("/great-docs/") == 1


def test_negation_is_not_the_build_entry(tmp_path: Path, layout: Layout):
    """
    Add the main build rule even when a negated nested path contains it

    A substring check would find `/great-docs/` within `!skills/great-docs/` and fail to add
    the actual build rule.
    """
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("!skills/great-docs/\n")

    update_gitignore(layout, report=print)

    lines = gitignore.read_text().splitlines()
    assert "!skills/great-docs/" in lines
    assert lines.count("/great-docs/") == 1


def test_versioning_pattern_does_not_match_nested_dir(tmp_path: Path, layout: Layout):
    """
    Leave nested directories outside the historical build pattern

    Use Git to verify the generated rule instead of duplicating its ignore semantics in the
    test.
    """
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not available")
    subprocess.run([git, "init", "-q"], cwd=tmp_path, check=True)

    update_gitignore(layout, report=print)

    nested = tmp_path / "docs" / "great-docs-examples"
    nested.mkdir(parents=True)
    (nested / "y.md").write_text("content\n")
    result = subprocess.run(
        [git, "check-ignore", str(nested / "y.md")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    # Git reports an unignored path with no output and a nonzero status.
    assert result.returncode != 0
    assert result.stdout.strip() == ""


@pytest.mark.parametrize("answer", ["", "y", " Yes "])
def test_creates_gitignore_when_user_agrees(tmp_path: Path, layout: Layout, answer: str):
    questions: list[str] = []
    lines: list[str] = []

    def ask(question: str) -> str:
        questions.append(question)
        return answer

    update_gitignore(layout, report=lines.append, ask=ask)

    assert (tmp_path / ".gitignore").exists()
    assert questions == ["Add '/great-docs/' to .gitignore? [Y/n]: "]
    assert lines == [
        "\nThe great-docs/ build directory is temporary and should not be committed.",
        "✅ Created .gitignore to ignore Great Docs build output",
    ]


def test_leaves_gitignore_absent_when_user_declines(tmp_path: Path, layout: Layout):
    lines: list[str] = []

    update_gitignore(layout, report=lines.append, ask=lambda _: "n")

    assert not (tmp_path / ".gitignore").exists()
    assert lines[-1] == "⚠️  Skipped .gitignore update. Remember to ignore /great-docs/."


def test_migration_asks_before_anchoring(tmp_path: Path, layout: Layout):
    """
    Require consent before migrating the legacy line

    If the user declines, preserve the file, as when adding a new entry.
    """
    gitignore = tmp_path / ".gitignore"
    original = "great-docs/\n" + _ROOT_ENTRIES.split("\n", 1)[1]
    gitignore.write_text(original)
    questions: list[str] = []
    lines: list[str] = []

    def ask(question: str) -> str:
        questions.append(question)
        return "n"

    update_gitignore(layout, report=lines.append, ask=ask)

    assert gitignore.read_text() == original
    assert questions == ["Anchor it to the project root as /great-docs/? [Y/n]: "]
    assert lines == [
        "\nThe great-docs/ entry in .gitignore matches directories at any depth.",
        "⚠️  Skipped .gitignore update. Remember to ignore /great-docs/.",
    ]


def test_docs_layout_ignores_source_relative_output(tmp_path: Path, docs_layout: Layout):
    lines: list[str] = []

    update_gitignore(docs_layout, report=lines.append)

    content = (tmp_path / ".gitignore").read_text().splitlines()
    assert "/docs/_quarto/" in content
    assert "/docs/_site/" in content
    assert "/docs/.cache/" in content
    assert "/great-docs/" not in content
    assert ".great-docs-cache/" not in content
    assert lines == []


def test_docs_layout_asks_before_writing(tmp_path: Path, docs_layout: Layout):
    questions: list[str] = []

    def ask(question: str) -> str:
        questions.append(question)
        return "n"

    update_gitignore(docs_layout, report=print, ask=ask)

    assert not (tmp_path / ".gitignore").exists()
    assert questions == ["Ignore Great Docs build output? [Y/n]: "]


def test_authors_yaml_is_empty_without_authors():
    assert format_authors_yaml([]) == ""


def test_authors_yaml_writes_fields_and_placeholders():
    authors = [
        {"name": "Alice", "role": "Author", "email": "alice@example.com"},
        {"name": "Bob", "role": "Maintainer"},
    ]

    assert format_authors_yaml(authors).splitlines() == [
        "authors:",
        "  - name: Alice",
        "    role: Author",
        "    # affiliation: ",
        "    email: alice@example.com",
        "    # github: ",
        "    # orcid: ",
        "    # homepage: ",
        "  - name: Bob",
        "    role: Maintainer",
        "    # affiliation: ",
        "    # email: ",
        "    # github: ",
        "    # orcid: ",
        "    # homepage: ",
    ]


@pytest.mark.parametrize(
    "name",
    [
        "Doe, Jane: PhD",
        "Jane #1",
        "@jane",
        "*star",
        "yes",
        "no",
        "true",
        "123",
        "Jane\nDoe",
    ],
)
def test_authors_yaml_reads_back_as_written(name: str):
    authors = [
        {"name": name, "role": name, "email": f"{name}@example.com"},
        {"name": name},
    ]

    parsed = parse_yaml(format_authors_yaml(authors))

    assert parsed == {"authors": authors}


def _write_initial_config(root: Path, *, force: bool = True) -> list[str]:
    """
    Write the initial configuration of the project at `root` to `root/great-docs.yml`

    Parameters
    ----------
    root
        The project directory.
    force
        Whether to replace an existing `great-docs.yml`.

    Returns
    -------
    :
        The lines reported to the user.
    """
    layout = Layout.make(root)
    config = layout.load_config()
    project = Project.make(config, layout)
    lines: list[str] = []
    write_initial_config(
        config, layout, project, Exports(config, project), force=force, report=lines.append
    )
    return lines


@contextmanager
def _detected(
    *,
    names: list[str] | None = None,
    categories: dict[str, object] | None = None,
    style: str = "numpy",
    dynamic: bool = False,
) -> Generator[None]:
    """
    Stub package loading, export discovery and the probes with the given results

    Parameters
    ----------
    names
        The discovered exports, or `None` when discovery fails.
    categories
        The categorised exports.
    style
        The detected docstring style.
    dynamic
        Whether the dynamic-mode probe succeeds.

    Yields
    ------
    :
        Nothing; the stubs apply until the context exits.
    """
    with (
        patch.object(Exports, "package", return_value=MagicMock()),
        patch.object(Exports, "names", return_value=names),
        patch.object(Exports, "categorise", return_value=categories),
        patch("great_docs._install.probe.detect_docstring_style", return_value=style),
        patch("great_docs._install.probe.detect_dynamic_mode", return_value=dynamic),
    ):
        yield


def _read_config(root: Path) -> dict[str, Any]:
    """
    Read the mapping in `root/great-docs.yml`

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The configuration's live keys.
    """
    config = read_yaml(root / "great-docs.yml")
    assert isinstance(config, dict), "the configuration must hold live keys"
    return cast("dict[str, Any]", config)


def test_initial_config_lists_maintainers_then_authors(tmp_path: Path):
    """Maintainers come first; a person who is both appears once, as a maintainer"""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n'
        '[[project.authors]]\nname = "Alice"\nemail = "alice@example.com"\n'
        '[[project.authors]]\nname = "Bob"\n'
        '[[project.maintainers]]\nname = "Bob"\nemail = "bob@example.com"\n'
        '[[project.maintainers]]\nemail = "nameless@example.com"\n',
        encoding="utf-8",
    )

    with _detected():
        _ = _write_initial_config(tmp_path)

    assert _read_config(tmp_path)["authors"] == [
        {"name": "Bob", "role": "Maintainer", "email": "bob@example.com"},
        {"name": "Alice", "role": "Author", "email": "alice@example.com"},
    ]


def test_initial_config_without_people_has_no_authors(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")

    with _detected():
        _ = _write_initial_config(tmp_path)

    assert "authors" not in _read_config(tmp_path)


def test_initial_config_lists_poetry_1_authors(tmp_path: Path):
    """`great-docs init` lists the authors of a Poetry 1.x project"""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry]\n"
        'name = "poetry-pkg"\n'
        'version = "1.0.0"\n'
        'authors = ["Ada Lovelace <ada@example.com>"]\n',
        encoding="utf-8",
    )

    with _detected():
        _ = _write_initial_config(tmp_path)

    assert _read_config(tmp_path)["authors"] == [
        {"name": "Ada Lovelace", "role": "Author", "email": "ada@example.com"}
    ]


def test_initial_config_with_package(tmp_path: Path):
    """Verify that initialisation creates a configuration for the package"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        '__all__ = ["Widget"]\n__version__ = "1.0"\nclass Widget:\n    pass\n'
    )

    with (
        patch("great_docs._install.probe.detect_docstring_style", return_value="numpy"),
        patch("great_docs._install.probe.detect_dynamic_mode", return_value=True),
    ):
        _ = _write_initial_config(tmp_path)

    assert "parser: numpy" in (tmp_path / "great-docs.yml").read_text()


def test_initial_config_is_template_with_detected_values(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n')
    categories: dict[str, object] = {
        "classes": ["Thing"],
        "class_methods": {"Thing": 0},
        "class_method_names": {},
        "cyclic_alias_count": 0,
    }

    with _detected(names=["Thing"], categories=categories, style="google"):
        _ = _write_initial_config(tmp_path)

    text = (tmp_path / "great-docs.yml").read_text()
    # Detected values are live:
    assert "\nparser: google\n" in text
    assert "\ndynamic: false\n" in text
    assert "  - title: Classes" in text
    assert "      - Thing" in text
    # Full template is present (a key init never used to emit) but commented:
    assert "# seo:" in text
    # Parses and round-trips through the config loader:
    cfg = _read_config(tmp_path)
    assert cfg["parser"] == "google"
    assert cfg["dynamic"] is False
    assert cfg["reference"][0]["title"] == "Classes"
    assert "module" not in cfg


def test_initial_config_turns_off_dynamic_mode_for_cyclic_aliases(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    categories: dict[str, object] = {"classes": ["Thing"], "cyclic_alias_count": 2}

    # A passing probe shows that the cycles alone select `dynamic: false`.
    with _detected(names=["Thing"], categories=categories, dynamic=True):
        lines = _write_initial_config(tmp_path)

    assert _read_config(tmp_path)["dynamic"] is False
    assert "Detected 2 cyclic alias(es), using dynamic: false" in lines


def test_initial_config_records_a_module_named_unlike_the_distribution(tmp_path: Path):
    write_pyproject(tmp_path, "py-yaml12")
    (tmp_path / "yaml12.pyi").write_text("")

    with _detected(dynamic=True):
        _ = _write_initial_config(tmp_path)

    assert _read_config(tmp_path)["module"] == "yaml12"


def test_initial_config_without_package_is_not_empty(tmp_path: Path):
    """A project with no packaging files and no package still gets live defaults"""
    _ = _write_initial_config(tmp_path)

    cfg = _read_config(tmp_path)
    assert cfg["parser"] == "numpy"
    assert cfg["dynamic"] is True


def test_initial_config_keeps_an_existing_file_without_force(tmp_path: Path):
    config_path = tmp_path / "great-docs.yml"
    _ = config_path.write_text("parser: numpy\n")

    lines = _write_initial_config(tmp_path, force=False)

    assert config_path.read_text() == "parser: numpy\n"
    assert lines == [
        f"great-docs.yml already exists at {config_path}\n"
        "Use --force to overwrite it (this will reset to defaults)."
    ]


def test_initial_config_without_exports(tmp_path: Path):
    """A package whose exports cannot be discovered still gets its parser and dynamic mode"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

    with _detected(style="google"):
        _ = _write_initial_config(tmp_path)

    content = (tmp_path / "great-docs.yml").read_text()
    assert "parser: google" in content
    assert "dynamic: false" in content


def test_initial_config_for_an_unloadable_package(tmp_path: Path):
    """Verify that a griffe load failure selects NumPy and `dynamic: true`"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "unloadable_pkg_q7z"\n')

    lines = _write_initial_config(tmp_path)

    content = (tmp_path / "great-docs.yml").read_text()
    assert "\nparser: numpy\n" in content
    assert "\ndynamic: true\n" in content
    assert any("Could not load package for docstring detection" in line for line in lines)
