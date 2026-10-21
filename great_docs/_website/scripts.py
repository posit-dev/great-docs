"""
Script elements for JavaScript files shipped at the site root

Every `src` is root-relative, and Quarto rewrites it relative to each page
in header includes, after-body includes and raw HTML. Quarto leaves a bare
relative `src` unchanged, so it would load only on pages at the site root.
"""

from __future__ import annotations


def script_tag(name: str) -> str:
    """
    Build a `<script>` element that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.

    Returns
    -------
    :
        The element as one line of HTML.
    """
    return f'<script src="/{name}"></script>'


def script_include(name: str) -> dict[str, str]:
    """
    Build a Quarto include entry that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.

    Returns
    -------
    :
        A text entry for `include-in-header` or `include-after-body`.
    """
    return {"text": script_tag(name)}
