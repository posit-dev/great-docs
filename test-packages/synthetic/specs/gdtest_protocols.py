"""
gdtest_protocols — ABC + Protocol abstract types.

Dimensions: A1, B1, C8, D1, E6, F6, G1, H7
Focus: 1 ABC subclass with @abstractmethod, 1 Protocol.
       Tests abstract method handling and protocol documentation.
"""

SPEC = {
    "name": "gdtest_protocols",
    "description": "ABC + Protocol abstract types",
    "dimensions": ["A1", "B1", "C8", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-protocols",
            "version": "0.1.0",
            "description": "A synthetic test package with ABC and Protocol",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_protocols/__init__.py": '''\
            """A test package with abstract base classes and protocols."""

            __version__ = "0.1.0"
            __all__ = ["Serializable", "Renderable"]

            from abc import ABC, abstractmethod
            from typing import Protocol, runtime_checkable


            class Serializable(ABC):
                """
                Abstract base class for serializable objects.

                Subclasses must implement ``to_bytes`` and ``from_bytes``.
                """

                @abstractmethod
                def to_bytes(self) -> bytes:
                    """
                    Serialize this object to bytes.

                    Returns
                    -------
                    bytes
                        The serialized representation.
                    """
                    ...

                @abstractmethod
                def from_bytes(self, data: bytes) -> "Serializable":
                    """
                    Deserialize from bytes.

                    Parameters
                    ----------
                    data
                        The bytes to deserialize.

                    Returns
                    -------
                    Serializable
                        A new instance.
                    """
                    ...

                def size(self) -> int:
                    """
                    Get the serialized size.

                    Returns
                    -------
                    int
                        Size in bytes.
                    """
                    return len(self.to_bytes())


            @runtime_checkable
            class Renderable(Protocol):
                """
                Protocol for objects that can be rendered to string.

                Any object with a ``render`` method returning ``str``
                satisfies this protocol.
                """

                def render(self) -> str:
                    """
                    Render this object as a string.

                    Returns
                    -------
                    str
                        The rendered representation.
                    """
                    ...
        ''',
        "README.md": """\
            # gdtest-protocols

            A synthetic test package with ``ABC`` and ``Protocol``.
        """,
    },
    "expected": {
        "detected_name": "gdtest-protocols",
        "detected_module": "gdtest_protocols",
        "detected_parser": "numpy",
        "export_names": ["Serializable", "Renderable"],
        "num_exports": 2,
        "section_titles": ["Abstract Classes", "Protocols"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
