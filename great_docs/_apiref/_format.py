from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from functools import lru_cache, singledispatch
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import griffe as gf

from great_docs._subprocess import TEXT_MODE_KWARGS
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import InterLink, Span

if TYPE_CHECKING:
    from typing import Any

    from . import content
    from .typing import DisplayNameFormat

HAS_RUFF = bool(shutil.which("ruff"))

# Pickout quoted strings from a string of code
STR_RE = re.compile(
    r"(?P<str>"  # group
    # Within quotes, match any character that has been backslashed
    # or that is not a double quote or backslash
    r'"(?:\\.|[^"\\])*"'  # double-quoted
    r"|"  # or
    r"'(?:\\.|[^'\\])*'"  # single-quoted
    ")",
    flags=re.UNICODE,
)
INT_RE = re.compile(r"^(?P<int>[+-]?\d+)$")
FLOAT_RE = re.compile(r"^(?P<float>[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?)$")
BOOL_RE = re.compile(r"^(?P<bool>True|False)$")
TYPE_RE_LOOKUP = {
    # The second element of the tuple are the respective pygments highlight classes
    "str": (STR_RE, "st"),
    "int": (INT_RE, "dv"),
    "float": (FLOAT_RE, "fl"),
    "bool": (BOOL_RE, "va"),
}

# Pickout qualified path names at the beginning of every line
_qualname = r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*"
QUALNAME_RE = re.compile(
    rf"^((?:{_qualname},\s*)+{_qualname})|" rf"^({_qualname})(?!,)",
    flags=re.MULTILINE,
)

SEE_ALSO_MULTILINEITEM_RE = re.compile(r"\n +")

# quotes in inline <code> are converted to curly quotes.
# This translation table maps the quotes to html escape sequences
QUOTES_TRANSLATION = str.maketrans({'"': "&quot;", "'": "&apos;"})

# Characters that can appear that the start of a markedup string
MARKDOWN_START_CHARS = {"_", "*"}

# `<`, `>` and `&` open html; the rest open a span, a link, a code span,
# or emphasis. A signature written as inline markup is read by pandoc, so
# whatever a parameter's annotation or default happens to contain is read
# with it.
SIGNATURE_HTML_TRANSLATION = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
SIGNATURE_MARKDOWN_RE = re.compile(r"([\\`*_\[\]{}])")


def escape_quotes(s: str) -> str:
    """
    Replace double & single quotes with html escape sequences
    """
    return s.translate(QUOTES_TRANSLATION)


def escape_indents(s: str) -> str:
    """
    Convert indent spaces & newlines to &nbsp; and <br>

    The goal of this function is to convert a few spaces as is required
    to preserve the formatting.
    """
    return s.replace(" " * 4, "&nbsp;" * 4).replace("\n", "<br>")


def escape_signature_markup(s: str) -> str:
    """
    Escape text a signature carries so that it cannot become markup

    Applies to the text of a signature written as inline markup, where
    pandoc reads a default value such as `"<b>"` or `"[x]{.y}"` as an html
    tag or a span rather than as the characters the user typed. Call it on
    the plain text only, never on markup this renderer has already added.

    Parameters
    ----------
    s
        Plain text from a signature, e.g. a parameter's default value.

    Returns
    -------
    :
        The text with its html and markdown characters neutralised.
    """
    return SIGNATURE_MARKDOWN_RE.sub(r"\\\1", s.translate(SIGNATURE_HTML_TRANSLATION))


def markdown_escape(s: str) -> str:
    """
    Escape a string that may be interpreted as markdown

    This function is deliberately not robust to all possibilities. It
    will improve as needed.
    """
    if s and s[0] in MARKDOWN_START_CHARS:
        s = rf"\{s}"
    return s


def _highlight_func(m: re.Match[str]) -> str:
    """
    Wrap the matched group in a `Span` for a string

    Helper function for highlight_repr_value
    """
    matched_type = cast("str", m.lastgroup)
    klass = TYPE_RE_LOOKUP[matched_type][1]
    value = m.group(matched_type)
    return str(Span(value, Attr(classes=[klass])))


@lru_cache(2048)
def highlight_repr_value(value: str) -> str:
    """
    Highlight a repr value

    Highlighting is done by creating a markdown span with a class
    that matches that used by pygments. This function only highlights
    values of type int, float and str, anything else is unmodified.

    Parameters
    ----------
    value
        A repr string value.

    Returns
    -------
    :
        Highlighted value. e.g.:
        - `"4"` becomes `'[4]{.dv}'`
        - `"3.14"` becomes `'[3.14]{.fl}'`
        - `'"some"'` becomes `"['some']{.st}"`
    """
    for pattern, _ in TYPE_RE_LOOKUP.values():
        value, count = pattern.subn(_highlight_func, value)
        if count > 0:
            break
    return value


def format_see_also(s: str) -> str:
    """
    Convert qualified names in see-also section content into interlinks
    """

    def replace_func(m: re.Match[str]) -> str:
        # There should only one string in the groups
        txt = [g for g in m.groups() if g][0]
        res = ", ".join([str(InterLink(target=f"~{s.strip()}")) for s in txt.split(",")])
        return res

    content = QUALNAME_RE.sub(replace_func, dedent(s))
    return SEE_ALSO_MULTILINEITEM_RE.sub(" ", content)


def format_name(doc: content.Doc, format: DisplayNameFormat = "relative") -> str:
    """
    Build a name to use for the object

    Parameters
    ----------
    format:
        The format to use for the object's name.
    """
    obj = cast("gf.Alias | gf.Object", doc.obj)
    if format == "doc":
        res = doc.name
    elif format in ("name", "short"):
        res = obj.name
    elif format == "relative":
        res = ".".join(obj.path.split(".")[1:])
    elif format == "full":
        res = obj.path
    elif format == "canonical":
        res = obj.canonical_path
    else:
        raise ValueError(f"Unknown format {format!r} for an object name.")
    return res


@singledispatch
def repr_obj(obj: Any) -> str:
    return repr(obj)


@repr_obj.register
def _(obj: gf.Expr) -> str:
    """
    Represent an expression as code
    """
    # We expect the obj expression to consist of
    # a combination of only strings and name expressions
    return "".join(repr_obj(x) for x in obj.iterate())


@repr_obj.register
def _(s: str) -> str:
    """
    Normalize a wrapping pair of single quotes on `s` to double quotes

    A string that is not single-quoted passes through unchanged.
    """
    if len(s) >= 2 and (s[0] == s[-1] == "'"):
        s = f'"{s[1:-1]}"'
    return s


@repr_obj.register
def _(obj: gf.ExprName) -> str:
    """
    Represent a named expression as its bare name
    """
    return obj.name


def make_call_signature_text(name: str, params: list[str]) -> str:
    """
    Build the text of a callable's signature

    Parameters
    ----------
    name
        Name of the function, method, or class (for the `__init__` method).
    params
        Parameters of the callable, each already rendered as a string,
        e.g. `a`, `*args`, `*`, `/`, `b=2`, `c=3`, `**kwargs`.

    Returns
    -------
    The signature, broken across lines according to the wrap style.
    """
    from ._globals import SIGNATURE_STYLE

    if SIGNATURE_STYLE.wrap == "width":
        return _wrap_to_width(name, params)
    return _wrap_per_parameter(name, params)


def _wrap_per_parameter(name: str, params: list[str]) -> str:
    """
    Break a signature so that each parameter has a line of its own

    Parameters
    ----------
    name
        Name of the callable.
    params
        Parameters of the callable, each already rendered as a string.

    Returns
    -------
    The signature on one line when it has fewer than two parameters, and one
    parameter per line otherwise.
    """
    if len(params) < 2:
        return f"{name}({', '.join(params)})"
    pad = " " * 4
    body = f",\n{pad}".join(params)
    return f"{name}(\n{pad}{body},\n)"


def _wrap_to_width(name: str, params: list[str]) -> str:
    """
    Break a signature only when it outgrows the line limit

    Parameters
    ----------
    name
        Name of the callable.
    params
        Parameters of the callable, each already rendered as a string.

    Returns
    -------
    The signature on one line when it fits within 78 characters, and broken
    across lines otherwise.
    """
    opening = f"{name}("
    params_string = ", ".join(params)
    closing = ")"
    pad = " " * 4
    if len(opening) + len(params_string) > 78:
        line_pad = f"\n{pad}"
        # One parameter per line
        if len(params_string) > 74:
            params_string = f",{line_pad}".join(params)
        params_string = f"{line_pad}{params_string}"
        closing = f"\n{closing}"
    return f"{opening}{params_string}{closing}"


def pretty_code(s: str) -> str:
    """
    Make code that pandoc will not syntax-highlight presentable

    code inside html <code></code> tags (and without <pre> tags)
    makes it possible to have links & interlinks. But the white
    spaces and newlines in the code are squashed. And this code
    is also not highlighted by pandoc.

    Parameters
    ----------
    s :
        Code to be modified. It should already have markdown for
        the links, but should not be wrapped inside the <code>
        tags. Those tags should wrap the output of this function.
    """
    return escape_quotes(escape_indents(highlight_repr_value(dedent(s))))


def render_formatted_expr(el: gf.Expr) -> str:
    """
    Render an expression as ruff-formatted code

    Uses ruff for formatting

    Parameters
    ----------
    el
        An expression. This expression will most likely represent an annotation or
        a value on the right hand side of an `=` operator.

    Returns
    -------
    :
        Expression formatted with ruff. Spaces are encoded as `&nbsp;` and
        newlines with the `<br>` tag.
    """
    el_str = format_str(str(el))
    return pretty_code(el_str)


@lru_cache(1)
def _stdin_filename() -> str:
    """
    Create a temp filename for ruff to use when formatting code snippets

    The file serves mainly as virtual placeholder to infer things like
    the location of the config file or as a reference for warnings and
    errors. So a single filename should suffice for all calls to ruff.

    ref: https://github.com/astral-sh/ruff/issues/17307
    """
    with tempfile.NamedTemporaryFile(suffix=".py", dir=Path.cwd()) as f:
        filename = Path(f.name).name
    return filename


@lru_cache(maxsize=2048)
def format_str(source: str) -> str:
    """
    Format Python source code with ruff

    Parameters
    ----------
    source
        Python code to format. This is a snippet, e.g. an expression,
        rather than the contents of a file.

    Returns
    -------
    :
        Formatted code, with no trailing newline. Only a file needs a
        newline to terminate it, and `ruff format` adds one because it
        reads and writes whole files.
    """
    if not HAS_RUFF:
        return source

    proc = subprocess.run(
        [
            "ruff",
            "format",
            "--stdin-filename",
            _stdin_filename(),
            "-",
        ],
        input=source,
        **TEXT_MODE_KWARGS,
        capture_output=True,
    )

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())

    return proc.stdout.removesuffix("\n")


def format_value(value: str | gf.Expr | None = None) -> str:
    """
    Render a value as escaped, highlighted markdown

    Parameters
    ----------
    value
        A value that can appear on the right-hand-side of an `=`
        operator.

    Returns
    -------
    :
        Escaped and highlighted markdown represenation of the value.
        It is not markedup as code.
    """
    return pretty_code(repr_obj(value))
