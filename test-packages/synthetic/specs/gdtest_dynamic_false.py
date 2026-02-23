"""
gdtest_dynamic_false — Tests dynamic: false config.

Dimensions: K9
Focus: dynamic config option set to false.
"""

SPEC = {
    "name": "gdtest_dynamic_false",
    "description": "Tests dynamic: false config",
    "dimensions": ["K9"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-dynamic-false",
            "version": "0.1.0",
            "description": "Test dynamic false config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "dynamic": False,
    },
    "files": {
        "gdtest_dynamic_false/__init__.py": '''\
            """Package testing dynamic false config."""

            __version__ = "0.1.0"
            __all__ = ["greet", "farewell"]


            def greet(name: str) -> str:
                """
                Greet a person by name.

                Parameters
                ----------
                name
                    The name of the person to greet.

                Returns
                -------
                str
                    A greeting message.
                """
                return f"Hello, {name}!"


            def farewell(name: str) -> str:
                """
                Say farewell to a person by name.

                Parameters
                ----------
                name
                    The name of the person to bid farewell.

                Returns
                -------
                str
                    A farewell message.
                """
                return f"Goodbye, {name}!"
        ''',
        "README.md": """\
            # gdtest-v2-dynamic-false

            Tests dynamic: false config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-dynamic-false",
        "detected_module": "gdtest_dynamic_false",
        "detected_parser": "numpy",
        "export_names": ["farewell", "greet"],
        "num_exports": 2,
    },
}
