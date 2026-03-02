"""
gdtest_google — Google-style docstrings.

Dimensions: A1, B1, C1, D2, E6, F6, G1, H7
Focus: 3 functions with Google-format docstrings (Args:, Returns:).
       Tests docstring style auto-detection and Google parser.
"""

SPEC = {
    "name": "gdtest_google",
    "description": "Google-style docstrings; disconnect is %nodoc and should not appear",
    "dimensions": ["A1", "B1", "C1", "D2", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-google",
            "version": "0.1.0",
            "description": "A synthetic test package with Google-style docstrings",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_google/__init__.py": '''\
            """A test package using Google-style docstrings."""

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect", "send_message"]


            def connect(host: str, port: int = 8080) -> bool:
                """Connect to a remote server.

                Args:
                    host: The hostname or IP address to connect to.
                    port: The port number. Defaults to 8080.

                Returns:
                    True if the connection was successful.

                Raises:
                    ConnectionError: If the server is unreachable.
                """
                return True


            def disconnect(force: bool = False) -> None:
                """Disconnect from the remote server.

                %nodoc

                Args:
                    force: If True, forcefully terminate the connection
                        without waiting for pending operations.
                """
                pass


            def send_message(msg: str, priority: int = 0) -> str:
                """Send a message to the connected server.

                Args:
                    msg: The message content to send.
                    priority: Message priority level (0=normal, 1=high).

                Returns:
                    A confirmation string with the message ID.

                Examples:
                    >>> send_message("hello")
                    'msg-001'
                """
                return "msg-001"
        ''',
        "README.md": """\
            # gdtest-google

            A synthetic test package with Google-style docstrings.
        """,
    },
    "expected": {
        "detected_name": "gdtest-google",
        "detected_module": "gdtest_google",
        "detected_parser": "google",
        "export_names": ["connect", "disconnect", "send_message"],
        "num_exports": 3,
        "nodoc_items": ["disconnect"],
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
