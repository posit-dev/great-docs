"""
gdtest_cli_click — Click CLI documentation.

Dimensions: A1, B1, C1, D1, E1+E6, F6, G1, H7
Focus: Click CLI discovery and documentation generation.
Package has a cli.py with @click.command, and config has cli.enabled: true.
"""

SPEC = {
    "name": "gdtest_cli_click",
    "description": "Simple Click CLI commands with CLI docs enabled",
    "dimensions": ["A1", "B1", "C1", "D1", "E1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-cli-click",
            "version": "0.1.0",
            "description": "A package with Click CLI",
            "scripts": {
                "gdtest-cli": "gdtest_cli_click.cli:main",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_cli_click/__init__.py": '''\
            """A package with Click CLI support."""

            __version__ = "0.1.0"
            __all__ = ["Formatter", "format_text"]


            class Formatter:
                """
                A text formatter.

                Parameters
                ----------
                style
                    The formatting style to use.
                """

                def __init__(self, style: str = "default"):
                    self.style = style

                def apply(self, text: str) -> str:
                    """
                    Apply formatting to text.

                    Parameters
                    ----------
                    text
                        The text to format.

                    Returns
                    -------
                    str
                        Formatted text.
                    """
                    return text


            def format_text(text: str, style: str = "default") -> str:
                """
                Format text with a given style.

                Parameters
                ----------
                text
                    The text to format.
                style
                    The style to apply.

                Returns
                -------
                str
                    Formatted text.
                """
                return Formatter(style).apply(text)
        ''',
        "gdtest_cli_click/cli.py": '''\
            """CLI entry point using Click."""

            import click


            @click.command()
            @click.argument("text")
            @click.option("--style", "-s", default="default", help="Formatting style.")
            @click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
            def main(text: str, style: str, verbose: bool) -> None:
                """Format text using the gdtest-cli-click formatter."""
                if verbose:
                    click.echo(f"Formatting with style: {style}")
                click.echo(text)
        ''',
        "README.md": """\
            # gdtest-cli-click

            A test package with Click CLI support.
        """,
    },
    "config": {
        "cli": {
            "enabled": True,
        },
    },
    "expected": {
        "detected_name": "gdtest-cli-click",
        "detected_module": "gdtest_cli_click",
        "detected_parser": "numpy",
        "export_names": ["Formatter", "format_text"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "cli_enabled": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
