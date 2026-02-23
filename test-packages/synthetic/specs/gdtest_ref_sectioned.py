"""
gdtest_ref_sectioned — Reference with 4 named sections.

Dimensions: P5
Focus: Reference config with four distinct named sections, each containing two functions.
"""

SPEC = {
    "name": "gdtest_ref_sectioned",
    "description": "Reference with 4 named sections, each containing two functions.",
    "dimensions": ["P5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-sectioned",
            "version": "0.1.0",
            "description": "Test reference with 4 named sections.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Constructors",
                "desc": "Create objects",
                "contents": [
                    {"name": "create_widget"},
                    {"name": "create_layout"},
                ],
            },
            {
                "title": "Transformers",
                "desc": "Transform data",
                "contents": [
                    {"name": "resize"},
                    {"name": "rotate"},
                ],
            },
            {
                "title": "Validators",
                "desc": "Validate input",
                "contents": [
                    {"name": "check_bounds"},
                    {"name": "check_type"},
                ],
            },
            {
                "title": "Utilities",
                "desc": "Helper utils",
                "contents": [
                    {"name": "to_string"},
                    {"name": "from_string"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_sectioned/__init__.py": '"""Test package for reference with 4 named sections."""\n',
        "gdtest_ref_sectioned/constructors.py": '''
            """Constructor functions for creating widgets and layouts."""


            def create_widget(name: str, width: int = 100) -> dict:
                """Create a new widget with the given name and width.

                Parameters
                ----------
                name : str
                    The name of the widget.
                width : int, optional
                    The width of the widget in pixels, by default 100.

                Returns
                -------
                dict
                    A dictionary representing the created widget.

                Examples
                --------
                >>> create_widget("button")
                {'name': 'button', 'width': 100}
                """
                return {"name": name, "width": width}


            def create_layout(orientation: str = "horizontal") -> dict:
                """Create a new layout container.

                Parameters
                ----------
                orientation : str, optional
                    The layout orientation, by default "horizontal".

                Returns
                -------
                dict
                    A dictionary representing the created layout.

                Examples
                --------
                >>> create_layout("vertical")
                {'orientation': 'vertical', 'children': []}
                """
                return {"orientation": orientation, "children": []}
        ''',
        "gdtest_ref_sectioned/transformers.py": '''
            """Transformer functions for resizing and rotating."""


            def resize(obj: dict, scale: float) -> dict:
                """Resize an object by the given scale factor.

                Parameters
                ----------
                obj : dict
                    The object to resize.
                scale : float
                    The scale factor to apply.

                Returns
                -------
                dict
                    The resized object.

                Examples
                --------
                >>> resize({"width": 100}, 0.5)
                {'width': 50.0}
                """
                return {k: v * scale if isinstance(v, (int, float)) else v for k, v in obj.items()}


            def rotate(obj: dict, angle: float) -> dict:
                """Rotate an object by the given angle in degrees.

                Parameters
                ----------
                obj : dict
                    The object to rotate.
                angle : float
                    The rotation angle in degrees.

                Returns
                -------
                dict
                    The rotated object with angle metadata.

                Examples
                --------
                >>> rotate({"name": "box"}, 90.0)
                {'name': 'box', 'rotation': 90.0}
                """
                obj["rotation"] = angle
                return obj
        ''',
        "gdtest_ref_sectioned/validators.py": '''
            """Validator functions for checking bounds and types."""


            def check_bounds(value: float, low: float, high: float) -> bool:
                """Check if a value is within the given bounds.

                Parameters
                ----------
                value : float
                    The value to check.
                low : float
                    The lower bound (inclusive).
                high : float
                    The upper bound (inclusive).

                Returns
                -------
                bool
                    True if the value is within bounds.

                Examples
                --------
                >>> check_bounds(5.0, 0.0, 10.0)
                True
                """
                return low <= value <= high


            def check_type(obj: object, expected: type) -> bool:
                """Check if an object is of the expected type.

                Parameters
                ----------
                obj : object
                    The object to type-check.
                expected : type
                    The expected type.

                Returns
                -------
                bool
                    True if the object matches the expected type.

                Examples
                --------
                >>> check_type("hello", str)
                True
                """
                return isinstance(obj, expected)
        ''',
        "gdtest_ref_sectioned/utilities.py": '''
            """Utility functions for string conversion."""


            def to_string(obj: object) -> str:
                """Convert an object to its string representation.

                Parameters
                ----------
                obj : object
                    The object to convert.

                Returns
                -------
                str
                    The string representation of the object.

                Examples
                --------
                >>> to_string(42)
                '42'
                """
                return str(obj)


            def from_string(text: str) -> object:
                """Parse a string into a Python object.

                Parameters
                ----------
                text : str
                    The string to parse.

                Returns
                -------
                object
                    The parsed object, or the original string if parsing fails.

                Examples
                --------
                >>> from_string("42")
                42
                """
                try:
                    return int(text)
                except ValueError:
                    try:
                        return float(text)
                    except ValueError:
                        return text
        ''',
        "README.md": ("# gdtest-v2-ref-sectioned\n\nTest reference with 4 named sections.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-sectioned",
        "detected_module": "gdtest_ref_sectioned",
        "detected_parser": "numpy",
        "export_names": [
            "check_bounds",
            "check_type",
            "create_layout",
            "create_widget",
            "from_string",
            "resize",
            "rotate",
            "to_string",
        ],
        "num_exports": 8,
    },
}
