"""
gdtest_flit — Flit build backend.

Dimensions: A10, B1, C1, D1, E6, F6, G1, H7
Focus: Package using flit_core.buildapi as build backend. Tests
       that Flit-style pyproject.toml is recognized for module discovery.
"""

SPEC = {
    "name": "gdtest_flit",
    "description": "Flit build backend",
    "dimensions": ["A10", "B1", "C1", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-flit",
            "version": "0.1.0",
            "description": "Test Flit build system",
        },
        "build-system": {
            "requires": ["flit_core>=3.2"],
            "build-backend": "flit_core.buildapi",
        },
    },
    "files": {
        "gdtest_flit/__init__.py": '''\
            """Package built with Flit."""

            __version__ = "0.1.0"
            __all__ = ["compose", "publish"]


            def compose(parts: list) -> str:
                """
                Compose parts into a document.

                Parameters
                ----------
                parts
                    List of document parts.

                Returns
                -------
                str
                    Composed document.
                """
                return "\\n".join(str(p) for p in parts)


            def publish(document: str, target: str = "web") -> bool:
                """
                Publish a document to a target.

                Parameters
                ----------
                document
                    Document content.
                target
                    Publication target (web, pdf, epub).

                Returns
                -------
                bool
                    True if published successfully.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-flit

            Tests Flit build backend recognition.
        """,
    },
    "expected": {
        "detected_name": "gdtest-flit",
        "detected_module": "gdtest_flit",
        "detected_parser": "numpy",
        "export_names": ["compose", "publish"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
