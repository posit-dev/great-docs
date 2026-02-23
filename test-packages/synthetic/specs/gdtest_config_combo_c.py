"""Tests config combo: sections (examples + tutorials) + user_guide (list) + reference (sections)."""

SPEC = {
    "name": "gdtest_config_combo_c",
    "description": (
        "Config combo: sections with examples and tutorials, user_guide as explicit list, "
        "reference with explicit sections. Full navigation structure."
    ),
    "dimensions": ["K18", "K20", "K22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-combo-c",
            "version": "0.1.0",
            "description": "Test package for config combo C (full navigation).",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": {
            "examples": {
                "title": "Examples",
                "description": "Example use cases",
                "path": "examples",
            },
            "tutorials": {
                "title": "Tutorials",
                "description": "Step-by-step tutorials",
                "path": "tutorials",
            },
        },
        "user_guide": [
            {"title": "Basics", "contents": ["intro.qmd"]},
            {"title": "Advanced Topics", "contents": ["advanced.qmd"]},
        ],
        "reference": [
            {
                "title": "Build Pipeline",
                "desc": "Build and deployment functions",
                "contents": [
                    {"name": "build"},
                    {"name": "deploy"},
                ],
            },
            {
                "title": "Operations",
                "desc": "Testing and monitoring functions",
                "contents": [
                    {"name": "test"},
                    {"name": "monitor"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_config_combo_c/__init__.py": (
            '"""Test package for config combo C."""\n'
            "\n"
            "from gdtest_config_combo_c.pipeline import build, deploy\n"
            "from gdtest_config_combo_c.ops import test, monitor\n"
        ),
        "gdtest_config_combo_c/pipeline.py": '''
            """Build and deployment pipeline functions."""


            def build(target: str = "all") -> dict:
                """Build the project for the specified target.

                Parameters
                ----------
                target : str, optional
                    The build target, by default "all".

                Returns
                -------
                dict
                    A dictionary containing the build status and artifacts.

                Examples
                --------
                >>> build("docs")
                {'status': 'success', 'target': 'docs'}
                """
                return {"status": "success", "target": target}


            def deploy(environment: str, dry_run: bool = False) -> str:
                """Deploy the project to the specified environment.

                Parameters
                ----------
                environment : str
                    The target environment (e.g., "staging", "production").
                dry_run : bool, optional
                    If True, simulate the deployment without making changes,
                    by default False.

                Returns
                -------
                str
                    A message indicating the deployment result.

                Examples
                --------
                >>> deploy("staging", dry_run=True)
                'Dry run: would deploy to staging'
                """
                if dry_run:
                    return f"Dry run: would deploy to {environment}"
                return f"Deployed to {environment}"
        ''',
        "gdtest_config_combo_c/ops.py": '''
            """Testing and monitoring operations."""


            def test(suite: str = "unit") -> dict:
                """Run the specified test suite.

                Parameters
                ----------
                suite : str, optional
                    The name of the test suite to run, by default "unit".

                Returns
                -------
                dict
                    A dictionary containing test results with passed and
                    failed counts.

                Examples
                --------
                >>> test("integration")
                {'suite': 'integration', 'passed': 10, 'failed': 0}
                """
                return {"suite": suite, "passed": 10, "failed": 0}


            def monitor(service: str, interval: int = 60) -> dict:
                """Monitor a service at the given interval.

                Parameters
                ----------
                service : str
                    The name of the service to monitor.
                interval : int, optional
                    The monitoring interval in seconds, by default 60.

                Returns
                -------
                dict
                    A dictionary containing the service status and uptime.

                Examples
                --------
                >>> monitor("api", interval=30)
                {'service': 'api', 'status': 'healthy', 'interval': 30}
                """
                return {"service": service, "status": "healthy", "interval": interval}
        ''',
        "examples/demo.qmd": (
            "---\ntitle: Demo Example\n---\n\n# Demo\n\nA demonstration of the package in action.\n"
        ),
        "tutorials/step1.qmd": (
            "---\n"
            "title: Step 1 - Getting Started\n"
            "---\n"
            "\n"
            "# Step 1\n"
            "\n"
            "The first step in the tutorial.\n"
        ),
        "user_guide/intro.qmd": (
            "---\ntitle: Introduction\n---\n\n# Introduction\n\nWelcome to the user guide.\n"
        ),
        "user_guide/advanced.qmd": (
            "---\n"
            "title: Advanced Topics\n"
            "---\n"
            "\n"
            "# Advanced Topics\n"
            "\n"
            "In-depth coverage of advanced features.\n"
        ),
    },
    "expected": {
        "build_succeeds": True,
        "files_exist": [
            "great-docs/reference/index.html",
            "great-docs/reference/build.html",
            "great-docs/reference/deploy.html",
            "great-docs/reference/test.html",
            "great-docs/reference/monitor.html",
            "great-docs/user-guide/intro.html",
            "great-docs/user-guide/advanced.html",
            "great-docs/examples/demo.html",
            "great-docs/tutorials/step1.html",
        ],
        "files_contain": {
            "great-docs/reference/index.html": ["Build Pipeline", "Operations"],
        },
    },
}
