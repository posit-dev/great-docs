"""
Automatic member placement with a limit of ten

Keep CompactClient's eight methods together and give FullClient's twelve methods separate pages.
"""

SPEC = {
    "name": "gdtest_inline_threshold",
    "description": "Places class members automatically with max_members_on_same_page: 10",
    "dimensions": ["K54"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-threshold",
            "version": "0.1.0",
            "description": "Automatic member placement with a limit of ten",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "max_members_on_same_page": 10,
    },
    "files": {
        "gdtest_inline_threshold/__init__.py": '''\
            """Automatic member placement with a limit of ten"""

            __version__ = "0.1.0"
            __all__ = ["CompactClient", "FullClient", "connect"]


            class CompactClient:
                """
                A client with 8 methods (stays inline since 8 <= 10).

                Parameters
                ----------
                host
                    The server hostname.
                """

                def __init__(self, host: str):
                    self.host = host

                def get(self, path: str) -> dict:
                    """
                    Send a GET request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def post(self, path: str, body: dict) -> dict:
                    """
                    Send a POST request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Request body.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def put(self, path: str, body: dict) -> dict:
                    """
                    Send a PUT request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Request body.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def delete(self, path: str) -> bool:
                    """
                    Send a DELETE request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    bool
                        True if successful.
                    """
                    return True

                def patch(self, path: str, body: dict) -> dict:
                    """
                    Send a PATCH request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Partial update payload.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def head(self, path: str) -> dict:
                    """
                    Send a HEAD request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    dict
                        Response headers.
                    """
                    return {}

                def options(self, path: str) -> list:
                    """
                    Send an OPTIONS request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    list
                        Allowed methods.
                    """
                    return []

                def close(self) -> None:
                    """Close the client connection."""
                    pass


            class FullClient:
                """
                A client with 12 methods (gets split since 12 > 10).

                Parameters
                ----------
                host
                    The server hostname.
                port
                    The server port.
                """

                def __init__(self, host: str, port: int = 443):
                    self.host = host
                    self.port = port

                def get(self, path: str) -> dict:
                    """
                    Send a GET request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def post(self, path: str, body: dict) -> dict:
                    """
                    Send a POST request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Request body.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def put(self, path: str, body: dict) -> dict:
                    """
                    Send a PUT request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Request body.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def delete(self, path: str) -> bool:
                    """
                    Send a DELETE request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    bool
                        True if successful.
                    """
                    return True

                def patch(self, path: str, body: dict) -> dict:
                    """
                    Send a PATCH request.

                    Parameters
                    ----------
                    path
                        Request path.
                    body
                        Partial update payload.

                    Returns
                    -------
                    dict
                        Response payload.
                    """
                    return {}

                def head(self, path: str) -> dict:
                    """
                    Send a HEAD request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    dict
                        Response headers.
                    """
                    return {}

                def options(self, path: str) -> list:
                    """
                    Send an OPTIONS request.

                    Parameters
                    ----------
                    path
                        Request path.

                    Returns
                    -------
                    list
                        Allowed methods.
                    """
                    return []

                def connect(self) -> None:
                    """Establish the connection."""
                    pass

                def disconnect(self) -> None:
                    """Terminate the connection."""
                    pass

                def ping(self) -> float:
                    """
                    Measure round-trip latency.

                    Returns
                    -------
                    float
                        Latency in milliseconds.
                    """
                    return 0.0

                def authenticate(self, token: str) -> bool:
                    """
                    Authenticate with the server.

                    Parameters
                    ----------
                    token
                        Bearer token.

                    Returns
                    -------
                    bool
                        True if authenticated.
                    """
                    return True

                def refresh_token(self) -> str:
                    """
                    Refresh the authentication token.

                    Returns
                    -------
                    str
                        New token value.
                    """
                    return "new-token"


            def connect(host: str, port: int = 443) -> FullClient:
                """
                Create and connect a client.

                Parameters
                ----------
                host
                    Server hostname.
                port
                    Server port.

                Returns
                -------
                FullClient
                    Connected client instance.
                """
                client = FullClient(host, port)
                client.connect()
                return client
        ''',
        "README.md": """\
            # gdtest-inline-threshold

            Set `max_members_on_same_page: 10` to keep `CompactClient`'s 8 methods
            on its class page. Each of `FullClient`'s 12 methods gets a separate page.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-threshold",
        "detected_module": "gdtest_inline_threshold",
        "detected_parser": "numpy",
        "export_names": ["CompactClient", "FullClient", "connect"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "big_class_name": "FullClient",
        "big_class_member_count": 12,
        "inline_class_name": "CompactClient",
        "same_page_member_count": 8,
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "ug", "supp", "hdg"],
    },
}
