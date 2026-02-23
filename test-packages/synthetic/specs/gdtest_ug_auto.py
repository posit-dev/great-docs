"""
gdtest_ug_auto — Auto-discovered user guide with unnumbered .qmd files.

Dimensions: M1
Focus: User guide auto-discovery from user_guide/ directory with unnumbered files.
"""

SPEC = {
    "name": "gdtest_ug_auto",
    "description": "Auto-discovered user guide with 3 unnumbered .qmd files in user_guide/.",
    "dimensions": ["M1"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ug-auto",
            "version": "0.1.0",
            "description": "Test auto-discovered user guide.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_ug_auto/__init__.py": '"""Test package for auto-discovered user guide."""\n',
        "gdtest_ug_auto/core.py": '''
            """Core start/stop functions."""


            def start(name: str) -> None:
                """Start a named service.

                Parameters
                ----------
                name : str
                    The name of the service to start.

                Examples
                --------
                >>> start("worker")
                """
                pass


            def stop() -> None:
                """Stop all running services.

                Returns
                -------
                None

                Examples
                --------
                >>> stop()
                """
                pass
        ''',
        "user_guide/basics.qmd": (
            "---\ntitle: Basics\n---\n\n# Basics\n\nLearn the basic concepts of the library.\n"
        ),
        "user_guide/configuration.qmd": (
            "---\n"
            "title: Configuration\n"
            "---\n"
            "\n"
            "# Configuration\n"
            "\n"
            "How to configure the library for your needs.\n"
        ),
        "user_guide/deployment.qmd": (
            "---\ntitle: Deployment\n---\n\n# Deployment\n\nSteps to deploy your application.\n"
        ),
    },
    "expected": {
        "files_exist": [
            "great-docs/user-guide/basics.html",
            "great-docs/user-guide/configuration.html",
            "great-docs/user-guide/deployment.html",
        ],
        "files_contain": {
            "great-docs/user-guide/basics.html": ["Basics", "basic concepts"],
            "great-docs/user-guide/configuration.html": ["Configuration", "configure the library"],
            "great-docs/user-guide/deployment.html": ["Deployment", "deploy your application"],
        },
    },
}
