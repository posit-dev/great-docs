"""
gdtest_parser_sphinx — Tests parser: 'sphinx' config.

Dimensions: K11
Focus: parser config option set to 'sphinx' with Sphinx :param:/:returns:/:rtype:/:raises: docstrings.
"""

SPEC = {
    "name": "gdtest_parser_sphinx",
    "description": "Tests parser: sphinx config",
    "dimensions": ["K11"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-parser-sphinx",
            "version": "0.1.0",
            "description": "Test parser sphinx config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "sphinx",
    },
    "files": {
        "gdtest_parser_sphinx/__init__.py": '''\
            """Package testing parser sphinx config."""

            __version__ = "0.1.0"
            __all__ = ["Timer", "create_timer", "format_duration"]


            class Timer:
                """A simple timer for measuring elapsed time.

                :param name: The name of the timer.
                :type name: str
                """

                def __init__(self, name: str = "default"):
                    self.name = name
                    self._start = None
                    self._end = None

                def start(self):
                    """Start the timer.

                    :returns: None
                    """
                    self._start = 0.0

                def stop(self):
                    """Stop the timer.

                    :returns: None
                    """
                    self._end = 1.0

                def elapsed(self) -> float:
                    """Return the elapsed time in seconds.

                    :returns: The elapsed time.
                    :rtype: float
                    :raises RuntimeError: If the timer has not been started.
                    """
                    if self._start is None:
                        raise RuntimeError("Timer not started")
                    return (self._end or 0.0) - self._start


            def create_timer(name: str) -> "Timer":
                """Create a new Timer instance.

                :param name: The name for the new timer.
                :type name: str
                :returns: A new Timer instance.
                :rtype: Timer
                """
                return Timer(name=name)


            def format_duration(seconds: float) -> str:
                """Format a duration in seconds as a human-readable string.

                :param seconds: The duration in seconds.
                :type seconds: float
                :returns: A formatted duration string.
                :rtype: str
                """
                return f"{seconds:.2f}s"
        ''',
        "README.md": """\
            # gdtest-v2-parser-sphinx

            Tests parser: sphinx config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-parser-sphinx",
        "detected_module": "gdtest_parser_sphinx",
        "detected_parser": "sphinx",
        "export_names": ["Timer", "create_timer", "format_duration"],
        "num_exports": 3,
    },
}
