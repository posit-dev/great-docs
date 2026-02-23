"""Tests changelog configuration."""

SPEC = {
    "name": "gdtest_config_changelog",
    "description": "Tests changelog config with enabled=True and max_releases=5. No actual GitHub repo.",
    "dimensions": ["K21"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-changelog",
            "version": "0.1.0",
            "description": "Test package for changelog config.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "changelog": {
            "enabled": True,
            "max_releases": 5,
        },
    },
    "files": {
        "gdtest_config_changelog/__init__.py": '"""Test package for changelog config."""\n',
        "gdtest_config_changelog/core.py": '''
            """Change logging functions."""


            def log_change(msg: str) -> None:
                """Log a change message.

                Parameters
                ----------
                msg : str
                    The change message to log.

                Examples
                --------
                >>> log_change("Added new feature")
                """
                pass


            def get_history() -> list:
                """Get the full change history.

                Returns
                -------
                list
                    A list of change log entries, newest first.

                Examples
                --------
                >>> get_history()
                []
                """
                return []
        ''',
    },
    "expected": {
        "build_succeeds": True,
        "files_exist": [
            "great-docs/reference/index.html",
        ],
    },
}
