"""
gdtest_nodocs — Objects with no docstrings at all.

Dimensions: A1, B1, C4, D4, E6, F6, G1, H7
Focus: 3 functions + 1 class, all with empty or missing docstrings.
       Tests graceful handling when no docstrings are found.
       Also tests that the page footer text is not pulled into headers.
"""

SPEC = {
    "name": "gdtest_nodocs",
    "description": "Objects with no docstrings",
    "dimensions": ["A1", "B1", "C4", "D4", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-nodocs",
            "version": "0.1.0",
            "description": "A synthetic test package with no docstrings",
            "authors": [
                {"name": "Alice Tester"},
                {"name": "Bob Builder"},
            ],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_nodocs/__init__.py": """\
            __version__ = "0.1.0"
            __all__ = ["Processor", "run", "stop", "status"]


            class Processor:
                def __init__(self, name: str):
                    self.name = name

                def execute(self) -> bool:
                    return True


            def run(task: str) -> bool:
                return True


            def stop(task: str) -> None:
                pass


            def status() -> str:
                return "idle"
        """,
        "README.md": """\
            # gdtest-nodocs

            A synthetic test package with no docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-nodocs",
        "detected_module": "gdtest_nodocs",
        "detected_parser": "numpy",
        "export_names": ["Processor", "run", "stop", "status"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'desc', 'param', 'ret'],
},
}
