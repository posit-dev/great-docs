"""
gdtest_auto_discover — Auto-discover: no metadata, single package dir.

Dimensions: A9, B3, C4, D1, E6, F6, G1, H7
Focus: No pyproject.toml, no setup.cfg, no setup.py. Only a single
       package directory with __init__.py. No __all__ either.
       Tests Pass 3 auto-discovery + griffe fallback together.
"""

SPEC = {
    "name": "gdtest_auto_discover",
    "description": "Auto-discover: no metadata files, no __all__",
    "dimensions": ["A9", "B3", "C4", "D1", "E6", "F6", "G1", "H7"],
    # No pyproject_toml, no setup.cfg, no setup.py
    "files": {
        "gdtest_auto_discover/__init__.py": '''\
            """A test package discovered via auto-discovery."""

            __version__ = "0.1.0"


            class Engine:
                """
                A simple engine.

                Parameters
                ----------
                power
                    Engine power level.
                """

                def __init__(self, power: int = 100):
                    self.power = power

                def start(self) -> bool:
                    """
                    Start the engine.

                    Returns
                    -------
                    bool
                        True if started.
                    """
                    return True

                def stop(self) -> None:
                    """Stop the engine."""
                    pass


            def ignite(engine: "Engine") -> bool:
                """
                Ignite an engine.

                Parameters
                ----------
                engine
                    The engine to ignite.

                Returns
                -------
                bool
                    True if ignited.
                """
                return engine.start()


            def shutdown(engine: "Engine") -> None:
                """
                Shut down an engine.

                Parameters
                ----------
                engine
                    The engine to shut down.
                """
                engine.stop()
        ''',
        "README.md": """\
            # gdtest-auto-discover

            A package with no metadata files — tests pure auto-discovery.
        """,
    },
    "expected": {
        "detected_name": "gdtest_auto_discover",
        "detected_module": "gdtest_auto_discover",
        "detected_parser": "numpy",
        "export_names": ["Engine", "ignite", "shutdown"],
        "num_exports": 3,
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'sechdg', 'sbsec'],
},
}
