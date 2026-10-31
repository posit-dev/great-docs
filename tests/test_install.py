import shutil
import subprocess
from pathlib import Path

import pytest

from great_docs._install import update_gitignore
from great_docs._layout import Layout

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
