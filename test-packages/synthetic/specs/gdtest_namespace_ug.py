"""
gdtest_namespace_ug — Namespace package + deeply nested user guide + subdirectory UG.

Dimensions: A12, F3, M6
Focus: Cross-dimension test combining namespace package layout with a deeply
       nested user guide using subdirectories.
"""

SPEC = {
    "name": "gdtest_namespace_ug",
    "description": (
        "Namespace package + deeply nested user guide + subdirectory UG. "
        "Tests namespace package detection with complex user guide structure."
    ),
    "dimensions": ["A12", "F3", "M6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-namespace-ug",
            "version": "0.1.0",
            "description": "Test package for namespace layout + nested user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "packages": {
                    "find": {
                        "include": ["gdtest_namespace_ug*"],
                    },
                },
            },
        },
    },
    "files": {
        "gdtest_namespace_ug/__init__.py": '''\
            """Namespace package with nested user guide."""

            from .core import initialize, shutdown

            __version__ = "0.1.0"
            __all__ = ["initialize", "shutdown"]
        ''',
        "gdtest_namespace_ug/core.py": '''\
            """Core lifecycle functions."""


            def initialize(config: dict | None = None) -> bool:
                """
                Initialize the application.

                Parameters
                ----------
                config : dict or None
                    Optional configuration dictionary.

                Returns
                -------
                bool
                    True if initialization succeeded.
                """
                return True


            def shutdown(force: bool = False) -> None:
                """
                Shut down the application gracefully.

                Parameters
                ----------
                force : bool
                    If True, force immediate shutdown.
                """
                pass
        ''',
        "user-guide/index.qmd": """\
            ---
            title: User Guide
            ---

            Welcome to the gdtest-namespace-ug user guide.
        """,
        "user-guide/getting-started/index.qmd": """\
            ---
            title: Getting Started
            ---

            Welcome to the getting started guide.
        """,
        "user-guide/getting-started/installation.qmd": """\
            ---
            title: Installation
            ---

            ## Install

            ```bash
            pip install gdtest-namespace-ug
            ```
        """,
        "user-guide/getting-started/quickstart.qmd": """\
            ---
            title: Quickstart
            ---

            ## Quick Start

            ```python
            from gdtest_namespace_ug import initialize
            initialize()
            ```
        """,
        "user-guide/advanced/index.qmd": """\
            ---
            title: Advanced Usage
            ---

            Advanced topics for power users.
        """,
        "user-guide/advanced/configuration.qmd": """\
            ---
            title: Configuration
            ---

            ## Configuration Options

            Pass a config dict to `initialize()`.
        """,
        "user-guide/advanced/deployment.qmd": """\
            ---
            title: Deployment
            ---

            ## Docker Deployment

            Use the provided Dockerfile.

            ## Cloud Deployment

            Deploy to your cloud provider.
        """,
        "README.md": """\
            # gdtest-namespace-ug

            Test package with namespace layout and deeply nested user guide.
        """,
    },
    "expected": {
        "detected_name": "gdtest-namespace-ug",
        "detected_module": "gdtest_namespace_ug",
        "detected_parser": "numpy",
        "export_names": ["initialize", "shutdown"],
        "num_exports": 2,
    },
}
