"""
gdtest_ref_title — Reference config with custom title.

Dimensions: P8
Focus: Reference config using a dict with a custom title instead of a list of sections.
"""

SPEC = {
    "name": "gdtest_ref_title",
    "description": "Reference config with custom title.",
    "dimensions": ["P8"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-ref-title",
            "version": "0.1.0",
            "description": "Test reference config with custom title.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "reference": {"title": "API Docs"},
    },
    "files": {
        "gdtest_ref_title/__init__.py": '''\
            """Package testing reference config with custom title."""

            __all__ = ["query", "insert", "delete"]


            def query(sql: str) -> list:
                """Execute a SQL query and return the results.

                Parameters
                ----------
                sql : str
                    The SQL query string to execute.

                Returns
                -------
                list
                    A list of result rows.

                Examples
                --------
                >>> query("SELECT * FROM users")
                [{'id': 1, 'name': 'Alice'}]
                """
                return [{"id": 1, "name": "Alice"}]


            def insert(table: str, data: dict) -> int:
                """Insert a row into a table and return the new row ID.

                Parameters
                ----------
                table : str
                    The name of the table to insert into.
                data : dict
                    A dictionary of column-value pairs.

                Returns
                -------
                int
                    The ID of the newly inserted row.

                Examples
                --------
                >>> insert("users", {"name": "Bob"})
                2
                """
                return 2


            def delete(table: str, id: int) -> bool:
                """Delete a row from a table by its ID.

                Parameters
                ----------
                table : str
                    The name of the table to delete from.
                id : int
                    The ID of the row to delete.

                Returns
                -------
                bool
                    True if the row was deleted successfully.

                Examples
                --------
                >>> delete("users", 1)
                True
                """
                return True
        ''',
        "README.md": ("# gdtest-v2-ref-title\n\nTest reference config with custom title.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-ref-title",
        "detected_module": "gdtest_ref_title",
        "detected_parser": "numpy",
        "export_names": ["delete", "insert", "query"],
        "num_exports": 3,
    },
}
