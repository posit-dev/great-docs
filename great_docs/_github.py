"""
GitHub repository identities and API credentials
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

__all__ = ["GithubRepo", "token_from_env"]

# Owner and name after `github.com/` (https) or `github.com:` (ssh)
_URL_PATH = re.compile(r"github\.com[/:]([^/]+)/([^/\s#?]+)")


@dataclass(frozen=True)
class GithubRepo:
    """A repository on GitHub"""

    owner: str
    """The user or organisation that owns the repository"""

    name: str
    """The repository name, without a `.git` suffix"""

    @property
    def url(self) -> str:
        """The repository's web address"""
        return f"https://github.com/{self.owner}/{self.name}"

    @classmethod
    def parse(cls, url: str | None) -> GithubRepo | None:
        """
        Read the repository from a GitHub URL

        Accepts `https://github.com/owner/repo`, the same with a `.git` suffix, and
        `git@github.com:owner/repo.git`. Anything after the name, such as a path, a
        query or a fragment, is ignored.

        Parameters
        ----------
        url
            The URL to read.

        Returns
        -------
        :
            The repository, or `None` when no GitHub repository can be read from `url`.
        """
        if not url or "github.com" not in url:
            return None
        match = _URL_PATH.search(url)
        if not match:
            return None
        owner, name = match.group(1), match.group(2)
        name = name.removesuffix(".git").rstrip("/")
        if not owner or not name:
            return None
        return cls(owner=owner, name=name)


def token_from_env() -> str | None:
    """
    Read a GitHub API token from the environment

    Returns
    -------
    :
        `GITHUB_TOKEN`, else `GH_TOKEN`, or `None` when neither is set.
    """
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
