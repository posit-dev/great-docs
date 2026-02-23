"""
gdtest_display_badges — Complex README with markdown badges.

Dimensions: Q7
Focus: README.md containing shields.io badge syntax, tables, and feature lists.
"""

SPEC = {
    "name": "gdtest_display_badges",
    "description": "Complex README with markdown badges.",
    "dimensions": ["Q7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-display-badges",
            "version": "0.1.0",
            "description": "A package with badge-rich README.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_display_badges/__init__.py": '''\
            """Package with badge-rich README."""

            __all__ = ["badge", "shield"]


            def badge(label: str, value: str) -> str:
                """Create a badge string from a label and value.

                Parameters
                ----------
                label : str
                    The badge label text.
                value : str
                    The badge value text.

                Returns
                -------
                str
                    A formatted badge string.

                Examples
                --------
                >>> badge("version", "0.1.0")
                'version: 0.1.0'
                """
                return f"{label}: {value}"


            def shield(name: str) -> dict:
                """Get shield metadata by name.

                Parameters
                ----------
                name : str
                    The shield name to look up.

                Returns
                -------
                dict
                    A dictionary with shield metadata.

                Examples
                --------
                >>> shield("python")
                {'name': 'python', 'color': 'green'}
                """
                return {"name": name, "color": "green"}
        ''',
        "README.md": (
            "# gdtest-v2-display-badges\n"
            "\n"
            "![Version](https://img.shields.io/badge/version-0.1.0-blue)\n"
            "![Python](https://img.shields.io/badge/python-3.9+-green)\n"
            "![License](https://img.shields.io/badge/license-MIT-orange)\n"
            "\n"
            "A package with badge-rich README.\n"
            "\n"
            "## Features\n"
            "\n"
            "- Feature one\n"
            "- Feature two\n"
            "\n"
            "| Column A | Column B |\n"
            "|----------|----------|\n"
            "| Value 1  | Value 2  |\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-display-badges",
        "detected_module": "gdtest_display_badges",
        "detected_parser": "numpy",
        "export_names": ["badge", "shield"],
        "num_exports": 2,
    },
}
