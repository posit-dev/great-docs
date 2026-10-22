"""
Script and stylesheet elements for files shipped at the site root

Every `src` and `href` is root-relative, and Quarto rewrites it relative to
each page in header includes, after-body includes and raw HTML. Quarto leaves
a bare relative path unchanged, so it would load only on pages at the site
root.
"""

from __future__ import annotations


def script_tag(name: str, *, defer: bool = False) -> str:
    """
    Build a `<script>` element that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.
    defer
        Whether the script runs after the document is parsed rather than
        blocking the parser where it appears.

    Returns
    -------
    :
        The element as one line of HTML.
    """
    attributes = " defer" if defer else ""
    return f'<script{attributes} src="/{name}"></script>'


def script_include(name: str, *, defer: bool = False) -> dict[str, str]:
    """
    Build a Quarto include entry that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.
    defer
        Whether the script runs after the document is parsed rather than
        blocking the parser where it appears.

    Returns
    -------
    :
        A text entry for `include-in-header` or `include-after-body`.
    """
    return {"text": script_tag(name, defer=defer)}


def stylesheet_include(name: str) -> dict[str, str]:
    """
    Build a Quarto include entry that loads a stylesheet from the site root

    Parameters
    ----------
    name
        The stylesheet's file name at the site root, such as `gd-lightbox.css`.

    Returns
    -------
    :
        A text entry for `include-in-header`.
    """
    return {"text": f'<link rel="stylesheet" href="/{name}">'}
