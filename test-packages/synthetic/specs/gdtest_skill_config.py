"""
gdtest_skill_config — Tests enriched auto-generated skill with config overrides.

Dimensions: S3
Focus: Auto-generated skill.md enriched with gotchas, best_practices,
       decision_table, and extra_body from great-docs.yml config.
"""

SPEC = {
    "name": "gdtest_skill_config",
    "description": "Tests enriched auto-generated skill with config overrides",
    "dimensions": ["S3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-config",
            "version": "0.2.0",
            "description": "A streaming toolkit with enriched skill configuration",
            "license": "MIT",
            "requires-python": ">=3.10",
            "urls": {
                "Repository": "https://github.com/test-org/gdtest-skill-config",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "skill": {
            "gotchas": [
                "Always close streams with `stream.close()` or use a context manager.",
                "The `batch()` generator is lazy — it won't pull data until iterated.",
                "Default chunk size is 1024 bytes; increase for large payloads.",
            ],
            "best_practices": [
                "Use `with Stream(source) as s:` for automatic cleanup.",
                "Prefer `batch()` over manual iteration for memory efficiency.",
                "Set `timeout` explicitly in production to avoid hangs.",
            ],
            "decision_table": [
                {
                    "if": "Need to read data incrementally",
                    "then": "stream = Stream(source)",
                },
                {
                    "if": "Need to process in fixed-size chunks",
                    "then": "for chunk in stream.batch(size=4096): ...",
                },
                {
                    "if": "Need to transform each element",
                    "then": "stream.map(fn) | stream.filter(pred)",
                },
                {
                    "if": "Need buffered output",
                    "then": "sink = Sink(dest, buffer_size=8192)",
                },
            ],
            "extra_body": (
                "## Performance notes\n\n"
                "Throughput scales linearly up to ~10 concurrent streams. "
                "Beyond that, consider using `asyncio` or a thread pool.\n\n"
                "## Compatibility\n\n"
                "Works with file-like objects, sockets, and any object "
                "implementing the `Readable` protocol."
            ),
        },
    },
    "files": {
        "gdtest_skill_config/__init__.py": '''\
            """A streaming toolkit."""

            __version__ = "0.2.0"
            __all__ = ["Stream", "Sink", "batch"]


            class Stream:
                """
                A lazy stream reader.

                Parameters
                ----------
                source
                    A file path or file-like object.
                chunk_size
                    Read chunk size in bytes.
                timeout
                    Read timeout in seconds.
                """

                def __init__(
                    self,
                    source: str,
                    chunk_size: int = 1024,
                    timeout: float | None = None,
                ):
                    self.source = source
                    self.chunk_size = chunk_size
                    self.timeout = timeout

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.close()

                def read(self, n: int = -1) -> bytes:
                    """
                    Read up to n bytes.

                    Parameters
                    ----------
                    n
                        Number of bytes. -1 for all remaining.

                    Returns
                    -------
                    bytes
                        The data read.
                    """
                    return b""

                def close(self) -> None:
                    """Close the stream and release resources."""
                    pass

                def map(self, fn) -> "Stream":
                    """
                    Apply a function to each element.

                    Parameters
                    ----------
                    fn
                        Callable to apply.

                    Returns
                    -------
                    Stream
                        A new transformed stream.
                    """
                    return self

                def filter(self, predicate) -> "Stream":
                    """
                    Filter elements by a predicate.

                    Parameters
                    ----------
                    predicate
                        Callable returning bool.

                    Returns
                    -------
                    Stream
                        A new filtered stream.
                    """
                    return self


            class Sink:
                """
                A buffered output sink.

                Parameters
                ----------
                dest
                    Destination file path or file-like object.
                buffer_size
                    Write buffer size in bytes.
                """

                def __init__(self, dest: str, buffer_size: int = 4096):
                    self.dest = dest
                    self.buffer_size = buffer_size

                def write(self, data: bytes) -> int:
                    """
                    Write data to the sink.

                    Parameters
                    ----------
                    data
                        Bytes to write.

                    Returns
                    -------
                    int
                        Number of bytes written.
                    """
                    return len(data)

                def flush(self) -> None:
                    """Flush the write buffer."""
                    pass


            def batch(iterable, size: int = 10):
                """
                Yield items from an iterable in fixed-size batches.

                Parameters
                ----------
                iterable
                    Input iterable.
                size
                    Batch size.

                Yields
                ------
                list
                    A batch of items.
                """
                batch_items = []
                for item in iterable:
                    batch_items.append(item)
                    if len(batch_items) == size:
                        yield batch_items
                        batch_items = []
                if batch_items:
                    yield batch_items
        ''',
        "README.md": """\
            # gdtest-skill-config

            A streaming toolkit with enriched skill configuration.

            ## Installation

            ```bash
            pip install gdtest-skill-config
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-config",
        "detected_module": "gdtest_skill_config",
        "detected_parser": "numpy",
        "export_names": ["Stream", "Sink", "batch"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_auto_generated": True,
        "skill_has_gotchas": True,
        "skill_has_best_practices": True,
        "skill_has_decision_table": True,
        "skill_has_extra_body": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
