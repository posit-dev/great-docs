"""
gdtest_autolink — autolink inline code to API reference pages.

Dimensions: A1, D1, E3, L26
Focus: Tests that inline code in docstrings matching API names is auto-
       converted into clickable links. Covers all autolink styles:
       - ``Name`` or ``Name()`` — plain autolink
       - ``~~pkg.Name`` — shortened display
       - ``~~.pkg.Name`` — dot-prefixed short display
       - ``Name(x=1)`` — NOT autolinked (has arguments)
       - ``{.gd-no-link}`` — opt-out of autolinking
"""

SPEC = {
    "name": "gdtest_autolink",
    "description": (
        "Autolink inline code to API reference pages. "
        "Tests that `Name`, `Name()`, `~~pkg.Name`, and `~~.pkg.Name` "
        "in docstring prose are converted to clickable links."
    ),
    "dimensions": ["A1", "D1", "E3", "L26"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-autolink",
            "version": "0.1.0",
            "description": "Test autolink inline code",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_autolink/__init__.py": '''\
            """Package demonstrating autolink of inline code references."""

            __version__ = "0.1.0"
            __all__ = ["Engine", "Pipeline", "run_pipeline", "Config"]


            class Config:
                """Configuration for pipelines.

                Parameters
                ----------
                name
                    The config name.
                """

                def __init__(self, name: str = "default") -> None:
                    self.name = name


            class Engine:
                """Core processing engine.

                Use ``Pipeline`` to chain multiple engines together.
                Call ``run_pipeline()`` to execute a full pipeline.

                The ``~~gdtest_autolink.Config`` class holds settings.

                Parameters
                ----------
                name
                    The engine name.
                """

                def __init__(self, name: str) -> None:
                    self.name = name


            class Pipeline:
                """A chain of processing steps.

                Each step uses an ``Engine`` instance. Configure with
                ``Config``.

                See ``~~.gdtest_autolink.run_pipeline`` for a shortcut
                to running the full pipeline.

                Parameters
                ----------
                steps
                    List of engine names.
                """

                def __init__(self, steps: list = None) -> None:
                    self.steps = steps or []


            def run_pipeline(data: dict, config: Config = None) -> dict:
                """Execute a full pipeline on the given data.

                Creates a ``Pipeline`` from the ``Config`` and runs each
                ``Engine`` step in order.

                Parameters
                ----------
                data
                    Input data to process.
                config
                    Pipeline configuration. See ``Config`` for options.

                Returns
                -------
                dict
                    Processed output data.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-autolink

            A synthetic test package testing autolink of inline code.
        """,
    },
    "expected": {
        "detected_name": "gdtest-autolink",
        "detected_module": "gdtest_autolink",
        "detected_parser": "numpy",
        "export_names": ["Config", "Engine", "Pipeline", "run_pipeline"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        # Inline code that should be autolinked on each page
        "autolinked_names": {
            "Engine": ["Pipeline", "run_pipeline()", "Config"],
            "Pipeline": ["Engine", "Config", "run_pipeline"],
            "run_pipeline": ["Pipeline", "Config", "Engine"],
        },
    },
}
