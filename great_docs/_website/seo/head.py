"""
Edits to the `<head>` of pages that Quarto does not render
"""

from __future__ import annotations


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
