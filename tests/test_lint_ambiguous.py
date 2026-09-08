from unittest.mock import MagicMock

from great_docs._interlinks import AliasClaims
from great_docs._lint import LintResult, _check_ambiguous_references


def _fake_item(name, docstring):
    """Stand-in for a manifest item, carrying the griffe object's docstring"""
    item = MagicMock()
    item.name = name
    item.obj.docstring = MagicMock()
    item.obj.docstring.value = docstring
    return item


def test_a_reference_to_an_ambiguous_short_name_is_an_error():
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset({"demo.store.Cache", "demo.net.Cache"}),
        ),
        {"demo.store.Cache": "See [](`Cache`) for details."},
        result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].check == "ambiguous-xref"
    assert result.issues[0].severity == "error"
    assert "demo.net.Cache" in result.issues[0].message
    assert "demo.store.Cache" in result.issues[0].message


def test_an_unreferenced_collision_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset(),
        ),
        {"demo.store.Cache": "No references here."},
        result,
    )

    assert result.issues == []


def test_a_reference_to_an_unambiguous_short_name_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(claimed=(("Thing", "demo.Thing"),), published=frozenset({"demo.Thing"})),
        {"demo.Thing": "See [](`Thing`)."},
        result,
    )

    assert result.issues == []


def test_the_shortening_marker_is_ignored_when_matching():
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset(),
        ),
        {"guide.qmd": "See [](`~Cache`)."},
        result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].symbol == "guide.qmd"


def test_a_reference_shown_as_example_text_in_a_fenced_block_is_not_reported():
    """Ignore interlink syntax inside a fenced code block."""
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset(),
        ),
        {"guide.qmd": "Example:\n\n```python\n# See [](`Cache`) for details.\n```\n"},
        result,
    )

    assert result.issues == []


def test_a_reference_shown_as_example_text_in_a_code_span_is_not_reported():
    """Ignore interlink syntax inside a multi-backtick span."""
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset(),
        ),
        {"guide.qmd": "Write `` [](`Cache`) `` to link to it."},
        result,
    )

    assert result.issues == []


def test_a_real_reference_alongside_example_text_is_still_reported():
    """Keep a live reference when example text appears beside it."""
    result = LintResult()

    _check_ambiguous_references(
        AliasClaims(
            claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
            published=frozenset(),
        ),
        {"guide.qmd": "See [](`Cache`) for details, written as `` [](`Cache`) `` in source."},
        result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].symbol == "guide.qmd"


def test_the_prose_walk_reads_docstrings_and_pages(tmp_path):
    from great_docs._lint import _gather_prose

    (tmp_path / "guide.qmd").write_text("See [](`Cache`).", encoding="utf-8")

    prose = _gather_prose([_fake_item("demo.Cache", "A cache.")], tmp_path)

    assert prose["demo.Cache"] == "A cache."
    assert prose["guide.qmd"] == "See [](`Cache`)."


def test_the_prose_walk_reads_a_submodule_qualified_docstring(tmp_path):
    """An object the renderer documents but the package does not export at top level."""
    from great_docs._lint import _gather_prose

    prose = _gather_prose([_fake_item("demo.store.Cache", "See [](`Cache`).")], tmp_path)

    assert prose["demo.store.Cache"] == "See [](`Cache`)."
