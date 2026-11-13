"""
GitHub API credentials
"""

from __future__ import annotations

import os

__all__ = ["token_from_env"]


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
