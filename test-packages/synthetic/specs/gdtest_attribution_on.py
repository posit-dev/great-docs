"""Tests that footer attribution text appears when attribution is enabled (default)."""

SPEC = {
    "name": "gdtest_attribution_on",
    "description": (
        "Attribution enabled (default): footer should contain "
        "'Site created with Great Docs (v...)' after the author line."
    ),
    "dimensions": ["K14", "K48"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-attribution-on",
            "version": "0.1.0",
            "description": "Test package for attribution on.",
            "authors": [{"name": "Test Author"}],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "authors": [
            {"name": "Test Author"},
        ],
    },
    "files": {
        "gdtest_attribution_on/__init__.py": '"""Attribution on test package."""\n',
        "gdtest_attribution_on/core.py": '''
            """Core functions."""


            def greet(name: str) -> str:
                """Greet someone by name.

                Parameters
                ----------
                name : str
                    The name to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"
        ''',
    },
    "expected": {
        "build_succeeds": True,
        "files_exist": [
            "great-docs/reference/index.html",
            "great-docs/reference/greet.html",
        ],
        "coverage_exclude": ['ref', 'nodoc', 'bigcl', 'ug', 'supp', 'title', 'badge', 'sig', 'desc', 'param', 'pmatch', 'ret', 'refidx', 'sechdg', 'sbar', 'sbsec', 'hdg'],
},
}
