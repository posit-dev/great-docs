"""
gdtest_docstring_notes — Detailed Notes sections with multiple paragraphs.

Dimensions: L19
Focus: Two functions with detailed Notes sections containing multiple
       paragraphs and inline code references.
"""

SPEC = {
    "name": "gdtest_docstring_notes",
    "description": "Detailed Notes sections with multi-paragraph prose and inline code",
    "dimensions": ["L19"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-notes",
            "version": "0.1.0",
            "description": "Test detailed Notes section rendering",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "parser": "numpy",
    },
    "files": {
        "gdtest_docstring_notes/__init__.py": '''\
            """Package with detailed Notes sections."""

            __version__ = "0.1.0"
            __all__ = ["merge_dicts", "flatten_list"]


            def merge_dicts(a: dict, b: dict) -> dict:
                """
                Merge two dictionaries into a new dictionary.

                Creates a new dictionary containing all key-value pairs from
                both ``a`` and ``b``. When keys overlap, values from ``b``
                take precedence.

                Parameters
                ----------
                a
                    The base dictionary.
                b
                    The dictionary whose values take priority on conflict.

                Returns
                -------
                dict
                    A new dictionary containing the merged key-value pairs.

                Notes
                -----
                The merge algorithm works in two phases. First, a shallow copy
                of ``a`` is created using ``dict.copy()``. Then, all entries
                from ``b`` are inserted into the copy using ``dict.update()``.

                This means that the original dictionaries ``a`` and ``b`` are
                never modified. However, because only a shallow copy is made,
                mutable values (such as lists or nested dicts) are shared
                between the original and the merged result.

                If you need a deep merge where nested structures are also
                merged recursively, consider using ``copy.deepcopy()`` on the
                result or implementing a custom recursive merge function.

                The time complexity is ``O(len(a) + len(b))`` since both
                the copy and update operations are linear.

                Examples
                --------
                >>> merge_dicts({"x": 1}, {"y": 2})
                {'x': 1, 'y': 2}

                >>> merge_dicts({"x": 1}, {"x": 99})
                {'x': 99}
                """
                result = a.copy()
                result.update(b)
                return result


            def flatten_list(nested: list) -> list:
                """
                Flatten an arbitrarily nested list into a single flat list.

                Recursively traverses the input list and collects all
                non-list elements into a single flat list.

                Parameters
                ----------
                nested
                    A potentially nested list of values.

                Returns
                -------
                list
                    A flat list containing all leaf elements.

                Notes
                -----
                The function uses recursion to handle arbitrarily deep nesting.
                For each element in the input, it checks whether the element
                is itself a ``list``. If so, it recurses into that sublist.
                Otherwise, the element is appended to the result.

                Because Python has a default recursion limit of 1000, this
                function will raise a ``RecursionError`` for lists nested
                deeper than approximately 500 levels (accounting for the
                two-frame overhead per recursive call).

                The implementation allocates a new list and extends it with
                each recursive result. The overall time complexity is
                ``O(n)`` where ``n`` is the total number of leaf elements,
                but the constant factor depends on the nesting depth due
                to intermediate list allocations.

                Examples
                --------
                >>> flatten_list([1, [2, [3, 4], 5], 6])
                [1, 2, 3, 4, 5, 6]

                >>> flatten_list([[["deep"]]])
                ['deep']
                """
                result = []
                for item in nested:
                    if isinstance(item, list):
                        result.extend(flatten_list(item))
                    else:
                        result.append(item)
                return result
        ''',
        "README.md": """\
            # gdtest-v2-docstring-notes

            A synthetic test package with detailed Notes sections.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-notes",
        "detected_module": "gdtest_docstring_notes",
        "detected_parser": "numpy",
        "export_names": ["flatten_list", "merge_dicts"],
        "num_exports": 2,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
