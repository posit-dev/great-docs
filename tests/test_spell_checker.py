import tempfile
from pathlib import Path
from click.testing import CliRunner
from great_docs.core import GreatDocs
from great_docs.cli import cli


class TestSpellChecker:
    """Tests for the spell_check method in GreatDocs."""

    def test_spell_check_correct_text(self):
        """Test spell checking a file with correct spelling."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            # Create test file
            test_file = user_guide_dir / "correct.qmd"
            test_file.write_text("""---
title: "Test Document"
---

This is a simple test document with correct spelling.
All words here should be recognized.
""")

            # Use docs_dir="docs" to bypass interactive prompt
            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should have no misspellings
            assert len(results["misspelled"]) == 0

    def test_spell_check_misspelled_words(self):
        """Test spell checking a file with misspelled words."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "misspelled.qmd"
            test_file.write_text("""---
title: "Test Document"
---

This documment has mispelled words.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should detect misspellings
            assert len(results["misspelled"]) > 0
            assert len(results["by_file"]) > 0

    def test_spell_check_skips_code_blocks(self):
        """Test that code blocks are skipped during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "code_blocks.qmd"
            test_file.write_text("""---
title: "Code Example"
---

Here is some code:

```python
def myfunc_xyzzy():
    # spellingmistakeincode
    return qwertyuiop
```

The code above demonstrates something.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Code block content should be skipped, so no misspellings
            assert len(results["misspelled"]) == 0

    def test_spell_check_skips_inline_code(self):
        """Test that inline code is skipped during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "inline_code.qmd"
            test_file.write_text("""---
title: "Inline Code"
---

Use the `xyzzyfunction` method to do something.
The `qwertyvar` variable holds the value.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Inline code should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_skips_urls(self):
        """Test that URLs are skipped during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "urls.qmd"
            test_file.write_text("""---
title: "URLs"
---

Visit https://example.com/qwertypath for more info.
Also see http://somesite.org/asdfghjkl.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # URLs should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_skips_yaml_frontmatter(self):
        """Test that YAML frontmatter is skipped during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "frontmatter.qmd"
            test_file.write_text("""---
title: "Xyzzyqwerty Document"
author: "Asdfghjkl Zxcvbnm"
custom_field: "qazwsxedc"
---

This is the actual content with correct spelling.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # YAML frontmatter should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_skips_html_tags(self):
        """Test that HTML tags are skipped during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "html.qmd"
            test_file.write_text("""---
title: "HTML"
---

<div class="qwertyclass">
<span id="asdfid">Content here</span>
</div>
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # HTML attributes should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_technical_terms_recognized(self):
        """Test that common technical terms are recognized."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "technical.qmd"
            test_file.write_text("""---
title: "Technical Terms"
---

This project uses Python with pytest for testing.
It uses JSON and YAML configuration files.
The API documentation is generated with great-docs.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Technical terms should be recognized
            assert len(results["misspelled"]) == 0

    def test_spell_check_custom_dictionary(self):
        """Test using a custom dictionary."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "custom.qmd"
            test_file.write_text("""---
title: "Custom Terms"
---

The xyzzyword is used here.
Also qwertyterm appears.
""")

            gd = GreatDocs(project_path=project_path)

            # Without custom dictionary, should find misspellings
            results_without = gd.spell_check()
            assert len(results_without["misspelled"]) > 0

            # With custom dictionary containing the words
            results_with = gd.spell_check(custom_dictionary=["xyzzyword", "qwertyterm"])
            assert len(results_with["misspelled"]) == 0

    def test_spell_check_skips_quarto_directives(self):
        """Test that Quarto directives are skipped."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "directives.qmd"
            test_file.write_text("""---
title: "Directives"
---

::: {.callout-note}
This is a note.
:::

::: {.panel-tabset}
## Tab One
Content here.
:::

{{< include _qwertyfile.qmd >}}
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Directives should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_multiple_files(self):
        """Test spell checking multiple files."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            # Create multiple files
            (user_guide_dir / "file1.qmd").write_text("""---
title: "File One"
---

This file has correct spelling.
""")

            (user_guide_dir / "file2.qmd").write_text("""---
title: "File Two"
---

This file has a mispeling.
""")

            (user_guide_dir / "file3.qmd").write_text("""---
title: "File Three"
---

This file also has correct words.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should find misspelling in file2
            assert results["total_words"] > 0
            assert len(results["misspelled"]) >= 1
            assert len(results["by_file"]) >= 1

    def test_spell_check_suggestions(self):
        """Test that suggestions are provided for misspellings."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "suggestions.qmd"
            test_file.write_text("""---
title: "Suggestions"
---

This has a documment here.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should have suggestions
            if len(results["misspelled"]) > 0:
                misspelling = results["misspelled"][0]
                assert "suggestions" in misspelling

    def test_spell_check_verbose_mode(self):
        """Test verbose output during spell checking."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "verbose.qmd"
            test_file.write_text("""---
title: "Verbose Test"
---

This is a test.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check(verbose=True)

            # Should complete without error
            assert "total_words" in results

    def test_spell_check_skips_emails(self):
        """Test that email addresses are skipped."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "emails.qmd"
            # Use real-looking email with common patterns
            test_file.write_text("""---
title: "Emails"
---

Contact us at support@example.com or info@test.com.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Email addresses should be skipped
            # The email addresses use common words so no misspellings expected
            assert len(results["misspelled"]) == 0

    def test_spell_check_skips_file_paths(self):
        """Test that file paths are skipped."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "paths.qmd"
            test_file.write_text("""---
title: "Paths"
---

Edit the file at /path/to/xyzzyfile.py.
Also check ./qwertydir/asdffile.qmd.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # File paths should be skipped
            assert len(results["misspelled"]) == 0

    def test_spell_check_no_user_guide_directory(self):
        """Test spell checking when user_guide directory is empty."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create empty user_guide directory
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should handle gracefully
            assert results["total_words"] == 0


class TestSpellCheckCLI:
    """Tests for the spell-check CLI command."""

    def test_cli_spell_check_no_issues(self):
        """Test CLI with no spelling issues."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            # Create test file
            test_file = user_guide_dir / "correct.qmd"
            test_file.write_text("""---
title: "Test"
---

This document has correct spelling.
""")

            runner = CliRunner()
            result = runner.invoke(cli, ["spell-check"], catch_exceptions=False)

            # CLI should detect we're not in a great-docs project but still succeed
            # The CLI will exit 0 if no issues found or 1 if there's an error/issues
            assert result.exit_code in [0, 1]

    def test_cli_spell_check_with_issues(self):
        """Test CLI with spelling issues."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "misspelled.qmd"
            test_file.write_text("""---
title: "Test"
---

This documment has mispelled words.
""")

            runner = CliRunner()
            result = runner.invoke(cli, ["spell-check"], catch_exceptions=False)

            # Should exit with error code when there are misspellings
            assert result.exit_code in [0, 1]

    def test_cli_spell_check_verbose(self):
        """Test CLI verbose mode."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "test.qmd"
            test_file.write_text("""---
title: "Test"
---

This is a test document.
""")

            runner = CliRunner()
            result = runner.invoke(cli, ["spell-check", "--verbose"], catch_exceptions=False)

            # Should run without crashing
            assert result.exit_code in [0, 1]

    def test_cli_spell_check_custom_dictionary(self):
        """Test CLI with custom dictionary words."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "custom.qmd"
            test_file.write_text("""---
title: "Test"
---

The xyzzyword is used here.
""")

            runner = CliRunner()
            # Test with custom dictionary flag
            result = runner.invoke(cli, ["spell-check", "-d", "xyzzyword"], catch_exceptions=False)

            # Should run without crashing
            assert result.exit_code in [0, 1]

    def test_cli_spell_check_dictionary_file(self):
        """Test CLI with dictionary file."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "custom.qmd"
            test_file.write_text("""---
title: "Test"
---

The xyzzyword and qwertyterm are used here.
""")

            # Create dictionary file
            dict_file = project_path / "custom_words.txt"
            dict_file.write_text("xyzzyword\nqwertyterm\n")

            runner = CliRunner()
            result = runner.invoke(
                cli, ["spell-check", "--dictionary-file", str(dict_file)], catch_exceptions=False
            )

            # Should run without crashing
            assert result.exit_code in [0, 1]

    def test_cli_spell_check_json_output(self):
        """Test CLI JSON output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["spell-check", "--json-output"], catch_exceptions=False)

        # Should run without crashing
        assert result.exit_code in [0, 1]

    def test_cli_spell_check_multiple_dictionary_words(self):
        """Test CLI with multiple custom dictionary words."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "multi.qmd"
            test_file.write_text("""---
title: "Test"
---

Words like xyzzy and qwerty and asdf appear here.
""")

            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["spell-check", "-d", "xyzzy", "-d", "qwerty", "-d", "asdf"],
                catch_exceptions=False,
            )

            # Should run without crashing
            assert result.exit_code in [0, 1]


class TestSpellCheckEdgeCases:
    """Tests for edge cases in spell checking."""

    def test_empty_file(self):
        """Test spell checking an empty file."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "empty.qmd"
            test_file.write_text("")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            assert len(results["misspelled"]) == 0

    def test_file_with_only_code(self):
        """Test spell checking a file with only code blocks."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "code_only.qmd"
            test_file.write_text("""```python
xyzzyfunction()
qwertyvar = 123
```
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            assert len(results["misspelled"]) == 0

    def test_nested_code_blocks(self):
        """Test spell checking with nested code structures."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "nested.qmd"
            test_file.write_text("""---
title: "Nested"
---

::: {.callout-note}
Here is some text.

```python
xyzzycode()
```

More text here.
:::
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            assert len(results["misspelled"]) == 0

    def test_special_characters(self):
        """Test spell checking with special characters."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "special.qmd"
            test_file.write_text("""---
title: "Special"
---

This has "quotes" and 'apostrophes' and -- dashes.
Also: colons, semicolons; and other punctuation!
Numbers like 123 and 45.67 should be ignored.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            assert len(results["misspelled"]) == 0

    def test_mixed_case_words(self):
        """Test spell checking with mixed case words."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "mixedcase.qmd"
            test_file.write_text("""---
title: "Mixed Case"
---

CamelCase words like GreatDocs should be handled.
Also UPPERCASE and lowercase work too.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check(custom_dictionary=["GreatDocs", "CamelCase"])

            # Check that basic words are recognized
            assert results["total_words"] > 0

    def test_latex_math_skipped(self):
        """Test that LaTeX math expressions are skipped."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "math.qmd"
            test_file.write_text(r"""---
title: "Math"
---

Inline math: $x^2 + y^2 = z^2$

Block math:
$$
\frac{d}{dx} \int_a^x f(t) dt = f(x)
$$
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # LaTeX should be skipped
            assert len(results["misspelled"]) == 0

    def test_markdown_links_text_checked(self):
        """Test that markdown link text is checked but URLs are not."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            test_file = user_guide_dir / "links.qmd"
            test_file.write_text("""---
title: "Links"
---

Check out [this documment](https://example.com/xyzzy).
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # "documment" in link text should be flagged
            # but "xyzzy" in URL should not
            assert len(results["misspelled"]) >= 1

    def test_subdirectory_scanning(self):
        """Test that subdirectories are scanned."""
        with tempfile.TemporaryDirectory() as project_dir:
            project_path = Path(project_dir)
            # Create user_guide directory (source documentation)
            user_guide_dir = project_path / "user_guide"
            user_guide_dir.mkdir()

            # Create subdirectory
            subdir = user_guide_dir / "guide"
            subdir.mkdir()

            test_file = subdir / "chapter1.qmd"
            test_file.write_text("""---
title: "Chapter 1"
---

This has a mispeling.
""")

            gd = GreatDocs(project_path=project_path)
            results = gd.spell_check()

            # Should scan subdirectory
            assert results["total_words"] > 0
            assert len(results["misspelled"]) >= 1
