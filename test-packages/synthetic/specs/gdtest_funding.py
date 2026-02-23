"""
gdtest_funding — Tests funding config.

Dimensions: K13
Focus: funding config option with name, roles, homepage, and ror fields.
"""

SPEC = {
    "name": "gdtest_funding",
    "description": "Tests funding config",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-funding",
            "version": "0.1.0",
            "description": "Test funding config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "funding": {
            "name": "Science Foundation",
            "roles": ["Funder", "Sponsor"],
            "homepage": "https://example.org/grant",
            "ror": "https://ror.org/12345",
        },
    },
    "files": {
        "gdtest_funding/__init__.py": '''\
            """Package testing funding config."""

            __version__ = "0.1.0"
            __all__ = ["donate", "sponsor"]


            def donate(amount: float) -> str:
                """
                Record a donation of the given amount.

                Parameters
                ----------
                amount
                    The donation amount in dollars.

                Returns
                -------
                str
                    A confirmation message.
                """
                return f"Donated ${amount:.2f}"


            def sponsor(project: str) -> bool:
                """
                Sponsor a project by name.

                Parameters
                ----------
                project
                    The name of the project to sponsor.

                Returns
                -------
                bool
                    True if the sponsorship was successful.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-v2-funding

            Tests funding config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-funding",
        "detected_module": "gdtest_funding",
        "detected_parser": "numpy",
        "export_names": ["donate", "sponsor"],
        "num_exports": 2,
    },
}
