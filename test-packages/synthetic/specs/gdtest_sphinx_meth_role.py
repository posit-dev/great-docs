"""
gdtest_sphinx_meth_role — :py:meth: cross-reference roles.

Dimensions: L13
Focus: One class with methods that reference each other via
       :py:meth:`Pipeline.method`. Tests that Sphinx meth roles render correctly.
"""

SPEC = {
    "name": "gdtest_sphinx_meth_role",
    "description": ":py:meth: cross-reference roles between methods",
    "dimensions": ["L13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-meth-role",
            "version": "0.1.0",
            "description": "Test :py:meth: Sphinx role rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx_meth_role/__init__.py": '''\
            """Package demonstrating :py:meth: cross-reference roles."""

            __version__ = "0.1.0"
            __all__ = ["Pipeline"]


            class Pipeline:
                """
                A processing pipeline that manages a sequence of steps.

                Parameters
                ----------
                name
                    The name of this pipeline.
                """

                def __init__(self, name: str = "default"):
                    self.name = name
                    self._steps: list = []

                def add_step(self, step: str) -> None:
                    """
                    Add a step to the pipeline.

                    Call :py:meth:`Pipeline.run` to execute.

                    Parameters
                    ----------
                    step
                        The step identifier to add.
                    """
                    self._steps.append(step)

                def remove_step(self, step: str) -> bool:
                    """
                    Remove a step from the pipeline.

                    Parameters
                    ----------
                    step
                        The step identifier to remove.

                    Returns
                    -------
                    bool
                        True if the step was found and removed.
                    """
                    if step in self._steps:
                        self._steps.remove(step)
                        return True
                    return False

                def run(self) -> list:
                    """
                    Execute all steps in the pipeline.

                    Use :py:meth:`Pipeline.reset` to clear after running.

                    Returns
                    -------
                    list
                        Results from each step execution.
                    """
                    return [f"executed:{s}" for s in self._steps]

                def reset(self) -> None:
                    """
                    Clear all steps from the pipeline.

                    After calling this, use :py:meth:`Pipeline.add_step` to add
                    new steps.

                    Returns
                    -------
                    None
                    """
                    self._steps.clear()
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-meth-role

            A synthetic test package testing ``:py:meth:`` cross-reference roles.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-meth-role",
        "detected_module": "gdtest_sphinx_meth_role",
        "detected_parser": "numpy",
        "export_names": ["Pipeline"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
    },
}
