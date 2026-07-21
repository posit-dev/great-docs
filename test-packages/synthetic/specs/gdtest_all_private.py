"""
gdtest_all_private — Module with mostly private names.

Dimensions: A1, B1, C1, D1, E6, F6, G1, H7
Focus: Module with many _private names plus one public function.
       Tests that private names are filtered even when they dominate.
"""

SPEC = {
    "name": "gdtest_all_private",
    "description": "Mostly private names with one public export",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-all-private",
            "version": "0.1.0",
            "description": "Test mostly-private module",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_all_private/__init__.py": '''\
            """Module with mostly private names."""

            __version__ = "0.1.0"
            __all__ = ["public_api"]


            def _private_helper_a():
                """Private helper A."""
                pass


            def _private_helper_b():
                """Private helper B."""
                pass


            def _private_helper_c():
                """Private helper C."""
                pass


            def _private_helper_d():
                """Private helper D."""
                pass


            def _private_helper_e():
                """Private helper E."""
                pass


            def public_api(data: str) -> str:
                """
                The only public function in this module.

                Parameters
                ----------
                data
                    Input data.

                Returns
                -------
                str
                    Processed data.
                """
                return data
        ''',
        "README.md": """\
            # gdtest-all-private

            Tests that private names are filtered when they dominate the module.
        """,
    },
    "expected": {
        "detected_name": "gdtest-all-private",
        "detected_module": "gdtest_all_private",
        "detected_parser": "numpy",
        "export_names": ["public_api"],
        "num_exports": 1,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
