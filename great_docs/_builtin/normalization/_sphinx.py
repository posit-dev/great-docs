"""Sphinx and reStructuredText source normalization"""

from __future__ import annotations

import re

import griffe as gf

from great_docs.hooks import on_object_resolved

_RST_CODE_BLOCK_RE = re.compile(
    r"^(.*?)::[ ]*\n"
    r"(\n)"
    r"((?:[ ]{4,}\S.*\n?)+)",
    re.MULTILINE,
)
_RST_INLINE_MATH_RE = re.compile(r":math:`([^`]+)`")
_RST_SIMPLE_TABLE_SEPARATOR_RE = re.compile(r"^=+(\s+=+)+\s*$")
_RST_SIMPLE_TABLE_SECOND_COLUMN_RE = re.compile(r"\s+(=+)")
_RST_SIMPLE_TABLE_COLUMN_RE = re.compile(r"=+")
_RST_GRID_TABLE_BORDER_RE = re.compile(r"^\+[-=]+(\+[-=]+)+\+\s*$")
_RST_GRID_TABLE_COLUMN_RE = re.compile(r"\+")
_RST_GRID_TABLE_ROW_RE = re.compile(r"^\|")
_RST_GRID_TABLE_HEADER_BORDER_RE = re.compile(r"^\+[=+]+\+\s*$")
_RST_GRID_TABLE_BODY_BORDER_RE = re.compile(r"^\+[-+]+\+\s*$")
_CALLABLE_RST_ROLES = frozenset({"func", "meth"})
_SPHINX_ROLE_NAMES = "exc|class|func|meth|attr|const|mod|obj|data|type"
_SPHINX_ROLE_RE = re.compile(rf":(?:py:)?(?P<role>{_SPHINX_ROLE_NAMES}):`(?P<inner>[^`]+)`")


@on_object_resolved(priority=10)  # pyright: ignore[reportArgumentType]
def normalize_sphinx_markup(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Convert ordinary Sphinx markup to Quarto-compatible Markdown

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    The object with Sphinx markup normalized when its parser is Sphinx.
    """
    docstring = obj.docstring
    if docstring is None or docstring.parser != gf.Parser.sphinx:
        return obj

    text = _smart_dedent(docstring.value)
    text = _RST_CODE_BLOCK_RE.sub(_replace_rst_code_block, text)
    text = _RST_INLINE_MATH_RE.sub(r"$\1$", text)
    text = _convert_sphinx_roles(text)
    text = _convert_rst_simple_tables(text)
    text = _convert_rst_grid_tables(text)
    docstring.value = text
    return obj


def _dedent_lines(lines: list[str]) -> list[str]:
    """Remove the smallest nonblank indentation from a sequence of lines"""
    min_indent = min((len(line) - len(line.lstrip()) for line in lines if line.strip()), default=0)
    return [line[min_indent:] for line in lines]


def _replace_rst_code_block(match: re.Match[str]) -> str:
    """Convert one RST double-colon block to a static Python fence"""
    prefix = match.group(1).rstrip()
    if prefix:
        prefix += ":"
    block = "\n".join(_dedent_lines(match.group(3).splitlines()))
    return f"{prefix}\n\n```python\n{block}\n```\n"


def _smart_dedent(text: str) -> str:
    """Remove indentation relative to the first nonblank source line"""
    lines = text.splitlines(True)
    margin = 0
    for line in lines:
        if line.strip():
            margin = len(line) - len(line.lstrip())
            break

    if not margin:
        return text

    result: list[str] = []
    for line in lines:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            result.append(line[min(margin, indent) :])
        else:
            result.append(line)
    return "".join(result)


def _convert_sphinx_roles(text: str) -> str:
    """Convert supported Sphinx cross-reference roles to code spans"""

    def replace(match: re.Match[str]) -> str:
        role = match.group("role")
        target = match.group("inner")
        if role in _CALLABLE_RST_ROLES and not target.endswith("()"):
            target += "()"
        return f"`{target}`"

    return _SPHINX_ROLE_RE.sub(replace, text)


def _markdown_table(header: list[str], rows: list[list[str]]) -> str:
    """Render a Markdown pipe table from its header and body rows"""
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
    return "\n".join(lines)


def _pad_rows(rows: list[list[str]], width: int) -> None:
    """Pad table rows to a common column count"""
    for row in rows:
        row.extend([""] * (width - len(row)))


def _convert_rst_simple_tables(text: str) -> str:
    """Convert RST simple tables to Markdown pipe tables"""
    lines = text.split("\n")
    result: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not _RST_SIMPLE_TABLE_SEPARATOR_RE.match(line):
            result.append(line)
            index += 1
            continue

        table_lines = [line]
        separator_count = 1
        second_column = _RST_SIMPLE_TABLE_SECOND_COLUMN_RE.search(line)
        second_column_start = second_column.start(1) if second_column else 4
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor]
            is_separator = bool(_RST_SIMPLE_TABLE_SEPARATOR_RE.match(current))
            table_lines.append(current)
            if is_separator:
                separator_count += 1
                if separator_count >= 3:
                    cursor += 1
                    break
                following = cursor + 1
                continues = (
                    following < len(lines)
                    and lines[following].strip()
                    and not _RST_SIMPLE_TABLE_SEPARATOR_RE.match(lines[following])
                    and len(lines[following]) > second_column_start
                    and lines[following][second_column_start] != " "
                )
                if not continues:
                    cursor += 1
                    break
            cursor += 1

        converted = _simple_table_to_markdown(table_lines)
        if converted is None:
            result.append(line)
            index += 1
        else:
            result.append(converted)
            index = cursor

    return "\n".join(result)


def _simple_table_to_markdown(table_lines: list[str]) -> str | None:
    """Convert one complete RST simple table to Markdown"""
    separators = [
        (index, line)
        for index, line in enumerate(table_lines)
        if _RST_SIMPLE_TABLE_SEPARATOR_RE.match(line)
    ]
    if len(separators) < 2:
        return None

    # The separator pattern requires at least two `=` runs, each defining a column.
    spans = [
        (match.start(), match.end())
        for match in _RST_SIMPLE_TABLE_COLUMN_RE.finditer(separators[0][1])
    ]

    def cells(line: str) -> list[str]:
        values: list[str] = []
        for index, (start, _end) in enumerate(spans):
            next_start = spans[index + 1][0] if index + 1 < len(spans) else None
            values.append(line[start:next_start].strip() if len(line) > start else "")
        return values

    first_separator = separators[0][0]
    last_separator = separators[-1][0]
    header_rows: list[list[str]] = []
    body_rows: list[list[str]] = []
    if len(separators) == 2:
        body_rows = [
            cells(table_lines[index]) for index in range(first_separator + 1, last_separator)
        ]
        if body_rows:
            header_rows = [body_rows.pop(0)]
    else:
        second_separator = separators[1][0]
        header_rows = [
            cells(table_lines[index]) for index in range(first_separator + 1, second_separator)
        ]
        body_rows = [
            cells(table_lines[index]) for index in range(second_separator + 1, last_separator)
        ]

    if not header_rows:
        return None
    header = header_rows[-1]
    _pad_rows([header, *body_rows], len(spans))
    return _markdown_table(header, body_rows)


def _convert_rst_grid_tables(text: str) -> str:
    """Convert RST grid tables to Markdown pipe tables"""
    lines = text.split("\n")
    result: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not _RST_GRID_TABLE_BORDER_RE.match(line):
            result.append(line)
            index += 1
            continue

        table_lines = [line]
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor]
            if _RST_GRID_TABLE_BORDER_RE.match(current):
                table_lines.append(current)
                if cursor + 1 >= len(lines) or not _RST_GRID_TABLE_ROW_RE.match(lines[cursor + 1]):
                    cursor += 1
                    break
            elif _RST_GRID_TABLE_ROW_RE.match(current):
                table_lines.append(current)
            else:
                break
            cursor += 1

        converted = _grid_table_to_markdown(table_lines)
        if converted is None:
            result.append(line)
            index += 1
        else:
            result.append(converted)
            index = cursor

    return "\n".join(result)


def _grid_table_to_markdown(table_lines: list[str]) -> str | None:
    """Convert one complete RST grid table to Markdown"""
    # The border pattern requires at least two cells, giving at least three `+` boundaries.
    positions = [match.start() for match in _RST_GRID_TABLE_COLUMN_RE.finditer(table_lines[0])]
    spans = list(zip(positions[:-1], positions[1:]))

    def cells(line: str) -> list[str]:
        return [line[start + 1 : end].strip() if len(line) > start else "" for start, end in spans]

    header_rows: list[list[str]] = []
    current_rows: list[list[str]] = []
    has_header = False
    for line in table_lines:
        if _RST_GRID_TABLE_HEADER_BORDER_RE.match(line):
            has_header = True
            header_rows = current_rows
            current_rows = []
        elif _RST_GRID_TABLE_BODY_BORDER_RE.match(line):
            continue
        elif _RST_GRID_TABLE_ROW_RE.match(line):
            current_rows.append(cells(line))

    body_rows = current_rows
    if has_header:
        if not header_rows:
            return None
    else:
        if not body_rows:
            return None
        header_rows = [body_rows.pop(0)]

    header = header_rows[-1]
    _pad_rows([header, *body_rows], len(spans))
    return _markdown_table(header, body_rows)
