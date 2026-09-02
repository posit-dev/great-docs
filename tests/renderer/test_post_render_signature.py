"""
Tests for the `sig-name`/`sig-class` markup `highlight_signature_with_pygments`
adds to the rendered `cb1` signature block, both for an ordinary callable
(name followed by its call brackets) and for a `TypedDict`/`Enum` page (a bare
name with no brackets at all).
"""

from __future__ import annotations

import re
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "great_docs" / "assets" / "post-render.py"


def _load_highlight_signature_with_pygments():
    """
    Extract `highlight_signature_with_pygments` from `post-render.py`

    The script is a standalone build step, not an importable package, and
    runs file-system side effects at module level, so the function (and
    the class-name map it relies on) is sliced out of the real source by
    name instead of duplicated here, the same way `tests/test_post_render.py`
    already does for `_postprocess_markdown_content`.

    Returns
    -------
    The live function, bound to the class map from the current source.
    """
    source = _SCRIPT.read_text()

    dict_start = source.index("PYGMENTS_TO_QUARTO_CLASS = {")
    dict_end = source.index("\n}\n", dict_start) + len("\n}\n")

    func_start = source.index("def highlight_signature_with_pygments(")
    func_end = source.index("\ndef strip_colgroup_tags(", func_start)

    ns = {
        "re": re,
        "highlight": highlight,
        "HtmlFormatter": HtmlFormatter,
        "PythonLexer": PythonLexer,
    }
    exec(source[dict_start:dict_end], ns)
    exec(source[func_start:func_end], ns)
    return ns["highlight_signature_with_pygments"]


highlight_signature_with_pygments = _load_highlight_signature_with_pygments()


def _cb1(code: str) -> str:
    """Wrap `code` in the `cb1` sourceCode div the function looks for"""
    return (
        '<div class="sourceCode" id="cb1">\n'
        '<pre class="sourceCode python"><code class="sourceCode python">'
        f"{code}"
        "</code></pre>\n</div>"
    )


def _line_with(html_content: str, needle: str) -> str:
    """Return the single line of `html_content` that contains `needle`"""
    (line,) = (line for line in html_content.splitlines() if needle in line)
    return line


class TestBareNameMarking:
    """A `TypedDict`/`Enum` page's signature is a bare name, no brackets"""

    def test_bare_name_is_marked_sig_name(self):
        result = highlight_signature_with_pygments(_cb1("UserProfile"))
        line = _line_with(result, "UserProfile")

        assert '<span class="sig-name">UserProfile</span>' in line
        assert "(" not in line


class TestCallableNameMarking:
    """An ordinary function or class keeps its name-then-brackets markup"""

    def test_function_name_is_marked_and_keeps_its_bracket(self):
        result = highlight_signature_with_pygments(_cb1("connect(host, port=8080)"))
        line = _line_with(result, "connect")

        assert '<span class="sig-name">connect</span>(' in line

    def test_dotted_method_name_is_marked_and_keeps_its_bracket(self):
        result = highlight_signature_with_pygments(_cb1("Widget.method(self)"))
        line = _line_with(result, "Widget")

        assert '<span class="sig-class">Widget</span>' in line
        assert '<span class="op">.</span><span class="sig-name">method</span>(' in line

    def test_each_overload_line_is_marked(self):
        # `_render_overload_signatures` joins one call signature per line, with
        # no `@overload` decorator or `def` keyword in the block it writes.
        code = "func(a)\nfunc(a, b)"
        result = highlight_signature_with_pygments(_cb1(code))

        lines = [line for line in result.splitlines() if "func" in line]
        assert len(lines) == 2
        for line in lines:
            assert '<span class="sig-name">func</span>(' in line
