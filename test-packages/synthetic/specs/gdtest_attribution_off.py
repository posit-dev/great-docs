"""Tests that footer attribution text is omitted when attribution: false."""

SPEC = {
    "name": "gdtest_attribution_off",
    "description": (
        "Attribution disabled: footer should NOT contain 'Site created with Great Docs' text."
    ),
    "dimensions": ["K14", "K49"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-attribution-off",
            "version": "0.1.0",
            "description": "Test package for attribution off.",
            "authors": [{"name": "Test Author"}],
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "attribution": False,
        "authors": [
            {"name": "Test Author"},
        ],
    },
    "files": {
        "gdtest_attribution_off/__init__.py": '"""Attribution off test package."""\n',
        "gdtest_attribution_off/core.py": '''
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
        "coverage_exclude": [
            "ref",
            "nodoc",
            "bigcl",
            "ug",
            "supp",
            "title",
            "badge",
            "sig",
            "desc",
            "param",
            "pmatch",
            "ret",
            "refidx",
            "sechdg",
            "sbar",
            "sbsec",
            "hdg",
        ],
    },
}
