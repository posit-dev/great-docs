from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from functools import lru_cache, partial, singledispatch
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import griffe as gf
from quartodoc.pandoc.components import Attr
from quartodoc.pandoc.inlines import Span

from ._pandoc.inlines import InterLink

if TYPE_CHECKING:
    from typing import Any

HAS_RUFF = bool(shutil.which("ruff"))

# Pickout python identifiers from a string of code
IDENTIFIER_RE = re.compile(r"\b(?P<identifier>[^\W\d]\w*)", flags=re.UNICODE)

# Pickout quoted strings from a string of code
STR_RE = re.compile(
    r"(?P<str>"  # group
    # Within quotes, match any character that has been backslashed
    # or that is not a double quote or backslash
    r'"(?:\\.|[^"\\])*"'  # double-quoted
    r"|"  # or
    r"'(?:\\.|[^'\\])*'"  # single-queoted
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


def markdown_escape(s: str) -> str:
    """
    Escape string that may be interpreted as markdown

    This function is deliberately not robust to all possibilities. It
    will improve as needed.
    """
    if s and s[0] in MARKDOWN_START_CHARS:
        s = rf"\{s}"
    return s


def _highlight_func(m: re.Match[str]) -> str:
    """
    Return matched group(string) wrapped in a Span for a string

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
    Convert qualified names in the see also section content into interlinks
    """

    def replace_func(m: re.Match[str]) -> str:
        # There should only one string in the groups
        txt = [g for g in m.groups() if g][0]
        res = ", ".join([str(InterLink(target=f"~{s.strip()}")) for s in txt.split(",")])
        return res

    content = QUALNAME_RE.sub(replace_func, dedent(s))
    return SEE_ALSO_MULTILINEITEM_RE.sub(" ", content)


@singledispatch
def repr_obj(obj: Any) -> str:
    return repr(obj)


@repr_obj.register
def _(obj: gf.Expr) -> str:
    """
    Representation of an expression as code
    """
    # We expect the obj expression to consist of
    # a combination of only strings and name expressions
    return "".join(repr_obj(x) for x in obj.iterate())


@repr_obj.register
def _(s: str) -> str:
    """
    Repr of str enclosed double quotes
    """
    if len(s) >= 2 and (s[0] == s[-1] == "'"):
        s = f'"{s[1:-1]}"'
    return s


@repr_obj.register
def _(obj: gf.ExprName) -> str:
    """
    A named expression
    """
    return obj.name


def canonical_path_lookup_table(el: gf.Expr):
    # Create lookup table
    lookup = {"TypeAlias": "typing.TypeAlias"}
    for o in el.iterate():
        # Assumes that name of an expresssion is a valid python
        # identifier
        if isinstance(o, gf.ExprName):
            lookup[o.name] = o.canonical_path
    return lookup


def formatted_signature(name: str, params: list[str]) -> str:
    """
    Return a formatted signature of function/method

    Parameters
    ----------
    name :
        Name of function/method/class(for the __init__ method)
    params :
        Parameters to the function. A each parameter is a
        string. e.g. a, *args, *, /, b=2, c=3, **kwargs
    """
    # Format to a maximum width of 78 chars
    # It fails when a parameter declarations is longer than 78
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
    sig = f"{opening}{params_string}{closing}"
    return sig


def pretty_code(s: str) -> str:
    """
    Make code that will not be highlighted by pandoc pretty

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


def interlink_groups(m: re.Match[str], lookup: dict[str, str]) -> str:
    """
    Substitute match text with value from lookup table
    """
    identifier_str = m.group("identifier")
    try:
        canonical_path = lookup[identifier_str]
    except KeyError:
        return identifier_str
    return str(InterLink(identifier_str, canonical_path))


def render_formatted_expr(el: gf.Expr) -> str:
    """
    Format and render expression any the identifiers interlinked

    Uses ruff for formatting

    Parameters
    ----------
    el
        An expression. This expression will most likely represent an annotation or
        a value on the right hand side of an `=` operator.

    Returns
    -------
    :
        Expression in markdown with the identifiers interlinked (to be handled by the
        interlinks filter). Any Spaces are encoded as `&nbsp;` and newlines with the
        `<br>` tag.
    """
    # This function works by:
    # 1. Formatting (with ruff) the str represented by the expression.
    # 2. Processes the expresssion and builds a {name: cannonical_path}
    #    lookup table for all the named parts of the expression.
    # 3. Creates a regex replacement function that uses the lookup table
    #    and to substitute a matched name (identifier) with an interlink.
    # 4. Does the regex substitution on the formatted string.
    # 5. Escapes the result to "hard code" the indentation, etc
    el_str = format_str(str(el))
    lookup = canonical_path_lookup_table(el)
    interlink_func = partial(interlink_groups, lookup=lookup)
    return pretty_code(IDENTIFIER_RE.sub(interlink_func, el_str))


def _tmp_stdin_filename() -> str:
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


_STDIN_FILENAME = _tmp_stdin_filename()


@lru_cache(maxsize=2048)
def format_str(source: str) -> str:
    """
    Format Python source code using Ruff

    This analogous to black.format_str.
    """
    proc = subprocess.run(
        [
            "ruff",
            "format",
            "--stdin-filename",
            _STDIN_FILENAME,
            "-",
        ],
        input=source,
        text=True,
        capture_output=True,
    )

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())

    return proc.stdout
