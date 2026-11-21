"""
The summary of a docstring: its first paragraph

The summary runs from the first line to the first blank line, so it may wrap over
several lines. A line that opens a code fence, a fenced div or display maths also ends
it, as such a block is never part of the summary.
"""

from __future__ import annotations

import re

__all__ = ("summary_lines", "summary_text")

_BLOCK_START = re.compile(r"\s*(```|~~~|:::|\$\$\s*$)")


def summary_lines(text: str) -> list[str]:
    """
    Read the lines of the paragraph that a docstring's text opens with

    Parameters
    ----------
    text
        The leading text of a docstring, without its indentation.

    Returns
    -------
    :
        The lines as written, or an empty list when the text starts with a blank line or
        opens a code fence, fenced div or display maths.
    """
    lines: list[str] = []
    for line in text.splitlines():
        if not line.strip() or _BLOCK_START.match(line):
            break
        lines.append(line)
    return lines


def summary_text(text: str) -> str:
    """
    Join the summary of a docstring's text into one line

    Parameters
    ----------
    text
        The leading text of a docstring, without its indentation.

    Returns
    -------
    :
        The summary's lines, stripped and joined with spaces, or an empty string when
        there is no summary.
    """
    return " ".join(line.strip() for line in summary_lines(text))
