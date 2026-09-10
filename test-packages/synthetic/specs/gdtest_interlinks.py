"""
gdtest_interlinks: interlink references in docstrings and user-guide pages

Dimensions: A1, D1, F1, L26
Focus: Exercise all interlinks syntax variants in docstrings and user-guide
       pages, plus autolinking and cross-project resolution against a published
       external inventory:
       - ``[](`~pkg.Name`)``  — shortened display
       - ``[](`pkg.Name`)``   — fully qualified display
       - ``[custom text](`pkg.Name`)`` — custom display text
       - ``[custom text](`~pkg.Name`)`` — custom text with tilde (text wins)
       - ``Name``, ``Name()`` — autolinked inline code on user-guide pages
       - ``[](`extdemo.Widget`)``, ``[](`ed.Widget`)`` — a configured
         external source, referenced by full name and by its declared alias
       The post-render resolver and all-pages GDLS pass should convert these
       references into hyperlinks. User-guide links must be relative to
       ``../reference/``.
"""

from pathlib import Path

from great_docs._interlinks import Source
from great_docs._interlinks.sources import InventoryCache
from great_docs._interlinks.sphinx_inventory import Inventory, InventoryEntry, encode

_EXTDEMO_URL = "https://extdemo.example/docs/"

# Represent another project's published inventory.
_EXTERNAL_INVENTORY = encode(
    Inventory(
        project="extdemo",
        version="1.0",
        entries=(
            InventoryEntry(
                name="extdemo.Widget",
                domain="py",
                role="class",
                priority=1,
                uri="Widget.html",
                dispname="extdemo.Widget",
            ),
        ),
    )
)

# Match the cache filename derived from the source URL.
_EXTDEMO_CACHE_NAME = (
    InventoryCache(Path(".")).path_for(Source(name="extdemo", url=_EXTDEMO_URL)).name
)

SPEC = {
    "name": "gdtest_interlinks",
    "description": (
        "Interlinks syntax in docstring prose and user-guide pages. "
        "Exercises [](`~Name`) references and inline-code autolinking on "
        "reference and user-guide pages, including full-name and alias "
        "resolution from a configured external source."
    ),
    "dimensions": ["A1", "D1", "F1", "L26"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-interlinks",
            "version": "0.1.0",
            "description": "Test interlinks in docstring prose and user-guide pages",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "interlinks": {
            "sources": {
                "extdemo": {
                    "url": _EXTDEMO_URL,
                    "aliases": ["ed"],
                },
            },
        },
    },
    "binary_files": {
        # Seed the cache so the build resolves this source without network access.
        f".great-docs-cache/interlinks/{_EXTDEMO_CACHE_NAME}": _EXTERNAL_INVENTORY,
    },
    "files": {
        "gdtest_interlinks/__init__.py": '''\
            """Package demonstrating interlinks in docstring prose and user-guide pages."""

            __version__ = "0.1.0"
            __all__ = ["BaseStore", "DuckDBStore", "ChromaDBStore", "query"]


            class BaseStore:
                """Base class for all stores.

                Available implementations:

                - [](`~gdtest_interlinks.DuckDBStore`): local storage with
                  embedded search.
                - [](`~gdtest_interlinks.ChromaDBStore`): vector storage
                  using ChromaDB.

                Parameters
                ----------
                name
                    The name of the store.
                """

                def __init__(self, name: str) -> None:
                    self.name = name


            class DuckDBStore(BaseStore):
                """Local storage backed by DuckDB.

                Inherits from [](`~gdtest_interlinks.BaseStore`).
                Use [](`~gdtest_interlinks.query`) to search the store
                after loading data.

                Parameters
                ----------
                name
                    The name of the store.
                path
                    Path to the DuckDB database file.
                """

                def __init__(self, name: str, path: str = ":memory:") -> None:
                    super().__init__(name)
                    self.path = path


            class ChromaDBStore(BaseStore):
                """Vector storage using ChromaDB.

                Inherits from [](`gdtest_interlinks.BaseStore`).
                See [the DuckDB-backed store](`~gdtest_interlinks.DuckDBStore`) for a
                simpler alternative.

                Parameters
                ----------
                name
                    The name of the store.
                collection
                    The ChromaDB collection name.
                """

                def __init__(self, name: str, collection: str = "default") -> None:
                    super().__init__(name)
                    self.collection = collection


            def query(store: BaseStore, text: str) -> list:
                """Search a store for matching documents.

                Works with any [](`~gdtest_interlinks.BaseStore`)
                implementation, including
                [](`gdtest_interlinks.DuckDBStore`) and
                [the ChromaDB store](`gdtest_interlinks.ChromaDBStore`).

                Parameters
                ----------
                store
                    The store to search. Must be an instance of
                    [a base store](`~gdtest_interlinks.BaseStore`).
                text
                    The search query string.

                Returns
                -------
                list
                    Matching documents.
                """
                return []
        ''',
        # ── User guide pages with interlinks ────────────────────────────
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            ## Creating a Store

            To store and search documents, first create a
            [](`~gdtest_interlinks.DuckDBStore`) instance:

            ```python
            from gdtest_interlinks import DuckDBStore
            store = DuckDBStore("my-store")
            ```

            ## Checking the Base Interface

            Every store implements the
            [](`~gdtest_interlinks.BaseStore`) interface:

            ```python
            isinstance(store, BaseStore)
            ```

            ## Running Queries

            Call [](`~gdtest_interlinks.query`) to search:

            ```python
            results = query(store, "hello")
            ```

            See the [API Reference](../reference/index.qmd) for full details.
        """,
        "user_guide/02-advanced.qmd": """\
            ---
            title: Advanced Usage
            ---

            ## Full Qualified References

            You can reference the full path:
            [](`gdtest_interlinks.BaseStore`).

            ## Custom Link Text

            Or use [custom link text](`gdtest_interlinks.DuckDBStore`)
            for any reference.

            ## Custom Text with Tilde

            And also [custom text with tilde](`~gdtest_interlinks.ChromaDBStore`)
            to override display.

            ## Autolinked Code

            Inline code like `BaseStore` and `DuckDBStore` and `query()`
            is automatically linked to reference pages.
        """,
        "user_guide/03-external.qmd": """\
            ---
            title: External Links
            ---

            # External Links

            Another project's objects are referenced the same way as our own:
            [](`extdemo.Widget`) names it in full, and [](`ed.Widget`) uses the
            alias the source declares.
        """,
        "README.md": """\
            # gdtest-interlinks

            A synthetic test package testing interlinks in docstring prose and
            user-guide pages.
        """,
    },
    "expected": {
        "detected_name": "gdtest-interlinks",
        "detected_module": "gdtest_interlinks",
        "detected_parser": "numpy",
        "export_names": ["BaseStore", "ChromaDBStore", "DuckDBStore", "query"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-getting-started.qmd", "02-advanced.qmd", "03-external.qmd"],
        # Map each documented object to the expected (display_text, target_name)
        # pairs after post-render interlinks resolution.
        "interlinks_in_prose": {
            # BaseStore: shortened links (~)
            "BaseStore": ["DuckDBStore", "ChromaDBStore"],
            # DuckDBStore: shortened links (~)
            "DuckDBStore": ["BaseStore", "query()"],
            # ChromaDBStore: fully qualified (without ~) and custom text with ~
            "ChromaDBStore": [
                "gdtest_interlinks.BaseStore",  # [](`pkg.Name`) → full name
                "the DuckDB-backed store",  # [custom](`~pkg.Name`) → custom text
            ],
            # query: mix of all styles
            "query": [
                "BaseStore",  # [](`~pkg.Name`) → short name
                "gdtest_interlinks.DuckDBStore",  # [](`pkg.Name`) → full name
                "the ChromaDB store",  # [custom](`pkg.Name`) → custom text
                "a base store",  # [custom](`~pkg.Name`) → custom text
            ],
        },
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
