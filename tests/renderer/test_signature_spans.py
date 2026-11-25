"""
Tests for the highlight spans of `pythonsignature` blocks, for Quarto 2 (experimental)

The expected tokens are those Quarto 1 writes for the same lines with `pythonsignature.xml`.
"""

from __future__ import annotations

import json

import pytest

from great_docs._apiref._signature import render_signature_block
from great_docs._apiref._signature_spans import LINE_CAPTURE, signature_spans
from great_docs.pandoc.components import Attr

from .test_signature_styles import _OVERLOADED, _rendered


def _tokens(text: str) -> list[tuple[str, str]]:
    """The text and capture of each span, with the line spans left out"""
    code = text.encode()
    return [
        (code[start:end].decode(), capture)
        for start, end, capture in json.loads(signature_spans(text))
        if capture != LINE_CAPTURE
    ]


def test_marks_the_name_parameters_defaults_and_operators():
    assert _tokens("f(a: int = 1, *args, b=None, c=True, **kwargs) -> str") == [
        ("f", "function"),
        ("a", "variable"),
        ("int", "function.builtin"),
        ("=", "operator"),
        ("1", "number"),
        ("*", "operator"),
        ("args", "variable"),
        ("b", "variable"),
        ("=", "operator"),
        ("None", "constant"),
        ("c", "variable"),
        ("=", "operator"),
        ("True", "boolean"),
        ("**", "operator"),
        ("kwargs", "variable"),
        ("->", "operator"),
        ("str", "function.builtin"),
    ]


def test_marks_the_class_of_a_method():
    assert _tokens("Graph.add_node(node)") == [
        ("Graph", "type"),
        (".", "operator"),
        ("add_node", "function"),
        ("node", "variable"),
    ]


def test_marks_strings_with_their_prefix_and_escapes():
    assert _tokens(r"f(a=rb'x\n', b=1.5e3)") == [
        ("f", "function"),
        ("a", "variable"),
        ("=", "operator"),
        ("rb", "extension"),
        (r"'x\n'", "string"),
        ("b", "variable"),
        ("=", "operator"),
        ("1.5e3", "number"),
    ]


def test_marks_only_a_name_at_the_start_of_a_line():
    assert _tokens("f(\n    a,\n    b=g(),\n)") == [
        ("f", "function"),
        ("a", "variable"),
        ("b", "variable"),
        ("=", "operator"),
        ("g", "variable"),
    ]


def test_offsets_count_the_bytes_of_the_code():
    text = 'f(a="é", b=1)'
    spans = json.loads(signature_spans(text))
    code = text.encode()

    assert [code[start:end].decode() for start, end, _ in spans] == [
        "f",
        "a",
        "=",
        '"é"',
        "b",
        "=",
        "1",
        text,
    ]


def test_each_line_has_a_span_around_its_tokens():
    text = "f(a)\n\ng(b)"
    spans = json.loads(signature_spans(text))

    assert spans == [
        [0, 1, "function"],
        [2, 3, "variable"],
        [0, 4, LINE_CAPTURE],
        [6, 7, "function"],
        [8, 9, "variable"],
        [6, 10, LINE_CAPTURE],
    ]


def test_quarto_1_block_has_no_spans(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GREAT_DOCS_QUARTO", raising=False)

    block = str(render_signature_block([("f(a)", ["a"])], Attr(), "highlighted"))

    assert "```pythonsignature\nf(a)\n```" in block
    assert "data-hl-spans" not in block


def test_quarto_2_block_lists_its_spans(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")

    block = str(render_signature_block([("f(a)", ["a"])], Attr(), "highlighted"))

    spans = json.dumps(json.loads(signature_spans("f(a)"))).replace(" ", "")
    escaped = spans.replace('"', '\\"')
    assert f'``` {{.pythonsignature data-hl-spans="{escaped}"}}\nf(a)\n```' in block


def test_quarto_2_overloads_have_a_span_for_each_line(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GREAT_DOCS_QUARTO", "q2")

    qmd = _rendered(_OVERLOADED, "convert")

    code = qmd.split("``` {.pythonsignature", 1)[1].split("\n", 1)[1].split("\n```", 1)[0]
    assert code.count("\nconvert(") == 1
    assert qmd.count(LINE_CAPTURE) == len(code.splitlines()) == 8
