"""
gdtest_slots_class — Class with __slots__.

Dimensions: A1, B1, C18, D1, E6, F6, G1, H7
Focus: Class using __slots__ instead of __dict__. Tests that slotted
       attributes render correctly.
"""

SPEC = {
    "name": "gdtest_slots_class",
    "description": "Class using __slots__",
    "dimensions": ["A1", "B1", "C18", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-slots-class",
            "version": "0.1.0",
            "description": "Test __slots__ class documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_slots_class/__init__.py": '''\
            """Package with a __slots__ class."""

            __version__ = "0.1.0"
            __all__ = ["SlottedPoint"]


            class SlottedPoint:
                """
                A 2D point using __slots__ for memory efficiency.

                Parameters
                ----------
                x
                    X coordinate.
                y
                    Y coordinate.
                label
                    Optional label for the point.
                """

                __slots__ = ("x", "y", "label")

                def __init__(self, x: float, y: float, label: str = ""):
                    self.x = x
                    self.y = y
                    self.label = label

                def distance_to(self, other: "SlottedPoint") -> float:
                    """
                    Calculate distance to another point.

                    Parameters
                    ----------
                    other
                        The other point.

                    Returns
                    -------
                    float
                        Euclidean distance.
                    """
                    return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

                def translate(self, dx: float, dy: float) -> "SlottedPoint":
                    """
                    Return a new point translated by (dx, dy).

                    Parameters
                    ----------
                    dx
                        X offset.
                    dy
                        Y offset.

                    Returns
                    -------
                    SlottedPoint
                        New translated point.
                    """
                    return SlottedPoint(self.x + dx, self.y + dy, self.label)

                def as_tuple(self) -> tuple:
                    """
                    Return coordinates as tuple.

                    Returns
                    -------
                    tuple
                        (x, y) tuple.
                    """
                    return (self.x, self.y)

                def __repr__(self) -> str:
                    """Return string representation."""
                    return f"SlottedPoint({self.x}, {self.y}, {self.label!r})"
        ''',
        "README.md": """\
            # gdtest-slots-class

            Tests documentation of a class using __slots__.
        """,
    },
    "expected": {
        "detected_name": "gdtest-slots-class",
        "detected_module": "gdtest_slots_class",
        "detected_parser": "numpy",
        "export_names": ["SlottedPoint"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
