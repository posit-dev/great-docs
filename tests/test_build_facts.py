"""
Tests for GitHub data fetched once per documentation build
"""

from __future__ import annotations

from pathlib import Path

from great_docs import GreatDocs
from great_docs._build.facts import Facts
from great_docs._github import GithubRepo
from great_docs._website.navigation.release import Release
from tests.support import StubRemote, make_run, mock_config, write_config

REPO = GithubRepo(owner="owner", name="repo")
RELEASE = {"tag_name": "v1.2.0", "published_at": "2025-06-15T10:00:00Z"}


def test_without_a_repository_nothing_is_fetched():
    remote = StubRemote(stats={"stars": 5, "forks": 1}, releases=[RELEASE])

    facts = Facts.make(mock_config(github_style="widget"), None, remote)

    assert facts == Facts()
    assert remote.calls == []


def test_the_widget_style_fetches_counts_and_the_latest_release():
    remote = StubRemote(stats={"stars": 5, "forks": 1}, releases=[RELEASE])

    facts = Facts.make(mock_config(github_style="widget"), REPO, remote)

    assert facts == Facts(
        github_stats={"stars": 5, "forks": 1},
        latest_release=Release(version="1.2.0", date="2025-06-15"),
    )
    assert remote.calls == ["github_stats", "github_releases"]


def test_the_icon_style_fetches_only_the_latest_release():
    remote = StubRemote(stats={"stars": 5, "forks": 1})

    facts = Facts.make(mock_config(github_style="icon"), REPO, remote)

    assert facts == Facts()
    assert remote.calls == ["github_releases"]


def test_both_configuration_passes_of_a_build_share_one_fetch(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n\n[project.urls]\nRepository = "https://github.com/owner/repo"\n',
        encoding="utf-8",
    )
    _ = write_config(tmp_path)
    docs = GreatDocs(project_path=str(tmp_path))
    docs._remote = remote = StubRemote(releases=[RELEASE])
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(
        "project:\n  type: website\nformat:\n  html: {}\n", encoding="utf-8"
    )
    run = make_run()

    docs._update_quarto_config(run)
    docs._update_quarto_config(run)

    assert remote.calls == ["github_stats", "github_releases"]
