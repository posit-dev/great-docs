"""
gdtest_sec_dir_titles — Custom section with dir_titles and numeric-prefix subdirectories.

Dimensions: N11
Focus: Subdirectory sidebar titles: numeric prefix stripping and custom dir_titles mapping.
"""

SPEC = {
    "name": "gdtest_sec_dir_titles",
    "description": "Custom section with dir_titles overrides and numeric-prefix subdirectories.",
    "dimensions": ["N11"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-dir-titles",
            "version": "0.1.0",
            "description": "Test dir_titles and numeric prefix stripping in section sidebars.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {
                "title": "Demos",
                "dir": "demos",
                "index": True,
                "dir_titles": {
                    "getting-started": "Getting Started",
                    "results-and-reporting": "Results/Reporting",
                    "advanced-topics": "Advanced Topics",
                },
            },
        ],
    },
    "files": {
        "gdtest_sec_dir_titles/__init__.py": (
            '"""Test package for dir_titles in section sidebars."""\n'
            "\n"
            "from .core import run_demo, show_results\n"
            "\n"
            '__all__ = ["run_demo", "show_results"]\n'
        ),
        "gdtest_sec_dir_titles/core.py": '''
            """Core demo functions."""


            def run_demo(name: str) -> str:
                """Run a demo by name.

                Parameters
                ----------
                name : str
                    The name of the demo to run.

                Returns
                -------
                str
                    A summary of the demo run.

                Examples
                --------
                >>> run_demo("starter")
                'Running demo: starter'
                """
                return f"Running demo: {name}"


            def show_results(data: list) -> str:
                """Show results from a demo run.

                Parameters
                ----------
                data : list
                    A list of result values.

                Returns
                -------
                str
                    Formatted results string.

                Examples
                --------
                >>> show_results([1, 2, 3])
                'Results: [1, 2, 3]'
                """
                return f"Results: {data}"
        ''',
        # Subdirectories with numeric prefixes — tests prefix stripping
        "demos/01-getting-started/installation.qmd": (
            "---\n"
            "title: Installation\n"
            "description: How to install the package.\n"
            "---\n"
            "\n"
            "# Installation\n"
            "\n"
            "Install with pip:\n"
            "\n"
            "```bash\n"
            "pip install gdtest-sec-dir-titles\n"
            "```\n"
        ),
        "demos/01-getting-started/first-steps.qmd": (
            "---\n"
            "title: First Steps\n"
            "description: Your first steps with the package.\n"
            "---\n"
            "\n"
            "# First Steps\n"
            "\n"
            "Start by importing the package and running a basic demo.\n"
        ),
        # dir_titles maps this to "Results/Reporting" instead of "Results And Reporting"
        "demos/02-results-and-reporting/basic-report.qmd": (
            "---\n"
            "title: Basic Report\n"
            "description: Generate a basic results report.\n"
            "---\n"
            "\n"
            "# Basic Report\n"
            "\n"
            "Use `show_results()` to display output.\n"
        ),
        "demos/02-results-and-reporting/custom-output.qmd": (
            "---\n"
            "title: Custom Output\n"
            "description: Customize the output format.\n"
            "---\n"
            "\n"
            "# Custom Output\n"
            "\n"
            "Override the default formatting.\n"
        ),
        # dir_titles maps this to "Advanced Topics"
        "demos/03-advanced-topics/tips-and-tricks.qmd": (
            "---\n"
            "title: Tips and Tricks\n"
            "description: Advanced tips for power users.\n"
            "---\n"
            "\n"
            "# Tips and Tricks\n"
            "\n"
            "Explore advanced patterns and optimizations.\n"
        ),
        "README.md": (
            "# gdtest-sec-dir-titles\n"
            "\n"
            "Test dir_titles and numeric prefix stripping in section sidebars.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-sec-dir-titles",
        "detected_module": "gdtest_sec_dir_titles",
        "detected_parser": "numpy",
        "export_names": ["run_demo", "show_results"],
        "num_exports": 2,
    },
}
