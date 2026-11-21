import griffe as gf
import pytest

from great_docs._apiref import FunctionRenderer, content
from great_docs._apiref._docstring_summary import summary_lines, summary_text
from great_docs._apiref._export import summary

WRAPPED = (
    "Keep the reader's view of the table, for when the page is opened again,\n"
    "and let them undo their changes to it.\n"
    "\n"
    "The view is the table's filters and sort."
)
WRAPPED_SUBJECT = (
    "Keep the reader's view of the table, for when the page is opened again, "
    "and let them undo their changes to it."
)


def _renderer(docstring: str) -> FunctionRenderer:
    function = gf.Function("process")
    function.docstring = gf.Docstring(docstring, parent=function, parser="numpy")
    return FunctionRenderer(content.Doc.from_griffe(function.name, function))


@pytest.mark.parametrize(
    ("text", "lines"),
    [
        ("One line.", ["One line."]),
        ("One line.\n\nMore.", ["One line."]),
        ("Wrapped\n  over two lines.\n\nMore.", ["Wrapped", "  over two lines."]),
        ("Summary.\n```python\nx = 1\n```", ["Summary."]),
        ("Summary.\n::: {.callout-note}\nNote.\n:::", ["Summary."]),
        ("Summary.\n$$\nx = 1\n$$", ["Summary."]),
        ("$$x$$ is the value.", ["$$x$$ is the value."]),
        ("$$\nx = 1\n$$", []),
        ("::: {.callout-note}\nNote.\n:::", []),
        ("~~~\ncode\n~~~", []),
        ("\nStarts blank.", []),
        ("", []),
    ],
)
def test_summary_lines_are_the_first_paragraph(text: str, lines: list[str]):
    assert summary_lines(text) == lines


def test_summary_text_joins_the_lines():
    assert summary_text(WRAPPED) == WRAPPED_SUBJECT


def test_wrapped_summary_is_the_whole_subject():
    renderer = _renderer(WRAPPED)

    assert renderer.docstring_subject == WRAPPED_SUBJECT
    body = str(renderer.render_body())
    assert "undo" not in body
    assert "The view is the table's filters and sort." in body


def test_wrapped_summary_is_whole_in_the_summary_row():
    [(_, description)] = _renderer(WRAPPED).render_summary()

    assert description == WRAPPED_SUBJECT


def test_one_line_summary_is_unchanged():
    renderer = _renderer("Process the input.\n\nMore details.")

    assert renderer.docstring_subject == "Process the input."
    body = str(renderer.render_body())
    assert "Process the input." not in body
    assert "More details." in body


def test_code_fence_after_the_summary_stays_in_the_body():
    renderer = _renderer("Process the input.\n```python\nprocess(1)\n```")

    assert renderer.docstring_subject == "Process the input."
    assert "process(1)" in str(renderer.render_body())


def test_export_summary_is_the_whole_first_paragraph():
    function = gf.Function("process")
    function.docstring = gf.Docstring(WRAPPED, parent=function, parser="numpy")

    assert summary(function) == WRAPPED_SUBJECT.rstrip(".")
