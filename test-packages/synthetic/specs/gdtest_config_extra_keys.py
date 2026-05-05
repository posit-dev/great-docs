"""
gdtest_config_extra_keys — Config with unrecognized YAML keys.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Config YAML includes unknown keys (custom_field, future_option)
       alongside valid ones. Build should succeed — forward-compat test.
"""

SPEC = {
    "name": "gdtest_config_extra_keys",
    "description": "Config with unrecognized keys for forward compatibility",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-extra-keys",
            "version": "0.1.0",
            "description": "Test forward-compatible config parsing",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Extra Keys Test",
        "custom_field": "this-should-be-ignored",
        "future_option": True,
        "nested_unknown": {
            "level": 2,
            "items": ["a", "b", "c"],
        },
    },
    "files": {
        "gdtest_config_extra_keys/__init__.py": '''\
            """Package testing forward-compatible config parsing."""

            __version__ = "0.1.0"
            __all__ = ["echo", "identity"]


            def echo(message: str) -> str:
                """
                Echo a message back.

                Parameters
                ----------
                message
                    The message to echo.

                Returns
                -------
                str
                    The same message.
                """
                return message


            def identity(x):
                """
                Return the input unchanged.

                Parameters
                ----------
                x
                    Any value.

                Returns
                -------
                object
                    The same value.
                """
                return x
        ''',
        "README.md": """\
            # gdtest-config-extra-keys

            Tests that unrecognized config keys are silently ignored.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-extra-keys",
        "detected_module": "gdtest_config_extra_keys",
        "detected_parser": "numpy",
        "export_names": ["echo", "identity"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
