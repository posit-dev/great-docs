"""
gdtest_homepage_ug_subdirs — Blended homepage with subdirectory user guide and section assets.

Dimensions: G7, M4, N1
Focus: Combines ``homepage: user_guide`` with a user guide that has subdirectories
       (including a root index.qmd) and a custom section whose source directory
       contains non-.qmd asset subdirectories (data/, img/).

       Exercises three bugs fixed together:
       1. _discover_user_guide() sorted by filename only, causing a numbered
          file in a subdirectory to beat root index.qmd to first position.
       2. _create_blended_index() used only the filename (not the full relative
          path) to locate the first user-guide page after copying, failing when
          the page lived inside a subdirectory.
       3. _process_sections() never copied asset subdirectories (directories
          without .qmd files), breaking relative paths from section pages.
"""

SPEC = {
    "name": "gdtest_homepage_ug_subdirs",
    "description": (
        "Blended homepage: user_guide with subdirectory structure + section with asset directories"
    ),
    "dimensions": ["G7", "M4", "N1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-homepage-ug-subdirs",
            "version": "0.1.0",
            "description": "Test blended homepage with subdir UG and section assets",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "homepage": "user_guide",
        "sections": [
            {"title": "Examples", "dir": "examples"},
        ],
    },
    "files": {
        # ── Package source ────────────────────────────────────────────────
        "gdtest_homepage_ug_subdirs/__init__.py": '''\
            """A test package for blended homepage with subdir user guide."""

            __version__ = "0.1.0"
            __all__ = ["process", "analyze"]


            def process(data: list) -> list:
                """
                Process a list of data items.

                Parameters
                ----------
                data
                    The input data to process.

                Returns
                -------
                list
                    The processed data.
                """
                return [x * 2 for x in data]


            def analyze(data: list) -> dict:
                """
                Analyze a list of data items.

                Parameters
                ----------
                data
                    The input data to analyze.

                Returns
                -------
                dict
                    Analysis results.
                """
                return {"count": len(data), "sum": sum(data)}
        ''',
        # ── User guide: root index + numbered subdirectories ──────────────
        "user_guide/index.qmd": (
            "---\n"
            "title: Welcome\n"
            "---\n"
            "\n"
            "# Welcome\n"
            "\n"
            "Welcome to the project documentation! This root index page should\n"
            "become the site landing page in blended homepage mode.\n"
            "\n"
            "## Overview\n"
            "\n"
            "This project provides data processing and analysis utilities.\n"
        ),
        "user_guide/00-getting-started/index.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "This section covers installation and basic setup.\n"
        ),
        "user_guide/00-getting-started/01-quickstart.qmd": (
            "---\n"
            "title: Quickstart\n"
            "---\n"
            "\n"
            "# Quickstart\n"
            "\n"
            "Get up and running in minutes.\n"
            "\n"
            "```python\n"
            "from gdtest_homepage_ug_subdirs import process\n"
            "result = process([1, 2, 3])\n"
            "```\n"
        ),
        "user_guide/01-advanced/01-analysis.qmd": (
            "---\n"
            "title: Analysis\n"
            "---\n"
            "\n"
            "# Analysis\n"
            "\n"
            "Learn how to use the analyze function for data insights.\n"
        ),
        # ── Custom section with asset subdirectories ──────────────────────
        "examples/01-basic-usage.qmd": (
            "---\n"
            "title: Basic Usage\n"
            "---\n"
            "\n"
            "# Basic Usage\n"
            "\n"
            "A simple example reading data from a local file.\n"
            "\n"
            "The data file is located at `../data/sample.csv`.\n"
        ),
        "examples/02-advanced-patterns.qmd": (
            "---\n"
            "title: Advanced Patterns\n"
            "---\n"
            "\n"
            "# Advanced Patterns\n"
            "\n"
            "An advanced example using images and data.\n"
            "\n"
            "![Diagram](../img/diagram.txt)\n"
        ),
        # Asset subdirectories (no .qmd files) — must be copied to build dir
        "examples/data/sample.csv": "name,value\nalpha,1\nbeta,2\ngamma,3\n",
        "examples/img/diagram.txt": "placeholder-diagram-content\n",
        # ── README ────────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-homepage-ug-subdirs\n"
            "\n"
            "Test blended homepage with subdir UG and section assets.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-homepage-ug-subdirs",
        "detected_module": "gdtest_homepage_ug_subdirs",
        "detected_parser": "numpy",
        "export_names": ["analyze", "process"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        # ── Blended-homepage expectations ─────────────────────────────────
        "homepage_mode": "user_guide",
        # Root index.qmd should become the site landing page
        "index_contains": [
            "Welcome",
            "Welcome to the project documentation!",
            "gd-meta-sidebar",
        ],
        # The promoted page should NOT remain in user-guide/
        "index_not_exists": [
            "user-guide/index.qmd",
        ],
        # Remaining UG pages should still exist (prefix-stripped paths)
        "ug_pages_exist": [
            "user-guide/getting-started/index.qmd",
            "user-guide/getting-started/quickstart.qmd",
            "user-guide/advanced/analysis.qmd",
        ],
        # Navbar should NOT have a "User Guide" link in blended mode
        "navbar_absent_texts": ["User Guide"],
        # Sidebar first entry should point to index.qmd (promoted root)
        "sidebar_first_href": "index.qmd",
        # ── Section asset directory expectations ──────────────────────────
        # Asset subdirectories must be copied to the build dir
        "section_asset_dirs": [
            "examples/data",
            "examples/img",
        ],
        "section_asset_files": [
            "examples/data/sample.csv",
            "examples/img/diagram.txt",
        ],
    },
}
