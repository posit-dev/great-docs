"""
gdtest_abstract_props — ABC with abstract methods and @property.

Dimensions: A1, B1, C16, D1, E6, F6, G1, H7
Focus: Abstract base class with abstract properties and a concrete
       subclass implementing them. Tests property/abstract rendering.
"""

SPEC = {
    "name": "gdtest_abstract_props",
    "description": "ABC with abstract properties",
    "dimensions": ["A1", "B1", "C16", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-abstract-props",
            "version": "0.1.0",
            "description": "Test abstract properties documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_abstract_props/__init__.py": '''\
            """Package with abstract properties."""

            from abc import ABC, abstractmethod
            import math

            __version__ = "0.1.0"
            __all__ = ["Shape", "Circle"]


            class Shape(ABC):
                """
                Abstract base class for geometric shapes.

                All shapes must implement area and perimeter properties.
                """

                @property
                @abstractmethod
                def area(self) -> float:
                    """
                    The area of the shape.

                    Returns
                    -------
                    float
                        Area value.
                    """
                    ...

                @property
                @abstractmethod
                def perimeter(self) -> float:
                    """
                    The perimeter of the shape.

                    Returns
                    -------
                    float
                        Perimeter value.
                    """
                    ...

                def describe(self) -> str:
                    """
                    Describe the shape.

                    Returns
                    -------
                    str
                        Human-readable description.
                    """
                    return f"Shape with area={self.area:.2f}, perimeter={self.perimeter:.2f}"


            class Circle(Shape):
                """
                A circle shape.

                Parameters
                ----------
                radius
                    The radius of the circle.
                """

                def __init__(self, radius: float):
                    self.radius = radius

                @property
                def area(self) -> float:
                    """
                    Area of the circle (pi * r^2).

                    Returns
                    -------
                    float
                        Area value.
                    """
                    return math.pi * self.radius ** 2

                @property
                def perimeter(self) -> float:
                    """
                    Perimeter (circumference) of the circle (2 * pi * r).

                    Returns
                    -------
                    float
                        Perimeter value.
                    """
                    return 2 * math.pi * self.radius
        ''',
        "README.md": """\
            # gdtest-abstract-props

            Tests ABC with abstract properties and concrete subclass.
        """,
    },
    "expected": {
        "detected_name": "gdtest-abstract-props",
        "detected_module": "gdtest_abstract_props",
        "detected_parser": "numpy",
        "export_names": ["Shape", "Circle"],
        "num_exports": 2,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
