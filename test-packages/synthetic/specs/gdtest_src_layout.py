"""
gdtest_src_layout — Modern src/ layout package.

Dimensions: A2, B1, C4, D1, E6, F6, G1, H7
Focus: Package code lives under src/<pkg>/ — tests the _find_package_init
       search through the src/ directory, plus mixed class+function exports.
"""

SPEC = {
    "name": "gdtest_src_layout",
    "description": "Modern src/ layout package; destroy_widget is %nodoc and should not appear",
    "dimensions": ["A2", "B1", "C4", "D1", "E6", "F6", "G1", "H7"],
    # ── Project metadata ─────────────────────────────────────────────
    "pyproject_toml": {
        "project": {
            "name": "gdtest-src-layout",
            "version": "0.1.0",
            "description": "A synthetic test package using src/ layout",
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
    # ── Source files ──────────────────────────────────────────────────
    "files": {
        "src/gdtest_src_layout/__init__.py": '''\
            """A test package using the modern src/ layout."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "create_widget", "destroy_widget"]


            class Widget:
                """
                A simple widget for demonstration.

                Parameters
                ----------
                name
                    The name of the widget.
                color
                    The widget color.

                Examples
                --------
                >>> w = Widget("button", color="blue")
                >>> w.name
                'button'
                """

                def __init__(self, name: str, color: str = "red"):
                    self.name = name
                    self.color = color

                def render(self) -> str:
                    """
                    Render the widget as a string.

                    Returns
                    -------
                    str
                        An HTML-like string representation.
                    """
                    return f"<widget name='{self.name}' color='{self.color}'/>"

                def resize(self, width: int, height: int) -> None:
                    """
                    Resize the widget.

                    Parameters
                    ----------
                    width
                        New width in pixels.
                    height
                        New height in pixels.
                    """
                    self.width = width
                    self.height = height


            def create_widget(name: str, **kwargs) -> Widget:
                """
                Factory function for creating widgets.

                Parameters
                ----------
                name
                    The widget name.
                **kwargs
                    Additional keyword arguments passed to :class:`Widget`.

                Returns
                -------
                Widget
                    A new widget instance.
                """
                return Widget(name, **kwargs)


            def destroy_widget(widget: Widget) -> bool:
                """
                Destroy a widget and free its resources.

                %nodoc

                Parameters
                ----------
                widget
                    The widget to destroy.

                Returns
                -------
                bool
                    True if successfully destroyed.
                """
                del widget
                return True
        ''',
        "README.md": """\
            # gdtest-src-layout

            A synthetic test package using the modern ``src/`` layout convention.
        """,
    },
    # ── Expected outcomes ─────────────────────────────────────────────
    "expected": {
        "detected_name": "gdtest-src-layout",
        "detected_module": "gdtest_src_layout",
        "detected_parser": "numpy",
        "export_names": ["Widget", "create_widget", "destroy_widget"],
        "num_exports": 3,
        "nodoc_items": ['destroy_widget'],
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
