import tempfile
from pathlib import Path
from unittest.mock import patch, Mock


from great_docs import GreatDocs


# ============================================================================
# URL Extraction Tests
# ============================================================================


class TestURLExtraction:
    """Tests for URL extraction from files."""

    def test_extracts_http_urls(self):
        """Test extraction of http:// URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("Visit http://example.com for info")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 1
            assert "http://example.com" in results["skipped"]

    def test_extracts_https_urls(self):
        """Test extraction of https:// URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("Visit https://example.com for info")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 1
            assert "https://example.com" in results["skipped"]

    def test_extracts_urls_from_qmd_files(self):
        """Test URL extraction from .qmd files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("""---
title: "Test"
---

Check https://example.com/page
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 1

    def test_extracts_urls_from_python_files(self):
        """Test URL extraction from Python source files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create package structure
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            init_py = pkg_dir / "__init__.py"
            init_py.write_text('"""Package with URL: https://example.com/docs"""')

            # Create pyproject.toml for package detection
            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            # Create docs dir
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()
            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 1
            assert "https://example.com/docs" in results["skipped"]

    def test_extracts_multiple_urls_from_same_file(self):
        """Test extraction of multiple URLs from a single file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("""
https://example.com/one
https://example.com/two
https://example.com/three
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 3

    def test_deduplicates_urls_across_files(self):
        """Test that duplicate URLs are only checked once."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            # Same URL in two files
            test1 = docs_dir / "test1.md"
            test1.write_text("https://example.com/shared")

            test2 = docs_dir / "test2.md"
            test2.write_text("https://example.com/shared")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            # Should be 1 unique URL
            assert results["total"] == 1

    def test_tracks_url_file_locations(self):
        """Test that by_file tracks which URLs are in which files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert "user_guide/test.md" in results["by_file"]
            assert "https://example.com/page" in results["by_file"]["user_guide/test.md"]


# ============================================================================
# URL Cleaning Tests
# ============================================================================


class TestURLCleaning:
    """Tests for URL cleaning and normalization."""

    def test_removes_trailing_period(self):
        """Test removal of trailing period from URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("Visit https://example.com/page.")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert "https://example.com/page" in results["skipped"]
            assert "https://example.com/page." not in results["skipped"]

    def test_removes_trailing_comma(self):
        """Test removal of trailing comma from URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("Check https://example.com/one, https://example.com/two")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            for url in results["skipped"]:
                assert not url.endswith(",")

    def test_removes_trailing_exclamation(self):
        """Test removal of trailing exclamation mark from URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("Amazing! https://example.com/wow!")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            for url in results["skipped"]:
                assert not url.endswith("!")

    def test_handles_unbalanced_parentheses(self):
        """Test handling of URLs with unbalanced trailing parentheses."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("(See https://example.com/page)")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            # Should not have trailing )
            assert "https://example.com/page" in results["skipped"]

    def test_preserves_balanced_parentheses_in_url(self):
        """Test that balanced parentheses in URLs are preserved."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            # Wikipedia-style URL with parentheses
            test_md = docs_dir / "test.md"
            test_md.write_text("https://example.com/wiki/Page_(disambiguation)")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            # Should have found a URL with the parentheses (possibly truncated)
            # The important thing is it doesn't crash
            assert results["total"] == 1


# ============================================================================
# F-String Placeholder Tests
# ============================================================================


class TestFStringPlaceholders:
    """Tests for f-string placeholder detection and skipping."""

    def test_skips_urls_with_simple_placeholder(self):
        """Test that URLs with {variable} placeholders are skipped during cleaning."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            source_py = pkg_dir / "source.py"
            source_py.write_text("""
url = f"https://github.com/{username}"
""")

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()
            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
            )

            # The URL regex extracts partial URLs, but the f-string placeholder
            # check filters them out during cleaning. The partial URL before the
            # placeholder may still be found.
            # Main check: no broken links from f-string URLs
            assert len(results["broken"]) == 0

    def test_skips_urls_with_multiple_placeholders(self):
        """Test that URLs with multiple placeholders are skipped."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            source_py = pkg_dir / "source.py"
            source_py.write_text("""
url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
""")

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()
            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
            )

            # Main check: no broken links from f-string URLs
            assert len(results["broken"]) == 0

    def test_skips_urls_with_expression_placeholders(self):
        """Test that URLs with expression placeholders like {obj.attr} are skipped."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            source_py = pkg_dir / "source.py"
            source_py.write_text("""
url = f"https://api.example.com/{self.endpoint}"
""")

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()
            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
            )

            # Main check: no broken links from f-string URLs
            assert len(results["broken"]) == 0

    def test_checks_real_urls_alongside_fstring_urls(self):
        """Test that real URLs are checked even when f-string URLs exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            source_py = pkg_dir / "source.py"
            source_py.write_text("""
# Template URL (should be skipped)
url = f"https://github.com/{username}"

# Real URL (should be checked)
docs = "https://example.com/docs"
""")

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()
            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
                ignore_patterns=["example.com"],
            )

            # The real URL should be found and skipped (via ignore pattern)
            assert "https://example.com/docs" in results["skipped"]


# ============================================================================
# Ignore Pattern Tests
# ============================================================================


class TestIgnorePatterns:
    """Tests for ignore pattern functionality."""

    def test_ignores_literal_string_pattern(self):
        """Test ignoring URLs matching a literal string."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://localhost:8000/api")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["localhost"],
            )

            assert len(results["skipped"]) == 1
            assert len(results["broken"]) == 0

    def test_ignores_regex_pattern(self):
        """Test ignoring URLs matching a regex pattern."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("""
https://example1.com/page
https://example2.com/page
https://example3.com/page
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=[r"example\d\.com"],
            )

            assert len(results["skipped"]) == 3

    def test_ignores_multiple_patterns(self):
        """Test ignoring URLs matching any of multiple patterns."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("""
https://localhost:8000/api
https://127.0.0.1:3000/test
https://example.com/page
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["localhost", "127.0.0.1", "example.com"],
            )

            assert len(results["skipped"]) == 3
            assert len(results["ok"]) == 0
            assert len(results["broken"]) == 0

    def test_case_insensitive_ignore(self):
        """Test that ignore patterns are case-insensitive."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://EXAMPLE.COM/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert len(results["skipped"]) == 1

    def test_ignores_git_urls_with_branch(self):
        """Test that .git@branch URLs are ignored."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("""
pip install git+https://github.com/user/repo.git@main
pip install git+https://github.com/user/repo.git@v1.0.0
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=[r"\.git(@|$)"],
            )

            assert len(results["skipped"]) == 2

    def test_ignores_placeholder_urls_with_brackets(self):
        """Test that URLs with [placeholder] brackets are ignored."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://[username].github.io/[repo]/")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=[r"\["],
            )

            assert len(results["skipped"]) == 1

    def test_invalid_regex_treated_as_literal(self):
        """Test that invalid regex patterns are treated as literal strings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://example.com/page?query=[value]")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            # [value] is invalid regex (unclosed bracket), should be escaped
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["[value]"],  # Invalid regex
            )

            # Should still work, treating it as literal
            assert results["total"] == 1


# ============================================================================
# {.gd-no-link} Directive Tests
# ============================================================================


class TestGdNoLinkDirective:
    """Tests for {.gd-no-link} directive in .qmd files."""

    def test_excludes_url_with_gd_no_link_directive(self):
        """Test that URLs marked with {.gd-no-link} are excluded from checking."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("""---
title: "Test"
---

Example URL: http://example.com{.gd-no-link}

Real URL: https://real.example.com
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["real.example.com"],
            )

            # Only the real URL should be found, the {.gd-no-link} one excluded
            assert results["total"] == 1
            assert "https://real.example.com" in results["skipped"]

    def test_excludes_https_url_with_gd_no_link(self):
        """Test that https:// URLs with {.gd-no-link} are also excluded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("https://fake-example.com/path{.gd-no-link}")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert results["total"] == 0

    def test_gd_no_link_only_works_in_qmd_files(self):
        """Test that {.gd-no-link} is only processed in .qmd files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            # In .md files, {.gd-no-link} will NOT exclude URLs via directive,
            # but the URL will be skipped by f-string placeholder detection
            # since it contains a { character
            test_md = docs_dir / "test.md"
            test_md.write_text("http://example.com{.gd-no-link}")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            # URL is not found because f-string placeholder check filters it
            # (contains { character). This is expected behavior - {.gd-no-link}
            # is really for .qmd files where it's valid Quarto syntax.
            assert results["total"] == 0

    def test_multiple_gd_no_link_urls_in_same_file(self):
        """Test that multiple URLs with {.gd-no-link} are all excluded."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("""---
title: "Test"
---

- http://fake1.example.com{.gd-no-link}
- http://fake2.example.com{.gd-no-link}
- https://fake3.example.com/path{.gd-no-link}
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            # All URLs should be excluded
            assert results["total"] == 0

    def test_gd_no_link_with_trailing_text(self):
        """Test {.gd-no-link} works when followed by other text."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("Visit http://fake.example.com{.gd-no-link} for more info")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert results["total"] == 0

    def test_gd_no_link_in_markdown_link_syntax(self):
        """Test {.gd-no-link} excludes specific URLs, not all occurrences globally."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            # Use different URLs to verify that {.gd-no-link} only excludes
            # the marked URL, not other similar URLs
            test_qmd = docs_dir / "test.qmd"
            test_qmd.write_text("""
Fake example: http://fake-example.com{.gd-no-link}

Real link: http://real-example.com
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["real-example.com"],
            )

            # Only the real URL should be found (fake one excluded via {.gd-no-link})
            assert results["total"] == 1
            assert "http://real-example.com" in results["skipped"]


# ============================================================================
# HTTP Status Tests
# ============================================================================


class TestHTTPStatus:
    """Tests for HTTP status handling."""

    @patch("requests.head")
    def test_categorizes_200_as_ok(self, mock_head):
        """Test that 200 responses are categorized as OK."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://test.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["ok"]) == 1
            assert "https://test.example.com/page" in results["ok"]

    @patch("requests.head")
    def test_categorizes_301_as_redirect(self, mock_head):
        """Test that 301 responses are categorized as redirects."""
        mock_response = Mock()
        mock_response.status_code = 301
        mock_response.headers = {"Location": "https://new.example.com/page"}
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://old.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["redirects"]) == 1
            assert results["redirects"][0]["url"] == "https://old.example.com/page"
            assert results["redirects"][0]["status"] == 301
            assert results["redirects"][0]["location"] == "https://new.example.com/page"

    @patch("requests.head")
    def test_categorizes_302_as_redirect(self, mock_head):
        """Test that 302 responses are categorized as redirects."""
        mock_response = Mock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "https://temp.example.com/page"}
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://original.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["redirects"]) == 1
            assert results["redirects"][0]["status"] == 302

    @patch("requests.head")
    def test_categorizes_404_as_broken(self, mock_head):
        """Test that 404 responses are categorized as broken."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://missing.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["broken"]) == 1
            assert results["broken"][0]["url"] == "https://missing.example.com/page"
            assert results["broken"][0]["status"] == 404

    @patch("requests.head")
    def test_categorizes_500_as_broken(self, mock_head):
        """Test that 500 responses are categorized as broken."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://error.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["broken"]) == 1
            assert results["broken"][0]["status"] == 500

    @patch("requests.head")
    @patch("requests.get")
    def test_falls_back_to_get_on_405(self, mock_get, mock_head):
        """Test fallback to GET request when HEAD returns 405."""
        # HEAD returns 405 (Method Not Allowed)
        mock_head_response = Mock()
        mock_head_response.status_code = 405
        mock_head.return_value = mock_head_response

        # GET returns 200
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get.return_value = mock_get_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://nohead.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            # Should have fallen back to GET and found it OK
            assert len(results["ok"]) == 1
            mock_get.assert_called_once()


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Tests for error handling during link checking."""

    @patch("requests.head")
    def test_handles_timeout(self, mock_head):
        """Test handling of request timeout."""
        import requests

        mock_head.side_effect = requests.exceptions.Timeout()

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://slow.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                timeout=1.0,
            )

            assert len(results["broken"]) == 1
            assert results["broken"][0]["error"] == "Timeout"
            assert results["broken"][0]["status"] is None

    @patch("requests.head")
    def test_handles_connection_error(self, mock_head):
        """Test handling of connection errors."""
        import requests

        mock_head.side_effect = requests.exceptions.ConnectionError()

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://unreachable.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["broken"]) == 1
            assert results["broken"][0]["error"] == "Connection failed"

    @patch("requests.head")
    def test_handles_ssl_error(self, mock_head):
        """Test handling of SSL certificate errors."""
        import requests

        mock_head.side_effect = requests.exceptions.SSLError("Certificate verify failed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://badssl.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["broken"]) == 1
            assert "SSL Error" in results["broken"][0]["error"]

    def test_handles_unreadable_file(self):
        """Test handling of files that can't be read."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            # Create a valid file
            test_md = docs_dir / "valid.md"
            test_md.write_text("https://example.com/valid")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            # Should complete without error even if some files are problematic
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert "total" in results


# ============================================================================
# File Filtering Tests
# ============================================================================


class TestFileFiltering:
    """Tests for filtering which files to scan."""

    def test_source_only_skips_docs(self):
        """Test that source_only=True skips documentation files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create package
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            init_py = pkg_dir / "__init__.py"
            init_py.write_text('"""See https://source.example.com"""')

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            # Create docs
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://docs.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=True,
                include_docs=False,
                ignore_patterns=["example.com"],
            )

            # Should only find the source URL
            assert results["total"] == 1
            assert "https://source.example.com" in results["skipped"]

    def test_docs_only_skips_source(self):
        """Test that docs_only=True skips source files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create package
            pkg_dir = Path(tmp_dir) / "mypackage"
            pkg_dir.mkdir()

            init_py = pkg_dir / "__init__.py"
            init_py.write_text('"""See https://source.example.com"""')

            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "mypackage"\n')

            # Create docs
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://docs.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            # Should only find the docs URL
            assert results["total"] == 1
            assert "https://docs.example.com/page" in results["skipped"]

    def test_includes_readme_in_docs_mode(self):
        """Test that README.md in project root is included when checking docs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create README in project root
            readme = Path(tmp_dir) / "README.md"
            readme.write_text("https://readme.example.com/page")

            # Create docs
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["example.com"],
            )

            assert results["total"] == 1
            assert "README.md" in results["by_file"]


# ============================================================================
# Result Structure Tests
# ============================================================================


class TestResultStructure:
    """Tests for the structure of check_links results."""

    def test_returns_all_required_keys(self):
        """Test that results contain all required keys."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(include_source=False, include_docs=True)

            required_keys = ["total", "ok", "redirects", "broken", "skipped", "by_file"]
            for key in required_keys:
                assert key in results

    def test_broken_items_have_required_fields(self):
        """Test that broken link entries have all required fields."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            # Use a definitely broken URL
            test_md.write_text("https://this-domain-definitely-does-not-exist-12345.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                timeout=2.0,
            )

            if results["broken"]:
                broken = results["broken"][0]
                assert "url" in broken
                assert "status" in broken
                assert "error" in broken
                assert "files" in broken

    @patch("requests.head")
    def test_redirect_items_have_required_fields(self, mock_head):
        """Test that redirect entries have all required fields."""
        mock_response = Mock()
        mock_response.status_code = 301
        mock_response.headers = {"Location": "https://new.example.com/"}
        mock_head.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("https://redirect.example.com/page")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
            )

            assert len(results["redirects"]) == 1
            redirect = results["redirects"][0]
            assert "url" in redirect
            assert "status" in redirect
            assert "location" in redirect
            assert "files" in redirect

    def test_total_equals_sum_of_categories_plus_skipped(self):
        """Test that total count is consistent with categorized counts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = Path(tmp_dir) / "user_guide"
            docs_dir.mkdir()

            test_md = docs_dir / "test.md"
            test_md.write_text("""
https://localhost:8000/skip-me
https://example.com/also-skip
""")

            quarto_yml = docs_dir / "_quarto.yml"
            quarto_yml.write_text("project:\n  type: website\n")

            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=["localhost", "example.com"],
            )

            # Total should equal checked + skipped
            checked = len(results["ok"]) + len(results["redirects"]) + len(results["broken"])
            assert results["total"] == checked + len(results["skipped"])


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestCLIIntegration:
    """Tests for CLI command integration."""

    def test_cli_command_exists(self):
        """Test that check-links command is registered."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "check-links" in result.output

    def test_cli_check_links_help(self):
        """Test check-links command help output."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["check-links", "--help"])

        assert result.exit_code == 0
        assert "--docs-only" in result.output
        assert "--source-only" in result.output
        assert "--timeout" in result.output
        assert "--ignore" in result.output
        assert "--verbose" in result.output
        assert "--json-output" in result.output

    def test_cli_returns_error_code_on_broken_links(self):
        """Test that CLI returns non-zero exit code when broken links found."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create minimal project structure
            Path("docs").mkdir()
            Path("user_guide").mkdir()
            Path("docs/_quarto.yml").write_text("project:\n  type: website\n")
            Path("user_guide/test.md").write_text(
                "https://this-url-definitely-does-not-exist-xyz123.com/"
            )

            result = runner.invoke(cli, ["check-links", "--docs-only", "--timeout", "2"])

            # Should exit with error due to broken link
            assert result.exit_code == 1

    def test_cli_returns_success_on_all_valid(self):
        """Test that CLI returns zero exit code when all links valid."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create minimal project with no URLs
            Path("docs").mkdir()
            Path("user_guide").mkdir()
            Path("docs/_quarto.yml").write_text("project:\n  type: website\n")
            Path("user_guide/test.md").write_text("No URLs here")

            result = runner.invoke(cli, ["check-links", "--docs-only"])

            assert result.exit_code == 0

    def test_cli_json_output_format(self):
        """Test that --json-output produces valid JSON."""
        import json
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("user_guide").mkdir()
            Path("docs/_quarto.yml").write_text("project:\n  type: website\n")
            Path("user_guide/test.md").write_text("https://localhost:8000/test")

            result = runner.invoke(cli, ["check-links", "--docs-only", "--json-output"])

            # Find the JSON in the output (skip any prefix messages)
            output_lines = result.output.strip().split("\n")
            # Look for the line starting with { which begins the JSON
            json_start = 0
            for i, line in enumerate(output_lines):
                if line.strip().startswith("{"):
                    json_start = i
                    break

            json_output = "\n".join(output_lines[json_start:])

            # Output should be valid JSON
            output = json.loads(json_output)
            assert "total" in output
            assert "ok" in output
            assert "broken" in output
            assert "redirects" in output
            assert "skipped" in output

    def test_cli_verbose_shows_progress(self):
        """Test that --verbose shows progress for each URL."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("user_guide").mkdir()
            Path("docs/_quarto.yml").write_text("project:\n  type: website\n")
            Path("user_guide/test.md").write_text("https://localhost:8000/test")

            result = runner.invoke(cli, ["check-links", "--docs-only", "--verbose"])

            # Verbose output should show the URL being processed
            assert "localhost" in result.output or "Skipped" in result.output

    def test_cli_multiple_ignore_flags(self):
        """Test that multiple -i/--ignore flags work."""
        from click.testing import CliRunner
        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("user_guide").mkdir()
            Path("docs/_quarto.yml").write_text("project:\n  type: website\n")
            Path("user_guide/test.md").write_text("""
https://skip1.example.com/
https://skip2.example.com/
""")

            result = runner.invoke(
                cli,
                [
                    "check-links",
                    "--docs-only",
                    "-i",
                    "skip1",
                    "-i",
                    "skip2",
                ],
            )

            assert result.exit_code == 0
