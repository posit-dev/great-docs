"""Tests user_guide as an explicit list of section dicts."""

SPEC = {
    "name": "gdtest_config_ug_list",
    "description": "Tests user_guide config as an explicit list of section dicts with titles and contents.",
    "dimensions": ["K20"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-ug-list",
            "version": "0.1.0",
            "description": "Test package for user_guide list config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": [
            {"title": "Getting Started", "contents": ["install.qmd", "quickstart.qmd"]},
            {"title": "Advanced", "contents": ["customization.qmd"]},
        ],
    },
    "files": {
        "gdtest_config_ug_list/__init__.py": '"""Test package for user_guide list config."""\n',
        "gdtest_config_ug_list/core.py": '''
            """Core setup and run functions."""


            def setup(config: dict) -> None:
                """Set up the application with the given configuration.

                Parameters
                ----------
                config : dict
                    A dictionary containing configuration options.

                Examples
                --------
                >>> setup({"debug": True})
                """
                pass


            def run(task: str) -> str:
                """Run a named task and return the result.

                Parameters
                ----------
                task : str
                    The name of the task to execute.

                Returns
                -------
                str
                    The result of executing the task.

                Examples
                --------
                >>> run("build")
                'build complete'
                """
                return f"{task} complete"
        ''',
        "user_guide/install.qmd": (
            "---\ntitle: Installation\n---\n\n# Installation\n\nHow to install the package.\n"
        ),
        "user_guide/quickstart.qmd": (
            "---\ntitle: Quickstart\n---\n\n# Quickstart\n\nGet started quickly with this guide.\n"
        ),
        "user_guide/customization.qmd": (
            "---\ntitle: Customization\n---\n\n# Customization\n\nAdvanced customization options.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/install.html",
            "great-docs/user-guide/quickstart.html",
            "great-docs/user-guide/customization.html",
        ],
        "files_contain": {
            "great-docs/user-guide/install.html": ["Installation"],
            "great-docs/user-guide/quickstart.html": ["Quickstart"],
            "great-docs/user-guide/customization.html": ["Customization"],
        },
    },
}
