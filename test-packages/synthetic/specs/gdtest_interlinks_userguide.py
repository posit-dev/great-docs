"""
gdtest_interlinks_userguide — interlink references in user-guide pages.

Dimensions: A1, D1, F1, L26
Focus: Tests that the GDLS (Great Docs Linking System) resolves interlinks
       and autolinking in user guide pages, not just reference pages.

       - ``[](`~pkg.Name`)``  — shortened display in user-guide prose
       - ``[](`pkg.Name`)``   — full qualified display in user-guide prose
       - ``[custom text](`pkg.Name`)`` — custom display text in user-guide prose
       - ``Name``, ``Name()`` — autolinked inline code in user-guide prose

       The post-render resolver should convert all of these into proper
       hyperlinks pointing back to the reference pages, with correct
       relative paths (e.g. ``../reference/Foo.html``).
"""

SPEC = {
    "name": "gdtest_interlinks_userguide",
    "description": (
        "Interlinks syntax in user-guide pages. "
        "Tests that [](`~Name`) references and inline-code autolinking "
        "work on non-reference pages via the all-pages GDLS pass."
    ),
    "dimensions": ["A1", "D1", "F1", "L26"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-interlinks-userguide",
            "version": "0.1.0",
            "description": "Test interlinks in user guide pages",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_interlinks_userguide/__init__.py": '''\
            """Package demonstrating interlinks in user-guide pages."""

            __version__ = "0.1.0"
            __all__ = ["Engine", "Connection", "execute"]


            class Engine:
                """Database engine that manages connections.

                Use [](`~gdtest_interlinks_userguide.Connection`) to interact
                with the database.

                Parameters
                ----------
                url
                    Database connection URL.
                """

                def __init__(self, url: str) -> None:
                    self.url = url


            class Connection:
                """Active database connection.

                Created by [](`~gdtest_interlinks_userguide.Engine`).

                Parameters
                ----------
                engine
                    The engine that spawned this connection.
                """

                def __init__(self, engine: Engine) -> None:
                    self.engine = engine


            def execute(conn: Connection, query: str) -> list:
                """Execute a SQL query on a connection.

                Parameters
                ----------
                conn
                    An active [](`~gdtest_interlinks_userguide.Connection`).
                query
                    The SQL query string.

                Returns
                -------
                list
                    Query results.
                """
                return []
        ''',
        # ── User guide pages with interlinks ────────────────────────────
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            ## Creating an Engine

            To connect to a database, first create an
            [](`~gdtest_interlinks_userguide.Engine`) instance:

            ```python
            from gdtest_interlinks_userguide import Engine
            engine = Engine("sqlite:///mydb.db")
            ```

            ## Opening a Connection

            Use the engine to open a
            [](`~gdtest_interlinks_userguide.Connection`):

            ```python
            conn = Connection(engine)
            ```

            ## Running Queries

            Call [](`~gdtest_interlinks_userguide.execute`) to run SQL:

            ```python
            results = execute(conn, "SELECT * FROM users")
            ```

            See the [API Reference](../reference/index.qmd) for full details.
        """,
        "user_guide/02-advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            ## Full Qualified References

            You can reference the full path:
            [](`gdtest_interlinks_userguide.Engine`).

            ## Custom Link Text

            Or use [custom link text](`gdtest_interlinks_userguide.Connection`)
            for any reference.

            ## Custom Text with Tilde

            And also [custom text with tilde](`~gdtest_interlinks_userguide.execute`)
            to override display.

            ## Autolinked Code

            Inline code like `Engine` and `Connection` and `execute()`
            should be automatically linked to reference pages.
        """,
        "README.md": """\
            # gdtest-interlinks-userguide

            A synthetic test package testing interlinks in user-guide pages.
        """,
    },
    "expected": {
        "detected_name": "gdtest-interlinks-userguide",
        "detected_module": "gdtest_interlinks_userguide",
        "detected_parser": "numpy",
        "export_names": ["Connection", "Engine", "execute"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-getting-started.qmd", "02-advanced.qmd"],
        # Interlinks that should be resolved in user-guide pages
        # Each key is a user-guide page filename, value is a list of
        # (display_text, target_page) tuples that should appear as links
        "interlinks_in_userguide": {
            "01-getting-started": {
                "shortened_links": ["Engine", "Connection", "execute()"],
            },
            "02-advanced": {
                "full_qualified_links": ["gdtest_interlinks_userguide.Engine"],
                "custom_text_links": [
                    "custom link text",
                    "custom text with tilde",
                ],
                "autolinked_code": ["Engine", "Connection", "execute()"],
            },
        },
    },
}
