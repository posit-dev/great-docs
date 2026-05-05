"""
gdtest_user_guide_explicit — Explicit user guide ordering via config.

Dimensions: A1, B1, C1, D1, E6, F4, G1, H7
Focus: Uses config user_guide: list to explicitly order guide pages.
       Tests config-driven ordering, text key for custom titles.
"""

SPEC = {
    "name": "gdtest_user_guide_explicit",
    "description": "Explicit user guide ordering via config",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F4", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-explicit",
            "version": "0.1.0",
            "description": "A synthetic test package with explicit user guide ordering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": [
            {
                "section": "Get Started",
                "contents": [
                    {"text": "Welcome", "href": "intro.qmd"},
                    "quickstart.qmd",
                ],
            },
            {
                "section": "Advanced",
                "contents": [
                    "advanced.qmd",
                ],
            },
        ],
    },
    "files": {
        "gdtest_user_guide_explicit/__init__.py": '''\
            """A test package with explicit user guide ordering."""

            __version__ = "0.1.0"
            __all__ = ["run", "stop"]


            def run() -> None:
                """
                Run the process.

                Returns
                -------
                None
                """
                pass


            def stop() -> None:
                """
                Stop the process.

                Returns
                -------
                None
                """
                pass
        ''',
        "user_guide/intro.qmd": """\
            ---
            title: Introduction
            ---

            Welcome to the project!
        """,
        "user_guide/quickstart.qmd": """\
            ---
            title: Quick Start
            ---

            Get started quickly.
        """,
        "user_guide/advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            Advanced topics.
        """,
        "README.md": """\
            # gdtest-user-guide-explicit

            A synthetic test package with explicit user guide ordering.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-explicit",
        "detected_module": "gdtest_user_guide_explicit",
        "detected_parser": "numpy",
        "export_names": ["run", "stop"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "user_guide_files": ["advanced.qmd", "intro.qmd", "quickstart.qmd"],
        "coverage_exclude": ['nodoc', 'bigcl', 'supp', 'hdg'],
},
}
