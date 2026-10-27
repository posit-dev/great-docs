"""Color swatch shortcode helper.

Called by `color-swatch.lua` via `io.popen`.  Reads an optional YAML body
from *stdin* (when the shortcode has inner content) or loads a built-in GD
palette preset, computes APCA contrast values, and emits self-contained HTML
for the requested display mode.
"""

from __future__ import annotations

import argparse
import colorsys
import html as html_mod
import importlib.util
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module bootstrap — load contrast helpers from great_docs.contrast
# ---------------------------------------------------------------------------

_parse_color = None
_ideal_text_color = None
_apca_contrast = None
_relative_luminance_apca = None


def _load_contrast_module() -> None:
    global _parse_color, _ideal_text_color, _apca_contrast, _relative_luminance_apca

    # Fast path: great_docs is installed
    try:
        from great_docs.contrast import (
            _apca_contrast as _ac,
        )
        from great_docs.contrast import (
            _relative_luminance_apca as _rl,
        )
        from great_docs.contrast import (
            ideal_text_color as _itc,
        )
        from great_docs.contrast import (
            parse_color as _pc,
        )

        _parse_color = _pc
        _ideal_text_color = _itc
        _apca_contrast = _ac
        _relative_luminance_apca = _rl
        return
    except Exception:  # pragma: no cover
        pass

    # Walk ancestors to find contrast.py  (only reached outside an installed package)
    cur = Path(__file__).resolve().parent  # pragma: no cover
    for ancestor in cur.parents:  # pragma: no cover
        contrast_path = ancestor / "great_docs" / "contrast.py"
        if contrast_path.exists():
            spec = importlib.util.spec_from_file_location("contrast", contrast_path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            _parse_color = mod.parse_color
            _ideal_text_color = mod.ideal_text_color
            _apca_contrast = mod._apca_contrast
            _relative_luminance_apca = mod._relative_luminance_apca
            return

    raise ImportError("Cannot locate great_docs/contrast.py")  # pragma: no cover


_load_contrast_module()

# ---------------------------------------------------------------------------
# Built-in GD palette presets
# ---------------------------------------------------------------------------

GD_PALETTES: dict[str, dict[str, Any]] = {
    "sky": {
        "description": "Soft sky blues",
        "light": [
            {"name": "Sky 100", "hex": "#e0f4ff"},
            {"name": "Sky 200", "hex": "#d0ecf9"},
            {"name": "Sky 300", "hex": "#c5e8f7"},
            {"name": "Sky 400", "hex": "#b8e0f5"},
        ],
        "dark": [
            {"name": "Sky 100", "hex": "#0096c7"},
            {"name": "Sky 200", "hex": "#0077b6"},
            {"name": "Sky 300", "hex": "#005f73"},
            {"name": "Sky 400", "hex": "#023e8a"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "peach": {
        "description": "Peach and blush",
        "light": [
            {"name": "Peach 100", "hex": "#ffe4cc"},
            {"name": "Peach 200", "hex": "#ffddc1"},
            {"name": "Peach 300", "hex": "#fdd0d8"},
            {"name": "Peach 400", "hex": "#fbc4d4"},
        ],
        "dark": [
            {"name": "Peach 100", "hex": "#c7760f"},
            {"name": "Peach 200", "hex": "#cc4a1a"},
            {"name": "Peach 300", "hex": "#b84a5f"},
            {"name": "Peach 400", "hex": "#a33560"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "prism": {
        "description": "Mint, sky, and lavender",
        "light": [
            {"name": "Prism 100", "hex": "#d0e8f5"},
            {"name": "Prism 200", "hex": "#c4f0e0"},
            {"name": "Prism 300", "hex": "#e4d4f4"},
            {"name": "Prism 400", "hex": "#d8cef0"},
        ],
        "dark": [
            {"name": "Prism 100", "hex": "#0c6a8a"},
            {"name": "Prism 200", "hex": "#048a65"},
            {"name": "Prism 300", "hex": "#52077d"},
            {"name": "Prism 400", "hex": "#2a0978"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "lilac": {
        "description": "Lilac and pink",
        "light": [
            {"name": "Lilac 100", "hex": "#f5d0e0"},
            {"name": "Lilac 200", "hex": "#e8d0f0"},
            {"name": "Lilac 300", "hex": "#f0d4f8"},
            {"name": "Lilac 400", "hex": "#eac8ee"},
        ],
        "dark": [
            {"name": "Lilac 100", "hex": "#8b1140"},
            {"name": "Lilac 200", "hex": "#561e64"},
            {"name": "Lilac 300", "hex": "#a02db3"},
            {"name": "Lilac 400", "hex": "#6e1a7d"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "slate": {
        "description": "Cool grays",
        "light": [
            {"name": "Slate 100", "hex": "#eceff1"},
            {"name": "Slate 200", "hex": "#e0e4e8"},
            {"name": "Slate 300", "hex": "#dde2e6"},
            {"name": "Slate 400", "hex": "#d5dadf"},
        ],
        "dark": [
            {"name": "Slate 100", "hex": "#455a64"},
            {"name": "Slate 200", "hex": "#37474f"},
            {"name": "Slate 300", "hex": "#3e525e"},
            {"name": "Slate 400", "hex": "#263238"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "honey": {
        "description": "Warm cream and apricot",
        "light": [
            {"name": "Honey 100", "hex": "#ffedcc"},
            {"name": "Honey 200", "hex": "#ffe0c2"},
            {"name": "Honey 300", "hex": "#ffe5b4"},
            {"name": "Honey 400", "hex": "#ffd6a8"},
        ],
        "dark": [
            {"name": "Honey 100", "hex": "#e65100"},
            {"name": "Honey 200", "hex": "#bf360c"},
            {"name": "Honey 300", "hex": "#ef6c00"},
            {"name": "Honey 400", "hex": "#b71c1c"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "dusk": {
        "description": "Soft lavender-blue",
        "light": [
            {"name": "Dusk 100", "hex": "#dddff5"},
            {"name": "Dusk 200", "hex": "#d8daf0"},
            {"name": "Dusk 300", "hex": "#d4d0ee"},
            {"name": "Dusk 400", "hex": "#dad4f2"},
        ],
        "dark": [
            {"name": "Dusk 100", "hex": "#141b55"},
            {"name": "Dusk 200", "hex": "#0d1244"},
            {"name": "Dusk 300", "hex": "#1a0f52"},
            {"name": "Dusk 400", "hex": "#261560"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
    "mint": {
        "description": "Pale aqua",
        "light": [
            {"name": "Mint 100", "hex": "#d5f0ec"},
            {"name": "Mint 200", "hex": "#ccece8"},
            {"name": "Mint 300", "hex": "#c4e8e4"},
            {"name": "Mint 400", "hex": "#d0f2ee"},
        ],
        "dark": [
            {"name": "Mint 100", "hex": "#00796b"},
            {"name": "Mint 200", "hex": "#00695c"},
            {"name": "Mint 300", "hex": "#004d40"},
            {"name": "Mint 400", "hex": "#00897b"},
        ],
        "gradient": {
            "angle": -45,
            "duration": "15s",
            "timing": "ease",
            "iteration": "infinite",
            "background_size": "400% 400%",
        },
    },
}

# ---------------------------------------------------------------------------
# Color utility helpers
# ---------------------------------------------------------------------------


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert a hex color string to (R, G, B) using `contrast.parse_color`."""
    return _parse_color(hex_str)  # type: ignore[return-value]


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Convert RGB (0-255) to HSL (degrees, percent, percent), rounded to ints."""
    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return (round(hue * 360) % 360, round(saturation * 100), round(lightness * 100))


def needs_border_ring(hex_str: str) -> tuple[bool, str]:
    """Determine if a swatch needs a border ring and return the ring color.

    Very light colors (luminance > 0.93) get a slightly darker ring.
    Very dark colors (luminance < 0.07) get a slightly lighter ring.
    Returns `(needs_ring, ring_color_hex)`.
    """
    r, g, b = hex_to_rgb(hex_str)
    lum = _relative_luminance_apca(r, g, b)  # type: ignore[misc]

    if lum > 0.93:
        # Darken by 10%
        dr = max(0, int(r * 0.9))
        dg = max(0, int(g * 0.9))
        db = max(0, int(b * 0.9))
        return True, f"#{dr:02x}{dg:02x}{db:02x}"
    if lum < 0.07:
        # Lighten by mixing with white
        lr = min(255, r + 40)
        lg = min(255, g + 40)
        lb = min(255, b + 40)
        return True, f"#{lr:02x}{lg:02x}{lb:02x}"

    return False, ""


def compute_contrast_info(hex_str: str) -> dict[str, Any]:
    """Compute APCA contrast values for a color against white and black."""
    r, g, b = hex_to_rgb(hex_str)
    lum = _relative_luminance_apca(r, g, b)  # type: ignore[misc]
    white_lum = _relative_luminance_apca(255, 255, 255)  # type: ignore[misc]
    black_lum = _relative_luminance_apca(0, 0, 0)  # type: ignore[misc]

    lc_vs_white = abs(_apca_contrast(white_lum, lum))  # type: ignore[misc]
    lc_vs_black = abs(_apca_contrast(black_lum, lum))  # type: ignore[misc]

    ideal = _ideal_text_color(hex_str)  # type: ignore[misc]

    # WCAG AA via APCA: normal text >= 60 Lc, large >= 45, non-text >= 30
    best_lc = max(lc_vs_white, lc_vs_black)
    aa_normal = best_lc >= 60
    aa_large = best_lc >= 45

    return {
        "lc_vs_white": round(lc_vs_white, 1),
        "lc_vs_black": round(lc_vs_black, 1),
        "ideal_text": ideal,
        "aa_normal": aa_normal,
        "aa_large": aa_large,
    }


# ---------------------------------------------------------------------------
# YAML parsing
# ---------------------------------------------------------------------------

try:
    from yaml12 import parse_yaml as _parse_yaml_raw

    def _parse_yaml(text: str) -> list[dict[str, Any]]:
        data = _parse_yaml_raw(text)
        if isinstance(data, list):
            return data
        return []

except ImportError:  # pragma: no cover
    # Minimal YAML-subset parser for simple list-of-dicts (no external dep)

    def _parse_yaml(text: str) -> list[dict[str, Any]]:  # type: ignore[misc]
        """Parse a trivial YAML list of dicts (single-level, string values)."""
        items: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- "):
                # New item — may have key on same line
                if current is not None:
                    items.append(current)
                current = {}
                rest = stripped[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    current[k.strip()] = v.strip().strip("\"'")
            elif ":" in stripped and current is not None:
                k, v = stripped.split(":", 1)
                current[k.strip()] = v.strip().strip("\"'")
        if current is not None:
            items.append(current)
        return items


def parse_colors(body: str, palette: str) -> list[dict[str, Any]]:
    """Resolve the color list from body YAML and/or a palette preset."""
    colors: list[dict[str, Any]] = []

    if palette:
        if palette == "all":
            for name, preset in GD_PALETTES.items():
                for c in preset["light"]:
                    colors.append({**c, "group": name.capitalize()})
        elif palette in GD_PALETTES:
            colors.extend(GD_PALETTES[palette]["light"])
        else:
            raise ValueError(f"Unknown palette: {palette!r}")

    if body.strip():
        parsed = _parse_yaml(body)
        for entry in parsed:
            if "hex" not in entry or "name" not in entry:
                continue
            colors.append(entry)

    return colors


# ---------------------------------------------------------------------------
# Tooltip HTML
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    return html_mod.escape(text, quote=True)


def build_tooltip_html(color: dict[str, Any], show_contrast: str) -> str:
    """Build the rich tooltip HTML for a single swatch."""
    hex_val = color["hex"]
    name = color.get("name", hex_val)
    r, g, b = hex_to_rgb(hex_val)
    hue, saturation, lightness = rgb_to_hsl(r, g, b)

    parts = [
        '<div class="gd-cs-tooltip">',
        f'<div class="gd-cs-tooltip-swatch" style="background:{_esc(hex_val)}"></div>',
        '<div class="gd-cs-tooltip-body">',
        f'<div class="gd-cs-tooltip-name">{_esc(name)}</div>',
        '<table class="gd-cs-tooltip-table">',
        f"<tr><td>HEX</td><td><code>{_esc(hex_val)}</code>"
        f' <button class="gd-cs-tooltip-copy" data-hex="{_esc(hex_val)}" '
        f'aria-label="Copy hex value" title="Copy">&#128203;</button></td></tr>',
        f"<tr><td>RGB</td><td>{r}, {g}, {b}</td></tr>",
        f"<tr><td>HSL</td><td>{hue}&deg;, {saturation}%, {lightness}%</td></tr>",
    ]

    if show_contrast != "false":
        info = compute_contrast_info(hex_val)
        parts.append('<tr><td colspan="2" class="gd-cs-tooltip-sep"></td></tr>')
        parts.append(f"<tr><td>vs White</td><td>{info['lc_vs_white']} Lc</td></tr>")
        parts.append(f"<tr><td>vs Black</td><td>{info['lc_vs_black']} Lc</td></tr>")
        verdict = "&#10003; AA" if info["aa_normal"] else "&#10007; AA"
        css_cls = "gd-cs-pass" if info["aa_normal"] else "gd-cs-fail"
        parts.append(f'<tr><td>WCAG</td><td class="{css_cls}">{verdict} (normal)</td></tr>')

    parts.append("</table></div></div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# HTML renderers
# ---------------------------------------------------------------------------

_ID_COUNTER = 0


def _next_id() -> str:
    global _ID_COUNTER
    _ID_COUNTER += 1
    return f"gd-cs-{_ID_COUNTER}"


def render_circles(
    colors: list[dict[str, Any]],
    *,
    size: str = "56px",
    show_contrast: str = "true",
    show_names: str = "true",
    show_hex: str = "true",
    copy_format: str = "hex",
    title: str = "",
    description: str = "",
    elem_id: str = "",
    extra_class: str = "",
    border: str = "true",
) -> str:
    """Render colors as circle swatches."""
    cid = elem_id or _next_id()
    cls = "gd-color-swatch gd-color-swatch--circles"
    if border == "true":
        cls += " gd-color-swatch--bordered"
    if extra_class:
        cls += " " + extra_class

    parts = [
        f'<div class="{cls}" id="{_esc(cid)}" data-copy-format="{_esc(copy_format)}" data-mode="circles" style="--gd-cs-size:{_esc(size)}">'
    ]

    if title:
        parts.append(f'<div class="gd-cs-title">{_esc(title)}</div>')
    if description:
        parts.append(f'<div class="gd-cs-description">{_esc(description)}</div>')

    parts.append('<div class="gd-cs-swatches">')

    for color in colors:
        hex_val = color["hex"]
        name = color.get("name", hex_val)
        ring, ring_color = needs_border_ring(hex_val)
        tooltip = build_tooltip_html(color, show_contrast)

        # Inline contrast info
        contrast_inline = ""
        if show_contrast == "inline":
            info = compute_contrast_info(hex_val)
            contrast_inline = f'<span class="gd-swatch-contrast">{info["lc_vs_white"]}/{info["lc_vs_black"]} Lc</span>'

        ring_attr = ""
        ring_style = ""
        if ring:
            ring_attr = ' data-needs-ring="true"'
            ring_style = f";--gd-ring-color:{ring_color}"

        # Escape tooltip HTML for data attribute (double-encode quotes)
        tooltip_escaped = _esc(tooltip)

        parts.append(
            f'<div class="gd-swatch" role="button" tabindex="0" '
            f'aria-label="{_esc(name)}, hex {_esc(hex_val)}, click to copy">'
            f'<div class="gd-swatch-color" style="background:{_esc(hex_val)}{ring_style}"'
            f'{ring_attr} data-hex="{_esc(hex_val)}" '
            f'data-tooltip-html="{tooltip_escaped}"></div>'
        )
        if show_names == "true":
            parts.append(f'<span class="gd-swatch-name">{_esc(name)}</span>')
        if show_hex == "true":
            parts.append(f'<span class="gd-swatch-hex">{_esc(hex_val)}</span>')
        if contrast_inline:
            parts.append(contrast_inline)
        parts.append("</div>")

    parts.append("</div></div>")
    return "\n".join(parts)


def render_rectangles(
    colors: list[dict[str, Any]],
    *,
    show_contrast: str = "true",
    show_names: str = "true",
    show_hex: str = "true",
    copy_format: str = "hex",
    title: str = "",
    description: str = "",
    elem_id: str = "",
    extra_class: str = "",
    border: str = "true",
) -> str:
    """Render colors as horizontal rectangle strips."""
    cid = elem_id or _next_id()
    cls = "gd-color-swatch gd-color-swatch--rectangles"
    if border == "true":
        cls += " gd-color-swatch--bordered"
    if extra_class:
        cls += " " + extra_class

    parts = [
        f'<div class="{cls}" id="{_esc(cid)}" data-copy-format="{_esc(copy_format)}" data-mode="rectangles">'
    ]

    if title:
        parts.append(f'<div class="gd-cs-title">{_esc(title)}</div>')
    if description:
        parts.append(f'<div class="gd-cs-description">{_esc(description)}</div>')

    for color in colors:
        hex_val = color["hex"]
        name = color.get("name", hex_val)
        info = compute_contrast_info(hex_val)
        text_color = info["ideal_text"]
        tooltip = build_tooltip_html(color, show_contrast)
        tooltip_escaped = _esc(tooltip)

        parts.append(
            f'<div class="gd-swatch-rect" role="button" tabindex="0" '
            f'style="background:{_esc(hex_val)};color:{_esc(text_color)}" '
            f'data-hex="{_esc(hex_val)}" '
            f'data-tooltip-html="{tooltip_escaped}" '
            f'aria-label="{_esc(name)}, hex {_esc(hex_val)}, click to copy">'
        )

        if show_names == "true":
            parts.append(f'<span class="gd-swatch-rect-name">{_esc(name)}</span>')
        if show_hex == "true":
            parts.append(f'<span class="gd-swatch-rect-hex">{_esc(hex_val)}</span>')

        if show_contrast != "false":
            white_cls = "gd-cs-pass" if info["lc_vs_white"] >= 60 else "gd-cs-fail"
            black_cls = "gd-cs-pass" if info["lc_vs_black"] >= 60 else "gd-cs-fail"
            parts.append(
                '<span class="gd-swatch-contrast-samples">'
                f'<span class="gd-swatch-aa-sample {white_cls}" style="color:#fff">Aa</span>'
                f'<span class="gd-swatch-aa-sample {black_cls}" style="color:#000">Aa</span>'
                "</span>"
            )

        parts.append("</div>")

    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Render color swatches as HTML.")
    parser.add_argument("--palette", default="", help="GD palette preset name")
    parser.add_argument("--mode", default="circles", help="Display mode")
    parser.add_argument("--cols", default="4", help="Grid columns")
    parser.add_argument("--size", default="56px", help="Swatch size")
    parser.add_argument("--show-contrast", default="true", dest="show_contrast")
    parser.add_argument("--show-names", default="true", dest="show_names")
    parser.add_argument("--show-hex", default="true", dest="show_hex")
    parser.add_argument("--copy-format", default="hex", dest="copy_format")
    parser.add_argument("--title", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--file", default="", dest="file_path")
    parser.add_argument("--height", default="200px")
    parser.add_argument("--show-css", default="true", dest="show_css")
    parser.add_argument("--show-details", default="true", dest="show_details")
    parser.add_argument("--show-controls", default="true", dest="show_controls")
    parser.add_argument("--id", default="", dest="elem_id")
    parser.add_argument("--class", default="", dest="extra_class")
    parser.add_argument("--border", default="true")

    args = parser.parse_args()

    try:
        # Read body from stdin (may be empty)
        body = ""
        if not sys.stdin.isatty():
            body = sys.stdin.read()

        # Or from an external file
        if args.file_path:
            file_p = Path(args.file_path)
            if not file_p.is_absolute():
                file_p = Path(".").resolve() / file_p
            body = file_p.read_text(encoding="utf-8")

        colors = parse_colors(body, args.palette)

        if not colors:
            print(
                "<!-- color-swatch: no colors to display -->",
                file=sys.stderr,
            )
            sys.exit(1)

        if args.mode == "circles":
            html_out = render_circles(
                colors,
                size=args.size,
                show_contrast=args.show_contrast,
                show_names=args.show_names,
                show_hex=args.show_hex,
                copy_format=args.copy_format,
                title=args.title,
                description=args.description,
                elem_id=args.elem_id,
                extra_class=args.extra_class,
                border=args.border,
            )
        elif args.mode == "rectangles":
            html_out = render_rectangles(
                colors,
                show_contrast=args.show_contrast,
                show_names=args.show_names,
                show_hex=args.show_hex,
                copy_format=args.copy_format,
                title=args.title,
                description=args.description,
                elem_id=args.elem_id,
                extra_class=args.extra_class,
                border=args.border,
            )
        else:
            print(
                f"<!-- color-swatch: unsupported mode '{args.mode}' -->",
                file=sys.stderr,
            )
            sys.exit(1)

        print(html_out, end="")

    except Exception as exc:
        print(
            f"<!-- color-swatch error: {exc} -->",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
