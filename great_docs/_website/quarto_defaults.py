"""
Quarto project defaults and settings from `site`

Project defaults set the output directory, pre-render scripts and freeze mode.
HTML defaults merge the user's `site` mapping into `format.html` and add Great
Docs' theme, signature grammar, stylesheets and header includes. Extension
settings register Great Docs' Lua filters and publish the interlinks inventory.

Include entries from `site` follow the build's entries. User scripts can read
Great Docs' globals, and user styles can override Great Docs' styles.
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

    from .._project.layout import Layout

_FILTERS = ("output-title", "details", "gd-lightbox", "interlinks")
"""Great Docs' Lua filters, in the order Quarto runs them"""

_INCLUDES = ("include-in-header", "include-before-body", "include-after-body")
"""`format.html` keys whose `site` entries join the build's entries"""


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

    The `site` mapping overrides `format.html` key by key, except that its
    include entries are appended to the existing include lists.

    Great Docs disables Quarto's code-copy button and lightbox in favour of
    its own scripts, and HTML table processing to preserve styled tables.
    It adds its theme, signature grammar and stylesheets, and appends the
    user's `include_in_header` entries. The user's `site.tbl-colwidths` and
    any existing heading shift take precedence over the corresponding defaults.

    The Great Docs theme is inserted before the first user stylesheet, or
    after all built-in themes if there are no stylesheets. An existing Great
    Docs theme entry keeps its position. For a mapping with `light` and `dark`
    entries, these placement rules apply to each mode.

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
    settings = {key: value for key, value in site.items() if key not in _INCLUDES}
    formats = cast("dict[str, Any]", quarto_config["format"])
    html = Config._merge(formats["html"], settings)  # pyright: ignore[reportPrivateUsage]
    formats["html"] = html
    for key, user_entries in _site_includes(config).items():
        entries = quarto_yml.entries(html, key)
        for entry in user_entries:
            if entry not in entries:
                entries.append(entry)

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

    # The `light` and `dark` keys select modes; their values name the themes.
    theme = cast("str | list[Any] | dict[str, Any]", html["theme"])
    if isinstance(theme, dict):
        html["theme"] = {mode: _with_great_docs_theme(entry) for mode, entry in theme.items()}
    else:
        html["theme"] = _with_great_docs_theme(theme)

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
    quarto_yml.entries(quarto_config, "filters").extend(_FILTERS)
    quarto_yml.add_resources(quarto_config, [INVENTORY_FILENAME])


def register_site_includes(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Place the `site` include entries after the build's entries

    Call this after all other include-list updates. The user's entries retain
    their order in `site`.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a
        `format.html` mapping.
    config
        Project configuration.

    Returns
    -------
    :
    """
    html = cast("dict[str, Any]", quarto_config["format"]["html"])
    for key, user_entries in _site_includes(config).items():
        entries = quarto_yml.entries(html, key)
        entries[:] = [entry for entry in entries if entry not in user_entries] + user_entries


def _site_includes(config: Config) -> dict[str, list[Any]]:
    """
    Return the non-null include settings from `site` as lists

    Parameters
    ----------
    config
        Project configuration.

    Returns
    -------
    :
        Each include key with a non-null value in `site`, mapped to a list of
        its entries.
    """
    includes: dict[str, list[Any]] = {}
    for key in _INCLUDES:
        value: Any = config.site_quarto.get(key)
        if value is not None:
            includes[key] = list(cast("list[Any]", value)) if isinstance(value, list) else [value]
    return includes


def _with_great_docs_theme(theme: str | list[Any]) -> str | list[Any]:
    """
    Add Great Docs' theme without moving an existing entry

    Later Quarto theme entries take precedence. User styles override Great Docs,
    which overrides preceding built-in themes.

    Parameters
    ----------
    theme
        A theme name or list shared by both modes, or used by one mode.

    Returns
    -------
    :
        `theme` unchanged if it contains `great-docs.scss`. Otherwise, a new list
        with `great-docs.scss` inserted before the first user stylesheet, or at
        the end if there are no user stylesheets.
    """
    themes = [theme] if isinstance(theme, str) else list(theme)
    if "great-docs.scss" in themes:
        return theme
    files = (i for i, entry in enumerate(themes) if _is_style_file(entry))
    themes.insert(next(files, len(themes)), "great-docs.scss")
    return themes


def _is_style_file(theme: object) -> bool:
    """
    Check whether a theme entry names a `.scss` or `.css` file

    Parameters
    ----------
    theme
        One entry of `format.html.theme`.

    Returns
    -------
    :
        `True` for a string with a `.scss` or `.css` suffix; `False` otherwise.
    """
    return isinstance(theme, str) and Path(theme).suffix in (".scss", ".css")
