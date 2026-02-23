"""
gdtest_parser_google — Tests parser: 'google' config.

Dimensions: K10
Focus: parser config option set to 'google' with Google-style docstrings.
"""

SPEC = {
    "name": "gdtest_parser_google",
    "description": "Tests parser: google config",
    "dimensions": ["K10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-parser-google",
            "version": "0.1.0",
            "description": "Test parser google config",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "google",
    },
    "files": {
        "gdtest_parser_google/__init__.py": '''\
            """Package testing parser google config."""

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect", "send", "receive", "status"]


            def connect(host: str, port: int = 8080) -> bool:
                """Connect to a remote host.

                Args:
                    host: The hostname or IP address to connect to.
                    port: The port number to use. Defaults to 8080.

                Returns:
                    True if the connection was successful, False otherwise.
                """
                return True


            def disconnect() -> None:
                """Disconnect from the remote host.

                Returns:
                    None.
                """
                pass


            def send(data: str) -> int:
                """Send data to the remote host.

                Args:
                    data: The string data to send.

                Returns:
                    The number of bytes sent.

                Raises:
                    ConnectionError: If the connection is not established.
                """
                return len(data)


            def receive(timeout: float = 5.0) -> str:
                """Receive data from the remote host.

                Args:
                    timeout: The maximum time to wait in seconds. Defaults to 5.0.

                Returns:
                    The received data as a string.
                """
                return ""


            def status() -> dict:
                """Get the current connection status.

                Returns:
                    A dictionary with connection status information.
                """
                return {}
        ''',
        "README.md": """\
            # gdtest-v2-parser-google

            Tests parser: google config.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-parser-google",
        "detected_module": "gdtest_parser_google",
        "detected_parser": "google",
        "export_names": ["connect", "disconnect", "receive", "send", "status"],
        "num_exports": 5,
    },
}
