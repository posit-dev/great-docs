"""
GitHub credentials, project counts and published releases
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .remote import ReleaseData
    from .repository import Repository

__all__ = ["token_from_env", "stats", "releases"]


def token_from_env() -> str | None:
    """
    Read a GitHub API token from the environment

    Returns
    -------
    :
        `GITHUB_TOKEN`, else `GH_TOKEN`, without surrounding whitespace; `None` when neither
        is set or the chosen one is blank.
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    return token.strip() or None


def stats(repo: Repository) -> dict[str, int]:
    """
    Fetch the repository's known star and fork counts

    Parameters
    ----------
    repo
        The repository.

    Returns
    -------
    :
        The counts under the keys `stars` and `forks`, or an empty dict when the request
        fails. Missing or invalid counts have no entry.
    """
    import requests

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = token_from_env()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo.namespace}/{repo.name}"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, dict):
                return {}
            data = cast("dict[str, object]", data)
            return {
                key: value
                for key, field in (("stars", "stargazers_count"), ("forks", "forks_count"))
                if isinstance(value := data.get(field), int)
                and not isinstance(value, bool)
                and value >= 0
            }
    except (requests.RequestException, ValueError):
        pass
    return {}


def releases(
    repo: Repository, max_releases: int, *, report: Callable[[str], None]
) -> list[ReleaseData]:
    """
    Fetch the repository's published releases, newest first

    Fetch pages of up to 100 releases until `max_releases` is reached or the provider has
    no more. If a page fails, report a warning and keep the releases already read.

    Parameters
    ----------
    repo
        The repository.
    max_releases
        The maximum number of releases to return.
    report
        The callback for incomplete or malformed release data.

    Returns
    -------
    :
        One dict per release with the keys `tag_name`, `name`, `body`, `published_at`,
        `html_url` and `prerelease`. Draft releases are excluded.
    """
    if max_releases <= 0:
        return []
    import requests

    releases: list[ReleaseData] = []
    per_page = min(max_releases, 100)
    page = 1

    headers = {"Accept": "application/vnd.github+json"}
    token = token_from_env()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    while len(releases) < max_releases:
        url = (
            f"https://api.github.com/repos/{repo.namespace}/{repo.name}/releases"
            f"?per_page={per_page}&page={page}"
        )

        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            report(f"Failed to fetch GitHub releases: {exc}")
            break

        if resp.status_code in (403, 429):
            report("GitHub API rate limit reached; changelog may be incomplete")
            break
        if resp.status_code == 404:
            report(f"GitHub repository {repo.namespace}/{repo.name} not found")
            break
        if resp.status_code != 200:
            report(f"GitHub API returned status {resp.status_code}")
            break

        try:
            data = resp.json()
        except ValueError:
            report("GitHub API returned a malformed release list")
            break
        if not isinstance(data, list):
            report("GitHub API returned a malformed release list")
            break
        entries = cast("list[object]", data)
        if not data:
            break

        for entry in entries:
            if not isinstance(entry, dict):
                report("GitHub API returned a malformed release entry")
                continue
            release = cast("dict[str, object]", entry)
            tag = release.get("tag_name")
            if not isinstance(tag, str):
                report("GitHub API returned a malformed release entry")
                continue
            if release.get("draft"):
                continue
            releases.append(
                {
                    "tag_name": tag,
                    "name": _text(release.get("name")),
                    "body": _text(release.get("body")),
                    "published_at": _text(release.get("published_at")),
                    "html_url": _text(release.get("html_url")),
                    "prerelease": release.get("prerelease") is True,
                }
            )
            if len(releases) >= max_releases:
                break

        # A short page is the last one
        if len(entries) < per_page:
            break
        page += 1

    return releases


def _text(value: object) -> str:
    """Read a nullable release text field as a string"""
    return value if isinstance(value, str) else ""
