"""
gdtest_index_wins — Both index.qmd and README.md exist.

Dimensions: A1, B1, C1, D1, E6, F6, G6, H7
Focus: index.qmd takes priority, README is ignored for landing page.
"""

SPEC = {
    "name": "gdtest_index_wins",
    "description": "index.qmd + README.md — index wins",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G6", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-index-wins",
            "version": "0.1.0",
            "description": "A synthetic test package where index.qmd wins",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_index_wins/__init__.py": '''\
            """A test package where index.qmd wins over README.md."""

            __version__ = "0.1.0"
            __all__ = ["winner"]


            def winner() -> str:
                """
                Return the winner.

                Returns
                -------
                str
                    The winning file.
                """
                return "index.qmd"
        ''',
        "index.qmd": """\
            ---
            title: Index Wins
            ---

            This index.qmd should take priority over README.md.
        """,
        "README.md": """\
            # README

            This README should be ignored because index.qmd exists.
        """,
    },
    "expected": {
        "detected_name": "gdtest-index-wins",
        "detected_module": "gdtest_index_wins",
        "detected_parser": "numpy",
        "export_names": ["winner"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
