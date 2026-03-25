"""Tests for Harper grammar checker integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from great_docs._harper import (
    find_harper_cli,
    get_harper_version,
    check_harper_available,
    run_harper_on_text,
    run_harper,
    HarperNotFoundError,
    HarperError,
    HarperLint,
    HarperFileResult,
)
from great_docs.core import GreatDocs
from great_docs.cli import cli


class TestHarperCLIDetection:
    """Tests for harper-cli detection."""

    def test_find_harper_cli_returns_path_when_installed(self):
        """Test that find_harper_cli returns a path when harper is installed."""
        path = find_harper_cli()
        # This test will pass if harper is installed, skip otherwise
        if path is None:
            pytest.skip("harper-cli not installed")
        assert path is not None
        assert Path(path).exists()

    def test_check_harper_available_returns_tuple(self):
        """Test that check_harper_available returns appropriate tuple."""
        available, message = check_harper_available()
        assert isinstance(available, bool)
        assert isinstance(message, str)
        if available:
            assert "harper" in message.lower()
        else:
            assert "install" in message.lower()


class TestHarperTextChecking:
    """Tests for Harper text checking functions."""

    @pytest.fixture
    def skip_if_no_harper(self):
        """Skip test if harper-cli is not installed."""
        if find_harper_cli() is None:
            pytest.skip("harper-cli not installed")

    def test_run_harper_on_text_with_correct_text(self, skip_if_no_harper):
        """Test checking text with no errors."""
        lints = run_harper_on_text("This is a correct sentence.")
        # Should have few or no lints for correct text
        spelling_lints = [l for l in lints if l.rule == "SpellCheck"]
        assert len(spelling_lints) == 0

    def test_run_harper_on_text_with_misspelling(self, skip_if_no_harper):
        """Test checking text with a spelling error."""
        lints = run_harper_on_text("This is a tset of spelling.")
        # Should detect the misspelling
        spelling_lints = [l for l in lints if l.rule == "SpellCheck"]
        assert len(spelling_lints) >= 1
        assert any("tset" in l.matched_text for l in spelling_lints)

    def test_run_harper_on_text_with_grammar_error(self, skip_if_no_harper):
        """Test checking text with a grammar error."""
        lints = run_harper_on_text("Their going to the store.")
        # Should detect the their/they're confusion
        grammar_lints = [l for l in lints if l.kind == "Grammar"]
        assert len(grammar_lints) >= 1

    def test_run_harper_on_text_with_dialect(self, skip_if_no_harper):
        """Test checking text with different dialects."""
        # Both dialects should work without error
        lints_us = run_harper_on_text("Color is correct.", dialect="us")
        lints_uk = run_harper_on_text("Colour is correct.", dialect="uk")
        # These are both valid spellings in their respective dialects
        assert isinstance(lints_us, list)
        assert isinstance(lints_uk, list)

    def test_run_harper_on_text_with_only_rules(self, skip_if_no_harper):
        """Test filtering to specific rules."""
        text = "This is a tset. Their going to the store."
        # Only check spelling
        lints = run_harper_on_text(text, only_rules=["SpellCheck"])
        # Should only have SpellCheck lints
        assert all(l.rule == "SpellCheck" for l in lints)

    def test_run_harper_on_text_with_ignore_rules(self, skip_if_no_harper):
        """Test ignoring specific rules."""
        text = "This is a tset. Their going to the store."
        # Ignore spelling, check everything else
        lints = run_harper_on_text(text, ignore_rules=["SpellCheck"])
        # Should not have SpellCheck lints
        assert all(l.rule != "SpellCheck" for l in lints)


class TestHarperFileChecking:
    """Tests for Harper file checking functions."""

    @pytest.fixture
    def skip_if_no_harper(self):
        """Skip test if harper-cli is not installed."""
        if find_harper_cli() is None:
            pytest.skip("harper-cli not installed")

    def test_run_harper_on_markdown_file(self, skip_if_no_harper):
        """Test checking a markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test\n\nThis is a tset document.")

            results = run_harper([md_file])
            assert len(results) == 1
            assert results[0].lint_count >= 1

    def test_run_harper_on_multiple_files(self, skip_if_no_harper):
        """Test checking multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md1 = Path(tmpdir) / "test1.md"
            md2 = Path(tmpdir) / "test2.md"
            md1.write_text("# Test 1\n\nCorrect text here.")
            md2.write_text("# Test 2\n\nThis has a tset error.")

            results = run_harper([md1, md2])
            assert len(results) == 2


class TestHarperLintDataclass:
    """Tests for HarperLint dataclass."""

    def test_harper_lint_creation(self):
        """Test creating a HarperLint instance."""
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

    def test_harper_file_result_creation(self):
        """Test creating a HarperFileResult instance."""
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


class TestGreatDocsProofread:
    """Tests for GreatDocs.proofread() method."""

    @pytest.fixture
    def skip_if_no_harper(self):
        """Skip test if harper-cli is not installed."""
        if find_harper_cli() is None:
            pytest.skip("harper-cli not installed")

    def test_proofread_correct_text(self, skip_if_no_harper):
        """Test proofreading a file with correct text."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "correct.qmd"
            test_file.write_text("""---
title: "Test Document"
---

This is a simple test document with correct spelling and grammar.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.proofread()

            assert "files_checked" in results
            assert "total_issues" in results
            assert "by_kind" in results
            assert "issues" in results

    def test_proofread_with_errors(self, skip_if_no_harper):
        """Test proofreading a file with errors."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "errors.qmd"
            test_file.write_text("""---
title: "Test Document"
---

This documment has mispelled words and their going to be detected.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.proofread()

            assert results["total_issues"] > 0
            assert len(results["issues"]) > 0

    def test_proofread_with_custom_dictionary(self, skip_if_no_harper):
        """Test proofreading with custom dictionary."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            # Use a word that Harper doesn't know
            test_file = user_guide_dir / "custom.qmd"
            test_file.write_text("""---
title: "Test"
---

The griffe library is useful.
""")

            gd = GreatDocs(project_path=project_path)

            # Without custom dictionary
            results_without = gd.proofread()
            griffe_issues_without = [
                i for i in results_without["issues"] if "griffe" in i["matched_text"]
            ]

            # With custom dictionary
            results_with = gd.proofread(custom_dictionary=["griffe"])
            griffe_issues_with = [
                i for i in results_with["issues"] if "griffe" in i["matched_text"]
            ]

            # Should have fewer griffe-related issues with dictionary
            assert len(griffe_issues_with) <= len(griffe_issues_without)

    def test_proofread_only_rules(self, skip_if_no_harper):
        """Test proofreading with only specific rules."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "mixed.qmd"
            test_file.write_text("""---
title: "Test"
---

This tset has errors. Their going to be caught.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.proofread(only_rules=["SpellCheck"])

            # All issues should be from SpellCheck
            assert all(i["rule"] == "SpellCheck" for i in results["issues"])


class TestProofreadCLI:
    """Tests for the proofread CLI command."""

    @pytest.fixture
    def skip_if_no_harper(self):
        """Skip test if harper-cli is not installed."""
        if find_harper_cli() is None:
            pytest.skip("harper-cli not installed")

    def test_proofread_help(self):
        """Test proofread --help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["proofread", "--help"])
        assert result.exit_code == 0
        assert "proofread" in result.output.lower()
        assert "harper" in result.output.lower()

    def test_proofread_no_files(self, skip_if_no_harper):
        """Test proofread with no documentation files."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create empty directory (no docs)
            result = runner.invoke(cli, ["proofread"])
            # Should exit cleanly when no files found
            assert "No documentation files found" in result.output or result.exit_code == 0

    def test_proofread_json_output(self, skip_if_no_harper):
        """Test proofread with JSON output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create a simple markdown file
            Path("README.md").write_text("# Test\n\nThis is a tset.")

            result = runner.invoke(cli, ["proofread", "README.md", "--json-output"])
            # Output should be valid JSON
            import json

            try:
                data = json.loads(result.output)
                assert "total_issues" in data
                assert "issues" in data
            except json.JSONDecodeError:
                pytest.fail("Output is not valid JSON")

    def test_proofread_compact_output(self, skip_if_no_harper):
        """Test proofread with compact output."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("README.md").write_text("# Test\n\nThis is a tset.")

            result = runner.invoke(cli, ["proofread", "README.md", "--compact"])
            # Compact output should have file:line:col format
            if result.exit_code == 1:  # Issues found
                assert "README.md:" in result.output


class TestSpellCheckDeprecation:
    """Tests for spell-check deprecation warning."""

    def test_spell_check_help_shows_deprecated(self):
        """Test spell-check --help shows deprecated notice."""
        runner = CliRunner()
        result = runner.invoke(cli, ["spell-check", "--help"])
        assert result.exit_code == 0
        assert "DEPRECATED" in result.output or "deprecated" in result.output.lower()
        assert "proofread" in result.output.lower()
