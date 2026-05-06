"""
gdtest_many_guides — 10 user guide pages.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7
Focus: Large number of user guide pages to stress-test sidebar rendering.
       All 10 pages should appear in order.
"""

SPEC = {
    "name": "gdtest_many_guides",
    "description": "User guide with 10 pages",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-many-guides",
            "version": "0.1.0",
            "description": "Test large user guide",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_many_guides/__init__.py": '''\
            """Package with many user guide pages."""

            __version__ = "0.1.0"
            __all__ = ["run_app"]


            def run_app() -> None:
                """
                Run the application.

                Returns
                -------
                None
                """
                pass
        ''',
        **{
            f"user_guide/{i:02d}-{title}.qmd": f"""\
            ---
            title: "{label}"
            ---

            ## {label}

            Content for the {label.lower()} guide page.
        """
            for i, (title, label) in enumerate(
                [
                    ("introduction", "Introduction"),
                    ("installation", "Installation"),
                    ("quickstart", "Quick Start"),
                    ("configuration", "Configuration"),
                    ("basic-usage", "Basic Usage"),
                    ("advanced-usage", "Advanced Usage"),
                    ("plugins", "Plugins"),
                    ("deployment", "Deployment"),
                    ("troubleshooting", "Troubleshooting"),
                    ("appendix", "Appendix"),
                ],
                start=1,
            )
        },
        "README.md": """\
            # gdtest-many-guides

            Tests user guide with 10 pages.
        """,
    },
    "expected": {
        "detected_name": "gdtest-many-guides",
        "detected_module": "gdtest_many_guides",
        "detected_parser": "numpy",
        "export_names": ["run_app"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
