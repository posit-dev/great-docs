"""
gdtest_src_big_class — src/ layout + big class (>5 methods).

Dimensions: A2, B1, C3, D1, E6, F6, G1, H7
Focus: A big class inside a src/ layout to verify method extraction
       works correctly when the module is discovered from src/.
"""

SPEC = {
    "name": "gdtest_src_big_class",
    "description": "src/ layout with a big class (>5 methods)",
    "dimensions": ["A2", "B1", "C3", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-src-big-class",
            "version": "0.1.0",
            "description": "Test big class method extraction with src/ layout",
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
    "files": {
        "src/gdtest_src_big_class/__init__.py": '''\
            """Package with a big class inside src/ layout."""

            __version__ = "0.1.0"
            __all__ = ["Pipeline", "create_pipeline"]


            class Pipeline:
                """
                A data processing pipeline with many stages.

                Parameters
                ----------
                name
                    Pipeline name.
                """

                def __init__(self, name: str):
                    self.name = name
                    self._steps = []

                def add_step(self, step: str) -> "Pipeline":
                    """
                    Add a processing step.

                    Parameters
                    ----------
                    step
                        Step name to add.

                    Returns
                    -------
                    Pipeline
                        Self for chaining.
                    """
                    self._steps.append(step)
                    return self

                def remove_step(self, index: int) -> None:
                    """
                    Remove a step by index.

                    Parameters
                    ----------
                    index
                        Index of step to remove.
                    """
                    self._steps.pop(index)

                def run(self) -> dict:
                    """
                    Execute the pipeline.

                    Returns
                    -------
                    dict
                        Execution results.
                    """
                    return {"status": "ok"}

                def pause(self) -> None:
                    """Pause pipeline execution."""
                    pass

                def resume(self) -> None:
                    """Resume pipeline execution."""
                    pass

                def reset(self) -> None:
                    """Reset pipeline to initial state."""
                    self._steps.clear()

                def status(self) -> str:
                    """
                    Get pipeline status.

                    Returns
                    -------
                    str
                        Current status string.
                    """
                    return "idle"


            def create_pipeline(name: str) -> Pipeline:
                """
                Create a new pipeline.

                Parameters
                ----------
                name
                    Name for the pipeline.

                Returns
                -------
                Pipeline
                    A new Pipeline instance.
                """
                return Pipeline(name)
        ''',
        "README.md": """\
            # gdtest-src-big-class

            Tests big class method extraction within a src/ layout.
        """,
    },
    "expected": {
        "detected_name": "gdtest-src-big-class",
        "detected_module": "gdtest_src_big_class",
        "detected_parser": "numpy",
        "export_names": ["Pipeline", "create_pipeline"],
        "num_exports": 2,
        "section_titles": ["Classes", "Pipeline Methods", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
