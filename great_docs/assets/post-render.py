from __future__ import annotations

import os
import sys


def _configure_stdio_for_unicode() -> None:
    """Use UTF-8 for console output when the platform default is narrow (e.g. cp1252)."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_stdio_for_unicode()

# Skip post-render processing during freeze-only renders
if os.environ.get("GD_FREEZE_ONLY"):
    print("Skipping post-render (freeze-only mode)")
    raise SystemExit(0)
