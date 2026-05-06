"""
gdtest_pdm — PDM build backend.

Dimensions: A11, B1, C1, D1, E6, F6, G1, H7
Focus: Package using pdm.backend as the build backend. Tests that
       PDM-style pyproject.toml is recognized.
"""

SPEC = {
    "name": "gdtest_pdm",
    "description": "PDM build backend",
    "dimensions": ["A11", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-pdm",
            "version": "0.1.0",
            "description": "Test PDM build system",
        },
        "build-system": {
            "requires": ["pdm-backend"],
            "build-backend": "pdm.backend",
        },
    },
    "files": {
        "gdtest_pdm/__init__.py": '''\
            """Package built with PDM."""

            __version__ = "0.1.0"
            __all__ = ["install", "remove"]


            def install(package: str, version: str = "latest") -> bool:
                """
                Install a package.

                Parameters
                ----------
                package
                    Package name.
                version
                    Version constraint.

                Returns
                -------
                bool
                    True if installed successfully.
                """
                return True


            def remove(package: str) -> bool:
                """
                Remove a package.

                Parameters
                ----------
                package
                    Package name to remove.

                Returns
                -------
                bool
                    True if removed successfully.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-pdm

            Tests PDM build backend recognition.
        """,
    },
    "expected": {
        "detected_name": "gdtest-pdm",
        "detected_module": "gdtest_pdm",
        "detected_parser": "numpy",
        "export_names": ["install", "remove"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
