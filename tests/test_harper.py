import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from great_docs._harper import (
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
    """Proofreading a file with correct text returns expected structure."""
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
        assert "files_checked" in results
        assert "total_issues" in results
        assert "by_kind" in results
        assert "issues" in results


@requires_harper
def test_proofread_with_errors():
    """Proofreading a file with errors finds issues."""
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
        assert results["total_issues"] > 0
        assert len(results["issues"]) > 0


@requires_harper
def test_proofread_with_custom_dictionary():
    """Custom dictionary reduces griffe-related issues."""
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
        results_without = gd.proofread()
        griffe_issues_without = [
            i for i in results_without["issues"] if "griffe" in i["matched_text"]
        ]
        results_with = gd.proofread(custom_dictionary=["griffe"])
        griffe_issues_with = [i for i in results_with["issues"] if "griffe" in i["matched_text"]]
        assert len(griffe_issues_with) <= len(griffe_issues_without)


@requires_harper
def test_proofread_only_rules():
    """Proofreading with only specific rules limits results."""
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
        assert all(i["rule"] == "SpellCheck" for i in results["issues"])


def test_proofread_help():
    """proofread --help exits cleanly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["proofread", "--help"])
    assert result.exit_code == 0
    assert "proofread" in result.output.lower()
    assert "harper" in result.output.lower()


@requires_harper
def test_proofread_no_files():
    """Proofread with no documentation files exits cleanly."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["proofread"])
        assert "No documentation files found" in result.output or result.exit_code == 0


@requires_harper
def test_proofread_json_output():
    """Proofread with JSON output produces valid JSON."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("README.md").write_text("# Test\n\nThis is a tset.")
        result = runner.invoke(cli, ["proofread", "README.md", "--json-output"])
        try:
            data = json.loads(result.output)
            assert "total_issues" in data
            assert "issues" in data
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")


@requires_harper
def test_proofread_compact_output():
    """Proofread with compact output has file:line:col format."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("README.md").write_text("# Test\n\nThis is a tset.")
        result = runner.invoke(cli, ["proofread", "README.md", "--compact"])
        if result.exit_code == 1:
            assert "README.md:" in result.output


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


@patch("great_docs._harper.shutil.which")
def test_find_harper_cli_from_path(mock_which):
    """Finds harper-cli on PATH."""
    mock_which.side_effect = lambda name: "/usr/bin/harper-cli" if name == "harper-cli" else None
    assert find_harper_cli() == "/usr/bin/harper-cli"


@patch("great_docs._harper.shutil.which")
def test_find_harper_cli_alternative_name(mock_which):
    """Falls back to 'harper' if 'harper-cli' not found."""
    mock_which.side_effect = lambda name: "/usr/bin/harper" if name == "harper" else None
    assert find_harper_cli() == "/usr/bin/harper"


@patch("great_docs._harper.shutil.which", return_value=None)
@patch("great_docs._harper.Path.home")
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


@patch("great_docs._harper.shutil.which", return_value=None)
@patch("great_docs._harper.Path.home")
def test_find_harper_cli_not_found(mock_home, mock_which):
    """Returns None when harper-cli is nowhere."""
    with tempfile.TemporaryDirectory() as tmp:
        mock_home.return_value = Path(tmp)
        assert find_harper_cli() is None


@patch("great_docs._harper.subprocess.run")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_success(mock_find, mock_run):
    """Parses version from 'harper-cli 1.12.0' output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="harper-cli 1.12.0\n")
    assert get_harper_version() == "1.12.0"


@patch("great_docs._harper.subprocess.run")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_no_space(mock_find, mock_run):
    """Returns raw output when no space in version string."""
    mock_run.return_value = MagicMock(returncode=0, stdout="1.12.0\n")
    assert get_harper_version() == "1.12.0"


@patch("great_docs._harper.find_harper_cli", return_value=None)
def test_get_harper_version_not_installed(mock_find):
    """Returns None when harper-cli not installed."""
    assert get_harper_version() is None


@patch("great_docs._harper.subprocess.run")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_subprocess_error(mock_find, mock_run):
    """Returns None on subprocess error."""
    mock_run.side_effect = subprocess.SubprocessError("fail")
    assert get_harper_version() is None


@patch("great_docs._harper.subprocess.run")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_get_harper_version_nonzero_exit(mock_find, mock_run):
    """Returns None on non-zero exit code."""
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    assert get_harper_version() is None


@patch("great_docs._harper.subprocess.run")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_run_harper_empty_output(mock_find, mock_run):
    """Returns empty list when harper produces no output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    results = run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")
    assert results == []


@patch("great_docs._harper.subprocess.run")
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


@patch("great_docs._harper.find_harper_cli", return_value=None)
def test_run_harper_not_installed(mock_find):
    """Raises HarperNotFoundError when harper-cli not available."""
    with pytest.raises(HarperNotFoundError):
        run_harper([Path("file.md")])


@patch("great_docs._harper.subprocess.run")
def test_run_harper_timeout(mock_run):
    """Raises HarperError on timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="harper-cli", timeout=30)
    with pytest.raises(HarperError, match="timed out"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._harper.subprocess.run")
def test_run_harper_os_error(mock_run):
    """Raises HarperError on OSError."""
    mock_run.side_effect = OSError("permission denied")
    with pytest.raises(HarperError, match="Failed to run"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._harper.subprocess.run")
def test_run_harper_invalid_json(mock_run):
    """Raises HarperError on invalid JSON output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="not json{", stderr="")
    with pytest.raises(HarperError, match="Failed to parse"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._harper.subprocess.run")
def test_run_harper_stderr_error(mock_run):
    """Raises HarperError when stderr has real errors (not Note: lines)."""
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error: file not found\n")
    with pytest.raises(HarperError, match="harper-cli error"):
        run_harper([Path("file.md")], harper_path="/usr/bin/harper-cli")


@patch("great_docs._harper.subprocess.run")
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


@patch("great_docs._harper.subprocess.run")
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


@patch("great_docs._harper.subprocess.run")
def test_run_harper_on_text_empty(mock_run):
    """Returns empty list when no output."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    lints = run_harper_on_text("Good text.", harper_path="/usr/bin/harper-cli")
    assert lints == []


@patch("great_docs._harper.find_harper_cli", return_value=None)
def test_run_harper_on_text_not_installed(mock_find):
    """Raises HarperNotFoundError when harper-cli not available."""
    with pytest.raises(HarperNotFoundError):
        run_harper_on_text("Some text.")


@patch("great_docs._harper.subprocess.run")
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


@patch("great_docs._harper.subprocess.run")
def test_run_harper_on_text_timeout(mock_run):
    """Raises HarperError on timeout."""
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="harper-cli", timeout=30)
    with pytest.raises(HarperError, match="timed out"):
        run_harper_on_text("Text.", harper_path="/usr/bin/harper-cli")


@patch("great_docs._harper.find_harper_cli", return_value=None)
def test_check_harper_available_not_installed(mock_find):
    """Returns (False, message) when harper not found."""
    available, msg = check_harper_available()
    assert available is False
    assert "not installed" in msg


@patch("great_docs._harper.get_harper_version", return_value="1.12.0")
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_check_harper_available_with_version(mock_find, mock_version):
    """Returns (True, version_string) when installed."""
    available, msg = check_harper_available()
    assert available is True
    assert "1.12.0" in msg


@patch("great_docs._harper.get_harper_version", return_value=None)
@patch("great_docs._harper.find_harper_cli", return_value="/usr/bin/harper-cli")
def test_check_harper_available_unknown_version(mock_find, mock_version):
    """Returns (True, unknown) when version can't be determined."""
    available, msg = check_harper_available()
    assert available is True
    assert "unknown" in msg
