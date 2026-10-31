"""
GitHub repository data and PyPI release dates

A build reads repository statistics, releases and dependency release dates through a
`Remote`. `HttpRemote` retrieves data from the services; `OfflineRemote` returns the
empty results of failed requests without accessing the network.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Any, Protocol

from ._github import GithubRepo, token_from_env

__all__ = ["HttpRemote", "OfflineRemote", "Remote"]


class Remote(Protocol):
    """A source of GitHub repository data and PyPI release dates"""

    def github_stats(self, repo: GithubRepo) -> dict[str, int]:
        """
        Read the repository's star and fork counts

        Parameters
        ----------
        repo
            The repository.

        Returns
        -------
        :
            The counts under the keys `stars` and `forks`, or an empty dict when they are
            unknown.
        """
        ...

    def github_releases(self, repo: GithubRepo, max_releases: int) -> list[dict[str, Any]]:
        """
        Read the repository's published releases, newest first

        Parameters
        ----------
        repo
            The repository.
        max_releases
            The maximum number of releases to return.

        Returns
        -------
        :
            One dict per release with the keys `tag_name`, `name`, `body`, `published_at`,
            `html_url` and `prerelease`. Draft releases are excluded.
        """
        ...

    def pypi_release_dates(self, package_names: Collection[str]) -> dict[str, str]:
        """
        Read the date of each package's latest release on PyPI

        Parameters
        ----------
        package_names
            The PyPI names of the packages.

        Returns
        -------
        :
            The `YYYY-MM-DD` date of each package's latest release, keyed by name. A package
            whose date is unknown has no entry.
        """
        ...


@dataclass(frozen=True, kw_only=True)
class HttpRemote:
    """
    A source of GitHub and PyPI data retrieved over HTTP

    Request failures leave the requested data unknown rather than raising an error.
    GitHub requests send `GITHUB_TOKEN` or `GH_TOKEN` when set for a higher rate limit.
    """

    report: Callable[[str], None]
    """The callback for warnings when releases cannot be read in full"""

    def github_stats(self, repo: GithubRepo) -> dict[str, int]:
        """
        Fetch the repository's star and fork counts from the GitHub API

        Parameters
        ----------
        repo
            The repository.

        Returns
        -------
        :
            The counts under the keys `stars` and `forks`, or an empty dict when the request
            fails or GitHub returns a status other than 200.
        """
        import requests

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = token_from_env()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{repo.owner}/{repo.name}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                }
        except requests.RequestException:
            pass
        return {}

    def github_releases(self, repo: GithubRepo, max_releases: int) -> list[dict[str, Any]]:
        """
        Fetch the repository's published releases from the GitHub API, newest first

        Fetch pages of up to 100 releases until `max_releases` is reached or GitHub has
        no more. If a page fails, report a warning and keep the releases already read.

        Parameters
        ----------
        repo
            The repository.
        max_releases
            The maximum number of releases to return.

        Returns
        -------
        :
            One dict per release with the keys `tag_name`, `name`, `body`, `published_at`,
            `html_url` and `prerelease`. Draft releases are excluded.
        """
        import requests

        releases: list[dict[str, Any]] = []
        per_page = min(max_releases, 100)
        page = 1

        headers = {"Accept": "application/vnd.github+json"}
        token = token_from_env()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        while len(releases) < max_releases:
            url = (
                f"https://api.github.com/repos/{repo.owner}/{repo.name}/releases"
                f"?per_page={per_page}&page={page}"
            )

            try:
                resp = requests.get(url, headers=headers, timeout=30)
            except requests.RequestException as exc:
                self.report(f"Failed to fetch GitHub releases: {exc}")
                break

            if resp.status_code == 403:
                self.report("GitHub API rate limit reached; changelog may be incomplete")
                break
            if resp.status_code == 404:
                self.report(f"GitHub repository {repo.owner}/{repo.name} not found")
                break
            if resp.status_code != 200:
                self.report(f"GitHub API returned status {resp.status_code}")
                break

            try:
                data = resp.json()
            except requests.exceptions.JSONDecodeError:
                self.report("GitHub API returned a malformed release list")
                break
            if not data:
                break

            for release in data:
                if release.get("draft"):
                    continue
                releases.append(
                    {
                        "tag_name": release.get("tag_name", ""),
                        "name": release.get("name", ""),
                        "body": release.get("body", ""),
                        "published_at": release.get("published_at", ""),
                        "html_url": release.get("html_url", ""),
                        "prerelease": release.get("prerelease", False),
                    }
                )
                if len(releases) >= max_releases:
                    break

            # A short page is the last one
            if len(data) < per_page:
                break
            page += 1

        return releases

    def pypi_release_dates(self, package_names: Collection[str]) -> dict[str, str]:
        """
        Fetch the date of each package's latest release from the PyPI JSON API

        Request up to eight packages at a time, with a timeout of 5 seconds per request.

        Parameters
        ----------
        package_names
            The PyPI names of the packages.

        Returns
        -------
        :
            The `YYYY-MM-DD` upload date of each package's latest version, keyed by name. A
            package whose request fails has no entry. Invalid JSON is a request failure;
            errors caused by an unexpected JSON structure propagate to the caller.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        import requests

        dates: dict[str, str] = {}
        if not package_names:
            return dates

        def fetch_one(name: str) -> tuple[str, str]:
            try:
                resp = requests.get(
                    f"https://pypi.org/pypi/{name}/json",
                    timeout=5,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # `info` describes the latest version; `releases` lists each version's files
                    latest_version = data.get("info", {}).get("version", "")
                    releases = data.get("releases", {})
                    if latest_version and latest_version in releases:
                        files = releases[latest_version]
                        if files:
                            upload_time = files[0].get("upload_time_iso_8601", "")
                            if upload_time:
                                return name, upload_time[:10]
            except requests.RequestException:
                pass
            return name, ""

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(fetch_one, name) for name in package_names]
            for future in as_completed(futures):
                name, date = future.result()
                if date:
                    dates[name] = date

        return dates


class OfflineRemote:
    """A source of empty results that makes no network requests"""

    def github_stats(self, repo: GithubRepo) -> dict[str, int]:
        """
        Report the repository's star and fork counts as unknown

        Parameters
        ----------
        repo
            The repository.

        Returns
        -------
        :
            An empty dict.
        """
        return {}

    def github_releases(self, repo: GithubRepo, max_releases: int) -> list[dict[str, Any]]:
        """
        Report that the repository has no known releases

        Parameters
        ----------
        repo
            The repository.
        max_releases
            The maximum number of releases to return.

        Returns
        -------
        :
            An empty list.
        """
        return []

    def pypi_release_dates(self, package_names: Collection[str]) -> dict[str, str]:
        """
        Report every package's release date as unknown

        Parameters
        ----------
        package_names
            The PyPI names of the packages.

        Returns
        -------
        :
            An empty dict.
        """
        return {}
