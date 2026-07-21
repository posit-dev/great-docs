"""
gdtest_config_exclude — Config-level exclusion.

Dimensions: A1, B5, C4, D1, E6, F6, G1, H7
Focus: __all__ includes items that are excluded via great-docs.yml config.
       Tests that config exclude is applied during section generation.
"""

SPEC = {
    "name": "gdtest_config_exclude",
    "description": "Config-level exclusion via great-docs.yml exclude list",
    "dimensions": ["A1", "B5", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-exclude",
            "version": "0.1.0",
            "description": "A synthetic test package testing config-based exclusion",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "exclude": ["helper_func", "InternalClass"],
    },
    "files": {
        "gdtest_config_exclude/__init__.py": '''\
            """A test package with config-level exclusions."""

            __version__ = "0.1.0"
            __all__ = ["PublicAPI", "transform", "helper_func", "InternalClass"]


            class PublicAPI:
                """
                The main public API class.

                Parameters
                ----------
                name
                    API name.
                """

                def __init__(self, name: str):
                    self.name = name

                def call(self) -> str:
                    """
                    Call the API.

                    Returns
                    -------
                    str
                        API response.
                    """
                    return f"response from {self.name}"


            class InternalClass:
                """
                An internal class excluded via config.

                This should NOT appear in documentation.
                """

                def __init__(self):
                    pass


            def transform(data: str) -> str:
                """
                Transform data.

                Parameters
                ----------
                data
                    Input data.

                Returns
                -------
                str
                    Transformed data.
                """
                return data.upper()


            def helper_func() -> None:
                """
                A helper function excluded via config.

                This should NOT appear in documentation.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-config-exclude

            A synthetic test package testing config-based exclusion.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-exclude",
        "detected_module": "gdtest_config_exclude",
        "detected_parser": "numpy",
        "export_names": ["PublicAPI", "transform"],
        "num_exports": 2,
        "config_excluded": ["helper_func", "InternalClass"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec"],
    },
}
