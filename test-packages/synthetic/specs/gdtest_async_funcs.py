"""
gdtest_async_funcs — Async def functions.

Dimensions: A1, B1, C13, D1, E6, F6, G1, H7
Focus: Module with async functions to verify coroutine signatures
       render correctly in the documentation.
"""

SPEC = {
    "name": "gdtest_async_funcs",
    "description": "Async functions (async def); async_save is %nodoc and should not appear",
    "dimensions": ["A1", "B1", "C13", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-async-funcs",
            "version": "0.1.0",
            "description": "Test async function documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_async_funcs/__init__.py": '''\
            """Package with async functions."""

            __version__ = "0.1.0"
            __all__ = ["async_fetch", "async_process", "async_save"]


            async def async_fetch(url: str) -> str:
                """
                Fetch data from a URL asynchronously.

                Parameters
                ----------
                url
                    The URL to fetch.

                Returns
                -------
                str
                    Response body.
                """
                return ""


            async def async_process(data: str) -> dict:
                """
                Process data asynchronously.

                Parameters
                ----------
                data
                    Raw data string.

                Returns
                -------
                dict
                    Processed results.
                """
                return {"data": data}


            async def async_save(data: dict, path: str) -> None:
                """
                Save data asynchronously to a file.

                %nodoc

                Parameters
                ----------
                data
                    Data to save.
                path
                    Destination file path.
                """
                pass
        ''',
        "README.md": """\
            # gdtest-async-funcs

            Tests documentation of async def functions.
        """,
    },
    "expected": {
        "detected_name": "gdtest-async-funcs",
        "detected_module": "gdtest_async_funcs",
        "detected_parser": "numpy",
        "export_names": ["async_fetch", "async_process", "async_save"],
        "num_exports": 3,
        "nodoc_items": ["async_save"],
        "section_titles": ["Async Functions"],
        "has_user_guide": False,
    },
}
