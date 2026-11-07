"""
Tables in the generated pages, as Quarto pipe tables or as raw HTML
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Protocol, Sequence

from great_docs._translations import translate

if TYPE_CHECKING:

    class Stringable(Protocol):
        def __str__(self) -> str: ...


# A backtick code span: a run of backticks, its content, and a run of the same length
_CODE_SPAN = re.compile(r"(`+).+?(?<!`)\1(?!`)")

# A `|` that is not already escaped
_PIPE = re.compile(r"(?<!\\)\|")


def _escape_pipes(text: str) -> str:
    """
    Escape the `|` characters that would otherwise split a pipe-table cell

    Pandoc keeps a `|` inside a code span as part of the code, and keeps the
    backslash of a `\\|` there too, so only the text outside code spans is escaped.

    Parameters
    ----------
    text
        The content of one cell.

    Returns
    -------
    :
        The cell content with each unescaped `|` outside code spans written as `\\|`.
    """
    pieces: list[str] = []
    pos = 0
    for m in _CODE_SPAN.finditer(text):
        pieces.append(_PIPE.sub(r"\\|", text[pos : m.start()]))
        pieces.append(m.group())
        pos = m.end()
    pieces.append(_PIPE.sub(r"\\|", text[pos:]))
    return "".join(pieces)


def _pipe_cell(text: str) -> str:
    """
    Fit Markdown text into a pipe-table cell

    Parameters
    ----------
    text
        The cell content, possibly over several lines.

    Returns
    -------
    :
        The content on one line, with `|` escaped.
    """
    line = " ".join(stripped for raw in text.splitlines() if (stripped := raw.strip()))
    return _escape_pipes(line)


def _pipe_row(cells: Sequence[str]) -> str:
    """
    Write one line of a pipe table

    Parameters
    ----------
    cells
        The cell contents, already fitted to one line each.

    Returns
    -------
    :
        The cells between `|` delimiters.
    """
    return "| " + " | ".join(cells) + " |"


def pipe_table(
    rows: Sequence[Sequence[str]],
    *,
    headers: Sequence[str],
    classes: Sequence[str] = (),
) -> str:
    """
    Render rows as a Quarto pipe table

    Each cell is Markdown and may span several lines; the table joins it onto
    one line and escapes any `|` that would split it.

    Parameters
    ----------
    rows
        The table body, one sequence of cells per row.
    headers
        The column headers, which also fix the number of columns.
    classes
        CSS classes for the rendered `<table>`. Quarto also adds its own
        `caption-top` and `table` classes to every pipe table.

    Returns
    -------
    :
        The pipe table, followed by an attribute line when `classes` is given.
    """
    lines = [
        _pipe_row([_pipe_cell(h) for h in headers]),
        "|" + "|".join("---" for _ in headers) + "|",
        *(_pipe_row([_pipe_cell(cell) for cell in row]) for row in rows),
    ]
    if classes:
        attributes = " ".join(f".{c}" for c in classes)
        lines += ["", f": {{{attributes}}}"]
    return "\n".join(lines)


def summary_table(rows: Sequence[tuple[Stringable, Stringable | None]], lang: str) -> str:
    """
    Render a two-column summary of documented objects

    The *Methods*, *Attributes* and similar sections, and the reference index in
    table mode, use this table. The `gd-summary-table` styles hide its header row
    and set the column widths.

    Parameters
    ----------
    rows
        One `(name, description)` pair per object. The name is usually a
        Markdown link to the object's documentation; a missing description
        leaves its cell empty.
    lang
        The language of the column headers, as a BCP 47 tag.

    Returns
    -------
    :
        A pipe table whose headers are in `lang`.
    """
    return pipe_table(
        [(str(name), "" if desc is None else str(desc)) for name, desc in rows],
        headers=[translate("name", lang), translate("description", lang)],
        classes=["gd-summary-table"],
    )


def html_table(
    rows: Sequence[Sequence[str]],
    *,
    headers: Sequence[str],
    table_class: str,
    col_widths: Sequence[int] | None = None,
) -> str:
    """
    Render rows as an HTML table with Quarto's Markdown-table classes

    The table carries Bootstrap's `caption-top table` classes alongside
    `table_class`, so it looks like the tables Quarto renders from Markdown.

    Parameters
    ----------
    rows
        The table body, one sequence of cells per row. Cells are inserted as
        HTML, so the caller escapes any text values.
    headers
        Column header labels, as plain text.
    table_class
        Extra CSS class for the `<table>` element.
    col_widths
        Percentage width of each column, applied as an inline `width` on each
        `<th>`. The widths take effect only if `table_class` sets
        `table-layout: fixed`.

    Returns
    -------
    :
        The HTML table.
    """
    full_class = f"caption-top table {table_class}"

    if col_widths is not None:
        header_cells = "".join(
            f'<th style="width: {w}%">{html.escape(h)}</th>' for h, w in zip(headers, col_widths)
        )
    else:
        header_cells = "".join(f"<th>{html.escape(h)}</th>" for h in headers)

    body_rows = ["  <tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows]

    return (
        f'<table class="{full_class}" data-quarto-disable-processing="true">\n'
        f'<thead>\n  <tr class="header">{header_cells}</tr>\n</thead>\n'
        f"<tbody>\n" + "\n".join(body_rows) + "\n</tbody>\n</table>"
    )
