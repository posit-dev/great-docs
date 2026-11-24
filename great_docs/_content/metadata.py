"""
Meta descriptions, the page summaries that search engines show in results

Quarto writes `<meta name="description">` from a page's `description-meta`,
or from its `description` when `description-meta` is unset. A site-wide
`description-meta` would therefore override every page's `description`, so
each page gets its own. Reference pages and the homepage take theirs from the
docstring or README they are written from. Every other page gets one before
rendering: its first paragraph when the page opens with one, otherwise the
site's default description.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from multimark import Node, NodeType, parse

if TYPE_CHECKING:
    from .._yaml import YamlMapping
    from ..config import Config

MAX_LENGTH = 155
"""Longest description in characters, about what search results show"""

SHORT_PARAGRAPH = 30
"""Length in characters at or below which a first paragraph is too short to use"""

PAGE_KEYS = ("description", "description-meta")
"""Front matter keys from which Quarto writes a page's description"""

_CODE_SPAN = r"(?<!`)(?P<ticks>`+)(?!`)[\s\S]*?(?<!`)(?P=ticks)(?!`)"
_LINK_TARGET = r"\]\([^)]*\)"
_SPAN_LABEL = r"(?:\\.|[^\[\]\\]|\[(?:\\.|[^\[\]\\])*\])*"
_PANDOC_INLINE = re.compile(
    r"\\."
    r"|\[\]\(`(?P<short>~?)(?P<target>[^`\n]+)`\)"
    rf"|(?P<code>{_CODE_SPAN})(?:\{{[^}}\n]*\}})?"
    rf"|{_LINK_TARGET}"
    rf"|\[(?P<span>{_SPAN_LABEL})\]\{{[^}}\n]*\}}"
)

# A Pandoc citation key, `@key` or `@{key}`, optionally with the `-` that suppresses the author
_CITATION_KEY = r"-?@(?:\{[^{}]+\}|\w(?:[\w:.#$%&+?<>~/-]*\w)?)"
# Code spans, escaped characters and link targets match first so that an `@` inside them is
# never a citation. An `@` after a word character or a `/` belongs to an address or a URL.
_CITATIONS = re.compile(
    rf"(?:{_CODE_SPAN}|\\.|{_LINK_TARGET})"
    rf"|(?P<bracketed>\s*\[[^\[\]]*(?<![\w\\/]){_CITATION_KEY}[^\[\]]*\](?![(\[{{]))"
    rf"|(?P<in_text>(?<![\w\\/]){_CITATION_KEY})"
)
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]$@~^]|&(?=[#\w]+;))")

_HEADING = re.compile(r"#{1,6}(\s|$)")
_SETEXT_UNDERLINE = re.compile(r"(=+|-+)\s*")
_LIST_ITEM = re.compile(r"([-*+]|\d+[.)])\s")
_TABLE = re.compile(r"(\||\+[-=]+\+)")
_SHORTCODE = re.compile(r"\{\{<.*>\}\}\s*")


@dataclass(frozen=True)
class FirstParagraph:
    """
    The opening paragraph of a page, or the reason the page has none

    Exactly one of the fields is set.
    """

    text: str | None = None
    """The paragraph as plain text, truncated to `MAX_LENGTH` characters"""

    fallback: str | None = None
    """Why the page falls back to the default description, worded to follow `The page`"""


def plain_text(markdown: str) -> str | None:
    """
    Convert Markdown to plain text for a page description

    Keep the visible text of links, spans and code, using the short name for
    interlinks marked with `~`. Omit images and bracketed citations. Remove
    literal angle brackets because Quarto emits them directly in the meta
    tag. Truncate the result to `MAX_LENGTH` characters at a word boundary.

    Parameters
    ----------
    markdown
        One paragraph or line of Markdown.

    Returns
    -------
    :
        The text, or `None` when nothing is left.
    """

    def replace_inline(match: re.Match[str]) -> str:
        if target := match["target"]:
            name = target.rsplit(".", 1)[-1] if match["short"] else target
            return f"`{name}`"
        if match["code"] is not None:
            return match["code"]
        if (span := match["span"]) is not None:
            return _PANDOC_INLINE.sub(replace_inline, span)
        return match[0]

    markdown = _CITATIONS.sub(lambda m: "" if m["bracketed"] else m[0], markdown)
    document = parse(_PANDOC_INLINE.sub(replace_inline, markdown))
    images = [
        node for event, node in document.walk() if event == "enter" and node.type == NodeType.IMAGE
    ]
    if images:
        # Keep the omitted nodes in a tree so multimark frees their native memory.
        omitted = parse("")
        paragraph = Node.new(NodeType.PARAGRAPH)
        omitted.append_child(paragraph)
        for image in images:
            paragraph.append_child(image)

    text = document.render_plaintext()
    text = " ".join(text.replace("<", "").replace(">", "").split())
    if len(text) > MAX_LENGTH:
        text = text[: MAX_LENGTH - 3].rsplit(" ", 1)[0] + "..."
    return text or None


def as_metadata(text: str) -> str:
    """
    Escape plain text for a `description-meta` value

    Quarto parses metadata values as Markdown. Escape characters that could
    start formatting, math, a citation or an HTML entity inside the tag.

    Parameters
    ----------
    text
        Plain text, as `plain_text` returns it.

    Returns
    -------
    :
        Markdown that Quarto renders back to `text`.
    """
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def metadata_value(markdown: str | None) -> str | None:
    """
    Convert inline Markdown into a `description-meta` value

    Parameters
    ----------
    markdown
        One paragraph or line of Markdown.

    Returns
    -------
    :
        The escaped plain text, or `None` when there is no text.
    """
    text = plain_text(markdown) if markdown else None
    return as_metadata(text) if text else None


def first_paragraph(body: str, *, citations: bool = False) -> FirstParagraph:
    """
    Find the paragraph a page opens with

    Skip blank lines, headings and HTML comments, then judge the first block.
    A plain paragraph longer than 30 characters is the description, unless
    citations resolve on the page and the paragraph cites a reference in its
    text, as in `@key argues`: before rendering, such a citation has no author
    name to show. Any other block means the page has no opening paragraph, and
    nothing after it is considered.

    Parameters
    ----------
    body
        The page body, without front matter.
    citations
        Whether Quarto resolves `@key` as a citation on the page, as
        `resolves_citations` reports. Without a bibliography, Quarto shows
        `@key` as written.

    Returns
    -------
    :
        The paragraph's plain text, or the reason for falling back.
    """
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or _HEADING.match(line):
            i += 1
            continue
        if line.startswith("<!--"):
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
            i += 1
            continue

        block: list[str] = []
        while i < len(lines) and lines[i].strip():
            block.append(lines[i])
            i += 1
        if len(block) == 2 and _SETEXT_UNDERLINE.fullmatch(block[1].strip()):
            continue

        if reason := _non_paragraph(block[0]):
            return FirstParagraph(fallback=f"starts with {reason}")
        paragraph = " ".join(block)
        if citations and any(m.group("in_text") for m in _CITATIONS.finditer(paragraph)):
            return FirstParagraph(
                fallback="opens with a paragraph that cites a reference in its text"
            )
        text = plain_text(paragraph)
        if text is None or len(text) <= SHORT_PARAGRAPH:
            return FirstParagraph(fallback="opens with a paragraph of 30 characters or fewer")
        return FirstParagraph(text=text)

    return FirstParagraph(fallback="has no content")


def _non_paragraph(line: str) -> str | None:
    """
    Name the kind of block that `line` opens, unless it opens a paragraph

    Parameters
    ----------
    line
        The first line of a block.

    Returns
    -------
    :
        A phrase such as "a code block", or `None` for a paragraph.
    """
    if line.startswith(("    ", "\t")):
        return "a code block"
    stripped = line.strip()
    if stripped.startswith(("```", "~~~")):
        return "a code block"
    if stripped.startswith(":::"):
        return "a callout or other fenced div"
    if stripped.startswith("!["):
        return "an image"
    if stripped.startswith("$$"):
        return "display math"
    if stripped.startswith(">"):
        return "a block quote"
    if stripped.startswith("<"):
        return "an HTML block"
    if _SHORTCODE.fullmatch(stripped):
        return "a shortcode"
    if _LIST_ITEM.match(stripped):
        return "a list"
    if _TABLE.match(stripped):
        return "a table"
    return None


def default_description(config: Config, package_description: str | None) -> str | None:
    """
    Resolve the site's default description as plain text

    Parameters
    ----------
    config
        Project configuration.
    package_description
        The package description from its metadata.

    Returns
    -------
    :
        `seo.default_description`, else the package description, or `None`
        when neither has text.
    """
    source = config.seo_default_description or package_description
    return plain_text(source) if source else None


def resolves_citations(front_matter: YamlMapping, config: Config) -> bool:
    """
    Check whether Quarto resolves `@key` citations on a page

    Parameters
    ----------
    front_matter
        The page's parsed front matter, empty when it has none.
    config
        Project configuration.

    Returns
    -------
    :
        `True` when the project or the page declares a bibliography, or the
        page lists its references inline.
    """
    return bool(config.bibliography) or any(
        key in front_matter for key in ("bibliography", "references")
    )


def page_description(
    front_matter: YamlMapping, body: str, default: str | None, *, citations: bool = False
) -> str | None:
    """
    Choose the `description-meta` value Python writes for a page

    Parameters
    ----------
    front_matter
        The page's parsed front matter, empty when it has none.
    body
        The page source after the front matter.
    default
        The site's default description as plain text.
    citations
        Whether Quarto resolves `@key` as a citation on the page.

    Returns
    -------
    :
        The escaped value, or `None` when the page sets its own description
        or there is nothing to write.
    """
    if any(key in front_matter for key in PAGE_KEYS):
        return None
    text = first_paragraph(body, citations=citations).text or default
    return as_metadata(text) if text else None
