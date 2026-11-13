"""
GitLab CI notices and preview comments
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import requests
from click.testing import CliRunner

from great_docs._build import gitlab_ci as glci
from great_docs._build import preview as shared_preview
from great_docs._build.preview_artifacts import PreviewError
from great_docs._project.repository import Repository
from great_docs.cli import cli


def test_gitlab_notice_has_copyable_full_identities_and_prefix() -> None:
    target = Repository("gitlab", "https://code.example/gitlab", "team/subteam", "package")
    source = Repository("gitlab", target.base_url, "contributor", "package")
    lines = glci.render_notice_lines(target, source, job=42, mr=7)
    joined = "\n".join(lines)
    assert "::notice" not in joined
    assert "--repo https://code.example/gitlab/contributor/package" in lines[1]
    assert "--job 42" in lines[1]
    assert "--repo https://code.example/gitlab/team/subteam/package" in lines[2]
    assert "--mr 7" in lines[2]
    assert all("--repo-base-url https://code.example/gitlab" in line for line in lines[1:3])
    body = glci.render_preview_comment(target, source, mr=7, job=42)
    assert body.startswith(shared_preview.PREVIEW_COMMENT_MARKER)
    assert lines[1] in body and lines[2] in body


def test_gitlab_ci_uses_authoritative_api_prefix_and_actual_mr_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_API_V4_URL", "https://code.example/gitlab/api/v4")
    monkeypatch.setenv("CI_PROJECT_URL", "https://code.example/gitlab/contributor/package")
    monkeypatch.setenv(
        "CI_MERGE_REQUEST_PROJECT_URL", "https://code.example/gitlab/team/subteam/package"
    )
    target, source = glci.resolve_ci_repositories(None, None, None)
    assert target.path == "team/subteam/package" and source.path == "contributor/package"
    assert target.base_url == source.base_url == "https://code.example/gitlab"


def test_gitlab_ci_explicit_target_retains_fork_artifact_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI_PROJECT_URL", "https://gitlab.com/unrelated/project")
    monkeypatch.delenv("CI_API_V4_URL", raising=False)
    target, source = glci.resolve_ci_repositories("https://gitlab.com/team/package", None, None)
    assert target.path == "team/package" and source.path == "unrelated/project"


def test_gitlab_notes_page_and_update_with_put(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.support import GitLabResponse

    repository = Repository("gitlab", "https://code.example/gitlab", "team/subteam", "package")
    responses = iter(
        [
            GitLabResponse([{"id": 1, "body": "unrelated"}], headers={"X-Next-Page": "2"}),
            GitLabResponse([{"id": 99, "body": shared_preview.PREVIEW_COMMENT_MARKER}]),
        ]
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(url: str, **kwargs: Any) -> GitLabResponse:
        calls.append(("get", url, kwargs))
        return next(responses)

    def put(url: str, **kwargs: Any) -> GitLabResponse:
        calls.append(("put", url, kwargs))
        return GitLabResponse(status=200)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "put", put)
    monkeypatch.setattr(
        requests, "post", lambda *args, **kwargs: pytest.fail("Existing note must use PUT")
    )
    assert glci.upsert_mr_comment(repository, 7, "updated body", "write-token") == "updated"
    assert [item[2]["params"]["page"] for item in calls[:2]] == [1, 2]
    assert (
        calls[-1][1]
        == "https://code.example/gitlab/api/v4/projects/team%2Fsubteam%2Fpackage/merge_requests/7/notes/99"
    )
    assert calls[-1][2]["json"] == {"body": "updated body"}
    assert all(item[2]["allow_redirects"] is False for item in calls)
    assert all(item[2]["headers"]["PRIVATE-TOKEN"] == "write-token" for item in calls)


def test_gitlab_notes_create_and_reject_write_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.support import GitLabResponse

    repository = Repository("gitlab", "https://gitlab.com", "team", "package")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: GitLabResponse([]))
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: GitLabResponse(status=201))
    assert glci.upsert_mr_comment(repository, 7, "body", "token") == "created"
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: GitLabResponse(status=403))
    with pytest.raises(PreviewError, match="write permissions"):
        glci.upsert_mr_comment(repository, 7, "body", "token")


def test_gitlab_note_never_falls_back_to_ci_job_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    monkeypatch.setenv("CI_JOB_TOKEN", "must-not-write")
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("Missing write token must fail before network"),
    )
    with pytest.raises(PreviewError, match="CI_JOB_TOKEN cannot write"):
        glci.post_preview_comment(mr=7, job=42, repo="https://gitlab.com/team/package")


def test_cli_gitlab_notice_and_comment_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CliRunner().invoke(
        cli,
        [
            "ci",
            "gitlab-notice",
            "--job",
            "42",
            "--mr",
            "7",
            "--repo",
            "https://gitlab.com/team/package",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "--job 42" in result.output and "--mr 7" in result.output
    assert "::notice" not in result.output
    captured: dict[str, Any] = {}

    def post(**kwargs: Any) -> tuple[str, str]:
        captured.update(kwargs)
        return "updated", "https://gitlab.com/team/package"

    monkeypatch.setattr(glci, "post_preview_comment", post)
    result = CliRunner().invoke(
        cli,
        [
            "ci",
            "mr-comment",
            "--job",
            "42",
            "--mr",
            "7",
            "--repo",
            "https://gitlab.com/team/package",
            "--artifact-repo",
            "https://gitlab.com/fork/package",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["mr"] == 7 and captured["job"] == 42
    assert captured["artifact_repo"] == "https://gitlab.com/fork/package"


def test_generated_gitlab_hooks_are_opt_in_and_preserve_configured_prefix(tmp_path: Path) -> None:
    import yaml

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    (tmp_path / "great-docs.yml").write_text(
        "repo: https://code.example/gitlab/team/subteam/package\nrepo_provider: gitlab\nrepo_base_url: https://code.example/gitlab\n"
    )
    result = CliRunner().invoke(
        cli, ["setup-gitlab-pages", "--project-path", str(tmp_path), "--package-manager", "poetry"]
    )
    assert result.exit_code == 0, result.output
    pipeline = yaml.safe_load((tmp_path / ".gitlab-ci.yml").read_text())
    preview = pipeline["great-docs-preview"]
    hook = preview["after_script"][0]
    assert '"${GREAT_DOCS_MR_COMMENT:-false}" = true' in hook
    assert "poetry run great-docs ci mr-comment" in hook
    assert "--repo-base-url https://code.example/gitlab" in hook
    assert (
        hook.index("gitlab-notice")
        < hook.index("GREAT_DOCS_MR_COMMENT")
        < hook.index("ci mr-comment")
    )
    assert preview["artifacts"]["name"] == "docs-html"
    assert "pages" not in preview


@pytest.mark.parametrize("selectors", [[], ["--job", "42", "--pipeline", "77"]])
def test_gitlab_ci_rejects_missing_or_multiple_build_selectors_before_post(
    monkeypatch: pytest.MonkeyPatch, selectors: list[str]
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "write-token")
    monkeypatch.delenv("CI_API_V4_URL", raising=False)
    monkeypatch.delenv("CI_PROJECT_URL", raising=False)
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: pytest.fail("Invalid selectors must not reach notes API"),
    )
    result = CliRunner().invoke(
        cli,
        ["ci", "mr-comment", "--mr", "7", "--repo", "https://gitlab.com/team/package", *selectors],
    )
    assert result.exit_code == 1 and "exactly one" in result.output
