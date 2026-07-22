"""
gdtest_small_class — Classes with ≤5 public methods.

Dimensions: A1, B1, C2, D1, E6, F6, G1, H7
Focus: 2 classes with 3 methods each, inline method documentation
       (no separate method section). Tests that small classes don't get
       the "ClassName Methods" treatment.
"""

SPEC = {
    "name": "gdtest_small_class",
    "description": "Small classes (≤5 methods) — inline docs",
    "dimensions": ["A1", "B1", "C2", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-small-class",
            "version": "0.1.0",
            "description": "A synthetic test package with small classes",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_small_class/__init__.py": '''\
            """A test package with small classes (≤5 methods each)."""

            __version__ = "0.1.0"
            __all__ = ["Point", "Color"]


            class Point:
                """
                A 2D point.

                Parameters
                ----------
                x
                    The x coordinate.
                y
                    The y coordinate.
                """

                def __init__(self, x: float = 0.0, y: float = 0.0):
                    self.x = x
                    self.y = y

                def distance_to(self, other: "Point") -> float:
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

                def translate(self, dx: float, dy: float) -> "Point":
                    """
                    Return a new point translated by (dx, dy).

                    Parameters
                    ----------
                    dx
                        Horizontal offset.
                    dy
                        Vertical offset.

                    Returns
                    -------
                    Point
                        New translated point.
                    """
                    return Point(self.x + dx, self.y + dy)

                def as_tuple(self) -> tuple:
                    """
                    Convert to a tuple.

                    Returns
                    -------
                    tuple
                        (x, y) tuple.
                    """
                    return (self.x, self.y)


            class Color:
                """
                An RGB color.

                Parameters
                ----------
                r
                    Red channel (0-255).
                g
                    Green channel (0-255).
                b
                    Blue channel (0-255).
                """

                def __init__(self, r: int = 0, g: int = 0, b: int = 0):
                    self.r = r
                    self.g = g
                    self.b = b

                def to_hex(self) -> str:
                    """
                    Convert to hex string.

                    Returns
                    -------
                    str
                        Hex color like ``#FF0000``.
                    """
                    return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

                def lighten(self, amount: float = 0.1) -> "Color":
                    """
                    Return a lighter version of this color.

                    Parameters
                    ----------
                    amount
                        Lighten factor (0.0 to 1.0).

                    Returns
                    -------
                    Color
                        New lighter color.
                    """
                    factor = 1 + amount
                    return Color(
                        min(255, int(self.r * factor)),
                        min(255, int(self.g * factor)),
                        min(255, int(self.b * factor)),
                    )

                def brightness(self) -> float:
                    """
                    Calculate perceived brightness.

                    Returns
                    -------
                    float
                        Brightness value (0.0 to 1.0).
                    """
                    return (0.299 * self.r + 0.587 * self.g + 0.114 * self.b) / 255
        ''',
        "README.md": """\
            # gdtest-small-class

            A synthetic test package with small classes (≤5 methods each).
        """,
    },
    "expected": {
        "detected_name": "gdtest-small-class",
        "detected_module": "gdtest_small_class",
        "detected_parser": "numpy",
        "export_names": ["Point", "Color"],
        "num_exports": 2,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
