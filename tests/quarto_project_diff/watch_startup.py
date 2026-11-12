"""
Signal when a watch command has subscribed to the measured source

The recorder copies this module to a watch-only `sitecustomize.py`. Its observer
wrapper leaves event handling unchanged and reports readiness only after the
native observer has registered the directory containing the measured edit.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import watchfiles.main

SOURCE_VARIABLE = "GREAT_DOCS_QUARTO_PROJECT_DIFF_WATCH_SOURCE"
READY_VARIABLE = "GREAT_DOCS_QUARTO_PROJECT_DIFF_WATCH_READY"


def install() -> None:
    """Report observer readiness for the recorder's measured source edit"""
    source = Path(os.environ[SOURCE_VARIABLE]).resolve()
    ready = Path(os.environ[READY_VARIABLE])
    original = watchfiles.main.RustNotify

    def subscribed(paths: list[str], *args: Any, **kwargs: Any) -> Any:
        """Create the real observer before reporting a matching subscription"""
        observer = original(paths, *args, **kwargs)
        if any(source.is_relative_to(Path(path).resolve()) for path in paths):
            ready.touch()
        return observer

    watchfiles.main.RustNotify = subscribed


if SOURCE_VARIABLE in os.environ and READY_VARIABLE in os.environ:
    install()
