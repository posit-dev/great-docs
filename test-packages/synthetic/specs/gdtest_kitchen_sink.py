"""
gdtest_kitchen_sink — Maximum feature coverage in one package.

Dimensions: A2, B1, C4, D1, F1, G1, H1+H2+H3+H4+H6
Focus: Everything at once.  src/ layout, mixed objects (big class, small
       class, dataclass, enum, functions), auto-discovered user guide,
       full supporting pages (LICENSE, CITATION.cff, CONTRIBUTING.md,
       CODE_OF_CONDUCT.md, assets/). Authors and funding in config.
       The "integration smoke test" package.
"""

SPEC = {
    "name": "gdtest_kitchen_sink",
    "description": "Maximum feature coverage — every major feature at once",
    "dimensions": ["A2", "B1", "C4", "D1", "F1", "G1", "H1", "H2", "H3", "H4", "H6"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-kitchen-sink",
            "version": "1.0.0",
            "description": "A comprehensive test package exercising all Great Docs features",
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
    # ── Config ────────────────────────────────────────────────────────
    "config": {
        "display_name": "Kitchen Sink",
        "parser": "numpy",
        "authors": [
            {
                "name": "Test Author",
                "email": "test@example.com",
                "role": "Lead Developer",
                "github": "testauthor",
            },
        ],
        "funding": {
            "name": "Test Foundation",
            "roles": ["Funder"],
            "homepage": "https://example.com/foundation",
        },
        "source": {
            "enabled": True,
            "branch": "main",
        },
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        # ---- Python source ----
        "src/gdtest_kitchen_sink/__init__.py": '''\
            """
            Kitchen Sink — a comprehensive test package.

            This package exercises every major Great Docs feature in a single
            codebase.
            """

            __version__ = "1.0.0"
            __all__ = [
                "Pipeline",
                "Config",
                "Status",
                "Result",
                "run_pipeline",
                "validate_config",
                "format_output",
                "parse_input",
                "helper_a",
                "helper_b",
            ]

            from dataclasses import dataclass, field
            from enum import Enum


            # ── Big class (>5 methods → separate method section) ──────────

            class Pipeline:
                """
                A data processing pipeline with many operations.

                Parameters
                ----------
                name
                    Pipeline name.
                """

                def __init__(self, name: str):
                    self.name = name
                    self._steps = []

                def add_step(self, step) -> "Pipeline":
                    """
                    Add a processing step.

                    Parameters
                    ----------
                    step
                        The step to add.

                    Returns
                    -------
                    Pipeline
                        Self, for chaining.
                    """
                    self._steps.append(step)
                    return self

                def remove_step(self, index: int) -> "Pipeline":
                    """
                    Remove a step by index.

                    Parameters
                    ----------
                    index
                        The step index to remove.

                    Returns
                    -------
                    Pipeline
                        Self, for chaining.
                    """
                    self._steps.pop(index)
                    return self

                def run(self) -> "Result":
                    """
                    Execute the pipeline.

                    Returns
                    -------
                    Result
                        The pipeline result.
                    """
                    return Result(status=Status.SUCCESS, message="done")

                def validate(self) -> bool:
                    """
                    Check that the pipeline is correctly configured.

                    Returns
                    -------
                    bool
                        True if valid.
                    """
                    return len(self._steps) > 0

                def reset(self) -> None:
                    """Clear all steps from the pipeline."""
                    self._steps.clear()

                def summary(self) -> dict:
                    """
                    Return a summary of the pipeline.

                    Returns
                    -------
                    dict
                        Summary with name, step count, etc.
                    """
                    return {"name": self.name, "steps": len(self._steps)}


            # ── Small class (≤5 methods → inline docs) ────────────────────

            class Config:
                """
                Configuration container for a pipeline.

                Parameters
                ----------
                settings
                    A dictionary of settings.
                """

                def __init__(self, settings: dict | None = None):
                    self._settings = settings or {}

                def get(self, key: str, default=None):
                    """
                    Get a config value.

                    Parameters
                    ----------
                    key
                        Setting key.
                    default
                        Default if key not found.

                    Returns
                    -------
                    object
                        The setting value.
                    """
                    return self._settings.get(key, default)

                def set(self, key: str, value) -> None:
                    """
                    Set a config value.

                    Parameters
                    ----------
                    key
                        Setting key.
                    value
                        New value.
                    """
                    self._settings[key] = value


            # ── Enum ──────────────────────────────────────────────────────

            class Status(Enum):
                """
                Pipeline execution status.
                """
                SUCCESS = "success"
                FAILURE = "failure"
                PENDING = "pending"
                SKIPPED = "skipped"


            # ── Dataclass ─────────────────────────────────────────────────

            @dataclass
            class Result:
                """
                The result of a pipeline execution.

                Parameters
                ----------
                status
                    Execution status.
                message
                    Human-readable message.
                errors
                    List of error strings, if any.
                """
                status: Status
                message: str = ""
                errors: list[str] = field(default_factory=list)


            # ── Functions ─────────────────────────────────────────────────

            def run_pipeline(name: str, **kwargs) -> Result:
                """
                High-level function to create and run a pipeline.

                Parameters
                ----------
                name
                    Pipeline name.
                **kwargs
                    Passed to Pipeline constructor.

                Returns
                -------
                Result
                    The execution result.
                """
                return Pipeline(name).run()


            def validate_config(config: Config) -> bool:
                """
                Validate a configuration object.

                Parameters
                ----------
                config
                    The config to validate.

                Returns
                -------
                bool
                    True if valid.
                """
                return True


            def format_output(result: Result, fmt: str = "text") -> str:
                """
                Format a result for display.

                Parameters
                ----------
                result
                    The result to format.
                fmt
                    Output format (text, json, html).

                Returns
                -------
                str
                    Formatted output.
                """
                return str(result)


            def parse_input(raw: str) -> dict:
                """
                Parse raw input into a structured dict.

                Parameters
                ----------
                raw
                    Raw input string.

                Returns
                -------
                dict
                    Parsed data.
                """
                return {"raw": raw}


            def helper_a() -> None:
                """
                A general-purpose helper function.

                Returns
                -------
                None
                """
                pass


            def helper_b() -> None:
                """
                Another general-purpose helper.

                Returns
                -------
                None
                """
                pass
        ''',
        # ---- User guide ----
        "user_guide/01-introduction.qmd": """\
            ---
            title: Introduction
            ---

            Welcome to Kitchen Sink! This is a comprehensive test package.
        """,
        "user_guide/02-quickstart.qmd": """\
            ---
            title: Quick Start
            ---

            Get started with Kitchen Sink in minutes.

            ```python
            from gdtest_kitchen_sink import Pipeline

            p = Pipeline("my-pipeline")
            result = p.run()
            ```
        """,
        "user_guide/03-advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            Advanced topics for power users.
        """,
        # ---- Supporting pages ----
        "README.md": """\
            # Kitchen Sink

            A comprehensive test package exercising all Great Docs features.

            ## Features

            - Pipeline processing
            - Configuration management
            - Status tracking
            - Result formatting
        """,
        "LICENSE": """\
            MIT License

            Copyright (c) 2026 Test Author

            Permission is hereby granted, free of charge, to any person obtaining a copy
            of this software and associated documentation files (the "Software"), to deal
            in the Software without restriction.
        """,
        "CITATION.cff": """\
            cff-version: 1.2.0
            message: "If you use this software, please cite it as below."
            title: "Kitchen Sink"
            version: "1.0.0"
            date-released: "2026-01-15"
            authors:
              - family-names: Author
                given-names: Test
                orcid: "https://orcid.org/0000-0000-0000-0001"
        """,
        "CONTRIBUTING.md": """\
            # Contributing

            We welcome contributions! Please open an issue or pull request.

            ## Development Setup

            ```bash
            pip install -e ".[dev]"
            ```
        """,
        "CODE_OF_CONDUCT.md": """\
            # Code of Conduct

            Be kind. Be respectful. Be constructive.
        """,
        "assets/logo.txt": """\
            ┌─────────────┐
            │ Kitchen Sink │
            └─────────────┘
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-kitchen-sink",
        "detected_module": "gdtest_kitchen_sink",
        "detected_parser": "numpy",
        "export_names": [
            "Pipeline",
            "Config",
            "Status",
            "Result",
            "run_pipeline",
            "validate_config",
            "format_output",
            "parse_input",
            "helper_a",
            "helper_b",
        ],
        "num_exports": 10,
        "big_class_name": "Pipeline",
        "big_class_method_count": 6,
        "has_user_guide": True,
        "user_guide_files": ["01-introduction.qmd", "02-quickstart.qmd", "03-advanced.qmd"],
        "has_license_page": True,
        "has_citation_page": True,
        "has_contributing_page": True,
        "has_code_of_conduct_page": True,
        "has_assets": True,
        "coverage_exclude": ["nodoc", "sechdg", "sbsec", "hdg"],
    },
}
