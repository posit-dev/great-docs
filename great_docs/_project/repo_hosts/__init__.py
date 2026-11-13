"""
Repository host statistics, releases and credentials
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..remote import ReleaseData
    from ..repository import Repository

__all__ = ["RepoHost"]


class RepoHost(Protocol):
    """Repository host operations shared by GitHub and GitLab"""

    def token_from_env(self) -> str | None:
        """Read the host API token from the environment"""
        ...

    def stats(self, repo: Repository, *, report: Callable[[str], None]) -> dict[str, int]:
        """Read known star and fork counts"""
        ...

    def releases(
        self, repo: Repository, maximum: int, *, report: Callable[[str], None]
    ) -> list[ReleaseData]:
        """Read published releases up to the requested maximum"""
        ...
