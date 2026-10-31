from pathlib import Path
from typing import Any

import pytest

from great_docs._contribution import Contribution, NavbarLink
from great_docs._github import GithubRepo
from great_docs._website import changelog
from tests.support import StubRemote, write_config

REPO = GithubRepo("owner", "repo")


def _release(
    tag: str, body: str = "", *, prerelease: bool = False, name: str = ""
) -> dict[str, Any]:
    """
    Create a release in the format returned by `Remote.github_releases`

    Parameters
    ----------
    tag
        The release's tag.
    body
        The release notes.
    prerelease
        Whether the release is a pre-release.
    name
        The release title; GitHub returns an empty title when none is set.

    Returns
    -------
    :
        The release, published on 2026-01-01.
    """
    return {
        "tag_name": tag,
        "name": name,
        "body": body,
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/owner/repo/releases/tag/{tag}",
        "prerelease": prerelease,
    }


def _page(build_dir: Path) -> str:
    """
    Read the changelog page

    Parameters
    ----------
    build_dir
        The directory the page was written into.

    Returns
    -------
    :
        The page's text.
    """
    return (build_dir / "changelog.qmd").read_text(encoding="utf-8")


def test_write_page_lists_each_release(tmp_path: Path):
    config = write_config(tmp_path)
    remote = StubRemote(
        releases=[
            _release("v2.0.0rc1", "Notes for #3.", prerelease=True, name="Version 2"),
            _release("v1.0.0"),
        ]
    )
    reported: list[str] = []

    contribution = changelog.write_page(config, tmp_path, REPO, remote, report=reported.append)

    assert contribution == Contribution(navbar=(NavbarLink("Changelog", "changelog.qmd"),))
    assert reported == [f"Created {tmp_path / 'changelog.qmd'}"]
    assert _page(tmp_path) == (
        "---\n"
        'title: "Changelog"\n'
        "gd-auto-generated: true\n"
        "body-classes: gd-changelog-page\n"
        "toc: true\n"
        "toc-depth: 1\n"
        'toc-title: "Releases"\n'
        "shift-heading-level-by: -1\n"
        "---\n"
        "\n"
        "This changelog is generated automatically from \n"
        "[GitHub Releases](https://github.com/owner/repo/releases).\n"
        "\n"
        "## Version 2  {.changelog-version}\n"
        "\n"
        "*2026-01-01* · *(pre-release)* · "
        "[GitHub](https://github.com/owner/repo/releases/tag/v2.0.0rc1)\n"
        "\n"
        "Notes for [#3](https://github.com/owner/repo/issues/3).\n"
        "\n"
        "## v1.0.0  {.changelog-version}\n"
        "\n"
        "*2026-01-01* · [GitHub](https://github.com/owner/repo/releases/tag/v1.0.0)\n"
    )


def test_write_page_without_releases_writes_nothing(tmp_path: Path):
    config = write_config(tmp_path)
    reported: list[str] = []

    contribution = changelog.write_page(
        config, tmp_path, REPO, StubRemote(), report=reported.append
    )

    assert contribution is None
    assert reported == []
    assert not (tmp_path / "changelog.qmd").exists()


@pytest.mark.parametrize(("lang", "expected"), [("fr", "Versions"), ("ja", "リリース")])
def test_write_page_translates_the_toc_title(tmp_path: Path, lang: str, expected: str):
    config = write_config(tmp_path, {"site": {"lang": lang}})
    remote = StubRemote(releases=[_release("v1.0.0")])

    _ = changelog.write_page(config, tmp_path, REPO, remote, report=print)

    assert f'toc-title: "{expected}"' in _page(tmp_path)


@pytest.mark.parametrize(("max_releases", "expected"), [(None, 2), (1, 1)])
def test_write_page_limits_the_releases(tmp_path: Path, max_releases: int | None, expected: int):
    config = write_config(tmp_path, {"changelog": {"max_releases": 2}})
    remote = StubRemote(releases=[_release(f"v1.{i}") for i in range(3)])

    _ = changelog.write_page(
        config, tmp_path, REPO, remote, max_releases=max_releases, report=print
    )

    assert _page(tmp_path).count("{.changelog-version}") == expected


def test_write_page_nests_note_headings_under_the_release(tmp_path: Path):
    config = write_config(tmp_path)
    body = "# Title\n\n## Features\n\n### Detail"
    remote = StubRemote(releases=[_release("v1.0.0", body)])

    _ = changelog.write_page(config, tmp_path, REPO, remote, report=print)

    assert "# Title\n\n### Features\n\n#### Detail\n" in _page(tmp_path)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(
            "Fixed (#42) and #100.",
            "Fixed ([#42](https://github.com/owner/repo/issues/42)) and "
            "[#100](https://github.com/owner/repo/issues/100).",
            id="bare-issue",
        ),
        pytest.param(
            "See gh issue #7 and GH PR #9.",
            "See [#7](https://github.com/owner/repo/issues/7) and "
            "[#9](https://github.com/owner/repo/issues/9).",
            id="gh-prefix",
        ),
        pytest.param(
            "Thanks @some-user.",
            "Thanks [@some-user](https://github.com/some-user).",
            id="mention",
        ),
        pytest.param(
            r"\#12 by \@bob doesn\'t \"break\"",
            "[#12](https://github.com/owner/repo/issues/12) by [@bob](https://github.com/bob) "
            'doesn\'t "break"',
            id="backslash-escapes",
        ),
        pytest.param(
            "Full Changelog: https://github.com/owner/repo/compare/v1...v2",
            "Full Changelog: [https://github.com/owner/repo/compare/v1...v2]"
            "(https://github.com/owner/repo/compare/v1...v2)",
            id="compare-url",
        ),
        pytest.param("Write to user@example.com", "Write to user@example.com", id="email"),
        pytest.param(
            "[#42](https://github.com/owner/repo/issues/42)",
            "[#42](https://github.com/owner/repo/issues/42)",
            id="linked-issue",
        ),
        pytest.param(
            "[https://github.com/owner/repo/compare/v1...v2]"
            "(https://github.com/owner/repo/compare/v1...v2)",
            "[https://github.com/owner/repo/compare/v1...v2]"
            "(https://github.com/owner/repo/compare/v1...v2)",
            id="linked-compare-url",
        ),
    ],
)
def test_linkify_references(text: str, expected: str):
    assert changelog.linkify_references(text, REPO) == expected
