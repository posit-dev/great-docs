"""
gdtest_src_explicit_ref — src/ layout + explicit reference config.

Dimensions: A2, B1, C4, D1, E6, F6, G1, H7
Focus: Explicit reference sections with module discovered from src/.
       Tests that explicit config and src/ work together.
"""

SPEC = {
    "name": "gdtest_src_explicit_ref",
    "description": "src/ layout with explicit reference configuration",
    "dimensions": ["A2", "B1", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-src-explicit-ref",
            "version": "0.1.0",
            "description": "Test src/ layout with explicit reference",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "package-dir": {"": "src"},
            },
        },
    },
    "config": {
        "reference": [
            {
                "title": "Core",
                "contents": ["Engine", "run"],
            },
            {
                "title": "Utility",
                "contents": ["format_result"],
            },
        ],
    },
    "files": {
        "src/gdtest_src_explicit_ref/__init__.py": '''\
            """Package in src/ with explicit reference config."""

            __version__ = "0.1.0"
            __all__ = ["Engine", "run", "format_result"]


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
                        Results.
                    """
                    return {}


            def run(engine: Engine) -> dict:
                """
                Run an engine instance.

                Parameters
                ----------
                engine
                    The engine to run.

                Returns
                -------
                dict
                    Run results.
                """
                return engine.execute()


            def format_result(result: dict) -> str:
                """
                Format an engine result for display.

                Parameters
                ----------
                result
                    Result dictionary.

                Returns
                -------
                str
                    Formatted string.
                """
                return str(result)
        ''',
        "README.md": """\
            # gdtest-src-explicit-ref

            Tests src/ layout with explicit reference configuration.
        """,
    },
    "expected": {
        "detected_name": "gdtest-src-explicit-ref",
        "detected_module": "gdtest_src_explicit_ref",
        "detected_parser": "numpy",
        "export_names": ["Engine", "run", "format_result"],
        "num_exports": 3,
        "section_titles": ["Core", "Utility"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
