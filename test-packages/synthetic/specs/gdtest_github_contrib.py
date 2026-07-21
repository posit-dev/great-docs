"""
gdtest_github_contrib — CONTRIBUTING.md in .github/ directory.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H3
Focus: .github/CONTRIBUTING.md fallback path (no root-level CONTRIBUTING.md).
Tests the core.py logic that checks both root and .github/ for CONTRIBUTING.md.
"""

SPEC = {
    "name": "gdtest_github_contrib",
    "description": "CONTRIBUTING.md in .github/ subdirectory only",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-github-contrib",
            "version": "0.1.0",
            "description": "A package with .github/CONTRIBUTING.md",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_github_contrib/__init__.py": '''\
            """A package with contributing guide in .github/ directory."""

            __version__ = "0.1.0"
            __all__ = ["process", "validate"]


            def process(data: list) -> list:
                """
                Process incoming data.

                Parameters
                ----------
                data
                    The data to process.

                Returns
                -------
                list
                    Processed data.
                """
                return data


            def validate(item: str) -> bool:
                """
                Validate a single item.

                Parameters
                ----------
                item
                    The item to validate.

                Returns
                -------
                bool
                    True if valid.
                """
                return bool(item)
        ''',
        ".github/CONTRIBUTING.md": """\
            # Contributing to gdtest-github-contrib

            Thank you for considering contributing!

            ## Getting Started

            1. Fork the repo
            2. Create a branch
            3. Make your changes
            4. Submit a PR

            ## Code of Conduct

            Please be respectful.
        """,
        "README.md": """\
            # gdtest-github-contrib

            A test package with .github/CONTRIBUTING.md.
        """,
    },
    "expected": {
        "detected_name": "gdtest-github-contrib",
        "detected_module": "gdtest_github_contrib",
        "detected_parser": "numpy",
        "export_names": ["process", "validate"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_contributing_page": True,
        "contributing_in_github_dir": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "hdg"],
    },
}
