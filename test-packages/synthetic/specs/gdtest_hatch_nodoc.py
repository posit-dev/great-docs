"""
gdtest_hatch_nodoc — Hatch layout + %nodoc directive + dataclasses.

Dimensions: A5, C5, E4
Focus: Cross-dimension test combining Hatch build layout with dataclasses
       and %nodoc to exclude specific items from documentation.
"""

SPEC = {
    "name": "gdtest_hatch_nodoc",
    "description": (
        "Hatch layout + dataclasses + %nodoc directive. "
        "Tests build layout, object types, and exclusion via directive."
    ),
    "dimensions": ["A5", "C5", "E4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hatch-nodoc",
            "version": "0.1.0",
            "description": "Test package for Hatch layout + dataclasses + nodoc.",
        },
        "build-system": {
            "requires": ["hatchling"],
            "build-backend": "hatchling.build",
        },
    },
    "files": {
        "src/gdtest_hatch_nodoc/__init__.py": '''\
            """Package with Hatch layout, dataclasses, and nodoc directives."""

            __version__ = "0.1.0"
            __all__ = ["Config", "UserProfile", "InternalState", "create_config"]
        ''',
        "src/gdtest_hatch_nodoc/models.py": '''\
            """Data models with nodoc directive."""

            from dataclasses import dataclass, field


            @dataclass
            class Config:
                """
                Application configuration.

                Parameters
                ----------
                name : str
                    The application name.
                debug : bool
                    Whether debug mode is enabled.
                max_retries : int
                    Maximum retry attempts.
                """

                name: str
                debug: bool = False
                max_retries: int = 3


            @dataclass
            class UserProfile:
                """
                User profile information.

                Parameters
                ----------
                username : str
                    The user's login name.
                email : str
                    The user's email address.
                roles : list[str]
                    Assigned roles.
                """

                username: str
                email: str
                roles: list[str] = field(default_factory=list)


            @dataclass
            class InternalState:
                """
                Internal state tracking — not for public use.

                %nodoc

                Parameters
                ----------
                counter : int
                    Internal counter.
                dirty : bool
                    Whether state has changed.
                """

                counter: int = 0
                dirty: bool = False


            def create_config(name: str, **kwargs) -> Config:
                """
                Create a Config instance with defaults.

                Parameters
                ----------
                name : str
                    The application name.
                **kwargs
                    Additional config fields.

                Returns
                -------
                Config
                    A new Config instance.
                """
                return Config(name=name, **kwargs)
        ''',
        "README.md": """\
            # gdtest-hatch-nodoc

            Test package with Hatch layout, dataclasses, and %nodoc directives.
        """,
    },
    "expected": {
        "detected_name": "gdtest-hatch-nodoc",
        "detected_module": "gdtest_hatch_nodoc",
        "detected_parser": "numpy",
        "export_names": ["Config", "InternalState", "UserProfile", "create_config"],
        "num_exports": 4,
    },
}
