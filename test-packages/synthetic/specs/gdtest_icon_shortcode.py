"""
gdtest_icon_shortcode — Exercise the {{< icon >}} shortcode in many contexts.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The Lucide icon shortcode in headings, prose, tables, callouts,
       lists, blockquotes, and definition lists. Tests that icons render
       as inline <svg> elements in all common Quarto content contexts.
"""

SPEC = {
    "name": "gdtest_icon_shortcode",
    "description": "Icon shortcode in headings, tables, callouts, and prose",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-icon-shortcode",
            "version": "1.0.0",
            "description": "A package demonstrating Lucide icon shortcodes",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_icon_shortcode/__init__.py": (
            '"""Icon shortcode demo package."""\n'
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
        # ── User guide page: icons in many contexts ──────────────────────
        "user_guide/01-icon-showcase.qmd": (
            "---\n"
            "title: Icon Showcase\n"
            "---\n"
            "\n"
            "This page exercises the `{{< icon >}}` shortcode in many\n"
            "different content contexts.\n"
            "\n"
            "## {{< icon rocket >}} Headings with Icons\n"
            "\n"
            "Icons can appear in section headings to give visual cues.\n"
            "\n"
            "### {{< icon settings >}} Sub-heading Example\n"
            "\n"
            "A sub-heading with an icon too.\n"
            "\n"
            "## Inline Prose\n"
            "\n"
            "You can place icons inline: {{< icon heart >}} for love,\n"
            "{{< icon star >}} for favorites, and {{< icon check >}} for\n"
            "completion.\n"
            "\n"
            "## Icons with Options\n"
            "\n"
            'A larger icon: {{< icon rocket size="24" >}} renders at 24px.\n'
            "\n"
            'An accessible icon: {{< icon alert-triangle label="Warning" >}}\n'
            "has an aria-label instead of aria-hidden.\n"
            "\n"
            "## {{< icon table >}} Tables\n"
            "\n"
            "Icons work inside table cells:\n"
            "\n"
            "| Feature | Status | Icon |\n"
            "|---------|--------|------|\n"
            "| Rendering | Complete | {{< icon check >}} |\n"
            "| Search | In Progress | {{< icon loader >}} |\n"
            "| Export | Planned | {{< icon calendar >}} |\n"
            "\n"
            "## {{< icon message-square >}} Callouts\n"
            "\n"
            ":::{.callout-note}\n"
            "## {{< icon info >}} Note with Icon\n"
            "This callout has an icon in its title.\n"
            ":::\n"
            "\n"
            ":::{.callout-tip}\n"
            "## {{< icon lightbulb >}} Tip\n"
            "Use `{{< icon name >}}` to insert any of the 1900+ Lucide icons.\n"
            ":::\n"
            "\n"
            ":::{.callout-warning}\n"
            "## {{< icon alert-triangle >}} Warning\n"
            "Some icons may not render if the name is misspelled.\n"
            ":::\n"
            "\n"
            "## {{< icon list >}} Lists\n"
            "\n"
            "Unordered list with icons:\n"
            "\n"
            "- {{< icon file-text >}} Documentation\n"
            "- {{< icon code-2 >}} Source code\n"
            "- {{< icon test-tube >}} Testing\n"
            "- {{< icon package >}} Packaging\n"
            "\n"
            "Ordered list:\n"
            "\n"
            "1. {{< icon download >}} Install the package\n"
            "2. {{< icon settings >}} Configure your project\n"
            "3. {{< icon play >}} Run the build\n"
            "\n"
            "## {{< icon quote >}} Blockquotes\n"
            "\n"
            "> {{< icon message-circle >}} Icons render inside blockquotes too.\n"
            "> This is useful for attributions and callouts.\n"
            "\n"
            "## {{< icon book-open >}} Definition Lists\n"
            "\n"
            "{{< icon heart >}} Heart\n"
            ":   Represents love or favorites.\n"
            "\n"
            "{{< icon star >}} Star\n"
            ":   Represents ratings or bookmarks.\n"
            "\n"
            "{{< icon zap >}} Zap\n"
            ":   Represents speed or energy.\n"
        ),
        # ── User guide page: icon gallery ────────────────────────────────
        "user_guide/02-icon-gallery.qmd": (
            "---\n"
            "title: Icon Gallery\n"
            "---\n"
            "\n"
            "A gallery of commonly used icons for quick reference.\n"
            "\n"
            "## Navigation Icons\n"
            "\n"
            "| Icon | Name |\n"
            "|------|------|\n"
            "| {{< icon home >}} | home |\n"
            "| {{< icon menu >}} | menu |\n"
            "| {{< icon search >}} | search |\n"
            "| {{< icon arrow-left >}} | arrow-left |\n"
            "| {{< icon arrow-right >}} | arrow-right |\n"
            "| {{< icon external-link >}} | external-link |\n"
            "\n"
            "## Status Icons\n"
            "\n"
            "| Icon | Name | Meaning |\n"
            "|------|------|---------|\n"
            "| {{< icon check-circle >}} | check-circle | Success |\n"
            "| {{< icon x-circle >}} | x-circle | Error |\n"
            "| {{< icon alert-circle >}} | alert-circle | Warning |\n"
            "| {{< icon info >}} | info | Information |\n"
            "| {{< icon help-circle >}} | help-circle | Help |\n"
            "\n"
            "## File & Code Icons\n"
            "\n"
            "| Icon | Name |\n"
            "|------|------|\n"
            "| {{< icon file >}} | file |\n"
            "| {{< icon folder >}} | folder |\n"
            "| {{< icon code-2 >}} | code-2 |\n"
            "| {{< icon terminal >}} | terminal |\n"
            "| {{< icon git-branch >}} | git-branch |\n"
            "| {{< icon git-commit-horizontal >}} | git-commit-horizontal |\n"
            "\n"
            "## Sized Icons\n"
            "\n"
            "Icons at different sizes:\n"
            "\n"
            '- 12px: {{< icon star size="12" >}}\n'
            '- 16px: {{< icon star size="16" >}} (default)\n'
            '- 20px: {{< icon star size="20" >}}\n'
            '- 24px: {{< icon star size="24" >}}\n'
            '- 32px: {{< icon star size="32" >}}\n'
        ),
        # ── README ───────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-icon-shortcode\n"
            "\n"
            "A synthetic test package that exercises the `{{< icon >}}` Quarto\n"
            "shortcode in many different content contexts: headings, tables,\n"
            "callouts, lists, blockquotes, and definition lists.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-icon-shortcode",
        "detected_module": "gdtest_icon_shortcode",
        "detected_parser": "numpy",
        "export_names": ["render", "transform"],
        "num_exports": 2,
        "has_user_guide": True,
        "user_guide_files": ["icon-showcase.qmd", "icon-gallery.qmd"],
        # Content assertions for dedicated tests
        "files_contain": {
            "great-docs/_site/user-guide/icon-showcase.html": [
                "<svg",  # icons rendered as SVG
                "gd-icon",  # CSS class on icon SVGs
                "Icon Showcase",  # page title
            ],
            "great-docs/_site/user-guide/icon-gallery.html": [
                "<svg",
                "Icon Gallery",
            ],
        },
    },
}
