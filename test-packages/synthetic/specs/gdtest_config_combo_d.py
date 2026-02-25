"""
gdtest_config_combo_d — Config combo: sidebar min_items + cli.name + display_name + user_guide string.

Dimensions: K7, K8, K12, K19
Focus: sidebar_filter.min_items, cli.name, display_name override, user_guide as string.
"""

SPEC = {
    "name": "gdtest_config_combo_d",
    "description": (
        "Config combo: sidebar_filter.min_items, cli.name, display_name, "
        "user_guide as string path. Tests metadata and navigation options."
    ),
    "dimensions": ["K7", "K8", "K12", "K19"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-combo-d",
            "version": "0.1.0",
            "description": "Test package for config combo D.",
            "scripts": {"combo-d": "gdtest_config_combo_d.cli:main"},
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Combo D Toolkit",
        "sidebar_filter": {
            "min_items": 3,
        },
        "cli": {
            "name": "combo-d",
        },
        "user_guide": "docs",
    },
    "files": {
        "gdtest_config_combo_d/__init__.py": '''\
            """Combo D Toolkit — sidebar min_items, cli.name, display_name, user_guide string."""

            __version__ = "0.1.0"
            __all__ = ["process", "validate", "transform", "load"]


            def process(data: list) -> list:
                """
                Process a list of data items.

                Parameters
                ----------
                data : list
                    The input data to process.

                Returns
                -------
                list
                    The processed data items.
                """
                return data


            def validate(value: str) -> bool:
                """
                Validate a string value.

                Parameters
                ----------
                value : str
                    The value to validate.

                Returns
                -------
                bool
                    True if the value is valid.
                """
                return bool(value)


            def transform(item: dict) -> dict:
                """
                Transform an item dictionary.

                Parameters
                ----------
                item : dict
                    The item to transform.

                Returns
                -------
                dict
                    The transformed item.
                """
                return item


            def load(path: str) -> str:
                """
                Load content from a path.

                Parameters
                ----------
                path : str
                    Path to load from.

                Returns
                -------
                str
                    The loaded content.
                """
                return path
        ''',
        "gdtest_config_combo_d/cli.py": '''\
            """CLI entry point for combo-d."""

            import click


            @click.group()
            def main():
                """Combo D command-line interface."""
                pass


            @main.command()
            @click.argument("input_path")
            def run(input_path: str):
                """Run processing on the given input path."""
                click.echo(f"Processing {input_path}")
        ''',
        "docs/getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            Welcome to the Combo D Toolkit getting started guide.

            ## Installation

            Install with pip:

            ```bash
            pip install gdtest-config-combo-d
            ```
        """,
        "docs/usage.qmd": """\
            ---
            title: Usage
            ---

            ## Basic Usage

            Use the toolkit functions to process data.
        """,
        "README.md": """\
            # Combo D Toolkit

            Tests sidebar min_items, cli.name, display_name, and user_guide string path.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-combo-d",
        "detected_module": "gdtest_config_combo_d",
        "detected_parser": "numpy",
        "export_names": ["load", "process", "transform", "validate"],
        "num_exports": 4,
    },
}
