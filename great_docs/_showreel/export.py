"""Video export: render the player headless and mux to MP4 with ffmpeg.

This is the "render once, output everywhere" keystone. Rather than a second
renderer, the export drives the *same* web player: it loads the built bundle in
headless Chrome (via nokap), steps the deterministic clock
(``window.__showreel.seek(t)``) one frame at a time, captures each frame, then
``ffmpeg`` muxes the frame sequence with the narration audio. Captions are
already burned into the frames by the player, so they need no separate track.
"""

from __future__ import annotations

import functools
import http.server
import json
import math
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from .capture import _grab  # viewport PNG capture via CDP
from .player import _QuietHandler

# JS injected before capture: enter deterministic export mode and make the
# stage full-bleed (hide controls, drop chrome) so frames are clean.
_PREP_JS = """
(() => {
  document.body.style.margin = '0';
  document.body.style.background = '#000';
  const st = document.createElement('style');
  st.textContent = '.gd-showreel{max-width:none!important;margin:0!important;' +
    'border-radius:0!important;box-shadow:none!important}' +
    '.gd-sr-controls{display:none!important}';
  document.head.appendChild(st);
  if (window.__showreel) window.__showreel.exportMode(true);
  return !!window.__showreel;
})()
"""


class ExportError(RuntimeError):
    """Raised when video export cannot proceed."""


def _aspect_size(aspect: str, height: int) -> tuple[int, int]:
    """Return an (even) width/height for a given aspect and target height."""
    ratios = {"16:9": 16 / 9, "9:16": 9 / 16, "1:1": 1.0, "4:3": 4 / 3}
    r = ratios.get(aspect, 16 / 9)
    w = int(round(height * r))
    return (w - w % 2, height - height % 2)


def _serve(directory: Path, port: int) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


_VIDEO_CODECS = {
    "mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    "webm": ["-c:v", "libvpx-vp9", "-b:v", "0", "-pix_fmt", "yuv420p"],
}
_AUDIO_CODECS = {"mp4": ["-c:a", "aac", "-b:a", "192k"], "webm": ["-c:a", "libopus", "-b:a", "160k"]}


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise ExportError("ffmpeg failed:\n" + proc.stderr.decode("utf-8", "replace")[-1800:])


def _audio_filter(clips: list[tuple[float, float]], music: dict | None, music_idx: int) -> str | None:
    """Build a filter_complex mixing delayed foreground clips (narration + SFX,
    each with its own delay and gain) + a music bed ducked under them.

    ``clips`` is a list of ``(start_seconds, gain_db)`` matching inputs 1..N.
    """
    parts = []
    n = len(clips)
    if n:
        for i, (start, gain) in enumerate(clips, start=1):
            d = max(0, int(round(start * 1000)))
            vol = f",volume={gain}dB" if gain else ""
            parts.append(f"[{i}:a]adelay={d}|{d}{vol}[c{i}]")
        labels = "".join(f"[c{i}]" for i in range(1, n + 1))
        parts.append(f"{labels}amix=inputs={n}:normalize=0[voice]")

    if music:
        gain = music.get("gain_db", -22)
        mfilters = [f"volume={gain}dB"]
        if music.get("fade_in"):
            mfilters.append(f"afade=t=in:st=0:d={music['fade_in']}")
        parts.append(f"[{music_idx}:a]{','.join(mfilters)}[mus]")

    if n and music:
        # Duck the music under the foreground (sidechain), then mix.
        parts.append("[voice]asplit=2[vmix][vsc]")
        parts.append(
            "[mus][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[musd]"
        )
        parts.append("[vmix][musd]amix=inputs=2:normalize=0[outa]")
    elif n:
        parts.append("[voice]anull[outa]")
    elif music:
        parts.append("[mus]anull[outa]")
    else:
        return None
    return ";".join(parts)


def _encode_av(
    ffmpeg: str,
    frames_pattern: str,
    fps: int,
    clips: list[tuple[float, Path, float]],
    music: dict | None,
    out_file: Path,
    *,
    fmt: str,
    crf: int,
    duration: float,
) -> None:
    """Encode frames + foreground clips (narration + SFX) + ducked music.

    ``clips`` is a list of ``(start_seconds, path, gain_db)``.
    """
    cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", frames_pattern]
    for _, path, _gain in clips:
        cmd += ["-i", str(path)]
    music_idx = 1 + len(clips)
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music["path"])]

    fc = _audio_filter([(start, gain) for (start, _p, gain) in clips], music, music_idx)
    if fc:
        cmd += ["-filter_complex", fc, "-map", "0:v:0", "-map", "[outa]"]
        cmd += _AUDIO_CODECS[fmt]
    else:
        cmd += ["-map", "0:v:0"]
    cmd += _VIDEO_CODECS[fmt] + ["-crf", str(crf), "-r", str(fps), "-t", f"{duration:.3f}"]
    cmd += [str(out_file)]
    _run(cmd)


def _encode_gif(
    ffmpeg: str, frames_pattern: str, fps: int, out_file: Path, *, gif_fps: int, width: int
) -> None:
    """Encode frames into an optimized animated GIF (palettegen/paletteuse)."""
    vf = (
        f"fps={gif_fps},scale={width}:-1:flags=lanczos,"
        "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer"
    )
    _run([ffmpeg, "-y", "-framerate", str(fps), "-i", frames_pattern, "-vf", vf, str(out_file)])


def export_poster(
    build_dir: str | Path,
    out_file: str | Path | None = None,
    *,
    at: float | None = None,
    height: int = 720,
    port: int = 8781,
) -> Path:
    """Capture a single representative frame as a social/OG poster PNG."""
    build_dir = Path(build_dir)
    manifest_path = build_dir / "manifest.json"
    if not manifest_path.exists():
        raise ExportError(f"no manifest.json in {build_dir} (build the showreel first)")
    manifest = json.loads(manifest_path.read_text())

    try:
        import nokap
        from nokap._cdp import SyncCDP
    except Exception as exc:  # pragma: no cover - optional dep
        raise ExportError(f"nokap + Chrome are required for posters: {exc}") from exc

    width, vheight = _aspect_size(manifest.get("aspect", "16:9"), height)
    out_file = Path(out_file) if out_file else build_dir / "poster.png"
    duration = float(manifest.get("duration", 1.0))
    at = at if at is not None else max(0.1, duration * 0.35)

    server = _serve(build_dir, port)
    browser = nokap.Chrome()
    cdp = SyncCDP(browser.ws_url)
    cdp.connect()
    try:
        import time as _time

        session = nokap.Session(cdp, width=width, height=vheight)
        session.set_viewport(width, vheight, device_scale_factor=1)
        session.navigate(f"http://127.0.0.1:{port}/index.html", timeout=30.0)
        for _ in range(100):
            if session.evaluate(_PREP_JS):
                break
            _time.sleep(0.05)
        session.evaluate(f"window.__showreel.seek({min(at, duration)})")
        _grab(session, out_file, width, vheight)
    finally:
        try:
            cdp.close()
        finally:
            browser.close()
            server.shutdown()
    return out_file


def export_showreel(
    build_dir: str | Path,
    out_file: str | Path | None = None,
    *,
    fmt: str = "mp4",
    fps: int = 30,
    height: int = 720,
    crf: int = 18,
    gif_fps: int = 15,
    gif_width: int = 720,
    port: int = 8780,
) -> Path:
    """Export a built showreel bundle to a video (``mp4``, ``webm``, or ``gif``)."""
    build_dir = Path(build_dir)
    fmt = fmt.lower()
    if fmt not in ("mp4", "webm", "gif"):
        raise ExportError(f"unsupported format {fmt!r} (use mp4, webm, or gif)")
    manifest_path = build_dir / "manifest.json"
    if not manifest_path.exists():
        raise ExportError(f"no manifest.json in {build_dir} (build the showreel first)")
    manifest = json.loads(manifest_path.read_text())

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ExportError("ffmpeg not found on PATH (required for video export)")

    try:
        import nokap
        from nokap._cdp import SyncCDP
    except Exception as exc:  # pragma: no cover - optional dep
        raise ExportError(f"nokap + Chrome are required for export: {exc}") from exc

    width, vheight = _aspect_size(manifest.get("aspect", "16:9"), height)
    out_file = Path(out_file) if out_file else build_dir.with_suffix("." + fmt)

    server = _serve(build_dir, port)
    browser = nokap.Chrome()
    cdp = SyncCDP(browser.ws_url)
    cdp.connect()
    tmpdir = Path(tempfile.mkdtemp(prefix="showreel-frames-"))
    try:
        session = nokap.Session(cdp, width=width, height=vheight)
        session.set_viewport(width, vheight, device_scale_factor=1)
        session.navigate(f"http://127.0.0.1:{port}/index.html", timeout=30.0)

        import time as _time

        for _ in range(100):
            if session.evaluate(_PREP_JS):
                break
            _time.sleep(0.05)

        duration = float(session.evaluate("window.__showreel.duration()") or manifest["duration"])
        nframes = max(1, int(math.ceil(duration * fps)))
        for i in range(nframes + 1):
            t = min(i / fps, duration)
            session.evaluate(f"window.__showreel.seek({t})")
            _grab(session, tmpdir / f"frame-{i:06d}.png", width, vheight)
    finally:
        try:
            cdp.close()
        finally:
            browser.close()
            server.shutdown()

    frames_pattern = str(tmpdir / "frame-%06d.png")
    if fmt == "gif":
        _encode_gif(ffmpeg, frames_pattern, fps, out_file, gif_fps=gif_fps, width=gif_width)
    else:
        clips: list[tuple[float, Path, float]] = [
            (float(sc["start"]), build_dir / sc["audio"], 0.0)
            for sc in manifest["scenes"]
            if sc.get("audio") and (build_dir / sc["audio"]).exists()
        ]
        clips += [
            (float(ev["time"]), build_dir / ev["file"], float(ev.get("gain_db", -8)))
            for ev in manifest.get("sfx", [])
            if ev.get("file") and (build_dir / ev["file"]).exists()
        ]
        music = None
        m = manifest.get("music")
        if m and m.get("file") and (build_dir / m["file"]).exists():
            music = {"path": build_dir / m["file"], **m}
        _encode_av(
            ffmpeg, frames_pattern, fps, clips, music, out_file,
            fmt=fmt, crf=crf, duration=duration,
        )
    shutil.rmtree(tmpdir, ignore_errors=True)
    return out_file
