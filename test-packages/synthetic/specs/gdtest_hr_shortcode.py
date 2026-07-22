"""
gdtest_hr_shortcode — Exercise the {{< hr >}} shortcode in many contexts.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The decorative horizontal rule shortcode with every supported option:
       line styles (solid, dashed, dotted, double), colors (palette + custom),
       thickness, width, alignment, embedded text, presets (gradient-shimmer,
       fade, dots, diamond, ornament, wave, double-line), and combined options.
       Tests that all styles render correctly and look good in dark mode.
"""

SPEC = {
    "name": "gdtest_hr_shortcode",
    "description": "Decorative horizontal rule shortcode with styles, presets, and text",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hr-shortcode",
            "version": "1.0.0",
            "description": "A package demonstrating the hr shortcode extension",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_hr_shortcode/__init__.py": (
            '"""Horizontal rule shortcode demo package."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["render", "transform"]\n'
            "\n"
            "\n"
            "def render(template: str) -> str:\n"
            '    """Render a template string.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    template\n"
            "        The template to render.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        Rendered output.\n"
            '    """\n'
            "    return template\n"
            "\n"
            "\n"
            "def transform(data: list) -> list:\n"
            '    """Transform a data list.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    data\n"
            "        Input data.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    list\n"
            "        Transformed data.\n"
            '    """\n'
            "    return data\n"
        ),
        # ── User guide page 1: Line styles ───────────────────────────────
        "user_guide/01-line-styles.qmd": (
            "---\n"
            "title: Line Styles\n"
            "---\n"
            "\n"
            "The `{{< hr >}}` shortcode supports multiple line styles.\n"
            "Each style changes how the rule is rendered.\n"
            "\n"
            "## Default (Solid)\n"
            "\n"
            "A plain horizontal rule with default settings:\n"
            "\n"
            "{{< hr >}}\n"
            "\n"
            "The default is a 2px solid line at full width.\n"
            "\n"
            "## Dashed\n"
            "\n"
            'A dashed rule using `style="dashed"`:\n'
            "\n"
            '{{< hr style="dashed" >}}\n'
            "\n"
            "Dashes work well for separating related content.\n"
            "\n"
            "## Dotted\n"
            "\n"
            'A dotted rule using `style="dotted"`:\n'
            "\n"
            '{{< hr style="dotted" >}}\n'
            "\n"
            "Dots create a softer, less prominent separation.\n"
            "\n"
            "## Double\n"
            "\n"
            'A double-line rule using `style="double"`:\n'
            "\n"
            '{{< hr style="double" >}}\n'
            "\n"
            "Double lines signal a more definitive break.\n"
            "\n"
            "## Comparing All Styles\n"
            "\n"
            "Here they are side by side for comparison:\n"
            "\n"
            "**Solid:**\n"
            "\n"
            "{{< hr >}}\n"
            "\n"
            "**Dashed:**\n"
            "\n"
            '{{< hr style="dashed" >}}\n'
            "\n"
            "**Dotted:**\n"
            "\n"
            '{{< hr style="dotted" >}}\n'
            "\n"
            "**Double:**\n"
            "\n"
            '{{< hr style="double" >}}\n'
        ),
        # ── User guide page 2: Colors ────────────────────────────────────
        "user_guide/02-colors.qmd": (
            "---\n"
            "title: Colors\n"
            "---\n"
            "\n"
            "Horizontal rules can use named palette colors or custom hex values.\n"
            "\n"
            "## Palette Colors\n"
            "\n"
            "Great Docs ships with eight gradient palette presets.\n"
            "Each can be used as a named color:\n"
            "\n"
            "**Sky:**\n"
            "\n"
            '{{< hr color="sky" >}}\n'
            "\n"
            "**Peach:**\n"
            "\n"
            '{{< hr color="peach" >}}\n'
            "\n"
            "**Prism:**\n"
            "\n"
            '{{< hr color="prism" >}}\n'
            "\n"
            "**Lilac:**\n"
            "\n"
            '{{< hr color="lilac" >}}\n'
            "\n"
            "**Slate:**\n"
            "\n"
            '{{< hr color="slate" >}}\n'
            "\n"
            "**Honey:**\n"
            "\n"
            '{{< hr color="honey" >}}\n'
            "\n"
            "**Dusk:**\n"
            "\n"
            '{{< hr color="dusk" >}}\n'
            "\n"
            "**Mint:**\n"
            "\n"
            '{{< hr color="mint" >}}\n'
            "\n"
            "## Custom Colors\n"
            "\n"
            "Any CSS color value works with the `color` parameter:\n"
            "\n"
            "**Rose red:**\n"
            "\n"
            '{{< hr color="#e11d48" >}}\n'
            "\n"
            "**Forest green:**\n"
            "\n"
            '{{< hr color="#16a34a" >}}\n'
            "\n"
            "**Royal blue:**\n"
            "\n"
            '{{< hr color="#2563eb" >}}\n'
            "\n"
            "**Amber:**\n"
            "\n"
            '{{< hr color="#d97706" >}}\n'
            "\n"
            "## Accent Color\n"
            "\n"
            'Use `color="accent"` to reference the site\'s theme accent:\n'
            "\n"
            '{{< hr color="accent" >}}\n'
            "\n"
            "## Colored Styles\n"
            "\n"
            "Colors combine with line styles naturally:\n"
            "\n"
            '{{< hr style="dashed" color="#e11d48" >}}\n'
            "\n"
            '{{< hr style="dotted" color="#2563eb" >}}\n'
            "\n"
            '{{< hr style="double" color="#16a34a" >}}\n'
        ),
        # ── User guide page 3: Sizing and alignment ──────────────────────
        "user_guide/03-sizing-alignment.qmd": (
            "---\n"
            "title: Sizing & Alignment\n"
            "---\n"
            "\n"
            "Control the thickness, width, alignment, and spacing of rules.\n"
            "\n"
            "## Thickness\n"
            "\n"
            "Named thickness values — `thin`, `medium` (default), and `thick`:\n"
            "\n"
            '{{< hr thickness="thin" >}}\n'
            "\n"
            "{{< hr >}}\n"
            "\n"
            '{{< hr thickness="thick" >}}\n'
            "\n"
            "Custom pixel values:\n"
            "\n"
            '{{< hr thickness="1px" >}}\n'
            "\n"
            '{{< hr thickness="3px" >}}\n'
            "\n"
            '{{< hr thickness="6px" >}}\n'
            "\n"
            "## Width\n"
            "\n"
            "Rules can be narrower than the full container:\n"
            "\n"
            '{{< hr width="100%" >}}\n'
            "\n"
            '{{< hr width="75%" >}}\n'
            "\n"
            '{{< hr width="50%" >}}\n'
            "\n"
            '{{< hr width="25%" >}}\n'
            "\n"
            "## Alignment\n"
            "\n"
            "When the rule is narrower than 100%, alignment matters:\n"
            "\n"
            "**Center (default):**\n"
            "\n"
            '{{< hr width="50%" align="center" >}}\n'
            "\n"
            "**Left:**\n"
            "\n"
            '{{< hr width="50%" align="left" >}}\n'
            "\n"
            "**Right:**\n"
            "\n"
            '{{< hr width="50%" align="right" >}}\n'
            "\n"
            "## Spacing\n"
            "\n"
            "Control the vertical margin around the rule:\n"
            "\n"
            "Content above.\n"
            "\n"
            '{{< hr spacing="compact" >}}\n'
            "\n"
            "Compact spacing (1rem).\n"
            "\n"
            '{{< hr spacing="normal" >}}\n'
            "\n"
            "Normal spacing (2rem, default).\n"
            "\n"
            '{{< hr spacing="spacious" >}}\n'
            "\n"
            "Spacious spacing (4rem).\n"
            "\n"
            "## Combined Sizing\n"
            "\n"
            "Mix thickness, width, and alignment:\n"
            "\n"
            '{{< hr thickness="thick" width="60%" align="left" color="#6366f1" >}}\n'
            "\n"
            '{{< hr thickness="thin" width="40%" align="right" style="dashed" >}}\n'
            "\n"
            '{{< hr thickness="3px" width="80%" color="#e11d48" >}}\n'
        ),
        # ── User guide page 4: Embedded text ─────────────────────────────
        "user_guide/04-embedded-text.qmd": (
            "---\n"
            "title: Embedded Text\n"
            "---\n"
            "\n"
            "Place text or symbols in the center of a horizontal rule.\n"
            "\n"
            "## Simple Symbols\n"
            "\n"
            "Single characters work great as decorative breaks:\n"
            "\n"
            '{{< hr text="§" >}}\n'
            "\n"
            '{{< hr text="✦" >}}\n'
            "\n"
            '{{< hr text="◆" >}}\n'
            "\n"
            '{{< hr text="❖" >}}\n'
            "\n"
            "## Multiple Symbols\n"
            "\n"
            "Repeat a symbol for a decorative pattern:\n"
            "\n"
            '{{< hr text="· · ·" >}}\n'
            "\n"
            '{{< hr text="★ ★ ★" >}}\n'
            "\n"
            '{{< hr text="— ✦ —" >}}\n'
            "\n"
            "## Text Labels\n"
            "\n"
            "Full words or short phrases as section dividers:\n"
            "\n"
            '{{< hr text="Continue Reading" >}}\n'
            "\n"
            '{{< hr text="Part Two" >}}\n'
            "\n"
            '{{< hr text="End of Section" >}}\n'
            "\n"
            "## Text Sizing\n"
            "\n"
            "Three text sizes are available — `sm`, `md` (default), and `lg`:\n"
            "\n"
            '{{< hr text="Small" text-size="sm" >}}\n'
            "\n"
            '{{< hr text="Medium" >}}\n'
            "\n"
            '{{< hr text="Large" text-size="lg" >}}\n'
            "\n"
            "## Colored Text Rules\n"
            "\n"
            "Combine text with colors:\n"
            "\n"
            '{{< hr text="Chapter One" color="#6366f1" >}}\n'
            "\n"
            '{{< hr text="Warning" color="#e11d48" text-color="#e11d48" >}}\n'
            "\n"
            '{{< hr text="Success" color="#16a34a" text-color="#16a34a" >}}\n'
            "\n"
            "## Text with Width and Alignment\n"
            "\n"
            '{{< hr text="Centered" width="70%" >}}\n'
            "\n"
            '{{< hr text="Left" width="60%" align="left" >}}\n'
            "\n"
            '{{< hr text="Right" width="60%" align="right" >}}\n'
        ),
        # ── User guide page 5: Presets ───────────────────────────────────
        "user_guide/05-presets.qmd": (
            "---\n"
            "title: Presets\n"
            "---\n"
            "\n"
            "Presets provide ready-made decorative styles.\n"
            "Each preset has a distinct visual character.\n"
            "\n"
            "## Gradient Shimmer\n"
            "\n"
            "An animated gradient that shifts across the rule — the signature\n"
            "Great Docs look from the homepage:\n"
            "\n"
            '{{< hr preset="gradient-shimmer" >}}\n'
            "\n"
            "## Gradient Static\n"
            "\n"
            "The same gradient palette without animation:\n"
            "\n"
            '{{< hr preset="gradient-static" >}}\n'
            "\n"
            "## Fade\n"
            "\n"
            "Full opacity at center, transparent at both edges:\n"
            "\n"
            '{{< hr preset="fade" >}}\n'
            "\n"
            "## Fade Edges\n"
            "\n"
            "Transparent edges that bloom into a colored center:\n"
            "\n"
            '{{< hr preset="fade-edges" >}}\n'
            "\n"
            "## Dots\n"
            "\n"
            "Three centered dots — a classic section break:\n"
            "\n"
            '{{< hr preset="dots" >}}\n'
            "\n"
            "## Diamond\n"
            "\n"
            "A diamond ornament flanked by fading lines:\n"
            "\n"
            '{{< hr preset="diamond" >}}\n'
            "\n"
            "## Ornament\n"
            "\n"
            "An elegant fleuron between fading lines:\n"
            "\n"
            '{{< hr preset="ornament" >}}\n'
            "\n"
            "## Wave\n"
            "\n"
            "A subtle repeating wave pattern:\n"
            "\n"
            '{{< hr preset="wave" >}}\n'
            "\n"
            "## Double Line\n"
            "\n"
            "Two parallel thin lines with a gap:\n"
            "\n"
            '{{< hr preset="double-line" >}}\n'
            "\n"
            "## Preset Gallery\n"
            "\n"
            "All presets in sequence for comparison:\n"
            "\n"
            '{{< hr preset="gradient-shimmer" >}}\n'
            '{{< hr preset="gradient-static" >}}\n'
            '{{< hr preset="fade" >}}\n'
            '{{< hr preset="fade-edges" >}}\n'
            '{{< hr preset="dots" >}}\n'
            '{{< hr preset="diamond" >}}\n'
            '{{< hr preset="ornament" >}}\n'
            '{{< hr preset="wave" >}}\n'
            '{{< hr preset="double-line" >}}\n'
        ),
        # ── User guide page 6: Combinations ──────────────────────────────
        "user_guide/06-combinations.qmd": (
            "---\n"
            "title: Combinations\n"
            "---\n"
            "\n"
            "The real power of `{{< hr >}}` comes from combining options.\n"
            "Presets can be customized with width, alignment, spacing, and color.\n"
            "\n"
            "## Preset with Width\n"
            "\n"
            "Narrow the shimmer preset to 60%:\n"
            "\n"
            '{{< hr preset="gradient-shimmer" width="60%" >}}\n'
            "\n"
            "A fade at 50%, centered:\n"
            "\n"
            '{{< hr preset="fade" width="50%" >}}\n'
            "\n"
            "## Preset with Spacing\n"
            "\n"
            "Spacious shimmer for a dramatic section break:\n"
            "\n"
            '{{< hr preset="gradient-shimmer" width="60%" spacing="spacious" >}}\n'
            "\n"
            "Compact dots for a subtle pause:\n"
            "\n"
            '{{< hr preset="dots" spacing="compact" >}}\n'
            "\n"
            "## Colored Presets\n"
            "\n"
            "Override the default accent color on presets:\n"
            "\n"
            '{{< hr preset="dots" color="#e11d48" >}}\n'
            "\n"
            '{{< hr preset="diamond" color="#2563eb" >}}\n'
            "\n"
            '{{< hr preset="ornament" color="#d97706" >}}\n'
            "\n"
            "## Style + Color + Sizing\n"
            "\n"
            "A thick dashed peach line, aligned left at 75%:\n"
            "\n"
            '{{< hr style="dashed" color="peach" width="75%" thickness="thick" >}}\n'
            "\n"
            "A thin dotted blue line at 40%, right-aligned:\n"
            "\n"
            '{{< hr style="dotted" color="#2563eb" width="40%" thickness="thin" align="right" >}}\n'
            "\n"
            "## Text + Style + Color\n"
            "\n"
            "A labeled rule with custom styling:\n"
            "\n"
            '{{< hr text="Chapter Break" color="#6366f1" thickness="thick" >}}\n'
            "\n"
            '{{< hr text="§" color="#e11d48" width="50%" >}}\n'
            "\n"
            "## Real-World Examples\n"
            "\n"
            "### Blog post section break\n"
            "\n"
            '{{< hr preset="dots" spacing="spacious" >}}\n'
            "\n"
            "### Chapter divider\n"
            "\n"
            '{{< hr text="Chapter Two" color="#6366f1" thickness="thick" width="80%" >}}\n'
            "\n"
            "### Elegant page separator\n"
            "\n"
            '{{< hr preset="ornament" width="60%" spacing="spacious" >}}\n'
            "\n"
            "### API section boundary\n"
            "\n"
            '{{< hr preset="gradient-shimmer" >}}\n'
            "\n"
            "### Light decorative break\n"
            "\n"
            '{{< hr preset="fade" thickness="thin" width="50%" >}}\n'
            "\n"
            "### Strong visual separator\n"
            "\n"
            '{{< hr thickness="thick" color="#1e293b" width="90%" >}}\n'
        ),
        # ── README ───────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-hr-shortcode\n"
            "\n"
            "A synthetic test package that exercises the `{{< hr >}}` Quarto\n"
            "shortcode with every supported option: line styles, colors,\n"
            "thickness, width, alignment, embedded text, animated presets,\n"
            "and combined parameters.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-hr-shortcode",
        "detected_module": "gdtest_hr_shortcode",
        "detected_parser": "numpy",
        "export_names": ["render", "transform"],
        "num_exports": 2,
        "has_user_guide": True,
        "user_guide_files": [
            "line-styles.qmd",
            "colors.qmd",
            "sizing-alignment.qmd",
            "embedded-text.qmd",
            "presets.qmd",
            "combinations.qmd",
        ],
        "files_contain": {
            "great-docs/_site/user-guide/line-styles.html": [
                "gd-hr",
                "gd-hr--dashed",
                "gd-hr--dotted",
                "gd-hr--double",
            ],
            "great-docs/_site/user-guide/colors.html": [
                "gd-hr",
                "--gd-hr-color",
                "gd-palette-sky",
            ],
            "great-docs/_site/user-guide/sizing-alignment.html": [
                "gd-hr",
                "--gd-hr-thickness",
                "--gd-hr-width",
                "gd-hr--left",
                "gd-hr--right",
            ],
            "great-docs/_site/user-guide/embedded-text.html": [
                "gd-hr--with-text",
                "gd-hr-text",
                "gd-hr-line",
            ],
            "great-docs/_site/user-guide/presets.html": [
                "gd-hr--gradient-shimmer",
                "gd-hr--fade",
                "gd-hr--dots",
                "gd-hr--diamond",
                "gd-hr--ornament",
                "gd-hr--wave",
                "gd-hr--double-line",
            ],
            "great-docs/_site/user-guide/combinations.html": [
                "gd-hr",
                "gd-hr--gradient-shimmer",
                "--gd-hr-width",
            ],
        },
        "coverage_exclude": ["nodoc", "bigcl", "supp", "sechdg", "sbsec", "hdg"],
    },
}
