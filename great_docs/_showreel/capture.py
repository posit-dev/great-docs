"""Web-scene capture via ``nokap`` (Chrome / CDP).

Drives a persistent Chrome tab through a scene's interaction ``steps`` and
captures a viewport-sized PNG keyframe at each ``capture`` step. Click/fill
targets are recorded so the builder can synthesize a cursor path.

Capture happens at build time and requires Chrome + ``nokap``. If either is
missing the builder degrades the scene to a placeholder (see ``CaptureError``).
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .spec import Scene


class CaptureError(RuntimeError):
    """Raised when a web scene cannot be captured."""


def is_url(s: str) -> bool:
    return s.startswith(("http://", "https://", "file://", "data:"))


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


@dataclass
class CaptureResult:
    keyframes: list[dict[str, Any]] = field(default_factory=list)  # [{file, label}]
    # Cursor waypoints as fractions of the capture timeline: (frac, x, y, click)
    cursor: list[tuple[float, float, float, bool]] = field(default_factory=list)


def _js_str(s: str) -> str:
    return json.dumps(s)


def _grab(session: Any, path: Path, vw: int, vh: int) -> None:
    """Capture the current viewport (following scroll) to ``path`` as PNG."""
    sx = session.evaluate("window.scrollX") or 0
    sy = session.evaluate("window.scrollY") or 0
    params = {
        "format": "png",
        "captureBeyondViewport": True,
        "clip": {"x": sx, "y": sy, "width": vw, "height": vh, "scale": 1},
    }
    result = session._send("Page.captureScreenshot", params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(result["data"]))


def _wait_for(session: Any, selector: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    js = f"(() => !!document.querySelector({_js_str(selector)}))()"
    while time.monotonic() < deadline:
        if session.evaluate(js):
            return
        time.sleep(0.1)
    raise CaptureError(f"timed out waiting for selector: {selector!r}")


def _element_center(session: Any, selector: str, vw: int, vh: int) -> tuple[float, float] | None:
    try:
        b = session.get_element_bounds(selector)
    except Exception:
        return None
    return ((b.x + b.width / 2) / vw, (b.y + b.height / 2) / vh)


def _resolve_url(scene: Scene, spec_dir: Path, base_url: str | None) -> str:
    url = scene.url
    if not url:
        raise CaptureError(f"web scene {scene.id!r} has no `url`")
    if is_url(url):
        return url
    if base_url and not url.startswith(("/", ".")):
        return base_url.rstrip("/") + "/" + url
    # Treat as a local path relative to the spec.
    return file_url(spec_dir / url)


def capture_web_scene(
    scene: Scene,
    *,
    spec_dir: Path,
    media_dir: Path,
    base_url: str | None = None,
    nav_timeout: float = 30.0,
) -> CaptureResult:
    """Capture a ``web`` scene's keyframes by driving Chrome through its steps."""
    try:
        import nokap
        from nokap._cdp import SyncCDP
    except Exception as exc:  # pragma: no cover - depends on optional dep
        raise CaptureError(f"nokap is required for web scenes: {exc}") from exc

    vp = scene.viewport or {}
    vw = int(vp.get("width", 1280))
    vh = int(vp.get("height", 720))
    scale = float(vp.get("scale", 1))

    # Resolve the URL first so an obvious mistake fails before launching Chrome.
    target_url = _resolve_url(scene, spec_dir, base_url)

    try:
        browser = nokap.Chrome()
    except Exception as exc:
        raise CaptureError(f"could not launch Chrome: {exc}") from exc

    cdp = SyncCDP(browser.ws_url)
    cdp.connect()
    result = CaptureResult()
    # Count the interaction "beats" so cursor waypoints can be spread in time.
    beats = [s for s in scene.steps if any(k in s for k in ("click", "fill", "select", "capture"))]
    beat_total = max(1, len(beats))
    beat_i = 0

    try:
        session = nokap.Session(cdp, width=vw, height=vh)
        session.set_viewport(vw, vh, device_scale_factor=scale)
        session.navigate(target_url, timeout=nav_timeout)
        n = 0
        for step in scene.steps:
            frac = beat_i / beat_total
            if "wait_for" in step:
                _wait_for(session, str(step["wait_for"]), float(step.get("timeout", 10.0)))
            elif "wait" in step:
                time.sleep(float(step["wait"]))
            elif "eval" in step:
                session.evaluate(str(step["eval"]))
            elif "scroll" in step:
                sv = step["scroll"]
                if isinstance(sv, str):
                    session.evaluate(
                        f"document.querySelector({_js_str(sv)})"
                        f".scrollIntoView({{behavior:'instant',block:'center'}})"
                    )
                else:
                    session.evaluate(f"window.scrollBy(0, {float(sv)})")
                beat_i += 1
            elif "click" in step:
                sel = str(step["click"])
                center = _element_center(session, sel, vw, vh)
                if center:
                    result.cursor.append((frac, center[0], center[1], True))
                session.evaluate(f"document.querySelector({_js_str(sel)}).click()")
                beat_i += 1
            elif "fill" in step:
                f = step["fill"]
                sel, text = str(f.get("selector", "")), str(f.get("text", ""))
                center = _element_center(session, sel, vw, vh)
                if center:
                    result.cursor.append((frac, center[0], center[1], False))
                session.evaluate(
                    f"(() => {{ const el=document.querySelector({_js_str(sel)});"
                    f" el.value={_js_str(text)};"
                    f" el.dispatchEvent(new Event('input',{{bubbles:true}})); }})()"
                )
                beat_i += 1
            elif "select" in step:
                s = step["select"]
                sel, val = str(s.get("selector", "")), str(s.get("value", ""))
                session.evaluate(
                    f"(() => {{ const el=document.querySelector({_js_str(sel)});"
                    f" el.value={_js_str(val)};"
                    f" el.dispatchEvent(new Event('change',{{bubbles:true}})); }})()"
                )
                beat_i += 1
            elif "capture" in step:
                cap = step["capture"] or {}
                path = media_dir / f"{scene.id}-{n:03d}.png"
                _grab(session, path, vw, vh)
                result.keyframes.append({"file": f"media/{path.name}", "label": cap.get("label", "")})
                n += 1
                beat_i += 1
        if not result.keyframes:
            # No explicit capture steps: grab the final state.
            path = media_dir / f"{scene.id}-000.png"
            _grab(session, path, vw, vh)
            result.keyframes.append({"file": f"media/{path.name}", "label": ""})
        return result
    finally:
        try:
            cdp.close()
        finally:
            browser.close()


def capture_notebook_scene(
    scene: Scene,
    *,
    spec_dir: Path,
    media_dir: Path,
    nav_timeout: float = 30.0,
) -> CaptureResult:
    """Execute a notebook to HTML, then capture it (full or scrolling keyframes)."""
    import tempfile

    from .notebooks import export_notebook_html

    try:
        import nokap
        from nokap._cdp import SyncCDP
    except Exception as exc:  # pragma: no cover - optional dep
        raise CaptureError(f"nokap is required for notebook scenes: {exc}") from exc

    nb_path = (spec_dir / scene.notebook).resolve()
    html = Path(tempfile.mkdtemp(prefix="showreel-nb-")) / "notebook.html"
    export_notebook_html(nb_path, html, runtime=scene.runtime)

    vp = scene.viewport or {}
    vw = int(vp.get("width", 1100))
    vh = int(vp.get("height", 760))
    scale = float(vp.get("scale", 1))
    cap = scene.capture or {}
    mode = str(cap.get("mode", "scroll"))
    settle = float(cap.get("settle_ms", 1500)) / 1000.0

    browser = nokap.Chrome()
    cdp = SyncCDP(browser.ws_url)
    cdp.connect()
    result = CaptureResult()
    try:
        session = nokap.Session(cdp, width=vw, height=vh)
        session.set_viewport(vw, vh, device_scale_factor=scale)
        session.navigate(html.resolve().as_uri(), timeout=nav_timeout)

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if session.evaluate(
                "(function(){var r=document.getElementById('root');"
                "return !!r && r.children.length>0;})()"
            ):
                break
            time.sleep(0.2)
        time.sleep(settle)

        total = int(session.evaluate("document.body.scrollHeight") or vh)
        n = 0
        if mode == "full" or total <= vh * 1.2:
            session.evaluate("window.scrollTo(0,0)")
            _grab(session, media_dir / f"{scene.id}-000.png", vw, vh)
            result.keyframes.append({"file": f"media/{scene.id}-000.png", "label": ""})
        else:
            step = max(1, int(vh * 0.85))
            y = 0
            while y < total and n < 12:
                session.evaluate(f"window.scrollTo(0,{y})")
                time.sleep(0.25)
                _grab(session, media_dir / f"{scene.id}-{n:03d}.png", vw, vh)
                result.keyframes.append({"file": f"media/{scene.id}-{n:03d}.png", "label": ""})
                n += 1
                y += step
        return result
    finally:
        try:
            cdp.close()
        finally:
            browser.close()
