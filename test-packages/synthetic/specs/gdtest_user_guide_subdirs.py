"""
gdtest_user_guide_subdirs — User guide with subdirectories.

Dimensions: A1, B1, C1, D1, E6, F3, G1, H7
Focus: user_guide/basics/ and user_guide/advanced/ subdirectories.
       Tests recursive scanning and subdirectory handling.
"""

SPEC = {
    "name": "gdtest_user_guide_subdirs",
    "description": "User guide with subdirectories",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F3", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-user-guide-subdirs",
            "version": "0.1.0",
            "description": "A synthetic test package with subdirectory user guide",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_user_guide_subdirs/__init__.py": '''\
            """A test package with subdirectory user guide."""

            __version__ = "0.1.0"
            __all__ = ["hello", "goodbye"]


            def hello(name: str) -> str:
                """
                Say hello.

                Parameters
                ----------
                name
                    Who to greet.

                Returns
                -------
                str
                    A greeting.
                """
                return f"Hello, {name}!"


            def goodbye(name: str) -> str:
                """
                Say goodbye.

                Parameters
                ----------
                name
                    Who to bid farewell.

                Returns
                -------
                str
                    A farewell.
                """
                return f"Goodbye, {name}!"
        ''',
        "user_guide/basics/01-intro.qmd": """\
            ---
            title: Introduction
            ---

            Basic introduction.
        """,
        "user_guide/basics/02-setup.qmd": """\
            ---
            title: Setup
            ---

            Basic setup instructions.
        """,
        "user_guide/advanced/01-tips.qmd": """\
            ---
            title: Tips and Tricks
            ---

            Advanced tips.
        """,
        "README.md": """\
            # gdtest-user-guide-subdirs

            A synthetic test package with subdirectory user guide.
        """,
    },
    "expected": {
        "detected_name": "gdtest-user-guide-subdirs",
        "detected_module": "gdtest_user_guide_subdirs",
        "detected_parser": "numpy",
        "export_names": ["hello", "goodbye"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": True,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
