"""
Separate member pages under a global override

Give every documented member its own page, including members of small classes.
"""

SPEC = {
    "name": "gdtest_inline_never",
    "description": "Gives each class member a page with members_on_same_page: false",
    "dimensions": ["K56"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-inline-never",
            "version": "0.1.0",
            "description": "Separate class member pages under a global override",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "members_on_same_page": False,
    },
    "files": {
        "gdtest_inline_never/__init__.py": '''\
            """Class members placed on separate pages by a global override"""

            __version__ = "0.1.0"
            __all__ = ["TinyWidget", "MediumService", "standalone_func"]


            class TinyWidget:
                """
                A two-method class whose members use separate pages

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

            Set `members_on_same_page: false` to give each method of `TinyWidget`
            (2 methods) and `MediumService` (4 methods) its own page. The override
            applies even though both classes are below the default limit.
        """,
    },
    "expected": {
        "detected_name": "gdtest-inline-never",
        "detected_module": "gdtest_inline_never",
        "detected_parser": "numpy",
        "export_names": ["TinyWidget", "MediumService", "standalone_func"],
        "num_exports": 3,
        # With members_on_same_page: false, both classes get separate member pages
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "methods_always_split": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
