import pytest

from great_docs._apiref._render._tables import pipe_table, summary_table


def test_pipe_table_has_a_row_per_input_and_no_attributes_by_default():
    """Lay out a header, a separator and one row per input"""
    table = pipe_table([("a", "1", "x"), ("b", "2", "y")], headers=["Key", "Value", "Note"])
    assert table.splitlines() == [
        "| Key | Value | Note |",
        "|---|---|---|",
        "| a | 1 | x |",
        "| b | 2 | y |",
    ]


def test_pipe_table_keeps_each_cell_on_one_line():
    """Join a multi-line cell onto one line and leave an empty cell empty"""
    table = pipe_table([("a", "first line\n   second line\n\n"), ("b", "")], headers=["K", "V"])
    assert table.splitlines()[2:] == ["| a | first line second line |", "| b |  |"]


def test_pipe_table_escapes_pipes_outside_code_spans():
    """Escape `|` in prose but not in code, where Pandoc would keep the backslash"""
    table = pipe_table([("a", "Return `int | None` or a | b")], headers=["K", "V"])
    assert table.splitlines()[2] == r"| a | Return `int | None` or a \| b |"


def test_summary_table_keeps_markdown_links_and_its_class():
    """Leave name links as Markdown and mark the table for the summary styles"""
    link = "[get()](reference/Config.qmd#get){.doc-function .doc-label .doc-label-method}"
    table = summary_table([(link, "Get a value."), ("[x](#x)", None)], "en")
    lines = table.splitlines()
    assert lines[2] == f"| {link} | Get a value. |"
    assert lines[3] == "| [x](#x) |  |"
    assert lines[-1] == ": {.gd-summary-table}"
    assert lines[-2] == ""


@pytest.mark.parametrize(
    ("lang", "header"), [("en", "| Name | Description |"), ("fr", "| Nom | Description |")]
)
def test_summary_table_headers_follow_the_site_language(lang: str, header: str):
    """Translate the column headers, which the Markdown companion shows"""
    assert summary_table([("[x](#x)", "y")], lang).splitlines()[0] == header
