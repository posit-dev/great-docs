"""
Ordered assembly of Great Docs' site-wide Quarto settings

The merge order determines the load order of scripts, stylesheets and filters.
Later settings also depend on entries added by earlier settings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from .._project.manifest import Manifest
from .._versions import selector as version_selector
from . import (
    appearance,
    footer,
    i18n,
    markdown_pages,
    metadata_partial,
    page_url,
    quarto_defaults,
    quarto_yml,
    scripts,
    social_cards,
)
from . import resources as project_resources
from .navigation import brand, reference_switcher
from .navigation import icons as nav_icons
from .navigation import label as nav_label
from .navigation import navbar as nav_navbar

if TYPE_CHECKING:
    from .._build.facts import Facts
    from .._contribution import Contribution
    from .._project.github import GithubRepo
    from .._project.layout import Layout
    from ..config import Config
    from .identity import Identity

__all__ = ["assemble"]


def assemble(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    *,
    repo: GithubRepo | None,
    facts: Facts,
    identity: Identity,
    package_name: str | None,
    metadata: Manifest,
    has_api_reference: bool,
    has_cli_reference: bool,
    contributions: Sequence[Contribution],
    report: Callable[[str], None],
    warn: Callable[[str], None],
) -> None:
    """
    Merge Great Docs' site-wide settings into a Quarto configuration

    Add pre-render scripts, theme, resources, page scripts, stylesheets, navigation,
    footer, canonical links and social cards. Apply the build steps' contributions
    in order and preserve unrelated configuration. Copy referenced files, including
    logos, header includes, the metadata partial and the social card image, into the
    build directory.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a `project`
        mapping and a `format.html` mapping.
    config
        Project configuration.
    layout
        Project directories for locating source files and writing build resources.
    repo
        The project's GitHub repository, if it has one.
    facts
        The repository's star and fork counts and its latest release.
    identity
        The site's name and addresses.
    package_name
        The detected package name, if any.
    metadata
        The project's package metadata, including its authors, maintainers and URLs.
    has_api_reference
        Whether the site has an API reference.
    has_cli_reference
        Whether the site has command-line reference pages.
    contributions
        Navigation, resources, render exclusions and script data recorded by build
        steps, in build step order.
    report
        Callback for messages about the settings, such as the bibliography files
        used and unknown icon names.
    warn
        Callback for warnings about the social card image.

    Returns
    -------
    :

    Raises
    ------
    KeyError
        If `quarto_config` lacks a `project` or `format.html` mapping.
    FileNotFoundError
        If a header include file does not exist.
    """
    has_repository = repo is not None
    build_dir = layout.build_dir

    quarto_defaults.register(quarto_config, config, layout)
    scripts.add_resources(config, quarto_config, has_repository=has_repository)
    project_resources.register(quarto_config, config, layout)
    quarto_defaults.register_site(quarto_config, config, layout, report=report)
    scripts.include_libraries(config, quarto_config)

    urls = cast("Mapping[str, Any]", metadata.get("urls", {}))
    brand.register(
        quarto_config,
        config,
        layout,
        identity=identity,
        package_name=package_name,
        repo=repo,
        facts=facts,
        documentation_url=urls.get("Documentation"),
        report=report,
    )

    # Table order preserves the order in which pages load the site's scripts.
    scripts.include(config, quarto_config, build_dir, has_repository=has_repository)
    scripts.include_webmcp_settings(
        config,
        quarto_config,
        has_api_reference=has_api_reference,
        has_cli_reference=has_cli_reference,
    )

    # Contributed links and data require the navbar and script includes to exist.
    # Apply them before configuring the reference switcher, icons and navbar order.
    for contribution in contributions:
        quarto_yml.apply(quarto_config, contribution, config)

    appearance.register_wide_layout(quarto_config, config)
    reference_switcher.register(
        quarto_config, config, build_dir, has_api_reference=has_api_reference
    )
    nav_icons.register(quarto_config, config, report=report)

    # The API reference step adds the reference sidebar later, when it finds exports.
    website = cast("dict[str, Any]", quarto_config["website"])
    if "sidebar" not in website:
        website["sidebar"] = []

    footer.register(quarto_config, config, metadata)
    appearance.register(quarto_config, config)
    brand.register_release(quarto_config, config, facts)
    quarto_defaults.register_extensions(quarto_config)

    # Quarto renders page titles and translation metadata from this partial.
    metadata_partial.write(quarto_config, config, layout, report=report)
    nav_label.register(quarto_config, config)
    i18n.register(quarto_config, config)

    # The user's header includes must be present before these checks to avoid
    # duplicate canonical links and Open Graph tags. Both use the preferred page address.
    page_url.register(
        quarto_config,
        config,
        identity.base_url,
        build_dir,
        og_url=social_cards.applies(quarto_config, config, build_dir),
    )
    card_image_url = social_cards.publish_image(config, layout, identity.base_url, report=warn)
    social_cards.register(quarto_config, config, card_image_url, build_dir)
    markdown_pages.register(quarto_config, config)

    # Reorder after every step above that adds a navbar item.
    nav_navbar.reorder(quarto_config, config)

    if config.has_versions:
        version_selector.register(quarto_config, config)

    quarto_defaults.register_site_includes(quarto_config, config)
