"""Deprecated parameters omitted from signatures and parameter descriptions"""

SPEC = {
    "name": "gdtest_nodoc_param",
    "description": "Exclude deprecated parameters from public documentation",
    "dimensions": ["A1", "B1", "C4", "D1", "E4", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {"name": "gdtest-nodoc-param", "version": "0.1.0"},
        "build-system": {"requires": ["setuptools"], "build-backend": "setuptools.build_meta"},
    },
    "files": {
        "gdtest_nodoc_param/__init__.py": '''
            """Deprecated arguments retained for compatibility"""

            __all__ = ['configure', 'Widget']

            def configure(value: int, old_option: bool = False) -> int:
                """
                Configure a value

                %nodoc_param old_option

                Parameters
                ----------
                value
                    The retained value.
                old_option
                    The excluded option description.

                Notes
                -----
                The previous option is deprecated.

                Examples
                --------
                ```text
                %nodoc_param literal_example
                ```
                """
                return value

            class Widget:
                """
                A configurable widget

                Parameters
                ----------
                value
                    The retained constructor value.
                old_option
                    The excluded constructor description.
                """

                def __init__(self, value: int, old_option: bool = False) -> None:
                    """
                    Configure the widget

                    %nodoc_param old_option
                    """
                    self.value = value
        ''',
        "README.md": "# Parameter exclusion\n\nKeep deprecated arguments out of public documentation.\n",
    },
    "expected": {
        "detected_name": "gdtest-nodoc-param",
        "detected_module": "gdtest_nodoc_param",
        "detected_parser": "numpy",
        "export_names": ["configure", "Widget"],
        "num_exports": 2,
        "documented_items": ["configure", "Widget"],
        "has_user_guide": False,
    },
}
