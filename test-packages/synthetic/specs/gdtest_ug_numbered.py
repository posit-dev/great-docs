"""
gdtest_ug_numbered — Numbered user guide pages.

Dimensions: M2
Focus: User guide with numbered filenames for explicit ordering.
"""

SPEC = {
    "name": "gdtest_ug_numbered",
    "description": "Numbered user guide with 4 sequentially named .qmd files.",
    "dimensions": ["M2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-numbered",
            "version": "0.1.0",
            "description": "Test numbered user guide ordering.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_numbered/__init__.py": '"""Test package for numbered user guide."""\n',
        "gdtest_ug_numbered/core.py": '''
            """Core run/status functions."""


            def run(task: str) -> str:
                """Run a named task.

                Parameters
                ----------
                task : str
                    The name of the task to execute.

                Returns
                -------
                str
                    A message indicating task completion.

                Examples
                --------
                >>> run("build")
                'build complete'
                """
                return f"{task} complete"


            def status() -> dict:
                """Return the current status of all tasks.

                Returns
                -------
                dict
                    A dictionary mapping task names to their status.

                Examples
                --------
                >>> status()
                {'build': 'idle'}
                """
                return {"build": "idle"}
        ''',
        "user_guide/01-intro.qmd": (
            "---\n"
            "title: Introduction\n"
            "---\n"
            "\n"
            "# Introduction\n"
            "\n"
            "Welcome to the introduction guide.\n"
        ),
        "user_guide/02-install.qmd": (
            "---\ntitle: Installation\n---\n\n# Installation\n\nHow to install the package.\n"
        ),
        "user_guide/03-usage.qmd": (
            "---\ntitle: Usage\n---\n\n# Usage\n\nHow to use the package effectively.\n"
        ),
        "user_guide/04-advanced.qmd": (
            "---\ntitle: Advanced\n---\n\n# Advanced\n\nAdvanced usage patterns and techniques.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/01-intro.html",
            "great-docs/user-guide/02-install.html",
            "great-docs/user-guide/03-usage.html",
            "great-docs/user-guide/04-advanced.html",
        ],
        "files_contain": {
            "great-docs/user-guide/01-intro.html": ["Introduction"],
            "great-docs/user-guide/02-install.html": ["Installation"],
            "great-docs/user-guide/03-usage.html": ["Usage"],
            "great-docs/user-guide/04-advanced.html": ["Advanced"],
        },
    },
}
