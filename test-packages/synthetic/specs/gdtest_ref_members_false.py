"""
gdtest_ref_members_false — Reference config with members: false on a class.

Dimensions: P2
Focus: Reference config suppressing member display for a class using members: false.
"""

SPEC = {
    "name": "gdtest_ref_members_false",
    "description": "Reference config with members: false on a class.",
    "dimensions": ["P2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-members-false",
            "version": "0.1.0",
            "description": "Test reference config with members: false.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Core",
                "desc": "Core API",
                "contents": [
                    {"name": "Engine", "members": False},
                    {"name": "start_engine"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_members_false/__init__.py": '"""Test package for reference config with members: false."""\n',
        "gdtest_ref_members_false/core.py": '''
            """Core Engine class and start_engine function."""


            class Engine:
                """A configurable engine for processing tasks.

                Parameters
                ----------
                name : str
                    The name of the engine.

                Examples
                --------
                >>> e = Engine("turbo")
                >>> e.status()
                'idle'
                """

                def __init__(self, name: str):
                    """Initialize the engine.

                    Parameters
                    ----------
                    name : str
                        The name of the engine.
                    """
                    self.name = name
                    self._running = False

                def start(self) -> None:
                    """Start the engine.

                    Returns
                    -------
                    None
                    """
                    self._running = True

                def stop(self) -> None:
                    """Stop the engine.

                    Returns
                    -------
                    None
                    """
                    self._running = False

                def restart(self) -> None:
                    """Restart the engine by stopping and starting it.

                    Returns
                    -------
                    None
                    """
                    self.stop()
                    self.start()

                def status(self) -> str:
                    """Return the current status of the engine.

                    Returns
                    -------
                    str
                        Either 'running' or 'idle'.
                    """
                    return "running" if self._running else "idle"

                def configure(self, options: dict) -> None:
                    """Configure the engine with the given options.

                    Parameters
                    ----------
                    options : dict
                        A dictionary of configuration options.

                    Returns
                    -------
                    None
                    """
                    self._options = options


            def start_engine(config: dict) -> "Engine":
                """Create and start an engine with the given configuration.

                Parameters
                ----------
                config : dict
                    A dictionary of engine configuration options.

                Returns
                -------
                Engine
                    A running Engine instance.

                Examples
                --------
                >>> engine = start_engine({"name": "main"})
                >>> engine.status()
                'running'
                """
                engine = Engine(config.get("name", "default"))
                engine.start()
                return engine
        ''',
        "README.md": (
            "# gdtest-v2-ref-members-false\n\nTest reference config with members: false.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-members-false",
        "detected_module": "gdtest_ref_members_false",
        "detected_parser": "numpy",
        "export_names": ["Engine", "start_engine"],
        "num_exports": 2,
    },
}
