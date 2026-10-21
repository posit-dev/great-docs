"""
The `<head>` of built pages: front matter tags, header includes and raw pages

Pages that Quarto renders list extra `<head>` elements under `HEAD_TAGS` in
their front matter. Site-wide header includes apply to every rendered page.
Raw custom pages bypass Quarto, so tags are added to them directly.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING, Any

from yaml12 import format_yaml

from .._yaml import YamlMapping, locate_front_matter

if TYPE_CHECKING:
    from pathlib import Path

    from .._yaml import YamlValue

HEAD_TAGS = "gd-head-tags"
"""Front matter key for tags that the metadata partial adds to a page's `<head>`"""

_BACKTICKS = re.compile("`+")


def meta_element(name: str, content: str) -> str:
    """
    Build a `<meta>` element with an escaped `content` value

    Parameters
    ----------
    name
        The `name` attribute, used as given.
    content
        The `content` attribute, escaped for a quoted attribute value.

    Returns
    -------
    :
        The element as one line of HTML.
    """
    return f'<meta name="{name}" content="{html.escape(content, quote=True)}">'


def add_tags(content: str, tags: list[str]) -> str:
    """
    Add elements to the `<head>` of a page that Quarto renders

    Store each element as inline raw HTML in the page's `HEAD_TAGS` list,
    after any elements already there. Every other front matter line,
    comments included, is kept as it is.

    Parameters
    ----------
    content
        The page source.
    tags
        The elements as single-line HTML markup. Elements already in the
        list are skipped.

    Returns
    -------
    :
        The page with the elements added, creating front matter if needed,
        or `content` unchanged when there is nothing new to add.

    Raises
    ------
    ValueError
        If the existing `HEAD_TAGS` value is not a list, or new elements
        cannot be merged into a list in the generated YAML style.
    """
    front_matter = locate_front_matter(content)
    existing = front_matter.mapping.get(HEAD_TAGS) if front_matter is not None else None
    if existing is not None and not isinstance(existing, list):
        raise ValueError(f"`{HEAD_TAGS}` in the front matter is not a list")
    existing_tags = existing or []
    new_tags = list(dict.fromkeys(tag for tag in map(raw_inline, tags) if tag not in existing_tags))
    if not new_tags:
        return content
    if front_matter is None or existing is None:
        block = format_yaml({HEAD_TAGS: new_tags}).rstrip()
        if front_matter is None:
            return f"---\n{block}\n---\n\n{content}"
        return f"---\n{block}\n{content[4:]}"

    # Match the generated block exactly to preserve surrounding YAML and comments.
    old_block = "\n" + format_yaml({HEAD_TAGS: existing}).rstrip() + "\n"
    block_offset = content.find(old_block, 3, front_matter.end)
    if block_offset == -1:
        raise ValueError(f"Cannot add to a hand-written `{HEAD_TAGS}` in the front matter")
    new_block = "\n" + format_yaml({HEAD_TAGS: [*existing_tags, *new_tags]}).rstrip() + "\n"
    return content[:block_offset] + new_block + content[block_offset + len(old_block) :]


def raw_inline(markup: str) -> str:
    """
    Wrap markup as an inline raw HTML span for Quarto Markdown

    Parameters
    ----------
    markup
        HTML that starts with `<` and ends with `>`.

    Returns
    -------
    :
        The markup in a backtick fence one longer than its longest run of
        backticks, so the markup needs no escaping.
    """
    fence = "`" * (max(map(len, _BACKTICKS.findall(markup)), default=0) + 1)
    return f"{fence}{markup}{fence}{{=html}}"


def search_includes(
    entries: list[YamlValue], base_dir: Path, pattern: re.Pattern[str]
) -> re.Match[str] | None:
    """
    Find the first match for `pattern` in `include-in-header` entries

    Parameters
    ----------
    entries
        Header entries containing file paths, inline `text`, or a `file` path.
    base_dir
        Base directory for relative header file paths.
    pattern
        The markup to look for.

    Returns
    -------
    :
        The match in an inline entry or a readable header file, or `None`.
    """
    for entry in entries:
        if isinstance(entry, dict):
            entry = YamlMapping(entry)
            text, path = entry.get("text"), entry.get("file")
        else:
            text, path = None, entry
        if text is None and path is not None:
            try:
                text = (base_dir / str(path)).read_text(encoding="utf-8")
            except OSError:
                continue
        if isinstance(text, str) and (match := pattern.search(text)):
            return match
    return None


def site_includes(quarto_config: dict[str, Any]) -> list[YamlValue]:
    """
    List the site's `include-in-header` entries

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.

    Returns
    -------
    :
        The entries, or an empty list when the site has none.
    """
    html_format = YamlMapping(quarto_config).mapping("format").mapping("html")
    return html_format.entries("include-in-header")


def includes_match(
    quarto_config: dict[str, Any], project_dir: Path, pattern: re.Pattern[str]
) -> bool:
    """
    Check whether the site's header includes contain a match for `pattern`

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    project_dir
        Base directory for relative header file paths.
    pattern
        The markup to look for.

    Returns
    -------
    :
        `True` when an inline entry or a readable header file matches.
    """
    return search_includes(site_includes(quarto_config), project_dir, pattern) is not None


def page_includes_match(
    front_matter: YamlMapping, page_dir: Path, pattern: re.Pattern[str]
) -> bool:
    """
    Check whether a page's own header includes contain a match for `pattern`

    Parameters
    ----------
    front_matter
        The page's front matter.
    page_dir
        Base directory for the page's relative header file paths.
    pattern
        The markup to look for.

    Returns
    -------
    :
        `True` when its `include-in-header`, its `format.html` one, or its
        `header-includes` matches.
    """
    for mapping in (front_matter, front_matter.mapping("format").mapping("html")):
        if search_includes(mapping.entries("include-in-header"), page_dir, pattern):
            return True
    texts = front_matter.entries("header-includes")
    return any(isinstance(text, str) and pattern.search(text) for text in texts)


def insert(html: str, tag: str, *, unless: str) -> str:
    """
    Insert a tag at the end of a page's `<head>`

    Parameters
    ----------
    html
        The page source.
    tag
        The element to insert.
    unless
        A string whose presence in the page means the tag already exists.

    Returns
    -------
    :
        The page with the tag added, or `html` unchanged when it contains
        `unless` or has no `</head>`.
    """
    if unless in html or "</head>" not in html:
        return html
    return html.replace("</head>", f"{tag}\n</head>", 1)
