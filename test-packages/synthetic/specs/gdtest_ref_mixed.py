"""
gdtest_ref_mixed — Mix of explicit reference sections and auto-discovered items.

Dimensions: P3
Focus: Reference config listing only some functions explicitly; others auto-discovered.
"""

SPEC = {
    "name": "gdtest_ref_mixed",
    "description": "Mix of explicit reference sections and auto-discovered items.",
    "dimensions": ["P3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-mixed",
            "version": "0.1.0",
            "description": "Test mixed explicit and auto-discovered reference.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": [
            {
                "title": "Primary API",
                "desc": "Main functions",
                "contents": [
                    {"name": "connect"},
                    {"name": "disconnect"},
                ],
            },
        ],
    },
    "files": {
        "gdtest_ref_mixed/__init__.py": '"""Test package for mixed reference config."""\n',
        "gdtest_ref_mixed/core.py": '''
            """Core networking functions."""


            def connect(host: str, port: int = 8080) -> dict:
                """Connect to a remote host.

                Parameters
                ----------
                host : str
                    The hostname or IP address to connect to.
                port : int, optional
                    The port number, by default 8080.

                Returns
                -------
                dict
                    A dictionary with connection details.

                Examples
                --------
                >>> connect("localhost")
                {'host': 'localhost', 'port': 8080, 'status': 'connected'}
                """
                return {"host": host, "port": port, "status": "connected"}


            def disconnect(connection: dict) -> bool:
                """Disconnect from a remote host.

                Parameters
                ----------
                connection : dict
                    The connection dictionary to disconnect.

                Returns
                -------
                bool
                    True if disconnected successfully.

                Examples
                --------
                >>> disconnect({"host": "localhost", "status": "connected"})
                True
                """
                return True


            def ping(host: str) -> float:
                """Ping a remote host and return the latency.

                Parameters
                ----------
                host : str
                    The hostname or IP address to ping.

                Returns
                -------
                float
                    The latency in milliseconds.

                Examples
                --------
                >>> ping("localhost")
                0.1
                """
                return 0.1


            def trace(host: str) -> list:
                """Trace the route to a remote host.

                Parameters
                ----------
                host : str
                    The hostname or IP address to trace to.

                Returns
                -------
                list
                    A list of hops along the route.

                Examples
                --------
                >>> trace("localhost")
                ['127.0.0.1']
                """
                return ["127.0.0.1"]
        ''',
        "README.md": (
            "# gdtest-v2-ref-mixed\n\nTest mixed explicit and auto-discovered reference.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-mixed",
        "detected_module": "gdtest_ref_mixed",
        "detected_parser": "numpy",
        "export_names": ["connect", "disconnect", "ping", "trace"],
        "num_exports": 4,
    },
}
