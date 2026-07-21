"""
gdtest_user_guide_hyphen — Hyphenated user guide directory name.

Dimensions: A1, B1, C1, D1, E6, F7, G1, H7
Focus: Uses user-guide/ (hyphen) instead of user_guide/ (underscore).
       Tests user-guide/ fallback when user_guide/ doesn't exist.
"""

SPEC = {
    "name": "gdtest_user_guide_hyphen",
    "description": "user-guide/ (hyphenated) directory name",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F7", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-hyphen",
            "version": "0.1.0",
            "description": "A synthetic test package with hyphenated user guide dir",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_user_guide_hyphen/__init__.py": '''\
            """A test package with hyphenated user guide directory."""

            __version__ = "0.1.0"
            __all__ = ["launch", "dock"]


            def launch(target: str) -> bool:
                """
                Launch a target.

                Parameters
                ----------
                target
                    The target to launch.

                Returns
                -------
                bool
                    True if launched.
                """
                return True


            def dock() -> None:
                """
                Dock the current process.
                """
                pass
        ''',
        "user-guide/01-intro.qmd": """\
            ---
            title: Introduction
            ---

            Welcome! Note the hyphenated directory name.
        """,
        "README.md": """\
            # gdtest-user-guide-hyphen

            A synthetic test package with ``user-guide/`` directory.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-hyphen",
        "detected_module": "gdtest_user_guide_hyphen",
        "detected_parser": "numpy",
        "export_names": ["launch", "dock"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-intro.qmd"],
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
