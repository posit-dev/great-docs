"""Subprocess helpers for consistent UTF-8 text-mode I/O."""

from __future__ import annotations

# Windows text-mode pipes default to the locale codec (e.g. cp1252). Quarto and
# Python post-render hooks emit UTF-8, so parent readers must not rely on
# locale.getpreferredencoding(False).
TEXT_MODE_KWARGS: dict[str, str | bool] = {
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
}
