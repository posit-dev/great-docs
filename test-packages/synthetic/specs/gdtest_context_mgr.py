"""
gdtest_context_mgr — Context managers with __enter__/__exit__.

Dimensions: A1, B1, C21, D1, E6, F6, G1, H7
Focus: Context manager classes to verify __enter__/__exit__ dunder
       methods render correctly.
"""

SPEC = {
    "name": "gdtest_context_mgr",
    "description": "Context manager classes",
    "dimensions": ["A1", "B1", "C21", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-context-mgr",
            "version": "0.1.0",
            "description": "Test context manager documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_context_mgr/__init__.py": '''\
            """Package with context manager classes."""

            import time
            from typing import Optional

            __version__ = "0.1.0"
            __all__ = ["ManagedResource", "Timer"]


            class ManagedResource:
                """
                A resource that must be explicitly acquired and released.

                Parameters
                ----------
                name
                    Resource name.
                """

                def __init__(self, name: str):
                    self.name = name
                    self._acquired = False

                def __enter__(self) -> "ManagedResource":
                    """
                    Acquire the resource.

                    Returns
                    -------
                    ManagedResource
                        Self.
                    """
                    self._acquired = True
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb) -> None:
                    """
                    Release the resource.

                    Parameters
                    ----------
                    exc_type
                        Exception type, if any.
                    exc_val
                        Exception value, if any.
                    exc_tb
                        Traceback, if any.
                    """
                    self._acquired = False

                def is_acquired(self) -> bool:
                    """
                    Check if resource is currently acquired.

                    Returns
                    -------
                    bool
                        True if acquired.
                    """
                    return self._acquired


            class Timer:
                """
                A context manager for timing code blocks.

                Parameters
                ----------
                label
                    Optional label for the timer.
                """

                def __init__(self, label: Optional[str] = None):
                    self.label = label
                    self.start_time: Optional[float] = None
                    self.elapsed: Optional[float] = None

                def __enter__(self) -> "Timer":
                    """
                    Start the timer.

                    Returns
                    -------
                    Timer
                        Self.
                    """
                    self.start_time = time.monotonic()
                    return self

                def __exit__(self, exc_type, exc_val, exc_tb) -> None:
                    """Stop the timer and record elapsed time."""
                    if self.start_time is not None:
                        self.elapsed = time.monotonic() - self.start_time

                def report(self) -> str:
                    """
                    Return a human-readable timing report.

                    Returns
                    -------
                    str
                        Report string.
                    """
                    label = self.label or "Timer"
                    elapsed = self.elapsed or 0.0
                    return f"{label}: {elapsed:.4f}s"
        ''',
        "README.md": """\
            # gdtest-context-mgr

            Tests context manager classes with __enter__/__exit__.
        """,
    },
    "expected": {
        "detected_name": "gdtest-context-mgr",
        "detected_module": "gdtest_context_mgr",
        "detected_parser": "numpy",
        "export_names": ["ManagedResource", "Timer"],
        "num_exports": 2,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
