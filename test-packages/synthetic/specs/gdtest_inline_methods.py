"""
Automatic placement with a limit of five documented members

Keep SmallWidget's three methods together and give BigProcessor's eight methods separate pages.
"""

SPEC = {
    "name": "gdtest_inline_methods",
    "description": "Places class members automatically with max_members_on_same_page: 5",
    "dimensions": ["K54"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-methods",
            "version": "0.1.0",
            "description": "Automatic member placement with a limit of five",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        # Default: max_members_on_same_page: 5 (split classes with >5 methods)
    },
    "files": {
        "gdtest_inline_methods/__init__.py": '''\
            """Automatic placement by documented member count"""

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

            With the default `max_members_on_same_page: 5`, `SmallWidget` keeps its
            3 methods on the class page. `BigProcessor` has 8 methods, so each gets
            its own page.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-methods",
        "detected_module": "gdtest_inline_methods",
        "detected_parser": "numpy",
        "export_names": ["SmallWidget", "BigProcessor", "helper_func"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "big_class_name": "BigProcessor",
        "big_class_member_count": 8,
        "inline_class_name": "SmallWidget",
        "same_page_member_count": 3,
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "ug", "supp", "hdg"],
    },
}
