"""API evolution markers and version badges in source pages"""

from __future__ import annotations

import re as _re
import tomllib
from pathlib import Path

from great_docs._api_evolution.compare import diff_snapshots
from great_docs._api_evolution.model import ApiSnapshot
from great_docs._api_evolution.render import _escape_html, render_evolution_table
from great_docs._build.steps import USER_CODE_ERRORS

EVOLUTION_ERRORS: tuple[type[Exception], ...] = (*USER_CODE_ERRORS, tomllib.TOMLDecodeError)


_EVOLUTION_MARKER_RE = _re.compile(
    r"<!--\s*%evolution\b([^>]*?)-->",
    _re.DOTALL,
)


_MARKER_ATTR_RE = _re.compile(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+))""")


def _parse_marker_attrs(attr_string: str) -> dict[str, str]:
    """Parse `key="value"` attributes from a marker body."""
    attrs: dict[str, str] = {}
    for m in _MARKER_ATTR_RE.finditer(attr_string):
        key = m.group(1)
        value = m.group(2) or m.group(3) or m.group(4) or ""
        attrs[key] = value
    return attrs


def process_evolution_markers(
    content: str,
    project_path: str | Path,
    *,
    package: str | None = None,
) -> str:
    """
    Replace `<!-- %evolution ... -->` markers in text with rendered tables

    This function scans *content* (typically a `.qmd` file body) for HTML comment markers of the
    form::

        <!-- %evolution symbol="build" -->

    and replaces each one with the output of :func:`render_evolution_table`.

    Supported attributes
    --------------------
    symbol (required)
        Name of the symbol to track.
    old_version
        Earliest version tag (inclusive).
    new_version
        Latest version tag (inclusive).
    changes_only
        `"true"` (default) or `"false"`.
    disclosure
        `"true"` (default) or `"false"`.
    summary
        Custom `<summary>` text for the disclosure wrapper.
    css
        `"true"` (default) or `"false"`: whether to include the `<style>` block. Set to `"false"`
        when multiple tables appear on the same page and only the first needs the CSS.

    Parameters
    ----------
    content
        The text to scan (e.g., the body of a `.qmd` file).
    project_path
        Root of the git repository.
    package
        Python package name. Auto-detected if omitted.

    Returns
    -------
    :
        `content` with evolution markers replaced by HTML tables. A missing `symbol` produces
        an HTML error comment. Handled package and command-line loading errors, invalid
        `pyproject.toml` files, and Git or file errors also produce an error comment. Other
        exception types propagate.

    Examples
    --------
    A `.qmd` file might contain::

        ## Build function

        The signature has evolved over time:

        <!-- %evolution symbol="build" changes_only="true" -->

    After processing, the marker line is replaced with the full HTML table (and optionally embedded
    CSS).
    """
    project_root = Path(project_path).resolve()

    def _replace(match: _re.Match) -> str:
        attrs = _parse_marker_attrs(match.group(1))

        symbol = attrs.get("symbol")
        if not symbol:
            return "<!-- %evolution error: missing symbol attribute -->"

        def _bool(key: str, default: bool = True) -> bool:
            val = attrs.get(key, "")
            if not val:
                return default
            return val.lower() not in ("false", "no", "0")

        try:
            return render_evolution_table(
                project_root,
                symbol,
                package=attrs.get("package") or package,
                old_version=attrs.get("old_version"),
                new_version=attrs.get("new_version"),
                changes_only=_bool("changes_only"),
                disclosure=_bool("disclosure"),
                summary_text=attrs.get("summary"),
                include_css=_bool("css"),
            )
        except EVOLUTION_ERRORS as exc:
            return f"<!-- %evolution error for {_escape_html(symbol)}: {_escape_html(str(exc))} -->"

    return _EVOLUTION_MARKER_RE.sub(_replace, content)


def process_evolution_markers_in_file(
    qmd_path: str | Path,
    project_path: str | Path,
    *,
    package: str | None = None,
    in_place: bool = False,
) -> str:
    """
    Process `<!-- %evolution ... -->` markers in a `.qmd` file.

    Parameters
    ----------
    qmd_path
        Path to the `.qmd` file.
    project_path
        Root of the git repository.
    package
        Python package name. Auto-detected if omitted.
    in_place
        If `True`, overwrite *qmd_path* with the processed content. If `False` (default), return the
        processed content without modifying the file.

    Returns
    -------
    str
        The processed file content.
    """
    path = Path(qmd_path)
    content = path.read_text(encoding="utf-8")
    result = process_evolution_markers(content, project_path, package=package)

    if in_place and result != content:
        path.write_text(result, encoding="utf-8")

    return result


def compute_version_badges(
    current: ApiSnapshot,
    previous: ApiSnapshot | None,
) -> dict[str, dict]:
    """
    Compute version badges for each symbol in *current* based on a diff against *previous*.

    Parameters
    ----------
    current
        The API snapshot for the version being documented.
    previous
        The API snapshot for the preceding version, or None if this is the first version.

    Returns
    -------
    dict[str, dict]
        Mapping of symbol name to badge info. Each value has keys: `"badge"` (`"new"`, `"changed"`,
        or `"deprecated"`), `"version"` (the current snapshot's version label), and optionally
        `"details"` (list of change descriptions).
    """
    badges: dict[str, dict] = {}

    # Check for deprecation decorators in current
    for name, sym in current.symbols.items():
        if any("deprecated" in d.lower() for d in sym.decorators):
            badges[name] = {
                "badge": "deprecated",
                "version": current.version,
            }

    if previous is None:
        # Everything is new in the first version — don't badge
        return badges

    diff = diff_snapshots(previous, current)

    for change in diff.added:
        # Don't override a deprecation badge
        if change.symbol not in badges:
            badges[change.symbol] = {
                "badge": "new",
                "version": current.version,
            }

    for change in diff.changed:
        if change.symbol not in badges:
            badges[change.symbol] = {
                "badge": "changed",
                "version": current.version,
                "details": change.details,
            }

    return badges


def render_badge_html(badge_info: dict) -> str:
    """
    Render a single badge as an HTML `<span>` for embedding in QMD pages.

    Parameters
    ----------
    badge_info
        A dict with `"badge"` and `"version"` keys (as returned by :func:`compute_version_badges`).

    Returns
    -------
    str
        An HTML `<span>` element with appropriate CSS class.
    """
    badge = badge_info["badge"]
    version = _escape_html(badge_info["version"])

    if badge == "new":
        return f'<span class="gd-badge gd-badge-new">New in {version}</span>'
    elif badge == "changed":
        return f'<span class="gd-badge gd-badge-changed">Changed in {version}</span>'
    elif badge == "deprecated":
        return f'<span class="gd-badge gd-badge-deprecated">Deprecated in {version}</span>'
    return ""


def inject_badges_into_qmd(
    content: str,
    badges: dict[str, dict],
) -> str:
    """
    Inject version badges into QMD content for API reference pages.

    Looks for lines that define API symbols (e.g. `## SymbolName` or `### package.SymbolName`) and
    inserts the badge HTML immediately after the heading.

    Parameters
    ----------
    content
        The `.qmd` file content.
    badges
        Badge dict as returned by :func:`compute_version_badges`.

    Returns
    -------
    str
        The content with badge HTML injected after matching headings.
    """
    if not badges:
        return content

    lines = content.split("\n")
    result: list[str] = []

    for line in lines:
        result.append(line)
        # Match Markdown headings: ## Name or ### pkg.Name
        stripped = line.strip()
        if stripped.startswith("#"):
            # Extract the heading text (after the # marks)
            heading_text = stripped.lstrip("#").strip()
            # Check both the full qualified name and the short name
            symbol_name = heading_text.split(".")[-1] if "." in heading_text else heading_text
            # Also strip any { .class } suffixes from Quarto
            symbol_name = symbol_name.split("{")[0].strip()
            heading_text_clean = heading_text.split("{")[0].strip()

            badge_info = badges.get(symbol_name) or badges.get(heading_text_clean)
            if badge_info:
                result.append(render_badge_html(badge_info))

    return "\n".join(result)
