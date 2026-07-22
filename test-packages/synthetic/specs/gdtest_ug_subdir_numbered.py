"""
gdtest_ug_subdir_numbered — Subdirectory user guide with numeric prefixes.

Dimensions: A1, D1, F3
Focus: User guide organized into numbered subdirectories with numbered files,
       testing that numeric prefixes are stripped from both directory names
       and filenames for clean URLs and sidebar labels.
"""

SPEC = {
    "name": "gdtest_ug_subdir_numbered",
    "description": (
        "Subdirectory user guide with numeric prefixes on directories and files. "
        "Tests clean URL generation and sidebar grouping from directory structure."
    ),
    "dimensions": ["A1", "D1", "F3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ug-subdir-numbered",
            "version": "0.1.0",
            "description": "Test package for numbered subdirectory user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_subdir_numbered/__init__.py": '''\
            """Package with numbered subdirectory user guide."""

            from .core import connect, disconnect

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect"]
        ''',
        "gdtest_ug_subdir_numbered/core.py": '''\
            """Core connection functions."""


            def connect(host: str, port: int = 8080) -> bool:
                """
                Connect to a remote server.

                Parameters
                ----------
                host : str
                    The hostname or IP address.
                port : int
                    The port number (default: 8080).

                Returns
                -------
                bool
                    True if the connection succeeded.
                """
                return True


            def disconnect() -> None:
                """
                Disconnect from the server.

                Closes the active connection gracefully.
                """
                pass
        ''',
        "user_guide/index.qmd": """\
            ---
            title: User Guide
            ---

            Welcome to the user guide for gdtest-ug-subdir-numbered.

            This guide is organized into sections using numbered subdirectories.
        """,
        "user_guide/01-getting-started/index.qmd": """\
            ---
            title: Getting Started
            ---

            Everything you need to get up and running.
        """,
        "user_guide/01-getting-started/01-installation.qmd": """\
            ---
            title: Installation
            ---

            ## Installing the Package

            ```bash
            pip install gdtest-ug-subdir-numbered
            ```
        """,
        "user_guide/01-getting-started/02-quickstart.qmd": """\
            ---
            title: Quickstart
            ---

            ## Quick Start

            ```python
            from gdtest_ug_subdir_numbered import connect

            connect("localhost")
            ```
        """,
        "user_guide/02-guides/index.qmd": """\
            ---
            title: Guides
            ---

            In-depth guides for common tasks.
        """,
        "user_guide/02-guides/01-configuration.qmd": """\
            ---
            title: Configuration
            ---

            ## Configuring Connections

            Pass the host and port to `connect()`.
        """,
        "user_guide/02-guides/02-troubleshooting.qmd": """\
            ---
            title: Troubleshooting
            ---

            ## Common Issues

            If `connect()` returns False, check that the server is running.
        """,
        "README.md": """\
            # gdtest-ug-subdir-numbered

            Test package with numbered subdirectory user guide layout.
        """,
    },
    "expected": {
        "detected_name": "gdtest-ug-subdir-numbered",
        "detected_module": "gdtest_ug_subdir_numbered",
        "detected_parser": "numpy",
        "export_names": ["connect", "disconnect"],
        "num_exports": 2,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec", "hdg"],
    },
}
