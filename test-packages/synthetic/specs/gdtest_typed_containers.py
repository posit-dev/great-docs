"""
gdtest_typed_containers — NamedTuple and TypedDict.

Dimensions: A1, B1, C7, D1, E6, F6, G1, H7
Focus: 1 NamedTuple (class syntax), 1 TypedDict.
       Tests typed container field documentation.
"""

SPEC = {
    "name": "gdtest_typed_containers",
    "description": "NamedTuple + TypedDict",
    "dimensions": ["A1", "B1", "C7", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-typed-containers",
            "version": "0.1.0",
            "description": "A synthetic test package with typed containers",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_typed_containers/__init__.py": '''\
            """A test package with NamedTuple and TypedDict."""

            __version__ = "0.1.0"
            __all__ = ["Coordinate", "UserProfile"]

            from typing import NamedTuple, TypedDict


            class Coordinate(NamedTuple):
                """
                A geographic coordinate.

                Parameters
                ----------
                latitude
                    Latitude in degrees (-90 to 90).
                longitude
                    Longitude in degrees (-180 to 180).
                altitude
                    Altitude in meters above sea level.
                """
                latitude: float
                longitude: float
                altitude: float = 0.0


            class UserProfile(TypedDict, total=False):
                """
                A user profile dictionary.

                Parameters
                ----------
                name
                    The user's display name.
                email
                    The user's email address.
                age
                    The user's age in years.
                active
                    Whether the user account is active.
                """
                name: str
                email: str
                age: int
                active: bool
        ''',
        "README.md": """\
            # gdtest-typed-containers

            A synthetic test package with ``NamedTuple`` and ``TypedDict``.
        """,
    },
    "expected": {
        "detected_name": "gdtest-typed-containers",
        "detected_module": "gdtest_typed_containers",
        "detected_parser": "numpy",
        "export_names": ["Coordinate", "UserProfile"],
        "num_exports": 2,
        "section_titles": ["Named Tuples", "Typed Dicts"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
