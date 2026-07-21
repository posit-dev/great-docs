"""
gdtest_mixed_guide_ext — User guide with mixed .qmd and .md files.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7
Focus: User guide directory containing both .qmd and .md files to
       verify both extensions are discovered and rendered.
"""

SPEC = {
    "name": "gdtest_mixed_guide_ext",
    "description": "User guide with mixed .qmd and .md files",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-mixed-guide-ext",
            "version": "0.1.0",
            "description": "Test mixed guide file extensions",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_mixed_guide_ext/__init__.py": '''\
            """Package with mixed guide file extensions."""

            __version__ = "0.1.0"
            __all__ = ["process"]


            def process(data: str) -> str:
                """
                Process input data.

                Parameters
                ----------
                data
                    Input data.

                Returns
                -------
                str
                    Processed data.
                """
                return data
        ''',
        "user_guide/01-intro.qmd": """\
            ---
            title: Introduction
            ---

            ## Introduction

            This is a .qmd guide page.
        """,
        "user_guide/02-setup.md": """\
            ---
            title: Setup
            ---

            ## Setup

            This is a .md guide page.
        """,
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced
            ---

            ## Advanced Topics

            This is another .qmd guide page.
        """,
        "README.md": """\
            # gdtest-mixed-guide-ext

            Tests user guide with mixed .qmd and .md file extensions.
        """,
    },
    "expected": {
        "detected_name": "gdtest-mixed-guide-ext",
        "detected_module": "gdtest_mixed_guide_ext",
        "detected_parser": "numpy",
        "export_names": ["process"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
