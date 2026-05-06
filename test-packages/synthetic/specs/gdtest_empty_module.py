"""
gdtest_empty_module — Module with only __version__.

Dimensions: A1, B1, C1, D4, E6, F6, G1, H7
Focus: Package that exports nothing — only has __version__. Tests
       that zero-export modules don't crash the build.
"""

SPEC = {
    "name": "gdtest_empty_module",
    "description": "Module with nothing to document",
    "dimensions": ["A1", "B1", "C1", "D4", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-empty-module",
            "version": "0.1.0",
            "description": "Test empty module handling",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_empty_module/__init__.py": '''\
            """An intentionally empty module — nothing to document."""

            __version__ = "0.1.0"
            __all__: list = []
        ''',
        "README.md": """\
            # gdtest-empty-module

            Tests that zero-export packages build without errors.
        """,
    },
    "expected": {
        "detected_name": "gdtest-empty-module",
        "detected_module": "gdtest_empty_module",
        "detected_parser": "numpy",
        "export_names": [],
        "num_exports": 0,
        "section_titles": [],
        "has_user_guide": False,
        "coverage_exclude": ['ref', 'nodoc', 'bigcl', 'ug', 'supp', 'title', 'badge', 'sig', 'desc', 'param', 'pmatch', 'ret', 'refidx', 'sechdg', 'sbar', 'sbsec', 'hdg'],
},
}
