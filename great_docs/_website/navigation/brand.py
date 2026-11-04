"""
The site's brand: its title, logo, favicons, GitHub entry and latest release

The navbar shows the site title or logo on the left and the GitHub entry on the
right. Logo images and favicons are copied or generated into the Quarto project
directory each time the configuration is written.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from ..._content import publish
from .. import branding, quarto_yml
from . import github, release

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..._build.facts import Facts
    from ..._github import GithubRepo
    from ..._layout import Layout
    from ...config import Config
    from ..identity import Identity


def register(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    build_dir: Path,
    *,
    identity: Identity,
    package_name: str | None,
    repo: GithubRepo | None,
    facts: Facts,
    documentation_url: str | None,
    report: Callable[[str], None],
) -> None:
    """
    Add the site's address, title, navbar, logo and favicons

    Set `website.site-url` to the site address when available. Enable page
    navigation and set the site title unless the Quarto configuration already
    sets them. Create a missing navbar, or remove the legacy `Home` link from
    the left side of an existing navbar. Add the GitHub entry on the right when
    the project has a GitHub repository.

    Show a configured logo, or one found at a conventional path, in place of
    the navbar title unless `logo.show_title` is set. Copy local logo images into
    `build_dir`. When a logo is present, generate favicons from the configured
    `favicon` or a local logo image and link them from every page.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a `format.html`
        mapping.
    config
        Project configuration.
    layout
        The project's directories, for finding the logo and favicon sources.
    build_dir
        The Quarto project directory that receives logo and favicon files.
    identity
        The site's name and address.
    package_name
        The detected package name, for finding a logo and as its alternative text.
    repo
        The project's GitHub repository, or `None` when it has none.
    facts
        The repository's star and fork counts for the GitHub widget.
    documentation_url
        The project's documentation address, which locates favicons when the
        configuration has no `website.site-url`.
    report
        A callback for warnings about missing images and favicon generation progress.

    Returns
    -------
    :

    Raises
    ------
    ValueError
        If a logo would overwrite a different file in `build_dir`.
    """
    website = cast("dict[str, Any]", quarto_config.setdefault("website", {}))
    if identity.url:
        website["site-url"] = identity.url
    _ = website.setdefault("page-navigation", True)
    if "title" not in website:
        title = identity.name or _binary_name(config, layout.package_root)
        if title:
            website["title"] = title

    _add_navbar(website, config, repo, facts)

    logo = config.logo
    if logo is None:
        logo = branding.detect_logo(layout.source_dir, package_name)
    if logo is not None:
        logo_file = _add_logo(quarto_config, config, layout, build_dir, logo, package_name, report)
        _add_favicons(
            quarto_config, config, layout, build_dir, logo_file, documentation_url, report
        )


def register_release(quarto_config: dict[str, Any], config: Config, facts: Facts) -> None:
    """
    Show the latest release beside the navbar title, or in the logo's tooltip

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration, for the language of the release date.
    facts
        The repository's latest release. Without one, any badge or tooltip from an
        earlier write is removed.

    Returns
    -------
    :
    """
    release.add_to_navbar(quarto_config, facts.latest_release, config.lang)


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
        The Go binary name, or the first Rust binary name if no Go name is found.
        `None` when neither CLI reference is enabled and detected.
    """
    name = None
    if config.go_cli_enabled:
        from ..._cliref.go import detect_go_cli_project

        go_project = detect_go_cli_project(package_root)
        if go_project:
            name = go_project.binary_name
    if not name and config.rust_cli_enabled:
        from ..._cliref.rust import detect_rust_cli_project

        rust_project = detect_rust_cli_project(package_root)
        if rust_project:
            name = rust_project.binary_names[0]
    return name


def _add_navbar(
    website: dict[str, Any], config: Config, repo: GithubRepo | None, facts: Facts
) -> None:
    """
    Create the navbar or update an existing one, with the GitHub entry on the right

    Parameters
    ----------
    website
        The `website` mapping of the Quarto configuration, updated in place.
    config
        Project configuration, for the GitHub entry's style.
    repo
        The project's GitHub repository, or `None` when it has none.
    facts
        The repository's star and fork counts for the GitHub widget.

    Returns
    -------
    :
    """
    item = (
        github.navbar_item(repo.url, repo.owner, repo.name, config.github_style, facts.github_stats)
        if repo is not None
        else None
    )
    if "navbar" not in website:
        navbar: dict[str, Any] = {"left": []}
        if item:
            navbar["right"] = [item]
        website["navbar"] = navbar
        return

    navbar = cast("dict[str, Any]", website["navbar"])
    if item:
        github.set_navbar_item(navbar, item)
    # The site title in the navbar already links to the home page.
    if "left" in navbar:
        navbar["left"] = [
            entry
            for entry in cast("list[Any]", navbar["left"])
            if not (isinstance(entry, dict) and cast("dict[str, Any]", entry).get("text") == "Home")
        ]


def _add_logo(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    build_dir: Path,
    logo: dict[str, Any],
    package_name: str | None,
    report: Callable[[str], None],
) -> Path | None:
    """
    Show the logo in the navbar, copying its images into the Quarto project

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    layout
        The project's directories.
    build_dir
        The Quarto project directory.
    logo
        The logo settings: `light` and, optionally, `dark`, `alt` and `href`.
        Image paths are relative to the documentation source directory; `light`
        may also be a URL.
    package_name
        The detected package name, the alternative text when neither `alt` nor
        the display name is set.
    report
        A callback for warnings about missing images.

    Returns
    -------
    :
        The light logo image when it is a local file, otherwise `None`.
    """
    navbar = cast("dict[str, Any]", quarto_config["website"]["navbar"])
    light = cast("str", logo["light"])
    dark = cast("str | None", logo.get("dark"))

    light_src = layout.source_dir / light
    logo_file = light_src if light_src.is_file() else None
    if logo_file is not None:
        light_name = logo_file.name
        if dark and dark != light and light_name == Path(dark).name:
            light_name = f"logo-light{logo_file.suffix}"
        _ = publish.copy_asset(layout, logo_file, build_dir / light_name)
        navbar["logo"] = light_name
    elif urlsplit(light).scheme or light.startswith("//"):
        navbar["logo"] = light
    else:
        report(f"Warning: Logo file not found: {light_src}")

    if dark and dark != light:
        dark_src = layout.source_dir / dark
        if dark_src.is_file():
            _ = publish.copy_asset(layout, dark_src, build_dir / dark_src.name)
            navbar["logo-dark"] = dark_src.name
            # `dark-mode-toggle.js` needs the dark logo in the rendered site
            # and its path in each page's metadata to swap the navbar image.
            quarto_yml.add_resources(quarto_config, [dark_src.name])
            quarto_yml.add_include(
                quarto_config,
                "include-in-header",
                {"text": f'<meta name="gd-logo-dark" content="{dark_src.name}">'},
                marker="gd-logo-dark",
            )
        else:
            report(f"Warning: Dark logo file not found: {dark_src}")

    alt = logo.get("alt") or config.display_name or package_name
    if alt:
        navbar["logo-alt"] = alt
    href = logo.get("href")
    if href:
        navbar["logo-href"] = href
    if not config.logo_show_title:
        navbar["title"] = False
    return logo_file


def _add_favicons(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    build_dir: Path,
    logo_file: Path | None,
    documentation_url: str | None,
    report: Callable[[str], None],
) -> None:
    """
    Generate the site's favicons and link them from every page

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration. Its `favicon` takes precedence over the logo.
    layout
        The project's directories.
    build_dir
        The Quarto project directory that receives the favicons.
    logo_file
        The local light logo image to generate favicons from, if any.
    documentation_url
        The site address to use when the configuration has no `website.site-url`.
    report
        A callback for warnings about missing favicons and generation progress.

    Returns
    -------
    :
    """
    website = cast("dict[str, Any]", quarto_config["website"])
    favicon = config.favicon
    generated: dict[str, str] = {}
    if favicon is not None:
        icon = favicon.get("icon")
        if icon:
            source = layout.source_dir / icon
            if source.is_file():
                generated = branding.generate_favicons(source, build_dir, report=report)
                if generated.get("icon"):
                    website["favicon"] = generated["icon"]
                else:
                    # Formats other than SVG and PNG are used as they are.
                    _ = shutil.copy2(source, build_dir / source.name)
                    website["favicon"] = source.name
            else:
                report(f"Warning: Favicon file not found: {source}")
    elif logo_file is not None:
        generated = branding.generate_favicons(logo_file, build_dir, report=report)
        if generated.get("icon"):
            website["favicon"] = generated["icon"]

    if not generated:
        return
    quarto_yml.add_resources(quarto_config, dict.fromkeys(generated.values()))

    # Quarto does not rewrite paths inside raw header HTML. Relative favicon
    # URLs would break on pages below the site root.
    site_url = cast("str", website.get("site-url") or documentation_url or "")
    if not site_url:
        return
    site_url = site_url.split("#")[0]
    if not site_url.endswith("/"):
        site_url += "/"

    links: list[str] = []
    if generated.get("icon", "").endswith(".ico"):
        links.append(
            f'<link rel="icon" type="image/x-icon" href="{site_url}favicon.ico" sizes="48x48">'
        )
    if generated.get("icon-svg"):
        links.append(f'<link rel="icon" type="image/svg+xml" href="{site_url}favicon.svg">')
    if generated.get("icon-32"):
        links.append(
            f'<link rel="icon" type="image/png" sizes="32x32" href="{site_url}favicon-32x32.png">'
        )
    if generated.get("icon-16"):
        links.append(
            f'<link rel="icon" type="image/png" sizes="16x16" href="{site_url}favicon-16x16.png">'
        )
    if generated.get("apple-touch-icon"):
        links.append(
            f'<link rel="apple-touch-icon" sizes="180x180" href="{site_url}apple-touch-icon.png">'
        )
    for link in links:
        quarto_yml.add_include(quarto_config, "include-in-header", {"text": link}, marker=link)
