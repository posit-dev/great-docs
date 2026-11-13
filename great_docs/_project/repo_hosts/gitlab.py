"""
GitLab project counts and published releases

Public projects support anonymous reads. `GITLAB_TOKEN` authenticates project and
release reads; `CI_JOB_TOKEN` authenticates releases only.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from urllib.parse import quote

if TYPE_CHECKING:
    from ..remote import ReleaseData
    from ..repository import Repository


def stats(repo: Repository, *, report: Callable[[str], None]) -> dict[str, int]:
    """
    Read known star and fork counts without using a CI job token

    Parameters
    ----------
    repo
        The GitLab project, including its instance base.
    report
        The callback for unavailable or malformed project data.

    Returns
    -------
    :
        Known non-negative counts. Missing counts have no entry.
    """
    data = _read(_project_url(repo), _headers(job_token=False), report)
    if not isinstance(data, dict):
        if data is not None:
            report("GitLab API returned malformed project data")
        return {}
    fields = cast("dict[str, object]", data)
    return {
        key: value
        for key, field in (("stars", "star_count"), ("forks", "forks_count"))
        if isinstance(value := fields.get(field), int)
        and not isinstance(value, bool)
        and value >= 0
    }


def releases(repo: Repository, maximum: int, *, report: Callable[[str], None]) -> list[ReleaseData]:
    """
    Read published releases and retain pages fetched before a failure

    Parameters
    ----------
    repo
        The GitLab project, including its instance base.
    maximum
        The maximum number of published releases to return.
    report
        The callback for incomplete or malformed release data.

    Returns
    -------
    :
        Normalised releases, newest first. Upcoming and future-dated releases
        are excluded. GitLab supplies no GitHub-equivalent pre-release flag.
    """
    result: list[ReleaseData] = []
    if maximum <= 0:
        return result
    per_page = min(maximum, 100)
    page = 1
    headers = _headers(job_token=True)
    now = datetime.now(timezone.utc)
    while len(result) < maximum:
        url = f"{_project_url(repo)}/releases?per_page={per_page}&page={page}"
        data = _read(url, headers, report)
        if data is None:
            break
        if not isinstance(data, list):
            report("GitLab API returned a malformed release list")
            break
        entries = cast("list[object]", data)
        for entry in entries:
            if not isinstance(entry, dict):
                report("GitLab API returned a malformed release entry")
                continue
            fields = cast("dict[str, object]", entry)
            if fields.get("upcoming_release") is True:
                continue
            tag = fields.get("tag_name")
            released = fields.get("released_at")
            if not isinstance(tag, str) or not tag or not isinstance(released, str):
                report("GitLab API returned a malformed release entry")
                continue
            try:
                date = datetime.fromisoformat(released.replace("Z", "+00:00"))
            except ValueError:
                report("GitLab API returned a malformed release date")
                continue
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            if date > now:
                continue
            links = fields.get("_links")
            web_url = (
                cast("dict[str, object]", links).get("self") if isinstance(links, dict) else None
            )
            result.append(
                {
                    "tag_name": tag,
                    "name": _text(fields.get("name")),
                    "body": _text(fields.get("description")),
                    "published_at": released,
                    "html_url": _text(web_url) or repo.release_url(tag),
                    "prerelease": False,
                }
            )
            if len(result) >= maximum:
                break
        if len(entries) < per_page:
            break
        page += 1
    return result


def _project_url(repo: Repository) -> str:
    """Form the project API address with the full path encoded once"""
    return f"{repo.base_url}/api/v4/projects/{quote(repo.path, safe='')}"


def _headers(*, job_token: bool) -> dict[str, str]:
    """Select credentials permitted by the requested endpoint"""
    headers = {"Accept": "application/json"}
    token = os.environ.get("GITLAB_TOKEN", "").strip()
    if token:
        headers["PRIVATE-TOKEN"] = token
    elif job_token and (token := os.environ.get("CI_JOB_TOKEN", "").strip()):
        headers["JOB-TOKEN"] = token
    return headers


def _read(url: str, headers: dict[str, str], report: Callable[[str], None]) -> object:
    """Read JSON while reporting failures without interrupting the build"""
    import requests

    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=False)
    except requests.RequestException as error:
        report(f"Failed to fetch GitLab repository data: {error}")
        return None
    status = response.status_code
    if 300 <= status < 400:
        report("GitLab API redirected the request; check the configured instance base")
    elif status == 401:
        report("GitLab authentication failed; check the token and project access")
    elif status == 403:
        report("GitLab denied access to repository data")
    elif status == 404:
        report("GitLab project not found or unavailable to the supplied credentials")
    elif status == 429:
        report("GitLab API rate limit reached; repository data may be incomplete")
    elif status != 200:
        report(f"GitLab API returned status {status}")
    else:
        try:
            data = cast("object", response.json())
        except ValueError:
            report("GitLab API returned malformed JSON")
        else:
            if data is None:
                report("GitLab API returned malformed repository data")
            return data
    return None


def _text(value: object) -> str:
    """Read a nullable release text field as a string"""
    return value if isinstance(value, str) else ""
