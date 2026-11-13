"""
Shared preview caches and archive handling
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from great_docs._build import preview_artifacts as pa


def test_safe_extract_zip_normal(tmp_path):
    zip_path = tmp_path / "site.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("index.html", "<html>hi</html>")
        zf.writestr("reference/index.html", "<html>ref</html>")
    dest = tmp_path / "out"
    dest.mkdir()
    pa.safe_extract_zip(zip_path, dest)
    assert (dest / "index.html").is_file()
    assert (dest / "reference" / "index.html").is_file()


def test_safe_extract_zip_rejects_zip_slip(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(pa.PreviewError, match="unsafe path"):
        pa.safe_extract_zip(zip_path, dest)
    assert not (tmp_path / "escape.txt").exists()


def test_find_site_root_at_root(tmp_path):
    (tmp_path / "index.html").write_text("x")
    assert pa.find_site_root(tmp_path) == tmp_path


def test_find_site_root_nested(tmp_path):
    nested = tmp_path / "_site"
    nested.mkdir()
    (nested / "index.html").write_text("x")
    assert pa.find_site_root(tmp_path) == nested


def test_find_site_root_missing(tmp_path):
    assert pa.find_site_root(tmp_path) is None


class _FakeResponse:
    """Minimal stand-in for a streaming requests.Response."""

    def __init__(self, chunks):
        self._chunks = chunks

    def iter_content(self, chunk_size=None):
        yield from self._chunks


def test_stream_to_file_writes_all_bytes(tmp_path):
    dest = tmp_path / "out.zip"
    resp = _FakeResponse([b"abc", b"def", b"ghi"])
    pa.stream_to_file(resp, dest, total=9)
    assert dest.read_bytes() == b"abcdefghi"


def test_stream_to_file_unknown_length(tmp_path):
    # total == 0 (no Content-Length) should still write the file, just without a bar.
    dest = tmp_path / "out.zip"
    resp = _FakeResponse([b"x" * 100])
    pa.stream_to_file(resp, dest, total=0)
    assert dest.read_bytes() == b"x" * 100


def test_stream_to_file_progress_bar_path(monkeypatch, tmp_path):
    # Force the TTY branch and stub click.progressbar to verify wiring (writes
    # the file and advances the bar) without depending on terminal rendering.
    import click

    class _FakeTTY:
        def isatty(self):
            return True

        def write(self, *a):
            pass

        def flush(self):
            pass

    updates: list[int] = []

    class _FakeBar:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, n):
            updates.append(n)

    monkeypatch.setattr(pa.sys, "stderr", _FakeTTY())
    monkeypatch.setattr(click, "progressbar", lambda **kwargs: _FakeBar())

    dest = tmp_path / "out.zip"
    pa.stream_to_file(_FakeResponse([b"aa", b"bb"]), dest, total=4)
    assert dest.read_bytes() == b"aabb"
    assert sum(updates) == 4


def test_clear_cache_removes_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    root = pa.cache_root()
    (root / "posit-dev-great-docs" / "42" / "docs-html").mkdir(parents=True)
    existed, path = pa.clear_cache()
    assert existed is True
    assert path == root
    assert not root.exists()


def test_cache_root_win32(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pa.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = pa.cache_root()
    assert result == tmp_path / "great-docs" / "pr-preview"


def test_cache_root_linux(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pa.sys, "platform", "linux")
    result = pa.cache_root()
    assert result == Path.home() / ".cache" / "great-docs" / "pr-preview"


def test_cache_root_darwin(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pa.sys, "platform", "darwin")
    result = pa.cache_root()
    assert result == Path.home() / "Library" / "Caches" / "great-docs" / "pr-preview"


def test_stream_to_file_resume_mode(monkeypatch, tmp_path):
    import click

    class _FakeTTY:
        def isatty(self):
            return True

        def write(self, *a):
            pass

        def flush(self):
            pass

    updates = []

    class _FakeBar:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, n):
            updates.append(n)

    monkeypatch.setattr(pa.sys, "stderr", _FakeTTY())
    monkeypatch.setattr(click, "progressbar", lambda **kwargs: _FakeBar())

    dest = tmp_path / "out.zip"
    dest.write_bytes(b"xx")  # pre-existing bytes
    resp = _FakeResponse([b"yy"])
    pa.stream_to_file(resp, dest, total=4, mode="ab", start=2)
    assert dest.read_bytes() == b"xxyy"

    # start=2 causes initial bar.update(2), then chunk update(2)
    assert updates == [2, 2]


@pytest.mark.parametrize(
    "name",
    ["/absolute.txt", "C:/escape.txt", "C:escape.txt", "..\\escape.txt", "dir/../../escape.txt"],
)
def test_shared_archive_rejects_platform_specific_unsafe_paths(tmp_path: Path, name: str) -> None:
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr(name, "unsafe")
    with pytest.raises(pa.PreviewError, match="unsafe path"):
        pa.safe_extract_zip(archive, tmp_path / "site")


def test_shared_archive_rejects_symbolic_links(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    member = zipfile.ZipInfo("link")
    member.create_system = 3
    member.external_attr = 0o120777 << 16
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr(member, "../outside")
    with pytest.raises(pa.PreviewError, match="unsafe path"):
        pa.safe_extract_zip(archive, tmp_path / "site")


def test_failed_cache_population_cannot_forge_completion(tmp_path: Path) -> None:
    calls = 0

    def download(dest: Path) -> None:
        nonlocal calls
        calls += 1
        (dest / ".gd-complete").write_text("forged")
        (dest / "index.html").write_text("partial")
        if calls == 1:
            raise pa.PreviewError("interrupted")
        (dest / "index.html").write_text("complete")

    with pytest.raises(pa.PreviewError, match="interrupted"):
        pa.cached_site(tmp_path / "cache", download)
    assert not (tmp_path / "cache/.gd-complete").exists()
    root = pa.cached_site(tmp_path / "cache", download)
    assert calls == 2 and (root / "index.html").read_text() == "complete"
