"""Derive published names from source names the same way for every caller"""

from __future__ import annotations

import re


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


def fix_numeric_prefix_links(content: str) -> str:
    """
    Rewrite relative Markdown links to `.qmd` files, stripping numeric prefixes

    When numeric prefixes are stripped from filenames during the copy step
    (e.g. `11-theming.qmd` -> `theming.qmd`), cross-references between pages
    that use the original prefixed names would otherwise break. Only relative
    links to `.qmd` files are affected; absolute URLs and anchors are left
    untouched.

    Parameters
    ----------
    content
        The Markdown source to rewrite.

    Returns
    -------
    str
        The content with numeric prefixes stripped from `.qmd` link targets.
    """

    def _rewrite(m: re.Match) -> str:
        path = m.group(1)
        anchor = ""
        for sep in ("#", "?"):
            idx = path.find(sep)
            if idx != -1:
                anchor = path[idx:]
                path = path[:idx]
                break
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
