"""
gdtest_docstring_seealso — See Also sections in NumPy-style docstrings.

Dimensions: L22
Focus: Three functions with See Also sections cross-referencing each other.
"""

SPEC = {
    "name": "gdtest_docstring_seealso",
    "description": "See Also sections cross-referencing related functions",
    "dimensions": ["L22"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-docstring-seealso",
            "version": "0.1.0",
            "description": "Test See Also section rendering",
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
        "gdtest_docstring_seealso/__init__.py": '''\
            """Package with See Also sections in docstrings."""

            __version__ = "0.1.0"
            __all__ = ["serialize", "deserialize", "to_json"]


            def serialize(obj: object) -> bytes:
                """
                Serialize a Python object to bytes.

                Converts the given object into a byte string representation
                using pickle serialization.

                Parameters
                ----------
                obj
                    The Python object to serialize. Must be picklable.

                Returns
                -------
                bytes
                    The serialized byte string.

                Raises
                ------
                TypeError
                    If the object cannot be pickled.

                See Also
                --------
                deserialize : Convert bytes back into a Python object.
                to_json : Serialize an object to a JSON string instead.

                Examples
                --------
                >>> data = serialize({"key": "value"})
                >>> isinstance(data, bytes)
                True
                """
                import pickle

                return pickle.dumps(obj)


            def deserialize(data: bytes) -> object:
                """
                Deserialize bytes back into a Python object.

                Reconstructs a Python object from a byte string that was
                previously created by ``serialize``.

                Parameters
                ----------
                data
                    A byte string produced by ``serialize``.

                Returns
                -------
                object
                    The reconstructed Python object.

                Raises
                ------
                ValueError
                    If the byte string is corrupted or invalid.

                See Also
                --------
                serialize : Convert a Python object to bytes.

                Examples
                --------
                >>> original = {"key": "value"}
                >>> data = serialize(original)
                >>> deserialize(data)
                {'key': 'value'}
                """
                import pickle

                return pickle.loads(data)


            def to_json(obj: object) -> str:
                """
                Serialize a Python object to a JSON string.

                Converts the given object into a human-readable JSON string.
                Supports dicts, lists, strings, numbers, booleans, and None.

                Parameters
                ----------
                obj
                    The Python object to serialize. Must be JSON-serializable.

                Returns
                -------
                str
                    A JSON-formatted string.

                Raises
                ------
                TypeError
                    If the object is not JSON-serializable.

                See Also
                --------
                serialize : Serialize to bytes using pickle (supports more types).
                from_json : Parse a JSON string back into a Python object.

                Examples
                --------
                >>> to_json({"name": "test", "value": 42})
                '{"name": "test", "value": 42}'
                """
                import json

                return json.dumps(obj)
        ''',
        "README.md": """\
            # gdtest-v2-docstring-seealso

            A synthetic test package with See Also sections.
        """,
    },
    "expected": {
        "detected_name": "gdtest-v2-docstring-seealso",
        "detected_module": "gdtest_docstring_seealso",
        "detected_parser": "numpy",
        "export_names": ["deserialize", "serialize", "to_json"],
        "num_exports": 3,
        "section_titles": ["Functions"],
        "has_user_guide": False,
    },
}
