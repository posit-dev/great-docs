"""Showreel: scripted, AI-augmented narrated demo videos for Great Docs.

See ``SHOWREEL_PLAN.md`` for the full design. This package is the P0 vertical
slice: spec parsing, narration synthesis, timeline composition, a manifest, and
a self-contained web player (title / card / image scenes + audio + captions).
"""

from __future__ import annotations

from .builder import BuildResult, build_showreel
from .embed import (
    discover_showreel_refs,
    prerender_showreels,
    render_embed_html,
)
from .manifest import Manifest, build_manifest
from .player import render_preview_html, serve_preview
from .spec import Scene, Showreel, ShowreelSpecError, load_showreel, scaffold_spec

__all__ = [
    "BuildResult",
    "Manifest",
    "Scene",
    "Showreel",
    "ShowreelSpecError",
    "build_manifest",
    "build_showreel",
    "discover_showreel_refs",
    "export_poster",
    "export_showreel",
    "load_showreel",
    "prerender_showreels",
    "render_embed_html",
    "render_preview_html",
    "scaffold_spec",
    "serve_preview",
]


def export_showreel(*args, **kwargs):
    """Export a built showreel to video (lazy import; needs nokap + ffmpeg)."""
    from .export import export_showreel as _export

    return _export(*args, **kwargs)


def export_poster(*args, **kwargs):
    """Capture a social/OG poster PNG (lazy import; needs nokap + Chrome)."""
    from .export import export_poster as _poster

    return _poster(*args, **kwargs)
