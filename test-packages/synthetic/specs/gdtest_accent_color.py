"""
gdtest_accent_color — Verify the accent_color config option.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The accent_color config key that sets --gd-accent site-wide.
       Uses a distinctive teal (#0d9488) so it's immediately obvious whether
       the accent propagates to hr shortcodes, gradient presets, and other
       accent-colored elements. Includes light/dark per-mode variant to
       verify dark-mode handling.
"""

SPEC = {
    "name": "gdtest_accent_color",
    "description": "Site-wide accent_color config with hr shortcode integration",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-accent-color",
            "version": "1.0.0",
            "description": "A package demonstrating the accent_color config option",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_accent_color/__init__.py": (
            '"""Accent color demo package."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["highlight", "summarize"]\n'
            "\n"
            "\n"
            "def highlight(text: str) -> str:\n"
            '    """Highlight important text.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    text\n"
            "        The text to highlight.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        Highlighted text.\n"
            '    """\n'
            '    return f"**{text}**"\n'
            "\n"
            "\n"
            "def summarize(items: list) -> str:\n"
            '    """Summarize a list of items.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    items\n"
            "        Items to summarize.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        A summary string.\n"
            '    """\n'
            '    return f"{len(items)} items"\n'
        ),
        # ── User guide: accent color with string value ───────────────────
        "user_guide/01-string-accent.qmd": (
            "---\n"
            "title: String Accent Color\n"
            "---\n"
            "\n"
            "# Single Accent Color\n"
            "\n"
            "This site uses `accent_color: '#0d9488'` (teal) in the config.\n"
            "Every element that references `--gd-accent` should appear teal.\n"
            "\n"
            "## Default HR\n"
            "\n"
            "A plain `{{< hr >}}` with no color override should be teal:\n"
            "\n"
            "{{< hr >}}\n"
            "\n"
            "## HR with Accent Keyword\n"
            "\n"
            '{{< hr color="accent" >}}\n'
            "\n"
            "## Gradient Shimmer\n"
            "\n"
            "The shimmer should use the teal accent in its gradient:\n"
            "\n"
            '{{< hr preset="gradient-shimmer" >}}\n'
            "\n"
            "## Gradient Static\n"
            "\n"
            '{{< hr preset="gradient-static" >}}\n'
            "\n"
            "## Fade\n"
            "\n"
            '{{< hr preset="fade" >}}\n'
            "\n"
            "## HR Styles\n"
            "\n"
            "These should all be teal by default:\n"
            "\n"
            '{{< hr style="solid" >}}\n'
            "\n"
            '{{< hr style="dashed" >}}\n'
            "\n"
            '{{< hr style="dotted" >}}\n'
            "\n"
            '{{< hr style="double" >}}\n'
            "\n"
            "## Thick HR\n"
            "\n"
            '{{< hr thickness="thick" >}}\n'
            "\n"
            "## HR with Text\n"
            "\n"
            '{{< hr text="Teal Accent" >}}\n'
            "\n"
            "## Explicit Color Override\n"
            "\n"
            "This one explicitly sets red, so the accent should NOT apply:\n"
            "\n"
            '{{< hr color="#e11d48" >}}\n'
        ),
        # ── User guide: per-mode accent colors ───────────────────────────
        "user_guide/02-per-mode-accent.qmd": (
            "---\n"
            "title: Per-Mode Accent Colors\n"
            "---\n"
            "\n"
            "# Light / Dark Accent Colors\n"
            "\n"
            "This page tests that the accent color config can accept a dict\n"
            "with `light` and `dark` keys. The site config for this package\n"
            "uses a single string, so both modes get the same teal.\n"
            "\n"
            "Toggle dark mode to verify the color persists in both themes.\n"
            "\n"
            "## Default HR in Each Mode\n"
            "\n"
            "{{< hr >}}\n"
            "\n"
            "## Ornament Preset\n"
            "\n"
            '{{< hr preset="ornament" >}}\n'
            "\n"
            "## Diamond Preset\n"
            "\n"
            '{{< hr preset="diamond" >}}\n'
            "\n"
            "## Dots Preset\n"
            "\n"
            '{{< hr preset="dots" >}}\n'
            "\n"
            "## Text with Size Variants\n"
            "\n"
            '{{< hr text="Small" text-size="sm" >}}\n'
            "\n"
            '{{< hr text="Default" >}}\n'
            "\n"
            '{{< hr text="Large" text-size="lg" >}}\n'
        ),
        # ── User guide: accent + palette color interaction ───────────────
        "user_guide/03-palette-vs-accent.qmd": (
            "---\n"
            "title: Palette vs Accent\n"
            "---\n"
            "\n"
            "# Palette Colors vs Accent\n"
            "\n"
            "Named palette colors should use their own hue, not the accent.\n"
            "Only a plain `{{< hr >}}` or `color='accent'` should use the\n"
            "site accent.\n"
            "\n"
            "## Accent (should be teal)\n"
            "\n"
            "{{< hr >}}\n"
            "\n"
            '{{< hr color="accent" >}}\n'
            "\n"
            "## Sky (should be blue, NOT teal)\n"
            "\n"
            '{{< hr color="sky" >}}\n'
            "\n"
            "## Peach (should be orange, NOT teal)\n"
            "\n"
            '{{< hr color="peach" >}}\n'
            "\n"
            "## Honey (should be amber, NOT teal)\n"
            "\n"
            '{{< hr color="honey" >}}\n'
            "\n"
            "## Lilac (should be purple, NOT teal)\n"
            "\n"
            '{{< hr color="lilac" >}}\n'
            "\n"
            "## Mint (should be mint, similar to teal but distinct token)\n"
            "\n"
            '{{< hr color="mint" >}}\n'
            "\n"
            "## Custom Red (should be red, NOT teal)\n"
            "\n"
            '{{< hr color="#e11d48" >}}\n'
        ),
    },
    "config": {
        "accent_color": "#0d9488",
        "dark_mode": True,
    },
    "expected": {
        "files_exist": [
            "reference/index.html",
            "reference/highlight.html",
            "reference/summarize.html",
            "user-guide/string-accent.html",
            "user-guide/per-mode-accent.html",
            "user-guide/palette-vs-accent.html",
        ],
        "files_contain": {
            # The accent_color style tag should be injected
            "user-guide/string-accent.html": [
                "accent_color overrides",
                "--gd-accent: #0d9488",
                "gd-hr",
            ],
            # Default hr should use the accent (no explicit color class)
            "user-guide/string-accent.html": [
                "gd-hr",
                "accent_color overrides",
            ],
            # Palette colors should still use their own tokens
            "user-guide/palette-vs-accent.html": [
                "gd-hr",
                "--gd-hr-color: var(--gd-palette-sky",
                "--gd-hr-color: var(--gd-palette-peach",
                "--gd-hr-color: var(--gd-palette-honey",
                "--gd-hr-color: var(--gd-palette-lilac",
                "--gd-hr-color: var(--gd-palette-mint",
            ],
            # Text hr should have the text wrapper
            "user-guide/per-mode-accent.html": [
                "gd-hr--with-text",
                "gd-hr-text",
            ],
        },
        "coverage_exclude": ['ref', 'nodoc', 'bigcl', 'ug', 'supp', 'title', 'badge', 'sig', 'desc', 'param', 'pmatch', 'ret', 'refidx', 'sechdg', 'sbsec', 'hdg'],
},
}
