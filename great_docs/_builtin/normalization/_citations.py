"""Numbered RST citation normalisation for every docstring parser"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from great_docs.hooks import on_object_resolved

if TYPE_CHECKING:
    import griffe as gf

_RST_CITATION_MARKER_RE = re.compile(r"^([ \t]*)\.\.\s+\[(\d+)\](?:[ \t]+(.*))?$")
_RST_CITATION_REF_RE = re.compile(r"\[(\d+)\]_")
_RST_CITATION_URL_RE = re.compile(r'(?<![<"])(https?://[^\s<>"`\[\]{}]+)')
_FENCE_RE = re.compile(r"^[ \t]*(?P<marker>`{3,}|~{3,})")
_DOCTEST_PROMPT_RE = re.compile(r"^[ \t]*(?:>>>(?: |$)|\.\.\. )")
_BACKTICK_RUN_RE = re.compile(r"`+")
_URL_TAIL_PUNCTUATION = ".,;:!?"


def _closes_fence(stripped: str, marker: str) -> bool:
    """
    Return whether a line closes the current code fence

    The line must contain only the opening character and repeat it at least as
    many times as the opening delimiter.

    Parameters
    ----------
    stripped
        The candidate line with surrounding whitespace removed.
    marker
        The opening delimiter.

    Returns
    -------
    :
        True when the line ends the fence.
    """
    return len(stripped) >= len(marker) and stripped == marker[0] * len(stripped)


def _fence_marker(line: str, previous_line: str | None) -> str | None:
    """
    Return a line's opening code-fence delimiter

    A line that starts with at least three backticks or tildes opens a fence
    unless it has one of two non-fence forms. A later backtick disqualifies a
    backtick opener, preventing the leading run of an inline code span from
    becoming a fence. A bare delimiter is an RST section underline when the
    preceding non-blank line is at least as long. Without a preceding line, a
    bare delimiter opens a fence.

    Parameters
    ----------
    line
        The candidate line.
    previous_line
        The preceding source line, or `None` for the first line.

    Returns
    -------
    :
        The opening run, or `None` when the line opens no fence.
    """
    match = _FENCE_RE.match(line)
    if match is None:
        return None

    marker = match.group("marker")
    stripped = line.strip()
    remainder = stripped[len(marker) :]

    if marker[0] == "`" and "`" in remainder:
        return None

    is_underline_candidate = (
        not remainder
        and previous_line is not None
        and previous_line.strip() != ""
        and len(stripped) <= len(previous_line.strip())
    )
    if is_underline_candidate:
        return None

    return marker


def _protected_lines(lines: list[str]) -> list[bool]:
    """
    Return flags for lines whose citation syntax must remain literal

    Mark fence delimiters and their content, plus doctest prompt and
    continuation lines outside a fence.

    Parameters
    ----------
    lines
        The docstring's lines.

    Returns
    -------
    :
        One flag per input line. `True` identifies literal code.
    """
    flags: list[bool] = []
    marker: str | None = None
    previous_line: str | None = None
    for line in lines:
        if marker is not None:
            flags.append(True)
            if _closes_fence(line.strip(), marker):
                marker = None
            previous_line = line
            continue

        opener = _fence_marker(line, previous_line)
        if opener is not None:
            marker = opener
            flags.append(True)
            previous_line = line
            continue

        flags.append(_DOCTEST_PROMPT_RE.match(line) is not None)
        previous_line = line
    return flags


def _inline_code_spans(line: str) -> list[tuple[int, int]]:
    """
    Return the ranges occupied by closed inline code spans

    Pair each backtick run with the next run of equal length. Stop at the first
    run without a matching closer; that run and all later runs remain unpaired.

    Parameters
    ----------
    line
        The line to scan.

    Returns
    -------
    :
        Half-open character ranges covering each span and its delimiters.
    """
    runs = list(_BACKTICK_RUN_RE.finditer(line))
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(runs):
        opener = runs[index]
        width = opener.end() - opener.start()
        for offset in range(index + 1, len(runs)):
            closer = runs[offset]
            if closer.end() - closer.start() == width:
                spans.append((opener.start(), closer.end()))
                index = offset + 1
                break
        else:
            break
    return spans


def _outside_inline_code(line: str, matches: list[re.Match[str]]) -> list[re.Match[str]]:
    """
    Select matches that begin outside inline code

    Parameters
    ----------
    line
        The line containing the matches.
    matches
        The matches to filter, in the order they appear.

    Returns
    -------
    :
        The matches whose first character lies outside every closed code span.
    """
    if not matches or "`" not in line:
        return matches

    spans = _inline_code_spans(line)
    return [
        match for match in matches if not any(start <= match.start() < end for start, end in spans)
    ]


def _live_reference_matches(line: str) -> list[re.Match[str]]:
    """
    Return citation references outside inline code

    Parameters
    ----------
    line
        The line to scan.

    Returns
    -------
    :
        The `[N]_` matches outside inline code, in the order they appear.
    """
    return _outside_inline_code(line, list(_RST_CITATION_REF_RE.finditer(line)))


def _wrap_url(match: re.Match[str]) -> str:
    """
    Wrap a detected URL while leaving trailing punctuation outside

    Remove sentence punctuation and unmatched closing parentheses from the URL
    before adding angle brackets. Check the new final character after each
    removal so endings such as `).` remain outside the link. Preserve balanced
    parentheses in URL paths.

    Parameters
    ----------
    match
        The regular expression match containing the URL.

    Returns
    -------
    :
        The angle-bracketed URL followed by any trailing punctuation.
    """
    url = match.group(1)
    trailer = ""
    while url:
        last = url[-1]
        unmatched_paren = last == ")" and url.count("(") < url.count(")")
        if last not in _URL_TAIL_PUNCTUATION and not unmatched_paren:
            break
        trailer = last + trailer
        url = url[:-1]
    return f"<{url}>{trailer}"


def _autolink_urls(text: str) -> str:
    """
    Convert bare URLs outside inline code to Markdown autolinks

    End each URL before a Markdown delimiter so generated reference markup
    cannot enter the link target. Leave URLs inside inline code unchanged.

    Parameters
    ----------
    text
        One citation-body line or a complete single-paragraph body.

    Returns
    -------
    :
        The text with each bare URL angle-bracketed.
    """
    matches = _outside_inline_code(text, list(_RST_CITATION_URL_RE.finditer(text)))
    if not matches:
        return text

    parts: list[str] = []
    cursor = 0
    for match in matches:
        parts.append(text[cursor : match.start()])
        parts.append(_wrap_url(match))
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


_NON_ANCHOR_CHARS_RE = re.compile(r"[^A-Za-z0-9_]+")

_CITE_REF_CLASS = ".gd-cite-ref"
_CITE_BODY_CLASS = ".gd-cite-body"
_CARET_CLASSES = ".gd-linkback-text .gd-linkback-caret"
_LETTER_CLASSES = ".gd-linkback-text .gd-linkback-letter"


@on_object_resolved(priority=20)  # pyright: ignore[reportArgumentType]
def normalize_citations(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Convert numbered RST citations and references in a resolved object

    Citations and matching `[N]_` references link in both directions.
    Conversion applies to every docstring parser.

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    :
        The resolved object with converted citations and references.
    """
    docstring = obj.docstring
    if docstring is None:
        return obj

    # TODO: Generate citation anchor stems during rendering from both the page and
    # each rendered object. A Griffe alias exposes its target's `Docstring`, so all
    # aliases mutate the same value. The first resolved path converts the citation
    # markers with its own stem; later paths reuse that markup. The links remain
    # self-consistent, but the stem names the wrong path and duplicate IDs can occur
    # when the same target appears twice on one page.
    #
    # This hook receives only object context. The renderer has both contexts and
    # must keep a separate citation namespace for every object. On a multi-object
    # page, `[1]_` in one docstring must not link to a definition in another.
    docstring.value = _convert_rst_citations(docstring.value, _anchor_slug(obj.path))
    return obj


def _anchor_slug(path: str) -> str:
    """
    Convert an object path to a citation-anchor stem

    Keep letters, digits, and underscores as written. Replace each run of other
    characters with a hyphen so paths that differ by case or separator remain
    distinct.

    Parameters
    ----------
    path
        The resolved object's dotted path.

    Returns
    -------
    :
        The path with other character runs replaced by hyphens.
    """
    return _NON_ANCHOR_CHARS_RE.sub("-", path).strip("-")


def _occurrence_label(index: int) -> str:
    """
    Return the backlink label for a zero-based reference index

    Parameters
    ----------
    index
        The reference's zero-based position among those naming one citation.

    Returns
    -------
    :
        A letter sequence running `a` to `z`, then `aa`, `ab`, and onwards.
    """
    label = ""
    position = index + 1
    while position:
        position, remainder = divmod(position - 1, 26)
        label = chr(ord("a") + remainder) + label
    return label


def _backlinks(anchor_stem: str, number: str, count: int) -> str:
    """
    Build a citation's return links

    One reference receives a linked caret. Multiple references receive an
    inert caret followed by one lettered link for each occurrence.

    Parameters
    ----------
    anchor_stem
        The stem shared by this object's anchors.
    number
        The citation's label.
    count
        The number of references that name this citation.

    Returns
    -------
    :
        Markdown ending in a space, or the empty string when nothing names it.
    """
    if not count:
        return ""

    def back(index: int, text: str, classes: str) -> str:
        anchor = f"ref-{anchor_stem}-{number}-{index + 1}"
        return f'[{text}](#{anchor}){{{classes} role="doc-backlink"}}'

    if count == 1:
        return f"{back(0, '^', _CARET_CLASSES)} "

    caret = f"[^]{{{_CARET_CLASSES}}}"
    letters = " ".join(
        back(index, _occurrence_label(index), _LETTER_CLASSES) for index in range(count)
    )
    return f"{caret} {letters} "


def _link_references(
    line: str,
    matches: list[re.Match[str]],
    anchor_stem: str,
    seen: dict[str, int],
) -> str:
    """
    Replace prose citation references with links to their definitions

    Parameters
    ----------
    line
        The line to rewrite.
    matches
        The prose references in their source order.
    anchor_stem
        The stem shared by this object's anchors.
    seen
        The number of earlier references to each label. Updated in place as
        each match is linked.

    Returns
    -------
    :
        The line with each match replaced by its link.
    """
    if not matches:
        return line

    parts: list[str] = []
    cursor = 0
    for match in matches:
        number = match.group(1)
        seen[number] = seen.get(number, 0) + 1
        anchor = f"ref-{anchor_stem}-{number}-{seen[number]}"
        parts.append(line[cursor : match.start()])
        parts.append(
            f"[^{number}^](#cite-{anchor_stem}-{number})"
            f'{{#{anchor} {_CITE_REF_CLASS} role="doc-noteref"}}'
        )
        cursor = match.end()
    parts.append(line[cursor:])
    return "".join(parts)


def _indent_width(line: str) -> int:
    """
    Count a line's leading spaces and tabs

    Parameters
    ----------
    line
        The line to measure.

    Returns
    -------
    :
        The number of leading whitespace characters.
    """
    return len(line) - len(line.lstrip(" \t"))


def _shifted(line: str, offset: int) -> str:
    """
    Shift a body line by an indentation offset

    Parameters
    ----------
    line
        The line to move.
    offset
        The number of spaces to add. A negative value removes that many leading
        whitespace characters and must not exceed the line's indentation.

    Returns
    -------
    :
        The shifted line, or an empty string for a blank line.
    """
    if not line.strip():
        return ""
    return " " * offset + line if offset > 0 else line[-offset:]


def _continuation_lines(
    lines: list[str],
    protected: list[bool],
    start: int,
    marker_width: int,
) -> tuple[list[str], int]:
    """
    Collect the lines continuing a citation body

    Stop before literal code, another definition, or the first non-blank line
    whose indentation does not exceed the marker's. Retain paragraph breaks
    within the body, but leave trailing blank lines with the following text.

    Parameters
    ----------
    lines
        The docstring's lines, with references already linked.
    protected
        One flag per line. `True` identifies literal code.
    start
        The definition marker's line index.
    marker_width
        The number of leading spaces and tabs before the marker.

    Returns
    -------
    :
        The continuation lines and the final source index consumed by the body.
    """
    collected: list[str] = []
    blanks: list[str] = []
    index = start
    while index + 1 < len(lines):
        line = lines[index + 1]
        if not line.strip():
            blanks.append(line)
            index += 1
            continue
        ends_body = (
            protected[index + 1]
            or _indent_width(line) <= marker_width
            or _RST_CITATION_MARKER_RE.match(line) is not None
        )
        if ends_body:
            break
        collected.extend(blanks)
        blanks.clear()
        collected.append(line)
        index += 1
    return collected, index - len(blanks)


def _span_definition(
    marker: str,
    anchor: str,
    backlinks: str,
    head: str,
    continuations: list[str],
) -> str:
    """
    Render a single-paragraph citation as an anchored span

    Parameters
    ----------
    marker
        The list marker, including its indentation and trailing space.
    anchor
        The citation's anchor ID.
    backlinks
        The citation's return links, or the empty string.
    head
        The body's first line, without indentation.
    continuations
        The body's remaining lines.

    Returns
    -------
    :
        The list item with its complete body inside the anchored span.
    """
    body = " ".join([head, *(line.strip() for line in continuations)]).strip()
    return f"{marker}{backlinks}[{_autolink_urls(body)}]{{#{anchor}}}"


def _block_definition(
    marker: str,
    anchor: str,
    backlinks: str,
    head: str,
    continuations: list[str],
) -> list[str]:
    """
    Render a multi-paragraph citation as an anchored fenced div

    Markdown spans cannot contain paragraph breaks. A fenced div keeps every
    paragraph within the citation anchor. Apply one indentation offset to all
    continuation lines so nested content retains its relative indentation.

    Parameters
    ----------
    marker
        The list marker, including its indentation and trailing space.
    anchor
        The citation's anchor ID.
    backlinks
        The citation's return links, or the empty string.
    head
        The body's first line, without indentation.
    continuations
        The body's remaining lines, including paragraph breaks.

    Returns
    -------
    :
        The opening fence, the body, and the closing fence.
    """
    content = " " * len(marker)
    offset = len(content) - min(_indent_width(line) for line in continuations if line.strip())
    body = [f"{content}{backlinks}{head}", *(_shifted(line, offset) for line in continuations)]
    return [
        f"{marker}::: {{#{anchor} {_CITE_BODY_CLASS}}}",
        *(_autolink_urls(line) for line in body),
        f"{content}:::",
    ]


def _convert_definitions(
    lines: list[str],
    protected: list[bool],
    counts: dict[str, int],
    anchor_stem: str,
) -> list[str]:
    """
    Convert prose citation definitions to anchored numbered list items

    A body starts after its marker and includes subsequent lines indented beyond
    the marker. Render one paragraph as an anchored span and multiple paragraphs
    as an anchored fenced div.

    Parameters
    ----------
    lines
        The docstring's lines, with references already linked.
    protected
        One flag per line. `True` identifies literal code.
    counts
        The number of prose references to each label.
    anchor_stem
        The stem shared by this object's anchors.

    Returns
    -------
    :
        The lines with every unprotected definition converted. Fenced divs add
        opening and closing lines around multi-paragraph bodies.
    """
    result: list[str] = []
    index = 0
    while index < len(lines):
        match = None if protected[index] else _RST_CITATION_MARKER_RE.match(lines[index])
        if match is None:
            result.append(lines[index])
            index += 1
            continue

        indent, number, inline_body = match.group(1), match.group(2), match.group(3)
        continuations, index = _continuation_lines(lines, protected, index, len(indent))

        # A marker can carry no text, leaving the body to start on the next line.
        head = (inline_body or "").strip()
        if not head and continuations:
            head, continuations = continuations[0].strip(), continuations[1:]

        marker = f"{indent}{number}. "
        anchor = f"cite-{anchor_stem}-{number}"
        backlinks = _backlinks(anchor_stem, number, counts.get(number, 0))
        if any(not line.strip() for line in continuations):
            result.extend(_block_definition(marker, anchor, backlinks, head, continuations))
        else:
            result.append(_span_definition(marker, anchor, backlinks, head, continuations))
        index += 1
    return result


def _convert_rst_citations(text: str, anchor_stem: str) -> str:
    """
    Convert numbered RST citations to bidirectional Markdown links

    Convert each prose definition to an anchored numbered item. Its body ends
    before literal code, another definition, or the first non-blank line whose
    indentation does not exceed the marker's. Each matching `[N]_` reference
    links to that item. The item links back with a caret for one reference or
    lettered links for several. Leave unmatched references unchanged.

    Preserve citation syntax in fenced blocks, inline code spans, and unfenced
    doctest prompts. Exclude these references from backlink counts. Return the
    original text when every definition appears in literal code.

    Autolink bare URLs in citation bodies. End each link before Markdown
    delimiters, trailing sentence punctuation, and adjacent citation-reference
    markup. Preserve balanced parentheses in URL paths. Leave URLs inside inline
    code unchanged.

    Put a single-paragraph body in a bracketed Markdown span and a
    multi-paragraph body in a fenced div. Both forms keep the complete body
    inside the anchor that Quarto uses for its hover preview. In the span form,
    authors must escape unmatched closing brackets because they can end the
    span early and detach its anchor.

    RST forbids duplicate labels. When they occur, both definitions reuse the
    same citation ID and backlinks because references are grouped by label. A
    reference inside a citation body behaves like any other prose reference.

    Parameters
    ----------
    text
        The docstring text.
    anchor_stem
        The stem shared by this object's citation and reference anchor IDs.

    Returns
    -------
    :
        The text with converted citations and bidirectional reference links.
    """
    lines = text.split("\n")
    protected = _protected_lines(lines)

    defined: set[str] = set()
    for line, guarded in zip(lines, protected):
        match = None if guarded else _RST_CITATION_MARKER_RE.match(line)
        if match is not None:
            defined.add(match.group(2))
    if not defined:
        return text

    live: list[list[re.Match[str]]] = []
    counts: dict[str, int] = {}
    for line, guarded in zip(lines, protected):
        matches = (
            []
            if guarded
            else [match for match in _live_reference_matches(line) if match.group(1) in defined]
        )
        live.append(matches)
        for match in matches:
            number = match.group(1)
            counts[number] = counts.get(number, 0) + 1

    # Match offsets refer to the original lines, so link references first. Links
    # preserve line count and indentation, which keeps `protected` aligned with
    # the rewritten lines. Convert definitions last because fenced divs change
    # the line count.
    seen: dict[str, int] = {}
    linked: list[str] = []
    for line, matches in zip(lines, live):
        linked.append(_link_references(line, matches, anchor_stem, seen))
    return "\n".join(_convert_definitions(linked, protected, counts, anchor_stem))
