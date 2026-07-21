"""
gdtest_user_guide_cli — User guide + CLI documentation.

Dimensions: A1, B1, C1, D1, E6, F1, G1, H7
Focus: Combines auto-discovered user guide with Click CLI docs to
       verify both appear in the sidebar without conflict.
"""

SPEC = {
    "name": "gdtest_user_guide_cli",
    "description": "User guide combined with CLI documentation",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-cli",
            "version": "0.1.0",
            "description": "Test user guide and CLI docs together",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "cli": {"enabled": True},
    },
    "files": {
        "gdtest_user_guide_cli/__init__.py": '''\
            """Package with API, user guide, and CLI."""

            __version__ = "0.1.0"
            __all__ = ["process", "analyze"]


            def process(data: str) -> str:
                """
                Process input data.

                Parameters
                ----------
                data
                    Input data string.

                Returns
                -------
                str
                    Processed output.
                """
                return data.upper()


            def analyze(data: str) -> dict:
                """
                Analyze data and return statistics.

                Parameters
                ----------
                data
                    Input data string.

                Returns
                -------
                dict
                    Analysis results.
                """
                return {"length": len(data)}
        ''',
        "gdtest_user_guide_cli/cli.py": '''\
            """CLI interface for gdtest_user_guide_cli."""

            try:
                import click
            except ImportError:
                import sys
                print("click not installed", file=sys.stderr)
                sys.exit(1)


            @click.group()
            def main():
                """Main CLI entry point for the user-guide-cli tool."""
                pass


            @main.command()
            @click.argument("input_file")
            @click.option("--output", "-o", default=None, help="Output file path.")
            def run(input_file, output):
                """Run processing on the input file."""
                click.echo(f"Processing {input_file}")


            @main.command()
            @click.argument("input_file")
            def stats(input_file):
                """Show statistics for the input file."""
                click.echo(f"Stats for {input_file}")
        ''',
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            ## Introduction

            Welcome to gdtest-user-guide-cli. This guide covers basic usage.

            ## Installation

            ```bash
            pip install gdtest-user-guide-cli
            ```
        """,
        "user_guide/02-advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            ## Configuration

            Advanced configuration options for power users.

            ## Batch Processing

            Process multiple files at once using the CLI.
        """,
        "README.md": """\
            # gdtest-user-guide-cli

            A test package with user guide and CLI documentation combined.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-cli",
        "detected_module": "gdtest_user_guide_cli",
        "detected_parser": "numpy",
        "export_names": ["process", "analyze"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "has_cli": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
