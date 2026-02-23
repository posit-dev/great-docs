"""
gdtest_sec_recipes — Custom "Recipes" section via config.

Dimensions: N3
Focus: Custom section with title "Recipes" sourced from recipes/ directory.
"""

SPEC = {
    "name": "gdtest_sec_recipes",
    "description": "Custom 'Recipes' section via sections config.",
    "dimensions": ["N3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-recipes",
            "version": "0.1.0",
            "description": "Test custom Recipes section.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Recipes", "dir": "recipes"},
        ],
    },
    "files": {
        "gdtest_sec_recipes/__init__.py": '"""Test package for custom Recipes section."""\n',
        "gdtest_sec_recipes/core.py": '''
            """Core cook/serve functions."""


            def cook(recipe: str) -> dict:
                """Cook a dish from the given recipe.

                Parameters
                ----------
                recipe : str
                    The name of the recipe to cook.

                Returns
                -------
                dict
                    A dictionary describing the cooked dish.

                Examples
                --------
                >>> cook("pasta")
                {'dish': 'pasta', 'status': 'cooked'}
                """
                return {"dish": recipe, "status": "cooked"}


            def serve(dish: dict) -> str:
                """Serve a cooked dish.

                Parameters
                ----------
                dish : dict
                    A dictionary describing the dish to serve.

                Returns
                -------
                str
                    A message confirming the dish was served.

                Examples
                --------
                >>> serve({"dish": "pasta", "status": "cooked"})
                'Serving pasta'
                """
                return f"Serving {dish.get('dish', 'unknown')}"
        ''',
        "recipes/quick-setup.qmd": (
            "---\n"
            "title: Quick Setup\n"
            "---\n"
            "\n"
            "# Quick Setup\n"
            "\n"
            "A recipe for quickly setting up the project.\n"
        ),
        "recipes/data-pipeline.qmd": (
            "---\n"
            "title: Data Pipeline\n"
            "---\n"
            "\n"
            "# Data Pipeline\n"
            "\n"
            "A recipe for building a data processing pipeline.\n"
        ),
        "README.md": ("# gdtest-v2-sec-recipes\n\nTest custom Recipes section.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-recipes",
        "detected_module": "gdtest_sec_recipes",
        "detected_parser": "numpy",
        "export_names": ["cook", "serve"],
        "num_exports": 2,
    },
}
