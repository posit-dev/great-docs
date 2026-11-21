"""
gdtest_wrapped_summary — Docstring summaries that wrap over several lines.

Dimensions: A1, B1, C4, D1, E6, F6, G5, H7
Focus: The summary is a docstring's whole first paragraph, so one that wraps
       over two or three lines shows in full under the title, in the index
       tables and in llms.txt, and none of it is left at the start of the
       description. Also covers a one-line summary, and a summary followed
       directly by a code block, which ends it.
"""

SPEC = {
    "name": "gdtest_wrapped_summary",
    "description": "Docstring summaries that wrap over several lines are shown whole",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F6", "G5", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-wrapped-summary",
            "version": "0.1.0",
            "description": "A synthetic test package with wrapped docstring summaries",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_wrapped_summary/__init__.py": '''\
            """A package whose docstrings open with wrapped summaries."""

            __version__ = "0.1.0"
            __all__ = ["Table", "fenced", "inspect_data", "scale", "view_state"]


            class Table:
                """A table whose view readers can change, kept between their
                visits to the page.

                The table holds its rows and the reader's view of them.
                """

                def view_state(self, url: bool = True, undo: bool = True) -> "Table":
                    """Keep the reader's view of this table, for when the page is
                    opened again, and let them undo their changes to it.

                    The view is the table's filters, sort and search.

                    Parameters
                    ----------
                    url
                        Whether to keep the view in the page's URL.
                    undo
                        Whether readers can undo their changes.

                    Returns
                    -------
                    Table
                        The table.
                    """
                    return self


            def view_state(url: bool = True, undo: bool = True) -> dict:
                """Keep the reader's view of the table, for when the page is opened again,
                and let them undo their changes to it.

                The view is the table's filters, sort, search, page and hidden columns.

                Parameters
                ----------
                url
                    Whether to keep the view in the page's URL.
                undo
                    Whether readers can undo their changes.

                Returns
                -------
                dict
                    The settings for the view.
                """
                return {"url": url, "undo": undo}


            def scale(where: str = "client") -> str:
                """Set where the rows of the table, shown as a widget
                or in a Shiny app, are searched, filtered
                and sorted.

                Searching in the browser suits small tables.

                Parameters
                ----------
                where
                    Either `"client"` or `"server"`.

                Returns
                -------
                str
                    Where the rows are processed.
                """
                return where


            def inspect_data() -> dict:
                """Show readers what's in the data.

                The details include the rows' numbers and the columns' dtypes.

                Returns
                -------
                dict
                    A description of the data.
                """
                return {}


            def fenced() -> str:
                """Return a greeting, as the example shows.
                ```python
                fenced()
                ```

                Returns
                -------
                str
                    The greeting.
                """
                return "hello"
        ''',
    },
    "expected": {
        "detected_name": "gdtest-wrapped-summary",
        "detected_module": "gdtest_wrapped_summary",
        "detected_parser": "numpy",
        "export_names": ["Table", "fenced", "inspect_data", "scale", "view_state"],
        "num_exports": 5,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_license_page": False,
        "has_citation_page": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp"],
        "files_contain": {
            "reference/view_state.html": [
                "Keep the reader’s view of the table, for when the page is opened again, "
                "and let them undo their changes to it.",
            ],
        },
    },
}
