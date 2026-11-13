"""
GitLab merge-request and job artifact previews
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
import requests

from great_docs._build import gitlab_preview as gl
from great_docs._build import preview_artifacts as pa
from great_docs._build import serve
from great_docs._project.repository import Repository
from tests.support import GitLabResponse


def _gitlab_repository(
    base: str = "https://gitlab.com", namespace: str = "team/subteam"
) -> Repository:
    return Repository("gitlab", base, namespace, "package")


def _zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("docs/_site/index.html", "<html>GitLab documentation</html>")
        archive.writestr("docs/_site/reference/index.html", "<html>Reference</html>")
    return buffer.getvalue()


@pytest.mark.parametrize("field", ["PRIVATE-TOKEN", "JOB-TOKEN"])
def test_gitlab_download_strips_credentials_on_cross_origin_redirects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str
) -> None:
    client = gl.GitLabClient(
        _gitlab_repository(),
        token="secret" if field == "PRIVATE-TOKEN" else None,
        job_token="secret" if field == "JOB-TOKEN" else None,
    )
    data = _zip_bytes()
    responses = iter(
        [
            GitLabResponse(status=302, headers={"Location": "https://gitlab.com/local-redirect"}),
            GitLabResponse(
                status=302, headers={"Location": "https://cdn.example.net/archive?signature=hidden"}
            ),
            GitLabResponse(status=302, headers={"Location": "https://gitlab.com/returned-archive"}),
            GitLabResponse(chunks=[data], headers={"Content-Length": str(len(data))}),
        ]
    )
    calls: list[dict[str, Any]] = []

    def get(url: str, **kwargs: Any) -> GitLabResponse:
        calls.append({"url": url, **kwargs})
        return next(responses)

    monkeypatch.setattr(requests, "get", get)
    client.download_artifact(gl.JobArtifact("team/subteam/package", 42), tmp_path)
    assert all(call["allow_redirects"] is False for call in calls)
    assert [field in call["headers"] for call in calls] == [True, True, False, False]
    assert (tmp_path / "docs/_site/index.html").is_file()
    assert calls[0]["url"].endswith("projects/team%2Fsubteam%2Fpackage/jobs/42/artifacts")


@pytest.mark.parametrize(
    "location",
    ["http://cdn.example.net/zip", "file:///tmp/zip", "https://user:secret@cdn.example.net/zip"],
)
def test_gitlab_download_rejects_unsafe_redirects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, location: str
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: GitLabResponse(status=302, headers={"Location": location}),
    )
    with pytest.raises(pa.PreviewError, match="unsafe destination"):
        gl.GitLabClient(_gitlab_repository(), token="hidden").download_artifact(
            gl.JobArtifact("team/package", 42), tmp_path
        )


def test_gitlab_metadata_never_uses_job_token_or_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def get(url: str, **kwargs: Any) -> GitLabResponse:
        calls.append(kwargs)
        return GitLabResponse(status=302, headers={"Location": "https://foreign.example/steal"})

    monkeypatch.setattr(requests, "get", get)
    client = gl.GitLabClient(_gitlab_repository(), job_token="hidden")
    with pytest.raises(gl.GitLabAPIError, match="redirected"):
        client.get_json("projects/team%2Fpackage/jobs/42")
    assert calls[0]["allow_redirects"] is False
    assert "JOB-TOKEN" not in calls[0]["headers"]


def test_gitlab_pagination_keeps_control_of_endpoint_and_private_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    responses = iter(
        [GitLabResponse([{"id": 1}], headers={"X-Next-Page": "2"}), GitLabResponse([{"id": 2}])]
    )

    def get(url: str, **kwargs: Any) -> GitLabResponse:
        calls.append((url, kwargs))
        return next(responses)

    monkeypatch.setattr(requests, "get", get)
    client = gl.GitLabClient(
        _gitlab_repository("https://code.example/gitlab"), token="private", job_token="job"
    )
    assert client.list_json("projects/team%2Fpackage/pipelines/1/jobs") == [{"id": 1}, {"id": 2}]
    assert [call[1]["params"]["page"] for call in calls] == [1, 2]
    assert calls[0][0] == calls[1][0]
    assert calls[0][0].startswith("https://code.example/gitlab/api/v4/")
    assert calls[0][1]["headers"]["PRIVATE-TOKEN"] == "private"
    assert "JOB-TOKEN" not in calls[0][1]["headers"]


def test_gitlab_tokens_keep_provider_and_explicit_file_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GITLAB_TOKEN", "env-private")
    monkeypatch.setenv("CI_JOB_TOKEN", "env-job")
    monkeypatch.setenv("GITHUB_TOKEN", "github")
    monkeypatch.setattr(gl, "find_dotenv", lambda **kwargs: "")
    explicit = tmp_path / "explicit.env"
    explicit.write_text("GITLAB_TOKEN=file-private\nCI_JOB_TOKEN=file-job\n")
    assert gl.resolve_tokens(tmp_path, str(explicit)) == ("file-private", "file-job")
    monkeypatch.delenv("GITLAB_TOKEN")
    monkeypatch.delenv("CI_JOB_TOKEN")
    assert gl.resolve_tokens(tmp_path, None) == (None, None)
    (tmp_path / ".env").write_text("GITLAB_TOKEN=auto-private\n")
    assert gl.resolve_tokens(tmp_path, None) == ("auto-private", None)


class _GitLabClient(gl.GitLabClient):
    def __init__(self, responses: dict[str, object]) -> None:
        super().__init__(_gitlab_repository())
        self.responses = responses
        self.calls: list[str] = []

    def get_json(self, path: str, params: dict[str, str | int] | None = None) -> tuple[object, str]:
        self.calls.append(path)
        value = self.responses[path]
        if isinstance(value, gl.GitLabAPIError):
            raise value
        return value, ""


def _docs_job(
    job: int = 20, name: str = "great-docs-preview", **kwargs: object
) -> dict[str, object]:
    return {
        "id": job,
        "name": name,
        "status": "success",
        "artifacts_file": {"filename": "docs-html.zip"},
        **kwargs,
    }


def test_gitlab_direct_job_requires_no_metadata() -> None:
    client = _GitLabClient({})
    assert gl.resolve_artifact(client, job=42) == gl.JobArtifact("team/subteam/package", 42)
    assert client.calls == []


@pytest.mark.parametrize("denial", [401, 403, 404])
def test_gitlab_minimal_mr_pipeline_routes_fork_project(denial: int) -> None:
    client = _GitLabClient(
        {
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7": {
                "sha": "current",
                "target_project_id": 10,
                "source_project_id": 11,
            },
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7/pipelines": [
                {"id": 77, "sha": "current", "ref": "main", "status": "success"}
            ],
            "projects/10/pipelines/77": gl.GitLabAPIError(denial, "Unavailable candidate"),
            "projects/11/pipelines/77": {
                "id": 77,
                "project_id": 11,
                "sha": "current",
                "ref": "main",
            },
            "projects/11/pipelines/77/jobs": [_docs_job()],
        }
    )
    chosen = gl.resolve_artifact(client, mr=7)
    assert chosen.project == "11" and chosen.job_id == 20 and chosen.pipeline_id == 77
    assert client.calls[-1] == "projects/11/pipelines/77/jobs"


def test_gitlab_mr_never_uses_old_success_for_current_head() -> None:
    client = _GitLabClient(
        {
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7": {
                "sha": "current",
                "target_project_id": 10,
                "source_project_id": 10,
            },
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7/pipelines": [
                {"id": 77, "sha": "old", "ref": "main", "status": "success"},
                {
                    "id": 78,
                    "sha": "current",
                    "ref": "refs/merge-requests/7/head",
                    "status": "running",
                },
            ],
            "projects/10/pipelines/78": {"id": 78, "project_id": 10, "sha": "current"},
            "projects/10/pipelines/78/jobs": [],
        }
    )
    with pytest.raises(pa.PreviewError, match="No successful documentation artifact"):
        gl.resolve_artifact(client, mr=7)
    assert not any("/77" in path for path in client.calls)


def test_gitlab_mr_prefers_authoritative_merged_result_pipeline() -> None:
    head = {
        "id": 78,
        "project_id": 10,
        "sha": "temporary-merge",
        "ref": "refs/merge-requests/7/merge",
        "status": "success",
    }
    client = _GitLabClient(
        {
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7": {
                "sha": "source-head",
                "target_project_id": 10,
                "source_project_id": 11,
                "head_pipeline": head,
            },
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7/pipelines": [
                {"id": 77, "sha": "old", "status": "success"},
                head,
            ],
            "projects/10/pipelines/78": head,
            "projects/10/pipelines/78/jobs": [_docs_job()],
        }
    )
    assert gl.resolve_artifact(client, mr=7).pipeline_id == 78
    assert not any("/77" in path for path in client.calls)


@pytest.mark.parametrize(
    "jobs, message",
    [
        ([], "No successful"),
        ([_docs_job(1), _docs_job(2)], "Several"),
        ([_docs_job(1, artifacts_expire_at="2000-01-01T00:00:00Z")], "expired"),
    ],
)
def test_gitlab_pipeline_selection_explains_unusable_artifacts(
    jobs: list[dict[str, object]], message: str
) -> None:
    client = _GitLabClient({"projects/team%2Fsubteam%2Fpackage/pipelines/1/jobs": jobs})
    with pytest.raises(pa.PreviewError, match=message):
        gl.resolve_artifact(client, pipeline=1)


def test_gitlab_cache_separates_instance_namespace_pipeline_job_and_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    repo = _gitlab_repository()
    artifact = gl.JobArtifact(repo.path, 42, 7, "docs-html.zip")
    paths = {gl.cache_dir_for(repo, artifact)}
    paths.add(gl.cache_dir_for(_gitlab_repository("https://custom.example/gitlab"), artifact))
    paths.add(gl.cache_dir_for(_gitlab_repository(namespace="another/team"), artifact))
    for changed in (
        gl.JobArtifact(repo.path, 43, 7, "docs-html.zip"),
        gl.JobArtifact(repo.path, 42, 8, "docs-html.zip"),
        gl.JobArtifact(repo.path, 42, 7, "another.zip"),
        gl.JobArtifact("fork/package", 42, 7, "docs-html.zip"),
    ):
        paths.add(gl.cache_dir_for(repo, changed))
    assert len(paths) == 7
    assert all(path.is_relative_to(tmp_path) and "gitlab" in path.parts for path in paths)


def test_gitlab_direct_job_downloads_and_serves_real_archive_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(gl, "resolve_tokens", lambda *args: (None, None))
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, **kwargs: (
            GitLabResponse(chunks=[_zip_bytes()])
            if url.endswith("/jobs/42/artifacts")
            else pytest.fail("Direct job attempted protected metadata")
        ),
    )
    served: list[Path] = []
    monkeypatch.setattr(serve, "site", lambda root, **kwargs: served.append(root))
    gl.preview_gitlab(None, repo="https://gitlab.com/team/package", job=42, open_browser=False)
    assert len(served) == 1 and served[0].name == "_site"
    assert (served[0] / "reference/index.html").is_file()


def test_gitlab_retry_resumes_archive_and_never_logs_signed_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _zip_bytes()
    attempts = 0
    ranges: list[str | None] = []

    class Interrupted(GitLabResponse):
        def iter_content(self, chunk_size: int) -> Any:
            yield data[:20]
            raise requests.ConnectionError("https://cdn.example/archive?signature=hidden")

    def get(url: str, **kwargs: Any) -> GitLabResponse:
        nonlocal attempts
        attempts += 1
        ranges.append(kwargs["headers"].get("Range"))
        if attempts == 1:
            return Interrupted()
        return GitLabResponse(
            status=206,
            headers={"Content-Range": f"bytes 20-{len(data) - 1}/{len(data)}"},
            chunks=[data[20:]],
        )

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(gl.time, "sleep", lambda seconds: None)
    gl.GitLabClient(_gitlab_repository()).download_artifact(
        gl.JobArtifact("team/package", 42), tmp_path
    )
    assert ranges == [None, "bytes=20-"]
    assert (tmp_path / "docs/_site/index.html").is_file()
    assert "signature" not in capsys.readouterr().out


def test_gitlab_missing_source_artifact_overrides_speculative_access_denial() -> None:
    client = _GitLabClient(
        {
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7": {
                "sha": "current",
                "target_project_id": 10,
                "source_project_id": 11,
            },
            "projects/team%2Fsubteam%2Fpackage/merge_requests/7/pipelines": [
                {"id": 77, "sha": "current", "ref": "main", "status": "failed"}
            ],
            "projects/10/pipelines/77": gl.GitLabAPIError(403, "Wrong-project denial"),
            "projects/11/pipelines/77": {"id": 77, "project_id": 11, "sha": "current"},
            "projects/11/pipelines/77/jobs": [],
        }
    )
    with pytest.raises(gl.MissingArtifactError, match="Available jobs"):
        gl.resolve_artifact(client, mr=7)


def test_gitlab_successful_docs_job_can_belong_to_failed_pipeline() -> None:
    client = _GitLabClient({"projects/team%2Fsubteam%2Fpackage/pipelines/77/jobs": [_docs_job()]})
    assert gl.resolve_artifact(client, pipeline=77).job_id == 20


def test_gitlab_retry_transient_status_and_restart_when_range_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = _zip_bytes()
    (tmp_path / "_artifact.zip").write_bytes(b"partial")
    responses = iter([GitLabResponse(status=503), GitLabResponse(chunks=[data])])
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(gl.time, "sleep", lambda seconds: None)
    gl.GitLabClient(_gitlab_repository()).download_artifact(
        gl.JobArtifact("team/package", 42), tmp_path
    )
    assert (tmp_path / "docs/_site/index.html").is_file()
