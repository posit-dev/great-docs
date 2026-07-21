"""
gdtest_name_mismatch — Project name ≠ module name.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: pyproject.toml has ``name = "gdtest-name-mismatch"`` but the
importable module is ``gdtest_nm``. Config uses ``module: gdtest_nm``
to override detection.
"""

SPEC = {
    "name": "gdtest_name_mismatch",
    "description": "Project name does not match module name; config overrides",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-name-mismatch",
            "version": "0.1.0",
            "description": "A package where project name differs from module name",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_nm/__init__.py": '''\
            """A package with a mismatched project/module name."""

            __version__ = "0.1.0"
            __all__ = ["transform", "Mapper"]


            def transform(data: list, func: object = None) -> list:
                """
                Transform data using a function.

                Parameters
                ----------
                data
                    The data to transform.
                func
                    Optional transformation function.

                Returns
                -------
                list
                    Transformed data.
                """
                if func is None:
                    return data
                return [func(item) for item in data]


            class Mapper:
                """
                A data mapper.

                Parameters
                ----------
                mapping
                    A dictionary mapping keys to values.
                """

                def __init__(self, mapping: dict):
                    self.mapping = mapping

                def apply(self, key: str) -> object:
                    """
                    Look up a key in the mapping.

                    Parameters
                    ----------
                    key
                        The key to look up.

                    Returns
                    -------
                    object
                        The mapped value.
                    """
                    return self.mapping.get(key)

                def keys(self) -> list:
                    """
                    Get all keys.

                    Returns
                    -------
                    list
                        All mapping keys.
                    """
                    return list(self.mapping.keys())
        ''',
        "README.md": """\
            # gdtest-name-mismatch

            Project name and module name are different.
        """,
    },
    "config": {
        "module": "gdtest_nm",
    },
    "expected": {
        "detected_name": "gdtest-name-mismatch",
        "detected_module": "gdtest_nm",
        "detected_parser": "numpy",
        "export_names": ["transform", "Mapper"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "name_module_mismatch": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
