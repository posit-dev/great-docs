"""
gdtest_numpy_seealso_desc — NumPy-style See Also sections with descriptions.

Dimensions: A1, D1, L22
Focus: Tests that NumPy-style ``See Also`` sections preserve descriptions
       through the post-render merge step.  Each function uses the standard
       ``name : description`` format inside a ``See Also`` docstring section.
"""

SPEC = {
    "name": "gdtest_numpy_seealso_desc",
    "description": (
        "NumPy-style See Also sections with descriptions. "
        "Tests that 'name : description' entries survive the post-render merge."
    ),
    "dimensions": ["A1", "D1", "L22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-numpy-seealso-desc",
            "version": "0.1.0",
            "description": "Test NumPy See Also description preservation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "numpy",
    },
    "files": {
        "gdtest_numpy_seealso_desc/__init__.py": '''\
            """Package with NumPy-style See Also sections including descriptions."""

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect", "send", "receive"]


            def connect(host: str, port: int = 8080) -> object:
                """
                Open a connection to a remote host.

                Parameters
                ----------
                host
                    The hostname or IP address.
                port
                    The port number.

                Returns
                -------
                object
                    A connection handle.

                See Also
                --------
                disconnect : Close an open connection.
                send : Transmit data over a connection.
                """
                return object()


            def disconnect(conn: object) -> None:
                """
                Close an open connection.

                Parameters
                ----------
                conn
                    The connection handle to close.

                See Also
                --------
                connect : Open a new connection.
                """
                pass


            def send(conn: object, data: bytes) -> int:
                """
                Send data over a connection.

                Parameters
                ----------
                conn
                    An open connection handle.
                data
                    The data to transmit.

                Returns
                -------
                int
                    Number of bytes sent.

                See Also
                --------
                receive : Read data from a connection.
                connect : Open a new connection first.
                """
                return len(data)


            def receive(conn: object, size: int = 1024) -> bytes:
                """
                Receive data from a connection.

                Parameters
                ----------
                conn
                    An open connection handle.
                size
                    Maximum number of bytes to read.

                Returns
                -------
                bytes
                    The received data.

                See Also
                --------
                send : Transmit data over a connection.
                disconnect : Close the connection when done.
                """
                return b""
        ''',
        "README.md": """\
            # gdtest-numpy-seealso-desc

            A synthetic test package testing NumPy See Also description preservation.
        """,
    },
    "expected": {
        "detected_name": "gdtest-numpy-seealso-desc",
        "detected_module": "gdtest_numpy_seealso_desc",
        "detected_parser": "numpy",
        "export_names": ["connect", "disconnect", "receive", "send"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "seealso": {
            "connect": ["disconnect", "send"],
            "disconnect": ["connect"],
            "send": ["receive", "connect"],
            "receive": ["send", "disconnect"],
        },
        "seealso_descriptions": {
            "connect": {
                "disconnect": "Close an open connection.",
                "send": "Transmit data over a connection.",
            },
            "disconnect": {
                "connect": "Open a new connection.",
            },
            "send": {
                "receive": "Read data from a connection.",
                "connect": "Open a new connection first.",
            },
            "receive": {
                "send": "Transmit data over a connection.",
                "disconnect": "Close the connection when done.",
            },
        },
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
