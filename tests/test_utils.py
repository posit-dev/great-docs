import pytest

from great_docs._utils import (
    GITIGNORE_CONTENT,
    QUARTO_YML_HEADER,
    fenced_lines,
    is_great_docs_build_dir,
    is_in_great_docs_build_dir,
    validate_build_dir,
)


def test_fenced_lines_without_markers_returns_lines_and_clear_mask():
    assert fenced_lines("first\nsecond") == (
        ["first", "second"],
        [False, False],
    )


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_lines_marks_opening_content_and_closing_lines(fence: str):
    assert fenced_lines(f"before\n{fence}python\ninside\n{fence}\nafter") == (
        ["before", f"{fence}python", "inside", fence, "after"],
        [False, True, True, True, False],
    )


def test_fenced_lines_requires_a_matching_long_enough_closer():
    assert fenced_lines("````text\ninside\n```\nstill inside\n````\nafter")[1] == [
        True,
        True,
        True,
        True,
        True,
        False,
    ]


@pytest.mark.parametrize("text", ["a `code` span", "value ~ default"])
def test_fenced_lines_ignores_non_fence_characters(text: str):
    assert fenced_lines(text) == ([text], [False])


@pytest.mark.parametrize(
    "parts",
    [
        ("great-docs", "index.qmd"),
    ],
)
def test_is_in_great_docs_build_dir_recognises_current_build(parts: tuple[str, ...], tmp_path):
    assert is_in_great_docs_build_dir(parts, tmp_path) is True


def test_is_in_great_docs_build_dir_recognises_historical_build(tmp_path):
    build_dir = tmp_path / "great-docs-0.2"
    build_dir.mkdir()
    (build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER, encoding="utf-8")

    assert is_in_great_docs_build_dir((build_dir.name, "index.qmd"), tmp_path) is True


@pytest.mark.parametrize(
    "parts",
    [
        (),
        ("docs", "great-docs-examples", "index.qmd"),
        ("great_docs_notes", "index.qmd"),
        ("great-docs-notes", "index.qmd"),
    ],
)
def test_is_in_great_docs_build_dir_rejects_non_build_paths(parts: tuple[str, ...], tmp_path):
    if parts:
        (tmp_path / parts[0]).mkdir(exist_ok=True)

    assert is_in_great_docs_build_dir(parts, tmp_path) is False


def test_is_great_docs_build_dir_recognises_a_pristine_clone(tmp_path):
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    assert is_great_docs_build_dir(build_dir) is True


def test_is_great_docs_build_dir_rejects_a_foreign_gitignore(tmp_path):
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    assert is_great_docs_build_dir(build_dir) is False


def test_is_great_docs_build_dir_rejects_a_pristine_gitignore_alongside_other_content(tmp_path):
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")
    (build_dir / "notes.txt").write_text("unrelated user file", encoding="utf-8")

    assert is_great_docs_build_dir(build_dir) is False


def test_validate_build_dir_accepts_a_pristine_clone(tmp_path):
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    validate_build_dir(build_dir)  # must not raise


def test_validate_build_dir_rejects_a_foreign_directory(tmp_path):
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / "notes.txt").write_text("unrelated user file", encoding="utf-8")

    with pytest.raises(ValueError, match="not a Great Docs-generated Quarto project"):
        validate_build_dir(build_dir)


def test_fenced_lines_backtick_fence_with_backtick_in_info_not_fenced():
    """A backtick fence opening line whose info string contains a backtick is not marked fenced."""
    # e.g. ```py`thon — info contains "`", so it looks like inline code, not a block fence
    lines, fenced = fenced_lines("before\n```py`thon\ninside\n```\nafter")

    # The opening line should be False (treated as not a block fence)
    assert fenced[1] is False


def test_parse_seealso_blank_name_entry_is_dropped():
    """parse_seealso silently drops %seealso entries whose name is blank."""
    from great_docs._utils import parse_seealso

    # The entry " : desc" has a blank name after strip()
    result = parse_seealso("Some docs\n%seealso  : no-name, real_func\n")
    names = [name for name, _ in result]
    assert "" not in names
    assert "real_func" in names
