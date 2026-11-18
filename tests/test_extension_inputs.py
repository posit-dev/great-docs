"""Verify extension-input fingerprints, watch paths and the publication of collected pages"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from great_docs._apiref._customisation import Extension, ExtensionError
from great_docs._apiref._extension_inputs import fingerprint
from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference


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


def test_same_size_source_edits_refresh_between_operations(tmp_path: Path) -> None:
    entry = tmp_path / "extension.py"
    entry.write_text("VALUE = 'first'\n")
    timestamp = entry.stat().st_mtime_ns
    first = digest(entry)
    entry.write_text("VALUE = 'other'\n")
    os.utime(entry, ns=(timestamp, timestamp))
    assert digest(entry) != first


def test_missing_file_creation_and_deletion_change_fingerprint(tmp_path: Path) -> None:
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    pass\n")
    missing = tmp_path / "missing.txt"
    original = digest(entry, missing)
    missing.write_text("current")
    assert digest(entry, missing) != original
    missing.unlink()
    assert digest(entry, missing) == original


def test_glob_membership_ignores_nonmatching_files_and_tracks_new_matches(tmp_path: Path) -> None:
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


def test_directory_fingerprints_include_empty_entries_and_file_bytes(tmp_path: Path) -> None:
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


def test_owner_input_cache_is_limited_to_its_operation(tmp_path: Path) -> None:
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    extension.watch('value.txt')\n")
    value = tmp_path / "value.txt"
    value.write_text("first")
    source = _ExtensionSource(entry, tmp_path, tmp_path)
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


def test_watch_paths_retain_patterns_and_do_not_activate_unused_reference(tmp_path: Path) -> None:
    entry = tmp_path / "extension.py"
    entry.write_text("def setup(extension):\n    extension.watch('data/*.txt')\n")
    source = _ExtensionSource(entry, tmp_path, tmp_path)
    reference = APIReference({"package": "unused"}, extension_source=source)
    assert reference.extension_watch_paths == (tmp_path,)
    assert reference.extension.declared_inputs == ()
    reference.extension.load()
    expected = (tmp_path, entry, tmp_path / "data/*.txt")
    assert reference.extension_watch_paths == expected
    reference.close()
    assert reference.extension_watch_paths == expected


def test_unconfigured_owner_has_no_fingerprint_or_watch_inputs() -> None:
    extension = Extension(Settings())
    assert extension.fingerprint() is None
    assert extension.watch_paths == ()
    extension.close()


@pytest.fixture
def reference_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Path, Path]]:
    """Own one small importable package and its generated output directory"""
    name = "input_collection_example"
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text(
        'def first():\n    """First subject"""\ndef last():\n    """Last subject"""\n'
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.chdir(output)
    try:
        yield tmp_path, output
    finally:
        sys.modules.pop(name, None)


def reference_for(root: Path, output: Path) -> APIReference:
    """Configure the fixture's two pages with explicit operation roots"""
    return APIReference(
        {
            "package": "input_collection_example",
            "dynamic": False,
            "sections": [{"contents": ["first", "last"]}],
        },
        extension_source=_ExtensionSource(root / "extension.py", root, root),
        output_root=output,
    )


def test_late_render_failure_preserves_every_previously_published_page(
    reference_project: tuple[Path, Path],
) -> None:
    root, output = reference_project
    (root / "extension.py").write_text(
        "from great_docs.rendering import FunctionRenderer, Renderers\n"
        "class Presentation(FunctionRenderer):\n"
        "    def render_docstring_body(self) -> str:\n"
        "        if self.context.authored_name == 'last':\n"
        "            raise ValueError('late render failure')\n"
        "        return 'new unpublished body'\n"
        "def setup(extension):\n"
        "    extension.set_renderers(Renderers(functions=Presentation))\n"
    )
    directory = output / "reference"
    directory.mkdir()
    for name in ("index", "first", "last"):
        (directory / f"{name}.qmd").write_text(f"last good {name}")
    reference = reference_for(root, output)
    try:
        with pytest.raises(ExtensionError, match="late render failure"):
            reference.build()
        assert [(directory / f"{name}.qmd").read_text() for name in ("index", "first", "last")] == [
            "last good index",
            "last good first",
            "last good last",
        ]
    finally:
        reference.close()


def test_unchanged_configured_object_pages_keep_their_timestamp(
    reference_project: tuple[Path, Path],
) -> None:
    root, output = reference_project
    (root / "extension.py").write_text("def setup(extension):\n    pass\n")
    first = reference_for(root, output)
    first.build()
    first.close()
    page = output / "reference" / "first.qmd"
    os.utime(page, ns=(1_000_000_000, 1_000_000_000))
    second = reference_for(root, output)
    try:
        second.build()
        assert page.stat().st_mtime_ns == 1_000_000_000
        assert "<!-- great-docs-api-reference-inputs:" in page.read_text()
    finally:
        second.close()
