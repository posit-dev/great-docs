"""
gdtest_monorepo — Package in a packages/ subdirectory.

Dimensions: A13, B1, C1, D1, E6, F6, G1, H7
Focus: Monorepo pattern where the package pyproject.toml is at
       the project root but the actual module is in the standard flat layout.
       Tests standard discovery still works.
"""

SPEC = {
    "name": "gdtest_monorepo",
    "description": "Monorepo-style package location",
    "dimensions": ["A13", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-monorepo",
            "version": "0.1.0",
            "description": "Test monorepo package layout",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_monorepo/__init__.py": '''\
            """Package in monorepo layout."""

            __version__ = "0.1.0"
            __all__ = ["build", "deploy"]


            def build(target: str = "production") -> dict:
                """
                Build the project.

                Parameters
                ----------
                target
                    Build target environment.

                Returns
                -------
                dict
                    Build results.
                """
                return {"target": target, "status": "built"}


            def deploy(artifact: str, environment: str = "staging") -> bool:
                """
                Deploy a build artifact.

                Parameters
                ----------
                artifact
                    Path to the build artifact.
                environment
                    Target environment.

                Returns
                -------
                bool
                    True if deployed successfully.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-monorepo

            Tests monorepo-style package discovery.
        """,
    },
    "expected": {
        "detected_name": "gdtest-monorepo",
        "detected_module": "gdtest_monorepo",
        "detected_parser": "numpy",
        "export_names": ["build", "deploy"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
