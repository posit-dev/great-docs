"""Named terminal color themes for termshow recordings.

Each theme defines a foreground, background, and 16-color ANSI palette
(8 normal colors followed by 8 bright colors). Themes are selected in a
`.termshow.yml` script via `settings.theme`, either by name or as an
inline mapping:

    settings:
      theme: dracula

    settings:
      theme:
        base: nord          # optional: start from a named theme
        bg: "#000000"
        cursor: "#88c0d0"
        palette: [...]      # 8 or 16 colors

A light/dark pair gives the player one theme for each color mode. `auto` is
the built-in pair, and each side can be a name or an inline mapping:

    settings:
      theme: auto

    settings:
      theme:
        light: catppuccin-latte
        dark: {base: catppuccin-mocha, bg: "#000000"}
"""

from __future__ import annotations

import re
from typing import Any

from .parser import Theme

# fg, bg, palette (black, red, green, yellow, blue, magenta, cyan, white, then bright variants)
_THEME_DATA: dict[str, tuple[str, str, list[str]]] = {
    "default": (
        Theme().fg,
        Theme().bg,
        Theme().palette,
    ),
    "catppuccin-mocha": (
        "#cdd6f4",
        "#1e1e2e",
        [
            "#45475a", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7", "#94e2d5", "#bac2de",
            "#585b70", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7", "#94e2d5", "#a6adc8",
        ],
    ),
    "catppuccin-latte": (
        "#4c4f69",
        "#eff1f5",
        [
            "#5c5f77", "#d20f39", "#40a02b", "#df8e1d", "#1e66f5", "#ea76cb", "#179299", "#acb0be",
            "#6c6f85", "#d20f39", "#40a02b", "#df8e1d", "#1e66f5", "#ea76cb", "#179299", "#bcc0cc",
        ],
    ),
    "dracula": (
        "#f8f8f2",
        "#282a36",
        [
            "#21222c", "#ff5555", "#50fa7b", "#f1fa8c", "#bd93f9", "#ff79c6", "#8be9fd", "#f8f8f2",
            "#6272a4", "#ff6e6e", "#69ff94", "#ffffa5", "#d6acff", "#ff92df", "#a4ffff", "#ffffff",
        ],
    ),
    "github-dark": (
        "#e6edf3",
        "#0d1117",
        [
            "#484f58", "#ff7b72", "#3fb950", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4",
            "#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#ffffff",
        ],
    ),
    "github-light": (
        "#1f2328",
        "#ffffff",
        [
            "#24292f", "#cf222e", "#116329", "#4d2d00", "#0969da", "#8250df", "#1b7c83", "#6e7781",
            "#57606a", "#a40e26", "#1a7f37", "#633c01", "#218bff", "#a475f9", "#3192aa", "#8c959f",
        ],
    ),
    "gruvbox-dark": (
        "#ebdbb2",
        "#282828",
        [
            "#282828", "#cc241d", "#98971a", "#d79921", "#458588", "#b16286", "#689d6a", "#a89984",
            "#928374", "#fb4934", "#b8bb26", "#fabd2f", "#83a598", "#d3869b", "#8ec07c", "#ebdbb2",
        ],
    ),
    "gruvbox-light": (
        "#3c3836",
        "#fbf1c7",
        [
            "#fbf1c7", "#cc241d", "#98971a", "#d79921", "#458588", "#b16286", "#689d6a", "#7c6f64",
            "#928374", "#9d0006", "#79740e", "#b57614", "#076678", "#8f3f71", "#427b58", "#3c3836",
        ],
    ),
    "monokai": (
        "#f8f8f2",
        "#272822",
        [
            "#272822", "#f92672", "#a6e22e", "#f4bf75", "#66d9ef", "#ae81ff", "#a1efe4", "#f8f8f2",
            "#75715e", "#f92672", "#a6e22e", "#f4bf75", "#66d9ef", "#ae81ff", "#a1efe4", "#f9f8f5",
        ],
    ),
    "nord": (
        "#d8dee9",
        "#2e3440",
        [
            "#3b4252", "#bf616a", "#a3be8c", "#ebcb8b", "#81a1c1", "#b48ead", "#88c0d0", "#e5e9f0",
            "#4c566a", "#bf616a", "#a3be8c", "#ebcb8b", "#81a1c1", "#b48ead", "#8fbcbb", "#eceff4",
        ],
    ),
    "one-dark": (
        "#abb2bf",
        "#282c34",
        [
            "#282c34", "#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#abb2bf",
            "#5c6370", "#e06c75", "#98c379", "#e5c07b", "#61afef", "#c678dd", "#56b6c2", "#ffffff",
        ],
    ),
    "rose-pine": (
        "#e0def4",
        "#191724",
        [
            "#26233a", "#eb6f92", "#31748f", "#f6c177", "#9ccfd8", "#c4a7e7", "#ebbcba", "#e0def4",
            "#6e6a86", "#eb6f92", "#31748f", "#f6c177", "#9ccfd8", "#c4a7e7", "#ebbcba", "#e0def4",
        ],
    ),
    "rose-pine-dawn": (
        "#575279",
        "#faf4ed",
        [
            "#f2e9e1", "#b4637a", "#286983", "#ea9d34", "#56949f", "#907aa9", "#d7827e", "#575279",
            "#9893a5", "#b4637a", "#286983", "#ea9d34", "#56949f", "#907aa9", "#d7827e", "#575279",
        ],
    ),
    "solarized-dark": (
        "#839496",
        "#002b36",
        [
            "#073642", "#dc322f", "#859900", "#b58900", "#268bd2", "#d33682", "#2aa198", "#eee8d5",
            "#002b36", "#cb4b16", "#586e75", "#657b83", "#839496", "#6c71c4", "#93a1a1", "#fdf6e3",
        ],
    ),
    "solarized-light": (
        "#657b83",
        "#fdf6e3",
        [
            "#073642", "#dc322f", "#859900", "#b58900", "#268bd2", "#d33682", "#2aa198", "#eee8d5",
            "#002b36", "#cb4b16", "#586e75", "#657b83", "#839496", "#6c71c4", "#93a1a1", "#fdf6e3",
        ],
    ),
    "tokyo-night": (
        "#c0caf5",
        "#1a1b26",
        [
            "#15161e", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#a9b1d6",
            "#414868", "#f7768e", "#9ece6a", "#e0af68", "#7aa2f7", "#bb9af7", "#7dcfff", "#c0caf5",
        ],
    ),
}  # fmt: skip

# Cursor colors for themes whose cursor isn't their foreground color
_CURSORS: dict[str, str] = {
    "catppuccin-mocha": "#f5e0dc",
    "catppuccin-latte": "#dc8a78",
}

# The pair used for `theme: auto`
AUTO_PAIR = ("github-light", "github-dark")

_PAIR_KEYS = {"light", "dark"}

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def theme_names() -> list[str]:
    """Return the sorted list of built-in theme names."""
    return sorted(_THEME_DATA)


def _normalize_name(name: str) -> str:
    return re.sub(r"[\s_]+", "-", name.strip().lower())


def get_theme(name: str) -> Theme:
    """Look up a built-in theme by name.

    Names are case-insensitive, and spaces/underscores are treated as hyphens
    (so `"Tokyo Night"` and `"tokyo_night"` both resolve to `"tokyo-night"`).

    Raises
    ------
    ValueError
        If the name doesn't match a built-in theme.
    """
    key = _normalize_name(name)
    if key not in _THEME_DATA:
        raise ValueError(
            f"Unknown termshow theme {name!r}. Available themes: {', '.join(theme_names())}"
        )
    fg, bg, palette = _THEME_DATA[key]
    return Theme(fg=fg, bg=bg, palette=list(palette), cursor=_CURSORS.get(key))


def _check_color(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError(
            f"termshow theme {field} must be a hex color like '#1e1e2e', got {value!r}"
        )
    return value


def is_theme_pair(spec: Any) -> bool:
    """Whether a `settings.theme` value is a light/dark pair (`auto` or `{light, dark}`)."""
    if spec == "auto":
        return True
    return isinstance(spec, dict) and bool(_PAIR_KEYS & set(spec))


def resolve_theme_pair(spec: str | dict[str, Any]) -> tuple[Theme, Theme | None]:
    """Resolve a `settings.theme` value into its light (or only) theme and its dark theme.

    Parameters
    ----------
    spec
        Anything `resolve_theme()` accepts, `"auto"` for the built-in pair
        (`AUTO_PAIR`), or a mapping with `light` and `dark` keys whose values
        are theme names or inline mappings.

    Returns
    -------
    tuple
        `(theme, dark)`. For a single theme, `dark` is None. For a pair,
        `theme` is the light side: it's the one used for SVG files and by
        players that don't know about the dark side.

    Raises
    ------
    ValueError
        If the spec is invalid, or a pair is missing a side or mixes in other keys.
    """
    if not is_theme_pair(spec):
        return resolve_theme(spec), None
    if spec == "auto":
        return get_theme(AUTO_PAIR[0]), get_theme(AUTO_PAIR[1])
    extra = set(spec) - _PAIR_KEYS
    if extra:
        raise ValueError(
            "termshow theme pair takes only `light` and `dark`, got "
            + ", ".join(sorted(map(str, extra)))
        )
    missing = _PAIR_KEYS - set(spec)
    if missing:
        raise ValueError(f"termshow theme pair is missing `{missing.pop()}`")
    sides = []
    for side in ("light", "dark"):
        value = spec[side]
        if is_theme_pair(value):
            raise ValueError(f"termshow theme `{side}` must be one theme, not a pair")
        sides.append(resolve_theme(value))
    return sides[0], sides[1]


def resolve_theme(spec: str | dict[str, Any]) -> Theme:
    """Resolve a `settings.theme` value from a script into a `Theme`.

    Parameters
    ----------
    spec
        A built-in theme name, or a mapping with optional `base` (theme name),
        `fg`, `bg`, `cursor`, and `palette` (8 or 16 hex colors; 8 colors are
        reused for the bright variants). For a light/dark pair, this returns
        the light side (see `resolve_theme_pair()`).

    Raises
    ------
    ValueError
        If the name is unknown or a color value is invalid.
    """
    if is_theme_pair(spec):
        return resolve_theme_pair(spec)[0]

    if isinstance(spec, str):
        return get_theme(spec)

    if not isinstance(spec, dict):
        raise ValueError(f"termshow theme must be a name or a mapping, got {type(spec).__name__}")

    base = spec.get("base")
    theme = get_theme(base) if base else Theme()

    if "fg" in spec:
        theme.fg = _check_color(spec["fg"], "fg")
    if "bg" in spec:
        theme.bg = _check_color(spec["bg"], "bg")
    if "cursor" in spec:
        theme.cursor = _check_color(spec["cursor"], "cursor")
    if "palette" in spec:
        palette = spec["palette"]
        if not isinstance(palette, list) or len(palette) not in (8, 16):
            raise ValueError("termshow theme palette must be a list of 8 or 16 hex colors")
        palette = [_check_color(c, f"palette[{i}]") for i, c in enumerate(palette)]
        if len(palette) == 8:
            palette = palette + palette
        theme.palette = palette

    return theme
