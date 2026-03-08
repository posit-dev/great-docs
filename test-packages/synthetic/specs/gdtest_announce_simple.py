"""
gdtest_announce_simple — Tests announcement banner with a simple string.

Dimensions: K25
Focus: announcement config as a plain string renders meta tag + script.
"""

SPEC = {
    "name": "gdtest_announce_simple",
    "description": "Tests announcement banner with a simple string config",
    "dimensions": ["K25"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-announce-simple",
            "version": "0.1.0",
            "description": "Test announcement banner simple config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "announcement": "This is a test announcement!",
    },
    "files": {
        "gdtest_announce_simple/__init__.py": '''\
            """Package testing announcement banner with simple string."""

            __version__ = "0.1.0"
            __all__ = ["greet", "farewell"]


            def greet(name: str) -> str:
                """
                Greet someone by name.

                Parameters
                ----------
                name
                    The person to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"


            def farewell(name: str) -> str:
                """
                Say goodbye to someone.

                Parameters
                ----------
                name
                    The person to say goodbye to.

                Returns
                -------
                str
                    A farewell string.
                """
                return f"Goodbye, {name}!"
        ''',
    },
    "expected": {
        "export_names": ["greet", "farewell"],
        "section_titles": ["Functions"],
    },
}
