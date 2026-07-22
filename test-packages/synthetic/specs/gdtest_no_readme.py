"""
gdtest_no_readme — No README or index file at all.

Dimensions: A1, B1, C1, D1, E6, F6, G5, H7
Focus: Only pyproject.toml with description field, no landing page source.
       Tests auto-generated landing page from project description.
"""

SPEC = {
    "name": "gdtest_no_readme",
    "description": "No README — auto-generated landing page",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G5", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-no-readme",
            "version": "0.1.0",
            "description": "A synthetic test package with no README file",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_no_readme/__init__.py": '''\
            """A test package with no README."""

            __version__ = "0.1.0"
            __all__ = ["noop"]


            def noop() -> None:
                """
                Do nothing.

                Returns
                -------
                None
                """
                pass
        ''',
    },
    "expected": {
        "detected_name": "gdtest-no-readme",
        "detected_module": "gdtest_no_readme",
        "detected_parser": "numpy",
        "export_names": ["noop"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
