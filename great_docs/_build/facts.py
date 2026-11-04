"""
Repository data fetched from GitHub once per documentation build
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._website.navigation.release import Release

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .._github import GithubRepo
    from .._remote import Remote
    from ..config import Config

__all__ = ["Facts"]


@dataclass(frozen=True)
class Facts:
    """GitHub data shown in the site's navbar"""

    github_stats: Mapping[str, int] | None = None
    """
    Star and fork counts under the keys `stars` and `forks`

    Empty when GitHub did not supply them, and `None` when the project has no GitHub
    repository or does not show the GitHub widget.
    """

    latest_release: Release | None = None
    """The newest published release, or `None` when there is none or it is unknown"""

    @classmethod
    def make(cls, config: Config, repo: GithubRepo | None, remote: Remote) -> Facts:
        """
        Fetch the repository's star and fork counts and its latest release

        Parameters
        ----------
        config
            Project configuration. Counts are fetched only when `github_style` is
            `"widget"`.
        repo
            The project's GitHub repository. Without one, nothing is fetched.
        remote
            The source of GitHub data.

        Returns
        -------
        :
            The star and fork counts and latest release, when available.
        """
        if repo is None:
            return cls()
        stats = remote.github_stats(repo) if config.github_style == "widget" else None
        latest = remote.github_releases(repo, max_releases=1)
        return cls(
            github_stats=stats,
            latest_release=Release.make(latest[0]) if latest else None,
        )
