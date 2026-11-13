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
    with pytest.raises(PreviewError, match="GitLab CI previews are not supported"):
        _ci.resolve_ci_repo("https://gitlab.com/group/project")
