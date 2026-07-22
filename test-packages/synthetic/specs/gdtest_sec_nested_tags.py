"""
gdtest_sec_nested_tags — Page tags inside a custom section with a nested dir.

Dimensions: T4
Focus: Regression for #213. A custom section whose ``dir`` is a nested path
       (``docs/examples``) that does NOT match the title-derived slug
       (``examples``). Tagged pages live under the build path
       ``great-docs/docs/examples/`` and must be discovered by tag scanning,
       which previously looked at the wrong title-slug directory.
"""

SPEC = {
    "name": "gdtest_sec_nested_tags",
    "description": "Page tags in a custom section with a nested dir (#213)",
    "dimensions": ["T4"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sec-nested-tags",
            "version": "0.1.0",
            "description": "Tags in a custom section published from a nested dir",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "display_name": "Nested Section Tags Demo",
        # The section dir is nested and intentionally differs from the
        # title-derived slug ("Examples" -> "examples"). The build copies it to
        # great-docs/docs/examples/, which is where tag scanning must look.
        "sections": [
            {"title": "Examples", "dir": "docs/examples"},
        ],
        "tags": {
            "enabled": True,
            "index_page": True,
            "show_on_pages": True,
            "hierarchical": True,
            "icons": {
                "Python": "code",
                "Tutorial": "book-open",
            },
        },
    },
    "files": {
        "gdtest_sec_nested_tags/__init__.py": '''\
            """A test package for tags in a nested custom section."""

            __version__ = "0.1.0"
            __all__ = ["transform", "validate"]


            def transform(data: list) -> list:
                """
                Transform a list of data items.

                Parameters
                ----------
                data
                    The input data to transform.

                Returns
                -------
                list
                    The transformed data.
                """
                return data


            def validate(data: list) -> bool:
                """
                Validate a list of data items.

                Parameters
                ----------
                data
                    The input data to validate.

                Returns
                -------
                bool
                    True if the data is valid.
                """
                return True
        ''',
        # Tagged pages under a NESTED section dir. With #213 unfixed, tag
        # scanning looks at great-docs/examples/ and finds nothing here.
        "docs/examples/basic-usage.qmd": """\
            ---
            title: Basic Usage
            tags: [Tutorial, Python]
            ---

            ## Getting Started

            This example shows basic usage of the library and carries tags.
        """,
        "docs/examples/advanced-patterns.qmd": """\
            ---
            title: Advanced Patterns
            tags: [Python/Advanced, Tutorial]
            ---

            ## Advanced Usage

            This example demonstrates advanced patterns and a hierarchical tag.
        """,
        "docs/examples/no-tags.qmd": """\
            ---
            title: Untagged Example
            ---

            This page has no tags and should not appear in the tag index.
        """,
        "README.md": """\
            # gdtest-sec-nested-tags

            A test package demonstrating page tags inside a custom section
            published from a nested directory (`docs/examples`).
        """,
    },
    "expected": {
        "detected_name": "gdtest-sec-nested-tags",
        "detected_module": "gdtest_sec_nested_tags",
        "detected_parser": "numpy",
        "export_names": ["transform", "validate"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec", "hdg"],
    },
}
