"""
Global same-page placement for class members

Keep all eight documented methods on the class page.
"""

SPEC = {
    "name": "gdtest_inline_always",
    "description": "Keeps class members together with members_on_same_page: true",
    "dimensions": ["K55"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-always",
            "version": "0.1.0",
            "description": "Class members kept together by a global override",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "members_on_same_page": True,
    },
    "files": {
        "gdtest_inline_always/__init__.py": '''\
            """Class members kept together by a global override"""

            __version__ = "0.1.0"
            __all__ = ["LargeAPI", "create_api"]


            class LargeAPI:
                """
                A class with many methods that would normally be split.

                With `members_on_same_page: true`, all methods stay on the class page
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

            Set `members_on_same_page: true` to keep all 8 of `LargeAPI`'s methods
            on its class page.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-always",
        "detected_module": "gdtest_inline_always",
        "detected_parser": "numpy",
        "export_names": ["LargeAPI", "create_api"],
        "num_exports": 2,
        # With members_on_same_page: true, members stay on their parent page
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "methods_never_split": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
