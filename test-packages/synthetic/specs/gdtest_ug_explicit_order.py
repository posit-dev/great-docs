"""
gdtest_ug_explicit_order — Explicit user guide ordering via config.

Dimensions: M9
Focus: User guide with explicit section ordering defined in config.
"""

SPEC = {
    "name": "gdtest_ug_explicit_order",
    "description": "Explicit user guide ordering via config with titled sections and contents lists.",
    "dimensions": ["M9"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-explicit-order",
            "version": "0.1.0",
            "description": "Test explicit user guide ordering.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": [
            {"title": "First Steps", "contents": ["quickstart.qmd", "install.qmd"]},
            {"title": "Deep Dive", "contents": ["internals.qmd"]},
        ],
    },
    "files": {
        "gdtest_ug_explicit_order/__init__.py": '"""Test package for explicit user guide ordering."""\n',
        "gdtest_ug_explicit_order/core.py": '''
            """Core begin/dive functions."""


            def begin() -> None:
                """Begin the initialization process.

                Returns
                -------
                None

                Examples
                --------
                >>> begin()
                """
                pass


            def dive(topic: str) -> str:
                """Dive deep into a specific topic.

                Parameters
                ----------
                topic : str
                    The topic to explore in depth.

                Returns
                -------
                str
                    A detailed explanation of the topic.

                Examples
                --------
                >>> dive("internals")
                'Deep dive into internals'
                """
                return f"Deep dive into {topic}"
        ''',
        "user_guide/quickstart.qmd": (
            "---\n"
            "title: Quickstart\n"
            "---\n"
            "\n"
            "# Quickstart\n"
            "\n"
            "Get started quickly with a minimal example.\n"
        ),
        "user_guide/install.qmd": (
            "---\n"
            "title: Installation\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "How to install the package and its dependencies.\n"
        ),
        "user_guide/internals.qmd": (
            "---\n"
            "title: Internals\n"
            "---\n"
            "\n"
            "# Internals\n"
            "\n"
            "A deep dive into the internal architecture.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/quickstart.html",
            "great-docs/user-guide/install.html",
            "great-docs/user-guide/internals.html",
        ],
        "files_contain": {
            "great-docs/user-guide/quickstart.html": ["Quickstart", "minimal example"],
            "great-docs/user-guide/install.html": ["Installation"],
            "great-docs/user-guide/internals.html": ["Internals", "internal architecture"],
        },
    },
}
