"""
Scripts and stylesheets that Great Docs ships at the site root

`SCRIPTS` lists each file once, in page load order. A file's gate controls
copying into the build directory, listing in `project.resources` and
inclusion in every page.

Every `src` and `href` is root-relative, and Quarto rewrites it relative to
each page in header includes, after-body includes and raw HTML. Quarto leaves
a bare relative path unchanged, so it would load only on pages at the site
root.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._marimo import get_islands_head_html
from . import quarto_yml

if TYPE_CHECKING:
    from ..config import Config
    from .quarto_yml import Slot

__all__ = [
    "SCRIPTS",
    "Script",
    "add_resources",
    "copy",
    "copy_asset",
    "include",
    "include_libraries",
    "named",
    "script_include",
    "script_tag",
    "stylesheet_include",
]

_ASSETS = Path(__file__).parents[1] / "assets"

_FONT_AWESOME = (
    '<link rel="stylesheet" '
    'href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
)


def script_tag(name: str, *, defer: bool = False) -> str:
    """
    Build a `<script>` element that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.
    defer
        Whether the script runs after the document is parsed rather than
        blocking the parser where it appears.

    Returns
    -------
    :
        The element as one line of HTML.
    """
    attributes = " defer" if defer else ""
    return f'<script{attributes} src="/{name}"></script>'


def script_include(name: str, *, defer: bool = False) -> dict[str, str]:
    """
    Build a Quarto include entry that loads a script from the site root

    Parameters
    ----------
    name
        The script's file name at the site root, such as `tooltips.js`.
    defer
        Whether the script runs after the document is parsed rather than
        blocking the parser where it appears.

    Returns
    -------
    :
        A text entry for `include-in-header` or `include-after-body`.
    """
    return {"text": script_tag(name, defer=defer)}


def stylesheet_include(name: str) -> dict[str, str]:
    """
    Build a Quarto include entry that loads a stylesheet from the site root

    Parameters
    ----------
    name
        The stylesheet's file name at the site root, such as `gd-lightbox.css`.

    Returns
    -------
    :
        A text entry for `include-in-header`.
    """
    return {"text": f'<link rel="stylesheet" href="/{name}">'}


def _always(config: Config) -> bool:
    """
    Accept every site

    Parameters
    ----------
    config
        The Great Docs configuration.

    Returns
    -------
    :
        `True`.
    """
    return True


@dataclass(frozen=True)
class Script:
    """A script or stylesheet that Great Docs ships at the site root"""

    name: str
    """The file name at the site root, such as `tooltips.js`"""

    slot: Slot | None = None
    """The include list that loads the file, or `None` when a page or another feature loads it"""

    gate: Callable[[Config], bool] = _always
    """Whether a site uses the file"""

    needs_repository: bool = False
    """Whether a site uses the file only when it has a GitHub repository"""

    defer: bool = False
    """Whether the script runs after the document is parsed"""

    library: bool = False
    """Whether the file loads with the libraries, ahead of the site's own header entries"""

    data: Callable[[Config], str | None] | None = None
    """The text of an include entry that must precede the file's, or `None` when a site needs none"""

    inline: str | None = None
    """
    A name the script defines, or `None` to load the script from the site root

    A script with a name is embedded in each page when the build directory holds
    it, and the name identifies its entry.
    """

    directory: str = ""
    """The directory, relative to the packaged assets, that holds the file"""

    def used(self, config: Config, *, has_repository: bool) -> bool:
        """
        Check whether the site configuration and repository satisfy the file's gate

        Parameters
        ----------
        config
            The Great Docs configuration.
        has_repository
            Whether the site has a GitHub repository.

        Returns
        -------
        :
            Whether the configuration passes the gate and any repository requirement is met.
        """
        return self.gate(config) and (has_repository or not self.needs_repository)

    def is_entry(self, entry: object) -> bool:
        """
        Report whether an include entry loads the file

        Parameters
        ----------
        entry
            An include entry.

        Returns
        -------
        :
            Whether the entry contains the file name or, for an embedded script,
            the name defined by the script.
        """
        text = str(entry)
        return self.name in text or (self.inline is not None and self.inline in text)

    def entry(self, build_dir: Path | None = None) -> dict[str, str]:
        """
        Build the include entry that loads the file

        Parameters
        ----------
        build_dir
            The Quarto project directory containing scripts to embed, or `None`
            to load the file from the site root.

        Returns
        -------
        :
            A text entry that embeds the script when `inline` is set and the
            build directory contains the file. Otherwise, an entry that loads
            the file from the site root.
        """
        if self.inline is not None and build_dir is not None:
            embedded = build_dir / self.name
            if embedded.is_file():
                return {"text": f"<script>{embedded.read_text(encoding='utf-8')}</script>"}
        if self.name.endswith(".css"):
            return stylesheet_include(self.name)
        return script_include(self.name, defer=self.defer)


def _marimo_runtime(config: Config) -> str:
    """
    Build the header tags that load the marimo islands runtime

    Parameters
    ----------
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The HTML for the configured marimo version.
    """
    return get_islands_head_html(config.marimo_version)


def _sidebar_filter_min_items(config: Config) -> str | None:
    """
    Build a script that sets the sidebar filter's custom minimum item count

    Parameters
    ----------
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The script, or `None` when the filter uses its default of 20 items.
    """
    min_items = config.sidebar_filter_min_items
    if min_items == 20:
        return None
    return f'<script>document.body.dataset.sidebarFilterMinItems = "{min_items}";</script>'


def _dark_mode_disabled(config: Config) -> str | None:
    """
    Build the tag that tells `theme-init.js` to ignore a stored dark-mode preference

    Parameters
    ----------
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The tag, or `None` when the site has a dark-mode toggle.
    """
    if config.dark_mode_toggle:
        return None
    return '<meta name="gd-dark-mode" content="disabled">'


_HEADER: Slot = "include-in-header"
_AFTER_BODY: Slot = "include-after-body"
_LIGHTBOX = "_extensions/gd-lightbox"

SCRIPTS: tuple[Script, ...] = (
    Script(
        "marimo-islands.js",
        _HEADER,
        lambda c: c.marimo_enabled,
        defer=True,
        library=True,
        data=_marimo_runtime,
    ),
    Script("marimo-islands.css", _HEADER, lambda c: c.marimo_enabled, library=True),
    Script("gd-lightbox.css", _HEADER, library=True, directory=_LIGHTBOX),
    Script("gd-lightbox.js", _HEADER, defer=True, library=True, directory=_LIGHTBOX),
    Script("gd-lightbox-compare.css", _HEADER, library=True, directory=_LIGHTBOX),
    Script("gd-lightbox-compare.js", _HEADER, defer=True, library=True, directory=_LIGHTBOX),
    Script("gd-lightbox-annotate.css", _HEADER, library=True, directory=_LIGHTBOX),
    Script("gd-lightbox-annotate.js", _HEADER, defer=True, library=True, directory=_LIGHTBOX),
    Script("theme-init.js", _HEADER, data=_dark_mode_disabled),
    Script("announcement-banner.js", gate=lambda c: c.announcement is not None),
    Script(
        "github-widget.js",
        _AFTER_BODY,
        lambda c: c.github_style == "widget",
        needs_repository=True,
    ),
    Script("copy-page.js", _AFTER_BODY, lambda c: c.markdown_pages_widget),
    Script("sidebar-wrap.js", _AFTER_BODY),
    Script("sidebar-float.js", _AFTER_BODY),
    Script(
        "sidebar-filter.js",
        _AFTER_BODY,
        lambda c: c.sidebar_filter_enabled,
        data=_sidebar_filter_min_items,
    ),
    Script("dark-mode-toggle.js", _AFTER_BODY, lambda c: c.dark_mode_toggle),
    Script("back-to-top.js", _AFTER_BODY, lambda c: c.back_to_top),
    Script("on-this-page.js", _AFTER_BODY, lambda c: c.back_to_top),
    Script("wide-layout.js", _AFTER_BODY, lambda c: c.wide_layout_enabled),
    Script("keyboard-nav.js", _AFTER_BODY, lambda c: c.keyboard_nav),
    Script("copy-code.js", _AFTER_BODY),
    Script("details.js", _AFTER_BODY),
    Script("mermaid-renderer.js", _AFTER_BODY),
    Script("page-metadata.js", _AFTER_BODY, lambda c: c.show_dates),
    Script("page-tags.js", _AFTER_BODY, lambda c: c.tags_show_on_pages),
    Script(
        "page-status-badges.js",
        _AFTER_BODY,
        lambda c: c.page_status_enabled,
        inline="renderPageBadge",
    ),
    Script("tooltips.js", _AFTER_BODY),
    Script("color-swatch.js", _AFTER_BODY),
    Script("responsive-tables.js", _AFTER_BODY),
    Script("video-embed.js", _AFTER_BODY),
    Script("version-selector.js", gate=lambda c: c.has_versions),
    Script("navbar-widgets.js", _AFTER_BODY),
    Script("navbar-style.js", gate=lambda c: c.navbar_style is not None),
    Script("content-style.js", gate=lambda c: c.content_style is not None),
    Script("starfield.js", gate=lambda c: c.hero_starfield),
    Script("skill-switcher.js", gate=lambda c: len(c.skill_skills) > 1),
)


def named(name: str) -> Script:
    """
    Look up a script or stylesheet by its site-root file name

    Parameters
    ----------
    name
        The file name at the site root.

    Returns
    -------
    :
        The table row describing the file.

    Raises
    ------
    KeyError
        If the table has no such file.
    """
    for script in SCRIPTS:
        if script.name == name:
            return script
    raise KeyError(name)


def copy(config: Config, build_dir: Path, *, has_repository: bool) -> None:
    """
    Copy the files a site uses from the packaged assets into the build directory

    Parameters
    ----------
    config
        The Great Docs configuration.
    build_dir
        The Quarto project directory.
    has_repository
        Whether the site has a GitHub repository.

    Returns
    -------
    :
    """
    for script in SCRIPTS:
        if script.used(config, has_repository=has_repository):
            source = _ASSETS / script.directory / script.name
            if source.exists():
                _ = shutil.copy2(source, build_dir / script.name)


def copy_asset(name: str, build_dir: Path) -> None:
    """
    Copy a packaged script or stylesheet into the build directory

    Parameters
    ----------
    name
        The file name at the site root, such as `reference-switcher.js`.
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
    """
    _ = shutil.copy2(_ASSETS / name, build_dir / name)


def add_resources(config: Config, quarto_config: dict[str, Any], *, has_repository: bool) -> None:
    """
    List the files a site uses in `project.resources`, in table order

    Parameters
    ----------
    config
        The Great Docs configuration.
    quarto_config
        The Quarto configuration, changed in place.
    has_repository
        Whether the site has a GitHub repository.

    Returns
    -------
    :
    """
    quarto_yml.add_resources(
        quarto_config,
        (script.name for script in SCRIPTS if script.used(config, has_repository=has_repository)),
    )


def include_libraries(config: Config, quarto_config: dict[str, Any]) -> None:
    """
    Load Font Awesome and the libraries a site uses in every page's header

    Parameters
    ----------
    config
        The Great Docs configuration.
    quarto_config
        The Quarto configuration, changed in place.

    Returns
    -------
    :
    """
    headers = quarto_yml.includes(quarto_config, _HEADER)
    if not any("font-awesome" in str(entry).lower() for entry in headers):
        headers.append({"text": _FONT_AWESOME})
    for script in SCRIPTS:
        if script.library and script.used(config, has_repository=False):
            _include(config, quarto_config, script)


def include(
    config: Config, quarto_config: dict[str, Any], build_dir: Path, *, has_repository: bool
) -> None:
    """
    Load the site's own scripts and stylesheets in every page, in table order

    Libraries and files loaded by another feature or an individual page are
    excluded. Repeated calls do not duplicate entries.

    Parameters
    ----------
    config
        The Great Docs configuration.
    quarto_config
        The Quarto configuration, changed in place.
    build_dir
        The Quarto project directory, which holds the scripts to embed.
    has_repository
        Whether the site has a GitHub repository.

    Returns
    -------
    :
    """
    for script in SCRIPTS:
        if (
            script.slot is not None
            and not script.library
            and script.used(config, has_repository=has_repository)
        ):
            _include(config, quarto_config, script, build_dir)


def _include(
    config: Config, quarto_config: dict[str, Any], script: Script, build_dir: Path | None = None
) -> None:
    """
    Add a file's include entry and any preceding data entry once each

    Parameters
    ----------
    config
        The Great Docs configuration.
    quarto_config
        The Quarto configuration, changed in place.
    script
        The table row for a file with an include slot.
    build_dir
        The Quarto project directory, which holds the scripts to embed, or `None`
        to load the file from the site root.

    Returns
    -------
    :
    """
    assert script.slot is not None
    items = quarto_yml.includes(quarto_config, script.slot)
    if not any(script.is_entry(item) for item in items):
        items.append(script.entry(build_dir))
    data = script.data(config) if script.data is not None else None
    if data is not None:
        quarto_yml.add_include(quarto_config, script.slot, {"text": data}, before=script.name)
