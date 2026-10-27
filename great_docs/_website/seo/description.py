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
from html import escape, unescape
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import head

if TYPE_CHECKING:
    from ..._yaml import YamlMapping
    from ...config import Config

MAX_LENGTH = 155
"""Longest description in characters, about what search results show"""

SHORT_PARAGRAPH = 30
"""Length in characters at or below which a first paragraph is too short to use"""

PAGE_KEYS = ("description", "description-meta")
"""Front matter keys from which Quarto writes a page's description"""

_INTERLINK = re.compile(r"\[\]\(`(~?)([^`]+)`\)")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SPAN = re.compile(r"\[([^\]]*)\]\{[^}]*\}")
_CODE = re.compile(r"`+([^`]*)`+(?:\{[^}]*\})?")
_STRONG = re.compile(r"(\*\*|__)(.+?)\1")
_EMPHASIS = re.compile(r"(?<!\w)([*_])(?!\s)(.+?)(?<!\s)\1(?!\w)")
_BACKSLASH_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")

# A Pandoc citation key, `@key` or `@{key}`, optionally with the `-` that suppresses the author
_CITATION_KEY = r"-?@(?:\{[^{}]+\}|\w(?:[\w:.#$%&+?<>~/-]*\w)?)"
# Code spans, escaped characters and link targets match first so that an `@` inside them is
# never a citation. An `@` after a word character or a `/` belongs to an address or a URL.
_CITATIONS = re.compile(
    r"(?P<kept>`+[^`]*`+|\\.|\]\([^)]*\))"
    rf"|(?P<bracketed>\s*\[[^\[\]]*(?<![\w\\/]){_CITATION_KEY}[^\[\]]*\](?![(\[{{]))"
    rf"|(?P<in_text>(?<![\w\\/]){_CITATION_KEY})"
)
_SET_ASIDE = re.compile("\ue000(\\d+)\ue001")
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]$@~^])")

_HEADING = re.compile(r"#{1,6}(\s|$)")
_SETEXT_UNDERLINE = re.compile(r"(=+|-+)\s*")
_LIST_ITEM = re.compile(r"([-*+]|\d+[.)])\s")
_TABLE = re.compile(r"(\||\+[-=]+\+)")
_SHORTCODE = re.compile(r"\{\{<.*>\}\}\s*")

_HEADER_DESCRIPTION = re.compile(r"""<meta\s+name=["']?description""")
_HEADER_DESCRIPTION_CONTENT = re.compile(
    r"""<meta\s+name=["']?description["']?\s+content=(?:"([^"]*)"|'([^']*)')"""
)


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
    Reduce inline Markdown to the text a reader sees

    Keep the text of links, spans and inline code, and an interlink's target
    as it is displayed: the short name for `~`, otherwise the full name. Drop emphasis markers, images, and the characters `<` and `>`,
    which Quarto does not escape inside a meta tag. Drop bracketed citations
    such as `[@key]` with the space before them, since only rendering resolves
    them. Truncate the result to `MAX_LENGTH` characters at a word boundary.

    Parameters
    ----------
    markdown
        One paragraph or line of Markdown.

    Returns
    -------
    :
        The text, or `None` when nothing is left.
    """
    # Set escaped characters aside so that no other pattern matches them
    escaped: list[str] = []

    def set_aside(match: re.Match[str]) -> str:
        escaped.append(match.group(1))
        return f"\ue000{len(escaped) - 1}\ue001"

    text = _BACKSLASH_ESCAPE.sub(set_aside, markdown)
    text = _CITATIONS.sub(lambda m: "" if m.group("bracketed") else m.group(0), text)
    text = _INTERLINK.sub(
        lambda m: m.group(2).rsplit(".", 1)[-1] if m.group(1) else m.group(2), text
    )
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _SPAN.sub(r"\1", text)
    text = _CODE.sub(r"\1", text)
    text = _STRONG.sub(r"\2", text)
    text = _EMPHASIS.sub(r"\2", text)
    text = _SET_ASIDE.sub(lambda m: escaped[int(m.group(1))], text)
    text = " ".join(text.replace("<", "").replace(">", "").split())
    if len(text) > MAX_LENGTH:
        text = text[: MAX_LENGTH - 3].rsplit(" ", 1)[0] + "..."
    return text or None


def as_metadata(text: str) -> str:
    """
    Escape plain text for a `description-meta` value

    Quarto parses metadata values as Markdown, so an unescaped `*`, `$` or
    `@` would become emphasis, math or a citation inside the tag.

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


def applies(quarto_config: dict[str, Any], config: Config, project_dir: Path) -> bool:
    """
    Check whether pages get a generated `description-meta`

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    config
        Project configuration.
    project_dir
        Base directory for relative header file paths.

    Returns
    -------
    :
        `True` when SEO is enabled and the site's header includes declare no
        description.
    """
    return config.seo_enabled and not head.includes_match(
        quarto_config, project_dir, _HEADER_DESCRIPTION
    )


def header_description(quarto_config: dict[str, Any], project_dir: Path) -> str | None:
    """
    Read the description that the site's header includes declare

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    project_dir
        Base directory for relative header file paths.

    Returns
    -------
    :
        The description as a metadata value, or `None` when the header
        includes declare none or it has no readable `content`.
    """
    includes = head.site_includes(quarto_config)
    match = head.search_includes(includes, project_dir, _HEADER_DESCRIPTION_CONTENT)
    if match is None:
        return None
    text = unescape(match.group(1) or match.group(2) or "").strip()
    return as_metadata(text) if text else None


def add_to_raw_page(html: str, default: str | None) -> str:
    """
    Add the default description to a raw custom page

    Parameters
    ----------
    html
        The page source.
    default
        The site's default description as plain text.

    Returns
    -------
    :
        The page with the tag added, or unchanged when it has a description
        already, has no `<head>`, or `default` is `None`.
    """
    if not default:
        return html
    tag = f'<meta name="description" content="{escape(default, quote=True)}">'
    return head.insert(html, tag, unless='name="description"')
