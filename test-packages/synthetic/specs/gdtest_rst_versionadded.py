"""
gdtest_rst_versionadded — Tests .. versionadded:: directives in docstrings.

Dimensions: L1
Focus: RST versionadded directives rendered as styled callout divs by post-render.
"""

SPEC = {
    "name": "gdtest_rst_versionadded",
    "description": "Tests versionadded RST directives in docstrings",
    "dimensions": ["L1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-rst-versionadded",
            "version": "0.1.0",
            "description": "Test versionadded RST directives",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_rst_versionadded/__init__.py": '''\
            """Package testing versionadded RST directives."""

            __version__ = "0.1.0"
            __all__ = ["create_session", "close_session"]


            def create_session(name: str) -> str:
                """
                Create a new session with the given name.

                Parameters
                ----------
                name
                    The name for the new session.

                Returns
                -------
                str
                    The session identifier.

                .. versionadded:: 2.0
                """
                return f"session-{name}"


            def close_session(session_id: str) -> None:
                """
                Close an existing session.

                Parameters
                ----------
                session_id
                    The identifier of the session to close.

                Returns
                -------
                None

                .. versionadded:: 2.1
                    Session cleanup was added.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-rst-versionadded

            Tests versionadded RST directives in docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-rst-versionadded",
        "detected_module": "gdtest_rst_versionadded",
        "detected_parser": "numpy",
        "export_names": ["close_session", "create_session"],
        "num_exports": 2,
    },
}
