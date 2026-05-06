"""
gdtest_frozen_dc — Frozen dataclass.

Dimensions: A1, B1, C19, D1, E6, F6, G1, H7
Focus: @dataclass(frozen=True) with typed fields. Tests that frozen
       dataclasses are introspected without errors.
"""

SPEC = {
    "name": "gdtest_frozen_dc",
    "description": "Frozen dataclass (@dataclass(frozen=True))",
    "dimensions": ["A1", "B1", "C19", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-frozen-dc",
            "version": "0.1.0",
            "description": "Test frozen dataclass documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_frozen_dc/__init__.py": '''\
            """Package with frozen dataclasses."""

            from dataclasses import dataclass, field

            __version__ = "0.1.0"
            __all__ = ["Coordinate", "BoundingBox"]


            @dataclass(frozen=True)
            class Coordinate:
                """
                An immutable 2D coordinate.

                Parameters
                ----------
                x
                    X coordinate.
                y
                    Y coordinate.
                label
                    Optional label.
                """

                x: float
                y: float
                label: str = ""

                def distance_to(self, other: "Coordinate") -> float:
                    """
                    Calculate distance to another coordinate.

                    Parameters
                    ----------
                    other
                        The other coordinate.

                    Returns
                    -------
                    float
                        Euclidean distance.
                    """
                    return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


            @dataclass(frozen=True)
            class BoundingBox:
                """
                An immutable bounding box defined by two corners.

                Parameters
                ----------
                min_corner
                    Bottom-left corner.
                max_corner
                    Top-right corner.
                """

                min_corner: Coordinate
                max_corner: Coordinate

                @property
                def width(self) -> float:
                    """
                    Width of the bounding box.

                    Returns
                    -------
                    float
                        Width.
                    """
                    return abs(self.max_corner.x - self.min_corner.x)

                @property
                def height(self) -> float:
                    """
                    Height of the bounding box.

                    Returns
                    -------
                    float
                        Height.
                    """
                    return abs(self.max_corner.y - self.min_corner.y)
        ''',
        "README.md": """\
            # gdtest-frozen-dc

            Tests frozen dataclass documentation.
        """,
    },
    "expected": {
        "detected_name": "gdtest-frozen-dc",
        "detected_module": "gdtest_frozen_dc",
        "detected_parser": "numpy",
        "export_names": ["Coordinate", "BoundingBox"],
        "num_exports": 2,
        "section_titles": ["Dataclasses"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
