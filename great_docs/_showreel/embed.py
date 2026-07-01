"""Embeddable, self-contained showreel HTML for Quarto integration.

Produces a snippet that inlines the manifest (with media/audio as ``data:``
URIs) plus the player runtime — zero runtime fetches, works offline and over
``file://``, mirroring termshow's inline-embedding philosophy. The prerender
step writes ``embed.html`` next to each built reel; the Quarto shortcode
(`{{< showreel >}}`) injects it.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path

from .player import _asset

# Matches `{{< showreel file="reels/x" ... >}}` shortcodes in .qmd/.md sources.
SHORTCODE_RE = re.compile(r"{{<\s*showreel\b([^>]*?)>}}")
_FILE_ATTR_RE = re.compile(r"""file\s*=\s*["']([^"']+)["']""")


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _inline_assets(build_dir: Path, manifest: dict) -> dict:
    """Rewrite scene asset paths to inline ``data:`` URIs."""
    for sc in manifest.get("scenes", []):
        src = sc.get("src")
        if src and (build_dir / src).exists():
            sc["src"] = _data_uri(build_dir / src)
        for kf in sc.get("keyframes", []):
            if (build_dir / kf["file"]).exists():
                kf["file"] = _data_uri(build_dir / kf["file"])
        audio = sc.get("audio")
        if audio and (build_dir / audio).exists():
            sc["audio"] = _data_uri(build_dir / audio)
    return manifest


def _safe_id(name: str) -> str:
    return "gd-showreel-" + re.sub(r"[^A-Za-z0-9_-]", "-", name).strip("-")


def render_embed_html(
    build_dir: str | Path,
    *,
    element_id: str | None = None,
    include_runtime: bool = True,
    inline_assets: bool = True,
) -> str:
    """Return a self-contained HTML snippet that mounts a built showreel."""
    build_dir = Path(build_dir)
    manifest = json.loads((build_dir / "manifest.json").read_text(encoding="utf-8"))
    if inline_assets:
        manifest = _inline_assets(build_dir, manifest)

    eid = element_id or _safe_id(build_dir.name)
    # Guard against an early </script> terminating the JSON island.
    manifest_json = json.dumps(manifest).replace("</", "<\\/")

    parts: list[str] = []
    if include_runtime:
        parts.append("<style>" + _asset("showreel.css") + "</style>")
    parts.append(f'<div class="gd-showreel" id="{eid}"></div>')
    parts.append(f'<script type="application/json" id="{eid}-manifest">{manifest_json}</script>')
    if include_runtime:
        parts.append("<script>" + _asset("showreel.js") + "</script>")
    parts.append(
        "<script>(function(){var el=document.getElementById('%s');"
        "var m=JSON.parse(document.getElementById('%s-manifest').textContent);"
        "window.GreatShowreel.mount(el,m,{base:''});})();</script>" % (eid, eid)
    )
    return "\n".join(parts)


def discover_showreel_refs(text: str) -> list[str]:
    """Return the ``file`` values of every ``{{< showreel >}}`` shortcode in text."""
    refs: list[str] = []
    for m in SHORTCODE_RE.finditer(text):
        fm = _FILE_ATTR_RE.search(m.group(1))
        if fm:
            refs.append(fm.group(1))
    return refs


def prerender_showreels(
    search_dir: str | Path,
    project_dir: str | Path | None = None,
    *,
    engine: str | None = None,
) -> dict[str, Path]:
    """Discover ``{{< showreel >}}`` references, build each reel, write embed.html.

    Mirrors ``_prerender_termshow_recordings``: scans ``.qmd``/``.md`` sources,
    builds ``project_dir/showreel/<name>/`` for each referenced spec, and writes
    a self-contained ``embed.html`` the Quarto shortcode injects.
    """
    from .builder import build_showreel

    search_dir = Path(search_dir)
    project_dir = Path(project_dir) if project_dir else search_dir

    refs: set[str] = set()
    for pattern in ("*.qmd", "*.md"):
        for path in search_dir.rglob(pattern):
            try:
                refs |= set(discover_showreel_refs(path.read_text(encoding="utf-8")))
            except (OSError, UnicodeDecodeError):
                continue

    built: dict[str, Path] = {}
    for ref in sorted(refs):
        name = Path(ref).name
        spec = None
        for cand in (
            project_dir / f"{ref}.showreel.yml",
            project_dir / f"{ref}.showreel.yaml",
            project_dir / ref,
        ):
            if cand.exists():
                spec = cand
                break
        if spec is None:
            print(f"  ! showreel spec not found for {ref!r}")
            continue
        out = project_dir / "showreel" / name
        build_showreel(spec, out, engine=engine)
        (out / "embed.html").write_text(
            render_embed_html(out, element_id=_safe_id(name)), encoding="utf-8"
        )
        built[ref] = out
    return built
