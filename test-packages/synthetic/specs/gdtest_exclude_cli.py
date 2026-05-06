"""
gdtest_exclude_cli — Config-level exclusion + CLI documentation.

Dimensions: A1, B5, C1, D1, E6, F6, G1, H7
Focus: Config-level export exclusion combined with CLI docs. Verifies
       excluded items don't appear while CLI section does.
"""

SPEC = {
    "name": "gdtest_exclude_cli",
    "description": "Config exclusion with CLI documentation",
    "dimensions": ["A1", "B5", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-exclude-cli",
            "version": "0.1.0",
            "description": "Test config exclusion with CLI docs",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "exclude": ["hidden_func"],
        "cli": {"enabled": True},
    },
    "files": {
        "gdtest_exclude_cli/__init__.py": '''\
            """Package with config exclusion and CLI."""

            __version__ = "0.1.0"
            __all__ = ["execute", "report", "hidden_func"]


            def execute(task: str) -> dict:
                """
                Execute a task.

                Parameters
                ----------
                task
                    Task name to execute.

                Returns
                -------
                dict
                    Execution results.
                """
                return {"task": task, "status": "done"}


            def report() -> str:
                """
                Generate a report.

                Returns
                -------
                str
                    Report text.
                """
                return "report"


            def hidden_func() -> None:
                """
                This function is excluded via config — should not appear.

                Returns
                -------
                None
                """
                pass
        ''',
        "gdtest_exclude_cli/cli.py": '''\
            """CLI for gdtest_exclude_cli."""

            try:
                import click
            except ImportError:
                import sys
                print("click not installed", file=sys.stderr)
                sys.exit(1)


            @click.group()
            def main():
                """Main CLI entry point."""
                pass


            @main.command()
            @click.argument("task")
            def run(task):
                """Run a specific task."""
                click.echo(f"Running {task}")


            @main.command()
            def show():
                """Show the current report."""
                click.echo("Report output")
        ''',
        "README.md": """\
            # gdtest-exclude-cli

            Tests config-level exclusion combined with CLI docs.
        """,
    },
    "expected": {
        "detected_name": "gdtest-exclude-cli",
        "detected_module": "gdtest_exclude_cli",
        "detected_parser": "numpy",
        "export_names": ["execute", "report"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_cli": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
