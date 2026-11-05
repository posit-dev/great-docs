"""
Package dependency tables with version constraints and optional PyPI release dates
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from yaml12 import format_yaml

from ..._apiref._render._tables import html_table
from ..._icons import get_icon_svg
from ..._translations import get_translation

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from ..._manifest import Dependency, Manifest
    from ..._remote import Remote
    from ...config import Config

__all__ = ["FILENAME", "write_page"]

FILENAME = "package-info.qmd"

# Widths are percentages in display order: package, version, optional environment marker,
# optional release date and PyPI link. Keys indicate (marker column, release-date column).
_COL_WIDTHS: dict[tuple[bool, bool], tuple[int, ...]] = {
    (False, True): (35, 30, 25, 10),
    (True, True): (28, 24, 20, 20, 8),
    (False, False): (50, 40, 10),
    (True, False): (35, 30, 27, 8),
}


def write_page(
    config: Config,
    build_dir: Path,
    metadata: Manifest,
    remote: Remote,
    *,
    report: Callable[[str], None],
) -> Path | None:
    """
    Write the package-info page listing runtime and optional dependencies

    The page has a table of runtime dependencies, a table for each non-empty optional
    dependency group and a summary of dependency counts and the Python requirement.
    Empty optional groups show a message instead of a table. Each row shows the version
    constraint and a PyPI link. A table includes an environment-marker column if any of
    its dependencies have a marker, and a latest PyPI release-date column if
    `package_info_page.release_dates` is enabled.

    Parameters
    ----------
    config
        The Great Docs configuration. No page is written when `package_info_page` is off
        or the project has no Python component. Set `package_info_page.release_dates`
        to `false` to omit the release-date column and skip PyPI requests.
    build_dir
        The Quarto project directory to write the page into.
    metadata
        The project metadata, read for `dependencies`, `optional_dependencies` and
        `requires_python`. No page is written when all three are empty.
    remote
        The source of PyPI release dates. Queries run only when the page is written and
        release dates are enabled. An unknown date appears as a dash.
    report
        A callback that receives the line announcing the written page.

    Returns
    -------
    :
        The path of the written page, or `None` if no page was written.
    """
    if not config.package_info_page or not config.is_python_project:
        return None

    runtime_deps = metadata.get("dependencies", [])
    optional_deps = metadata.get("optional_dependencies", {})
    requires_python = metadata.get("requires_python", "")

    if not runtime_deps and not optional_deps and not requires_python:
        return None

    lang = config.lang
    title = get_translation("package_info", lang)
    runtime_label = get_translation("runtime_dependencies", lang)
    optional_label = get_translation("optional_dependencies", lang)
    summary_label = get_translation("dependency_summary", lang)
    package_header = get_translation("dep_package", lang)
    version_header = get_translation("dep_version_constraint", lang)
    marker_header = get_translation("dep_environment_marker", lang)

    link_svg = get_icon_svg("external-link", size=14, css_class="")

    all_dep_names = {d["name"] for d in runtime_deps}
    for deps in optional_deps.values():
        all_dep_names |= {d["name"] for d in deps}
    show_dates = config.package_info_page_release_dates
    pypi_dates = remote.pypi_release_dates(all_dep_names) if show_dates else {}

    def dependency_table(deps: list[Dependency]) -> str:
        """
        Format a dependency table with PyPI links and optional release dates

        Parameters
        ----------
        deps
            The dependencies for this table, with names, version constraints and optional
            environment markers.

        Returns
        -------
        :
            The HTML table, with a marker column only if a dependency in this table has
            an environment marker.
        """
        has_markers = any(d.get("marker") for d in deps)
        rows: list[list[str]] = []
        for dep in deps:
            name = dep["name"]
            spec = f"<code>{html.escape(dep['specifier'])}</code>" if dep["specifier"] else "—"
            pypi_cell = (
                f'<a href="https://pypi.org/project/{html.escape(name)}/"'
                f' class="gd-pypi-link">{link_svg}</a>'
            )
            pkg_cell = f'<code class="gd-no-link">{html.escape(name)}</code>'
            row = [pkg_cell, spec]
            if has_markers:
                marker = dep.get("marker")
                row.append(f"<code>{html.escape(marker)}</code>" if marker else "")
            if show_dates:
                row.append(html.escape(pypi_dates.get(name, "—")))
            row.append(pypi_cell)
            rows.append(row)

        headers = [package_header, version_header]
        if has_markers:
            headers.append(marker_header)
        if show_dates:
            headers.append("Last Published")
        headers.append("PyPI")
        return html_table(
            rows,
            headers=headers,
            col_widths=_COL_WIDTHS[has_markers, show_dates],
            table_class="gd-dep-table",
        )

    sections: list[str] = []

    if runtime_deps:
        sections.append(f"## {runtime_label}\n")
        sections.append(dependency_table(runtime_deps))
        sections.append("")

    if optional_deps:
        sections.append(f"## {optional_label}\n")
        for group_name, group_deps in sorted(optional_deps.items()):
            sections.append(f"### `{group_name}`\n")
            if group_deps:
                sections.append(dependency_table(group_deps))
                sections.append("")
            else:
                sections.append("*No dependencies declared.*\n")

    sections.append(f"## {summary_label}\n")

    all_opt_names = {dep["name"] for deps in optional_deps.values() for dep in deps}
    all_names = {dep["name"] for dep in runtime_deps} | all_opt_names

    if requires_python:
        requires_label = get_translation("requires_python", lang)
        sections.append(f"- **{requires_label}:** Python `{requires_python}`")
    sections.append(f"- **{runtime_label}:** {len(runtime_deps)}")
    if optional_deps:
        sections.append(
            f"- **{optional_label}:** {len(optional_deps)} groups"
            f" ({len(all_opt_names)} unique packages)"
        )
    sections.append(f"- **Total unique dependencies:** {len(all_names)}")
    sections.append("")

    body = "\n".join(sections)

    front_matter = format_yaml(
        {
            "title": title,
            "toc": True,
            "sidebar": False,
            "body-classes": "gd-package-info-page",
            "anchor-sections": True,
        }
    )
    content = f"---\n{front_matter.rstrip()}\n---\n\n{body}\n"

    path = build_dir / FILENAME
    _ = path.write_text(content, encoding="utf-8")
    report(f"Created {path}")
    return path
