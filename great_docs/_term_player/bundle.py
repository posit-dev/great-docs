"""Bundles: a rendered recording in one file (`NAME.termshow.json`).

A bundle is a version 2 manifest with everything the player needs inside it,
so embedding a recording takes one URL instead of a render directory. It
differs from the `manifest.json` that `termshow render` writes in two ways:

- keyframes have no `file` member, since there are no SVG files with it
- a `transcript` member holds the recording's text as Markdown, which the
  `<termshow-player>` element and the Quarto shortcode put after the player
  for screen readers
"""

from __future__ import annotations

from .manifest import Manifest, generate_manifest
from .parser import Recording
from .script import Script, apply_script
from .transcript import transcript_markdown

BUNDLE_SUFFIX = ".termshow.json"


def make_bundle(recording: Recording, script: Script | None = None) -> tuple[Manifest, str]:
    """Render a recording as a bundle.

    Parameters
    ----------
    recording
        The recording, on its own timeline (the script isn't applied yet).
    script
        A script to apply: its cuts, speed changes, theme, and overlays.

    Returns
    -------
    tuple[Manifest, str]
        The manifest, and the bundle's JSON text. Like a manifest, the text is
        safe to embed in an HTML `<script>` element.
    """
    played = apply_script(recording, script) if script is not None else recording
    manifest = generate_manifest(played, script)
    text = manifest.to_json(files=False, transcript=transcript_markdown(recording, script))
    return manifest, text
