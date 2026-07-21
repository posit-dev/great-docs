"""
gdtest_inline_methods — Tests inline_methods config option variants.

Dimensions: K54
Focus: inline_methods config controlling whether class methods get their own
pages or stay inline on the class page. Uses three classes of different sizes
to demonstrate the default threshold (5), always-inline (true), and
always-split (false) behaviors.

This spec uses the default (inline_methods: 5), which matches the standard
behavior: classes with >5 methods get split, others stay inline.
"""

SPEC = {
    "name": "gdtest_inline_methods",
    "description": "Tests inline_methods config (default threshold of 5)",
    "dimensions": ["K54"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-methods",
            "version": "0.1.0",
            "description": "Test package for inline_methods config option",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        # Default: inline_methods: 5 (split classes with >5 methods)
    },
    "files": {
        "gdtest_inline_methods/__init__.py": '''\
            """Package testing inline_methods config option."""

            __version__ = "0.1.0"
            __all__ = ["SmallWidget", "BigProcessor", "helper_func"]


            class SmallWidget:
                """
                A widget with few methods (should stay inline with default threshold).

                Parameters
                ----------
                name
                    The widget name.
                """

                def __init__(self, name: str):
                    self.name = name

                def render(self) -> str:
                    """
                    Render the widget as HTML.

                    Returns
                    -------
                    str
                        HTML representation of the widget.
                    """
                    return f"<widget>{self.name}</widget>"

                def resize(self, width: int, height: int) -> None:
                    """
                    Resize the widget.

                    Parameters
                    ----------
                    width
                        New width in pixels.
                    height
                        New height in pixels.
                    """
                    pass

                def toggle(self) -> bool:
                    """
                    Toggle the widget visibility.

                    Returns
                    -------
                    bool
                        New visibility state.
                    """
                    return True


            class BigProcessor:
                """
                A processor with many methods (should split with default threshold).

                Parameters
                ----------
                config
                    Configuration dictionary.

                Examples
                --------
                >>> proc = BigProcessor({"verbose": True})
                >>> proc.validate()
                True
                """

                def __init__(self, config: dict):
                    self.config = config
                    self._data = None

                def load(self, path: str) -> None:
                    """
                    Load data from a file.

                    Parameters
                    ----------
                    path
                        Path to the data file.
                    """
                    self._data = path

                def transform(self, func) -> "BigProcessor":
                    """
                    Apply a transformation.

                    Parameters
                    ----------
                    func
                        A callable to apply.

                    Returns
                    -------
                    BigProcessor
                        Self for chaining.
                    """
                    return self

                def filter(self, predicate) -> "BigProcessor":
                    """
                    Filter data by predicate.

                    Parameters
                    ----------
                    predicate
                        Filter function returning bool.

                    Returns
                    -------
                    BigProcessor
                        Self for chaining.
                    """
                    return self

                def sort(self, key: str) -> "BigProcessor":
                    """
                    Sort data by key.

                    Parameters
                    ----------
                    key
                        The sort key.

                    Returns
                    -------
                    BigProcessor
                        Self for chaining.
                    """
                    return self

                def aggregate(self, func, column: str) -> "BigProcessor":
                    """
                    Aggregate data.

                    Parameters
                    ----------
                    func
                        Aggregation function.
                    column
                        Column to aggregate.

                    Returns
                    -------
                    BigProcessor
                        Self for chaining.
                    """
                    return self

                def validate(self) -> bool:
                    """
                    Validate current state.

                    Returns
                    -------
                    bool
                        True if valid.
                    """
                    return self._data is not None

                def export(self, path: str, fmt: str = "csv") -> None:
                    """
                    Export data to file.

                    Parameters
                    ----------
                    path
                        Output path.
                    fmt
                        Output format.
                    """
                    pass

                def summary(self) -> dict:
                    """
                    Get a data summary.

                    Returns
                    -------
                    dict
                        Summary statistics.
                    """
                    return {"has_data": self._data is not None}


            def helper_func(x: int, y: int) -> int:
                """
                Add two numbers.

                Parameters
                ----------
                x
                    First number.
                y
                    Second number.

                Returns
                -------
                int
                    Sum of x and y.
                """
                return x + y
        ''',
        "README.md": """\
            # gdtest-inline-methods

            Package testing the `inline_methods` config option with default
            threshold of 5. SmallWidget (3 methods) stays inline; BigProcessor
            (8 methods) gets split to separate pages.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-methods",
        "detected_module": "gdtest_inline_methods",
        "detected_parser": "numpy",
        "export_names": ["SmallWidget", "BigProcessor", "helper_func"],
        "num_exports": 3,
        "section_titles": ["Classes", "BigProcessor Methods", "Functions"],
        "big_class_name": "BigProcessor",
        "big_class_method_count": 8,
        "inline_class_name": "SmallWidget",
        "inline_class_method_count": 3,
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "ug", "supp", "hdg"],
    },
}
