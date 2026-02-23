"""
gdtest_sphinx_class_role — :py:class: cross-reference roles.

Dimensions: L11
Focus: One class and two functions that reference the class via
       :py:class:`Processor`. Tests that Sphinx class roles render correctly.
"""

SPEC = {
    "name": "gdtest_sphinx_class_role",
    "description": ":py:class: cross-reference roles to a class",
    "dimensions": ["L11"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sphinx-class-role",
            "version": "0.1.0",
            "description": "Test :py:class: Sphinx role rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_sphinx_class_role/__init__.py": '''\
            """Package demonstrating :py:class: cross-reference roles."""

            __version__ = "0.1.0"
            __all__ = ["Processor", "create_processor", "is_processor"]


            class Processor:
                """
                A data processor.

                Parameters
                ----------
                name
                    The name of this processor.
                """

                def __init__(self, name: str = "default"):
                    self.name = name

                def run(self) -> None:
                    """
                    Execute the processor.

                    Returns
                    -------
                    None
                    """
                    pass


            def create_processor(name: str) -> Processor:
                """
                Create a new processor.

                Returns a :py:class:`Processor` instance.

                Parameters
                ----------
                name
                    The name for the new processor.

                Returns
                -------
                Processor
                    A new processor instance.
                """
                return Processor(name=name)


            def is_processor(obj: object) -> bool:
                """
                Check if an object is a processor.

                Check if obj is a :py:class:`Processor`.

                Parameters
                ----------
                obj
                    The object to check.

                Returns
                -------
                bool
                    True if obj is a Processor instance.
                """
                return isinstance(obj, Processor)
        ''',
        "README.md": """\
            # gdtest-v2-sphinx-class-role

            A synthetic test package testing ``:py:class:`` cross-reference roles.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-sphinx-class-role",
        "detected_module": "gdtest_sphinx_class_role",
        "detected_parser": "numpy",
        "export_names": ["Processor", "create_processor", "is_processor"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
