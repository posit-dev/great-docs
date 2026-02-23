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


# ---------------------------------------------------------------------------
# Instead of importing the whole script (which has top-level side effects),
# extract just the functions we need by exec-ing the function defs.
# ---------------------------------------------------------------------------


def _get_functions():
    """Extract translate_sphinx_roles and translate_rst_directives via exec."""
    import re as _re  # noqa: F811

    source = _SCRIPT.read_text()

    # Build a minimal namespace with the imports the functions need
    ns = {"re": _re, "__builtins__": __builtins__}

    # Extract function definitions by finding their source blocks
    funcs_to_extract = ["translate_sphinx_roles", "translate_rst_directives"]

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

    return ns["translate_sphinx_roles"], ns["translate_rst_directives"]


translate_sphinx_roles, translate_rst_directives = _get_functions()


# ── translate_sphinx_roles ──────────────────────────────────────────────────


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


# ── translate_rst_directives ────────────────────────────────────────────────


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
