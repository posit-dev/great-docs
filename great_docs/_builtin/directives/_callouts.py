"""Canonical Great Docs callout directives and their Quarto representation"""

from __future__ import annotations

import re
from textwrap import dedent

import griffe as gf

from great_docs._apiref.resolve import resolution_lang
from great_docs._translations import translate_versioned
from great_docs._utils import fenced_lines
from great_docs.hooks import on_object_resolved
from great_docs.pandoc.blocks import Div
from great_docs.pandoc.components import Attr

_CALLOUT_MAP: dict[str, str] = {
    "note": "note",
    "warning": "warning",
    "caution": "caution",
    "danger": "important",
    "important": "important",
    "tip": "tip",
    "hint": "tip",
}

# Translate version callout titles by directive name.
_VERSION_LABELS: dict[str, str] = {
    "versionadded": "added_in_version",
    "versionchanged": "changed_in_version",
    "deprecated": "deprecated_since_version",
}

_VERSION_DIRECTIVES = frozenset(_VERSION_LABELS)
CALLOUT_DIRECTIVES = frozenset(_CALLOUT_MAP) | _VERSION_DIRECTIVES
_DIRECTIVE_NAME_PATTERN = "|".join(
    re.escape(name) for name in sorted(CALLOUT_DIRECTIVES, key=len, reverse=True)
)
_DIRECTIVE_RE = re.compile(
    rf"^(?P<indent>[ \t]*)%(?P<name>{_DIRECTIVE_NAME_PATTERN})"
    r"(?:[ \t]+(?P<inline>.*?))?[ \t]*$"
)


@on_object_resolved(priority=0)  # pyright: ignore[reportArgumentType]
def add_callouts(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Replace canonical directives in docstring text with Quarto callouts

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    The object with canonical directives replaced in its docstring value.
    """
    docstring = obj.docstring
    if docstring is None:
        return obj

    converted = convert_directives(docstring.value)
    if converted != docstring.value:
        docstring.value = converted
    return obj


def render_callout(name: str, body: str, inline: str = "") -> str:
    """
    Render a recognized docstring directive as Quarto callout markup

    Parameters
    ----------
    name
        The directive name.
    body
        The directive's indented body.
    inline
        Text written on the directive line.

    Returns
    -------
    Quarto callout markup.
    """
    content = join_content(inline, body)
    if name in _VERSION_DIRECTIVES:
        parts = content.split(None, 1) if content else []
        version = parts[0] if parts else ""
        description = parts[1] if len(parts) > 1 else ""
        title = translate_versioned(_VERSION_LABELS[name], resolution_lang.get(), version)
        callout = "warning" if name == "deprecated" else "note"
        attr = Attr(
            classes=[f"callout-{callout}"],
            attributes={"title": title},
        )
        return str(Div(content=description, attr=attr))

    callout = _CALLOUT_MAP[name]
    return str(Div(content=content, attr=Attr(classes=[f"callout-{callout}"])))


def convert_directives(text: str) -> str:
    """
    Render canonical callout directives in docstring text as Quarto blocks

    Parameters
    ----------
    text
        Docstring text containing canonical directives.

    Returns
    -------
    The text with recognized directives replaced by Quarto callouts.
    """
    if "%" not in text:
        return text

    lines, fenced = fenced_lines(text)
    converted: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        candidate = not fenced[index] and line.lstrip().startswith("%")
        match = _DIRECTIVE_RE.match(line) if candidate else None
        if match is None:
            converted.append(line)
            index += 1
            continue

        directive_indent = len(match.group("indent"))
        body_lines, index = collect_indented_body(lines, index + 1, directive_indent)
        body = "\n".join(dedent_lines(body_lines))
        converted.extend(
            render_callout(
                match.group("name"),
                body,
                match.group("inline") or "",
            ).splitlines()
        )

    return "\n".join(converted)


def join_content(inline: str, body: str) -> str:
    """
    Join inline directive text with its multiline body

    Parameters
    ----------
    inline
        Text written on the directive line.
    body
        Text collected from the directive body.

    Returns
    -------
    The non-empty inline and body text joined in source order.
    """
    parts = [part.strip() for part in (inline, body) if part.strip()]
    return "\n".join(parts)


def collect_indented_body(
    lines: list[str],
    start: int,
    directive_indent: int,
) -> tuple[list[str], int]:
    """
    Collect an indented directive body and its first unconsumed line

    Parameters
    ----------
    lines
        Source lines following a directive.
    start
        Index at which to start collecting.
    directive_indent
        Indentation of the directive line.

    Returns
    -------
    The collected body lines and the index of the first unconsumed line.
    """
    body: list[str] = []
    index = start

    while index < len(lines):
        line = lines[index]
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if indent <= directive_indent:
                break
            body.append(line)
            index += 1
            continue

        next_content = index + 1
        while next_content < len(lines) and not lines[next_content].strip():
            next_content += 1
        if next_content >= len(lines):
            break
        next_line = lines[next_content]
        next_indent = len(next_line) - len(next_line.lstrip())
        if next_indent <= directive_indent:
            break
        body.append("")
        index += 1

    return body, index


def dedent_lines(lines: list[str]) -> list[str]:
    """
    Align body lines to the least-indented nonblank content

    Parameters
    ----------
    lines
        Body lines to align.

    Returns
    -------
    The body lines with their common indentation removed.
    """
    return dedent("\n".join(lines)).splitlines()
