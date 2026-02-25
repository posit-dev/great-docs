"""
gdtest_config_combo_e — Config combo: source.branch + source.path + parser sphinx + changelog.

Dimensions: K2, K3, K11, K21
Focus: source link overrides with sphinx docstring parsing and changelog config.
"""

SPEC = {
    "name": "gdtest_config_combo_e",
    "description": (
        "Config combo: source.branch=develop, source.path=lib, parser=sphinx, "
        "changelog config. Tests source link customization with Sphinx parsing."
    ),
    "dimensions": ["K2", "K3", "K11", "K21"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-combo-e",
            "version": "0.1.0",
            "description": "Test package for config combo E.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "sphinx",
        "source": {
            "branch": "develop",
            "path": "lib",
        },
        "changelog": "CHANGELOG.md",
    },
    "files": {
        "gdtest_config_combo_e/__init__.py": '''\
            """Config combo E — source.branch, source.path, parser=sphinx, changelog."""

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect", "send", "receive"]


            def connect(host: str, port: int = 8080) -> bool:
                """
                Connect to a remote host.

                :param host: The hostname or IP address.
                :type host: str
                :param port: The port number (default 8080).
                :type port: int
                :returns: True if connected successfully.
                :rtype: bool
                """
                return True


            def disconnect() -> None:
                """
                Disconnect from the remote host.

                :returns: None
                """
                pass


            def send(data: bytes) -> int:
                """
                Send data to the remote host.

                :param data: The bytes to send.
                :type data: bytes
                :returns: Number of bytes sent.
                :rtype: int
                """
                return len(data)


            def receive(max_bytes: int = 1024) -> bytes:
                """
                Receive data from the remote host.

                :param max_bytes: Maximum bytes to receive.
                :type max_bytes: int
                :returns: The received bytes.
                :rtype: bytes
                """
                return b""
        ''',
        "CHANGELOG.md": """\
            # Changelog

            ## [0.1.0] - 2026-01-15

            ### Added
            - Initial release.
            - Connection management functions.
        """,
        "README.md": """\
            # Config Combo E

            Tests source.branch=develop, source.path=lib, parser=sphinx, and changelog.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-combo-e",
        "detected_module": "gdtest_config_combo_e",
        "detected_parser": "sphinx",
        "export_names": ["connect", "disconnect", "receive", "send"],
        "num_exports": 4,
    },
}
