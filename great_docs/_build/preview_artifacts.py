"""
Local caches and safe extraction for CI documentation archives
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol


class PreviewError(Exception):
    """A preview failure that the CLI can explain without a traceback"""


class StreamResponse(Protocol):
    """A response body available as byte chunks"""

    def iter_content(self, chunk_size: int) -> Iterator[bytes]: ...


def stream_to_file(
    resp: StreamResponse, zip_path: Path, total: int, mode: str = "wb", start: int = 0
) -> None:
    """Write response bytes and show known-size progress on interactive terminals"""
    chunk_size = 1 << 16
    if total > 0 and sys.stderr.isatty():
        import click

        with (
            zip_path.open(mode) as handle,
            click.progressbar(length=total, label="→ Downloading", file=sys.stderr) as bar,
        ):
            if start:
                bar.update(start)
            for chunk in resp.iter_content(chunk_size=chunk_size):
                _ = handle.write(chunk)
                bar.update(len(chunk))
    else:
        with zip_path.open(mode) as handle:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                _ = handle.write(chunk)


def cache_root() -> Path:
    """Locate the existing CI-preview cache for this platform"""
    if env := os.environ.get("XDG_CACHE_HOME"):
        base = Path(env)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path.home() / ".cache"
    return base / "great-docs" / "pr-preview"


def safe_extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract regular ZIP members after rejecting unsafe paths and symbolic links"""
    dest = dest.resolve()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                name = member.filename
                path = PurePosixPath(name)
                windows = PureWindowsPath(name)
                target = (dest / name).resolve()
                mode = member.external_attr >> 16
                if (
                    path.is_absolute()
                    or windows.drive
                    or "\\" in name
                    or ".." in path.parts
                    or not target.is_relative_to(dest)
                    or stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                ):
                    raise PreviewError(f"Refusing to extract unsafe path from artifact: {name!r}")
            archive.extractall(dest)
    except (zipfile.BadZipFile, OSError) as error:
        raise PreviewError("Could not extract the downloaded artifact ZIP archive.") from error


def find_site_root(base: Path) -> Path | None:
    """Find the shallowest directory containing an extracted index.html"""
    if (base / "index.html").is_file():
        return base
    candidates = sorted(base.rglob("index.html"), key=lambda p: len(p.relative_to(base).parts))
    return candidates[0].parent if candidates else None


def cached_site(dest: Path, download: Callable[[Path], None], *, refresh: bool = False) -> Path:
    """Reuse a complete site cache or download and validate its replacement"""
    marker = dest / ".gd-complete"
    if not refresh and marker.is_file() and (root := find_site_root(dest)) is not None:
        print("→ Using cached download")
        return root
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    complete = False
    try:
        download(dest)
        root = find_site_root(dest)
        if root is None:
            raise PreviewError(
                "The downloaded artifact does not contain an index.html; is this a docs site?"
            )
        _ = marker.write_text("ok\n", encoding="utf-8")
        complete = True
        return root
    finally:
        if not complete:
            marker.unlink(missing_ok=True)
