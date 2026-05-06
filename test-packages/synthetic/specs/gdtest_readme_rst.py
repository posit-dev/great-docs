"""
gdtest_readme_rst — README.rst conversion.

Dimensions: A1, B1, C1, D1, E6, F6, G2, H7
Focus: Has README.rst (no .md). Tests RST → QMD conversion.
"""

SPEC = {
    "name": "gdtest_readme_rst",
    "description": "README.rst — RST conversion",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G2", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-readme-rst",
            "version": "0.1.0",
            "description": "A synthetic test package with README.rst",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_readme_rst/__init__.py": '''\
            """A test package with README.rst."""

            __version__ = "0.1.0"
            __all__ = ["convert", "parse"]


            def convert(text: str, fmt: str = "html") -> str:
                """
                Convert text to a target format.

                Parameters
                ----------
                text
                    Input text.
                fmt
                    Target format.

                Returns
                -------
                str
                    Converted text.
                """
                return text


            def parse(text: str) -> dict:
                """
                Parse structured text.

                Parameters
                ----------
                text
                    Input text.

                Returns
                -------
                dict
                    Parsed structure.
                """
                return {}
        ''',
        "README.rst": """\
            gdtest-readme-rst
            =================

            A synthetic test package with ``README.rst``.

            Installation
            ------------

            .. code-block:: bash

                pip install gdtest-readme-rst

            Usage
            -----

            .. code-block:: python

                from gdtest_readme_rst import convert
                convert("hello", "html")
        """,
    },
    "expected": {
        "detected_name": "gdtest-readme-rst",
        "detected_module": "gdtest_readme_rst",
        "detected_parser": "numpy",
        "export_names": ["convert", "parse"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
