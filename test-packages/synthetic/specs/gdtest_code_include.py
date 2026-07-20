"""
gdtest_code_include — Code-include shortcode in user guide pages.

Dimensions: A1, B1, C4, D1, E6, F1, G1, H7
Focus: {{< include >}} shortcode usage in user guide pages.
       Tests basic includes with auto language detection, different file types,
       line ranges, and language overrides.
"""

SPEC = {
    "name": "gdtest_code_include",
    "description": "Code-include shortcode in user guide pages",
    "dimensions": ["A1", "B1", "C4", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-code-include",
            "version": "0.1.0",
            "description": "A synthetic test package demonstrating the include shortcode",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_code_include/__init__.py": '''\
            """A test package demonstrating the include shortcode."""

            __version__ = "0.1.0"
            __all__ = ["Widget", "run_widget"]


            class Widget:
                """
                A configurable widget.

                Parameters
                ----------
                name
                    The widget name.
                """

                def __init__(self, name: str):
                    self.name = name
                    self._color = "red"
                    self._size = 5

                def configure(self, color: str = "red", size: int = 5) -> None:
                    """
                    Configure the widget appearance.

                    Parameters
                    ----------
                    color
                        Widget color.
                    size
                        Widget size.
                    """
                    self._color = color
                    self._size = size

                def run(self) -> str:
                    """
                    Run the widget and return a result string.

                    Returns
                    -------
                    str
                        A summary of the widget state.
                    """
                    return f"{self.name}: color={self._color}, size={self._size}"


            def run_widget(name: str, color: str = "blue", size: int = 10) -> str:
                """
                Create, configure, and run a widget in one call.

                Parameters
                ----------
                name
                    The widget name.
                color
                    Widget color.
                size
                    Widget size.

                Returns
                -------
                str
                    The widget result string.
                """
                w = Widget(name)
                w.configure(color=color, size=size)
                return w.run()
        ''',
        "gdtest_code_include/examples/demo.py": '''\
            from gdtest_code_include import Widget

            # Create and configure a widget
            widget = Widget("demo")
            widget.configure(color="blue", size=10)

            # Run the widget
            result = widget.run()
            print(f"Result: {result}")
        ''',
        "gdtest_code_include/examples/config.yaml": '''\
            app:
              name: my-app
              version: "1.0"
              settings:
                debug: true
                log_level: info
        ''',
        "user_guide/01-includes.qmd": '''\
            ---
            title: Code Includes
            guide-section: Tutorials
            ---

            This guide demonstrates the `include` shortcode, which lets you
            embed source files directly into your documentation pages.

            ## Basic Python Include

            The simplest usage includes an entire file with automatic language
            detection. The shortcode infers the language from the file extension.

            {{< include gdtest_code_include/examples/demo.py >}}

            ## Including a YAML File

            The `include` shortcode works with any text file type. Here we
            include a YAML configuration file, and the language is detected
            automatically from the `.yaml` extension.

            {{< include gdtest_code_include/examples/config.yaml >}}

            ## Selecting a Line Range

            You can include only specific lines from a file using the `lines`
            parameter. This is useful for highlighting a particular section
            without showing the entire file.

            {{< include gdtest_code_include/examples/demo.py lines="1-3" >}}

            ## Overriding the Language

            Sometimes a file extension doesn't match the highlighting you want.
            Use the `lang` parameter to override the auto-detected language. Here
            we display a Python file with R syntax highlighting instead.

            {{< include gdtest_code_include/examples/demo.py lang="r" >}}
        ''',
        "README.md": """\
            # gdtest-code-include

            A synthetic test package demonstrating the include shortcode.
        """,
    },
    "expected": {
        "detected_name": "gdtest-code-include",
        "detected_module": "gdtest_code_include",
        "detected_parser": "numpy",
        "export_names": ["Widget", "run_widget"],
        "num_exports": 2,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": ["01-includes.qmd"],
        "coverage_exclude": ["nodoc", "bigcl", "supp", "hdg"],
    },
}
