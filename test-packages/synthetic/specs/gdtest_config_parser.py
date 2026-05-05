"""
gdtest_config_parser — Config overrides parser to 'google'.

Dimensions: A1, B1, C1, D1, E3, F2, G1, H7
Focus: Explicit parser='google' in config while code uses Google-style
       docstrings.
"""

SPEC = {
    "name": "gdtest_config_parser",
    "description": "Config overrides parser to google",
    "dimensions": ["A1", "B1", "C1", "D1", "E3", "F2", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-config-parser",
            "version": "0.1.0",
            "description": "Test parser override in config",
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
        "gdtest_config_parser/__init__.py": '''\
            """
            Package with Google docstrings and parser config override.
            """

            __version__ = "0.1.0"
            __all__ = ["connect", "disconnect", "query", "fetch_all"]


            def connect(host: str, port: int = 5432) -> object:
                """Connect to a database.

                Args:
                    host: Database hostname.
                    port: Port number.

                Returns:
                    Connection object.
                """
                return {"host": host, "port": port, "connected": True}


            def disconnect(conn: object) -> None:
                """Disconnect from the database.

                Args:
                    conn: Active connection.
                """
                pass


            def query(conn: object, sql: str) -> list:
                """Execute a SQL query.

                Args:
                    conn: Active connection.
                    sql: SQL query string.

                Returns:
                    List of result rows.
                """
                return []


            def fetch_all(conn: object, table: str) -> list:
                """Fetch all rows from a table.

                Args:
                    conn: Active connection.
                    table: Table name.

                Returns:
                    All rows from the table.
                """
                return []
        ''',
        "README.md": """\
            # gdtest-config-parser

            Tests explicit parser='google' config override.
        """,
    },
    "expected": {
        "detected_name": "gdtest-config-parser",
        "detected_module": "gdtest_config_parser",
        "detected_parser": "google",
        "export_names": ["connect", "disconnect", "query", "fetch_all"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
