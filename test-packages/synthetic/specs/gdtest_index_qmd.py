"""
gdtest_index_qmd — Pre-existing index.qmd.

Dimensions: A1, B1, C1, D1, E6, F6, G3, H7
Focus: Has index.qmd (custom landing page). It should be used as-is
       with no README processing.
"""

SPEC = {
    "name": "gdtest_index_qmd",
    "description": "index.qmd — used as-is, no generation",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G3", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-index-qmd",
            "version": "0.1.0",
            "description": "A synthetic test package with index.qmd",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_index_qmd/__init__.py": '''\
            """A test package with index.qmd."""

            __version__ = "0.1.0"
            __all__ = ["hello"]


            def hello() -> str:
                """
                Say hello.

                Returns
                -------
                str
                    A greeting.
                """
                return "Hello!"
        ''',
        "index.qmd": """\
            ---
            title: Custom Landing Page
            ---

            This is a custom landing page written in Quarto markdown.

            ## Features

            - Feature A
            - Feature B

            ```{python}
            print("Hello from index.qmd!")
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-index-qmd",
        "detected_module": "gdtest_index_qmd",
        "detected_parser": "numpy",
        "export_names": ["hello"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
