"""
gdtest_sec_sidebar_single — Section sidebar visibility for single-page sections.

Dimensions: N9
Focus: Two custom sections — one with 2 pages (sidebar visible) and one with
       only 1 page (sidebar should be hidden, content takes full width).
"""

SPEC = {
    "name": "gdtest_sec_sidebar_single",
    "description": "Section sidebar: hidden for single-page sections, visible for multi-page.",
    "dimensions": ["N9"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-sidebar-single",
            "version": "0.1.0",
            "description": "Test sidebar visibility for single vs multi-page sections.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Guides", "dir": "guides"},
            {"title": "FAQ", "dir": "faq"},
        ],
    },
    "files": {
        # ── Python module ──────────────────────────────────────────────────
        "gdtest_sec_sidebar_single/__init__.py": (
            '"""Test package for section sidebar visibility."""\n'
            "\n"
            "from .core import hello, goodbye\n"
            "\n"
            '__all__ = ["hello", "goodbye"]\n'
        ),
        "gdtest_sec_sidebar_single/core.py": (
            '"""Core functions."""\n'
            "\n"
            "\n"
            "def hello(name: str) -> str:\n"
            '    """Say hello.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name : str\n"
            "        Who to greet.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        A greeting.\n"
            '    """\n'
            '    return f"Hello, {name}!"\n'
            "\n"
            "\n"
            "def goodbye(name: str) -> str:\n"
            '    """Say goodbye.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name : str\n"
            "        Who to bid farewell.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        A farewell.\n"
            '    """\n'
            '    return f"Goodbye, {name}!"\n'
        ),
        # ── Guides section: 2 pages (sidebar should be visible) ───────────
        "guides/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "This guide walks you through the basics of the package.\n"
            "\n"
            "## Installation\n"
            "\n"
            "```bash\n"
            "pip install gdtest-sec-sidebar-single\n"
            "```\n"
            "\n"
            "## Quick Example\n"
            "\n"
            "```python\n"
            "from gdtest_sec_sidebar_single import hello\n"
            'hello("world")\n'
            "```\n"
        ),
        "guides/advanced.qmd": (
            "---\n"
            "title: Advanced Usage\n"
            "---\n"
            "\n"
            "# Advanced Usage\n"
            "\n"
            "This guide covers advanced topics and patterns.\n"
            "\n"
            "## Customization\n"
            "\n"
            "You can customize greetings by subclassing the core functions.\n"
            "\n"
            "## Integration\n"
            "\n"
            "Integrate with other tools using the standard API.\n"
        ),
        # ── FAQ section: 1 page (sidebar should be hidden) ────────────────
        "faq/questions.qmd": (
            "---\n"
            "title: Frequently Asked Questions\n"
            "---\n"
            "\n"
            "# Frequently Asked Questions\n"
            "\n"
            "## How do I install this package?\n"
            "\n"
            "Use pip: `pip install gdtest-sec-sidebar-single`\n"
            "\n"
            "## What Python versions are supported?\n"
            "\n"
            "Python 3.9 and above.\n"
            "\n"
            "## Where can I report issues?\n"
            "\n"
            "Open an issue on the GitHub repository.\n"
        ),
        # ── README ────────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-sec-sidebar-single\n"
            "\n"
            "Test sidebar visibility for single vs multi-page sections.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-sec-sidebar-single",
        "detected_module": "gdtest_sec_sidebar_single",
        "detected_parser": "numpy",
        "export_names": ["goodbye", "hello"],
        "num_exports": 2,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec', 'hdg'],
},
}
