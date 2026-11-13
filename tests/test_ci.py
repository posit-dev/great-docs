"""Tests for the `great-docs ci` helpers (log notice + sticky PR comment)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from great_docs._build import ci as _ci
from great_docs._build.pr_preview import PreviewError
from great_docs.cli import cli

# ---------------------------------------------------------------------------
# Message rendering
# ---------------------------------------------------------------------------


def test_render_preview_comment_structure():
    body = _ci.render_preview_comment(123, 302)
    assert body.startswith(_ci.PREVIEW_COMMENT_MARKER)
    assert "great-docs preview --run 123" in body
    assert "great-docs preview --pr 302" in body
    assert "<details>" in body and "</details>" in body
    assert "<summary>Auth &amp; tips</summary>" in body


def test_render_notice_lines_with_pr():
    lines = _ci.render_notice_lines(123, 302)
    assert lines[0].startswith("::notice title=Preview these docs locally::")
    joined = "\n".join(lines)
    assert "great-docs preview --run 123" in joined
    assert "great-docs preview --pr 302" in joined


def test_render_notice_lines_without_pr():
    joined = "\n".join(_ci.render_notice_lines(123, None))
    assert "great-docs preview --run 123" in joined
    assert "--pr" not in joined


# ---------------------------------------------------------------------------
# Repo / token resolution
# ---------------------------------------------------------------------------


def test_resolve_ci_repo_override():
    assert _ci.resolve_ci_repo("posit-dev/great-docs") == ("posit-dev", "great-docs")


def test_resolve_ci_repo_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "posit-dev/great-docs")
    assert _ci.resolve_ci_repo(None) == ("posit-dev", "great-docs")


def test_github_token_missing_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(PreviewError, match="GITHUB_TOKEN"):
        _ci._github_token()


# ---------------------------------------------------------------------------
# Sticky comment upsert (mocked requests)
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status_code=200, payload=None, links=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.links = links or {}

    def json(self):
        return self._payload


def test_upsert_creates_when_absent(monkeypatch):
    calls = {}

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(200, payload=[{"id": 1, "body": "unrelated"}])

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] = (url, json)
        return _FakeResp(201)

    def fake_patch(url, headers=None, json=None, timeout=None):
        calls["patch"] = True
        return _FakeResp(200)

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "patch", fake_patch)

    action = _ci.upsert_pr_comment("o", "r", 302, "hello", "tok")
    assert action == "created"
    assert "post" in calls and "patch" not in calls
    assert "/issues/302/comments" in calls["post"][0]


def test_upsert_updates_when_present(monkeypatch):
    calls = {}
    existing = [{"id": 99, "body": f"prev {_ci.PREVIEW_COMMENT_MARKER}"}]

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(200, payload=existing)

    def fake_patch(url, headers=None, json=None, timeout=None):
        calls["patch"] = url
        return _FakeResp(200)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] = url
        return _FakeResp(201)

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "patch", fake_patch)
    monkeypatch.setattr(requests, "post", fake_post)

    action = _ci.upsert_pr_comment("o", "r", 302, "hello", "tok")

    assert action == "updated"
    assert "post" not in calls
    assert "/issues/comments/99" in calls["patch"]


def test_upsert_follows_pagination(monkeypatch):
    # First page has no marker but a next link; second page has the marker.
    page1 = _FakeResp(
        200,
        payload=[{"id": 1, "body": "nope"}],
        links={"next": {"url": "https://api.github.com/next-page"}},
    )
    page2 = _FakeResp(200, payload=[{"id": 42, "body": _ci.PREVIEW_COMMENT_MARKER}])
    responses = iter([page1, page2])
    patched = {}

    def fake_get(url, headers=None, timeout=None):
        return next(responses)

    def fake_patch(url, headers=None, json=None, timeout=None):
        patched["url"] = url
        return _FakeResp(200)

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "patch", fake_patch)

    action = _ci.upsert_pr_comment("o", "r", 302, "hello", "tok")

    assert action == "updated"
    assert "/issues/comments/42" in patched["url"]


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def test_cli_ci_notice_outputs_commands():
    result = CliRunner().invoke(cli, ["ci", "notice", "--run", "123", "--pr", "302"])

    assert result.exit_code == 0
    assert "::notice" in result.output
    assert "great-docs preview --run 123" in result.output
    assert "great-docs preview --pr 302" in result.output


def test_cli_ci_pr_comment_dispatch(monkeypatch):
    captured = {}

    def fake_post(run_id, pr, repo_override=None):
        captured.update(run_id=run_id, pr=pr, repo=repo_override)
        return "created", "posit-dev/great-docs"

    monkeypatch.setattr(_ci, "post_preview_comment", fake_post)
    result = CliRunner().invoke(
        cli, ["ci", "pr-comment", "--run", "123", "--pr", "302", "--repo", "posit-dev/great-docs"]
    )

    assert result.exit_code == 0, result.output
    assert captured == {"run_id": 123, "pr": 302, "repo": "posit-dev/great-docs"}
    assert "Created preview comment on posit-dev/great-docs#302" in result.output


def test_cli_ci_pr_comment_error_exits(monkeypatch):
    def boom(run_id, pr, repo_override=None):
        raise PreviewError("no token")

    monkeypatch.setattr(_ci, "post_preview_comment", boom)
    result = CliRunner().invoke(cli, ["ci", "pr-comment", "--run", "1", "--pr", "2"])

    assert result.exit_code == 1
    assert "no token" in result.output


# ---------------------------------------------------------------------------
# Coverage: resolve_ci_repo edge cases
# ---------------------------------------------------------------------------


def test_resolve_ci_repo_unparseable_override():
    """Raises when override is present but not parseable."""
    with pytest.raises(PreviewError, match="Could not parse --repo"):
        _ci.resolve_ci_repo("not-a-valid-repo-spec!!!")


def test_resolve_ci_repo_falls_through_to_resolve_repo(monkeypatch):
    """No override and no GITHUB_REPOSITORY → delegates to resolve_repo."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    import great_docs._build.pr_preview as _pr_preview

    monkeypatch.setattr(
        _pr_preview, "resolve_repo", lambda _a, _b: ("fallback-owner", "fallback-repo")
    )

    assert _ci.resolve_ci_repo(None) == ("fallback-owner", "fallback-repo")


# ---------------------------------------------------------------------------
# Coverage: _github_token success
# ---------------------------------------------------------------------------


def test_github_token_success(monkeypatch):
    """Returns stripped token when present."""
    monkeypatch.setenv("GITHUB_TOKEN", "  ghp_abc123  ")

    assert _ci._github_token() == "ghp_abc123"


# ---------------------------------------------------------------------------
# Coverage: _find_existing_comment error
# ---------------------------------------------------------------------------


def test_find_existing_comment_non_200_raises(monkeypatch):
    """Raises PreviewError on non-200 from comments API."""
    import requests

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(403)

    monkeypatch.setattr(requests, "get", fake_get)
    headers = {"Authorization": "Bearer tok"}
    with pytest.raises(PreviewError, match="Could not list PR comments"):
        _ci._find_existing_comment("o", "r", 1, headers)


# ---------------------------------------------------------------------------
# Coverage: upsert_pr_comment error paths
# ---------------------------------------------------------------------------


def test_upsert_request_exception_raises(monkeypatch):
    """RequestException during post/patch is wrapped."""
    import requests

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(200, payload=[])

    def fake_post(url, headers=None, json=None, timeout=None):
        raise requests.RequestException("connection reset")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(PreviewError, match="Failed to post PR comment"):
        _ci.upsert_pr_comment("o", "r", 1, "body", "tok")


def test_upsert_bad_status_raises(monkeypatch):
    """Non-200/201 response raises PreviewError."""
    import requests

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(200, payload=[])

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp(422)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(PreviewError, match="Failed to creat.* PR comment"):
        _ci.upsert_pr_comment("o", "r", 1, "body", "tok")


# ---------------------------------------------------------------------------
# Coverage: post_preview_comment integration
# ---------------------------------------------------------------------------


def test_post_preview_comment_full_flow(monkeypatch):
    """Exercises the full post_preview_comment orchestration."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/docs")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")

    import requests

    def fake_get(url, headers=None, timeout=None):
        return _FakeResp(200, payload=[])

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp(201)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    action, slug = _ci.post_preview_comment(run_id=999, pr=42)

    assert action == "created"
    assert slug == "acme/docs"


def test_gitlab_ci_override_reports_unsupported() -> None:
    with pytest.raises(PreviewError, match="Use ci mr-comment"):
        _ci.resolve_ci_repo("https://gitlab.com/group/project")


from pathlib import Path
from typing import Any

import requests

from great_docs._build import gitlab_ci as glci
from great_docs._project.repository import Repository


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
    assert body.startswith(_ci.PREVIEW_COMMENT_MARKER)
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
    from tests.test_pr_preview import _GitLabResponse

    repository = Repository("gitlab", "https://code.example/gitlab", "team/subteam", "package")
    responses = iter(
        [
            _GitLabResponse([{"id": 1, "body": "unrelated"}], headers={"X-Next-Page": "2"}),
            _GitLabResponse([{"id": 99, "body": _ci.PREVIEW_COMMENT_MARKER}]),
        ]
    )
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(url: str, **kwargs: Any) -> _GitLabResponse:
        calls.append(("get", url, kwargs))
        return next(responses)

    def put(url: str, **kwargs: Any) -> _GitLabResponse:
        calls.append(("put", url, kwargs))
        return _GitLabResponse(status=200)

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
    from tests.test_pr_preview import _GitLabResponse

    repository = Repository("gitlab", "https://gitlab.com", "team", "package")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: _GitLabResponse([]))
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _GitLabResponse(status=201))
    assert glci.upsert_mr_comment(repository, 7, "body", "token") == "created"
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _GitLabResponse(status=403))
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
