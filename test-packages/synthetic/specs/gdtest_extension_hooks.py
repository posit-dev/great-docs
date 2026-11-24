"""CSV reference customised with object and docstring hooks"""

SPEC = {
    "name": "gdtest_extension_hooks",
    "description": "Document the supported CSV reader and keep the text export in sync.",
    "dimensions": ["D1", "P5"],
    "pyproject_toml": {"project": {"name": "gdtest-extension-hooks", "version": "0.1.0"}},
    "config": {
        "api_reference_extension": "_api_reference_extension.py",
        "dynamic": False,
        "reference": [
            {"title": "CSV imports", "contents": ["read_csv"]},
            {"title": "Legacy readers", "contents": ["read_legacy_csv", "read_compat_csv"]},
        ],
    },
    "files": {
        "gdtest_extension_hooks/__init__.py": '''\
            """CSV readers for current and legacy files"""

            from .readers import read_csv, read_legacy_csv
            from .readers import read_legacy_csv as read_compat_csv

            __all__ = ["read_csv", "read_legacy_csv", "read_compat_csv"]
        ''',
        "gdtest_extension_hooks/readers.py": '''\
            import csv
            from pathlib import Path


            def read_csv(path: str | Path, encoding: str = "utf-8") -> list[dict[str, str]]:
                """
                Read a CSV file with a header row

                Parameters
                ----------
                path
                    Path to the CSV file.
                encoding
                    Text encoding of the file.

                Returns
                -------
                A dictionary per row, keyed by column name.

                Notes
                -----
                The legacy reader treats every file as Latin-1.
                """
                with Path(path).open(encoding=encoding, newline="") as stream:
                    return list(csv.DictReader(stream))


            def read_legacy_csv(path: str | Path) -> list[dict[str, str]]:
                """Read a CSV file saved in Latin-1"""
                return read_csv(path, encoding="latin-1")
        ''',
        "docs/_api_reference_extension.py": """\
            from pathlib import Path

            import griffe as gf

            from great_docs.extensions import Extension


            def setup(extension: Extension) -> None:
                extension.watch("encoding-note.txt")
                note = Path(__file__).with_name("encoding-note.txt").read_text(encoding="utf-8")

                @extension.on_object_resolved
                def document_supported_reader(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
                    if obj.name == "read_legacy_csv":
                        return None
                    if obj.name == "read_csv" and obj.docstring is not None:
                        summary, sections = obj.docstring.value.split("\\n\\n", 1)
                        obj.docstring.value = f"{summary}\\n\\n{note.strip()}\\n\\n{sections}"
                    return obj

                @extension.on_docstring_parsed
                def public_sections(
                    obj: gf.Object | gf.Alias, sections: list[gf.DocstringSection]
                ) -> list[gf.DocstringSection]:
                    if obj.name == "read_csv":
                        return [
                            section
                            for section in sections
                            if not (
                                isinstance(section, gf.DocstringSectionAdmonition)
                                and section.title == "Notes"
                            )
                        ]
                    return sections
        """,
        "docs/encoding-note.txt": "Use UTF-8 for new CSV files.\n",
        "README.md": (
            "# CSV imports\n\n"
            "Use [`read_csv`](reference/read_csv.html) to import a CSV file with a header row. "
            "Its reference page explains which encoding to use. The two legacy import names "
            "remain available to existing Python callers.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-extension-hooks",
        "detected_module": "gdtest_extension_hooks",
        "export_names": ["read_csv", "read_legacy_csv", "read_compat_csv"],
        "num_exports": 3,
        "nodoc_items": ["read_legacy_csv", "read_compat_csv"],
        "explicit_reference": True,
        "init_section_titles": ["Functions"],
    },
}
