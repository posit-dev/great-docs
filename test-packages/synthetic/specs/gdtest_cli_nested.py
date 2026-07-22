"""
gdtest_cli_nested — Nested Click groups and subcommands.

Dimensions: A1, B1, C1, D1, E1+E6, F6, G1, H7
Focus: Nested Click group with subcommands for CLI documentation.
Tests nested subcommand handling and command tree documentation.
"""

SPEC = {
    "name": "gdtest_cli_nested",
    "description": "Nested Click groups with subcommands",
    "dimensions": ["A1", "B1", "C1", "D1", "E1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-cli-nested",
            "version": "0.1.0",
            "description": "A package with nested Click CLI groups",
            "scripts": {
                "gdtest-nested": "gdtest_cli_nested.cli:cli",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_cli_nested/__init__.py": '''\
            """A package with nested Click CLI groups."""

            __version__ = "0.1.0"
            __all__ = ["Engine", "run_task"]


            class Engine:
                """
                A task execution engine.

                Parameters
                ----------
                workers
                    Number of worker threads.
                """

                def __init__(self, workers: int = 4):
                    self.workers = workers

                def execute(self, task: str) -> bool:
                    """
                    Execute a named task.

                    Parameters
                    ----------
                    task
                        Name of the task.

                    Returns
                    -------
                    bool
                        True if successful.
                    """
                    return True


            def run_task(name: str, dry_run: bool = False) -> str:
                """
                Run a task by name.

                Parameters
                ----------
                name
                    The task name.
                dry_run
                    If True, simulate without executing.

                Returns
                -------
                str
                    Task result message.
                """
                return f"{'[DRY RUN] ' if dry_run else ''}Ran: {name}"
        ''',
        "gdtest_cli_nested/cli.py": '''\
            """Nested CLI entry point using Click groups."""

            import click


            @click.group()
            @click.version_option()
            def cli():
                """gdtest-cli-nested: A nested command-line tool."""
                pass


            @cli.group()
            def task():
                """Manage tasks."""
                pass


            @task.command()
            @click.argument("name")
            @click.option("--dry-run", is_flag=True, help="Simulate without executing.")
            def run(name: str, dry_run: bool) -> None:
                """Run a specific task."""
                click.echo(f"Running task: {name}")


            @task.command()
            def list():
                """List all available tasks."""
                click.echo("task1\\ntask2\\ntask3")


            @cli.group()
            def config():
                """Manage configuration."""
                pass


            @config.command()
            @click.argument("key")
            def get(key: str) -> None:
                """Get a configuration value."""
                click.echo(f"Config[{key}]")


            @config.command()
            @click.argument("key")
            @click.argument("value")
            def set(key: str, value: str) -> None:
                """Set a configuration value."""
                click.echo(f"Set {key}={value}")
        ''',
        "README.md": """\
            # gdtest-cli-nested

            A test package with nested Click CLI groups.
        """,
    },
    "config": {
        "cli": {
            "enabled": True,
        },
    },
    "expected": {
        "detected_name": "gdtest-cli-nested",
        "detected_module": "gdtest_cli_nested",
        "detected_parser": "numpy",
        "export_names": ["Engine", "run_task"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "cli_enabled": True,
        "cli_has_groups": True,
        "cli_group_names": ["task", "config"],
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
