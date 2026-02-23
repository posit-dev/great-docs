"""
gdtest_sec_deep — Custom section with nested subdirectories.

Dimensions: N2
Focus: Custom Tutorials section with nested beginner/ and advanced/ subdirectories.
"""

SPEC = {
    "name": "gdtest_sec_deep",
    "description": "Custom section with nested subdirectories.",
    "dimensions": ["N2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-deep",
            "version": "0.1.0",
            "description": "Test custom section with nested subdirectories.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "sections": [
            {"title": "Tutorials", "dir": "tutorials"},
        ],
    },
    "files": {
        "gdtest_sec_deep/__init__.py": '"""Test package for custom section with nested subdirectories."""\n',
        "gdtest_sec_deep/core.py": '''
            """Core learn/test_knowledge functions."""


            def learn(topic: str) -> str:
                """Learn about a specific topic.

                Parameters
                ----------
                topic : str
                    The topic to learn about.

                Returns
                -------
                str
                    A summary of the learned topic.

                Examples
                --------
                >>> learn("python")
                'Learned: python'
                """
                return f"Learned: {topic}"


            def test_knowledge(quiz: str) -> bool:
                """Test knowledge on a given quiz topic.

                Parameters
                ----------
                quiz : str
                    The quiz topic to test.

                Returns
                -------
                bool
                    True if the quiz was passed.

                Examples
                --------
                >>> test_knowledge("basics")
                True
                """
                return True
        ''',
        "tutorials/beginner/hello.qmd": (
            "---\n"
            "title: Hello World\n"
            "---\n"
            "\n"
            "# Hello World\n"
            "\n"
            "A beginner tutorial for getting started.\n"
        ),
        "tutorials/beginner/basics.qmd": (
            "---\ntitle: Basics\n---\n\n# Basics\n\nLearn the basic concepts and patterns.\n"
        ),
        "tutorials/advanced/patterns.qmd": (
            "---\n"
            "title: Advanced Patterns\n"
            "---\n"
            "\n"
            "# Advanced Patterns\n"
            "\n"
            "Explore advanced design patterns and techniques.\n"
        ),
        "README.md": ("# gdtest-v2-sec-deep\n\nTest custom section with nested subdirectories.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-deep",
        "detected_module": "gdtest_sec_deep",
        "detected_parser": "numpy",
        "export_names": ["learn", "test_knowledge"],
        "num_exports": 2,
    },
}
