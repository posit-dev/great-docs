"""
Preview inputs and content fingerprints for an API reference extension

A fingerprint covers the extension file, its helper modules and every declared input,
including missing inputs, directory contents and the current matches of each glob. File
digests may be reused within one operation, but directory contents and glob matches are
read afresh every time.
"""

from __future__ import annotations

import glob
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path


def watch_paths(
    entry_path: Path, imported_paths: Iterable[Path], declared_inputs: Iterable[Path]
) -> tuple[Path, ...]:
    """
    List the paths that a preview watches for an extension

    Include the extension file's directory, so helper modules first imported in a later
    rebuild are already watched. Keep globs unexpanded, so the preview can observe files
    created or matched after the first build.

    Parameters
    ----------
    entry_path
        The extension file.
    imported_paths
        The helper modules the extension imported from the project.
    declared_inputs
        The absolute files, directories or globs the extension declared.

    Returns
    -------
    :
        The paths without repeats: the extension file's directory, the helper modules in
        sorted order, then the declarations in order.
    """
    paths = [entry_path.parent, *sorted(imported_paths), *declared_inputs]
    return tuple(dict.fromkeys(paths))


def fingerprint(
    entry_path: Path,
    imported_paths: Iterable[Path],
    declared_inputs: Iterable[Path],
    file_hashes: dict[Path, str],
) -> str:
    """
    Hash the extension's source files and declared inputs as they are now

    Parameters
    ----------
    entry_path
        The extension file.
    imported_paths
        The helper modules the extension imported from the project, including those
        first imported during rendering.
    declared_inputs
        Absolute file, directory or glob declarations, including missing inputs.
    file_hashes
        File digests cached for this operation. A later operation must pass a new
        mapping, or an edited file would keep its old digest.

    Returns
    -------
    :
        A deterministic SHA-256 digest of each input's path, kind and file contents.
    """
    records: list[tuple[str, str, str]] = []
    sources = {entry_path, *imported_paths}
    for source in sorted(sources):
        _record_path(source, records, file_hashes)
    for declared in sorted(set(declared_inputs)):
        pattern = str(declared)
        if glob.has_magic(pattern):
            matches = sorted(Path(path) for path in glob.glob(pattern, recursive=True))
            records.append(("glob", pattern, json.dumps([str(path) for path in matches])))
            for match in matches:
                _record_path(match, records, file_hashes)
        else:
            records.append(("declared", pattern, ""))
            _record_path(declared, records, file_hashes)
    data = json.dumps(records, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _record_path(
    path: Path, records: list[tuple[str, str, str]], file_hashes: dict[Path, str]
) -> None:
    """
    Record a file, a missing input or a directory tree, including empty directories

    Parameters
    ----------
    path
        The input to record.
    records
        The fingerprint records. Receives the records for this input.
    file_hashes
        File digests cached for this operation. Receives the digests this call computes.
    """
    if path.is_file():
        digest = file_hashes.get(path)
        if digest is None:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            file_hashes[path] = digest
        records.append(("file", str(path), digest))
    elif path.is_dir():
        records.append(("directory", str(path), ""))
        for child in sorted(path.rglob("*")):
            if child.is_file():
                _record_path(child, records, file_hashes)
            elif child.is_dir():
                records.append(("directory", str(child), ""))
    else:
        records.append(("missing", str(path), ""))
