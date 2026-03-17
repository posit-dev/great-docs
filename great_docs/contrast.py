"""
APCA (Accessible Perceptual Contrast Algorithm) contrast utilities.

Determines whether light or dark foreground text provides better contrast against an arbitrary
background color. This is used for automatically selecting navbar text color when a custom navbar
background is specified.

The APCA algorithm implements SAPC APCA Beta 0.0.98G-4g (Oct 1, 2021).
"""

from __future__ import annotations

import re

# APCA coefficient values (Beta 0.0.98G-4g, Oct 1, 2021)
_APCA = {
    "mainTRC": 2.4,
    "sRco": 0.2126729,
    "sGco": 0.7151522,
    "sBco": 0.0721750,
    "normBG": 0.56,
    "normTXT": 0.57,
    "revTXT": 0.62,
    "revBG": 0.65,
    "blkThrs": 0.022,
    "blkClmp": 1.414,
    "scaleBoW": 1.14,
    "scaleWoB": 1.14,
    "loBoWoffset": 0.027,
    "deltaYmin": 0.0005,
}

# CSS named colors (basic + extended) mapped to hex
_CSS_COLORS: dict[str, str] = {
    "aliceblue": "#f0f8ff",
    "antiquewhite": "#faebd7",
    "aqua": "#00ffff",
    "aquamarine": "#7fffd4",
    "azure": "#f0ffff",
    "beige": "#f5f5dc",
    "bisque": "#ffe4c4",
    "black": "#000000",
    "blanchedalmond": "#ffebcd",
    "blue": "#0000ff",
    "blueviolet": "#8a2be2",
    "brown": "#a52a2a",
    "burlywood": "#deb887",
    "cadetblue": "#5f9ea0",
    "chartreuse": "#7fff00",
    "chocolate": "#d2691e",
    "coral": "#ff7f50",
    "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc",
    "crimson": "#dc143c",
    "cyan": "#00ffff",
    "darkblue": "#00008b",
    "darkcyan": "#008b8b",
    "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b",
    "darkmagenta": "#8b008b",
    "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00",
    "darkorchid": "#9932cc",
    "darkred": "#8b0000",
    "darksalmon": "#e9967a",
    "darkseagreen": "#8fbc8f",
    "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f",
    "darkslategrey": "#2f4f4f",
    "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3",
    "deeppink": "#ff1493",
    "deepskyblue": "#00bfff",
    "dimgray": "#696969",
    "dimgrey": "#696969",
    "dodgerblue": "#1e90ff",
    "firebrick": "#b22222",
    "floralwhite": "#fffaf0",
    "forestgreen": "#228b22",
    "fuchsia": "#ff00ff",
    "gainsboro": "#dcdcdc",
    "ghostwhite": "#f8f8ff",
    "gold": "#ffd700",
    "goldenrod": "#daa520",
    "gray": "#808080",
    "green": "#008000",
    "greenyellow": "#adff2f",
    "grey": "#808080",
    "honeydew": "#f0fff0",
    "hotpink": "#ff69b4",
    "indianred": "#cd5c5c",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lavenderblush": "#fff0f5",
    "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd",
    "lightblue": "#add8e6",
    "lightcoral": "#f08080",
    "lightcyan": "#e0ffff",
    "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1",
    "lightsalmon": "#ffa07a",
    "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa",
    "lightslategray": "#778899",
    "lightslategrey": "#778899",
    "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0",
    "lime": "#00ff00",
    "limegreen": "#32cd32",
    "linen": "#faf0e6",
    "magenta": "#ff00ff",
    "maroon": "#800000",
    "mediumaquamarine": "#66cdaa",
    "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3",
    "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371",
    "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a",
    "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585",
    "midnightblue": "#191970",
    "mintcream": "#f5fffa",
    "mistyrose": "#ffe4e1",
    "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead",
    "navy": "#000080",
    "oldlace": "#fdf5e6",
    "olive": "#808000",
    "olivedrab": "#6b8e23",
    "orange": "#ffa500",
    "orangered": "#ff4500",
    "orchid": "#da70d6",
    "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98",
    "paleturquoise": "#afeeee",
    "palevioletred": "#db7093",
    "papayawhip": "#ffefd5",
    "peachpuff": "#ffdab9",
    "peru": "#cd853f",
    "pink": "#ffc0cb",
    "plum": "#dda0dd",
    "powderblue": "#b0e0e6",
    "purple": "#800080",
    "rebeccapurple": "#663399",
    "red": "#ff0000",
    "rosybrown": "#bc8f8f",
    "royalblue": "#4169e1",
    "saddlebrown": "#8b4513",
    "salmon": "#fa8072",
    "sandybrown": "#f4a460",
    "seagreen": "#2e8b57",
    "seashell": "#fff5ee",
    "sienna": "#a0522d",
    "silver": "#c0c0c0",
    "skyblue": "#87ceeb",
    "slateblue": "#6a5acd",
    "slategray": "#708090",
    "slategrey": "#708090",
    "snow": "#fffafa",
    "springgreen": "#00ff7f",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "teal": "#008080",
    "thistle": "#d8bfd8",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "white": "#ffffff",
    "whitesmoke": "#f5f5f5",
    "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}

# Regex for hex color formats
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3,8})$")


def parse_color(color: str) -> tuple[int, int, int]:
    """Parse a CSS color string to an (R, G, B) tuple.

    Supports hex (#RGB, #RRGGBB, #RRGGBBAA) and CSS named colors.

    Parameters
    ----------
    color
        A CSS color string.

    Returns
    -------
    tuple[int, int, int]
        The (R, G, B) components, each in 0-255.

    Raises
    ------
    ValueError
        If the color string is not recognized.
    """
    color = color.strip()

    # Named color lookup
    lower = color.lower()
    if lower in _CSS_COLORS:
        color = _CSS_COLORS[lower]

    m = _HEX_RE.match(color)
    if not m:
        raise ValueError(f"Unrecognized color: {color!r}")

    hex_str = m.group(1)

    if len(hex_str) == 3 or len(hex_str) == 4:
        # #RGB or #RGBA -> expand to #RRGGBB(AA)
        r = int(hex_str[0] * 2, 16)
        g = int(hex_str[1] * 2, 16)
        b = int(hex_str[2] * 2, 16)
    elif len(hex_str) in (6, 8):
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
    else:  # pragma: no cover
        raise ValueError(f"Unrecognized color: {color!r}")

    return (r, g, b)


def _relative_luminance_apca(r: int, g: int, b: int) -> float:
    """Compute APCA relative luminance from sRGB values (0-255)."""
    # Normalize to 0-1 and apply sRGB transfer curve
    rs = (r / 255.0) ** _APCA["mainTRC"]
    gs = (g / 255.0) ** _APCA["mainTRC"]
    bs = (b / 255.0) ** _APCA["mainTRC"]

    # Weighted sum
    y = rs * _APCA["sRco"] + gs * _APCA["sGco"] + bs * _APCA["sBco"]

    # Black clamp
    if y <= _APCA["blkThrs"]:
        y = (_APCA["blkThrs"] - y) ** _APCA["blkClmp"] + y

    return y


def _apca_contrast(txt_lum: float, bg_lum: float) -> float:
    """Compute APCA contrast value (Lc) for text on background.

    Returns a signed value: positive for light-on-dark, negative for dark-on-light. The magnitude is
    in Lc units (0-108 typical range).
    """
    if abs(bg_lum - txt_lum) < _APCA["deltaYmin"]:
        return 0.0

    if bg_lum >= txt_lum:
        # Normal polarity (dark text on light background)
        lc = (bg_lum ** _APCA["normBG"] - txt_lum ** _APCA["normTXT"]) * _APCA["scaleBoW"]
        if lc < 0.1:
            return 0.0
        return (lc - _APCA["loBoWoffset"]) * 100.0
    else:
        # Reverse polarity (light text on dark background)
        lc = (bg_lum ** _APCA["revBG"] - txt_lum ** _APCA["revTXT"]) * _APCA["scaleWoB"]
        if lc > -0.1:
            return 0.0
        return (lc + _APCA["loBoWoffset"]) * 100.0


def ideal_text_color(
    bg_color: str,
    light: str = "#FFFFFF",
    dark: str = "#000000",
) -> str:
    """Determine the ideal foreground text color for a given background.

    Uses the APCA (Accessible Perceptual Contrast Algorithm) to decide whether light or dark text
    provides better contrast against the specified background color.

    Parameters
    ----------
    bg_color
        Background color (hex or CSS named color).
    light
        The light text color option. Defaults to white.
    dark
        The dark text color option. Defaults to black.

    Returns
    -------
    str
        The chosen text color (either `light` or `dark`).
    """
    bg_rgb = parse_color(bg_color)
    light_rgb = parse_color(light)
    dark_rgb = parse_color(dark)

    bg_lum = _relative_luminance_apca(*bg_rgb)
    light_lum = _relative_luminance_apca(*light_rgb)
    dark_lum = _relative_luminance_apca(*dark_rgb)

    contrast_light = abs(_apca_contrast(light_lum, bg_lum))
    contrast_dark = abs(_apca_contrast(dark_lum, bg_lum))

    return dark if contrast_dark >= contrast_light else light


def navbar_color_css(
    bg_color: str,
    light_text: str = "#FFFFFF",
    dark_text: str = "#000000",
) -> str:
    """Generate the CSS variable overrides for a custom navbar color.

    Returns a CSS string that sets `--gd-navbar-bg` and `--gd-navbar-text` to provide maximum
    contrast.

    Parameters
    ----------
    bg_color
        The navbar background color (hex or CSS named color).
    light_text
        Light text option for contrast calculation.
    dark_text
        Dark text option for contrast calculation.

    Returns
    -------
    str
        A CSS variable declaration block (without selector).
    """
    text_color = ideal_text_color(bg_color, light=light_text, dark=dark_text)

    # Normalize bg_color to hex for consistency
    r, g, b = parse_color(bg_color)
    bg_hex = f"#{r:02x}{g:02x}{b:02x}"

    return f"--gd-navbar-bg: {bg_hex};\n    --gd-navbar-text: {text_color};"
