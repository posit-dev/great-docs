"""
Quarto project defaults and settings from `site`

Project defaults set the output directory, pre-render scripts and freeze mode.
HTML defaults merge the user's `site` mapping into `format.html` and add Great
Docs' theme, signature grammar, stylesheets and header includes. Extension
settings register Great Docs' Lua filters and publish the interlinks inventory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .._content import publish
from .._interlinks.sphinx_inventory import INVENTORY_FILENAME
from ..config import Config
from . import i18n, quarto_yml

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._layout import Layout

_FILTERS = ("output-title", "details", "gd-lightbox", "interlinks")
"""Great Docs' Lua filters, in the order Quarto runs them"""


def register(quarto_config: dict[str, Any], config: Config, layout: Layout) -> None:
    """
    Set the output directory, the pre-render scripts and the freeze mode

    The freeze restore script runs first when freeze mode is configured or a
    freeze cache exists. The user's `pre_render` scripts follow it. A single
    script is stored as a string.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a `project`
        mapping.
    config
        Project configuration.
    layout
        The project's directories.

    Returns
    -------
    :
    """
    project = cast("dict[str, Any]", quarto_config["project"])
    project["output-dir"] = "_site"

    pre_render: list[str] = []
    if config.freeze is not None or layout.freeze_dir.is_dir():
        pre_render.append("scripts/restore-freeze.py")
    for script in config.pre_render:
        entry = f"scripts/{Path(script).name}"
        if entry not in pre_render:
            pre_render.append(entry)
    if pre_render:
        project["pre-render"] = pre_render[0] if len(pre_render) == 1 else pre_render

    if config.freeze is not None:
        execute = cast("dict[str, Any]", quarto_config.setdefault("execute", {}))
        execute["freeze"] = config.freeze


def register_site(
    quarto_config: dict[str, Any],
    config: Config,
    layout: Layout,
    *,
    report: Callable[[str], None],
) -> None:
    """
    Merge the `site` settings into `format.html` and add Great Docs' HTML defaults

    The `site` mapping overrides `format.html` key by key.

    Great Docs disables Quarto's code-copy button and lightbox in favour of
    its own scripts, and HTML table processing to preserve styled tables.
    It adds its theme, signature grammar and stylesheets, and appends the
    user's `include_in_header` entries. The user's `site.tbl-colwidths` and
    any existing heading shift take precedence over the corresponding defaults.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a
        `format.html` mapping with a `theme`.
    config
        Project configuration.
    layout
        Project directories. Header include files are copied from the source
        directory to `_includes/` in the build directory.
    report
        Callback for messages naming the bibliography files used by the site.

    Returns
    -------
    :

    Raises
    ------
    FileNotFoundError
        If a header include file does not exist.
    """
    site = config.site_quarto
    formats = cast("dict[str, Any]", quarto_config["format"])
    html = Config._merge(formats["html"], site)  # pyright: ignore[reportPrivateUsage]
    formats["html"] = html

    i18n.register_toc_title(quarto_config, config)

    html["code-copy"] = False
    quarto_config["lightbox"] = False

    # The build directory holds copies of these files under their basenames.
    # Quarto localises the references heading from `lang`. A custom
    # `reference-section-title` would become a paragraph after the heading
    # shift and duplicate Quarto's appendix heading.
    if config.bibliography:
        names = [Path(file).name for file in config.bibliography]
        quarto_config["bibliography"] = names[0] if len(names) == 1 else names
        report(f"Using bibliography: {', '.join(names)}")
    if config.csl:
        quarto_config["csl"] = Path(config.csl).name

    i18n.register_quarto_strings(quarto_config, config)

    # Bootstrap styling would alter tables that already have styles, such as GT tables.
    html["html-table-processing"] = "none"
    # Pandoc can derive column widths from the separator line of long pipe
    # tables. The browser and responsive table script size columns by content.
    if "tbl-colwidths" not in site:
        html["tbl-colwidths"] = False
    # Dark mode puts diagrams on a light background, so one theme serves both.
    html["mermaid"] = {"theme": "default"}

    theme = cast("str | list[Any]", html["theme"])
    if "great-docs.scss" not in theme:
        themes = [theme] if isinstance(theme, str) else theme
        themes.append("great-docs.scss")
        html["theme"] = themes

    grammars = cast("str | list[Any]", html.get("syntax-definitions") or [])
    if isinstance(grammars, str):
        grammars = [grammars]
    if "pythonsignature.xml" not in grammars:
        grammars.append("pythonsignature.xml")
    html["syntax-definitions"] = grammars

    if config.css:
        html["css"] = [Path(file).name for file in config.css]

    if "shift-heading-level-by" not in html:
        html["shift-heading-level-by"] = -1

    headers = quarto_yml.includes(quarto_config, "include-in-header")
    for entry in config.include_in_header:
        file = entry.get("file")
        if isinstance(file, str):
            source = layout.source_dir / file
            if not source.is_file():
                raise FileNotFoundError(f"Header include file not found: {source}")
            destination = layout.build_dir / "_includes" / source.name
            _ = publish.copy_asset(layout, source, destination)
            entry = {**entry, "file": destination.relative_to(layout.build_dir).as_posix()}
        if entry not in headers:
            headers.append(entry)


def register_extensions(quarto_config: dict[str, Any]) -> None:
    """
    Register Great Docs' Lua filters and publish the interlinks inventory

    Quarto copies the inventory into the rendered site as a resource so
    other projects can link to its documented objects.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.

    Returns
    -------
    :
    """
    filters = quarto_yml.entries(quarto_config, "filters")
    for name in _FILTERS:
        if name not in filters:
            filters.append(name)
    quarto_yml.add_resources(quarto_config, [INVENTORY_FILENAME])
