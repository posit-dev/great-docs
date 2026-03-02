"""
gdtest_sphinx — Sphinx/reST-style docstrings.

Dimensions: A1, B1, C4, D3, E6, F6, G1, H7
Focus: 2 functions + 1 class with Sphinx-format docstrings (:param:, :returns:, :rtype:).
       Tests Sphinx parser auto-detection and mixed class/function output.
"""

SPEC = {
    "name": "gdtest_sphinx",
    "description": "Sphinx/reST-style docstrings; format_duration is %nodoc and should not appear",
    "dimensions": ["A1", "B1", "C4", "D3", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sphinx",
            "version": "0.1.0",
            "description": "A synthetic test package with Sphinx-style docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx/__init__.py": '''\
            """A test package using Sphinx/reST-style docstrings."""

            __version__ = "0.1.0"
            __all__ = ["Timer", "start_timer", "format_duration"]


            class Timer:
                """A simple timer for measuring elapsed time.

                :param label: A label for this timer instance.
                :type label: str
                :param auto_start: Whether to start timing immediately.
                :type auto_start: bool
                """

                def __init__(self, label: str, auto_start: bool = False):
                    self.label = label
                    self._elapsed = 0.0
                    if auto_start:
                        self.start()

                def start(self) -> None:
                    """Start the timer.

                    :raises RuntimeError: If the timer is already running.
                    """
                    pass

                def stop(self) -> float:
                    """Stop the timer and return elapsed time.

                    :returns: The elapsed time in seconds.
                    :rtype: float
                    """
                    return self._elapsed

                def reset(self) -> None:
                    """Reset the timer to zero."""
                    self._elapsed = 0.0


            def start_timer(label: str) -> Timer:
                """Create and start a new timer.

                :param label: The timer label.
                :type label: str
                :returns: A started timer instance.
                :rtype: Timer
                """
                return Timer(label, auto_start=True)


            def format_duration(seconds: float, precision: int = 2) -> str:
                """Format a duration in seconds as a human-readable string.

                %nodoc

                :param seconds: The duration in seconds.
                :param precision: Number of decimal places.
                :returns: Formatted duration string (e.g., ``"1.50s"``).
                :rtype: str
                """
                return f"{seconds:.{precision}f}s"
        ''',
        "README.md": """\
            # gdtest-sphinx

            A synthetic test package with Sphinx/reST-style docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-sphinx",
        "detected_module": "gdtest_sphinx",
        "detected_parser": "sphinx",
        "export_names": ["Timer", "start_timer", "format_duration"],
        "num_exports": 3,
        "nodoc_items": ['format_duration'],
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
