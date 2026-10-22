"""Subprocess helpers for consistent UTF-8 text-mode I/O."""

from __future__ import annotations

from typing import TypedDict


class TextModeKwargs(TypedDict):
    """Subprocess options for decoding child process output as UTF-8 text"""

    text: bool
    encoding: str
    errors: str


# Windows text-mode pipes default to the locale codec (e.g. cp1252). Quarto and
# Python pre-render scripts emit UTF-8, so parent readers must not rely on
# locale.getpreferredencoding(False).
TEXT_MODE_KWARGS: TextModeKwargs = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}
