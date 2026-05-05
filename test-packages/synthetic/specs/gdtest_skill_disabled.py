"""
gdtest_skill_disabled — Tests that skill generation is disabled.

Dimensions: S4
Focus: When ``skill.enabled`` is False, no skill.md, skills.qmd, or
       .well-known directory should be created.
"""

SPEC = {
    "name": "gdtest_skill_disabled",
    "description": "Tests that skill generation is disabled via config",
    "dimensions": ["S4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-disabled",
            "version": "0.1.0",
            "description": "A package with skill generation disabled",
            "license": "MIT",
            "requires-python": ">=3.10",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "skill": {
            "enabled": False,
        },
    },
    "files": {
        "gdtest_skill_disabled/__init__.py": '''\
            """A package with skill generation disabled."""

            __version__ = "0.1.0"
            __all__ = ["greet", "farewell"]


            def greet(name: str) -> str:
                """
                Return a greeting.

                Parameters
                ----------
                name
                    The name to greet.

                Returns
                -------
                str
                    A greeting string.
                """
                return f"Hello, {name}!"


            def farewell(name: str) -> str:
                """
                Return a farewell.

                Parameters
                ----------
                name
                    The name to bid farewell.

                Returns
                -------
                str
                    A farewell string.
                """
                return f"Goodbye, {name}!"
        ''',
        "README.md": """\
            # gdtest-skill-disabled

            A package with skill generation disabled in great-docs.yml.
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-disabled",
        "detected_module": "gdtest_skill_disabled",
        "detected_parser": "numpy",
        "export_names": ["greet", "farewell"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "has_skill_md": False,
        "has_skills_page": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
