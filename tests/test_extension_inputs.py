"""Verify extension-input fingerprints, watch paths and the publication of collected pages"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from great_docs._apiref._customisation import Extension, ExtensionError
from great_docs._apiref._extension_inputs import fingerprint
from great_docs._apiref._settings import Settings
from tests.support import MakeReference, WriteExtension

PACKAGE_FILES = {
    "__init__.py": '''
        def first():
            """First subject"""

        def last():
            """Last subject"""
    '''
}
BLOCK = {
    "package": "input_collection_example",
    "dynamic": False,
    "sections": [{"contents": ["first", "last"]}],
}


def digest(entry: Path, *declarations: Path) -> str:
    """
    Fingerprint an entry file and its declared inputs with an empty digest cache

    Parameters
    ----------
    entry
        The extension entry file.
    declarations
        The declared files, directories or globs.

    Returns
    -------
    :
        The fingerprint that a new operation computes.
    """
    return fingerprint(entry, [], declarations, {})


def test_same_size_source_edits_refresh_between_operations(tmp_path: Path):
    entry = tmp_path / "extension.py"
    entry.write_text("VALUE = 'first'\n")
    timestamp = entry.stat().st_mtime_ns
    first = digest(entry)
    entry.write_text("VALUE = 'other'\n")
    os.utime(entry, ns=(timestamp, timestamp))
    assert digest(entry) != first


def test_missing_file_creation_and_deletion_change_fingerprint(tmp_path: Path):
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    pass\n")
    missing = tmp_path / "missing.txt"
    original = digest(entry, missing)
    missing.write_text("current")
    assert digest(entry, missing) != original
    missing.unlink()
    assert digest(entry, missing) == original


def test_glob_membership_ignores_nonmatching_files_and_tracks_new_matches(tmp_path: Path):
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    pass\n")
    data = tmp_path / "data"
    data.mkdir()
    pattern = data / "*.txt"
    original = digest(entry, pattern)
    (data / "ignored.csv").write_text("ignored")
    assert digest(entry, pattern) == original
    first = data / "first.txt"
    first.write_text("same content")
    one_match = digest(entry, pattern)
    assert one_match != original
    second = data / "second.txt"
    second.write_text("same content")
    assert digest(entry, pattern) != one_match
    first.unlink()
    second.unlink()
    assert digest(entry, pattern) == original


def test_directory_fingerprints_include_empty_entries_and_file_bytes(tmp_path: Path):
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    pass\n")
    data = tmp_path / "data"
    data.mkdir()
    original = digest(entry, data)
    nested = data / "empty"
    nested.mkdir()
    assert digest(entry, data) != original
    nested.rmdir()
    assert digest(entry, data) == original
    value = data / "value.txt"
    value.write_text("first")
    first = digest(entry, data)
    value.write_text("other")
    assert digest(entry, data) != first


def test_owner_input_cache_is_limited_to_its_operation(
    tmp_path: Path, write_extension: WriteExtension
):
    source = write_extension(
        """
        def setup(extension):
            extension.watch('value.txt')
        """
    )
    value = tmp_path / "value.txt"
    value.write_text("first")
    first = Extension(Settings(), source)
    first.load()
    initial = first.fingerprint()
    value.write_text("other")
    assert first.fingerprint() == initial
    first.close()
    second = Extension(Settings(), source)
    try:
        second.load()
        assert second.fingerprint() != initial
    finally:
        second.close()


def test_watch_paths_retain_patterns_and_do_not_activate_unused_reference(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        def setup(extension):
            extension.watch('data/*.txt')
        """
    )
    reference = make_reference({"package": "unused"}, source)
    assert reference.extension_watch_paths == (tmp_path,)
    assert reference.extension.declared_inputs == ()
    reference.extension.load()
    expected = (tmp_path, source.entry_path, tmp_path / "data/*.txt")
    assert reference.extension_watch_paths == expected
    reference.close()
    assert reference.extension_watch_paths == expected


def test_unconfigured_owner_has_no_fingerprint_or_watch_inputs():
    extension = Extension(Settings())
    assert extension.fingerprint() is None
    assert extension.watch_paths == ()
    extension.close()


def test_late_render_failure_preserves_every_previously_published_page(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        from great_docs.rendering import FunctionRenderer, Renderers

        class Presentation(FunctionRenderer):
            def render_docstring_body(self) -> str:
                if self.context.authored_name == 'last':
                    raise ValueError('late render failure')
                return 'new unpublished body'

        def setup(extension):
            extension.set_renderers(Renderers(functions=Presentation))
        """
    )
    output = tmp_path / "output"
    reference = make_reference(BLOCK, source, package_files=PACKAGE_FILES, output_root=output)
    directory = output / "reference"
    directory.mkdir()
    for name in ("index", "first", "last"):
        (directory / f"{name}.qmd").write_text(f"last good {name}")
    with pytest.raises(ExtensionError, match="late render failure"):
        reference.build()
    assert [(directory / f"{name}.qmd").read_text() for name in ("index", "first", "last")] == [
        "last good index",
        "last good first",
        "last good last",
    ]


def test_unchanged_configured_object_pages_keep_their_timestamp(
    tmp_path: Path, write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        def setup(extension):
            pass
        """
    )
    output = tmp_path / "output"
    first = make_reference(BLOCK, source, package_files=PACKAGE_FILES, output_root=output)
    first.build()
    first.close()
    page = output / "reference" / "first.qmd"
    os.utime(page, ns=(1_000_000_000, 1_000_000_000))
    second = make_reference(BLOCK, source, package_files=PACKAGE_FILES, output_root=output)
    second.build()
    assert page.stat().st_mtime_ns == 1_000_000_000
    assert "<!-- great-docs-api-reference-inputs:" in page.read_text()
