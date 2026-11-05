import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from great_docs._checks import proofread as proofreading
from great_docs._checks.harper import (
    HarperError,
    HarperFileResult,
    HarperLint,
    HarperNotFoundError,
    check_harper_available,
    extract_prose_from_markdown,
    find_harper_cli,
    get_builtin_dictionary,
    get_default_ignore_rules,
    get_harper_version,
    run_harper,
    run_harper_on_text,
)
from great_docs.cli import cli
from great_docs.core import GreatDocs
from tests.support import AUTHORED_PAGES, write_authored_pages

_harper_available = find_harper_cli() is not None
requires_harper = pytest.mark.skipif(not _harper_available, reason="harper-cli not installed")


@requires_harper
def test_find_harper_cli_returns_path_when_installed():
    """find_harper_cli returns a path when harper is installed."""
    path = find_harper_cli()
    assert path is not None
    assert Path(path).exists()


def test_check_harper_available_returns_tuple():
    """check_harper_available returns appropriate tuple."""
    available, message = check_harper_available()
    assert isinstance(available, bool)
    assert isinstance(message, str)
    if available:
        assert "harper" in message.lower()
    else:
        assert "install" in message.lower()


@requires_harper
def test_run_harper_on_text_correct_text():
    """Correct text has no spelling lints."""
    lints = run_harper_on_text("This is a correct sentence.")
    spelling_lints = [l for l in lints if l.rule == "SpellCheck"]
    assert len(spelling_lints) == 0


@requires_harper
def test_run_harper_on_text_misspelling():
    """Detects misspelled words."""
    lints = run_harper_on_text("This is a tset of spelling.")
    spelling_lints = [l for l in lints if l.rule == "SpellCheck"]
    assert len(spelling_lints) >= 1
    assert any("tset" in l.matched_text for l in spelling_lints)


@requires_harper
def test_run_harper_on_text_grammar_error():
    """Detects grammar errors."""
    lints = run_harper_on_text("Their going to the store.")
    grammar_lints = [l for l in lints if l.kind == "Grammar"]
    assert len(grammar_lints) >= 1


@requires_harper
def test_run_harper_on_text_dialect():
    """Both US and UK dialects work."""
    lints_us = run_harper_on_text("Color is correct.", dialect="us")
    lints_uk = run_harper_on_text("Colour is correct.", dialect="uk")
    assert isinstance(lints_us, list)
    assert isinstance(lints_uk, list)


@requires_harper
def test_run_harper_on_text_only_rules():
    """Filtering to specific rules returns only those rules."""
    text = "This is a tset. Their going to the store."
    lints = run_harper_on_text(text, only_rules=["SpellCheck"])
    assert all(l.rule == "SpellCheck" for l in lints)


@requires_harper
def test_run_harper_on_text_ignore_rules():
    """Ignoring specific rules excludes those rules."""
    text = "This is a tset. Their going to the store."
    lints = run_harper_on_text(text, ignore_rules=["SpellCheck"])
    assert all(l.rule != "SpellCheck" for l in lints)


@requires_harper
def test_run_harper_on_markdown_file():
    """Checks a markdown file and finds lints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        md_file = Path(tmpdir) / "test.md"
        md_file.write_text("# Test\n\nThis is a tset document.")
        results = run_harper([md_file])
        assert len(results) == 1
        assert results[0].lint_count >= 1


@requires_harper
def test_run_harper_on_multiple_files():
    """Checks multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        md1 = Path(tmpdir) / "test1.md"
        md2 = Path(tmpdir) / "test2.md"
        md1.write_text("# Test 1\n\nCorrect text here.")
        md2.write_text("# Test 2\n\nThis has a tset error.")
        results = run_harper([md1, md2])
        assert len(results) == 2


def test_harper_lint_creation():
    """Creates a HarperLint instance with all fields."""
    lint = HarperLint(
        rule="SpellCheck",
        kind="Spelling",
        line=1,
        column=10,
        message="Did you mean 'test'?",
        matched_text="tset",
        suggestions=["test"],
        priority=63,
        file="test.md",
    )
    assert lint.rule == "SpellCheck"
    assert lint.kind == "Spelling"
    assert lint.matched_text == "tset"


def test_harper_file_result_creation():
    """Creates a HarperFileResult instance."""
    result = HarperFileResult(
        file="test.md",
        lint_count=1,
        lints=[
            HarperLint(
                rule="SpellCheck",
                kind="Spelling",
                line=1,
                column=1,
                message="test",
                matched_text="tset",
            )
        ],
    )
    assert result.file == "test.md"
    assert result.lint_count == 1
    assert len(result.lints) == 1


@requires_harper
def test_proofread_correct_text():
    """Return a checked file with no error for correctly written text"""
    with tempfile.TemporaryDirectory() as project_dir:
        project_path = Path(project_dir)
        user_guide_dir = project_path / "user_guide"
        user_guide_dir.mkdir()
        test_file = user_guide_dir / "correct.qmd"
        test_file.write_text(
            """---
title: "Test Document"
---

This is a simple test document with correct spelling and grammar.
"""
        )
        gd = GreatDocs(project_path=project_path)
        results = gd.proofread()
        assert [r.file for r in results] == ["user_guide/correct.qmd"]
        assert results[0].error is None


@requires_harper
def test_proofread_with_errors():
    """Report issues for a page containing spelling and grammar errors"""
    with tempfile.TemporaryDirectory() as project_dir:
        project_path = Path(project_dir)
        user_guide_dir = project_path / "user_guide"
        user_guide_dir.mkdir()
        test_file = user_guide_dir / "errors.qmd"
        test_file.write_text(
            """---
title: "Test Document"
---

This documment has mispelled words and their going to be detected.
"""
        )
        gd = GreatDocs(project_path=project_path)
        results = gd.proofread()
        assert sum(len(r.issues) for r in results) > 0


@requires_harper
def test_proofread_with_custom_words():
    """Report no more `griffe` issues when the word is explicitly accepted"""
    with tempfile.TemporaryDirectory() as project_dir:
        project_path = Path(project_dir)
        user_guide_dir = project_path / "user_guide"
        user_guide_dir.mkdir()
        test_file = user_guide_dir / "custom.qmd"
        test_file.write_text(
            """---
title: "Test"
---

The griffe library is useful.
"""
        )
        gd = GreatDocs(project_path=project_path)
        results_without = gd.proofread(strict=True)
        griffe_issues_without = [
            i for r in results_without for i in r.issues if "griffe" in i.matched_text
        ]
        results_with = gd.proofread(custom_words=["griffe"], strict=True)
        griffe_issues_with = [
            i for r in results_with for i in r.issues if "griffe" in i.matched_text
        ]
        assert len(griffe_issues_with) <= len(griffe_issues_without)


@requires_harper
def test_proofread_only_rules():
    """Return only `SpellCheck` issues when that rule is selected"""
    with tempfile.TemporaryDirectory() as project_dir:
        project_path = Path(project_dir)
        user_guide_dir = project_path / "user_guide"
        user_guide_dir.mkdir()
        test_file = user_guide_dir / "mixed.qmd"
        test_file.write_text(
            """---
title: "Test"
---

This tset has errors. Their going to be caught.
"""
        )
        gd = GreatDocs(project_path=project_path)
        results = gd.proofread(only_rules=["SpellCheck"])
        assert all(i.rule == "SpellCheck" for r in results for i in r.issues)


def test_proofread_help():
    """proofread --help exits cleanly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["proofread", "--help"])
    assert result.exit_code == 0
    assert "proofread" in result.output.lower()
    assert "harper" in result.output.lower()


@requires_harper
def test_proofread_no_files(tmp_path, monkeypatch):
    """Proofread with no documentation files exits cleanly."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["proofread"])
    assert "No documentation files found" in result.output or result.exit_code == 0


@requires_harper
def test_proofread_json_output(tmp_path, monkeypatch):
    """Proofread with JSON output produces valid JSON."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("README.md").write_text("# Test\n\nThis is a tset.")
    result = runner.invoke(cli, ["proofread", "README.md", "--json-output"])
    try:
        data = json.loads(result.output)
        assert "total_issues" in data
        assert "issues" in data
    except json.JSONDecodeError:
        pytest.fail("Output is not valid JSON")


@requires_harper
def test_proofread_compact_output(tmp_path, monkeypatch):
    """Proofread with compact output has file:line:col format."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("README.md").write_text("# Test\n\nThis is a tset.")
    result = runner.invoke(cli, ["proofread", "README.md", "--compact"])
    if result.exit_code == 1:
        assert "README.md:" in result.output


@pytest.fixture
def stub_harper(monkeypatch):
    """Report one spelling issue on the first line of any text, without `harper-cli`"""

    def run_harper_on_text(text, **kwargs):
        return [HarperLint("SpellCheck", "Spelling", 1, 1, "Misspelled", "tset")]

    monkeypatch.setattr(
        "great_docs._checks.harper.check_harper_available", lambda: (True, "harper-cli 1.0")
    )
    monkeypatch.setattr("great_docs._checks.harper.run_harper_on_text", run_harper_on_text)


@pytest.mark.parametrize(
    ("args", "page"),
    [
        (["user_guide/a.qmd"], "user_guide/a.qmd"),
        (["--docs-dir", "user_guide"], "user_guide/a.qmd"),
    ],
    ids=["explicit-file", "docs-dir"],
)
def test_proofread_relative_qmd_page(tmp_path, monkeypatch, stub_harper, args, page):
    """Report a `.qmd` page reached by a relative path relative to the project root"""
    (tmp_path / "user_guide").mkdir()
    (tmp_path / "user_guide" / "a.qmd").write_text("This is a tset.\n")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["proofread", *args, "--project-path", ".", "--json-output"])

    assert [issue["file"] for issue in json.loads(result.stdout)["issues"]] == [page]


def test_check_qmd_page_outside_project_root(tmp_path, stub_harper):
    """Report a `.qmd` page outside the project root by the path given"""
    root = tmp_path / "project"
    root.mkdir()
    page = tmp_path / "elsewhere.qmd"
    page.write_text("This is a tset.\n")

    results = proofreading.check([page], root, proofreading.Options(), report=lambda _line: None)

    assert [r.file for r in results] == [str(page)]


def test_extract_prose_plain_text():
    """Plain text with no code blocks or frontmatter passes through."""
    content = "Hello world.\nSecond line."
    prose, mapping = extract_prose_from_markdown(content)
    assert "Hello world." in prose
    assert "Second line." in prose
    assert mapping[1] == 1
    assert mapping[2] == 2


def test_extract_prose_frontmatter():
    """YAML frontmatter at start of file is stripped."""
    content = "---\ntitle: Test\n---\nActual prose."
    prose, mapping = extract_prose_from_markdown(content)
    lines = prose.split("\n")
    # First 3 lines should be empty placeholders
    assert lines[0] == ""
    assert lines[1] == ""
    assert lines[2] == ""
    assert lines[3] == "Actual prose."
    assert mapping[4] == 4


def test_extract_prose_fenced_code_block():
    """Fenced code blocks are replaced with empty lines."""
    content = "Before code.\n```python\nprint('hi')\n```\nAfter code."
    prose, mapping = extract_prose_from_markdown(content)
    assert "Before code." in prose
    assert "After code." in prose
    assert "print('hi')" not in prose


def test_extract_prose_tilde_fence():
    """Tilde fenced code blocks are also stripped."""
    content = "Text.\n~~~\ncode\n~~~\nMore text."
    prose, mapping = extract_prose_from_markdown(content)
    assert "Text." in prose
    assert "More text." in prose
    assert "code" not in prose.split("\n")[2]


def test_extract_prose_inline_code_preserved():
    """Inline code like `foo` is kept in prose."""
    content = "Use `my_function()` here."
    prose, _ = extract_prose_from_markdown(content)
    assert "`my_function()`" in prose


def test_extract_prose_line_mapping():
    """Line mapping maps prose lines to original file lines correctly."""
    content = "---\ntitle: X\n---\n\nProse line."
    prose, mapping = extract_prose_from_markdown(content)
    # Line 5 in original is "Prose line."
    assert mapping[5] == 5


def test_extract_prose_multiple_code_blocks():
    """Multiple code blocks are all stripped."""
    content = "Intro.\n```\nblock1\n```\nMiddle.\n```\nblock2\n```\nEnd."
    prose, _ = extract_prose_from_markdown(content)
    assert "Intro." in prose
    assert "Middle." in prose
    assert "End." in prose
    assert "block1" not in prose.split("\n")[2]
    assert "block2" not in prose.split("\n")[6]


def test_get_builtin_dictionary():
    """Returns a non-empty list of strings."""
    words = get_builtin_dictionary()
    assert isinstance(words, list)
    assert len(words) > 0
    assert all(isinstance(w, str) for w in words)


def test_get_default_ignore_rules():
    """Returns a non-empty list of rule names."""
    rules = get_default_ignore_rules()
    assert isinstance(rules, list)
    assert len(rules) > 0


@patch("great_docs._checks.harper.shutil.which")
def test_find_harper_cli_from_path(mock_which):
    """Finds harper-cli on PATH."""
    mock_which.side_effect = lambda name: "/usr/bin/harper-cli" if name == "harper-cli" else None
    assert find_harper_cli() == "/usr/bin/harper-cli"


@patch("great_docs._checks.harper.shutil.which")
def test_find_harper_cli_alternative_name(mock_which):
    """Falls back to 'harper' if 'harper-cli' not found."""
    mock_which.side_effect = lambda name: "/usr/bin/harper" if name == "harper" else None
    assert find_harper_cli() == "/usr/bin/harper"


@patch("great_docs._checks.harper.shutil.which", return_value=None)
@patch("great_docs._checks.harper.Path.home")
def test_find_harper_cli_cargo_bin(mock_home, mock_which):
    """Falls back to ~/.cargo/bin/harper-cli."""
    with tempfile.TemporaryDirectory() as tmp:
        mock_home.return_value = Path(tmp)
        cargo_bin = Path(tmp) / ".cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        (cargo_bin / "harper-cli").write_text("#!/bin/sh\n")
        result = find_harper_cli()
        assert result is not None
        assert "harper-cli" in result


@patch("great_docs._checks.harper.shutil.which", return_value=None)
@patch("great_docs._checks.harper.Path.home")
def test_find_harper_cli_not_found(mock_home, mock_which):
    """Returns None when harper-cli is nowhere."""
    with tempfile.TemporaryDirectory() as tmp:
        mock_home.return_value = Path(tmp)
        assert find_harper_cli() is None


@patch("great_docs._checks.harper.subprocess.run")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_success(mock_find, mock_run):
    """Parses version from 'harper-cli 1.12.0' output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="harper-cli 1.12.0\n")
    assert get_harper_version() == "1.12.0"


@patch("great_docs._checks.harper.subprocess.run")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_no_space(mock_find, mock_run):
    """Returns raw output when no space in version string."""
    mock_run.return_value = MagicMock(returncode=0, stdout="1.12.0\n")
    assert get_harper_version() == "1.12.0"


@patch("great_docs._checks.harper.find_harper_cli", return_value=None)
def test_get_harper_version_not_installed(mock_find):
    """Returns None when harper-cli not installed."""
    assert get_harper_version() is None


@patch("great_docs._checks.harper.subprocess.run")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_subprocess_error(mock_find, mock_run):
    """Returns None on subprocess error."""
    mock_run.side_effect = subprocess.SubprocessError("fail")
    assert get_harper_version() is None


@patch("great_docs._checks.harper.subprocess.run")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_nonzero_exit(mock_find, mock_run):
    """Returns None on non-zero exit code."""
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    assert get_harper_version() is None


@patch("great_docs._checks.harper.subprocess.run")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_run_harper_empty_output(mock_find, mock_run):
    """Returns empty list when harper produces no output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    results = run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")
    assert results == []


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_json_results(mock_run):
    """Parses JSON output into HarperFileResult objects."""
    harper_output = json.dumps(
        [
            {
                "file": "test.md",
                "lint_count": 1,
                "lints": [
                    {
                        "rule": "SpellCheck",
                        "kind": "Spelling",
                        "line": 3,
                        "column": 10,
                        "message": "Did you mean 'test'?",
                        "matched_text": "tset",
                        "suggestions": ["test"],
                        "priority": 63,
                        "span": {"char_start": 20, "char_end": 24},
                    }
                ],
            }
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=harper_output, stderr="")
    results = run_harper([Path("test.md")], harper_path="/usr/bin/harper-cli")
    assert len(results) == 1
    assert results[0].file == "test.md"
    assert results[0].lint_count == 1
    assert len(results[0].lints) == 1
    assert results[0].lints[0].rule == "SpellCheck"
    assert results[0].lints[0].char_start == 20
    assert results[0].lints[0].char_end == 24


@patch("great_docs._checks.harper.find_harper_cli", return_value=None)
def test_run_harper_not_installed(mock_find):
    """Raises HarperNotFoundError when harper-cli not available."""
    with pytest.raises(HarperNotFoundError):
        run_harper([Path("file.md")])


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_timeout(mock_run):
    """Raises HarperError on timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="harper-cli", timeout=30)
    with pytest.raises(HarperError, match="timed out"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_os_error(mock_run):
    """Raises HarperError on OSError."""
    mock_run.side_effect = OSError("permission denied")
    with pytest.raises(HarperError, match="Failed to run"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_invalid_json(mock_run):
    """Raises HarperError on invalid JSON output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="not json{", stderr="")
    with pytest.raises(HarperError, match="Failed to parse"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_stderr_error(mock_run):
    """Raises HarperError when stderr has real errors (not Note: lines)."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: file not found\n")
    with pytest.raises(HarperError, match="harper-cli error"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_with_user_dict(mock_run):
    """User dictionary path is added to command."""
    mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
    run_harper(
        [Path("file.md")],
        harper_path="/usr/bin/harper-cli",
        user_dict_path=Path("/tmp/dict.txt"),
    )
    cmd = mock_run.call_args[0][0]
    assert "--user-dict-path" in cmd
    assert "/tmp/dict.txt" in cmd


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_on_text_json_results(mock_run):
    """Parses JSON output into HarperLint objects."""
    harper_output = json.dumps(
        [
            {
                "lints": [
                    {
                        "rule": "SpellCheck",
                        "kind": "Spelling",
                        "line": 1,
                        "column": 5,
                        "message": "Misspelled",
                        "matched_text": "tset",
                        "suggestions": ["test"],
                        "priority": 63,
                        "span": {"char_start": 5, "char_end": 9},
                    }
                ]
            }
        ]
    )
    mock_run.return_value = MagicMock(returncode=0, stdout=harper_output, stderr="")
    lints = run_harper_on_text("This tset.", harper_path="/usr/bin/harper-cli")
    assert len(lints) == 1
    assert lints[0].rule == "SpellCheck"
    assert lints[0].matched_text == "tset"
    assert lints[0].char_start == 5
    assert lints[0].file == "<stdin>"


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_on_text_empty(mock_run):
    """Returns empty list when no output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    lints = run_harper_on_text("Good text.", harper_path="/usr/bin/harper-cli")
    assert lints == []


@patch("great_docs._checks.harper.find_harper_cli", return_value=None)
def test_run_harper_on_text_not_installed(mock_find):
    """Raises HarperNotFoundError when harper-cli not available."""
    with pytest.raises(HarperNotFoundError):
        run_harper_on_text("Some text.")


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_on_text_with_user_dict(mock_run):
    """User dictionary path is added to command for text checking."""
    mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
    run_harper_on_text(
        "Some text.",
        harper_path="/usr/bin/harper-cli",
        user_dict_path=Path("/tmp/dict.txt"),
    )
    cmd = mock_run.call_args[0][0]
    assert "--user-dict-path" in cmd


@patch("great_docs._checks.harper.subprocess.run")
def test_run_harper_on_text_timeout(mock_run):
    """Raises HarperError on timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="harper-cli", timeout=30)
    with pytest.raises(HarperError, match="timed out"):
        run_harper_on_text("Text.", harper_path="/usr/bin/harper-cli")


@patch("great_docs._checks.harper.find_harper_cli", return_value=None)
def test_check_harper_available_not_installed(mock_find):
    """Returns (False, message) when harper not found."""
    available, msg = check_harper_available()
    assert available is False
    assert "not installed" in msg


@patch("great_docs._checks.harper.get_harper_version", return_value="1.12.0")
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_check_harper_available_with_version(mock_find, mock_version):
    """Returns (True, version_string) when installed."""
    available, msg = check_harper_available()
    assert available is True
    assert "1.12.0" in msg


@patch("great_docs._checks.harper.get_harper_version", return_value=None)
@patch("great_docs._checks.harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_check_harper_available_unknown_version(mock_find, mock_version):
    """Returns (True, unknown) when version can't be determined."""
    available, msg = check_harper_available()
    assert available is True
    assert "unknown" in msg


@patch("subprocess.run")
def test_run_harper_only_rules_extends_cmd(mock_run):
    """When only_rules is provided, --only flag is added."""
    mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
    run_harper(
        [Path("test.md")],
        only_rules=["spelling", "grammar"],
        harper_path="/usr/bin/harper-cli",
    )
    cmd = mock_run.call_args[0][0]
    assert "--only" in cmd
    idx = cmd.index("--only")
    assert cmd[idx + 1] == "spelling,grammar"


GUIDE_DIRECTORIES = pytest.mark.parametrize(
    ("settings", "directory"),
    [("user_guide: guides\n", "guides"), ("", "user-guide")],
    ids=["configured", "hyphenated"],
)


@GUIDE_DIRECTORIES
def test_proofread_reads_the_guide_directory_the_build_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: str, directory: str
):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (tmp_path / "great-docs.yml").write_text(settings)
    (tmp_path / directory).mkdir()
    (tmp_path / directory / "page.qmd").write_text("# Page\n")
    checked: list[Path] = []

    def check(files: list[Path], *args: object, **kwargs: object) -> list[object]:
        checked.extend(files)
        return []

    monkeypatch.setattr(proofreading, "check", check)

    GreatDocs(project_path=tmp_path).proofread()

    assert checked == [tmp_path / directory / "page.qmd"]


@GUIDE_DIRECTORIES
def test_proofread_command_reads_the_guide_directory_the_build_uses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: str, directory: str
):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (tmp_path / "great-docs.yml").write_text(settings)
    (tmp_path / directory).mkdir()
    (tmp_path / directory / "page.qmd").write_text("# Page\n")
    checked: list[Path] = []

    def check(files: list[Path], *args: object, **kwargs: object) -> list[object]:
        checked.extend(files)
        return []

    monkeypatch.setattr(proofreading, "check", check)
    monkeypatch.setattr(
        "great_docs._checks.harper.check_harper_available", lambda: (True, "harper-cli")
    )

    result = CliRunner().invoke(cli, ["proofread", "--project-path", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert checked == [tmp_path / directory / "page.qmd"]


@pytest.mark.parametrize("directory", ["src", "python", "lib"])
def test_proofread_reads_docstrings_where_the_build_loads_the_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str
):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (tmp_path / directory / "demo").mkdir(parents=True)
    (tmp_path / directory / "demo" / "__init__.py").write_text('"""A demo"""\n')
    checked: list[Path] = []

    def check(files: list[Path], *args: object, **kwargs: object) -> list[object]:
        checked.extend(files)
        return []

    monkeypatch.setattr(proofreading, "check", check)

    GreatDocs(project_path=tmp_path).proofread(include_docs=False, include_docstrings=True)

    assert checked == [tmp_path / directory / "demo" / "__init__.py"]


def _record_checked_files(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Record the files passed to proofreading without checking their prose

    Parameters
    ----------
    monkeypatch
        The test's patcher.

    Returns
    -------
    :
        A list populated with project-relative POSIX paths in discovery order.
    """
    checked: list[str] = []

    def check(files: list[Path], root: Path, *args: object, **kwargs: object) -> list[object]:
        checked.extend(path.relative_to(root).as_posix() for path in files)
        return []

    monkeypatch.setattr(proofreading, "check", check)
    return checked


def test_proofread_reads_the_authored_pages_the_build_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    write_authored_pages(tmp_path)
    checked = _record_checked_files(monkeypatch)

    GreatDocs(project_path=tmp_path).proofread(include_docstrings=True)

    assert checked == [*AUTHORED_PAGES, "src/demo/__init__.py"]


def test_proofread_command_reads_the_authored_pages_the_build_publishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    write_authored_pages(tmp_path)
    checked = _record_checked_files(monkeypatch)
    monkeypatch.setattr(
        "great_docs._checks.harper.check_harper_available", lambda: (True, "harper-cli")
    )

    result = CliRunner().invoke(
        cli, ["proofread", "--project-path", str(tmp_path), "--include-docstrings"]
    )

    assert result.exit_code == 0, result.output
    assert checked == [*AUTHORED_PAGES, "src/demo/__init__.py"]


def _write_unnamed_project(root: Path) -> None:
    """
    Write a project with a configured module and no distribution name
    """
    (root / "great-docs.yml").write_text("module: beta\n")
    for package in ("alpha", "beta"):
        (root / package).mkdir()
        (root / package / "__init__.py").write_text(f'"""The {package} package"""\n')


def test_proofread_reads_the_configured_module_of_a_project_without_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_unnamed_project(tmp_path)
    checked = _record_checked_files(monkeypatch)

    GreatDocs(project_path=tmp_path).proofread(include_docs=False, include_docstrings=True)

    assert checked == ["beta/__init__.py"]


def test_proofread_command_reads_the_configured_module_of_a_project_without_a_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_unnamed_project(tmp_path)
    checked = _record_checked_files(monkeypatch)
    monkeypatch.setattr(
        "great_docs._checks.harper.check_harper_available", lambda: (True, "harper-cli")
    )

    result = CliRunner().invoke(
        cli, ["proofread", "--project-path", str(tmp_path), "--include-docstrings"]
    )

    assert result.exit_code == 0, result.output
    assert checked == ["beta/__init__.py"]
