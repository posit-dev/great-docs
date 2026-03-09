"""
gdtest_header_list — Tests include_in_header with a list of text entries.

Dimensions: K41
Focus: include_in_header as a list injects multiple items into <head>.
"""

SPEC = {
    "name": "gdtest_header_list",
    "description": "Tests include_in_header with a list of text entries",
    "dimensions": ["K41"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-header-list",
            "version": "0.1.0",
            "description": "Test include_in_header list config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "include_in_header": [
            '<meta name="gd-list-item-one" content="first-injection">',
            {"text": '<meta name="gd-list-item-two" content="second-injection">'},
        ],
    },
    "files": {
        "gdtest_header_list/__init__.py": '''\
            """Package testing include_in_header with a list."""

            __version__ = "0.1.0"
            __all__ = ["greet", "shout"]


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


            def shout(msg: str) -> str:
                """
                Convert a message to uppercase.

                Parameters
                ----------
                msg
                    The message to shout.

                Returns
                -------
                str
                    Uppercased message.
                """
                return msg.upper()
        ''',
    },
    "expected": {
        "export_names": ["greet", "shout"],
        "section_titles": ["Functions"],
    },
}
