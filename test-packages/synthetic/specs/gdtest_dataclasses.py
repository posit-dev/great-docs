"""
gdtest_dataclasses — @dataclass objects.

Dimensions: A1, B1, C5, D1, E6, F6, G1, H7
Focus: 3 dataclasses: one with default_factory, one frozen, one that also
       defines methods. Tests dataclass field documentation, __init__
       generation, and that a dataclass which defines methods still renders its
       constructor signature (regression: `Class.overloads` is a dict keyed by
       member name, so any class with methods was rendered through the overload
       path and lost its constructor parameters).
"""

SPEC = {
    "name": "gdtest_dataclasses",
    "description": "@dataclass objects with various field types",
    "dimensions": ["A1", "B1", "C5", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-dataclasses",
            "version": "0.1.0",
            "description": "A synthetic test package with dataclasses",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_dataclasses/__init__.py": '''\
            """A test package with dataclass objects."""

            __version__ = "0.1.0"
            __all__ = ["Config", "Record", "Mutable"]

            from dataclasses import dataclass, field


            @dataclass
            class Config:
                """
                Application configuration.

                Parameters
                ----------
                name
                    Configuration name.
                debug
                    Whether debug mode is enabled.
                tags
                    List of configuration tags.
                settings
                    Additional settings dictionary.
                """
                name: str
                debug: bool = False
                tags: list[str] = field(default_factory=list)
                settings: dict[str, str] = field(default_factory=dict)


            @dataclass(frozen=True)
            class Record:
                """
                An immutable data record.

                Parameters
                ----------
                id
                    Unique record identifier.
                value
                    The record value.
                timestamp
                    When the record was created.
                """
                id: int
                value: str
                timestamp: float = 0.0


            @dataclass
            class Mutable:
                """
                A mutable record that also defines methods.

                Parameters
                ----------
                label
                    Human-readable label.
                count
                    Current count.
                """
                label: str
                count: int = 0

                def increment(self, by: int = 1) -> None:
                    """Increase the count."""
                    self.count += by

                @classmethod
                def empty(cls) -> "Mutable":
                    """Create an empty record."""
                    return cls(label="")
        ''',
        "README.md": """\
            # gdtest-dataclasses

            A synthetic test package with ``@dataclass`` objects.
        """,
    },
    "expected": {
        "detected_name": "gdtest-dataclasses",
        "detected_module": "gdtest_dataclasses",
        "detected_parser": "numpy",
        "export_names": ["Config", "Record", "Mutable"],
        "num_exports": 3,
        "section_titles": ["Dataclasses"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
    },
}
