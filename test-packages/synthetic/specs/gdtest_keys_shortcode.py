"""
gdtest_keys_shortcode — Exercise the {{< keys >}} shortcode in many contexts.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The keyboard key-cap shortcode for single keys, shortcut combos,
       platform-aware rendering (macOS symbols vs Windows labels), and use
       in headings, prose, tables, callouts, lists, and code-adjacent docs.
       Tests that keys render as styled <kbd> elements with correct classes.
"""

SPEC = {
    "name": "gdtest_keys_shortcode",
    "description": "Keyboard key shortcode with combos, platform-aware rendering",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-keys-shortcode",
            "version": "1.0.0",
            "description": "A package demonstrating the keys shortcode extension",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_keys_shortcode/__init__.py": (
            '"""Keyboard shortcode demo package."""\n'
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
        # ── User guide page 1: Single keys ───────────────────────────────
        "user_guide/01-single-keys.qmd": (
            "---\n"
            "title: Single Keys\n"
            "---\n"
            "\n"
            "The `{{< keys >}}` shortcode renders individual keyboard keys\n"
            "with styled key-cap appearance.\n"
            "\n"
            "## Basic Keys\n"
            "\n"
            'Press {{< keys "Esc" >}} to cancel.\n'
            "\n"
            'Press {{< keys "Enter" >}} to confirm.\n'
            "\n"
            'Press {{< keys "Tab" >}} to move to the next field.\n'
            "\n"
            'Press {{< keys "Space" >}} to toggle.\n'
            "\n"
            "## Modifier Keys\n"
            "\n"
            'The {{< keys "Ctrl" >}} key is used for shortcuts.\n'
            "\n"
            'Hold {{< keys "Shift" >}} to select a range.\n'
            "\n"
            'The {{< keys "Alt" >}} key triggers alternate actions.\n'
            "\n"
            "## Letter and Number Keys\n"
            "\n"
            'Press {{< keys "A" >}} to select all (with Ctrl).\n'
            "\n"
            'Press {{< keys "F5" >}} to refresh.\n'
            "\n"
            'Press {{< keys "F1" >}} for help.\n'
            "\n"
            "## Arrow Keys\n"
            "\n"
            "Use the arrow keys to navigate:\n"
            '{{< keys "Up" >}} {{< keys "Down" >}}'
            ' {{< keys "Left" >}} {{< keys "Right" >}}\n'
            "\n"
            "## Function Keys\n"
            "\n"
            "Function keys render with compact, x-height styling:\n"
            "\n"
            '{{< keys "F1" >}} {{< keys "F2" >}} {{< keys "F3" >}} '
            '{{< keys "F4" >}} {{< keys "F5" >}}\n'
            '{{< keys "F6" >}} {{< keys "F7" >}} {{< keys "F8" >}} '
            '{{< keys "F9" >}} {{< keys "F10" >}}\n'
            '{{< keys "F11" >}} {{< keys "F12" >}}\n'
        ),
        # ── User guide page 2: Shortcut combos ──────────────────────────
        "user_guide/02-shortcut-combos.qmd": (
            "---\n"
            "title: Shortcut Combos\n"
            "---\n"
            "\n"
            "Use `shortcut=` to render multi-key combinations automatically.\n"
            "\n"
            "## Common Editor Shortcuts\n"
            "\n"
            "| Action | Shortcut |\n"
            "|--------|----------|\n"
            '| Copy | {{< keys shortcut="Ctrl+C" >}} |\n'
            '| Paste | {{< keys shortcut="Ctrl+V" >}} |\n'
            '| Undo | {{< keys shortcut="Ctrl+Z" >}} |\n'
            '| Save | {{< keys shortcut="Ctrl+S" >}} |\n'
            '| Find | {{< keys shortcut="Ctrl+F" >}} |\n'
            "\n"
            "## VS Code Shortcuts\n"
            "\n"
            "Open the command palette with\n"
            '{{< keys shortcut="Ctrl+Shift+P" >}}.\n'
            "\n"
            "Toggle the terminal with\n"
            '{{< keys shortcut="Ctrl+Shift+`" >}}.\n'
            "\n"
            "Quick open a file with\n"
            '{{< keys shortcut="Ctrl+P" >}}.\n'
            "\n"
            "## Manual Combos\n"
            "\n"
            "You can also build combos manually:\n"
            '{{< keys "Ctrl" >}}+{{< keys "Shift" >}}+{{< keys "P" >}}\n'
        ),
        # ── User guide page 3: Platform-aware rendering ──────────────────
        "user_guide/03-platform-aware.qmd": (
            "---\n"
            "title: Platform-Aware Rendering\n"
            "---\n"
            "\n"
            "The `platform=` parameter translates keys for macOS or Windows.\n"
            "\n"
            "## macOS Rendering\n"
            "\n"
            "On macOS, modifier keys render as symbols:\n"
            "\n"
            "| Generic | macOS |\n"
            "|---------|-------|\n"
            '| Ctrl | {{< keys shortcut="Ctrl+C" platform="mac" >}} |\n'
            '| Cmd | {{< keys shortcut="Cmd+S" platform="mac" >}} |\n'
            '| Alt/Option | {{< keys shortcut="Alt+F" platform="mac" >}} |\n'
            '| Shift | {{< keys shortcut="Shift+A" platform="mac" >}} |\n'
            "\n"
            "Command palette on macOS:\n"
            '{{< keys shortcut="Cmd+Shift+P" platform="mac" >}}\n'
            "\n"
            "## Windows Rendering\n"
            "\n"
            "On Windows, macOS-specific keys are translated:\n"
            "\n"
            "| macOS | Windows |\n"
            "|-------|--------|\n"
            '| Cmd+S | {{< keys shortcut="Cmd+S" platform="win" >}} |\n'
            '| Option+F | {{< keys shortcut="Option+F" platform="win" >}} |\n'
            "\n"
            "## Default (No Platform)\n"
            "\n"
            "Without `platform=`, keys are rendered as-is:\n"
            "\n"
            '{{< keys shortcut="Ctrl+Shift+P" >}}\n'
        ),
        # ── User guide page 4: Keys in context ──────────────────────────
        "user_guide/04-keys-in-context.qmd": (
            "---\n"
            "title: Keys in Context\n"
            "---\n"
            "\n"
            "Keyboard shortcuts work in many documentation contexts.\n"
            "\n"
            '## {{< keys "F1" >}} Headings with Keys\n'
            "\n"
            "Keys can appear in section headings for quick reference.\n"
            "\n"
            "## In Callouts\n"
            "\n"
            ":::{.callout-tip}\n"
            "## Keyboard Shortcut\n"
            'Press {{< keys shortcut="Ctrl+Shift+P" >}} to open the command\n'
            "palette in VS Code.\n"
            ":::\n"
            "\n"
            ":::{.callout-note}\n"
            "## Navigation\n"
            'Use {{< keys "Tab" >}} and {{< keys shortcut="Shift+Tab" >}} to\n'
            "move between form fields.\n"
            ":::\n"
            "\n"
            "## In Lists\n"
            "\n"
            "Common shortcuts:\n"
            "\n"
            '- {{< keys shortcut="Ctrl+C" >}} — Copy\n'
            '- {{< keys shortcut="Ctrl+V" >}} — Paste\n'
            '- {{< keys shortcut="Ctrl+Z" >}} — Undo\n'
            '- {{< keys shortcut="Ctrl+Y" >}} — Redo\n'
            "\n"
            "## In Blockquotes\n"
            "\n"
            '> Press {{< keys "Esc" >}} to close any dialog or cancel\n'
            "> the current operation.\n"
            "\n"
            "## In Prose\n"
            "\n"
            'To save your work, press {{< keys shortcut="Ctrl+S" >}}. '
            "If you need to undo a mistake, reach for\n"
            '{{< keys shortcut="Ctrl+Z" >}}. For more advanced operations,\n'
            'open the command palette with {{< keys shortcut="Ctrl+Shift+P" >}}.\n'
        ),
        # ── README ───────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-keys-shortcode\n"
            "\n"
            "A synthetic test package that exercises the `{{< keys >}}` Quarto\n"
            "shortcode for rendering keyboard keys with styled key-caps.\n"
            "Covers single keys, shortcut combos, platform-aware rendering,\n"
            "and keys in various content contexts.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-keys-shortcode",
        "detected_module": "gdtest_keys_shortcode",
        "detected_parser": "numpy",
        "export_names": ["render", "transform"],
        "num_exports": 2,
        "has_user_guide": True,
        "user_guide_files": [
            "single-keys.qmd",
            "shortcut-combos.qmd",
            "platform-aware.qmd",
            "keys-in-context.qmd",
        ],
        # Content assertions for dedicated tests
        "files_contain": {
            "great-docs/_site/user-guide/single-keys.html": [
                "gd-keys",  # CSS class on kbd elements
                "gd-keys-fn",  # function key compact styling
                "Single Keys",  # page title
            ],
            "great-docs/_site/user-guide/shortcut-combos.html": [
                "gd-keys",
                "gd-keys-sep",  # separator between combo keys
                "Shortcut Combos",
            ],
            "great-docs/_site/user-guide/platform-aware.html": [
                "gd-keys",
                "Platform-Aware Rendering",
            ],
            "great-docs/_site/user-guide/keys-in-context.html": [
                "gd-keys",
                "Keys in Context",
            ],
        },
        "coverage_exclude": ["nodoc", "bigcl", "supp", "sechdg", "sbsec", "hdg"],
    },
}
