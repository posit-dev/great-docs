"""
Repository data and PyPI release dates

A build reads repository statistics, releases and dependency release dates through a
`Remote`. `HttpRemote` retrieves data from the services; `OfflineRemote` returns the
empty results of failed requests without accessing the network.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from dataclasses import dataclass
from typing import Protocol, TypedDict

from . import github
from .repository import Repository

__all__ = ["HttpRemote", "OfflineRemote", "ReleaseData", "Remote"]


class ReleaseData(TypedDict):
    """The published release fields shared by repository providers"""

    tag_name: str
    name: str
    body: str
    published_at: str
    html_url: str
    prerelease: bool


class Remote(Protocol):
    """A source of repository data and PyPI release dates"""

    def repository_stats(self, repo: Repository) -> dict[str, int]:
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

    def repository_releases(self, repo: Repository, max_releases: int) -> list[ReleaseData]:
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
            `html_url` and `prerelease`. Draft and upcoming releases are excluded.
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
    A source of repository and PyPI data retrieved over HTTP

    Request failures leave the requested data unknown rather than raising an error.
    Provider credentials are sent only to that provider's endpoints.
    """

    report: Callable[[str], None]
    """The callback for warnings when releases cannot be read in full"""

    def repository_stats(self, repo: Repository) -> dict[str, int]:
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
        if repo.provider == "gitlab":
            from . import gitlab

            return gitlab.stats(repo, report=self.report)
        return github.stats(repo)

    def repository_releases(self, repo: Repository, max_releases: int) -> list[ReleaseData]:
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

        Returns
        -------
        :
            One dict per release with the keys `tag_name`, `name`, `body`, `published_at`,
            `html_url` and `prerelease`. Draft releases are excluded.
        """
        if max_releases <= 0:
            return []
        if repo.provider == "gitlab":
            from . import gitlab

            return gitlab.releases(repo, max_releases, report=self.report)
        return github.releases(repo, max_releases, report=self.report)

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

    def repository_stats(self, repo: Repository) -> dict[str, int]:
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

    def repository_releases(self, repo: Repository, max_releases: int) -> list[ReleaseData]:
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
