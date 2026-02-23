"""
gdtest_sec_tutorials — Custom "Tutorials" section via config.

Dimensions: N2
Focus: Custom section with title "Tutorials" sourced from tutorials/ directory.
"""

SPEC = {
    "name": "gdtest_sec_tutorials",
    "description": "Custom 'Tutorials' section via sections config.",
    "dimensions": ["N2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-sec-tutorials",
            "version": "0.1.0",
            "description": "Test custom Tutorials section.",
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
        "gdtest_sec_tutorials/__init__.py": '"""Test package for custom Tutorials section."""\n',
        "gdtest_sec_tutorials/core.py": '''
            """Core learn/practice functions."""


            def learn(topic: str) -> str:
                """Learn about a specific topic.

                Parameters
                ----------
                topic : str
                    The topic to learn about.

                Returns
                -------
                str
                    A summary of the topic.

                Examples
                --------
                >>> learn("python")
                'Learned about python'
                """
                return f"Learned about {topic}"


            def practice(exercise: int) -> bool:
                """Practice a specific exercise.

                Parameters
                ----------
                exercise : int
                    The exercise number to practice.

                Returns
                -------
                bool
                    True if the exercise was completed successfully.

                Examples
                --------
                >>> practice(1)
                True
                """
                return True
        ''',
        "tutorials/getting-started.qmd": (
            "---\n"
            "title: Getting Started\n"
            "---\n"
            "\n"
            "# Getting Started\n"
            "\n"
            "A beginner-friendly tutorial to help you get started.\n"
        ),
        "tutorials/intermediate.qmd": (
            "---\n"
            "title: Intermediate Tutorial\n"
            "---\n"
            "\n"
            "# Intermediate Tutorial\n"
            "\n"
            "A tutorial covering intermediate-level concepts.\n"
        ),
        "README.md": ("# gdtest-v2-sec-tutorials\n\nTest custom Tutorials section.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-sec-tutorials",
        "detected_module": "gdtest_sec_tutorials",
        "detected_parser": "numpy",
        "export_names": ["learn", "practice"],
        "num_exports": 2,
    },
}
