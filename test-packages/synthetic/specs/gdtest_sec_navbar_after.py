"""
gdtest_sec_navbar_after — Custom section with navbar_after specified.

Dimensions: N7
Focus: Custom section with navbar_after placement control.
"""

SPEC = {
    "name": "gdtest_sec_navbar_after",
    "description": "Custom section with navbar_after placement control.",
    "dimensions": ["N7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-navbar-after",
            "version": "0.1.0",
            "description": "Test custom section with navbar_after.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Cookbook", "dir": "cookbook", "navbar_after": "Reference"},
        ],
    },
    "files": {
        "gdtest_sec_navbar_after/__init__.py": '"""Test package for custom section with navbar_after."""\n',
        "gdtest_sec_navbar_after/core.py": '''
            """Core prepare/serve functions."""


            def prepare(ingredient: str) -> dict:
                """Prepare an ingredient for cooking.

                Parameters
                ----------
                ingredient : str
                    The ingredient to prepare.

                Returns
                -------
                dict
                    A dictionary with the prepared ingredient details.

                Examples
                --------
                >>> prepare("tomato")
                {'ingredient': 'tomato', 'status': 'prepared'}
                """
                return {"ingredient": ingredient, "status": "prepared"}


            def serve(dish: dict) -> str:
                """Serve a prepared dish.

                Parameters
                ----------
                dish : dict
                    A dictionary representing the dish to serve.

                Returns
                -------
                str
                    A message indicating the dish has been served.

                Examples
                --------
                >>> serve({"name": "pasta"})
                'Serving pasta'
                """
                return f"Serving {dish.get('name', 'dish')}"
        ''',
        "cookbook/recipe1.qmd": (
            "---\ntitle: Recipe One\n---\n\n# Recipe One\n\nThe first recipe in the cookbook.\n"
        ),
        "cookbook/recipe2.qmd": (
            "---\ntitle: Recipe Two\n---\n\n# Recipe Two\n\nThe second recipe in the cookbook.\n"
        ),
        "README.md": ("# gdtest-v2-sec-navbar-after\n\nTest custom section with navbar_after.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-navbar-after",
        "detected_module": "gdtest_sec_navbar_after",
        "detected_parser": "numpy",
        "export_names": ["prepare", "serve"],
        "num_exports": 2,
    },
}
