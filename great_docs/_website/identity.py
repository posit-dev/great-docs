"""
The site's name and addresses

One `Identity` supplies the site name and addresses for page titles, social
cards, structured data, canonical links, sitemaps and crawler rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import page_url

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
        package_root: Path,
        github_owner: str | None,
        github_repo: str | None,
        package_name: str | None,
    ) -> Identity:
        """
        Resolve the site's name and addresses

        The name is the configured display name, else `package_name`, else the
        name of the project's Go or Rust command-line program when its CLI
        reference is enabled, else an empty string. The preferred address is
        `seo.canonical.base_url`, else `site_url`, else the repository's GitHub
        Pages address.

        Parameters
        ----------
        config
            Project configuration.
        package_root
            The project's root directory, searched for a Go or Rust program when
            its CLI reference is enabled.
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
            name=config.display_name or package_name or _binary_name(config, package_root) or "",
            url=config.site_url,
            base_url=page_url.resolve_base_url(config, github_owner, github_repo),
        )


def _binary_name(config: Config, package_root: Path) -> str | None:
    """
    Find the name of the project's Go or Rust command-line program

    Parameters
    ----------
    config
        Project configuration, which enables the Go and Rust CLI references.
    package_root
        The project's root directory.

    Returns
    -------
    :
        The Go binary name when the Go CLI reference is enabled and a Go project
        is detected, else the first Rust binary name under the same conditions
        for Rust, else `None`.
    """
    name = None
    if config.go_cli_enabled:
        from .._cliref.go import detect_go_cli_project

        go_project = detect_go_cli_project(package_root)
        if go_project:
            name = go_project.binary_name
    if not name and config.rust_cli_enabled:
        from .._cliref.rust import detect_rust_cli_project

        rust_project = detect_rust_cli_project(package_root)
        if rust_project:
            name = rust_project.binary_names[0]
    return name
