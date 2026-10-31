"""Shared rules for published names, paths and fallback titles"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


def strip_numeric_prefix(filename: str) -> str:
    """
    Strip a numeric ordering prefix from a filename

    Handles common patterns like `00-introduction.qmd` -> `introduction.qmd`,
    `1-getting-started.qmd` -> `getting-started.qmd`, and
    `0001-overview.qmd` -> `overview.qmd`.

    Parameters
    ----------
    filename
        The filename to process.

    Returns
    -------
    str
        The filename with its numeric prefix stripped, or unchanged if it has none.
    """
    return re.sub(r"^\d+-|^\d+_", "", filename)


def published_path(relative: Path, *, strip_prefix: bool) -> Path:
    """
    Map a source path to the path it is published under

    Parameters
    ----------
    relative
        A page or directory path relative to its content root, such as a section or the
        user guide.
    strip_prefix
        Whether to strip numeric ordering prefixes from every path component. When enabled,
        `01-basics/02-setup.qmd` publishes as `basics/setup.qmd`.

    Returns
    -------
    :
        The published path, relative to the published root of the content.
    """
    if not strip_prefix:
        return relative
    return Path(*(strip_numeric_prefix(part) for part in relative.parts))


def title_from_name(name: str) -> str:
    """
    Derive a page or directory title from its name

    Parameters
    ----------
    name
        A file stem or a directory name. A numeric ordering prefix is kept, so strip it first
        when the title should not show it.

    Returns
    -------
    :
        The name with `-` and `_` replaced by spaces, in title case: `my-cool_page` becomes
        `My Cool Page`.
    """
    return name.replace("-", " ").replace("_", " ").title()


def fix_numeric_prefix_links(content: str, directory: Path) -> str:
    """
    Strip numeric prefixes from relative Markdown links to missing `.qmd` pages

    A link whose target exists is left as written: it already names the target. This
    preserves links to blog posts such as `2024-01-welcome/index.qmd`. A link to a missing
    page, such as `11-theming.qmd`, loses the numeric prefix of every path component,
    matching the published names of prefixed pages. Absolute URLs and paths are left
    unchanged; anchors and queries are preserved.

    Parameters
    ----------
    content
        The Markdown source to rewrite.
    directory
        The directory used to resolve relative links.

    Returns
    -------
    :
        The content with numeric prefixes stripped from links to missing `.qmd` pages.
    """

    def _rewrite(m: re.Match[str]) -> str:
        path = m.group(1)
        anchor = ""
        for sep in ("#", "?"):
            idx = path.find(sep)
            if idx != -1:
                anchor = path[idx:]
                path = path[:idx]
                break
        if (directory / unquote(path)).is_file():
            return m.group(0)
        parts = path.split("/")
        clean_parts = [re.sub(r"^\d+[-_]", "", p) for p in parts]
        return "](" + "/".join(clean_parts) + anchor + ")"

    return re.sub(r"\]\((?!https?://|/)([^)]+\.qmd(?:[#?][^)]*)?)\)", _rewrite, content)


def section_slug(name: str) -> str:
    """
    Slug a configured section directory name for its published output directory

    Parameters
    ----------
    name
        A `sections[].dir`-style relative path, in POSIX form.

    Returns
    -------
    str
        The name with underscores and spaces replaced by dashes, lowercased.
    """
    return name.replace("_", "-").replace(" ", "-").lower()
