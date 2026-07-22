"""
gdtest_inline_always — Tests inline_methods: true (never split methods).

Dimensions: K55
Focus: When inline_methods is set to true, no class—regardless of method
count—gets split into separate method pages. All methods remain inline on
the class page.
"""

SPEC = {
    "name": "gdtest_inline_always",
    "description": "Tests inline_methods: true (always inline, never split)",
    "dimensions": ["K55"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-always",
            "version": "0.1.0",
            "description": "Test package for inline_methods: true",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "inline_methods": True,
    },
    "files": {
        "gdtest_inline_always/__init__.py": '''\
            """Package testing inline_methods: true (never split)."""

            __version__ = "0.1.0"
            __all__ = ["LargeAPI", "create_api"]


            class LargeAPI:
                """
                A class with many methods that would normally be split.

                With inline_methods: true, all methods stay on the class page
                regardless of count.

                Parameters
                ----------
                base_url
                    The API base URL.
                """

                def __init__(self, base_url: str):
                    self.base_url = base_url

                def get(self, endpoint: str) -> dict:
                    """
                    Perform a GET request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.

                    Returns
                    -------
                    dict
                        Response data.
                    """
                    return {}

                def post(self, endpoint: str, data: dict) -> dict:
                    """
                    Perform a POST request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.
                    data
                        Request body payload.

                    Returns
                    -------
                    dict
                        Response data.
                    """
                    return {}

                def put(self, endpoint: str, data: dict) -> dict:
                    """
                    Perform a PUT request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.
                    data
                        Request body payload.

                    Returns
                    -------
                    dict
                        Response data.
                    """
                    return {}

                def delete(self, endpoint: str) -> bool:
                    """
                    Perform a DELETE request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.

                    Returns
                    -------
                    bool
                        True if deletion was successful.
                    """
                    return True

                def patch(self, endpoint: str, data: dict) -> dict:
                    """
                    Perform a PATCH request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.
                    data
                        Partial update payload.

                    Returns
                    -------
                    dict
                        Response data.
                    """
                    return {}

                def head(self, endpoint: str) -> dict:
                    """
                    Perform a HEAD request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.

                    Returns
                    -------
                    dict
                        Response headers.
                    """
                    return {}

                def options(self, endpoint: str) -> list:
                    """
                    Perform an OPTIONS request.

                    Parameters
                    ----------
                    endpoint
                        The API endpoint path.

                    Returns
                    -------
                    list
                        Allowed methods.
                    """
                    return []

                def authenticate(self, token: str) -> None:
                    """
                    Set authentication token.

                    Parameters
                    ----------
                    token
                        Bearer token for authentication.
                    """
                    pass


            def create_api(url: str) -> LargeAPI:
                """
                Create a new API client.

                Parameters
                ----------
                url
                    Base URL for the API.

                Returns
                -------
                LargeAPI
                    Configured API client instance.
                """
                return LargeAPI(url)
        ''',
        "README.md": """\
            # gdtest-inline-always

            Package testing `inline_methods: true`. LargeAPI has 8 methods but
            they all stay inline on the class page (no separate method pages).
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-always",
        "detected_module": "gdtest_inline_always",
        "detected_parser": "numpy",
        "export_names": ["LargeAPI", "create_api"],
        "num_exports": 2,
        # With inline_methods: true, NO "Methods" companion section
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "methods_never_split": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
