"""
gdtest_namespace_src — Namespace package with src/ layout.

Dimensions: A2, A12, B1, C4, D1, E6, F6, G1, H7
Focus: Namespace package using src/ layout — the importable module is
       dotted (e.g., ``nspkg.core``) and lives under ``src/nspkg/core/``.
       Tests the fix for namespace package discovery with ``module:`` config
       in great-docs.yml (GitHub issue: firebird-base src layout).
"""

SPEC = {
    "name": "gdtest_namespace_src",
    "description": "Namespace package with src/ layout and dotted module name",
    "dimensions": ["A2", "A12", "B1", "C4", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-namespace-src",
            "version": "0.1.0",
            "description": "Test namespace package in src/ layout",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
        "tool": {
            "setuptools": {
                "package-dir": {"": "src"},
            },
        },
    },
    # ── Great-docs config ────────────────────────────────────────────
    "config": {
        "module": "nspkg.core",
    },
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        # Namespace top level — implicit namespace (no __all__)
        "src/nspkg/__init__.py": '''\
            """Namespace top-level package."""
        ''',
        # The actual sub-package with the API
        "src/nspkg/core/__init__.py": '''\
            """Core sub-package of the nspkg namespace."""

            __version__ = "0.1.0"
            __all__ = ["Config", "connect", "disconnect"]


            class Config:
                """
                Configuration holder for connections.

                Parameters
                ----------
                host
                    Server hostname.
                port
                    Port number.

                Examples
                --------
                >>> cfg = Config("localhost", 5432)
                >>> cfg.host
                'localhost'
                """

                def __init__(self, host: str, port: int = 5432):
                    self.host = host
                    self.port = port

                def as_dict(self) -> dict:
                    """
                    Return configuration as a dictionary.

                    Returns
                    -------
                    dict
                        Keys are ``host`` and ``port``.
                    """
                    return {"host": self.host, "port": self.port}

                def validate(self) -> bool:
                    """
                    Validate the configuration.

                    Returns
                    -------
                    bool
                        True if the configuration is valid.

                    Raises
                    ------
                    ValueError
                        If the host is empty or port is out of range.
                    """
                    if not self.host:
                        raise ValueError("Host cannot be empty")
                    if not (1 <= self.port <= 65535):
                        raise ValueError("Port must be between 1 and 65535")
                    return True


            def connect(config: Config) -> str:
                """
                Establish a connection using the given config.

                Parameters
                ----------
                config
                    The connection configuration.

                Returns
                -------
                str
                    Connection URI string.
                """
                return f"{config.host}:{config.port}"


            def disconnect(connection: str) -> bool:
                """
                Close an active connection.

                Parameters
                ----------
                connection
                    The connection string to close.

                Returns
                -------
                bool
                    True if disconnection succeeded.
                """
                return True
        ''',
        "README.md": """\
            # gdtest-namespace-src

            Tests namespace package discovery with src/ layout and dotted module name.
        """,
    },
    # ── Expected outcomes ────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-namespace-src",
        "detected_module": "nspkg.core",
        "detected_parser": "numpy",
        "export_names": ["Config", "connect", "disconnect"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
