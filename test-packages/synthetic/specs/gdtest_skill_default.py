"""
gdtest_skill_default — Tests default auto-generated skill.md.

Dimensions: S1
Focus: Skill.md auto-generation from package metadata. No skill config,
       no curated skill directory. Tests that skill.md, skills.qmd, and
       .well-known are created automatically with correct content.
"""

SPEC = {
    "name": "gdtest_skill_default",
    "description": "Tests default auto-generated skill.md (no config, no curated skill)",
    "dimensions": ["S1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-default",
            "version": "0.1.0",
            "description": "A package that tests default skill.md auto-generation",
            "license": "MIT",
            "requires-python": ">=3.10",
            "urls": {
                "Repository": "https://github.com/test-org/gdtest-skill-default",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_skill_default/__init__.py": '''\
            """A test package for default skill generation."""

            __version__ = "0.1.0"
            __all__ = ["transform", "validate", "Config"]


            class Config:
                """
                Configuration container.

                Parameters
                ----------
                debug
                    Enable debug mode.
                verbose
                    Enable verbose output.
                """

                def __init__(self, debug: bool = False, verbose: bool = False):
                    self.debug = debug
                    self.verbose = verbose


            def transform(data: list, scale: float = 1.0) -> list:
                """
                Transform a list of values by a scale factor.

                Parameters
                ----------
                data
                    Input values.
                scale
                    Multiplier to apply.

                Returns
                -------
                list
                    Scaled values.
                """
                return [x * scale for x in data]


            def validate(value: str) -> bool:
                """
                Check whether a value is non-empty and valid.

                Parameters
                ----------
                value
                    The string to validate.

                Returns
                -------
                bool
                    True if the value is valid.
                """
                return bool(value and value.strip())
        ''',
        "README.md": """\
            # gdtest-skill-default

            A package that tests default skill.md auto-generation.

            ## Installation

            ```bash
            pip install gdtest-skill-default
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-default",
        "detected_module": "gdtest_skill_default",
        "detected_parser": "numpy",
        "export_names": ["transform", "validate", "Config"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_auto_generated": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
