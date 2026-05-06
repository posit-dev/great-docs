"""
gdtest_homepage_ug — Blended user-guide homepage mode.

Dimensions: A1, B1, C1, D1, E6, F1, G7, H7
Focus: Uses ``homepage: user_guide`` config so the first user-guide page
       becomes the site landing page (index.qmd) with the metadata sidebar.
       The sidebar links the first entry to ``index.qmd`` and no separate
       "User Guide" navbar item appears.
"""

SPEC = {
    "name": "gdtest_homepage_ug",
    "description": "Blended user-guide homepage mode (homepage: user_guide)",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G7", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-homepage-ug",
            "version": "0.1.0",
            "description": "A synthetic test package for blended homepage mode",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "homepage": "user_guide",
    },
    "files": {
        "gdtest_homepage_ug/__init__.py": '''\
            """A test package for blended homepage mode."""

            __version__ = "0.1.0"
            __all__ = ["greet", "farewell"]


            def greet(name: str) -> str:
                """
                Greet someone.

                Parameters
                ----------
                name
                    The name to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"


            def farewell(name: str) -> str:
                """
                Say farewell to someone.

                Parameters
                ----------
                name
                    The name to bid farewell.

                Returns
                -------
                str
                    A farewell string.
                """
                return f"Goodbye, {name}!"
        ''',
        "user_guide/00-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            # Getting Started

            Welcome to the project! This is the first user guide page and will
            become the site landing page in blended homepage mode.

            ## Installation

            Install with pip:

            ```bash
            pip install gdtest-homepage-ug
            ```
        """,
        "user_guide/01-configuration.qmd": """\
            ---
            title: Configuration
            ---

            # Configuration

            Learn how to configure the package.

            ## Basic Setup

            Create a config file and set your options.
        """,
        "user_guide/02-advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            # Advanced Usage

            Explore advanced topics and customization.
        """,
        "README.md": """\
            # gdtest-homepage-ug

            A synthetic test package for blended homepage mode.
        """,
    },
    "expected": {
        "detected_name": "gdtest-homepage-ug",
        "detected_module": "gdtest_homepage_ug",
        "detected_parser": "numpy",
        "export_names": ["farewell", "greet"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "00-getting-started.qmd",
            "01-configuration.qmd",
            "02-advanced.qmd",
        ],
        # ── Blended-homepage-specific expectations ──
        "homepage_mode": "user_guide",
        # index.qmd should contain the first UG page content
        "index_contains": [
            "Getting Started",
            "Welcome to the project!",
            "gd-meta-sidebar",
        ],
        # The first UG page should NOT exist as a separate file
        "index_not_exists": [
            "user-guide/getting-started.qmd",
        ],
        # Remaining UG pages should still exist
        "ug_pages_exist": [
            "user-guide/configuration.qmd",
            "user-guide/advanced.qmd",
        ],
        # Navbar should NOT have a "User Guide" link
        "navbar_absent_texts": ["User Guide"],
        # Sidebar first entry should point to index.qmd
        "sidebar_first_href": "index.qmd",
        "coverage_exclude": ['nodoc', 'bigcl', 'supp', 'hdg'],
},
}
