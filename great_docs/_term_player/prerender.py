"""Recording loading and pre-rendering for the Termshow player"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from .manifest import Manifest, generate_manifest
from .parser import Recording, parse_asciicast, parse_termshow
from .script import Script, apply_script, load_script
from .transcript import write_transcript

# Project subdirectory containing all rendered recordings
OUTPUT_ROOT = "termshow"


@dataclass(frozen=True)
class Prerendered:
    """Summary of rendered recordings"""

    count: int
    """Number of recordings rendered"""

    manifest_bytes: int
    """Total size of their manifests, which is what the player loads"""


def load_recording(
    source: Path, script: Path | None = None, *, use_script: bool = True
) -> tuple[Recording, Script | None]:
    """
    Read a recording and its script

    Parameters
    ----------
    source
        A `.cast` asciicast file or a `.termshow` recording.
    script
        Explicit script path. If omitted, the companion `.termshow.yml` path is
        used: `demo.termshow.yml` for either `demo.cast` or `demo.termshow`.
        A script is loaded only if the selected path exists.
    use_script
        Whether to load a script at all.

    Returns
    -------
    :
        The original recording, without script edits, and the loaded script. The
        script is `None` when loading is disabled or the selected path does not exist.

    Raises
    ------
    OSError
        If a file cannot be read.
    ValueError
        If the recording is not valid JSON lines, or the script is not valid YAML
        or names an unknown theme.
    """
    if source.suffix == ".cast":
        recording = parse_asciicast(source)
    else:
        recording = parse_termshow(source)
    if not use_script:
        return recording, None
    script_path = script or source.with_suffix(".termshow.yml")
    return recording, load_script(script_path) if script_path.exists() else None


def output_dir(recording: Path, source_dir: Path, project_dir: Path) -> Path:
    """
    Derive a rendered recording's output directory

    The output is `termshow/<relative path without suffix>/` inside `project_dir`.
    Paths are relative to `source_dir`, so recordings with the same name in different
    directories do not overwrite each other. The `termshow` shortcode's `file` uses
    that relative path without the suffix. The shortcode falls back to
    `termshow/<name>/` for a recording rendered from its own directory.

    Parameters
    ----------
    recording
        The recording file, inside `source_dir`.
    source_dir
        The directory that shortcode paths are relative to.
    project_dir
        The Quarto project directory to render into.

    Returns
    -------
    :
        The output directory.
    """
    return project_dir / OUTPUT_ROOT / recording.relative_to(source_dir).with_suffix("")


def render_recording(
    recording: Recording,
    script: Script | None,
    output_dir: Path,
    *,
    keyframe_interval: float = 2.0,
) -> Manifest:
    """
    Render a recording's SVG keyframes, `manifest.json` and transcript

    Parameters
    ----------
    recording
        The recording as written.
    script
        Script containing the cuts, speed changes, chapters and annotations to apply.
    output_dir
        The directory to write into.
    keyframe_interval
        Seconds between keyframes.

    Returns
    -------
    :
        The manifest written.

    Raises
    ------
    OSError
        If a file cannot be written.
    """
    played = apply_script(recording, script) if script is not None else recording
    manifest = generate_manifest(
        played, script, output_dir=output_dir, keyframe_interval=keyframe_interval
    )
    # Use the original recording so the transcript retains all its text; cuts
    # shorten playback time without removing text from the transcript.
    _ = write_transcript(recording, script, output_dir)
    return manifest


def find_recordings(source_dir: Path) -> list[Path]:
    """
    Find the `.termshow` recordings in a documentation source directory

    Parameters
    ----------
    source_dir
        The directory to search.

    Returns
    -------
    :
        The recordings, leaving out those in the build and site directories.
    """
    return [
        path
        for path in source_dir.rglob("*.termshow")
        if path.relative_to(source_dir).parts[0] not in ("great-docs", "_site", "_quarto")
    ]


def render_recordings(
    recordings: Iterable[Path],
    source_dir: Path,
    project_dir: Path,
    *,
    report: Callable[[str], None],
) -> Prerendered:
    """
    Render recordings with their companion scripts into a Quarto project

    An `OSError` or `ValueError` while loading or rendering a recording is reported,
    and processing continues with the next recording. Other exceptions propagate.

    Parameters
    ----------
    recordings
        The recording files, inside `source_dir`.
    source_dir
        The directory that shortcode paths are relative to.
    project_dir
        The Quarto project directory to render into.
    report
        Callback that receives one warning line per failed recording.

    Returns
    -------
    :
        The number of recordings rendered and their total manifest size in bytes.
    """
    count = 0
    manifest_bytes = 0
    for path in recordings:
        try:
            recording, script = load_recording(path)
            manifest = render_recording(
                recording, script, output_dir(path, source_dir, project_dir)
            )
        except (OSError, ValueError) as e:
            name = path.relative_to(source_dir).as_posix()
            report(f"termshow: failed to render {name}: {e}")
            continue
        count += 1
        manifest_bytes += manifest.stats.manifest_bytes
    return Prerendered(count, manifest_bytes)
