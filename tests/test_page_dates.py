"""Date and author metadata for copied pages"""

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from great_docs._website.page_dates import copy_portraits, head_tags, site_authors
from great_docs.config import Config
from tests.support import write_config


def _tags(source: Path, config: Config, authors: list[dict] | None = None) -> dict[str, str]:
    """
    Index a page's raw metadata tags by name

    Parameters
    ----------
    source
        The page source.
    config
        Project configuration.
    authors
        The configured authors.

    Returns
    -------
    :
        The raw tags keyed by the `name` attribute.
    """
    tags = head_tags(source, config, authors or [])
    return {tag.split('"')[1]: tag for tag in tags}


def _git(repo: Path, *args: str) -> None:
    """
    Run `git` in `repo` with a fixed identity and commit date

    Parameters
    ----------
    repo
        The repository.
    *args
        Arguments to `git`.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_AUTHOR_DATE": "2024-05-06T07:08:09+00:00",
        "GIT_COMMITTER_DATE": "2024-05-06T07:08:09+00:00",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def test_front_matter_dates_win_over_git(tmp_path: Path):
    """Preserve explicit dates and add midnight when the time is omitted"""
    page = tmp_path / "page.qmd"
    page.write_text(
        '---\ndate_created: "2025-06-01"\nlast_update:\n  date: "2026-03-15T10:30:00Z"\n---\n',
        encoding="utf-8",
    )

    tags = _tags(page, write_config(tmp_path, "show_dates: true\n"))

    assert 'content="2026-03-15T10:30:00Z"' in tags["gd-page-modified"]
    assert 'content="2025-06-01T00:00:00"' in tags["gd-page-created"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_committed_page_takes_dates_from_git(tmp_path: Path):
    """Read commit dates from the source file's repository"""
    repo = tmp_path / "repo"
    (repo / "guide").mkdir(parents=True)
    page = repo / "guide" / "page.qmd"
    page.write_text("Text\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "Add page")

    tags = _tags(page, write_config(tmp_path, "show_dates: true\n"))

    # Older Git writes UTC as `+00:00`, newer Git as `Z`
    committed = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
    for name in ("gd-page-modified", "gd-page-created"):
        content = re.search(r'content="([^"]+)"', tags[name])
        assert content is not None
        assert datetime.fromisoformat(content[1]) == committed


def test_untracked_page_takes_modified_date_from_mtime(tmp_path: Path):
    """Omit the created date for an untracked page"""
    page = tmp_path / "page.qmd"
    page.write_text("Text\n", encoding="utf-8")

    tags = _tags(page, write_config(tmp_path, "show_dates: true\n"))

    assert set(tags) == {"gd-page-modified"}


@pytest.mark.parametrize(
    ("entry", "image", "url"),
    [
        (
            {"name": "Ada", "image": "/a.png", "homepage": "https://ada.dev"},
            "/a.png",
            "https://ada.dev",
        ),
        ({"name": "Ada", "github": "ada"}, "https://github.com/ada.png", ""),
        (
            {"name": "Ada", "homepage": "https://github.com/ada"},
            "https://github.com/ada.png",
            "https://github.com/ada",
        ),
    ],
)
def test_author_details_come_from_configured_authors(
    tmp_path: Path, entry: dict, image: str, url: str
):
    """Use configured author details, with GitHub avatars as a fallback"""
    page = tmp_path / "page.qmd"
    page.write_text("---\nauthor: Ada\n---\n", encoding="utf-8")

    tags = _tags(page, write_config(tmp_path, "show_dates: true\n"), [entry])

    assert 'content="Ada"' in tags["gd-page-author"]
    assert f'content="{image}"' in tags["gd-page-author-image"]
    if url:
        assert f'content="{url}"' in tags["gd-page-author-url"]
    else:
        assert "gd-page-author-url" not in tags


def test_show_author_false_drops_author_tags(tmp_path: Path):
    page = tmp_path / "page.qmd"
    page.write_text("---\nauthor: Ada\n---\n", encoding="utf-8")
    config = write_config(tmp_path, "show_dates: true\nshow_author: false\n")

    tags = _tags(page, config, [{"name": "Ada", "github": "ada"}])

    assert not {"gd-page-author", "gd-page-author-image", "gd-page-author-url"} & set(tags)


def test_author_name_is_escaped(tmp_path: Path):
    page = tmp_path / "page.qmd"
    page.write_text("---\nauthor: 'O''Brien & \"Co\"'\n---\n", encoding="utf-8")

    tags = _tags(page, write_config(tmp_path, "show_dates: true\n"))

    assert tags["gd-page-author"] == (
        '<meta name="gd-page-author" content="O&#x27;Brien &amp; &quot;Co&quot;">'
    )


def test_show_dates_off_builds_no_tags(tmp_path: Path):
    page = tmp_path / "page.qmd"
    page.write_text("Text\n", encoding="utf-8")

    assert head_tags(page, write_config(tmp_path, "show_dates: false\n"), []) == []


def test_local_portrait_is_copied_and_addressed_on_the_site(tmp_path: Path):
    """Preserve query strings, fragments and remote portrait URLs"""
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "ada.png").write_bytes(b"png")
    config = write_config(
        tmp_path,
        "show_dates: true\nauthors:\n"
        "  - {name: Ada, image: 'img/ada.png?v=2#face'}\n"
        "  - {name: Bo, image: 'https://example.com/bo.png'}\n",
    )
    build = tmp_path / "build"

    authors = site_authors(config, tmp_path, "https://docs.example.com/")
    copy_portraits(config, tmp_path, build)

    assert [a["image"] for a in authors] == [
        "https://docs.example.com/_shared/authors/ada.png?v=2#face",
        "https://example.com/bo.png",
    ]
    assert (build / "_shared" / "authors" / "ada.png").read_bytes() == b"png"
