"""GIF, MP4, and WebM export: a recording as an animated image or a video.

Each stretch of the playback timeline where nothing visible changes (the same
screen, chapter label, and annotations) becomes one still, drawn by
`snap_svg()` and rasterized like a screenshot's PNG. `ffmpeg` then joins the
stills, each shown for its stretch's length:

- a GIF keeps one image per stretch (its frames can each have their own
  delay), with a palette made from all of them
- an MP4 (H.264) or WebM (VP9) plays at a constant frame rate

The timeline is laid out on a grid of `1 / fps` seconds, so a stretch shorter
than a grid step (a fast burst of output) is skipped, as it would be in any
video at that frame rate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .manifest import Manifest
from .snap import SnapError, rasterize, snap_svg

VIDEO_FORMATS = ("gif", "mp4", "webm")
# Frames per second, by format. A GIF's delays are in hundredths of a second, so 20 fits
# exactly; video players are happiest at a common rate.
DEFAULT_FPS = {"gif": 20, "mp4": 30, "webm": 30}
# Pixels per SVG unit, by format. GIFs grow quickly with size; video compresses well.
DEFAULT_SCALE = {"gif": 1.0, "mp4": 2.0, "webm": 2.0}
# Seconds the last screen stays up at the end
DEFAULT_END_PAUSE = 2.0
# GitHub doesn't accept bigger images or videos in issues and pull requests
SIZE_WARNING_BYTES = 10 * 1024 * 1024

_INSTALL_FFMPEG = (
    "Install it (for example `brew install ffmpeg` or `apt install ffmpeg`, or see "
    "https://ffmpeg.org/download.html)"
)


class VideoError(Exception):
    """A GIF or video can't be made: a tool is missing or failed."""


@dataclass
class Still:
    """One stretch of the timeline with nothing changing, and how long it shows."""

    time: float  # the playback time it shows
    duration: float  # seconds in the output


@dataclass
class VideoResult:
    """What went into a GIF or video."""

    duration: float  # seconds
    stills: int  # stretches of the timeline, one per change on screen
    images: int  # unique images among them
    width: int  # pixels
    height: int


def video_stills(
    manifest: Manifest,
    *,
    fps: int,
    end_pause: float = DEFAULT_END_PAUSE,
    annotations: bool = True,
    max_idle: float | None = None,
) -> list[Still]:
    """Split the playback timeline into the stretches a GIF or video shows.

    Parameters
    ----------
    manifest
        A version 2 manifest from `generate_manifest()`.
    fps
        Frames per second: stretches start and end on a grid of `1 / fps` seconds.
    end_pause
        Seconds to add to the last stretch.
    annotations
        Start a new stretch where an annotation shows or hides.
    max_idle
        The longest any stretch can be (before `end_pause` is added), in seconds, so long
        pauses play faster. `None` keeps them.

    Returns
    -------
    list[Still]
        The stretches in order; none is shorter than `1 / fps`.
    """
    if fps <= 0:
        raise ValueError("fps must be more than 0")
    end = manifest.duration
    times = {0.0}
    times.update(kf.time for kf in manifest.keyframes if kf.frame is not None)
    times.update(ch.time for ch in manifest.chapters)
    if annotations:
        for ann in manifest.annotations:
            times.update((ann.time, ann.time + ann.duration))
    starts = sorted({round(t, 6) for t in times if 0 <= t <= end})

    # Lengths on the playback timeline, with long ones capped
    spans: list[tuple[float, float]] = []
    for start, stop in zip(starts, starts[1:] + [end]):
        length = stop - start
        if max_idle is not None:
            length = min(length, max_idle)
        spans.append((start, length))
    # The last screen shows for at least one frame, even when it comes at the very end
    time, length = spans[-1]
    spans[-1] = (time, max(length, 1 / fps) + max(0.0, end_pause))

    # Lay the output timeline on the frame grid, rounding where each stretch starts (not its
    # length) so the rounding doesn't add up
    stills: list[Still] = []
    elapsed = 0.0
    step = 0
    for time, length in spans:
        elapsed += length
        next_step = round(elapsed * fps)
        if next_step > step:
            stills.append(Still(time, (next_step - step) / fps))
            step = next_step
    return stills


def find_ffmpeg() -> str | None:
    """The path of `ffmpeg`, if it's installed."""
    return shutil.which("ffmpeg")


def export_video(
    manifest: Manifest,
    output: str | Path,
    fmt: str,
    *,
    dark: bool = False,
    fps: int | None = None,
    scale: float | None = None,
    loop: bool = True,
    end_pause: float = DEFAULT_END_PAUSE,
    annotations: bool = True,
    max_idle: float | None = None,
) -> VideoResult:
    """Write a rendered recording as a GIF, MP4, or WebM file.

    Parameters
    ----------
    manifest
        A version 2 manifest from `generate_manifest()`.
    output
        The file to write.
    fmt
        `"gif"`, `"mp4"`, or `"webm"`.
    dark
        Draw the dark side of a light/dark theme pair.
    fps
        Frames per second (default: `DEFAULT_FPS` for the format).
    scale
        Pixels per SVG unit (default: `DEFAULT_SCALE` for the format).
    loop
        Make a GIF repeat forever. Videos loop, or not, in their player.
    end_pause
        Seconds to hold the last screen.
    annotations
        Draw the script's annotations.
    max_idle
        Shorten pauses longer than this many seconds to this length.

    Returns
    -------
    VideoResult
        The output's length, size in pixels, and how many images went into it.

    Raises
    ------
    VideoError
        If `ffmpeg` or a rasterizer isn't installed, or one of them fails.
    ValueError
        If the format is unknown or the manifest isn't version 2.
    """
    if fmt not in VIDEO_FORMATS:
        raise ValueError(f"unknown format {fmt!r}: use one of {', '.join(VIDEO_FORMATS)}")
    if manifest.screen is None or not manifest.frames:
        raise ValueError("GIF and video export need a version 2 manifest")
    fps = fps or DEFAULT_FPS[fmt]
    scale = scale or DEFAULT_SCALE[fmt]
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise VideoError(f"{fmt.upper()} export needs ffmpeg. {_INSTALL_FFMPEG}")

    stills = video_stills(
        manifest, fps=fps, end_pause=end_pause, annotations=annotations, max_idle=max_idle
    )
    # Every frame is drawn at the size of the largest screen
    cells = (
        max(fr.size[0] if fr.size else manifest.cols for fr in manifest.frames),
        max(len(fr.lines) for fr in manifest.frames),
    )
    kept: list[Still] = []
    svgs: list[str] = []
    for still in stills:
        svg = snap_svg(manifest, still.time, dark=dark, annotations=annotations, cells=cells)
        if svgs and svg == svgs[-1]:
            # Nothing visible changed (a chapter starts, but there's no title bar to show it)
            kept[-1].duration += still.duration
        else:
            kept.append(still)
            svgs.append(svg)
    stills = kept
    unique = list(dict.fromkeys(svgs))
    side = manifest.dark if dark else None
    bg = side.bg if side else manifest.screen.bg

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        images = [work / f"{n:05d}.png" for n in range(len(unique))]

        def draw(n: int) -> None:
            rasterize(unique[n], images[n], scale=scale, background=bg)

        try:
            with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
                list(pool.map(draw, range(len(unique))))
        except SnapError as e:
            raise VideoError(str(e).replace("PNG output", f"{fmt.upper()} export")) from e

        index = {svg: n for n, svg in enumerate(unique)}
        listing = ["ffconcat version 1.0"]
        for still, svg in zip(stills, svgs):
            listing += [f"file '{images[index[svg]].name}'", f"duration {still.duration:.6f}"]
        # The concat demuxer only applies the last duration when the file is listed again
        listing.append(f"file '{images[index[svgs[-1]]].name}'")
        (work / "frames.txt").write_text("\n".join(listing) + "\n", encoding="utf-8")

        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        argv += ["-f", "concat", "-safe", "0", "-i", str(work / "frames.txt")]
        argv += _encoding_args(fmt, fps, loop, bg)
        if fmt != "gif":
            # The listed-again file would otherwise be held as long as the one before it. (A
            # GIF gets it as a last frame of a few hundredths of a second instead, which keeps
            # the one before it on screen for its whole duration.)
            argv += ["-t", f"{sum(s.duration for s in stills):.6f}"]
        argv.append(str(out.resolve()))
        result = subprocess.run(argv, capture_output=True, text=True, cwd=work)
        if result.returncode != 0:
            message = result.stderr.strip() or f"exit status {result.returncode}"
            raise VideoError(f"ffmpeg couldn't make the {fmt.upper()}: {message}")
        width, height = _png_size(images[0])

    if fmt != "gif":
        width, height = width + width % 2, height + height % 2
    return VideoResult(
        duration=sum(s.duration for s in stills),
        stills=len(stills),
        images=len(unique),
        width=width,
        height=height,
    )


def _encoding_args(fmt: str, fps: int, loop: bool, bg: str) -> list[str]:
    """ffmpeg's arguments after the input, for each format."""
    if fmt == "gif":
        # One palette for the whole GIF, from all of its images; only the changed part of each
        # frame is stored, and each still is one frame with its own delay.
        palette = (
            "split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
            "[b][p]paletteuse=dither=none:diff_mode=rectangle"
        )
        return ["-filter_complex", palette, "-loop", "0" if loop else "-1"]
    # H.264 and VP9 in 4:2:0 need an even width and height
    pad = f"fps={fps},pad=ceil(iw/2)*2:ceil(ih/2)*2:color={bg}"
    common = ["-vf", pad, "-pix_fmt", "yuv420p"]
    if fmt == "mp4":
        return common + [
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-tune",
            "stillimage",
            "-movflags",
            "+faststart",
        ]
    return common + ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1"]


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[16:24]
    return int.from_bytes(data[:4], "big"), int.from_bytes(data[4:], "big")
