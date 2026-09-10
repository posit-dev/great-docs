"""
gdtest_ref_section_order — Custom reference section ordering.

Dimensions: A1, B1, C1, D1, E1+E6, F6, G1, H7
Focus: ref_section_order config key. The reference switcher tabs should
appear in the order specified by the config (cli, api) instead of the
default (api, cli). The data-gd-ref-sections body attribute should
reflect this custom ordering.
"""

SPEC = {
    "name": "gdtest_ref_section_order",
    "description": "CLI-first reference section ordering via ref_section_order config",
    "dimensions": ["A1", "B1", "C1", "D1", "E1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ref-section-order",
            "version": "0.1.0",
            "description": "A package demonstrating custom ref section order",
            "scripts": {
                "gdtest-rso": "gdtest_ref_section_order.cli:main",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ref_section_order/__init__.py": '''\
            """A CLI-first package with custom reference section ordering."""

            __version__ = "0.1.0"
            __all__ = ["run_task", "TaskConfig"]


            class TaskConfig:
                """
                Configuration for a task.

                Parameters
                ----------
                name
                    The task name.
                timeout
                    Timeout in seconds.
                """

                def __init__(self, name: str, timeout: int = 30):
                    self.name = name
                    self.timeout = timeout


            def run_task(config: TaskConfig) -> str:
                """
                Run a task with the given configuration.

                Parameters
                ----------
                config
                    The task configuration.

                Returns
                -------
                str
                    Task result message.
                """
                return f"Task {config.name} completed"
        ''',
        "gdtest_ref_section_order/cli.py": '''\
            """CLI entry point using Click."""

            import click


            @click.group()
            def main() -> None:
                """gdtest-rso: a CLI-first tool for running tasks."""


            @main.command()
            @click.argument("name")
            @click.option("--timeout", "-t", default=30, help="Timeout in seconds.")
            def run(name: str, timeout: int) -> None:
                """Run a named task."""
                click.echo(f"Running {name} (timeout={timeout}s)")


            @main.command()
            def list() -> None:
                """List available tasks."""
                click.echo("task-a\\ntask-b\\ntask-c")
        ''',
        "README.md": """\
            # gdtest-ref-section-order

            A CLI-first test package demonstrating custom reference section ordering.
        """,
    },
    "config": {
        "cli": {
            "enabled": True,
        },
        "mcp": {
            "enabled": False,
        },
        "ref_section_order": ["cli", "api"],
    },
    "expected": {
        "detected_name": "gdtest-ref-section-order",
        "detected_module": "gdtest_ref_section_order",
        "detected_parser": "numpy",
        "export_names": ["TaskConfig", "run_task"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "cli_enabled": True,
        "ref_section_order": ["cli", "api"],
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
