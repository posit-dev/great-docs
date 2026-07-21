"""
gdtest_index_md — index.md takes priority over README.md.

Dimensions: A1, B1, C1, D1, E6, F6, G4, H7
Focus: Both index.md and README.md exist. index.md should win.
       Tests priority order: index.qmd > index.md > README.md.
"""

SPEC = {
    "name": "gdtest_index_md",
    "description": "index.md — priority over README.md",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G4", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-index-md",
            "version": "0.1.0",
            "description": "A synthetic test package with index.md",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_index_md/__init__.py": '''\
            """A test package with index.md."""

            __version__ = "0.1.0"
            __all__ = ["greet"]


            def greet(name: str) -> str:
                """
                Greet someone.

                Parameters
                ----------
                name
                    Who to greet.

                Returns
                -------
                str
                    Greeting message.
                """
                return f"Hi, {name}!"
        ''',
        "index.md": """\
            # Custom Index

            This is index.md and should take priority over README.md.
        """,
        "README.md": """\
            # README

            This README should be ignored in favor of index.md.
        """,
    },
    "expected": {
        "detected_name": "gdtest-index-md",
        "detected_module": "gdtest_index_md",
        "detected_parser": "numpy",
        "export_names": ["greet"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
