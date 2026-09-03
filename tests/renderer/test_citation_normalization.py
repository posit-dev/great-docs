import griffe as gf
import pytest

from great_docs._builtin.normalization._citations import (
    normalize_citations,
    _protected_lines,
    _live_reference_matches,
)

_PARSERS = ("numpy", "google", "sphinx")


def _function(text: str, parser: str) -> gf.Function:
    """Build a function whose docstring uses the selected parser"""
    obj = gf.Function("process")
    obj.docstring = gf.Docstring("", parent=obj, parser=parser)
    obj.docstring.value = text
    return obj


def _normalized(text: str, parser: str) -> str:
    """Return the docstring text after citation normalisation"""
    result = normalize_citations(_function(text, parser))
    assert result.docstring is not None
    return result.docstring.value


def _normalized_for(name: str, text: str, parser: str) -> str:
    """Return normalised docstring text for an object with the given name"""
    obj = gf.Function(name)
    obj.docstring = gf.Docstring("", parent=obj, parser=parser)
    obj.docstring.value = text
    result = normalize_citations(obj)
    assert result.docstring is not None
    return result.docstring.value


@pytest.mark.parametrize("parser", _PARSERS)
def test_citation_converts_under_every_parser(parser: str):
    """
    Verify every parser converts numbered citation markers

    Numbered citation conversion is parser-independent.
    """
    source = '.. [1] Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."'
    expected = '1. [Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."]{#cite-process-1}'
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_wrapped_citation_joins_onto_one_line(parser: str):
    """Verify an indented continuation joins its citation"""
    source = '.. [1] Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."\n   Communications of the ACM, 4(7), 321.'
    expected = '1. [Hoare, C.A.R. (1961). "Algorithm 64: Quicksort." Communications of the ACM, 4(7), 321.]{#cite-process-1}'
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_bare_url_in_a_citation_becomes_a_link(parser: str):
    """Verify Quarto autolinks bare citation URLs"""
    source = ".. [2] https://en.wikipedia.org/wiki/Arithmetic_mean"
    expected = "2. [<https://en.wikipedia.org/wiki/Arithmetic_mean>]{#cite-process-2}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_markdown_link_in_a_citation_keeps_its_closing_parenthesis(parser: str):
    """Verify autolinking preserves a Markdown link's closing parenthesis"""
    source = ".. [1] Author, [Title](https://example.com/paper) 2020."
    expected = "1. [Author, [Title](<https://example.com/paper>) 2020.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_sentence_full_stop_stays_outside_url_autolink(parser: str):
    """Keep a sentence-ending full stop outside the URL autolink"""
    source = ".. [1] Hoare, C.A.R. (1961). https://example.com/a."
    expected = "1. [Hoare, C.A.R. (1961). <https://example.com/a>.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_comma_between_url_and_prose_stays_outside_autolink(parser: str):
    """Keep a separating comma outside the URL autolink"""
    source = ".. [1] Hoare, https://example.com/a, 1961."
    expected = "1. [Hoare, <https://example.com/a>, 1961.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_url_autolink_excludes_parenthesis_and_full_stop(parser: str):
    """Keep an unmatched closing parenthesis and full stop outside the autolink"""
    source = ".. [1] Hoare (https://example.com/a)."
    expected = "1. [Hoare (<https://example.com/a>).]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_url_autolink_stops_before_adjacent_citation_reference(parser: str):
    """Keep adjacent citation-reference markup outside the URL autolink"""
    source = ".. [1] See https://example.com/a[1]_"
    expected = (
        "1. "
        '[^](#ref-process-1-1){.gd-linkback-text .gd-linkback-caret role="doc-backlink"} '
        "[See <https://example.com/a>"
        '[^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"}'
        "]{#cite-process-1}"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_every_bare_url_on_a_line_becomes_an_autolink(parser: str):
    """Autolink every bare URL in a citation body"""
    source = ".. [1] Data https://example.com/a. Code https://example.com/b, 2020."
    expected = (
        "1. [Data <https://example.com/a>. Code <https://example.com/b>, 2020.]{#cite-process-1}"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_rst_inline_literal_url_remains_literal(parser: str):
    """Leave a URL inside double backticks unchanged"""
    source = ".. [1] See ``https://example.com/a`` for details."
    expected = "1. [See ``https://example.com/a`` for details.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_markdown_inline_code_url_remains_literal(parser: str):
    """Leave a URL inside single backticks unchanged"""
    source = ".. [1] See `https://example.com/a` for details."
    expected = "1. [See `https://example.com/a` for details.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_citation_body_is_passed_through_unescaped(parser: str):
    """
    Verify citation bodies enter anchor spans without escaping

    Normalisation preserves unmatched brackets. Authors must escape them to
    keep the span valid.
    """
    source = ".. [1] Author ] stray 2020."
    expected = "1. [Author ] stray 2020.]{#cite-process-1}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_consecutive_citations_keep_their_numbers(parser: str):
    """Verify consecutive citations retain their labels"""
    source = ".. [1] First source.\n.. [2] Second source."
    expected = "1. [First source.]{#cite-process-1}\n2. [Second source.]{#cite-process-2}"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_text_without_citations_passes_through(parser: str):
    """Verify text without citations remains unchanged"""
    source = "Compute the mean.\n\nSee the module docs for details."
    assert _normalized(source, parser) == source


@pytest.mark.parametrize("parser", _PARSERS)
def test_alphabetic_label_is_left_alone(parser: str):
    """
    Verify alphabetic citation labels remain unchanged

    Markdown ordered lists require numeric labels, so conversion handles only
    numbered citations.
    """
    source = '.. [CIT2002] Cormen, T.H. et al. (2009). "Introduction to Algorithms".'
    assert _normalized(source, parser) == source


def test_docstringless_object_is_returned_unchanged():
    """Verify an object without a docstring remains unchanged"""
    obj = gf.Function("process")
    assert normalize_citations(obj) is obj


@pytest.mark.parametrize("parser", _PARSERS)
def test_indented_citation_keeps_its_indentation(parser: str):
    """Verify nested citations retain their indentation"""
    source = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    .. [1] Hoare, C. A. R. (1961). Algorithm 64: Quicksort.\n"
    )
    expected = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    1. [Hoare, C. A. R. (1961). Algorithm 64: Quicksort.]{#cite-process-1}\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_consecutive_indented_citations_stay_separate(parser: str):
    """Verify adjacent nested citations remain separate"""
    source = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    .. [1] Hoare, C. A. R. (1961). Algorithm 64: Quicksort.\n"
        "    .. [2] Knuth, D. (1998). The Art of Computer Programming.\n"
    )
    expected = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    1. [Hoare, C. A. R. (1961). Algorithm 64: Quicksort.]{#cite-process-1}\n"
        "    2. [Knuth, D. (1998). The Art of Computer Programming.]{#cite-process-2}\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_indented_continuation_joins_when_more_indented_than_its_marker(parser: str):
    """Verify a nested continuation joins only its citation"""
    source = (
        '    .. [1] Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."\n'
        "       Communications of the ACM, 4(7), 321.\n"
    )
    expected = (
        '    1. [Hoare, C.A.R. (1961). "Algorithm 64: Quicksort." '
        "Communications of the ACM, 4(7), 321.]{#cite-process-1}\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_citation_with_body_on_the_following_line_converts(parser: str):
    """Verify a citation can start its body on the following line"""
    source = ".. [1]\n   Hoare, C. A. R. (1961). Algorithm 64.\n"
    expected = "1. [Hoare, C. A. R. (1961). Algorithm 64.]{#cite-process-1}\n"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_indented_citation_does_not_swallow_the_following_text(parser: str):
    """Verify a nested citation preserves the following section"""
    source = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    .. [1] Hoare, C. A. R. (1961). Algorithm 64: Quicksort.\n"
        "\n"
        "Returns\n"
        "-------\n"
        "int\n"
        "    A description.\n"
    )
    result = _normalized(source, parser)
    assert "Returns" in result
    assert "A description." in result
    assert ".. [" not in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_multi_paragraph_citation_anchors_every_paragraph(parser: str):
    """
    Verify one citation anchor contains every paragraph

    Quarto builds its hover preview from the target element, but a bracketed
    Markdown span cannot contain multiple paragraphs.
    """
    source = (
        '.. [1] Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."\n'
        "\n"
        "       Communications of the ACM, 4(7), 321.\n"
    )
    expected = (
        "1. ::: {#cite-process-1 .gd-cite-body}\n"
        '   Hoare, C.A.R. (1961). "Algorithm 64: Quicksort."\n'
        "\n"
        "   Communications of the ACM, 4(7), 321.\n"
        "   :::\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_block_citation_preserves_nested_indentation(parser: str):
    """Preserve a nested list's relative indentation in a block citation"""
    source = (
        ".. [1] Knuth, D. (1998). The Art of Computer Programming.\n"
        "\n"
        "       - Volume 3, Sorting and Searching,\n"
        "         second edition\n"
        "       - Section 6.2.1\n"
    )
    expected = (
        "1. ::: {#cite-process-1 .gd-cite-body}\n"
        "   Knuth, D. (1998). The Art of Computer Programming.\n"
        "\n"
        "   - Volume 3, Sorting and Searching,\n"
        "     second edition\n"
        "   - Section 6.2.1\n"
        "   :::\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_block_citation_keeps_backlink_inside_anchor(parser: str):
    """Keep the backlink in the anchored first paragraph"""
    source = "See [1]_.\n\n.. [1] Hoare, C.A.R. (1961).\n\n       A second paragraph.\n"
    expected = (
        'See [^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"}.\n'
        "\n"
        "1. ::: {#cite-process-1 .gd-cite-body}\n"
        "   [^](#ref-process-1-1){.gd-linkback-text .gd-linkback-caret "
        'role="doc-backlink"} Hoare, C.A.R. (1961).\n'
        "\n"
        "   A second paragraph.\n"
        "   :::\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_marker_indentation_ends_citation_body(parser: str):
    """Keep prose at the marker's indentation outside the citation"""
    source = ".. [1] Hoare, C.A.R. (1961).\n\nUnrelated prose.\n"
    expected = "1. [Hoare, C.A.R. (1961).]{#cite-process-1}\n\nUnrelated prose.\n"
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_following_definition_ends_citation_body(parser: str):
    """Recognise a following definition at any indentation as a new citation"""
    same_indent = ".. [1] First source.\n\n       Its second paragraph.\n\n.. [2] Second source.\n"
    assert _normalized(same_indent, parser) == (
        "1. ::: {#cite-process-1 .gd-cite-body}\n"
        "   First source.\n"
        "\n"
        "   Its second paragraph.\n"
        "   :::\n"
        "\n"
        "2. [Second source.]{#cite-process-2}\n"
    )

    deeper_indent = ".. [1] First source.\n\n   .. [2] Second source.\n"
    assert _normalized(deeper_indent, parser) == (
        "1. [First source.]{#cite-process-1}\n\n   2. [Second source.]{#cite-process-2}\n"
    )


@pytest.mark.parametrize("parser", _PARSERS)
def test_fenced_code_after_blank_line_ends_citation_body(parser: str):
    """Keep fenced code after a blank line outside the citation"""
    source = ".. [1] Hoare, C.A.R. (1961).\n\n   ```python\n   quicksort(xs)\n   ```\n"
    expected = (
        "1. [Hoare, C.A.R. (1961).]{#cite-process-1}\n\n   ```python\n   quicksort(xs)\n   ```\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_indented_block_citation_preserves_outer_indentation(parser: str):
    """Convert a nested block citation without changing its outer indentation"""
    source = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    .. [1] Hoare, C.A.R. (1961).\n"
        "\n"
        "           A second paragraph.\n"
    )
    expected = (
        "Parameters\n"
        "----------\n"
        "x\n"
        "    Something clever.\n"
        "\n"
        "    1. ::: {#cite-process-1 .gd-cite-body}\n"
        "       Hoare, C.A.R. (1961).\n"
        "\n"
        "       A second paragraph.\n"
        "       :::\n"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_single_reference_links_both_ways(parser: str):
    """
    Verify one reference and its citation link in both directions

    The citation uses a linked caret to return to the single reference.
    """
    source = "See [1]_ for details.\n\n.. [1] Hoare, C.A.R. (1961)."
    expected = (
        'See [^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"} for details.\n\n'
        "1. "
        '[^](#ref-process-1-1){.gd-linkback-text .gd-linkback-caret role="doc-backlink"} '
        "[Hoare, C.A.R. (1961).]{#cite-process-1}"
    )
    assert _normalized(source, parser) == expected


@pytest.mark.parametrize("parser", _PARSERS)
def test_repeated_references_get_lettered_backlinks(parser: str):
    """
    Verify repeated references receive distinct backlinks

    The citation uses an inert caret followed by one lettered link for each
    reference in source order.
    """
    source = "Based on [1]_. Refined in [1]_.\n\n.. [1] Hoare, C.A.R. (1961)."
    result = _normalized(source, parser)

    assert '[^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"}' in result
    assert '[^1^](#cite-process-1){#ref-process-1-2 .gd-cite-ref role="doc-noteref"}' in result
    assert "[^]{.gd-linkback-text .gd-linkback-caret}" in result
    assert (
        '[a](#ref-process-1-1){.gd-linkback-text .gd-linkback-letter role="doc-backlink"}'
    ) in result
    assert (
        '[b](#ref-process-1-2){.gd-linkback-text .gd-linkback-letter role="doc-backlink"}'
    ) in result
    assert "[^](#ref-process-1-1)" not in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_uncited_citation_carries_no_marker(parser: str):
    """Verify an unreferenced citation has no backlink marker"""
    source = ".. [1] Hoare, C.A.R. (1961)."
    assert _normalized(source, parser) == "1. [Hoare, C.A.R. (1961).]{#cite-process-1}"


@pytest.mark.parametrize("parser", _PARSERS)
def test_forward_reference_links(parser: str):
    """
    Verify a reference can precede its citation

    References sections usually follow the prose that cites them.
    """
    source = "Notes\n-----\nBased on [1]_.\n\nReferences\n----------\n.. [1] Smith, J. (2020)."
    result = _normalized(source, parser)
    assert '[^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"}' in result
    assert "[^](#ref-process-1-1){.gd-linkback-text" in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_unmatched_reference_is_left_alone(parser: str):
    """
    Verify an undefined reference remains literal

    Linking it would hide the missing citation.
    """
    source = "See [1]_ and [7]_.\n\n.. [1] Hoare, C.A.R. (1961)."
    result = _normalized(source, parser)
    assert '[^1^](#cite-process-1){#ref-process-1-1 .gd-cite-ref role="doc-noteref"}' in result
    assert "[7]_" in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_reference_without_any_citation_is_left_alone(parser: str):
    """Verify references remain unchanged when no citations are defined"""
    source = "See [1]_ for details."
    assert _normalized(source, parser) == source


@pytest.mark.parametrize("parser", _PARSERS)
def test_anchors_differ_between_objects(parser: str):
    """
    Verify separate objects use distinct citation anchors

    A class page can render several members that each define `.. [1]`.
    Including the object path prevents their anchors from colliding.
    """
    source = "See [1]_.\n\n.. [1] Hoare, C.A.R. (1961)."
    first = _normalized_for("quicksort", source, parser)
    second = _normalized_for("binary_search", source, parser)

    assert "#cite-quicksort-1" in first
    assert "#cite-binary_search-1" in second
    assert "quicksort" not in second


@pytest.mark.parametrize("parser", _PARSERS)
def test_dotted_object_path_becomes_a_valid_anchor(parser: str):
    """
    Verify dotted object paths produce selector-safe anchors

    Replace dots with hyphens so CSS treats them as text rather than class
    selectors. The `cite-` prefix also prevents a leading digit.
    """
    module = gf.Module("gdtest_long_docs")
    obj = gf.Function("transform_data", parent=module)
    obj.docstring = gf.Docstring("", parent=obj, parser=parser)
    obj.docstring.value = "See [1]_.\n\n.. [1] Smith, J. (2020)."
    result = normalize_citations(obj)
    assert result.docstring is not None
    assert "#cite-gdtest_long_docs-transform_data-1" in result.docstring.value


@pytest.mark.parametrize("parser", _PARSERS)
def test_anchor_slug_does_not_collapse_distinct_paths(parser: str):
    """
    Verify case and separator differences produce distinct anchors

    Keep case and underscores so `pkg.foo_bar` and `pkg_foo.bar`, and `Foo.Bar`
    and `foo.bar`, cannot collapse to the same anchor.
    """
    source = "See [1]_.\n\n.. [1] Hoare, C.A.R. (1961)."

    def _for(dotted_path: str) -> str:
        parts = dotted_path.split(".")
        module = gf.Module(parts[0])
        obj = gf.Function(parts[1], parent=module)
        obj.docstring = gf.Docstring("", parent=obj, parser=parser)
        obj.docstring.value = source
        result = normalize_citations(obj)
        assert result.docstring is not None
        return result.docstring.value

    underscore_first = _for("pkg.foo_bar")
    underscore_second = _for("pkg_foo.bar")
    assert "#cite-pkg-foo_bar-1" in underscore_first
    assert "#cite-pkg_foo-bar-1" in underscore_second
    assert underscore_first != underscore_second

    case_first = _for("Foo.Bar")
    case_second = _for("foo.bar")
    assert "#cite-Foo-Bar-1" in case_first
    assert "#cite-foo-bar-1" in case_second
    assert case_first != case_second

    digit_led = _for("123pkg.thing")
    assert "#cite-123pkg-thing-1" in digit_led

    for value in (underscore_first, underscore_second, case_first, case_second, digit_led):
        anchor_id = value.split("#", 1)[1].split("}", 1)[0]
        assert not anchor_id[0].isdigit()


@pytest.mark.parametrize("parser", _PARSERS)
def test_anchor_span_wraps_the_reference_text(parser: str):
    """
    Verify each citation anchor wraps its body

    Quarto builds a footnote-style hover preview from the target element's
    HTML. Wrapping the body gives the preview content to display.
    """
    source = ".. [1] Hoare, C.A.R. (1961)."
    result = _normalized(source, parser)
    assert "[Hoare, C.A.R. (1961).]{#cite-process-1}" in result


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "a"), (1, "b"), (25, "z"), (26, "aa"), (27, "ab"), (51, "az"), (52, "ba")],
)
def test_occurrence_label_sequence(index: int, expected: str):
    """Verify backlink labels continue after `z`"""
    from great_docs._builtin.normalization._citations import _occurrence_label

    assert _occurrence_label(index) == expected


def test_fenced_block_and_delimiters_remain_literal():
    """Mark both fence delimiters and their content as literal code"""
    lines = ["before", "```python", "code", "```", "after"]
    assert _protected_lines(lines) == [False, True, True, True, False]


def test_tilde_fenced_block_remains_literal():
    """Recognise tilde delimiters as a fenced code block"""
    lines = ["~~~", "code", "~~~", "after"]
    assert _protected_lines(lines) == [True, True, True, False]


def test_shorter_delimiter_does_not_close_longer_fence():
    """Keep a fence open until a delimiter is at least as long as its opener"""
    lines = ["````", "```", "code", "```", "````", "after"]
    assert _protected_lines(lines) == [True, True, True, True, True, False]


def test_info_string_opens_fence():
    """Open a fence when its delimiter includes an info string"""
    lines = ["```python", "code"]
    assert _protected_lines(lines) == [True, True]


def test_unfenced_doctest_prompts_remain_literal():
    """Mark doctest prompts and continuations as code, but not their output"""
    lines = [">>> value = 1", "... value", "1", ">>>", "prose"]
    assert _protected_lines(lines) == [True, True, False, True, False]


def test_prose_references_are_found():
    """Return citation references that occur in prose"""
    matches = _live_reference_matches("See [1]_ and [2]_.")
    assert [match.group(1) for match in matches] == ["1", "2"]


def test_single_backtick_span_excludes_reference():
    """Ignore a reference inside a single-backtick code span"""
    assert _live_reference_matches("Use `[1]_` to cite.") == []


def test_rst_literal_excludes_reference():
    """Ignore a reference inside a double-backtick RST literal"""
    assert _live_reference_matches("Use ``[1]_`` to cite.") == []


def test_inline_code_excludes_only_enclosed_reference():
    """Keep a neighbouring prose reference outside the protected span"""
    matches = _live_reference_matches("Show `[1]_`, then cite [2]_.")
    assert [match.group(1) for match in matches] == ["2"]


def test_unpaired_backtick_preserves_reference():
    """Treat a reference after an unmatched backtick as prose"""
    matches = _live_reference_matches("An unmatched ` precedes [1]_.")
    assert [match.group(1) for match in matches] == ["1"]


@pytest.mark.parametrize("parser", _PARSERS)
def test_fenced_definition_remains_literal(parser: str):
    """Preserve a fenced definition while converting a prose definition"""
    source = (
        "Citation syntax:\n\n```\n.. [1] Author. Title.\n```\n\nSee [1]_.\n\n.. [1] Author. Title."
    )
    result = _normalized(source, parser)
    assert "```\n.. [1] Author. Title.\n```" in result
    assert result.count("{#cite-process-1}") == 1


@pytest.mark.parametrize("parser", _PARSERS)
def test_fenced_reference_is_excluded_from_backlink_count(parser: str):
    """
    Count only prose references when generating backlinks

    One prose reference produces a linked caret. Counting the fenced reference
    would instead produce two lettered backlinks.
    """
    source = "```\nSee [1]_.\n```\n\nSee [1]_.\n\n.. [1] Author. Title."
    result = _normalized(source, parser)
    assert "```\nSee [1]_.\n```" in result
    assert ".gd-linkback-caret" in result
    assert ".gd-linkback-letter" not in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_rst_literal_reference_is_excluded_from_backlink_count(parser: str):
    """Exclude an RST literal from backlink generation"""
    source = "Cite with ``[1]_``.\n\nSee [1]_.\n\n.. [1] Author. Title."
    result = _normalized(source, parser)
    assert "``[1]_``" in result
    assert ".gd-linkback-letter" not in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_doctest_prompt_keeps_its_reference_literal(parser: str):
    """Preserve citation syntax in an unfenced doctest prompt"""
    source = ">>> cite('[1]_')\n\n.. [1] Author. Title."
    result = _normalized(source, parser)
    assert ">>> cite('[1]_')" in result
    assert result.endswith("1. [Author. Title.]{#cite-process-1}")


@pytest.mark.parametrize("parser", _PARSERS)
def test_fenced_citation_example_is_unchanged(parser: str):
    """Return a fenced citation example unchanged"""
    source = "Citation syntax:\n\n```\n.. [1] Author. Title.\n\nSee [1]_.\n```"
    assert _normalized(source, parser) == source


@pytest.mark.parametrize("parser", _PARSERS)
def test_fenced_block_after_citation_remains_literal(parser: str):
    """Keep a following fenced block outside the converted citation body"""
    source = ".. [1] Author. Title.\n\n```\n   indented code\n```"
    result = _normalized(source, parser)
    assert result == "1. [Author. Title.]{#cite-process-1}\n\n```\n   indented code\n```"


def test_tilde_section_underline_is_not_a_fence():
    """Keep a tilde RST section underline in prose"""
    lines = ["Details", "~~~~~~~", "", "See [1]_ here."]
    assert _protected_lines(lines) == [False, False, False, False]


def test_backtick_section_underline_is_not_a_fence():
    """Keep a backtick RST section underline in prose"""
    lines = ["Details", "```````", "", "See [1]_ here."]
    assert _protected_lines(lines) == [False, False, False, False]


def test_info_string_opens_fence_after_short_text():
    """Open a fence with an info string after shorter prose"""
    lines = ["Hi", "```python", "code", "```", "after"]
    assert _protected_lines(lines) == [False, True, True, True, False]


@pytest.mark.parametrize("parser", _PARSERS)
def test_tilde_section_underline_allows_later_conversion(parser: str):
    """Continue citation conversion after a tilde RST section underline"""
    source = "Details\n~~~~~~~\n\nSee [1]_ here.\n\n.. [1] Smith."
    result = _normalized(source, parser)
    assert "[^1^](#cite-process-1)" in result
    assert "{#cite-process-1}" in result


@pytest.mark.parametrize("parser", _PARSERS)
def test_backtick_section_underline_allows_later_conversion(parser: str):
    """Continue citation conversion after a backtick RST section underline"""
    source = "Details\n```````\n\nSee [1]_ here.\n\n.. [1] Smith."
    result = _normalized(source, parser)
    assert "[^1^](#cite-process-1)" in result
    assert "{#cite-process-1}" in result


def test_leading_inline_code_span_does_not_open_fence():
    """Do not interpret a leading inline code span as a fence"""
    lines = ["```yaml``` is an inline span.", "See [1]_ here."]
    assert _protected_lines(lines) == [False, False]


@pytest.mark.parametrize("parser", _PARSERS)
def test_leading_inline_code_span_allows_later_conversion(parser: str):
    """Continue citation conversion after a leading inline code span"""
    source = "```yaml``` is an inline span.\n\nSee [1]_ here.\n\n.. [1] Smith."
    result = _normalized(source, parser)
    assert "[^1^](#cite-process-1)" in result
    assert "{#cite-process-1}" in result
