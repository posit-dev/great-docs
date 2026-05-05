"""
gdtest_inline_never — Tests inline_methods: false (always split methods).

Dimensions: K56
Focus: When inline_methods is set to false, every class with at least one
method gets its methods split into separate pages, regardless of method count.
"""

SPEC = {
    "name": "gdtest_inline_never",
    "description": "Tests inline_methods: false (always split to separate pages)",
    "dimensions": ["K56"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-never",
            "version": "0.1.0",
            "description": "Test package for inline_methods: false",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "inline_methods": False,
    },
    "files": {
        "gdtest_inline_never/__init__.py": '''\
            """Package testing inline_methods: false (always split)."""

            __version__ = "0.1.0"
            __all__ = ["TinyWidget", "MediumService", "standalone_func"]


            class TinyWidget:
                """
                A class with only two methods—still gets split with inline_methods: false.

                Parameters
                ----------
                label
                    Display label for the widget.
                """

                def __init__(self, label: str):
                    self.label = label

                def show(self) -> str:
                    """
                    Show the widget.

                    Returns
                    -------
                    str
                        Rendered representation.
                    """
                    return f"[{self.label}]"

                def hide(self) -> None:
                    """Hide the widget from display."""
                    pass


            class MediumService:
                """
                A service class with a moderate number of methods.

                Parameters
                ----------
                host
                    Service hostname.
                port
                    Service port number.
                """

                def __init__(self, host: str, port: int = 8080):
                    self.host = host
                    self.port = port

                def start(self) -> None:
                    """Start the service."""
                    pass

                def stop(self) -> None:
                    """Stop the service."""
                    pass

                def restart(self) -> None:
                    """Restart the service."""
                    pass

                def status(self) -> str:
                    """
                    Get the service status.

                    Returns
                    -------
                    str
                        Current status (running, stopped, error).
                    """
                    return "running"


            def standalone_func(value: str) -> str:
                """
                Process a standalone value.

                Parameters
                ----------
                value
                    Input string to process.

                Returns
                -------
                str
                    Processed output string.
                """
                return value.upper()
        ''',
        "README.md": """\
            # gdtest-inline-never

            Package testing `inline_methods: false`. Both TinyWidget (2 methods)
            and MediumService (4 methods) get split into separate method pages,
            even though they would normally stay inline with the default threshold.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-never",
        "detected_module": "gdtest_inline_never",
        "detected_parser": "numpy",
        "export_names": ["TinyWidget", "MediumService", "standalone_func"],
        "num_exports": 3,
        # With inline_methods: false, BOTH classes get "Methods" companion sections
        "section_titles": [
            "Classes",
            "TinyWidget Methods",
            "MediumService Methods",
            "Functions",
        ],
        "has_user_guide": False,
        "methods_always_split": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
