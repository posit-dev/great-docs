"""
gdtest_many_exports — 30+ exported functions.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Large number of exports to stress-test rendering. All 30
       functions should appear without truncation.
"""

SPEC = {
    "name": "gdtest_many_exports",
    "description": "Module with 30+ exported functions",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-many-exports",
            "version": "0.1.0",
            "description": "Test large export count rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_many_exports/__init__.py": (
            '"""Package with many exported functions."""\n\n'
            '__version__ = "0.1.0"\n'
            "__all__ = ["
            + ", ".join(f'"func_{i:02d}"' for i in range(1, 31))
            + "]\n\n\n"
            + "\n\n".join(
                f"def func_{i:02d}(x: int) -> int:\n"
                f'    """\n'
                f"    Function number {i}.\n\n"
                f"    Parameters\n"
                f"    ----------\n"
                f"    x\n"
                f"        Input value.\n\n"
                f"    Returns\n"
                f"    -------\n"
                f"    int\n"
                f"        Processed value.\n"
                f'    """\n'
                f"    return x + {i}"
                for i in range(1, 31)
            )
            + "\n"
        ),
        "README.md": """\
            # gdtest-many-exports

            Tests rendering of a module with 30+ exports.
        """,
    },
    "expected": {
        "detected_name": "gdtest-many-exports",
        "detected_module": "gdtest_many_exports",
        "detected_parser": "numpy",
        "export_names": [f"func_{i:02d}" for i in range(1, 31)],
        "num_exports": 30,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
