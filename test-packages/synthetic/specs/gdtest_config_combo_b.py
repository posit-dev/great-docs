"""Tests config combo: parser=google, dynamic=false, sidebar_filter off, dark_mode_toggle off, source off."""

SPEC = {
    "name": "gdtest_config_combo_b",
    "description": (
        "Config combo: parser=google, dynamic=false, sidebar_filter.enabled=false, "
        "dark_mode_toggle=false, source.enabled=false. All opt-out flags."
    ),
    "dimensions": ["K5", "K6", "K9", "K10", "K15"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-config-combo-b",
            "version": "0.1.0",
            "description": "Test package for config combo B (all opt-out).",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "google",
        "dynamic": False,
        "sidebar_filter": {
            "enabled": False,
        },
        "dark_mode_toggle": False,
        "source": {
            "enabled": False,
        },
    },
    "files": {
        "gdtest_config_combo_b/__init__.py": '"""Test package for config combo B."""\n',
        "gdtest_config_combo_b/core.py": '''
            """Search and ranking functions using Google-style docstrings."""


            def search(query: str) -> list:
                """Search for items matching a query string.

                Args:
                    query: The search query string.

                Returns:
                    A list of matching results as dictionaries.

                Examples:
                    >>> search("widgets")
                    [{'name': 'widget_a', 'score': 0.9}]
                """
                return [{"name": "widget_a", "score": 0.9}]


            def filter_results(results: list, criteria: str) -> list:
                """Filter a list of results by the given criteria.

                Args:
                    results: The list of result dictionaries to filter.
                    criteria: A string describing the filter criteria.

                Returns:
                    A filtered list of result dictionaries.

                Examples:
                    >>> filter_results([{"name": "a", "score": 0.9}], "score>0.5")
                    [{'name': 'a', 'score': 0.9}]
                """
                return results


            def rank(results: list) -> list:
                """Rank a list of results by score in descending order.

                Args:
                    results: The list of result dictionaries to rank. Each dict
                        should have a 'score' key.

                Returns:
                    The sorted list of result dictionaries, highest score first.

                Examples:
                    >>> rank([{"score": 0.5}, {"score": 0.9}])
                    [{'score': 0.9}, {'score': 0.5}]
                """
                return sorted(results, key=lambda r: r.get("score", 0), reverse=True)
        ''',
    },
    "expected": {
        "build_succeeds": True,
        "files_exist": [
            "great-docs/reference/index.html",
            "great-docs/reference/search.html",
            "great-docs/reference/filter_results.html",
            "great-docs/reference/rank.html",
        ],
        "files_not_contain": {
            "great-docs/reference/search.html": ["sidebar-filter.js", "dark-mode-toggle.js"],
        },
    },
}
