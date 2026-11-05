"""
Repository data from GitHub and the local checkout, read once per documentation build
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .._apiref._settings import SourceLinks
from .._subprocess import TEXT_MODE_KWARGS
from .._website.navigation.release import Release

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from .._github import GithubRepo
    from .._remote import Remote
    from ..config import Config

__all__ = ["Facts", "exact_tag", "source_links", "source_ref"]


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


def source_links(
    config: Config,
    package_root: Path,
    repo_url: str | None,
    *,
    warn: Callable[[str], None],
) -> SourceLinks:
    """
    Resolve the source-link destinations for documented objects

    Parameters
    ----------
    config
        Project configuration. `source.enabled: false` disables source links.
        `source.branch` overrides the ref; `source.path` overrides the source
        directory used in links.
    package_root
        The repository root used for relative source paths and as the working
        directory for `git`.
    repo_url
        The project's GitHub repository URL, or `None` when it has none.
    warn
        The callback for reporting warnings to the user.

    Returns
    -------
    :
        The source-link settings. No links are produced and `git` does not run
        when source links are disabled or there is no repository. Otherwise,
        `git` runs only when no `source.branch` is configured.
    """
    if not (config.source_enabled and repo_url):
        return SourceLinks()
    return SourceLinks(
        repo_url=repo_url,
        ref=source_ref(config, package_root, warn=warn),
        package_root=package_root,
        path=config.source_path,
    )


def source_ref(config: Config, package_root: Path, *, warn: Callable[[str], None]) -> str:
    """
    Resolve the tag or branch targeted by source links

    A configured `source.branch` takes precedence, and `git` does not run.
    Otherwise the exact tag at `HEAD` wins over the branch name. When `git`
    cannot start, even after one retry, a warning names the error and the ref
    falls back to `main`. When `git` exits with a non-zero status, as outside
    a repository, or `HEAD` is detached and has no exact tag, the ref falls
    back to `main` silently.

    Parameters
    ----------
    config
        Project configuration.
    package_root
        The directory to run `git` in.
    warn
        The callback for reporting warnings to the user.

    Returns
    -------
    :
        The tag or branch name, or `main` as the fallback.
    """
    if config.source_branch:
        return config.source_branch
    try:
        tag = exact_tag(package_root)
        if tag is not None:
            return tag
        result = _git(package_root, "rev-parse", "--abbrev-ref", "HEAD")
    except OSError as error:
        warn(f"Could not run git to detect the source-link ref ({error}); using 'main'")
        return "main"
    branch = result.stdout.strip()
    # A detached `HEAD` has no branch name.
    return branch if result.returncode == 0 and branch != "HEAD" else "main"


def exact_tag(root: Path) -> str | None:
    """
    Find the tag that names the commit at `HEAD`

    Parameters
    ----------
    root
        The directory to run `git` in.

    Returns
    -------
    :
        The tag, or `None` when no tag names the commit or `root` is not in a
        repository.

    Raises
    ------
    OSError
        If `git` cannot start on either of the two attempts.
    """
    result = _git(root, "describe", "--tags", "--exact-match", "HEAD")
    tag = result.stdout.strip()
    return tag if result.returncode == 0 and tag else None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """
    Run a `git` command, retrying once if the process cannot start

    Parameters
    ----------
    root
        The directory to run `git` in.
    *args
        Arguments passed to `git`.

    Returns
    -------
    :
        The completed process.

    Raises
    ------
    OSError
        If `git` cannot start on either of the two attempts.
    """
    command = ["git", *args]
    try:
        return subprocess.run(command, cwd=root, capture_output=True, **TEXT_MODE_KWARGS)
    except OSError:
        # Under heavy load, an immediate retry can encounter `EAGAIN` again.
        time.sleep(0.2)
    return subprocess.run(command, cwd=root, capture_output=True, **TEXT_MODE_KWARGS)
