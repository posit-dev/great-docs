"""
GitLab job-log instructions and opt-in merge-request notes
"""

from __future__ import annotations

import os
import shlex
from typing import cast

import requests

from ..._project.repository import Repository
from ..preview import PREVIEW_COMMENT_MARKER, resolve_repository
from ..preview_artifacts import PreviewError
from .gitlab_preview import GitLabClient


def resolve_ci_repositories(
    repo: str | None, artifact_repo: str | None, base_url: str | None
) -> tuple[Repository, Repository]:
    """Resolve the MR target and artifact owner on one explicit GitLab instance"""
    if base_url is None:
        api = os.environ.get("CI_API_V4_URL", "").rstrip("/")
        if api.endswith("/api/v4"):
            base_url = api.removesuffix("/api/v4")
    target_url = (
        repo or os.environ.get("CI_MERGE_REQUEST_PROJECT_URL") or os.environ.get("CI_PROJECT_URL")
    )
    target = resolve_repository(None, target_url, provider="gitlab", base_url=base_url)
    artifact_url = artifact_repo or os.environ.get("CI_PROJECT_URL") or target.url
    artifact = resolve_repository(None, artifact_url, provider="gitlab", base_url=target.base_url)
    if (
        target.provider != "gitlab"
        or artifact.provider != "gitlab"
        or target.base_url != artifact.base_url
    ):
        raise PreviewError(
            "The MR target and artifact repository must belong to the same GitLab instance."
        )
    return target, artifact


def _command(repository: Repository, selector: str, value: int, artifact: str) -> str:
    """Render a standalone command that retains the complete instance and project"""
    args = [
        "great-docs",
        "preview",
        "--provider",
        "gitlab",
        "--repo",
        repository.url,
        "--repo-base-url",
        repository.base_url,
        selector,
        str(value),
    ]
    if selector != "--job" and artifact != "docs-html":
        args.extend(["--artifact", artifact])
    return shlex.join(args)


def preview_commands(
    target: Repository,
    owner: Repository,
    *,
    job: int | None = None,
    pipeline: int | None = None,
    mr: int | None = None,
    artifact: str = "docs-html",
) -> list[str]:
    """Render exact-build and optional latest-MR commands with their owning projects"""
    if (job is None) == (pipeline is None):
        raise PreviewError(
            "Pass exactly one of --job or --pipeline to identify the built artifact."
        )
    commands = (
        [_command(owner, "--job", job, artifact)]
        if job is not None
        else [_command(owner, "--pipeline", cast("int", pipeline), artifact)]
    )
    if mr is not None:
        commands.append(_command(target, "--mr", mr, artifact))
    return commands


def render_notice_lines(
    target: Repository,
    owner: Repository,
    *,
    job: int | None = None,
    pipeline: int | None = None,
    mr: int | None = None,
    artifact: str = "docs-html",
) -> list[str]:
    """Print ordinary GitLab log instructions without GitHub workflow annotations"""
    return [
        "Preview these documentation artifacts locally:",
        *preview_commands(target, owner, job=job, pipeline=pipeline, mr=mr, artifact=artifact),
        "Install Great Docs with uv tool install great-docs, or use uvx great-docs preview ...",
        "Use GITLAB_TOKEN for private artifacts and MR/pipeline discovery. CI_JOB_TOKEN supports permitted artifact downloads only.",
        "Add --path reference/index.html to open a page, or --refresh to download again.",
    ]


def render_preview_comment(
    target: Repository,
    owner: Repository,
    *,
    mr: int,
    job: int | None = None,
    pipeline: int | None = None,
    artifact: str = "docs-html",
) -> str:
    """Render a marked MR note with separate artifact and target-project commands"""
    commands = preview_commands(target, owner, job=job, pipeline=pipeline, mr=mr, artifact=artifact)
    return "\n".join(
        [
            PREVIEW_COMMENT_MARKER,
            "### Preview this merge request's documentation locally",
            "",
            "Download the exact build, or select the latest documentation build for this MR:",
            "",
            "```bash",
            *commands,
            "```",
            "",
            "Install with `uv tool install great-docs`, or run with `uvx great-docs preview ...`.",
            "Use `GITLAB_TOKEN` for private artifacts and MR/pipeline metadata. A permitted `CI_JOB_TOKEN` can download job artifacts only.",
            "Add `--path reference/index.html` to open a page or `--refresh` to download again.",
        ]
    )


def upsert_mr_comment(repository: Repository, mr: int, body: str, token: str) -> str:
    """Create a preview note or update its marker match with GitLab's PUT endpoint"""
    client = GitLabClient(repository, token=token)
    path = f"{client.project_path()}/merge_requests/{mr}/notes"
    notes = client.list_json(path)
    existing = next(
        (
            note.get("id")
            for note in notes
            if isinstance(note.get("body"), str)
            and PREVIEW_COMMENT_MARKER in cast("str", note["body"])
        ),
        None,
    )
    if existing is not None and (
        not isinstance(existing, int) or isinstance(existing, bool) or existing <= 0
    ):
        raise PreviewError("GitLab returned an invalid preview-note ID.")
    url = f"{client.api_url}/{path}"
    try:
        if existing is None:
            response = requests.post(
                url,
                headers=client.headers(),
                json={"body": body},
                timeout=15,
                allow_redirects=False,
            )
            action = "created"
        else:
            response = requests.put(
                f"{url}/{existing}",
                headers=client.headers(),
                json={"body": body},
                timeout=15,
                allow_redirects=False,
            )
            action = "updated"
    except requests.RequestException as error:
        raise PreviewError(
            f"GitLab preview-note request failed ({type(error).__name__})."
        ) from error
    if response.status_code not in (200, 201):
        raise PreviewError(
            f"Could not {action.removesuffix('d')} GitLab preview note (HTTP {response.status_code}). Check GITLAB_TOKEN API write permissions and MR project access."
        )
    return action


def post_preview_comment(
    *,
    mr: int,
    job: int | None = None,
    pipeline: int | None = None,
    repo: str | None = None,
    artifact_repo: str | None = None,
    base_url: str | None = None,
    artifact: str = "docs-html",
) -> tuple[str, str]:
    """Require a write token before rendering and upserting a GitLab MR preview note"""
    token = os.environ.get("GITLAB_TOKEN", "").strip()
    if not token:
        raise PreviewError(
            "Set GITLAB_TOKEN with API write permissions to post MR notes. CI_JOB_TOKEN cannot write notes."
        )
    target, owner = resolve_ci_repositories(repo, artifact_repo, base_url)
    body = render_preview_comment(
        target, owner, mr=mr, job=job, pipeline=pipeline, artifact=artifact
    )
    return upsert_mr_comment(target, mr, body, token), target.url
