"""
Shared preview identity, selectors and local serving
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from great_docs._build import preview as shared_preview
from great_docs._build import preview_artifacts as pa
from great_docs._build import serve
from great_docs._build.repo_hosts import github_preview as pp
from great_docs._build.repo_hosts import gitlab_preview as gl
from great_docs.cli import preview


class _FakeServer:
    def __init__(self, addr, handler):
        pass

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass


def _patch_server(monkeypatch):
    import http.server

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", _FakeServer)


def test_serve_deep_link_target(monkeypatch, tmp_path, capsys):
    (tmp_path / "index.html").write_text("<html>home</html>")
    sub = tmp_path / "reference"
    sub.mkdir()
    (sub / "page.html").write_text("<html>page</html>")

    _patch_server(monkeypatch)
    serve.site(
        tmp_path, port=45999, open_path="reference/page.html", open_browser=False, report=print
    )
    out = capsys.readouterr().out
    assert "Opening: http://localhost:45999/reference/page.html" in out


def test_serve_missing_page_warns(monkeypatch, tmp_path, capsys):
    (tmp_path / "index.html").write_text("<html>home</html>")

    _patch_server(monkeypatch)
    serve.site(
        tmp_path, port=45998, open_path="does/not/exist.html", open_browser=False, report=print
    )
    out = capsys.readouterr().out
    assert "not found" in out
    assert "Opening:" not in out


def test_cli_mutually_exclusive_sources():
    result = CliRunner().invoke(preview, ["--pr", "1", "--branch", "main"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


def test_cli_dispatches_to_preview_pr(monkeypatch):
    captured = {}

    def fake_preview_pr(project_path, **kwargs):
        captured["project_path"] = project_path
        captured.update(kwargs)

    monkeypatch.setattr(pp, "preview_pr", fake_preview_pr)

    result = CliRunner().invoke(
        preview,
        ["--run", "18273645521", "--no-open", "--path", "reference/index.html", "--use-gh"],
    )
    assert result.exit_code == 0, result.output
    assert captured["run"] == 18273645521
    assert captured["open_browser"] is False
    assert captured["path"] == "reference/index.html"
    assert captured["use_gh"] is True


def test_cli_preview_pr_error_exits(monkeypatch):
    def boom(project_path, **kwargs):
        raise pa.PreviewError("no docs run found")

    monkeypatch.setattr(pp, "preview_pr", boom)
    result = CliRunner().invoke(preview, ["--pr", "999"])
    assert result.exit_code == 1
    assert "no docs run found" in result.output


def test_cli_clear_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    (pa.cache_root() / "posit-dev-great-docs").mkdir(parents=True)
    result = CliRunner().invoke(preview, ["--clear-cache"])
    assert result.exit_code == 0
    assert "Cleared PR-preview cache" in result.output
    assert not pa.cache_root().exists()


@pytest.mark.parametrize("project", ["team/subteam/package", "other/project"])
def test_gitlab_configured_prefix_survives_explicit_project_override(
    tmp_path: Path, project: str
) -> None:
    (tmp_path / "great-docs.yml").write_text(
        "repo: https://code.example/gitlab/team/subteam/package\nrepo_provider: gitlab\nrepo_base_url: https://code.example/gitlab\n"
    )
    selected = shared_preview.resolve_repository(tmp_path, f"https://code.example/gitlab/{project}")
    assert selected.provider == "gitlab" and selected.path == project
    assert selected.base_url == "https://code.example/gitlab"
    other = shared_preview.resolve_repository(tmp_path, "https://github.com/owner/repo")
    assert other.provider == "github" and other.path == "owner/repo"


@pytest.mark.parametrize(
    "flags",
    [
        ["--mr", "1", "--run", "2"],
        ["--job", "1", "--pipeline", "2"],
        ["--job", "1", "--provider", "github"],
        ["--branch", "main", "--provider", "gitlab"],
        ["--mr", "1", "--use-gh"],
    ],
)
def test_cli_gitlab_rejects_incompatible_selectors(flags: list[str]) -> None:
    result = CliRunner().invoke(preview, flags)
    assert result.exit_code == 1 and "Error:" in result.output


def test_cli_gitlab_dispatches_without_github(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        gl, "preview_gitlab", lambda project_path, **kwargs: captured.update(kwargs)
    )
    result = CliRunner().invoke(
        preview,
        [
            "--job",
            "42",
            "--repo",
            "https://code.example/gitlab/team/package",
            "--provider",
            "gitlab",
            "--repo-base-url",
            "https://code.example/gitlab",
            "--no-open",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["job"] == 42 and captured["repo_base_url"] == "https://code.example/gitlab"
    assert captured["open_browser"] is False


def test_gitlab_scp_username_preserves_configured_instance(tmp_path: Path) -> None:
    (tmp_path / "great-docs.yml").write_text(
        "repo: https://code.example/gitlab/team/package\nrepo_provider: gitlab\nrepo_base_url: https://code.example/gitlab\n"
    )
    selected = shared_preview.resolve_repository(tmp_path, "sshuser@code.example:other/project.git")
    assert selected.path == "other/project" and selected.base_url == "https://code.example/gitlab"
    with pytest.raises(pa.PreviewError):
        shared_preview.repository_from_input("group/repo:malformed", provider="gitlab")
