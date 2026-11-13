"""
GitLab merge-request, pipeline and job artifact previews
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.parse import quote, urljoin, urlsplit

import requests
from dotenv import dotenv_values, find_dotenv

from .._project.repository import Repository
from . import serve
from .preview import resolve_repository
from .preview_artifacts import (
    PreviewError,
    cache_root,
    cached_site,
    safe_extract_zip,
    stream_to_file,
)

_TIMEOUT = 15
_READ_TIMEOUT = 120
_DOWNLOAD_RETRIES = 5


class MissingArtifactError(PreviewError):
    """A pipeline without a matching successful documentation archive"""


class GitLabAPIError(PreviewError):
    """A failed GitLab API response with its HTTP status"""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def resolve_tokens(
    project_path: str | Path | None, env_file: str | None
) -> tuple[str | None, str | None]:
    """Read GitLab credentials without consulting GitHub credentials or command-line tools"""
    values: list[dict[str, str | None]] = []
    if env_file:
        try:
            values.append(dict(dotenv_values(env_file)))
        except (OSError, UnicodeDecodeError):
            pass
    values.append(dict(os.environ))
    candidates = [Path(project_path) / ".env"] if project_path else []
    if found := find_dotenv(usecwd=True):
        candidates.append(Path(found))
    for candidate in dict.fromkeys(candidates):
        try:
            values.append(dict(dotenv_values(candidate)))
        except (OSError, UnicodeDecodeError):
            pass
    private = next(
        (v.strip() for item in values if (v := item.get("GITLAB_TOKEN")) and v.strip()), None
    )
    job = next(
        (v.strip() for item in values if (v := item.get("CI_JOB_TOKEN")) and v.strip()), None
    )
    return private, job


def _mapping(value: object) -> dict[str, object]:
    """Require an API object before reading its fields"""
    if not isinstance(value, dict):
        raise PreviewError("GitLab returned malformed object data.")
    return cast("dict[str, object]", value)


def _identifier(value: object) -> int:
    """Require a positive API identifier"""
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise PreviewError("GitLab returned an invalid project, pipeline or job ID.")


@dataclass(frozen=True)
class JobArtifact:
    """A job archive in the project that owns its pipeline"""

    project: str
    job_id: int
    pipeline_id: int | None = None
    name: str = "archive"


class GitLabClient:
    """GitLab metadata reads and endpoint-restricted artifact credentials"""

    def __init__(
        self, repository: Repository, *, token: str | None = None, job_token: str | None = None
    ) -> None:
        self.repository = repository
        self.token = token
        self.job_token = job_token
        self.api_url = f"{repository.base_url}/api/v4"

    def project_path(self, project: str | int | None = None) -> str:
        """Encode the complete project identity once for API use"""
        return f"projects/{quote(str(project if project is not None else self.repository.path), safe='')}"

    def headers(self, *, artifact: bool = False) -> dict[str, str]:
        """Choose credentials permitted by metadata or artifact-download endpoints"""
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        elif artifact and self.job_token:
            headers["JOB-TOKEN"] = self.job_token
        return headers

    def get_json(self, path: str, params: dict[str, str | int] | None = None) -> tuple[object, str]:
        """Read one JSON page without following credential-bearing API redirects"""
        try:
            response = requests.get(
                f"{self.api_url}/{path}",
                headers=self.headers(),
                params=params,
                timeout=_TIMEOUT,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise PreviewError(f"GitLab request failed ({type(error).__name__}).") from error
        if response.status_code != 200:
            self.raise_status(response.status_code)
        try:
            data = cast("object", response.json())
        except ValueError as error:
            raise PreviewError("GitLab returned malformed JSON.") from error
        return data, response.headers.get("X-Next-Page", "")

    def list_json(
        self, path: str, params: dict[str, str | int] | None = None
    ) -> list[dict[str, object]]:
        """Collect paginated objects using controlled API page parameters"""
        result: list[dict[str, object]] = []
        page = 1
        while True:
            data, next_page = self.get_json(path, {**(params or {}), "per_page": 100, "page": page})
            if not isinstance(data, list):
                raise PreviewError("GitLab returned a malformed list.")
            entries = cast("list[object]", data)
            result.extend(_mapping(item) for item in entries)
            if not next_page and len(entries) < 100:
                return result
            try:
                following = int(next_page) if next_page else page + 1
            except ValueError as error:
                raise PreviewError("GitLab returned malformed pagination.") from error
            if following <= page:
                raise PreviewError("GitLab returned repeated pagination.")
            page = following

    @staticmethod
    def raise_status(status: int) -> None:
        """Explain unavailable metadata without exposing request URLs or credentials"""
        if status in (401, 403):
            message = "GitLab denied metadata access. Set GITLAB_TOKEN with read_api access; CI_JOB_TOKEN supports artifact downloads only. Use --job for a directly accessible artifact."
        elif status == 404:
            message = "GitLab project, MR or pipeline was not found or is unavailable to these credentials."
        elif status == 429:
            message = "GitLab API rate limit reached; try again later."
        elif 300 <= status < 400:
            message = "GitLab API redirected the request; check --repo-base-url."
        else:
            message = f"GitLab API request failed (HTTP {status})."
        raise GitLabAPIError(status, message)

    def _artifact_response(self, url: str, have: int) -> requests.Response:
        """Follow CDN redirects after removing credentials when the origin changes"""
        headers = self.headers(artifact=True)
        if have:
            headers["Range"] = f"bytes={have}-"
        for _ in range(11):
            response = requests.get(
                url,
                headers=headers,
                timeout=(_TIMEOUT, _READ_TIMEOUT),
                stream=True,
                allow_redirects=False,
            )
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise PreviewError("GitLab artifact redirect has no destination.")
            following = urljoin(url, location)
            before, after = urlsplit(url), urlsplit(following)
            if (
                after.scheme not in ("http", "https")
                or after.username
                or after.password
                or (before.scheme == "https" and after.scheme != "https")
            ):
                raise PreviewError("GitLab artifact redirect has an unsafe destination.")
            if (before.scheme, before.hostname, before.port) != (
                after.scheme,
                after.hostname,
                after.port,
            ):
                headers = {
                    key: value
                    for key, value in headers.items()
                    if key.lower() not in {"private-token", "job-token", "authorization", "cookie"}
                }
            url = following
        raise PreviewError("GitLab artifact download redirected too many times.")

    def download_artifact(self, artifact: JobArtifact, dest: Path) -> None:
        """Download and safely unpack a job archive without requiring job metadata"""
        url = (
            f"{self.api_url}/{self.project_path(artifact.project)}/jobs/{artifact.job_id}/artifacts"
        )
        archive = dest / "_artifact.zip"
        for attempt in range(_DOWNLOAD_RETRIES):
            have = archive.stat().st_size if archive.exists() else 0
            try:
                with self._artifact_response(url, have) as response:
                    status = response.status_code
                    if status in (404, 410):
                        raise PreviewError(
                            "GitLab job artifact is missing, expired or unavailable. Check the project/job ID and credentials, or rebuild the documentation."
                        )
                    if status in (401, 403):
                        raise PreviewError(
                            "GitLab denied artifact access. Supply GITLAB_TOKEN or a permitted CI_JOB_TOKEN and check project access."
                        )
                    if status in (429, 500, 502, 503, 504):
                        raise requests.HTTPError(f"Transient artifact response {status}")
                    if status not in (200, 206):
                        raise PreviewError(f"GitLab artifact download failed (HTTP {status}).")
                    if status == 206 and (
                        not have
                        or not response.headers.get("Content-Range", "").startswith(
                            f"bytes {have}-"
                        )
                    ):
                        raise PreviewError("GitLab returned an invalid artifact resume range.")
                    start = have if status == 206 else 0
                    total = start + int(response.headers.get("Content-Length") or 0)
                    stream_to_file(
                        response, archive, total, mode="ab" if start else "wb", start=start
                    )
                break
            except requests.RequestException as error:
                if attempt == _DOWNLOAD_RETRIES - 1:
                    raise PreviewError(
                        f"GitLab artifact download failed after {_DOWNLOAD_RETRIES} attempts ({type(error).__name__})."
                    ) from error
                print(
                    f"→ Artifact download interrupted; retrying ({attempt + 2}/{_DOWNLOAD_RETRIES})."
                )
                time.sleep(2 * (attempt + 1))
        safe_extract_zip(archive, dest)
        archive.unlink(missing_ok=True)


def _job_artifact(client: GitLabClient, project: str, pipeline: int, name: str) -> JobArtifact:
    """Select one successful documentation archive or explain missing and ambiguous jobs"""
    jobs = client.list_json(
        f"{client.project_path(project)}/pipelines/{pipeline}/jobs",
        {"scope": "success", "include_retried": "false"},
    )
    archives = [
        job
        for job in jobs
        if job.get("status") == "success"
        and isinstance(job.get("artifacts_file"), dict)
        and _mapping(job["artifacts_file"]).get("filename")
        and not job.get("erased_at")
    ]
    exact = [
        job
        for job in archives
        if job.get("name") == name
        or _mapping(job["artifacts_file"]).get("filename") in (name, f"{name}.zip")
    ]
    candidates = exact
    if not candidates and name == "docs-html":
        candidates = [
            job
            for job in archives
            if job.get("name") in ("great-docs-preview", "great-docs-pages", "docs", "pages")
        ]
    if not candidates:
        names = ", ".join(str(job.get("name")) for job in archives) or "none"
        raise MissingArtifactError(
            f"No successful documentation artifact '{name}' in pipeline {pipeline}. Available jobs: {names}. Pass --artifact with a job/archive name, or --job with its ID."
        )
    if len(candidates) > 1:
        choices = ", ".join(f"{job.get('name')} (--job {job.get('id')})" for job in candidates)
        raise PreviewError(
            f"Several documentation artifacts match: {choices}. Select one with --job."
        )
    job = candidates[0]
    if isinstance(expires := job.get("artifacts_expire_at"), str):
        try:
            date = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        except ValueError:
            raise PreviewError("GitLab returned an invalid artifact expiry date.") from None
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        if date < datetime.now(timezone.utc):
            raise PreviewError(
                "The selected GitLab documentation artifact has expired; rebuild the documentation."
            )
    return JobArtifact(
        project,
        _identifier(job.get("id")),
        pipeline,
        str(_mapping(job["artifacts_file"])["filename"]),
    )


def resolve_artifact(
    client: GitLabClient,
    *,
    mr: int | None = None,
    pipeline: int | None = None,
    job: int | None = None,
    name: str = "docs-html",
) -> JobArtifact:
    """Resolve project-local MR IIDs or pipeline/job IDs to an artifact-owning project"""
    if sum(value is not None for value in (mr, pipeline, job)) != 1:
        raise PreviewError("Specify exactly one of --mr, --pipeline or --job.")
    if job is not None:
        return JobArtifact(client.repository.path, _identifier(job))
    if pipeline is not None:
        return _job_artifact(client, client.repository.path, _identifier(pipeline), name)
    mr = _identifier(mr)
    target_path = client.project_path()
    data, _ = client.get_json(f"{target_path}/merge_requests/{mr}")
    merge_request = _mapping(data)
    head_value = merge_request.get("head_pipeline")
    head = {} if head_value is None else _mapping(head_value)
    diff_value = merge_request.get("diff_refs")
    diff = {} if diff_value is None else _mapping(diff_value)
    current_sha = merge_request.get("sha") or diff.get("head_sha") or head.get("sha")
    if not isinstance(current_sha, str) or not current_sha:
        raise PreviewError(
            "Could not determine the current MR head commit; pass --pipeline or --job."
        )
    pipelines = client.list_json(f"{target_path}/merge_requests/{mr}/pipelines")
    if isinstance(head.get("id"), int):
        head_id = _identifier(head["id"])
        pipelines = [item for item in pipelines if item.get("id") == head_id]
        if not pipelines:
            pipelines = [head]
    else:
        pipelines = [item for item in pipelines if item.get("sha") == current_sha]
    pipelines.sort(
        key=lambda item: (item.get("status") == "success", _identifier(item.get("id"))),
        reverse=True,
    )
    if not pipelines:
        raise PreviewError(
            f"No pipeline found for MR !{mr}; wait for its documentation build or pass --job."
        )
    access_error: GitLabAPIError | None = None
    missing_error: MissingArtifactError | None = None
    for item in pipelines:
        pipeline_id = _identifier(item.get("id"))
        project_ids: list[str] = []
        for value in (
            item.get("project_id"),
            head.get("project_id") if head.get("id") == pipeline_id else None,
            merge_request.get("target_project_id"),
            merge_request.get("source_project_id"),
            client.repository.path,
        ):
            if isinstance(value, (int, str)) and str(value) not in project_ids:
                project_ids.append(str(value))
        for project in project_ids:
            try:
                details, _ = client.get_json(
                    f"{client.project_path(project)}/pipelines/{pipeline_id}"
                )
            except GitLabAPIError as error:
                if error.status in (401, 403, 404):
                    if access_error is None or error.status in (401, 403):
                        access_error = error
                    continue
                raise
            resolved = _mapping(details)
            if _identifier(resolved.get("id")) != pipeline_id:
                raise PreviewError("GitLab returned a different pipeline than requested.")
            actual_project = str(_identifier(resolved.get("project_id")))
            if project.isdigit() and actual_project != project:
                raise PreviewError("GitLab returned a pipeline owned by a different project.")
            if resolved.get("sha") != item.get("sha"):
                raise PreviewError("GitLab returned a pipeline for a different commit.")
            access_error = None
            try:
                return _job_artifact(client, actual_project, pipeline_id, name)
            except MissingArtifactError as error:
                missing_error = error
                break
    if missing_error is not None:
        raise missing_error
    if access_error is not None and access_error.status in (401, 403):
        raise access_error
    raise PreviewError(
        f"No successful documentation artifact found for MR !{mr}. Check fork project access, build status and artifact expiry; pass --pipeline or --job to select an exact build."
    )


def cache_dir_for(repository: Repository, artifact: JobArtifact) -> Path:
    """Separate GitLab instances, full projects and immutable job archives in the cache"""
    identity = json.dumps(
        [repository.base_url, repository.path, artifact.project], ensure_ascii=True
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()
    archive = hashlib.sha256(artifact.name.encode()).hexdigest()[:16]
    return (
        cache_root()
        / "gitlab"
        / digest
        / f"pipeline-{artifact.pipeline_id or 'unknown'}"
        / f"job-{artifact.job_id}"
        / archive
    )


def download_and_extract(
    client: GitLabClient, artifact: JobArtifact, *, refresh: bool = False
) -> Path:
    """Download a GitLab archive into its complete-site cache"""
    return cached_site(
        cache_dir_for(client.repository, artifact),
        lambda dest: client.download_artifact(artifact, dest),
        refresh=refresh,
    )


def preview_gitlab(
    project_path: str | Path | None,
    *,
    mr: int | None = None,
    pipeline: int | None = None,
    job: int | None = None,
    repo: str | None = None,
    provider: str | None = None,
    repo_base_url: str | None = None,
    config_path: str | None = None,
    artifact: str = "docs-html",
    path: str = "",
    port: int = 3000,
    open_browser: bool = True,
    refresh: bool = False,
    env_file: str | None = None,
) -> None:
    """Fetch a GitLab documentation job and serve its extracted site locally"""
    repository = resolve_repository(
        project_path, repo, provider=provider, base_url=repo_base_url, config_path=config_path
    )
    if repository.provider != "gitlab":
        raise PreviewError(
            "GitLab selectors require a GitLab repository. Pass --provider gitlab for shorthand input."
        )
    token, job_token = resolve_tokens(project_path, env_file)
    client = GitLabClient(repository, token=token, job_token=job_token)
    chosen = resolve_artifact(client, mr=mr, pipeline=pipeline, job=job, name=artifact)
    print(f"→ GitLab repository: {repository.url}")
    print(
        f"→ Job {chosen.job_id}"
        + (f" in pipeline {chosen.pipeline_id}" if chosen.pipeline_id else "")
    )
    root = download_and_extract(client, chosen, refresh=refresh)
    serve.site(root, port=port, open_path=path, open_browser=open_browser, report=print)
