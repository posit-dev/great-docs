"""
gdtest_reexports — Re-exports from submodules via __init__.py.

Dimensions: A1, B6, C24, D1, E6, F6, G1, H7
Focus: Package with submodules where __init__.py re-exports symbols
       from core.py and utils.py via __all__.
"""

SPEC = {
    "name": "gdtest_reexports",
    "description": "Submodule re-exports via __init__.py",
    "dimensions": ["A1", "B6", "C24", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-reexports",
            "version": "0.1.0",
            "description": "Test re-export documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_reexports/__init__.py": '''\
            """Package that re-exports from submodules."""

            __version__ = "0.1.0"

            from gdtest_reexports.core import Engine, run
            from gdtest_reexports.utils import format_result, parse_input

            __all__ = ["Engine", "run", "format_result", "parse_input"]
        ''',
        "gdtest_reexports/core.py": '''\
            """Core module with engine logic."""


            class Engine:
                """
                Core processing engine.

                Parameters
                ----------
                name
                    Engine name.
                """

                def __init__(self, name: str):
                    self.name = name

                def execute(self) -> dict:
                    """
                    Execute the engine.

                    Returns
                    -------
                    dict
                        Execution result.
                    """
                    return {"engine": self.name, "status": "ok"}


            def run(engine: Engine) -> dict:
                """
                Run an engine instance.

                Parameters
                ----------
                engine
                    Engine to run.

                Returns
                -------
                dict
                    Run result.
                """
                return engine.execute()
        ''',
        "gdtest_reexports/utils.py": '''\
            """Utility functions."""


            def format_result(result: dict) -> str:
                """
                Format a result dictionary for display.

                Parameters
                ----------
                result
                    Result to format.

                Returns
                -------
                str
                    Formatted string.
                """
                return str(result)


            def parse_input(text: str) -> dict:
                """
                Parse raw input text into a dictionary.

                Parameters
                ----------
                text
                    Raw input text.

                Returns
                -------
                dict
                    Parsed data.
                """
                return {"raw": text}
        ''',
        "README.md": """\
            # gdtest-reexports

            Tests re-exports from submodules via __init__.py __all__.
        """,
    },
    "expected": {
        "detected_name": "gdtest-reexports",
        "detected_module": "gdtest_reexports",
        "detected_parser": "numpy",
        "export_names": ["Engine", "run", "format_result", "parse_input"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
