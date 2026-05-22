"""Importers for asciicast and VHS tape formats."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .parser import Recording, parse_asciicast


def import_asciicast(source: str | Path, output: str | Path) -> Recording:
    """Import an asciicast v2/v3 file and save as .termshow.

    Parameters
    ----------
    source
        Path to .cast file.
    output
        Path to write .termshow file.

    Returns
    -------
    Recording
        The parsed recording.
    """
    recording = parse_asciicast(source)

    # Convert to termshow format and write
    _write_termshow(recording, output)
    return recording


def import_tape(source: str | Path, output: str | Path) -> Recording:
    """Import a VHS .tape file and convert to .termshow.

    Parses the VHS tape DSL and generates synthetic terminal events.
    This produces a scripted recording rather than a real capture.

    Parameters
    ----------
    source
        Path to .tape file.
    output
        Path to write .termshow file.

    Returns
    -------
    Recording
        The generated recording.
    """
    path = Path(source)
    text = path.read_text(encoding="utf-8")

    recording = _parse_tape(text)
    _write_termshow(recording, output)
    return recording


