"""
The text and markup of a callable's signature
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from great_docs.pandoc.blocks import CodeBlock, Div
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import Code, Span

from ._format import escape_indents, escape_quotes, highlight_repr_value

if TYPE_CHECKING:
    from great_docs.pandoc.blocks import BlockContent


# Pandoc treats `<`, `>` and `&` as HTML, and the other characters as span,
# link, code-span, emphasis, maths, subscript, superscript, or citation
# delimiters. It reads a signature written as inline markup together with
# the annotation or default text it contains.
SIGNATURE_HTML_TRANSLATION = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
SIGNATURE_MARKDOWN_RE = re.compile(r"([\\`*_\[\]{}$~^@])")
# Pandoc also reads `--` as an en dash and `...` as an ellipsis. Escaping the
# second character breaks each run while preserving the lone `-` or `.` that
# numeric highlighting patterns match.
SIGNATURE_SMART_RE = re.compile(r"(?<=-)-|(?<=\.)\.")


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
    escaped = SIGNATURE_MARKDOWN_RE.sub(r"\\\1", s.translate(SIGNATURE_HTML_TRANSLATION))
    return SIGNATURE_SMART_RE.sub(r"\\\g<0>", escaped)


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
    # Read through the module: `active_settings` rebinds `SETTINGS` for the
    # duration of a build, so a name bound once would hold the old object.
    from . import _globals

    if _globals.SETTINGS.callable_signatures.wrap == "width":
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


# A parameter's own name, e.g. `host` in `host` or `port` in `port=8080`,
# with an optional `*`/`**` prefix preserved ahead of it. A bare `/` or `*`
# separator has no name to match, so it is left for the caller to skip.
_PARAMETER_NAME_RE = re.compile(r"^(\*{0,2})([A-Za-z_]\w*)")


def _mark_parameter(param: str) -> str:
    """
    Mark up a rendered parameter for the `plain` signature style

    The parameter's own name carries the class its term also carries in the
    `Parameters` section, naming the same thing the same way in both places.
    The stylesheet gives that class its weight only inside the docstring
    sections, so here the class marks the name without yet styling it. A
    literal default is highlighted the same way `highlight_repr_value`
    highlights it anywhere else; an annotation, when shown, is left as plain
    text. Every piece that came from the source is escaped, because a
    default value is arbitrary text that pandoc would otherwise read as
    markup.

    Parameters
    ----------
    param
        A single rendered parameter, e.g. `host` or `port=8080`.

    Returns
    -------
    The parameter with its name and any default marked up, or merely
    escaped if it is a bare `/` or `*` separator rather than a named
    parameter.
    """
    match = _PARAMETER_NAME_RE.match(param)
    if not match:
        return escape_signature_markup(param)
    prefix, bare_name = match.groups()
    annotation, sep, default = param[match.end() :].partition("=")
    if sep:
        # Escape first: the highlighting adds markup of its own, which must
        # survive intact, and escaping leaves a literal's quotes and digits
        # where the highlighting patterns expect them.
        default = highlight_repr_value(escape_signature_markup(default))
    marked_name = str(
        Span(escape_signature_markup(bare_name), Attr(classes=["doc-parameter-name"]))
    )
    prefix = escape_signature_markup(prefix)
    return f"{prefix}{marked_name}{escape_signature_markup(annotation)}{sep}{default}"


def _splice_marked_parameters(rest: str, params: list[str]) -> str:
    """
    Replace each parameter in already-wrapped signature text with its marked-up form

    `rest` is the `(...)` half of the text `make_call_signature_text`
    returned for the *plain* `params`, so the line breaks are already
    settled; this only substitutes each parameter's own text for
    `_mark_parameter`'s markup, at that parameter's own position. What
    lies between and after the parameters, such as a return annotation on
    an `@overload` variant, is escaped rather than marked up.

    A parameter is found by a cursor that only moves forward through
    `rest`, never by searching the whole string afresh on every
    parameter. A parameter's rendered text can itself contain another
    parameter's plain text as a substring, most often through a string
    default such as `x="a=1"` containing the literal text `a=1`; a fresh
    whole-string search would find that substring before the second
    parameter's real occurrence.

    Parameters
    ----------
    rest
        The text after the signature's opening `(`, built from `params`.
    params
        The same parameters, each still in its plain, unmarked form.

    Returns
    -------
    `rest` with each parameter's own text replaced by its marked-up form.
    """
    pieces: list[str] = []
    cursor = 0
    for param in params:
        start = rest.index(param, cursor)
        pieces.append(escape_signature_markup(rest[cursor:start]))
        pieces.append(_mark_parameter(param))
        cursor = start + len(param)
    pieces.append(escape_signature_markup(rest[cursor:]))
    return "".join(pieces)


def _mark_signature_text(text: str, params: list[str]) -> str:
    """
    Mark up one line of signature text for the `plain` signature style

    Parameters
    ----------
    text
        One rendered signature, e.g. `connect(host, port=8080)`, or a bare
        name for the kinds that are never called.
    params
        The parameters `text` was built from, each still in its plain,
        unmarked form.

    Returns
    -------
    The signature with its name and each of its parameters marked up, and
    everything else escaped.
    """
    name, bracket, rest = text.partition("(")
    marked_name = str(Span(escape_signature_markup(name), Attr(classes=["sig-name"])))
    if not bracket:
        return marked_name
    # `rest` carries the closing bracket, and the return annotation of an
    # `@overload` variant after it.
    return f"{marked_name}{bracket}{_splice_marked_parameters(rest, params)}"


def render_signature_block(lines: list[tuple[str, list[str]]], attr: Attr) -> BlockContent:
    """
    Build the block that carries a callable's signature

    Parameters
    ----------
    lines
        One pair per signature line: the line's text, and the parameters it
        was built from.
    attr
        The attributes of the enclosing div.

    Returns
    -------
    The signature, as a code block or as inline markup, according to
    `callable_signatures.style`.
    """
    # Read through the module: `active_settings` rebinds `SETTINGS` for the
    # duration of a build, so a name bound once would hold the old object.
    from . import _globals

    if _globals.SETTINGS.callable_signatures.style == "plain":
        marked = "\n".join(_mark_signature_text(text, params) for text, params in lines)
        # Not `pretty_code`: each default was already highlighted in isolation
        # by `_mark_parameter`, and `highlight_repr_value`'s string pattern is
        # unanchored, so running it again over the whole signature would match
        # the quotes already inside that markup and wrap them a second time.
        return Div(Code(escape_quotes(escape_indents(marked))).html, attr)

    text = "\n".join(text for text, _ in lines)
    return Div(CodeBlock(text, Attr(classes=["python"])), attr)
