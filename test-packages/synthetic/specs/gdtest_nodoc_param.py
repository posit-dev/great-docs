"""Deprecated parameters omitted from signatures, parameter descriptions and dataclass fields"""

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

            from dataclasses import dataclass

            __all__ = ['configure', 'Widget', 'Settings']

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

            @dataclass
            class Settings:
                """
                Plot settings

                %nodoc_param old_dpi
                """

                dpi: int = 100
                "The retained resolution"
                old_dpi: int = 0
                "The excluded resolution"
                title: str = "plot"
                "The retained title"

                def scale(self, factor: float) -> float:
                    """Scale the resolution"""
                    return self.dpi * factor
        ''',
        "README.md": "# Parameter exclusion\n\nKeep deprecated arguments out of public documentation.\n",
    },
    "expected": {
        "detected_name": "gdtest-nodoc-param",
        "detected_module": "gdtest_nodoc_param",
        "detected_parser": "numpy",
        "export_names": ["configure", "Widget", "Settings"],
        "num_exports": 3,
        "documented_items": ["configure", "Widget", "Settings"],
        "has_user_guide": False,
    },
}
