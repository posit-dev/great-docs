from __future__ import annotations

import re
from functools import partial, singledispatch
from textwrap import dedent
from typing import TYPE_CHECKING, cast

import griffe as gf
from quartodoc.pandoc.components import Attr
from quartodoc.pandoc.inlines import Span

from ._pandoc.inlines import InterLink

if TYPE_CHECKING:
    from typing import Any

# Pickout python identifiers from a string of code
IDENTIFIER_RE = re.compile(r"\b(?P<identifier>[^\W\d]\w*)", flags=re.UNICODE)

# Pickout quoted strings from a string of code
STRING_RE = re.compile(
    r"(?P<string>"  # group
    # Within quotes, match any character that has been backslashed
    # or that is not a double quote or backslash
    r'"(?:\\.|[^"\\])*"'  # double-quoted
    r"|"  # or
    r"'(?:\\.|[^'\\])*'"  # single-queoted
    ")",
    flags=re.UNICODE,
)

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


def string_match_highlight_func(m: re.Match[str]) -> str:
    """
    Return matched group(string) wrapped in a Span for a string
    """
    string_str = m.group("string")
    return str(Span(string_str, Attr(classes=["st"])))


def highlight_strings(s: str) -> str:
    """
    Wrap quoted sub-strings in s with a hightlight group for strings
    """
    return STRING_RE.sub(string_match_highlight_func, s)


def format_see_also(s: str) -> str:
    """
    Convert qualified names in the see also section content into interlinks
    """

    def replace_func(m: re.Match[str]) -> str:
        # There should only one string in the groups
        txt = [g for g in m.groups() if g][0]
        res = ", ".join(
            [str(InterLink(target=f"~{s.strip()}")) for s in txt.split(",")]
        )
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
    return escape_quotes(escape_indents(highlight_strings(dedent(s))))


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


def render_attribute_declaration(el: gf.Attribute) -> str:
    """
    Render expression with identifiers in them interlinked
    """
    if not el.value or isinstance(el.value, str):
        return str(el.value)

    lookup = canonical_path_lookup_table(el.value)
    interlink_func = partial(interlink_groups, lookup=lookup)
    definition_str = "\n".join(el.lines)
    return IDENTIFIER_RE.sub(interlink_func, definition_str)


def render_dataclass_parameter(
    param: gf.Parameter,
    attr: gf.Attribute,
) -> str:
    """
    Render a dataclass parameter

    Parameters
    ----------
    param :
        The parameter
    attr :
        The attribute form of the parameter
    """
    definition_str = "\n".join(attr.lines)

    match param.annotation:
        case gf.Expr():
            lookup = canonical_path_lookup_table(param.annotation)
            interlink_func = partial(interlink_groups, lookup=lookup)
            res = IDENTIFIER_RE.sub(interlink_func, definition_str)
        case _:
            res = definition_str

    return res


def render_dataclass_init_parameter(param: gf.Parameter) -> str:
    """
    Render a dataclass parameter

    Parameters
    ----------
    param :
        The parameter
    """
    try:
        annotation = cast(
            "gf.Expr", cast("gf.ExprSubscript", param.annotation).slice
        )
    except AttributeError:
        # A dataclass that also defines an __init__ may have parameters
        # that do not have annotations.
        return param.name
    lookup = canonical_path_lookup_table(annotation)
    interlink_func = partial(interlink_groups, lookup=lookup)
    default = f"=  {param.default}" if param.default else ""
    definition_str = f"{param.name}: {annotation} {default}"
    return IDENTIFIER_RE.sub(interlink_func, definition_str)
