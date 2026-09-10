"""Tests for post-render transformation functions."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the post-render script as a module (it's a standalone script, not a package)
_SCRIPT = Path(__file__).resolve().parent.parent / "great_docs" / "assets" / "post-render.py"


def _load_post_render():
    """Import post-render.py as a module so its functions can be tested."""
    spec = importlib.util.spec_from_file_location("post_render", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    # The script runs top-level code (glob, file I/O) that will fail when not
    # inside a build directory.  We only need the function definitions, so we
    # monkey-patch a few things and catch errors at import time.
    return spec, mod


def _get_functions():
    """Post-render helpers available to focused unit tests"""
    import html as _html
    import os as _os
    import re as _re  # noqa: F811

    source = _SCRIPT.read_text()

    # Stub _t so translated labels fall back to English
    def _t(key: str, fallback: str | None = None) -> str:
        return fallback if fallback is not None else key

    # Build a minimal namespace with the imports the functions need
    ns = {
        "html": _html,
        "os": _os,
        "re": _re,
        "__builtins__": __builtins__,
        "_t": _t,
    }

    # Extract function definitions by finding their source blocks
    funcs_to_extract = [
        "_postprocess_markdown_content",
    ]

    for func_name in funcs_to_extract:
        # Find the function in the source
        start = source.find(f"def {func_name}(")
        if start == -1:
            raise RuntimeError(f"Could not find {func_name} in {_SCRIPT}")

        # Find the end of the function (next def at same indent level or EOF)
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            # Stop at next top-level def or class
            if (
                line
                and not line[0].isspace()
                and (line.startswith("def ") or line.startswith("class "))
            ):
                break
            func_lines.append(line)

        func_source = "\n".join(func_lines)
        exec(func_source, ns)

    return (ns["_postprocess_markdown_content"],)


(postprocess_markdown_content,) = _get_functions()


class TestPostprocessMarkdownContent:
    """Tests for markdown cleanup used by generated .md reference pages."""

    def test_removes_source_anchor_and_converts_links(self):
        md = (
            "Usage\n\n"
            '<a href="https://example.com/src.py#L1" target="_blank" rel="noopener">Source</a>\n\n'
            "The workflow is: "
            '<a href="GreatDocs.install.html#great_docs.GreatDocs.install" class="gdls-link gdls-code">install()</a>'
            " then "
            '<a href="GreatDocs.build.html#great_docs.GreatDocs.build" class="gdls-link gdls-code">build()</a>.\n'
        )

        out = postprocess_markdown_content(md, "reference/GreatDocs.md")

        assert "Source</a>" not in out
        assert "[install()](GreatDocs.install.md#great_docs.GreatDocs.install)" in out
        assert "[build()](GreatDocs.build.md#great_docs.GreatDocs.build)" in out
        assert "<a href=" not in out

    def test_simplifies_parameter_signature_artifact(self):
        md = "`project_path``:`` ``str | None`` ``=`` ``None`  \n"

        out = postprocess_markdown_content(md, "reference/GreatDocs.md")

        assert "`project_path`: `str | None` = `None`" in out
        assert "``:``" not in out

    def test_decodes_html_entities_in_markdown(self):
        """HTML entities from pandoc output should be properly decoded."""
        # Common curly quote entities that can end up in markdown
        md = (
            "# What You&rsquo;ll Learn\n\n"
            "Let&rsquo;s get started!\n\n"
            "He said &ldquo;Hello&rdquo; with a smile.\n"
        )

        out = postprocess_markdown_content(md, "user-guide/intro.md")

        # Should decode and normalize to plain ASCII punctuation
        assert "# What You'll Learn" in out
        assert "Let's get started!" in out
        assert 'He said "Hello" with a smile.' in out
        # Should not contain the original HTML entities
        assert "&rsquo;" not in out
        assert "&ldquo;" not in out
        assert "&rdquo;" not in out

    def test_fixes_mojibake_characters(self):
        """UTF-8 mojibake like the three-char sequence should be fixed."""
        # Mojibake: UTF-8 bytes interpreted as Latin-1
        # U+2019 (') is E2 80 99 in UTF-8, but as Latin-1 chars becomes: U+00E2 U+20AC U+2122
        mojibake_apostrophe = "\u00e2\u20ac\u2122"  # This is what â€™ looks like in Python

        md = f"Great Docs automatically discovers and documents your package{mojibake_apostrophe}s public API."

        out = postprocess_markdown_content(md, "user-guide/intro.md")

        # Should have converted mojibake and normalized punctuation to ASCII apostrophe
        assert "package's public API" in out
        # Should not have the mojibake character
        assert mojibake_apostrophe not in out

    def test_normalizes_user_guide_typography_to_ascii(self):
        """Smart punctuation in prose should be normalized for robust raw markdown display."""
        md = (
            "# What You’ll Learn\n\n"
            "1.  **Installation** – Getting Great Docs set up\n"
            "2.  **Quick Start** – Creating your first documentation site\n\n"
            "Let’s get started!\n"
        )

        out = postprocess_markdown_content(md, "user-guide/introduction.md")

        assert "# What You'll Learn" in out
        assert "**Installation** - Getting Great Docs set up" in out
        assert "**Quick Start** - Creating your first documentation site" in out
        assert "Let's get started!" in out
        assert "’" not in out
        assert "–" not in out


class TestFixScriptPathsBackToTop:
    """Verify fix_script_paths handles back-to-top.js in subdirectories."""

    def test_back_to_top_listed_in_fix_script_paths(self):
        """back-to-top.js should appear in the fix_script_paths function body."""
        source = _SCRIPT.read_text()
        # Find the fix_script_paths function
        assert "def fix_script_paths():" in source
        # Find the start of the function
        start = source.find("def fix_script_paths():")
        # Find the next top-level definition after it
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            func_lines.append(line)
        func_body = "\n".join(func_lines)
        assert "back-to-top.js" in func_body

    def test_back_to_top_path_fix_pattern(self):
        """The fix uses the same old/new replacement pattern as other scripts."""
        source = _SCRIPT.read_text()
        # Verify the exact pattern strings exist
        assert "'<script src=\"back-to-top.js\"></script>'" in source
        assert "back-to-top.js" in source


class TestFixScriptPathsKeyboardNav:
    """Verify fix_script_paths handles keyboard-nav.js in subdirectories."""

    def test_keyboard_nav_listed_in_fix_script_paths(self):
        """keyboard-nav.js should appear in the fix_script_paths function body."""
        source = _SCRIPT.read_text()
        assert "def fix_script_paths():" in source
        start = source.find("def fix_script_paths():")
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            func_lines.append(line)
        func_body = "\n".join(func_lines)
        assert "keyboard-nav.js" in func_body

    def test_keyboard_nav_path_fix_pattern(self):
        """The fix uses the same old/new replacement pattern as other scripts."""
        source = _SCRIPT.read_text()
        assert "'<script src=\"keyboard-nav.js\"></script>'" in source
        assert "keyboard-nav.js" in source
