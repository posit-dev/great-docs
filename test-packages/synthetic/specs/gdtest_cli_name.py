"""
gdtest_cli_name — Tests cli.name: 'mytool' config with CLI enabled.

Dimensions: K8
Focus: cli.name config option with cli.enabled and cli.module specified.
"""

SPEC = {
    "name": "gdtest_cli_name",
    "description": "Tests cli.name: mytool config",
    "dimensions": ["K8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-cli-name",
            "version": "0.1.0",
            "description": "Test cli.name mytool config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "cli": {
            "enabled": True,
            "module": "gdtest_cli_name.cli",
            "name": "mytool",
        },
    },
    "files": {
        "gdtest_cli_name/__init__.py": '''\
            """Package testing cli.name mytool config."""

            __version__ = "0.1.0"
            __all__ = ["process", "summarize"]


            def process(data: list) -> list:
                """
                Process a list of data items.

                Parameters
                ----------
                data
                    The input data to process.

                Returns
                -------
                list
                    The processed data.
                """
                return data


            def summarize(data: list) -> str:
                """
                Summarize a list of data items.

                Parameters
                ----------
                data
                    The input data to summarize.

                Returns
                -------
                str
                    A summary of the data.
                """
                return ""
        ''',
        "gdtest_cli_name/cli.py": '''\
            import click


            @click.group()
            def cli():
                """MyTool CLI."""
                pass


            @cli.command()
            def run():
                """Run the process."""
                click.echo("Running...")


            @cli.command()
            def status():
                """Show status."""
                click.echo("Status: OK")
        ''',
        "README.md": """\
            # gdtest-v2-cli-name

            Tests cli.name: mytool config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-cli-name",
        "detected_module": "gdtest_cli_name",
        "detected_parser": "numpy",
        "export_names": ["process", "summarize"],
        "num_exports": 2,
    },
}
