"""
gdtest_ref_include_inherited — Reference config with include_inherited: true.

Dimensions: P10
Focus: Reference config using include_inherited: true to automatically
       document all inherited methods on a child class without listing them
       explicitly.
"""

SPEC = {
    "name": "gdtest_ref_include_inherited",
    "description": "Reference config with include_inherited: true flag.",
    "dimensions": ["P10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-ref-include-inherited",
            "version": "0.1.0",
            "description": "Test include_inherited flag in reference config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Shapes",
                "desc": "Shape hierarchy",
                "contents": [
                    "Shape",
                    {
                        "name": "Circle",
                        "include_inherited": True,
                    },
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_include_inherited/__init__.py": '''\
            """Package testing include_inherited flag."""

            __version__ = "0.1.0"
            __all__ = ["Shape", "Circle"]


            class Shape:
                """
                Abstract base shape.

                Parameters
                ----------
                color : str
                    Fill color.
                """

                def __init__(self, color: str = "red"):
                    self.color = color

                def area(self) -> float:
                    """
                    Compute the area of the shape.

                    Returns
                    -------
                    float
                        Area value.
                    """
                    raise NotImplementedError

                def perimeter(self) -> float:
                    """
                    Compute the perimeter of the shape.

                    Returns
                    -------
                    float
                        Perimeter value.
                    """
                    raise NotImplementedError

                def describe(self) -> str:
                    """
                    Return a human-readable description.

                    Returns
                    -------
                    str
                        Description string.
                    """
                    return f"{self.__class__.__name__}(color={self.color})"


            class Circle(Shape):
                """
                A circle shape.

                Parameters
                ----------
                radius : float
                    Circle radius.
                color : str
                    Fill color.
                """

                def __init__(self, radius: float, color: str = "blue"):
                    super().__init__(color)
                    self.radius = radius

                def area(self) -> float:
                    """
                    Compute the area of the circle.

                    Returns
                    -------
                    float
                        Pi * radius^2.
                    """
                    import math
                    return math.pi * self.radius ** 2

                def perimeter(self) -> float:
                    """
                    Compute the circumference.

                    Returns
                    -------
                    float
                        2 * pi * radius.
                    """
                    import math
                    return 2 * math.pi * self.radius
        ''',
        "README.md": (
            "# gdtest-ref-include-inherited\n\n"
            "Tests include_inherited: true flag for auto-documenting inherited methods.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-ref-include-inherited",
        "detected_module": "gdtest_ref_include_inherited",
        "detected_parser": "numpy",
        "export_names": ["Shape", "Circle"],
        "num_exports": 2,
        "section_titles": ["Shapes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
