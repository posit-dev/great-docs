"""
gdtest_python_layout — python/ layout convention.

Dimensions: A3, B1, C1, D1, E6, F6, G1, H7
Focus: Package code lives under python/<pkg>/.
       Tests _find_package_init detection of python/ directory.
"""

SPEC = {
    "name": "gdtest_python_layout",
    "description": "python/ layout convention",
    "dimensions": ["A3", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-python-layout",
            "version": "0.1.0",
            "description": "A synthetic test package using python/ layout",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "python/gdtest_python_layout/__init__.py": '''\
            """A test package using the python/ layout convention."""

            __version__ = "0.1.0"
            __all__ = ["read_file", "write_file"]


            def read_file(path: str) -> str:
                """
                Read contents of a file.

                Parameters
                ----------
                path
                    Path to the file.

                Returns
                -------
                str
                    File contents.
                """
                return ""


            def write_file(path: str, content: str) -> None:
                """
                Write content to a file.

                Parameters
                ----------
                path
                    Path to the file.
                content
                    Content to write.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-python-layout

            A synthetic test package using the ``python/`` layout convention.
        """,
    },
    "expected": {
        "detected_name": "gdtest-python-layout",
        "detected_module": "gdtest_python_layout",
        "detected_parser": "numpy",
        "export_names": ["read_file", "write_file"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
