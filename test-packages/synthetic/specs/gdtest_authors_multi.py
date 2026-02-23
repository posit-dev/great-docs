"""
gdtest_authors_multi — Tests multiple authors config.

Dimensions: K14
Focus: authors config option with three author entries including name, email, role, and github.
"""

SPEC = {
    "name": "gdtest_authors_multi",
    "description": "Tests multiple authors config",
    "dimensions": ["K14"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-authors-multi",
            "version": "0.1.0",
            "description": "Test multiple authors config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "authors": [
            {
                "name": "Alice Smith",
                "email": "alice@example.com",
                "role": "Lead",
                "github": "alicesmith",
            },
            {
                "name": "Bob Jones",
                "email": "bob@example.com",
                "role": "Contributor",
                "github": "bobjones",
            },
            {
                "name": "Carol Lee",
                "email": "carol@example.com",
                "role": "Reviewer",
                "github": "carollee",
            },
        ],
    },
    "files": {
        "gdtest_authors_multi/__init__.py": '''\
            """Package testing multiple authors config."""

            __version__ = "0.1.0"
            __all__ = ["collaborate", "review"]


            def collaborate(team: list) -> str:
                """
                Collaborate with a team of contributors.

                Parameters
                ----------
                team
                    A list of team member names.

                Returns
                -------
                str
                    A summary of the collaboration.
                """
                return ", ".join(team)


            def review(code: str) -> bool:
                """
                Review a piece of code.

                Parameters
                ----------
                code
                    The code string to review.

                Returns
                -------
                bool
                    True if the code passes review.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-v2-authors-multi

            Tests multiple authors config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-authors-multi",
        "detected_module": "gdtest_authors_multi",
        "detected_parser": "numpy",
        "export_names": ["collaborate", "review"],
        "num_exports": 2,
    },
}
