"""
gdtest_setuptools_find — Setuptools find packages configuration.

Dimensions: A6, B1, C4, D1, E6, F6, G1, H7
Focus: Uses [tool.setuptools.packages.find] with where=["src"].
       Module name derives from scanning the src/ directory.
       Tests _detect_module_name setuptools find path.
"""

SPEC = {
    "name": "gdtest_setuptools_find",
    "description": "Setuptools find packages with where=src",
    "dimensions": ["A6", "B1", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-setuptools-find",
            "version": "0.1.0",
            "description": "A synthetic test package using setuptools find packages",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "packages": {
                    "find": {
                        "where": ["src"],
                    },
                },
            },
        },
    },
    "files": {
        "src/gdtest_stfind/__init__.py": '''\
            """A test package using setuptools find packages."""

            __version__ = "0.1.0"
            __all__ = ["Scanner", "scan", "report"]


            class Scanner:
                """
                A file scanner.

                Parameters
                ----------
                root
                    Root directory to scan.
                """

                def __init__(self, root: str = "."):
                    self.root = root

                def scan(self) -> list:
                    """
                    Scan the directory.

                    Returns
                    -------
                    list
                        List of found files.
                    """
                    return []


            def scan(path: str) -> list:
                """
                Scan a directory for files.

                Parameters
                ----------
                path
                    Directory path to scan.

                Returns
                -------
                list
                    List of file paths.
                """
                return []


            def report(results: list) -> str:
                """
                Generate a report from scan results.

                Parameters
                ----------
                results
                    List of scan results.

                Returns
                -------
                str
                    Formatted report string.
                """
                return f"Found {len(results)} items"
        ''',
        "README.md": """\
            # gdtest-setuptools-find

            A synthetic test package using setuptools ``find`` packages.
        """,
    },
    "expected": {
        "detected_name": "gdtest-setuptools-find",
        "detected_module": "gdtest_stfind",
        "detected_parser": "numpy",
        "export_names": ["Scanner", "scan", "report"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
