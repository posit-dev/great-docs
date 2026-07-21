"""
gdtest_descriptors — Properties, classmethods, staticmethods.

Dimensions: A1, B1, C9, D1, E6, F6, G1, H7
Focus: 1 class with @property, @classmethod, @staticmethod.
       Tests descriptor type handling in method enumeration.
"""

SPEC = {
    "name": "gdtest_descriptors",
    "description": "Properties, classmethods, staticmethods",
    "dimensions": ["A1", "B1", "C9", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-descriptors",
            "version": "0.1.0",
            "description": "A synthetic test package with descriptor types",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_descriptors/__init__.py": '''\
            """A test package with various descriptor types."""

            __version__ = "0.1.0"
            __all__ = ["Resource"]


            class Resource:
                """
                A managed resource with properties and class/static methods.

                Parameters
                ----------
                name
                    Resource name.
                capacity
                    Maximum capacity.
                """

                _instances: list = []

                def __init__(self, name: str, capacity: int = 100):
                    self._name = name
                    self._capacity = capacity
                    self._used = 0

                @property
                def name(self) -> str:
                    """
                    The resource name.

                    Returns
                    -------
                    str
                        Resource name (read-only).
                    """
                    return self._name

                @property
                def available(self) -> int:
                    """
                    Available capacity.

                    Returns
                    -------
                    int
                        Remaining capacity.
                    """
                    return self._capacity - self._used

                @available.setter
                def available(self, value: int) -> None:
                    self._used = self._capacity - value

                def allocate(self, amount: int) -> bool:
                    """
                    Allocate some capacity.

                    Parameters
                    ----------
                    amount
                        Amount to allocate.

                    Returns
                    -------
                    bool
                        True if allocation succeeded.
                    """
                    if amount <= self.available:
                        self._used += amount
                        return True
                    return False

                @classmethod
                def from_dict(cls, data: dict) -> "Resource":
                    """
                    Create a Resource from a dictionary.

                    Parameters
                    ----------
                    data
                        Dictionary with 'name' and optional 'capacity' keys.

                    Returns
                    -------
                    Resource
                        A new resource instance.
                    """
                    return cls(name=data["name"], capacity=data.get("capacity", 100))

                @staticmethod
                def validate_name(name: str) -> bool:
                    """
                    Check whether a resource name is valid.

                    Parameters
                    ----------
                    name
                        The name to validate.

                    Returns
                    -------
                    bool
                        True if valid.
                    """
                    return bool(name) and name.isidentifier()
        ''',
        "README.md": """\
            # gdtest-descriptors

            A synthetic test package with ``@property``, ``@classmethod``, and ``@staticmethod``.
        """,
    },
    "expected": {
        "detected_name": "gdtest-descriptors",
        "detected_module": "gdtest_descriptors",
        "detected_parser": "numpy",
        "export_names": ["Resource"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
