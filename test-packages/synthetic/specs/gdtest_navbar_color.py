"""
gdtest_navbar_color — Visual showcase of navbar_color + APCA contrast.

Dimensions: K43
Focus: navbar_color config with APCA-based automatic text color selection.
The user guide page contains a visual grid showing how the APCA contrast
algorithm picks light or dark text for a wide range of background colors.
"""

# Build the color swatch HTML table at spec-generation time so the
# resulting .qmd is purely static (no Python execution needed at render).

_SWATCH_COLORS = [
    # Reds
    ("#FF0000", "Red"),
    ("#DC143C", "Crimson"),
    ("#8B0000", "Dark Red"),
    ("#FF6347", "Tomato"),
    ("#CD5C5C", "Indian Red"),
    ("#F08080", "Light Coral"),
    # Oranges
    ("#FF4500", "Orange Red"),
    ("#FF8C00", "Dark Orange"),
    ("#FFA500", "Orange"),
    ("#FF7F50", "Coral"),
    ("#E9967A", "Dark Salmon"),
    ("#FA8072", "Salmon"),
    # Yellows
    ("#FFD700", "Gold"),
    ("#FFFF00", "Yellow"),
    ("#F0E68C", "Khaki"),
    ("#FAFAD2", "Lt Goldenrod"),
    ("#FFFACD", "Lemon Chiffon"),
    ("#EEE8AA", "Pale Goldenrod"),
    # Greens
    ("#006400", "Dark Green"),
    ("#008000", "Green"),
    ("#228B22", "Forest Green"),
    ("#2E8B57", "Sea Green"),
    ("#32CD32", "Lime Green"),
    ("#00FF00", "Lime"),
    ("#90EE90", "Light Green"),
    ("#98FB98", "Pale Green"),
    ("#ADFF2F", "Green Yellow"),
    # Teals / Cyans
    ("#008080", "Teal"),
    ("#008B8B", "Dark Cyan"),
    ("#20B2AA", "Lt Sea Green"),
    ("#00CED1", "Dark Turquoise"),
    ("#40E0D0", "Turquoise"),
    ("#00FFFF", "Cyan"),
    ("#E0FFFF", "Light Cyan"),
    # Blues
    ("#000080", "Navy"),
    ("#00008B", "Dark Blue"),
    ("#0000FF", "Blue"),
    ("#191970", "Midnight Blue"),
    ("#4169E1", "Royal Blue"),
    ("#4682B4", "Steel Blue"),
    ("#1E90FF", "Dodger Blue"),
    ("#6495ED", "Cornflower Blue"),
    ("#87CEEB", "Sky Blue"),
    ("#ADD8E6", "Light Blue"),
    ("#B0E0E6", "Powder Blue"),
    ("#E3F2FD", "Ice Blue"),
    # Purples
    ("#4B0082", "Indigo"),
    ("#663399", "Rebecca Purple"),
    ("#800080", "Purple"),
    ("#8B008B", "Dark Magenta"),
    ("#9370DB", "Medium Purple"),
    ("#BA55D3", "Medium Orchid"),
    ("#DA70D6", "Orchid"),
    ("#DDA0DD", "Plum"),
    ("#E6E6FA", "Lavender"),
    # Pinks
    ("#C71585", "Med Violet Red"),
    ("#FF1493", "Deep Pink"),
    ("#FF69B4", "Hot Pink"),
    ("#FFB6C1", "Light Pink"),
    ("#FFC0CB", "Pink"),
    ("#FFF0F5", "Lavender Blush"),
    # Browns
    ("#8B4513", "Saddle Brown"),
    ("#A0522D", "Sienna"),
    ("#D2691E", "Chocolate"),
    ("#CD853F", "Peru"),
    ("#DEB887", "Burlywood"),
    ("#F5DEB3", "Wheat"),
    # Grays
    ("#000000", "Black"),
    ("#1a1a1a", "#1a1a1a"),
    ("#333333", "#333333"),
    ("#555555", "#555555"),
    ("#696969", "Dim Gray"),
    ("#808080", "Gray"),
    ("#A9A9A9", "Dark Gray"),
    ("#C0C0C0", "Silver"),
    ("#D3D3D3", "Light Gray"),
    ("#F5F5F5", "White Smoke"),
    ("#FFFFFF", "White"),
    # Misc popular
    ("#2c3e50", "Charcoal"),
    ("#34495e", "Wet Asphalt"),
    ("#1abc9c", "Turquoise"),
    ("#2ecc71", "Emerald"),
    ("#3498db", "Peter River"),
    ("#9b59b6", "Amethyst"),
    ("#e74c3c", "Alizarin"),
    ("#f39c12", "Sun Flower"),
    ("#e67e22", "Carrot"),
    ("#ecf0f1", "Clouds"),
    ("#bdc3c7", "Silver Cloud"),
    ("#7f8c8d", "Asbestos"),
    ("#27ae60", "Nephritis"),
    ("#16a085", "Green Sea"),
    ("#2980b9", "Belize Hole"),
    ("#8e44ad", "Wisteria"),
    ("#f1c40f", "Sunflower"),
    ("#d35400", "Pumpkin"),
    ("#c0392b", "Pomegranate"),
]


def _build_swatch_table() -> str:
    """Build an HTML table of color swatches with APCA-chosen text color."""
    # Import from the actual package
    from great_docs.contrast import ideal_text_color, parse_color

    rows: list[str] = []
    for hex_color, label in _SWATCH_COLORS:
        text_color = ideal_text_color(hex_color)
        r, g, b = parse_color(hex_color)
        text_label = "white" if text_color.upper() == "#FFFFFF" else "black"
        rows.append(
            f"  <tr>"
            f'<td style="background:{hex_color};color:{text_color};'
            f"padding:10px 16px;font-weight:600;font-size:15px;"
            f'font-family:monospace;min-width:120px;text-align:center;">'
            f"{hex_color}</td>"
            f'<td style="background:{hex_color};color:{text_color};'
            f'padding:10px 12px;font-size:14px;">{label}</td>'
            f'<td style="padding:10px 12px;font-size:14px;font-family:monospace;">'
            f"rgb({r},{g},{b})</td>"
            f'<td style="padding:10px 12px;font-size:14px;font-weight:600;'
            f'font-family:monospace;color:{text_color};background:{hex_color};">'
            f"{text_label}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


_SWATCH_HTML = _build_swatch_table()

# Build the user guide content at module level (no indentation) so that
# textwrap.dedent() in the generator doesn't break the HTML.
_GUIDE_CONTENT = f"""\
---
title: "APCA Contrast Showcase"
---

## How `navbar_color` Works

When you set `navbar_color` in your `great-docs.yml`, Great Docs
uses the **APCA (Accessible Perceptual Contrast Algorithm)** to
automatically determine whether the navbar text, icons, and
controls should be **light** (white) or **dark** (black).

This page shows the algorithm's choices across **{len(_SWATCH_COLORS)}
different background colors** spanning the entire spectrum.

### Configuration for This Site

This site uses per-mode navbar colors:

```yaml
navbar_color:
  light: "#2c3e50"   # Charcoal (gets white text)
  dark: "#1a237e"    # Deep indigo (gets white text)
```

You can also set a single color for both modes:

```yaml
navbar_color: steelblue
```

## Color Swatch Grid

Each row shows a background color with the APCA-selected text
color rendered on top. The **Hex** and **Name** columns use
the computed text color directly on the background, so you can
judge readability at a glance.

<div style="overflow-x:auto;">
<table style="border-collapse:collapse;width:100%;margin:1.5em 0;">
<thead>
<tr style="border-bottom:2px solid var(--gd-border-color,#ccc);">
  <th style="padding:8px 16px;text-align:left;">Hex</th>
  <th style="padding:8px 12px;text-align:left;">Name</th>
  <th style="padding:8px 12px;text-align:left;">RGB</th>
  <th style="padding:8px 12px;text-align:left;">Text Choice</th>
</tr>
</thead>
<tbody>
{_SWATCH_HTML}
</tbody>
</table>
</div>

## About the APCA Algorithm

The APCA (Accessible Perceptual Contrast Algorithm) is a modern
replacement for the WCAG 2.x contrast ratio. Key advantages:

- **Perceptually uniform**: matches how humans actually perceive
  contrast, unlike the simple luminance ratio in WCAG 2.x.
- **Polarity-aware**: treats dark-on-light differently from
  light-on-dark, reflecting the asymmetry in human vision.
- **Better mid-range decisions**: WCAG 2.x often fails for
  medium-tone colors; APCA handles these correctly.

The implementation is ported from the
[gt R package](https://github.com/rstudio/gt), using
SAPC APCA Beta 0.0.98G-4g coefficients.
"""

SPEC = {
    "name": "gdtest_navbar_color",
    "description": "Visual showcase of navbar_color with APCA contrast algorithm",
    "dimensions": ["K43"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-navbar-color",
            "version": "0.1.0",
            "description": "APCA contrast showcase for navbar_color",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "navbar_color": {
            "light": "#2c3e50",
            "dark": "#1a237e",
        },
        "display_name": "Navbar Color Showcase",
    },
    "files": {
        "gdtest_navbar_color/__init__.py": '''\
            """
            APCA Navbar Color Showcase
            ==========================

            This package demonstrates the ``navbar_color`` configuration option
            in Great Docs, which uses the APCA (Accessible Perceptual Contrast
            Algorithm) to automatically choose light or dark text for maximum
            readability against any navbar background color.
            """

            __version__ = "0.1.0"
            __all__ = ["contrast_ratio", "ideal_text_color"]


            def contrast_ratio(bg_color: str, fg_color: str) -> float:
                """
                Compute the APCA contrast ratio between two colors.

                Parameters
                ----------
                bg_color
                    Background color as a hex string (e.g., ``"#2c3e50"``).
                fg_color
                    Foreground (text) color as a hex string.

                Returns
                -------
                float
                    The APCA Lc contrast value. Higher absolute values
                    indicate stronger contrast.

                Examples
                --------
                >>> contrast_ratio("#000000", "#FFFFFF")
                106.04
                >>> contrast_ratio("#FFFFFF", "#000000")
                -107.88
                """
                return 0.0


            def ideal_text_color(bg_color: str) -> str:
                """
                Choose the best text color (light or dark) for a background.

                Uses the APCA algorithm to determine whether white or black
                text provides better contrast against the given background.

                Parameters
                ----------
                bg_color
                    Background color as a hex string or CSS named color.

                Returns
                -------
                str
                    Either ``"#FFFFFF"`` (white) or ``"#000000"`` (black).

                Examples
                --------
                >>> ideal_text_color("#2c3e50")
                '#FFFFFF'
                >>> ideal_text_color("#e3f2fd")
                '#000000'
                >>> ideal_text_color("navy")
                '#FFFFFF'
                """
                return "#FFFFFF"
        ''',
        "docs/user_guide/01-contrast-showcase.qmd": _GUIDE_CONTENT,
        "README.md": """\
            # Navbar Color Showcase

            This site demonstrates the `navbar_color` configuration option in
            Great Docs. Look at the navbar above — its background color and
            text color are automatically paired for maximum contrast using
            the APCA algorithm.

            Visit the **User Guide** to see a comprehensive grid of color
            swatches showing how the algorithm selects light or dark text
            for over 100 different background colors.
        """,
    },
}
