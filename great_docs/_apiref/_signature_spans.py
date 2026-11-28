"""
The highlight spans of a `pythonsignature` block, for Quarto 2 (experimental)

Quarto 1 highlights `pythonsignature` blocks with the grammar in `pythonsignature.xml`. Quarto 2
reads no such grammars, but it highlights a code block whose `data-hl-spans` attribute lists
the spans, as `[start, end, capture]` triples with byte offsets into the code. It writes each
span as `<span class="hl-{capture}">`, with any `.` in the capture written as `-`. This module
applies the grammar's rules, so that a signature has the same tokens under both Quartos.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

__all__ = ["LINE_CAPTURE", "signature_spans"]

_GRAMMAR = Path(__file__).parents[1] / "assets" / "pythonsignature.xml"

LINE_CAPTURE = "signature.line"
"""The capture of the span around each line, standing in for Quarto 1's line `span`"""

# The capture for each of the grammar's attributes. Where Quarto 2 has a capture for the
# skylighting token that Quarto 1 gives an attribute, the span uses it, so Quarto 2's
# translation of the highlight style colours the span as Quarto 1 does.
_CAPTURES = {
    "Name": "function",
    "Class": "type",
    "Variable": "variable",
    "Builtin": "function.builtin",
    "Exception": "extension",
    "StringPrefix": "extension",
    "Keyword": "keyword",
    "None": "constant",
    "Bool": "boolean",
    "Int": "number",
    "Float": "number",
    "String": "string",
    "Operator": "operator",
}

# The grammar's word lists, in the order its rules try them
_WORD_LISTS = (
    ("nones", "None"),
    ("bools", "Bool"),
    ("builtins", "Builtin"),
    ("exceptions", "Exception"),
    ("keywords", "Keyword"),
    ("wordops", "Operator"),
)

# Skylighting's default keyword delimiters. A listed word matches only when it begins after
# one of them, or at the start of a line, and ends before one.
_DELIMITERS = frozenset(" \t.():!+,-<=>%&*/;?[]^{|}~\\")

_IDENT = r"[^\W\d]\w*"
_CLASS_RE = re.compile(rf"{_IDENT}(?=\.{_IDENT}(\(|$))")
_NAME_RE = re.compile(rf"{_IDENT}(?=\(|$)")
_IDENT_RE = re.compile(_IDENT)
_PREFIX_RE = re.compile(r"[bBrRuUfF]{1,2}(?=[\"'])")
_FLOAT_RE = re.compile(r"(\d+\.\d*|\.\d+)([eE][+-]?\d+)?|\d+[eE][+-]?\d+")
_INT_RE = re.compile(r"\d+")
# Skylighting's `HlCStringChar`: a C escape sequence
_ESCAPE_RE = re.compile(r"\\(?:[abefnrtv\"'?\\]|x[0-9A-Fa-f]+|[0-7]{1,3})")
_OPERATORS = frozenset("=*/|-+.<>%&^~@!")


@cache
def _word_lists() -> tuple[tuple[frozenset[str], str], ...]:
    """
    Read the grammar's word lists, each with the attribute its rule gives

    Returns
    -------
    :
        One pair for each list, in the order the grammar's rules try them.
    """
    root = ET.parse(_GRAMMAR).getroot()
    lists = {
        element.get("name"): frozenset(item.text or "" for item in element.iter("item"))
        for element in root.iter("list")
    }
    return tuple((lists[name], attribute) for name, attribute in _WORD_LISTS)


def _listed_word(line: str, pos: int) -> tuple[int, str] | None:
    """
    Match a word from one of the grammar's lists at a position in a line

    Parameters
    ----------
    line
        A line of the signature.
    pos
        The position of the word's first character.

    Returns
    -------
    :
        The end of the word and its attribute, or `None` when no listed word begins there.
    """
    if pos > 0 and line[pos - 1] not in _DELIMITERS:
        return None
    end = pos
    while end < len(line) and line[end] not in _DELIMITERS:
        end += 1
    word = line[pos:end]
    for words, attribute in _word_lists():
        if word in words:
            return end, attribute
    return None


def _line_tokens(line: str) -> list[tuple[int, int, str]]:
    """
    Split a line of a signature into the grammar's tokens

    Parameters
    ----------
    line
        A line of the signature, without its line break.

    Returns
    -------
    :
        The start, end and attribute of each token, as character positions in the line.
        Adjacent tokens with the same attribute are one token, and text without an
        attribute has no token.
    """
    tokens: list[tuple[int, int, str]] = []

    def add(start: int, end: int, attribute: str) -> int:
        if tokens and tokens[-1][2] == attribute and tokens[-1][1] == start:
            tokens[-1] = (tokens[-1][0], end, attribute)
        else:
            tokens.append((start, end, attribute))
        return end

    pos = 0
    context = "Start"
    quote = ""
    while pos < len(line):
        char = line[pos]
        if context == "String":
            escape = _ESCAPE_RE.match(line, pos)
            end = escape.end() if escape else pos + 1
            if not escape and char == quote:
                context = "Start"
            pos = add(pos, end, "String")
            continue
        if context == "Qualified":
            name = _IDENT_RE.match(line, pos)
            if char == ".":
                pos = add(pos, pos + 1, "Operator")
            elif name:
                context = "Start"
                pos = add(pos, name.end(), "Name")
            else:
                pos += 1
            continue
        if pos == 0 and (match := _CLASS_RE.match(line)):
            context = "Qualified"
            pos = add(pos, match.end(), "Class")
            continue
        if pos == 0 and (match := _NAME_RE.match(line)):
            pos = add(pos, match.end(), "Name")
            continue
        if listed := _listed_word(line, pos):
            pos = add(pos, *listed)
            continue
        for pattern, attribute in (
            (_PREFIX_RE, "StringPrefix"),
            (_IDENT_RE, "Variable"),
            (_FLOAT_RE, "Float"),
            (_INT_RE, "Int"),
        ):
            if match := pattern.match(line, pos):
                pos = add(pos, match.end(), attribute)
                break
        else:
            if char in "\"'":
                context = "String"
                quote = char
                pos = add(pos, pos + 1, "String")
            elif char in _OPERATORS:
                pos = add(pos, pos + 1, "Operator")
            else:
                pos += 1
    return tokens


def signature_spans(text: str) -> str:
    """
    Build the `data-hl-spans` value that highlights a signature as Quarto 1 does

    Parameters
    ----------
    text
        The signature, one line per `@overload` variant or wrapped parameter.

    Returns
    -------
    :
        The spans as JSON: each token's span, then a `LINE_CAPTURE` span around its line.
    """
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.split("\n"):
        # Byte offsets into the UTF-8 code, at each character of the line
        positions = [offset]
        for char in line:
            positions.append(positions[-1] + len(char.encode()))
        spans.extend(
            (positions[start], positions[end], _CAPTURES[attribute])
            for start, end, attribute in _line_tokens(line)
        )
        # The span around the line, which the stylesheet's overload gap selects
        if line:
            spans.append((positions[0], positions[-1], LINE_CAPTURE))
        offset = positions[-1] + 1
    return json.dumps([list(span) for span in spans], separators=(",", ":"))
