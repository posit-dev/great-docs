"""
gdtest_ref_inherited_explicit — Reference config with explicit inherited members.

Dimensions: P9
Focus: Reference config listing inherited methods explicitly via members list.
       The child class's reference page should document both its own and
       inherited methods specified in the members list.
"""

SPEC = {
    "name": "gdtest_ref_inherited_explicit",
    "description": "Reference config listing inherited methods explicitly.",
    "dimensions": ["P9"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ref-inherited-explicit",
            "version": "0.1.0",
            "description": "Test explicit inherited members in reference config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Core",
                "desc": "Core classes",
                "contents": [
                    "BaseProcessor",
                    {
                        "name": "AdvancedProcessor",
                        "members": ["process", "validate", "reset"],
                    },
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_inherited_explicit/__init__.py": '''\
            """Package testing explicit inherited member documentation."""

            __version__ = "0.1.0"
            __all__ = ["BaseProcessor", "AdvancedProcessor"]


            class BaseProcessor:
                """
                Base processor with core functionality.

                Parameters
                ----------
                name : str
                    Processor name.
                """

                def __init__(self, name: str):
                    self.name = name

                def validate(self, data: dict) -> bool:
                    """
                    Validate input data.

                    Parameters
                    ----------
                    data : dict
                        Data to validate.

                    Returns
                    -------
                    bool
                        True if valid.
                    """
                    return bool(data)

                def reset(self) -> None:
                    """
                    Reset the processor state.

                    Returns
                    -------
                    None
                    """
                    pass


            class AdvancedProcessor(BaseProcessor):
                """
                Advanced processor that inherits validate and reset from Base.

                Parameters
                ----------
                name : str
                    Processor name.
                mode : str
                    Processing mode.
                """

                def __init__(self, name: str, mode: str = "fast"):
                    super().__init__(name)
                    self.mode = mode

                def process(self, data: dict) -> dict:
                    """
                    Process data using the configured mode.

                    Parameters
                    ----------
                    data : dict
                        Data to process.

                    Returns
                    -------
                    dict
                        Processed results.
                    """
                    if self.validate(data):
                        return {"result": data, "mode": self.mode}
                    return {}
        ''',
        "README.md": (
            "# gdtest-ref-inherited-explicit\n\n"
            "Tests explicit inherited member documentation via reference config.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-ref-inherited-explicit",
        "detected_module": "gdtest_ref_inherited_explicit",
        "detected_parser": "numpy",
        "export_names": ["BaseProcessor", "AdvancedProcessor"],
        "num_exports": 2,
        "section_titles": ["Core"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
