"""
gdtest_minimal — Absolute minimum viable package.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: 2 functions with NumPy docstrings, flat layout, README.md,
       and nothing else.  The baseline "does it work at all?" test.
"""

SPEC = {
    "name": "gdtest_minimal",
    "description": "Absolute minimum viable package",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-minimal",
            "version": "0.1.0",
            "description": "A minimal synthetic test package for Great Docs",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "gdtest_minimal/__init__.py": '''\
            """A minimal test package for Great Docs."""

            __version__ = "0.1.0"
            __all__ = ["greet", "add"]


            def greet(name: str) -> str:
                """
                Greet someone by name.

                Parameters
                ----------
                name
                    The name of the person to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"


            def add(a: int, b: int) -> int:
                """
                Add two numbers.

                Parameters
                ----------
                a
                    First number.
                b
                    Second number.

                Returns
                -------
                int
                    The sum of a and b.
                """
                return a + b
        ''',
        "README.md": """\
            # gdtest-minimal

            A minimal synthetic test package for Great Docs.

            ## Installation

            ```bash
            pip install gdtest-minimal
            ```

            ## Usage

            ```python
            from gdtest_minimal import greet, add

            greet("World")
            add(1, 2)
            ```
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-minimal",
        "detected_module": "gdtest_minimal",
        "detected_parser": "numpy",
        "export_names": ["greet", "add"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        # Baseline "does it work?" test — only functions, no classes/UG/extras/nodoc
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
