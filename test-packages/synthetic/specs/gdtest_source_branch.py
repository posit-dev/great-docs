"""
gdtest_source_branch — Tests source.branch: 'develop' config.

Dimensions: K2
Focus: source.branch config option set to 'develop' instead of default.
"""

SPEC = {
    "name": "gdtest_source_branch",
    "description": "Tests source.branch: develop config",
    "dimensions": ["K2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-source-branch",
            "version": "0.1.0",
            "description": "Test source.branch develop config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "source": {
            "branch": "develop",
        },
    },
    "files": {
        "gdtest_source_branch/__init__.py": '''\
            """Package testing source.branch develop config."""

            __version__ = "0.1.0"
            __all__ = ["read_data", "write_data"]


            def read_data(path: str) -> str:
                """
                Read data from a file path.

                Parameters
                ----------
                path
                    The file path to read from.

                Returns
                -------
                str
                    The file contents.
                """
                return ""


            def write_data(path: str, data: str) -> None:
                """
                Write data to a file path.

                Parameters
                ----------
                path
                    The file path to write to.
                data
                    The data to write.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-v2-source-branch

            Tests source.branch: develop config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-source-branch",
        "detected_module": "gdtest_source_branch",
        "detected_parser": "numpy",
        "export_names": ["read_data", "write_data"],
        "num_exports": 2,
    },
}
