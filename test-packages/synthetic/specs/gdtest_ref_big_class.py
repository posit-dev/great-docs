"""
gdtest_ref_big_class — Reference config with a big class (>5 methods).

Dimensions: P7
Focus: Reference config listing a class with many methods and members: true.
"""

SPEC = {
    "name": "gdtest_ref_big_class",
    "description": "Reference config with a big class having >5 methods.",
    "dimensions": ["P7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-big-class",
            "version": "0.1.0",
            "description": "Test reference config with a big class.",
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
                    {"name": "Manager", "members": True},
                    {"name": "create_manager"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_big_class/__init__.py": '"""Test package for reference config with a big class."""\n',
        "gdtest_ref_big_class/core.py": '''
            """Core Manager class and factory function."""


            class Manager:
                """A manager for orchestrating tasks and resources.

                Parameters
                ----------
                name : str
                    The name of the manager instance.

                Examples
                --------
                >>> m = Manager("prod")
                >>> m.status()
                'idle'
                """

                def __init__(self, name: str):
                    """Initialize the manager.

                    Parameters
                    ----------
                    name : str
                        The name of the manager.
                    """
                    self.name = name
                    self._running = False
                    self._config: dict = {}

                def start(self) -> None:
                    """Start the manager.

                    Returns
                    -------
                    None

                    Examples
                    --------
                    >>> m = Manager("test")
                    >>> m.start()
                    >>> m.status()
                    'running'
                    """
                    self._running = True

                def stop(self) -> None:
                    """Stop the manager.

                    Returns
                    -------
                    None

                    Examples
                    --------
                    >>> m = Manager("test")
                    >>> m.start()
                    >>> m.stop()
                    >>> m.status()
                    'idle'
                    """
                    self._running = False

                def restart(self) -> None:
                    """Restart the manager by stopping and starting it.

                    Returns
                    -------
                    None
                    """
                    self.stop()
                    self.start()

                def status(self) -> str:
                    """Return the current status of the manager.

                    Returns
                    -------
                    str
                        Either 'running' or 'idle'.
                    """
                    return "running" if self._running else "idle"

                def configure(self, options: dict) -> None:
                    """Configure the manager with the given options.

                    Parameters
                    ----------
                    options : dict
                        A dictionary of configuration options.

                    Returns
                    -------
                    None

                    Examples
                    --------
                    >>> m = Manager("test")
                    >>> m.configure({"timeout": 30})
                    """
                    self._config = options

                def report(self) -> dict:
                    """Generate a status report for the manager.

                    Returns
                    -------
                    dict
                        A dictionary containing the manager's status report.

                    Examples
                    --------
                    >>> m = Manager("test")
                    >>> m.report()
                    {'name': 'test', 'running': False}
                    """
                    return {"name": self.name, "running": self._running}


            def create_manager(name: str) -> Manager:
                """Create and return a new Manager instance.

                Parameters
                ----------
                name : str
                    The name for the new manager.

                Returns
                -------
                Manager
                    A new Manager instance.

                Examples
                --------
                >>> m = create_manager("main")
                >>> m.name
                'main'
                """
                return Manager(name)
        ''',
        "README.md": ("# gdtest-v2-ref-big-class\n\nTest reference config with a big class.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-big-class",
        "detected_module": "gdtest_ref_big_class",
        "detected_parser": "numpy",
        "export_names": ["Manager", "create_manager"],
        "num_exports": 2,
    },
}
