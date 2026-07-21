"""
gdtest_multi_inherit — Diamond / multiple inheritance.

Dimensions: A1, B1, C17, D1, E6, F6, G1, H7
Focus: Base → Mixin1, Mixin2 → Combined class demonstrating
       multiple inheritance doesn't crash the renderer.
"""

SPEC = {
    "name": "gdtest_multi_inherit",
    "description": "Multiple inheritance (diamond pattern)",
    "dimensions": ["A1", "B1", "C17", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-multi-inherit",
            "version": "0.1.0",
            "description": "Test multiple inheritance documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_multi_inherit/__init__.py": '''\
            """Package with multiple inheritance patterns."""

            __version__ = "0.1.0"
            __all__ = ["Base", "LogMixin", "CacheMixin", "Combined"]


            class Base:
                """
                Base class with core functionality.

                Parameters
                ----------
                name
                    Instance name.
                """

                def __init__(self, name: str):
                    self.name = name

                def identify(self) -> str:
                    """
                    Return identity string.

                    Returns
                    -------
                    str
                        Identity.
                    """
                    return self.name


            class LogMixin:
                """Mixin that adds logging capability."""

                def log(self, message: str) -> None:
                    """
                    Log a message.

                    Parameters
                    ----------
                    message
                        Message to log.
                    """
                    print(f"[LOG] {message}")


            class CacheMixin:
                """Mixin that adds caching capability."""

                def cache(self, key: str, value) -> None:
                    """
                    Cache a value.

                    Parameters
                    ----------
                    key
                        Cache key.
                    value
                        Value to cache.
                    """
                    pass

                def get_cached(self, key: str):
                    """
                    Retrieve a cached value.

                    Parameters
                    ----------
                    key
                        Cache key.

                    Returns
                    -------
                    object
                        Cached value or None.
                    """
                    return None


            class Combined(Base, LogMixin, CacheMixin):
                """
                Combined class inheriting from Base, LogMixin, and CacheMixin.

                Parameters
                ----------
                name
                    Instance name.
                """

                def __init__(self, name: str):
                    super().__init__(name)

                def process(self) -> dict:
                    """
                    Process with logging and caching.

                    Returns
                    -------
                    dict
                        Processing results.
                    """
                    self.log(f"Processing {self.name}")
                    return {"name": self.name}
        ''',
        "README.md": """\
            # gdtest-multi-inherit

            Tests multiple inheritance (diamond pattern) documentation.
        """,
    },
    "expected": {
        "detected_name": "gdtest-multi-inherit",
        "detected_module": "gdtest_multi_inherit",
        "detected_parser": "numpy",
        "export_names": ["Base", "LogMixin", "CacheMixin", "Combined"],
        "num_exports": 4,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
