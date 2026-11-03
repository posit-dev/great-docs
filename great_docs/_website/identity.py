"""
The site's name and addresses

One `Identity` supplies the site name and addresses for page titles, social
cards, structured data, canonical links, sitemaps and crawler rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from . import page_url, quarto_yml

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import Config


@dataclass(frozen=True)
class Identity:
    """The site's name, serving address and preferred address for links"""

    name: str
    """The site name in page titles, or an empty string when none is known"""

    url: str | None
    """The configured `site_url`, where the site is served, or `None`"""

    base_url: str | None
    """The preferred site address with a trailing slash, or `None` when unknown"""

    @classmethod
    def make(
        cls,
        config: Config,
        build_dir: Path,
        github_owner: str | None,
        github_repo: str | None,
        package_name: str | None,
    ) -> Identity:
        """
        Resolve the site's name and addresses

        Quarto uses `website.title` from the build directory's `_quarto.yml`
        in page titles, so it takes precedence. The name falls back to the
        configured display name, then `package_name`. The preferred address
        is `seo.canonical.base_url`, with fallbacks to `site_url`, then the
        repository's GitHub Pages address.

        Parameters
        ----------
        config
            Project configuration.
        build_dir
            The Quarto project directory. Its `_quarto.yml` may be missing or
            unreadable.
        github_owner
            Owner of the project's GitHub repository, if it has one.
        github_repo
            Name of the project's GitHub repository, if it has one.
        package_name
            The detected package name, if any.

        Returns
        -------
        :
            The site's identity.
        """
        return cls(
            name=_title(build_dir) or config.display_name or package_name or "",
            url=config.site_url,
            base_url=page_url.resolve_base_url(config, github_owner, github_repo),
        )


def _title(build_dir: Path) -> str | None:
    """
    Read the site title from a build directory's `_quarto.yml`

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        A non-empty `website.title`, or `None` when the file is missing,
        unreadable or has no title.
    """
    if not quarto_yml.path(build_dir).exists():
        return None
    try:
        quarto_config = quarto_yml.read(build_dir)
    except (OSError, ValueError):
        return None
    website = quarto_config.get("website")
    if isinstance(website, dict):
        title = cast("dict[str, Any]", website).get("title")
        if isinstance(title, str) and title:
            return title
    return None
