from unittest.mock import MagicMock

from great_docs._checks.lint import LintResult, _check_ambiguous_references
from great_docs._interlinks import AliasClaims, resolve_aliases


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
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset({"demo.store.Cache", "demo.net.Cache"}),
            )
        ).dropped,
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
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset(),
            )
        ).dropped,
        {"demo.store.Cache": "No references here."},
        result,
    )

    assert result.issues == []


def test_a_reference_to_an_unambiguous_short_name_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        resolve_aliases(
            AliasClaims(claimed=(("Thing", "demo.Thing"),), published=frozenset({"demo.Thing"}))
        ).dropped,
        {"demo.Thing": "See [](`Thing`)."},
        result,
    )

    assert result.issues == []


def test_the_shortening_marker_is_ignored_when_matching():
    result = LintResult()

    _check_ambiguous_references(
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset(),
            )
        ).dropped,
        {"guide.qmd": "See [](`~Cache`)."},
        result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].symbol == "guide.qmd"


def test_a_reference_shown_as_example_text_in_a_fenced_block_is_not_reported():
    """Ignore interlink syntax inside a fenced code block."""
    result = LintResult()

    _check_ambiguous_references(
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset(),
            )
        ).dropped,
        {"guide.qmd": "Example:\n\n```python\n# See [](`Cache`) for details.\n```\n"},
        result,
    )

    assert result.issues == []


def test_a_reference_shown_as_example_text_in_a_code_span_is_not_reported():
    """Ignore interlink syntax inside a multi-backtick span."""
    result = LintResult()

    _check_ambiguous_references(
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset(),
            )
        ).dropped,
        {"guide.qmd": "Write `` [](`Cache`) `` to link to it."},
        result,
    )

    assert result.issues == []


def test_a_real_reference_alongside_example_text_is_still_reported():
    """Keep a live reference when example text appears beside it."""
    result = LintResult()

    _check_ambiguous_references(
        resolve_aliases(
            AliasClaims(
                claimed=(("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")),
                published=frozenset(),
            )
        ).dropped,
        {"guide.qmd": "See [](`Cache`) for details, written as `` [](`Cache`) `` in source."},
        result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].symbol == "guide.qmd"


def test_the_prose_walk_reads_docstrings_and_pages(tmp_path):
    from great_docs._checks.lint import _gather_prose

    (tmp_path / "guide.qmd").write_text("See [](`Cache`).", encoding="utf-8")

    prose = _gather_prose([_fake_item("demo.Cache", "A cache.")], tmp_path)

    assert prose["demo.Cache"] == "A cache."
    assert prose["guide.qmd"] == "See [](`Cache`)."


def test_the_prose_walk_reads_a_submodule_qualified_docstring(tmp_path):
    """An object the renderer documents but the package does not export at top level."""
    from great_docs._checks.lint import _gather_prose

    prose = _gather_prose([_fake_item("demo.store.Cache", "See [](`Cache`).")], tmp_path)

    assert prose["demo.store.Cache"] == "See [](`Cache`)."


def test_a_reference_in_an_indented_code_block_is_not_reported():
    """Ignore an indented example while still reporting the prose around it"""
    result = LintResult()

    _check_ambiguous_references(
        {"Cache": ("demo.net.Cache", "demo.store.Cache")},
        {
            "guide.qmd": (
                "Write it like this:\n"
                "\n"
                "    See [](`Cache`) for details.\n"
                "\n"
                "        A deeper line of the same example, [](`Cache`) again.\n"
                "\n"
                "And [](`Cache`) here is a reference the page really makes.\n"
            )
        },
        result,
    )

    assert len(result.issues) == 1


def test_a_reference_in_an_indented_list_continuation_is_reported():
    """Indented prose under a list item is prose, not an example"""
    result = LintResult()

    _check_ambiguous_references(
        {"Cache": ("demo.net.Cache", "demo.store.Cache")},
        {"guide.qmd": "- The first item\n\n      goes on about [](`Cache`) at length.\n"},
        result,
    )

    assert len(result.issues) == 1


_FLUSH = {"flush": ("demo.NetCache.flush", "demo.StoreCache.flush")}


def test_a_code_span_naming_an_ambiguous_short_name_is_a_warning():
    """The build would link the span if one object claimed the name"""
    result = LintResult()

    _check_ambiguous_references(_FLUSH, {"guide.qmd": "Call `flush()` when done."}, result)

    assert len(result.issues) == 1
    assert result.issues[0].check == "ambiguous-autolink"
    assert result.issues[0].severity == "warning"
    assert result.issues[0].symbol == "guide.qmd"
    assert "`~~demo.NetCache.flush`" in result.issues[0].message


def test_code_spans_with_and_without_parentheses_and_shortening_are_reported():
    result = LintResult()

    _check_ambiguous_references(
        _FLUSH, {"guide.qmd": "Use `flush`, `~~flush()` or `~~.flush()`."}, result
    )

    assert [issue.check for issue in result.issues] == ["ambiguous-autolink"] * 3


def test_a_qualified_code_span_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        _FLUSH,
        {"guide.qmd": "Use `~~demo.StoreCache.flush()` or `NetCache.flush()`."},
        result,
    )

    assert result.issues == []


def test_a_docstring_naming_its_own_object_is_not_reported():
    """The page of `demo.StoreCache.flush` saying "`flush()` writes..." links nowhere new"""
    result = LintResult()

    _check_ambiguous_references(
        _FLUSH,
        {
            "demo.StoreCache.flush": "The `flush()` method writes the cache.",
            "demo.StoreCache": "Call `flush()` to write the cache.",
        },
        result,
    )

    assert [issue.symbol for issue in result.issues] == ["demo.StoreCache"]


def test_a_code_span_the_build_leaves_alone_is_not_reported():
    """A span marked `.gd-no-link`, in link text, or in example code is never linked"""
    result = LintResult()

    _check_ambiguous_references(
        _FLUSH,
        {
            "guide.qmd": (
                "The `flush`{.gd-no-link} key, [`flush()`](https://example.com) and "
                "[`flush()`](`StoreCache.flush`) aren't reported.\n"
                "\n"
                "```python\n"
                "cache.flush()  # `flush()`\n"
                "```\n"
                "\n"
                "Nor is `` `flush()` `` written as example text.\n"
            )
        },
        result,
    )

    assert result.issues == []


def test_an_explicit_reference_is_reported_once_as_an_error():
    """The code span inside an explicit reference is the reference's text, not a second finding"""
    result = LintResult()

    _check_ambiguous_references(_FLUSH, {"guide.qmd": "See [](`flush`)."}, result)

    assert [(issue.check, issue.severity) for issue in result.issues] == [
        ("ambiguous-xref", "error")
    ]


def test_the_prose_walk_reads_an_object_documented_under_two_paths_once(tmp_path):
    """The reference lists `demo.Cache` and the `demo.store.Cache` it re-exports"""
    from great_docs._checks.lint import _gather_prose

    module_path = _fake_item("demo.store.Cache", "A cache.")
    module_path.aliases = ()
    public_path = _fake_item("demo.Cache", "A cache.")
    public_path.aliases = ("Cache",)
    for item in (module_path, public_path):
        item.obj.canonical_path = "demo.store.Cache"

    prose = _gather_prose([module_path, public_path], tmp_path)

    assert prose == {"demo.Cache": "A cache."}


def test_code_spans_are_checked_only_in_the_prose_the_site_renders():
    """A planning note isn't published, so its code spans are never linked"""
    result = LintResult()

    _check_ambiguous_references(
        _FLUSH,
        {
            "user_guide/caching.qmd": "Call `flush()`.",
            "NOTES.md": "Call `flush()`, see [](`flush`).",
        },
        result,
        autolinked={"user_guide/caching.qmd"},
    )

    assert [(issue.symbol, issue.check) for issue in result.issues] == [
        ("user_guide/caching.qmd", "ambiguous-autolink"),
        ("NOTES.md", "ambiguous-xref"),
    ]
