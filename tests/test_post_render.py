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
    """Extract translate_sphinx_roles and translate_rst_directives via exec."""
    import html as _html
    import os as _os
    import re as _re  # noqa: F811

    source = _SCRIPT.read_text()

    from pygments import highlight as _highlight
    from pygments.formatters import HtmlFormatter as _HtmlFormatter
    from pygments.lexers import PythonLexer as _PythonLexer

    # Stub _t so translated labels fall back to English
    def _t(key: str, fallback: str | None = None) -> str:
        return fallback if fallback is not None else key

    # Build a minimal namespace with the imports the functions need
    ns = {
        "html": _html,
        "os": _os,
        "re": _re,
        "__builtins__": __builtins__,
        "highlight": _highlight,
        "HtmlFormatter": _HtmlFormatter,
        "PythonLexer": _PythonLexer,
        "_t": _t,
    }

    # Extract PYGMENTS_TO_QUARTO_CLASS dict (needed by fix_plain_doctest_code_blocks)
    cm_start = source.find("PYGMENTS_TO_QUARTO_CLASS = {")
    if cm_start != -1:
        cm_rest = source[cm_start:]
        cm_end = cm_rest.find("}\n") + 2
        exec(cm_rest[:cm_end], ns)

    # Extract function definitions by finding their source blocks
    funcs_to_extract = [
        "translate_sphinx_roles",
        "translate_rst_directives",
        "translate_rst_math",
        "fix_plain_doctest_code_blocks",
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

    return (
        ns["translate_sphinx_roles"],
        ns["translate_rst_directives"],
        ns["translate_rst_math"],
        ns["fix_plain_doctest_code_blocks"],
        ns["_postprocess_markdown_content"],
    )


(
    translate_sphinx_roles,
    translate_rst_directives,
    translate_rst_math,
    fix_plain_doctest_code_blocks,
    postprocess_markdown_content,
) = _get_functions()


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


def _get_seealso_functions():
    """Extract See Also and interlinks functions from post-render.py."""
    import re as _re

    source = _SCRIPT.read_text()

    # Stub _t so translated labels fall back to English
    def _t(key: str, fallback: str | None = None) -> str:
        return fallback if fallback is not None else key

    ns = {
        "re": _re,
        "__builtins__": __builtins__,
        # Provide empty inventory for resolve_interlinks
        "_interlinks_inventory": {},
        "_t": _t,
    }

    funcs_to_extract = [
        "extract_seealso_from_html",
        "extract_seealso_from_doc_section",
        "generate_seealso_html",
        "_resolve_interlink_name",
        "resolve_interlinks",
        "autolink_code_references",
    ]

    for func_name in funcs_to_extract:
        start = source.find(f"def {func_name}(")
        if start == -1:
            raise RuntimeError(f"Could not find {func_name} in {_SCRIPT}")

        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if (
                line
                and not line[0].isspace()
                and (line.startswith("def ") or line.startswith("class "))
            ):
                break
            func_lines.append(line)

        func_source = "\n".join(func_lines)
        exec(func_source, ns)

    return (
        ns["extract_seealso_from_html"],
        ns["extract_seealso_from_doc_section"],
        ns["generate_seealso_html"],
        ns["_resolve_interlink_name"],
        ns["resolve_interlinks"],
        ns["autolink_code_references"],
    )


(
    extract_seealso_from_html,
    extract_seealso_from_doc_section,
    generate_seealso_html,
    _resolve_interlink_name,
    resolve_interlinks,
    autolink_code_references,
) = _get_seealso_functions()


class TestTranslateSphinxRoles:
    """Tests for Sphinx cross-reference role translation."""

    def test_py_exc_with_code_tag(self):
        html = "<p>Raises :py:exc:<code>ValueError</code> on failure.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Raises <code>ValueError</code> on failure.</p>"

    def test_py_class_with_code_tag(self):
        html = "<p>Returns a :py:class:<code>datetime.datetime</code> object.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Returns a <code>datetime.datetime</code> object.</p>"

    def test_py_func_adds_parens(self):
        html = "<p>See :py:func:<code>datetime.tzinfo.fromutc</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>See <code>datetime.tzinfo.fromutc()</code>.</p>"

    def test_py_meth_adds_parens(self):
        html = "<p>Uses :py:meth:<code>parser.parse</code> internally.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Uses <code>parser.parse()</code> internally.</p>"

    def test_bare_class_role(self):
        html = "<p>Returns a :class:<code>tzinfo</code> subclass.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Returns a <code>tzinfo</code> subclass.</p>"

    def test_bare_func_role_adds_parens(self):
        html = "<p>See :func:<code>get_object</code> for details.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>See <code>get_object()</code> for details.</p>"

    def test_const_role(self):
        html = "<p>:py:const:<code>DEFAULTPARSER</code> is used.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p><code>DEFAULTPARSER</code> is used.</p>"

    def test_attr_role(self):
        html = "<p>The :attr:<code>name</code> attribute.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>The <code>name</code> attribute.</p>"

    def test_mod_role(self):
        html = "<p>Provided by :py:mod:<code>dateutil.tz</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Provided by <code>dateutil.tz</code>.</p>"

    def test_backtick_role_in_pre(self):
        html = "<pre><code>Use :func:`get_zonefile_instance` to retrieve</code></pre>"
        result = translate_sphinx_roles(html)
        assert "<code>get_zonefile_instance()</code>" in result

    def test_backtick_class_no_parens(self):
        html = "<pre><code>:class:`MyClass`</code></pre>"
        result = translate_sphinx_roles(html)
        assert "<code>MyClass</code>" in result
        assert "MyClass()" not in result

    def test_multiple_roles_in_one_line(self):
        html = (
            "<p>Takes a :py:class:<code>datetime</code> and returns "
            "a :py:class:<code>timedelta</code>.</p>"
        )
        result = translate_sphinx_roles(html)
        assert ":py:class:" not in result
        assert "<code>datetime</code>" in result
        assert "<code>timedelta</code>" in result

    def test_no_double_parens(self):
        """If the name already has (), don't add more."""
        html = "<p>See :func:<code>foo()</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>See <code>foo()</code>.</p>"

    def test_no_change_for_non_role_text(self):
        html = "<p>This is regular text with <code>code</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == html

    def test_obj_role(self):
        html = "<p>See :py:obj:<code>some_thing</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>See <code>some_thing</code>.</p>"

    def test_data_role(self):
        html = "<p>See :py:data:<code>MY_CONST</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>See <code>MY_CONST</code>.</p>"

    def test_type_role(self):
        html = "<p>Is :py:type:<code>int</code>.</p>"
        result = translate_sphinx_roles(html)
        assert result == "<p>Is <code>int</code>.</p>"


class TestTranslateRstDirectives:
    """Tests for RST directive translation."""

    def test_versionadded_simple(self):
        html = "<p>.. versionadded:: 2.8.1</p>"
        result = translate_rst_directives(html)
        assert "Added in version 2.8.1" in result
        assert "<p>.." not in result
        assert "059669" in result  # green border color

    def test_versionchanged_with_description(self):
        html = "<p>.. versionchanged:: 2.7.0 Now returns a singleton.</p>"
        result = translate_rst_directives(html)
        assert "Changed in version 2.7.0" in result
        assert "Now returns a singleton." in result
        assert "3B82F6" in result  # blue border color

    def test_deprecated_with_description(self):
        html = "<p>.. deprecated:: 2.6 Use X instead.</p>"
        result = translate_rst_directives(html)
        assert "Deprecated since version 2.6" in result
        assert "Use X instead." in result
        assert "DC2626" in result  # red border color

    def test_note_directive(self):
        html = "<p>.. note:: Something important to know.</p>"
        result = translate_rst_directives(html)
        assert "Note" in result
        assert "Something important to know." in result

    def test_warning_directive(self):
        html = "<p>.. warning:: Be careful with this.</p>"
        result = translate_rst_directives(html)
        assert "Warning" in result
        assert "Be careful with this." in result
        assert "D97706" in result  # amber border color

    def test_caution_directive(self):
        html = "<p>.. caution:: Handle with care.</p>"
        result = translate_rst_directives(html)
        assert "Caution" in result
        assert "Handle with care." in result

    def test_tip_directive(self):
        html = "<p>.. tip:: Use this shortcut.</p>"
        result = translate_rst_directives(html)
        assert "Tip" in result
        assert "Use this shortcut." in result

    def test_hint_directive(self):
        html = "<p>.. hint:: Try this approach.</p>"
        result = translate_rst_directives(html)
        assert "Hint" in result
        assert "Try this approach." in result

    def test_danger_directive(self):
        html = "<p>.. danger:: This will delete data.</p>"
        result = translate_rst_directives(html)
        assert "Danger" in result
        assert "This will delete data." in result

    def test_important_directive(self):
        html = "<p>.. important:: Read this first.</p>"
        result = translate_rst_directives(html)
        assert "Important" in result
        assert "Read this first." in result

    def test_versionadded_no_description(self):
        html = "<p>.. versionadded:: 2.8.1</p>"
        result = translate_rst_directives(html)
        assert "Added in version 2.8.1" in result
        # Should not have an empty content paragraph
        assert '<p style="margin: 0;"></p>' not in result

    def test_deprecated_no_description(self):
        html = "<p>.. deprecated:: 3.0</p>"
        result = translate_rst_directives(html)
        assert "Deprecated since version 3.0" in result

    def test_no_change_for_non_directive(self):
        html = "<p>This is a regular paragraph.</p>"
        result = translate_rst_directives(html)
        assert result == html

    def test_directive_in_pre_not_matched(self):
        """Directives inside <pre> blocks should NOT be translated
        (they are code examples)."""
        html = "<pre><code>.. note:: This is in a code block</code></pre>"
        result = translate_rst_directives(html)
        # The regex only matches <p>.. directive::</p>, not <pre><code>
        assert result == html

    def test_multiple_directives(self):
        html = (
            "<p>Some text.</p>\n"
            "<p>.. versionadded:: 1.0</p>\n"
            "<p>.. deprecated:: 2.0 Use new_func instead.</p>\n"
            "<p>More text.</p>"
        )
        result = translate_rst_directives(html)
        assert "Added in version 1.0" in result
        assert "Deprecated since version 2.0" in result
        assert "Use new_func instead." in result
        assert "<p>Some text.</p>" in result
        assert "<p>More text.</p>" in result

    def test_output_is_styled_div(self):
        html = "<p>.. warning:: Watch out!</p>"
        result = translate_rst_directives(html)
        assert result.startswith("<div style=")
        assert "border-left: 4px solid" in result
        assert "border-radius: 4px" in result
        assert "</div>" in result

    def test_deprecated_with_code_tags_in_body(self):
        """Directive body can contain <code> tags (from Sphinx role translation)."""
        html = (
            "<p>.. deprecated:: 2.6 Use <code>ZoneInfoFile</code> "
            "and call <code>ZoneInfoFile.get(name)()</code> instead.</p>"
        )
        result = translate_rst_directives(html)
        assert "Deprecated since version 2.6" in result
        assert "<code>ZoneInfoFile</code>" in result
        assert "<code>ZoneInfoFile.get(name)()</code>" in result
        assert "DC2626" in result  # red border color

    def test_note_with_code_tags_in_body(self):
        """Note directive body with inline code should also be translated."""
        html = "<p>.. note:: Use <code>foo()</code> instead of <code>bar()</code>.</p>"
        result = translate_rst_directives(html)
        assert "Note" in result
        assert "<code>foo()</code>" in result
        assert "<code>bar()</code>" in result


class TestTranslateRstMath:
    """Tests for translate_rst_math (post-render HTML math conversion)."""

    def test_double_colon_pre_code(self):
        """Original pattern: <p>.. math::</p><pre><code>...</code></pre>."""
        html = (
            "<html><head></head><body>"
            "<p>.. math::</p>"
            "<pre><code>E = mc^2</code></pre>"
            "</body></html>"
        )
        result = translate_rst_math(html)
        assert 'class="math display"' in result
        assert "E = mc^2" in result
        assert ".. math::" not in result
        # KaTeX CDN should be injected
        assert "katex" in result

    def test_single_colon_sourcecode_div(self):
        """Pandoc-mangled pattern: <p>.. math:</p> + sourceCode div."""
        html = (
            "<html><head></head><body>"
            "<p>.. math:</p>"
            '<div class="sourceCode"><pre class="sourceCode python">'
            '<code class="sourceCode python">'
            "<span>\\|x\\|</span>"
            "</code></pre></div>"
            "</body></html>"
        )
        result = translate_rst_math(html)
        assert 'class="math display"' in result
        assert ".. math:" not in result

    def test_single_colon_plain_pre(self):
        """Pandoc-mangled pattern: <p>.. math:</p> + plain <pre><code>."""
        html = (
            "<html><head></head><body>"
            "<p>.. math:</p>"
            "<pre><code>a^2 + b^2 = c^2</code></pre>"
            "</body></html>"
        )
        result = translate_rst_math(html)
        assert 'class="math display"' in result
        assert "a^2 + b^2 = c^2" in result

    def test_no_math_no_katex(self):
        """KaTeX CDN is NOT injected when no math blocks are found."""
        html = "<html><head></head><body><p>Hello</p></body></html>"
        result = translate_rst_math(html)
        assert "katex" not in result
        assert result == html

    def test_multiple_math_blocks(self):
        """Multiple math blocks are all converted."""
        html = (
            "<html><head></head><body>"
            "<p>.. math::</p><pre><code>a = b</code></pre>"
            "<p>.. math::</p><pre><code>c = d</code></pre>"
            "</body></html>"
        )
        result = translate_rst_math(html)
        assert result.count('class="math display"') == 2

    def test_span_tags_stripped_from_sourcecode(self):
        """Syntax-highlighting <span> tags inside code are removed for math."""
        html = (
            "<html><head></head><body>"
            "<p>.. math:</p>"
            '<div class="sourceCode"><pre class="sourceCode python">'
            '<code class="sourceCode python">'
            '<span class="op">\\</span>frac{1}{2}'
            "</code></pre></div>"
            "</body></html>"
        )
        result = translate_rst_math(html)
        assert 'class="math display"' in result
        # span tags should be stripped, leaving just the LaTeX
        assert "<span" not in result.split('class="math display"')[1].split("</p>")[0]


class TestFixPlainDoctestCodeBlocks:
    """Tests for fix_plain_doctest_code_blocks (site 137 regression)."""

    def test_single_plain_doctest_converted(self):
        """A plain <pre><code> block with >>> gets proper sourceCode styling."""
        html = "<pre><code>&gt;&gt;&gt; foo(\"hello\")\n'world'</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert 'class="sourceCode python' in result
        assert 'class="code-copy-outer-scaffold"' in result
        assert "<pre><code>" not in result

    def test_consecutive_plain_doctests_all_converted(self):
        """Multiple consecutive plain doctest blocks are all converted."""
        html = (
            # First block (already styled by Quarto — should be left alone)
            '<div class="sourceCode" id="cb1">'
            '<pre class="sourceCode python code-with-copy">'
            '<code class="sourceCode python">'
            '<span class="op">&gt;&gt;&gt;</span> schedule("cleanup")\n'
            '<span class="va">True</span></code></pre></div>\n'
            # Second block (plain — should be converted)
            '<pre><code>&gt;&gt;&gt; schedule("backup", delay=60.0)\n'
            "True</code></pre>\n"
            # Third block (plain — should be converted)
            '<pre><code>&gt;&gt;&gt; schedule("cleanup")\n'
            "False</code></pre>"
        )
        result = fix_plain_doctest_code_blocks(html)
        # The already-styled block should remain
        assert result.count('class="sourceCode python') >= 3
        # No plain <pre><code> blocks should remain
        assert "<pre><code>" not in result

    def test_plain_code_block_without_doctest_unchanged(self):
        """A plain <pre><code> without >>> is left as-is."""
        html = "<pre><code>just some plain text</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert result == html

    def test_unique_cb_ids_no_collision(self):
        """Generated cb IDs don't collide with existing ones."""
        html = (
            '<div class="sourceCode" id="cb3">'
            '<pre class="sourceCode python"><code class="sourceCode python">'
            "existing</code></pre></div>\n"
            "<pre><code>&gt;&gt;&gt; first()\n1</code></pre>\n"
            "<pre><code>&gt;&gt;&gt; second()\n2</code></pre>"
        )
        result = fix_plain_doctest_code_blocks(html)
        # Existing cb3 plus two new blocks should give cb4 and cb5
        assert 'id="cb4"' in result
        assert 'id="cb5"' in result

    def test_html_entities_decoded_for_highlighting(self):
        """HTML entities in the plain block are decoded before Pygments."""
        html = "<pre><code>&gt;&gt;&gt; x &lt; 10 &amp; y &gt; 5\nTrue</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        # Should be in a sourceCode block, not plain
        assert 'class="sourceCode python' in result
        # The original plain block should be gone
        assert "<pre><code>" not in result


class TestExtractSeeAlsoFromHtml:
    """Tests for extracting %seealso items from rendered HTML."""

    def test_basic_seealso(self):
        html = "<p>%seealso func_a, func_b</p>"
        result = extract_seealso_from_html(html)
        assert result == [("func_a", ""), ("func_b", "")]

    def test_seealso_with_descriptions(self):
        html = "<p>%seealso DuckDBStore : Local storage, ChromaDBStore : ChromaDB</p>"
        result = extract_seealso_from_html(html)
        assert result == [
            ("DuckDBStore", "Local storage"),
            ("ChromaDBStore", "ChromaDB"),
        ]

    def test_mixed_descriptions(self):
        html = "<p>%seealso func_a : Does stuff, func_b</p>"
        result = extract_seealso_from_html(html)
        assert result == [("func_a", "Does stuff"), ("func_b", "")]

    def test_no_seealso(self):
        html = "<p>Just a normal paragraph.</p>"
        result = extract_seealso_from_html(html)
        assert result == []


class TestExtractSeeAlsoFromDocSection:
    """Tests for extracting See Also from rendered doc-section blocks."""

    def test_classic_with_descriptions(self):
        html = (
            '<section id="see-also" class="level1 doc-section">'
            "<h1>See Also</h1>"
            "<p>transform : Transform data before analysis.</p>"
            "</section>"
        )
        result = extract_seealso_from_doc_section(html)
        assert result == [("transform", "Transform data before analysis.")]

    def test_classic_without_descriptions(self):
        html = (
            '<section id="see-also" class="level1 doc-section">'
            "<h1>See Also</h1>"
            "<p>func_a, func_b</p>"
            "</section>"
        )
        result = extract_seealso_from_doc_section(html)
        assert result == [("func_a", ""), ("func_b", "")]

    def test_interlink_names(self):
        html = (
            '<section id="see-also" class="level1 doc-section">'
            "<h1>See Also</h1>"
            '<dt><a href="`~MyClass`">MyClass</a></dt><dd>A class.</dd>'
            "</section>"
        )
        result = extract_seealso_from_doc_section(html)
        assert result == [("MyClass", "A class.")]

    def test_interlink_without_dd(self):
        html = (
            '<section id="see-also" class="level1 doc-section">'
            "<h1>See Also</h1>"
            '<a href="`~MyClass`">MyClass</a>'
            "</section>"
        )
        result = extract_seealso_from_doc_section(html)
        assert result == [("MyClass", "")]

    def test_no_section(self):
        html = "<p>No see also here.</p>"
        result = extract_seealso_from_doc_section(html)
        assert result == []


class TestGenerateSeeAlsoHtml:
    """Tests for generating the See Also HTML block."""

    def test_empty_items(self):
        result = generate_seealso_html([])
        assert result == ""

    def test_names_only(self):
        result = generate_seealso_html([("func_a", ""), ("func_b", "")])
        assert "func_a" in result
        assert "func_b" in result
        assert "See Also" in result
        # No descriptions → comma-separated links
        assert "<ul" not in result

    def test_with_descriptions(self):
        result = generate_seealso_html(
            [
                ("DuckDBStore", "Local storage"),
                ("ChromaDBStore", "ChromaDB storage"),
            ]
        )
        assert "DuckDBStore" in result
        assert "Local storage" in result
        assert "ChromaDBStore" in result
        assert "ChromaDB storage" in result
        # Descriptions present → list layout
        assert "<ul" in result

    def test_mixed_descriptions(self):
        result = generate_seealso_html(
            [
                ("func_a", "Does stuff"),
                ("func_b", ""),
            ]
        )
        assert "func_a" in result
        assert "Does stuff" in result
        assert "func_b" in result
        assert "<ul" in result


def _make_autolink(inventory):
    """Create an autolink function bound to a given inventory."""
    import re as _re

    source = _SCRIPT.read_text()
    ns = {
        "re": _re,
        "__builtins__": __builtins__,
        "_interlinks_inventory": inventory,
    }
    for func_name in ("_resolve_interlink_name", "autolink_code_references"):
        start = source.find(f"def {func_name}(")
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if (
                line
                and not line[0].isspace()
                and (line.startswith("def ") or line.startswith("class "))
            ):
                break
            func_lines.append(line)
        exec("\n".join(func_lines), ns)
    return ns["autolink_code_references"]


class TestAutolinkCodeReferences:
    """Tests for autolink_code_references."""

    INVENTORY = {
        "mypackage.MyClass": {"uri": "reference/MyClass.html#mypackage.MyClass", "dispname": "-"},
        "mypackage.my_func": {"uri": "reference/my_func.html#mypackage.my_func", "dispname": "-"},
        "mypackage.utils.helper": {
            "uri": "reference/helper.html#mypackage.utils.helper",
            "dispname": "-",
        },
    }

    def _autolink(self, html):
        fn = _make_autolink(self.INVENTORY)
        return fn(html)

    def test_simple_name_match(self):
        result = self._autolink("<p><code>MyClass</code></p>")
        assert (
            '<a href="MyClass.html#mypackage.MyClass" class="gdls-link gdls-code">MyClass</a>'
            in result
        )

    def test_qualified_name_match(self):
        result = self._autolink("<p><code>mypackage.MyClass</code></p>")
        assert (
            '<a href="MyClass.html#mypackage.MyClass" class="gdls-link gdls-code">mypackage.MyClass</a>'
            in result
        )

    def test_name_with_parens(self):
        result = self._autolink("<p><code>my_func()</code></p>")
        assert (
            '<a href="my_func.html#mypackage.my_func" class="gdls-link gdls-code">my_func()</a>'
            in result
        )

    def test_tilde_shortening(self):
        result = self._autolink("<p><code>~~mypackage.MyClass</code></p>")
        assert (
            '<a href="MyClass.html#mypackage.MyClass" class="gdls-link gdls-code">MyClass</a>'
            in result
        )

    def test_tilde_shortening_with_parens(self):
        result = self._autolink("<p><code>~~mypackage.my_func()</code></p>")
        assert (
            '<a href="my_func.html#mypackage.my_func" class="gdls-link gdls-code">my_func()</a>'
            in result
        )

    def test_tilde_dot_shortening(self):
        result = self._autolink("<p><code>~~.mypackage.MyClass</code></p>")
        assert (
            '<a href="MyClass.html#mypackage.MyClass" class="gdls-link gdls-code">.MyClass</a>'
            in result
        )

    def test_tilde_dot_shortening_with_parens(self):
        result = self._autolink("<p><code>~~.mypackage.my_func()</code></p>")
        assert (
            '<a href="my_func.html#mypackage.my_func" class="gdls-link gdls-code">.my_func()</a>'
            in result
        )

    def test_no_match_left_alone(self):
        result = self._autolink("<p><code>unknown_thing</code></p>")
        assert result == "<p><code>unknown_thing</code></p>"

    def test_code_with_args_not_linked(self):
        result = self._autolink("<p><code>my_func(x=1)</code></p>")
        assert "<a" not in result

    def test_code_with_spaces_not_linked(self):
        result = self._autolink("<p><code>a + b</code></p>")
        assert "<a" not in result

    def test_code_with_operator_not_linked(self):
        result = self._autolink("<p><code>-MyClass</code></p>")
        assert "<a" not in result

    def test_gd_no_link_class_skipped(self):
        result = self._autolink('<p><code class="gd-no-link">MyClass</code></p>')
        assert "<a" not in result

    def test_code_in_pre_not_linked(self):
        result = self._autolink("<pre><code>MyClass</code></pre>")
        assert "<a" not in result

    def test_already_inside_link_not_doubled(self):
        result = self._autolink('<a href="foo.html"><code>MyClass</code></a>')
        # Should not wrap in another <a>
        assert result.count("<a ") == 1

    def test_unresolved_tilde_strips_prefix(self):
        result = self._autolink("<p><code>~~unknown.module.Thing</code></p>")
        assert "<a" not in result
        assert "<code>Thing</code>" in result

    def test_unresolved_tilde_dot_strips_prefix(self):
        result = self._autolink("<p><code>~~.unknown.module.Thing()</code></p>")
        assert "<a" not in result
        assert "<code>.Thing()</code>" in result

    def test_empty_inventory(self):
        fn = _make_autolink({})
        html = "<p><code>MyClass</code></p>"
        assert fn(html) == html


class TestFixPlainDoctestGdCodeNav:
    """Tests that fix_plain_doctest_code_blocks emits the gd-code-nav copy button."""

    def test_converted_block_has_gd_code_nav(self):
        """Converted doctest block should contain a gd-code-nav element."""
        html = "<pre><code>&gt;&gt;&gt; foo()\n42</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert 'class="gd-code-nav"' in result

    def test_converted_block_has_gd_code_copy_button(self):
        """Converted block should have a gd-code-copy button inside the nav."""
        html = "<pre><code>&gt;&gt;&gt; bar(1, 2)\n3</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert 'class="gd-code-copy"' in result
        assert 'title="Copy to clipboard"' in result

    def test_no_legacy_code_copy_button(self):
        """Converted block should NOT have the old code-copy-button class."""
        html = "<pre><code>&gt;&gt;&gt; baz()\nNone</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert "code-copy-button" not in result
        assert '<i class="bi">' not in result

    def test_nav_is_inside_scaffold(self):
        """gd-code-nav should be nested inside code-copy-outer-scaffold."""
        html = "<pre><code>&gt;&gt;&gt; x = 1\n</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        scaffold_start = result.find('class="code-copy-outer-scaffold"')
        nav_start = result.find('class="gd-code-nav"')
        assert scaffold_start < nav_start

    def test_no_code_with_copy_class_on_pre(self):
        """Converted <pre> should NOT have the Quarto 'code-with-copy' class."""
        html = "<pre><code>&gt;&gt;&gt; hello()\n'world'</code></pre>"
        result = fix_plain_doctest_code_blocks(html)
        assert "code-with-copy" not in result


# ---------------------------------------------------------------------------
# fix_script_paths — back-to-top.js path resolution
# ---------------------------------------------------------------------------


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
