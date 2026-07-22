"""
gdtest_extras_guide — Full supporting pages + user guide.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H1, H2, H3, H4
Focus: All four supporting pages (LICENSE, CITATION.cff, CONTRIBUTING.md,
       CODE_OF_CONDUCT.md) combined with a user guide.
"""

SPEC = {
    "name": "gdtest_extras_guide",
    "description": "Full extras (license, citation, etc.) plus user guide",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H1", "H2", "H3", "H4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-extras-guide",
            "version": "0.1.0",
            "description": "Test all extras with user guide",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_extras_guide/__init__.py": '''\
            """Package with full extras and user guide."""

            __version__ = "0.1.0"
            __all__ = ["start", "stop"]


            def start() -> None:
                """
                Start the service.

                Returns
                -------
                None
                """
                pass


            def stop() -> None:
                """
                Stop the service.

                Returns
                -------
                None
                """
                pass
        ''',
        "user_guide/01-intro.qmd": """\
            ---
            title: Introduction
            ---

            Welcome to the extras-guide package.
        """,
        "user_guide/02-config.qmd": """\
            ---
            title: Configuration
            ---

            Configuration details for the extras-guide package.
        """,
        "LICENSE": """\
            MIT License

            Copyright (c) 2024 Test Author
        """,
        "CITATION.cff": """\
            cff-version: 1.2.0
            title: gdtest-extras-guide
            message: "Please cite this software."
            authors:
              - family-names: Author
                given-names: Test
        """,
        "CONTRIBUTING.md": """\
            # Contributing

            Thank you for contributing!

            ## How to contribute

            1. Fork the repository
            2. Create a branch
            3. Submit a pull request
        """,
        "CODE_OF_CONDUCT.md": """\
            # Code of Conduct

            Be kind and respectful.
        """,
        "README.md": """\
            # gdtest-extras-guide

            Tests all supporting pages combined with a user guide.
        """,
    },
    "expected": {
        "detected_name": "gdtest-extras-guide",
        "detected_module": "gdtest_extras_guide",
        "detected_parser": "numpy",
        "export_names": ["start", "stop"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "has_license_page": True,
        "has_citation_page": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "hdg"],
    },
}
