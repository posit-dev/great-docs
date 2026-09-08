from __future__ import annotations

import json
import os
import re
import re as _re
import shutil
import subprocess
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from great_docs._subprocess import TEXT_MODE_KWARGS
from great_docs._utils import QUARTO_YML_HEADER, is_great_docs_build_dir
from great_docs._versioning import (
    VersionEntry,
    build_version_map,
    get_latest_version,
    is_page_upcoming,
    is_page_upcoming_for_version,
    page_matches_version,
    parse_versions_config,
    process_version_fences,
)

if TYPE_CHECKING:
    from great_docs._api_diff import ApiSnapshot
    from great_docs._interlinks import AliasClaims
    from great_docs.config import Config

# ---------------------------------------------------------------------------
# Stage 1: Preprocess — create version-specific build directories
# ---------------------------------------------------------------------------


_UNSAFE_TAG_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _safe_tag_dirname(tag: str) -> str:
    """Return `tag` with unsafe directory-name characters replaced by `-`"""
    return _UNSAFE_TAG_CHARS.sub("-", tag)


def _version_build_dir(source_dir: Path, entry: VersionEntry, latest_tag: str) -> Path:
    """
    Return the Quarto project directory for a version

    The latest version uses `source_dir`. Each historical version uses a
    sibling directory. This keeps every version at the same depth below the
    project root, so relative paths resolve consistently with or without a
    `versions:` block.

    Parameters
    ----------
    source_dir
        Build directory for the latest version.
    entry
        Version to locate.
    latest_tag
        The tag of the latest version.

    Returns
    -------
    Quarto project directory for the version.
    """
    if entry.tag == latest_tag:
        return source_dir
    return source_dir.parent / f"{source_dir.name}-{_safe_tag_dirname(entry.tag)}"


def _check_build_dir_collisions(
    source_dir: Path,
    targets: list[VersionEntry],
    latest_tag: str,
) -> None:
    """
    Reject version tags that map to the same build directory

    Sanitising directory names can map distinct tags, such as `release/1.0`
    and `release-1.0`, to one directory. Building both would publish one
    version's pages under the other version's tag.

    Parameters
    ----------
    source_dir
        Build directory for the latest version.
    targets
        Versions to build.
    latest_tag
        The tag of the latest version.

    Raises
    ------
    ValueError
        If two tags map to the same build directory.
    """
    seen: dict[Path, str] = {}
    for entry in targets:
        ver_dir = _version_build_dir(source_dir, entry, latest_tag)
        if ver_dir in seen:
            raise ValueError(
                f"Version tags {seen[ver_dir]!r} and {entry.tag!r} both map to "
                f"build directory {ver_dir.name!r}. Rename one of the tags."
            )
        seen[ver_dir] = entry.tag


def _clean_stale_version_dirs(source_dir: Path) -> list[str]:
    """
    Remove version build directories left behind by earlier builds

    Remove only directories whose `_quarto.yml` contains the Great Docs
    marker. Keep and report matching directories that may contain user files.

    Parameters
    ----------
    source_dir
        Build directory for the latest version. Matching sibling directories
        are cleanup candidates.

    Returns
    -------
    Warnings for matching directories retained because they lacked the marker.
    """
    warnings: list[str] = []
    for candidate in sorted(source_dir.parent.glob(f"{source_dir.name}-*")):
        if not candidate.is_dir() or candidate.is_symlink():
            continue
        if is_great_docs_build_dir(candidate):
            shutil.rmtree(candidate)
        else:
            warnings.append(
                f"Kept {candidate.name}/ because it does not contain a Great Docs-generated "
                f"_quarto.yml. Delete it manually if it is a leftover build directory."
            )
    return warnings


def _collect_qmd_files(source_dir: Path) -> list[Path]:
    """Recursively collect all .qmd and .md files under *source_dir*."""
    files: list[Path] = []
    for ext in ("*.qmd", "*.md"):
        files.extend(source_dir.rglob(ext))
    return sorted(files)


_FRONTMATTER_VALUE_RE = _re.compile(r"^---\s*\n(.*?)\n---\s*\n", _re.DOTALL)


def _extract_frontmatter_value(content: str, key: str) -> str | None:
    """Extract a scalar value for *key* from YAML frontmatter, or `None`."""
    m = _FRONTMATTER_VALUE_RE.match(content)
    if not m:
        return None
    fm = m.group(1)
    # Simple line-based extraction that handles `key: value` and `key: "value"`
    pattern = _re.compile(rf"^{_re.escape(key)}\s*:\s*(.+)$", _re.MULTILINE)
    km = pattern.search(fm)
    if not km:
        return None
    val = km.group(1).strip().strip('"').strip("'")
    return val


def _inject_upcoming_status(content: str) -> str:
    """Inject `status: upcoming` into YAML frontmatter if no status is already set.

    Used only for pages scoped exclusively to prerelease versions that have no explicit status.
    Pages with an existing status (e.g. `experimental`) keep their status and the upcoming indicator
    renders independently.
    """
    m = _FRONTMATTER_VALUE_RE.match(content)
    if not m:
        return content
    fm = m.group(1)
    if _re.search(r"^status\s*:", fm, _re.MULTILINE):
        return content
    new_fm = fm + "\nstatus: upcoming"
    return content[: m.start(1)] + new_fm + content[m.end(1) :]


def _update_page_status_json(dest_dir: Path, upcoming_pages: list[tuple[str, str | None]]) -> None:
    """Update `_page_status.json` in the per-version build dir with upcoming page data.

    Upcoming pages are stored in a separate `upcoming_pages` key so they render independently from
    the regular `page_statuses` (which tracks status like `experimental`, `new`, etc.).

    Parameters
    ----------
    dest_dir
        Per-version build directory containing the JSON file.
    upcoming_pages
        List of `(page_href, version)` tuples. *version* is the upcoming version string (e.g.,
        `"0.8"`) or None if inferred from version scoping.
    """
    status_path = dest_dir / "_page_status.json"
    if not status_path.exists():
        return
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    upcoming_map = data.get("upcoming_pages", {})
    for page_href, version in upcoming_pages:
        qmd_href = page_href.replace(".html", ".qmd")
        upcoming_map[qmd_href] = version or True

    data["upcoming_pages"] = upcoming_map
    status_path.write_text(json.dumps(data), encoding="utf-8")


def _sync_status_inline_script(dest_dir: Path) -> None:
    """Inject a **separate** `__GD_UPCOMING_DATA__` inline script into `_quarto.yml`.

    Instead of modifying the existing (large, SVG-laden) `__GD_STATUS_DATA__` script (which breaks
    when round-tripped through yaml12 due to nested quoting issues) we append a tiny new `<script>`
    that only carries the lightweight `upcoming_pages` map. The page-status-badges JS reads both
    globals.

    Must be called AFTER `_update_page_status_json` so that the JSON file contains the
    `upcoming_pages` map.
    """
    status_path = dest_dir / "_page_status.json"
    quarto_yml_path = dest_dir / "_quarto.yml"
    if not status_path.exists() or not quarto_yml_path.exists():
        return
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    upcoming_map = data.get("upcoming_pages")
    if not upcoming_map:
        return

    # Build a tiny inline script with just the upcoming data (no SVGs, no
    # complex escaping).
    upcoming_json = json.dumps(upcoming_map)
    inline_script = "<script>window.__GD_UPCOMING_DATA__=" + upcoming_json + ";</script>"

    # Insert directly into the raw YAML text — find the __GD_STATUS_DATA__
    # line and append the new script entry right after it.
    yml_content = quarto_yml_path.read_text(encoding="utf-8")

    # Guard: check for the actual injected script tag (not JS references)
    if "<script>window.__GD_UPCOMING_DATA__=" in yml_content:
        return  # Already injected

    lines = yml_content.split("\n")
    insert_after = None
    for i, line in enumerate(lines):
        if "<script>window.__GD_STATUS_DATA__=" in line:
            insert_after = i
            break

    if insert_after is None:
        return

    # Match the indentation of the status data line
    status_line = lines[insert_after]
    indent = len(status_line) - len(status_line.lstrip())
    # The upcoming JSON is simple (no quotes to escape in YAML single-quoted)
    new_line = " " * indent + "- text: '" + inline_script + "'"
    lines.insert(insert_after + 1, new_line)
    quarto_yml_path.write_text("\n".join(lines), encoding="utf-8")


def _prune_cli_pages(dest_dir: Path, snap: object) -> None:
    """
    Remove CLI reference QMD files for commands not in the snapshot.

    The main build generates CLI pages from the *current* installed CLI. When building an older
    version, commands that didn't exist yet must be removed so they don't appear in that version's
    site. Also rewrites the CLI index page so the embedded help text only lists valid commands.
    """
    cli_ref_dir = dest_dir / "reference" / "cli"
    if not cli_ref_dir.is_dir():
        return

    cli_commands = getattr(snap, "cli_commands", None)
    if cli_commands is None:
        return

    # Build the set of valid command file stems from the snapshot.
    # CliCommandInfo.subcommands holds the actual commands; the index page maps to `index.qmd`
    # and the root command's own page maps to the entry point's safe name.
    valid_stems: set[str] = {"index"}
    entry_name = getattr(cli_commands, "name", "") or ""
    if entry_name:
        valid_stems.add(entry_name.replace("-", "_"))
    for sub in getattr(cli_commands, "subcommands", []):
        # Click command names use hyphens; file stems use underscores
        valid_stems.add(sub.name.replace("-", "_"))

    # Remove QMD files for commands not present at this version
    for qmd_file in list(cli_ref_dir.iterdir()):
        if qmd_file.suffix not in (".qmd", ".md"):
            continue
        if qmd_file.stem not in valid_stems:
            qmd_file.unlink()

    # Rewrite the index.qmd to remove stale commands from the listing
    index_qmd = cli_ref_dir / "index.qmd"
    if index_qmd.exists():
        _rewrite_cli_index(index_qmd, valid_stems)

    # Prune the CLI sidebar in _quarto.yml
    _prune_quarto_cli_sidebar(dest_dir, valid_stems)


def _rewrite_cli_index(index_qmd: Path, valid_stems: set[str]) -> None:
    """Remove command entries for non-existent commands from the CLI index listing.

    The index is a definition list of ``[name](href){...}`` entries. An entry is kept when the
    first path component of its href (e.g. ``init`` from ``init.qmd``, or ``skill`` from
    ``skill/install.qmd``) is a valid command stem at this version. Dropping an entry also drops
    its ``:   description`` line and the trailing blank line.
    """
    content = index_qmd.read_text(encoding="utf-8")
    lines = content.split("\n")
    entry_re = re.compile(r"^\[[^\]]+\]\((?P<href>[^)]+)\)\{")

    new_lines: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        match = entry_re.match(lines[i].strip())
        if match:
            stem = match.group("href").split("/")[0]
            if stem.endswith(".qmd"):
                stem = stem[:-4]
            elif stem.endswith(".md"):
                stem = stem[:-3]

            if stem in valid_stems:
                new_lines.append(lines[i])
                i += 1
            else:
                # Skip the link line, its ":   description" line, and one trailing blank line.
                i += 1
                if i < n and lines[i].lstrip().startswith(":"):
                    i += 1
                if i < n and not lines[i].strip():
                    i += 1
            continue

        new_lines.append(lines[i])
        i += 1

    index_qmd.write_text("\n".join(new_lines), encoding="utf-8")


def _prune_quarto_cli_sidebar(dest_dir: Path, valid_stems: set[str]) -> None:
    """Remove CLI sidebar entries from _quarto.yml for pruned commands."""
    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    try:
        from yaml12 import read_yaml, write_yaml

        content = read_yaml(quarto_yml)
        if not content:
            return

        sidebars = content.get("website", {}).get("sidebar", [])
        modified = False

        for sidebar in sidebars:
            if sidebar.get("id") != "cli-reference":
                continue
            contents = sidebar.get("contents", [])
            new_contents = []
            for item in contents:
                if isinstance(item, str) and item.startswith("reference/cli/"):
                    stem = Path(item).stem
                    if stem in valid_stems:
                        new_contents.append(item)
                    else:
                        modified = True
                else:
                    new_contents.append(item)
            if modified:
                sidebar["contents"] = new_contents
            break

        if modified:
            write_yaml(content, quarto_yml)
    except Exception:  # pragma: no cover
        pass  # pragma: no cover


def _prune_missing_sidebar_pages(dest_dir: Path) -> None:
    """Remove sidebar entries whose .qmd files no longer exist in *dest_dir*.

    After page-level and section-level version scoping delete excluded `.qmd` files, the sidebar in
    `_quarto.yml` may still reference them. Quarto renders those stale entries as raw path text
    instead of links. This function walks every sidebar section and drops entries that point to
    non-existent files. Empty sections are removed entirely.
    """
    from yaml12 import read_yaml, write_yaml

    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    try:
        with open(quarto_yml, "r", encoding="utf-8") as fh:
            content = read_yaml(fh)
        if not content:
            return

        sidebars = content.get("website", {}).get("sidebar", [])
        modified = False

        for sidebar in sidebars:
            pruned = _prune_sidebar_contents(sidebar.get("contents", []), dest_dir)
            if pruned != sidebar.get("contents", []):
                sidebar["contents"] = pruned
                modified = True

        if modified:
            with open(quarto_yml, "w", encoding="utf-8") as fh:
                write_yaml(content, fh)
    except Exception:
        pass  # Best-effort


def _prune_sidebar_contents(contents: list, dest_dir: Path) -> list:
    """Recursively prune sidebar entries whose target files are missing."""
    result = []
    for item in contents:
        if isinstance(item, str):
            # Bare href like "user-guide/scale-to-fit.qmd"
            if item.endswith((".qmd", ".md")) and not (dest_dir / item).exists():
                continue
            result.append(item)
        elif isinstance(item, dict):
            if "section" in item:
                # Section group — recurse into contents
                inner = _prune_sidebar_contents(item.get("contents", []), dest_dir)
                if inner:
                    result.append({**item, "contents": inner})
                # else: drop the empty section entirely
            elif "href" in item:
                href = item["href"]
                if href.endswith((".qmd", ".md")) and not (dest_dir / href).exists():
                    continue
                result.append(item)
            else:
                result.append(item)
        else:
            result.append(item)
    return result


def _prune_cli_pages_for_version(dest_dir: Path, project_root: Path, entry: VersionEntry) -> None:
    """Load the cached snapshot for a version and prune stale CLI pages."""
    git_ref = entry.git_ref
    if not git_ref:
        return

    cache_path = _snapshot_cache_path(project_root, git_ref)
    if not cache_path.exists():
        return

    try:
        from great_docs._api_diff import ApiSnapshot

        snap = ApiSnapshot.load(cache_path)
        _prune_cli_pages(dest_dir, snap)
    except Exception:  # pragma: no cover
        pass  # pragma: no cover


def preprocess_version(
    source_dir: Path,
    dest_dir: Path,
    entry: VersionEntry,
    all_versions: list[VersionEntry],
    project_root: Path | None = None,
    section_configs: list[dict] | None = None,
    badge_expiry: "BadgeExpiry | None" = None,
    config: Config | None = None,
) -> list[str]:
    """
    Prepare the documentation source for one version

    Copy `source_dir` to `dest_dir` unless they are the same directory. Then:

    1. Remove pages whose front matter excludes the version.
    2. Remove sections whose configuration excludes the version.
    3. Process version fences in the remaining `.qmd` files.
    4. Expand version badges and callouts.
    5. Generate API reference pages from a configured snapshot, and rebuild
       the inventory and interlinks index to match them.
    6. Generate API reference pages from a configured Git tag, and rebuild
       the inventory and interlinks index to match them.

    Parameters
    ----------
    source_dir
        Prepared documentation tree before version-specific filtering.
    dest_dir
        Quarto project directory for the version. When it equals `source_dir`,
        prepare the latest version in place.
    entry
        Version to prepare.
    all_versions
        All configured versions in display order.
    project_root
        Project root used to resolve snapshot paths.
    section_configs
        Section configuration entries from `great-docs.yml`.
    badge_expiry
        Default expiry policy for `new` badges.
    config
        Project configuration, forwarded to steps 5 and 6 for rebuilding the
        inventory and interlinks index. Skipped for a version that keeps the
        live inventory when omitted.

    Returns
    -------
    Page paths relative to `dest_dir`, with `.qmd` extensions replaced by
    `.html`.
    """
    # Build a set of directories excluded by section-level version scoping
    excluded_dirs = _compute_excluded_section_dirs(entry.tag, section_configs)

    # The latest version uses `source_dir` directly; only historical versions
    # need a copy.
    if dest_dir.resolve() != source_dir.resolve():  # pragma: no cover
        if dest_dir.exists():  # pragma: no cover
            shutil.rmtree(dest_dir)  # pragma: no cover
        shutil.copytree(source_dir, dest_dir, dirs_exist_ok=False)  # pragma: no cover

    included_pages: list[str] = []
    upcoming_pages: list[tuple[str, str | None]] = []

    for qmd_file in _collect_qmd_files(dest_dir):
        rel = qmd_file.relative_to(dest_dir)

        # Skip internal files
        if str(rel).startswith("_"):  # pragma: no cover
            continue  # pragma: no cover

        # 0. Section-level version scoping
        if _in_excluded_section(rel, excluded_dirs):
            qmd_file.unlink()
            continue

        content = qmd_file.read_text(encoding="utf-8", errors="replace")

        # 1. Page-level version scoping
        if not page_matches_version(content, entry.tag, all_versions):
            qmd_file.unlink()
            continue

        # 2. Process version fences
        processed = process_version_fences(content, entry.tag, all_versions)

        # 3. Detect upcoming pages (independent of status: badge).
        #    Two mechanisms: (a) page scoped exclusively to prerelease versions,
        #    (b) page has `upcoming: "0.8"` and current build is older than 0.8.
        is_upcoming = False
        upcoming_val: str | None = None
        if is_page_upcoming(content, all_versions):
            is_upcoming = True
            # For pages with no existing status, inject status: upcoming
            processed = _inject_upcoming_status(processed)
        else:
            upcoming_val = _extract_frontmatter_value(content, "upcoming")
            if upcoming_val and is_page_upcoming_for_version(upcoming_val, entry.tag, all_versions):
                is_upcoming = True

        if is_upcoming:
            page_href = str(rel).replace(".qmd", ".html").replace(".md", ".html")
            upcoming_pages.append((page_href, upcoming_val))

        if processed != content:
            qmd_file.write_text(processed, encoding="utf-8")

        # Track included page (convert .qmd → .html for the manifest)
        html_rel = str(rel).replace(".qmd", ".html").replace(".md", ".html")
        included_pages.append(html_rel)

    # 3. Strategy A: regenerate API reference from snapshot if configured
    if entry.api_snapshot and project_root:
        snap_path = project_root / entry.api_snapshot
        if snap_path.exists():
            api_pages = _rebuild_api_from_snapshot(dest_dir, snap_path, entry, config)
            included_pages.extend(api_pages)

    # 4. Strategy B: git-ref introspection with caching
    elif entry.git_ref and project_root:
        api_pages = _rebuild_api_from_git_ref(dest_dir, project_root, entry, config)
        included_pages.extend(api_pages)

    # 5. Prune CLI pages that don't exist at this version
    if entry.git_ref and project_root:
        _prune_cli_pages_for_version(dest_dir, project_root, entry)

    # 6. Expand inline [version-badge] markers and version callouts
    for qmd_file in _collect_qmd_files(dest_dir):
        content = qmd_file.read_text(encoding="utf-8", errors="replace")

        # Per-page new-is-old override
        page_expiry = badge_expiry
        page_override = _extract_frontmatter_value(content, "new-is-old")
        if page_override is not None:
            from great_docs._versioning import parse_badge_expiry

            page_expiry = parse_badge_expiry(page_override)

        updated = expand_version_badges(content, entry, all_versions, page_expiry)
        updated = expand_version_callouts(updated, entry)
        if updated != content:
            qmd_file.write_text(updated, encoding="utf-8")

    # 7. Update _page_status.json with upcoming pages for this version
    if upcoming_pages:
        _update_page_status_json(dest_dir, upcoming_pages)

    return included_pages


def _compute_excluded_section_dirs(
    target_tag: str,
    section_configs: list[dict] | None,
) -> set[str]:
    """
    Compute the set of directory names excluded by section-level scoping.

    A section config with a `"versions"` list that does NOT include *target_tag* means all pages
    under that section's `"dir"` are excluded.

    Parameters
    ----------
    target_tag
        The version being built.
    section_configs
        Section configurations from config, each with `"dir"` and optionally `"versions"` keys.

    Returns
    -------
    set[str]
        Directory names (not paths) to exclude.
    """
    if not section_configs:
        return set()

    excluded: set[str] = set()
    for section in section_configs:
        section_dir = section.get("dir", "")
        section_versions = section.get("versions")
        if section_dir and section_versions and target_tag not in section_versions:
            excluded.add(section_dir)

    return excluded


def _in_excluded_section(rel_path: Path, excluded_dirs: set[str]) -> bool:
    """Check if a file's relative path falls under an excluded section directory."""
    if not excluded_dirs:
        return False
    # Check if any path component matches an excluded dir
    for part in rel_path.parts:
        if part in excluded_dirs:
            return True
    return False


def _rebuild_api_from_snapshot(
    dest_dir: Path,
    snapshot_path: Path,
    entry: VersionEntry,
    config: Config | None = None,
) -> list[str]:
    """
    Rebuild API reference pages from a snapshot, pruning pages not in the snapshot.

    When the source tree already contains reference pages (e.g. from the main build), pages for
    symbols in the snapshot are regenerated from the snapshot data and pages for symbols *not* in
    the snapshot are removed. When no reference directory exists, pages are generated from scratch.
    When *config* is given, the version's inventory and interlinks index are rebuilt from the same
    snapshot afterwards, so they describe the pages this call just produced.

    Parameters
    ----------
    dest_dir
        The version's build directory.
    snapshot_path
        Path to the snapshot JSON file.
    entry
        The version being built.
    config
        Project configuration, for rebuilding the inventory and interlinks
        index. Skipped when omitted.

    Returns
    -------
    list[str]
        Relative paths of API pages (as .html).
    """
    from great_docs._api_diff import ApiSnapshot

    snap = ApiSnapshot.load(snapshot_path)
    ref_dir = dest_dir / "reference"

    snapshot_symbols = set(snap.symbols.keys())

    # --- Prune existing pages not in the snapshot ---
    if ref_dir.exists():
        for qmd_file in list(ref_dir.iterdir()):
            if qmd_file.is_dir():  # pragma: no cover
                continue  # pragma: no cover
            if qmd_file.suffix not in (".qmd", ".md"):  # pragma: no cover
                continue  # pragma: no cover
            stem = qmd_file.stem
            if stem == "index":
                continue
            if not _is_valid_ref_name(stem, snapshot_symbols):
                qmd_file.unlink()
    else:
        ref_dir.mkdir(parents=True, exist_ok=True)

    # --- Generate / overwrite pages for each symbol in the snapshot ---
    generated: list[str] = []

    for name, sym in snap.symbols.items():
        qmd_path = ref_dir / f"{name}.qmd"

        # Preserve existing rich renderer-generated pages (they contain full docstrings,
        # examples, attributes, etc.). Only generate a minimal fallback page when no rich
        # page exists.
        if qmd_path.exists():
            existing_content = qmd_path.read_text(encoding="utf-8")
            if "{.doc-" in existing_content:
                generated.append(f"reference/{name}.html")
                continue

        sig = _format_signature(name, sym)

        lines = [
            "---",
            f'title: "{name}"',
            "---",
            "",
            f"# {name} {{.doc-heading}}",
            "",
            f"`{sig}`",
            "",
            f"*Kind:* {sym.kind}",
            "",
        ]

        if sym.bases:
            bases_str = ", ".join(sym.bases)
            lines.append(f"*Bases:* {bases_str}")
            lines.append("")

        if sym.parameters:
            lines.append("## Parameters")
            lines.append("")
            for p in sym.parameters:
                ann = f": {p.annotation}" if p.annotation else ""
                default = f" = {p.default}" if p.default else ""
                lines.append(f"- **{p.name}**{ann}{default}")
            lines.append("")

        if sym.return_annotation:
            lines.append("## Returns")
            lines.append("")
            lines.append(f"`{sym.return_annotation}`")
            lines.append("")

        qmd_path.write_text("\n".join(lines), encoding="utf-8")
        generated.append(f"reference/{name}.html")

    # --- Update or generate index page ---
    index_path = ref_dir / "index.qmd"

    # Detect whether the existing index is a rich renderer-generated page (has Pandoc attribute
    # classes like {.doc-label ...}) vs. a plain placeholder. Rich pages are preserved and pruned;
    # plain/missing pages are regenerated from the snapshot.
    _has_rich_index = False
    if index_path.exists():
        _idx_content = index_path.read_text(encoding="utf-8")
        _has_rich_index = "{.doc-" in _idx_content

    if _has_rich_index:
        # Preserve the styled index — just remove entries for symbols not in this version
        _prune_reference_index(index_path, snapshot_symbols)
    else:
        # No existing index or it's a plain placeholder; generate from snapshot
        index_lines = [
            "---",
            f'title: "API Reference ({entry.label})"',
            "---",
            "",
        ]

        classes = [(n, s) for n, s in snap.symbols.items() if s.kind == "class"]
        functions = [(n, s) for n, s in snap.symbols.items() if s.kind == "function"]

        if classes:
            index_lines.append("## Classes")
            index_lines.append("")
            for name, _ in sorted(classes):
                index_lines.append(f"- [{name}]({name}.qmd)")
            index_lines.append("")

        if functions:
            index_lines.append("## Functions")
            index_lines.append("")
            for name, _ in sorted(functions):
                index_lines.append(f"- [{name}]({name}.qmd)")
            index_lines.append("")

        index_path.write_text("\n".join(index_lines), encoding="utf-8")

    generated.append("reference/index.html")

    # --- Update _quarto.yml sidebar to remove missing reference entries ---
    _prune_quarto_sidebar(dest_dir, "reference", snapshot_symbols)

    if config is not None:
        _write_snapshot_inventory(dest_dir, snap, config)

    return generated


def _snapshot_claims(snap: ApiSnapshot) -> AliasClaims:
    """
    Derive the short names a snapshot-built version's objects claim

    The live build reads these from the resolved API reference, which a
    historical version has no way to run. A snapshot's stems carry the same
    information: the last component is the bare short name, and a dotted stem
    is already the class-qualified form.

    Parameters
    ----------
    snap
        The snapshot the version's reference pages were rebuilt from.

    Returns
    -------
    :
        The claims, in the shape `build_project_index` consumes.
    """
    from ._interlinks import AliasClaims

    claimed: list[tuple[str, str]] = []
    published: list[str] = []
    for stem in snap.symbols:
        full = f"{snap.package_name}.{stem}"
        published.append(full)
        claimed.append((stem, full))
        bare = stem.rpartition(".")[2]
        if bare != stem:
            claimed.append((bare, full))
    return AliasClaims(claimed=tuple(claimed), published=frozenset(published))


def _write_snapshot_inventory(dest_dir: Path, snap: ApiSnapshot, config: Config) -> None:
    """
    Publish this version's own inventory and interlinks index

    The inventory and interlinks index copied into `dest_dir` describe the
    live checkout's API, not this version's. Since `_rebuild_api_from_snapshot`
    has just pruned and regenerated `dest_dir`'s reference pages to match
    *snap*, rebuild both from the same snapshot so they describe what this
    version actually publishes rather than what the live build did.

    The claims come from the snapshot's own stems rather than from a resolved
    API reference, which a historical version has no way to run. That recovers
    every short name the live build indexes except one: a name written into an
    `api-reference:` config that differs from the object's path.

    Parameters
    ----------
    dest_dir
        The version's build directory.
    snap
        The snapshot the version's reference pages were rebuilt from.
    config
        Project configuration, for the interlinks sources and cache.
    """
    from ._apiref.inventory import reference_uri
    from ._interlinks import build_project_index
    from ._sphinx_inventory import (
        INVENTORY_FILENAME,
        Inventory,
        InventoryEntry,
        encode,
        role_for_kind,
    )

    classes = {name for name, sym in snap.symbols.items() if sym.kind == "class"}

    entries = tuple(
        InventoryEntry(
            name=f"{snap.package_name}.{name}",
            domain="py",
            role=role_for_kind(sym.kind, in_class=name.rpartition(".")[0] in classes),
            priority=1,
            uri=reference_uri("reference", name),
            dispname=f"{snap.package_name}.{name}",
        )
        for name, sym in snap.symbols.items()
    )
    inv = Inventory(project=snap.package_name, version=snap.version, entries=entries)
    (dest_dir / INVENTORY_FILENAME).write_bytes(encode(inv))

    build_project_index(dest_dir, config, snap.package_name, _snapshot_claims(snap))


def _format_signature(name: str, sym) -> str:
    """Format a Python-like signature string from a SymbolInfo."""
    if sym.kind == "class":
        if sym.parameters:
            params = ", ".join(_format_param(p) for p in sym.parameters)
            return f"class {name}({params})"
        return f"class {name}"
    elif sym.kind == "function":
        params = ", ".join(_format_param(p) for p in sym.parameters)
        ret = f" -> {sym.return_annotation}" if sym.return_annotation else ""
        prefix = "async " if sym.is_async else ""
        return f"{prefix}def {name}({params}){ret}"
    else:
        return name


def _format_param(p) -> str:
    """Format a single parameter for display."""
    parts = [p.name]
    if p.annotation:
        parts.append(f": {p.annotation}")
    if p.default:
        parts.append(f" = {p.default}")
    return "".join(parts)


def _is_valid_ref_name(name: str, valid_symbols: set[str]) -> bool:
    """Whether a reference page stem names a symbol documented in this version.

    A *deep* snapshot lists every valid stem explicitly (including method
    stems like `Class.method` and submodule-qualified names like `sub.Widget`)
    so exact set membership is sufficient and authoritative.

    A *shallow* snapshot holds only the package's top-level exports; it is the
    back-compat fallback used when no documented set can be resolved (e.g.
    `documented_symbol_names()` returned nothing). Such a snapshot carries no
    dotted keys, so a `Class.method` page would be wrongly pruned under exact
    membership. For that case only, fall back to validating a dotted stem by
    its top-level prefix, matching the pre-deep-snapshot behavior and keeping
    the failure mode non-destructive.
    """
    if name == "index" or name in valid_symbols:
        return True
    # Shallow-snapshot safety net: a snapshot with no dotted keys cannot speak
    # to method/submodule pages, so keep `Prefix.rest` when `Prefix` is known.
    if "." in name and not any("." in symbol for symbol in valid_symbols):
        return name.split(".")[0] in valid_symbols
    return False


def _prune_reference_index(index_qmd: Path, valid_symbols: set[str]) -> None:
    """Remove links/rows for symbols not in the snapshot from reference/index.qmd.

    This handles three levels of cleanup:
    1. Remove link lines referencing symbols not in the snapshot.
    2. Remove orphaned definition-list descriptions (`:   ...`) that followed a removed link.
    3. Remove empty section headers (`## Title {.doc-group}` plus their `.doc-description` divs)
       when all entries in the section have been removed.
    """
    import re

    content = index_qmd.read_text(encoding="utf-8")
    lines = content.split("\n")

    # --- Pass 1: mark link lines for removal and their trailing description lines ---
    remove_indices: set[int] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()

        qmd_ref = re.search(r"\(([^)]+)\.qmd(?:#[^)]*)?\)", stripped)
        if qmd_ref:
            symbol_name = qmd_ref.group(1)
            if not _is_valid_ref_name(symbol_name, valid_symbols):
                remove_indices.add(i)
                # Also remove the following definition-list description line(s)
                # Pattern: `:   description text` (Pandoc definition list)
                j = i + 1
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if next_stripped == "":
                        # Blank line between entries — remove it too
                        remove_indices.add(j)
                        j += 1
                        continue
                    if next_stripped.startswith(":"):
                        remove_indices.add(j)
                        j += 1
                        continue
                    break
                continue

        bare_ref = re.match(r"^\s*-\s+(\S+)\.qmd\s*$", stripped)
        if bare_ref:
            symbol_name = bare_ref.group(1)
            if not _is_valid_ref_name(symbol_name, valid_symbols):
                remove_indices.add(i)

    filtered = [line for i, line in enumerate(lines) if i not in remove_indices]

    # --- Pass 2: remove empty sections ---
    # A section block looks like:
    #   ## Title {.doc-group}
    #   <blank>
    #   ::: {.doc-description}
    #   description text
    #   :::
    #   <blank>
    #   (entries would follow here)
    #
    # If the next non-blank content after the closing ::: is another ## heading or EOF,
    # the section is empty and should be removed entirely.
    result: list[str] = []
    idx = 0
    while idx < len(filtered):
        line = filtered[idx]
        stripped = line.strip()

        # Detect a section header with {.doc-group}
        if stripped.startswith("##") and "{.doc-group}" in stripped:
            # Collect the entire section header block (header + optional blank +
            # description div + optional trailing blank)
            block_start = idx
            idx += 1

            # Skip blank lines after header
            while idx < len(filtered) and filtered[idx].strip() == "":
                idx += 1

            # If there's a ::: {.doc-description} div, consume it
            if idx < len(filtered) and filtered[idx].strip().startswith("::: {.doc-description"):
                idx += 1
                # Consume lines until closing :::
                while idx < len(filtered) and filtered[idx].strip() != ":::":
                    idx += 1
                if idx < len(filtered):
                    idx += 1  # skip the closing :::

            # Skip trailing blank lines
            while idx < len(filtered) and filtered[idx].strip() == "":
                idx += 1

            # Now check if the section has any content: the next line should be
            # something other than another ## heading or EOF
            if idx >= len(filtered) or filtered[idx].strip().startswith("##"):
                # Empty section — drop the entire block by not appending it
                continue
            else:
                # Non-empty section — keep the block
                result.extend(filtered[block_start:idx])
        else:
            result.append(line)
            idx += 1

    index_qmd.write_text("\n".join(result), encoding="utf-8")


def _prune_quarto_sidebar(dest_dir: Path, section: str, valid_symbols: set[str]) -> None:
    """Remove sidebar entries for missing symbols/commands from _quarto.yml.

    Handles both flat string entries (`reference/Name.qmd`) and nested section groups
    (`section: Title` with `contents: [...]`). Empty section groups are removed entirely.
    """
    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    try:
        from yaml12 import read_yaml, write_yaml

        content = read_yaml(quarto_yml)
        if not content:
            return

        sidebars = content.get("website", {}).get("sidebar", [])
        modified = False

        for sidebar in sidebars:
            contents = sidebar.get("contents", [])
            if not contents:  # pragma: no cover
                continue  # pragma: no cover

            # Check if this sidebar has any reference to our section (flat or nested)
            def _has_section_ref(items: list) -> bool:
                for c in items:
                    if isinstance(c, str) and c.startswith(f"{section}/"):
                        return True
                    if isinstance(c, dict):
                        sub = c.get("contents", [])
                        if sub and _has_section_ref(sub):
                            return True
                return False

            if not _has_section_ref(contents):
                continue

            def _prune_contents(items: list) -> tuple[list, bool]:
                """Recursively prune items, returning (new_items, was_modified)."""
                new_items: list = []
                changed = False
                for item in items:
                    if isinstance(item, str) and item.startswith(f"{section}/"):
                        if "/" in item.replace(f"{section}/", "", 1):
                            # Sub-path like reference/cli/... — keep
                            new_items.append(item)
                        else:
                            stem = Path(item).stem
                            if _is_valid_ref_name(stem, valid_symbols):
                                new_items.append(item)
                            else:
                                changed = True
                    elif isinstance(item, dict) and "section" in item:
                        sub_contents = item.get("contents", [])
                        pruned_sub, sub_changed = _prune_contents(sub_contents)
                        if sub_changed:
                            changed = True
                        if pruned_sub:
                            new_item = dict(item)
                            new_item["contents"] = pruned_sub
                            new_items.append(new_item)
                        else:
                            # All entries removed — drop the entire section group
                            changed = True
                    else:
                        new_items.append(item)  # pragma: no cover
                return new_items, changed

            new_contents, was_modified = _prune_contents(contents)
            if was_modified:
                sidebar["contents"] = new_contents
                modified = True

        if modified:
            write_yaml(content, quarto_yml)
    except Exception:  # pragma: no cover
        pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Strategy B: Git-ref introspection with caching
# ---------------------------------------------------------------------------

import re as _re

_GIT_TAG_RE = _re.compile(r"^v?\d+[\w.\-]*$")


def _validate_git_ref_is_tag(project_root: Path, git_ref: str) -> bool:
    """
    Validate that *git_ref* is an existing git tag.

    Only tags are accepted (not branches or arbitrary SHAs) to avoid executing setup code from
    untrusted or in-progress work.
    """
    if not _GIT_TAG_RE.match(git_ref):
        return False

    try:
        result = subprocess.run(
            ["git", "tag", "--list", git_ref],
            cwd=project_root,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=10,
        )
        return result.returncode == 0 and git_ref in result.stdout.strip().split("\n")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _snapshot_cache_path(project_root: Path, git_ref: str) -> Path:
    """Return the cache file path for a git-ref snapshot."""
    return project_root / ".great-docs-cache" / "snapshots" / f"{git_ref}.json"


def _rebuild_api_from_git_ref(
    dest_dir: Path,
    project_root: Path,
    entry: VersionEntry,
    config: Config | None = None,
) -> list[str]:
    """
    Introspect a package at a git tag and generate API reference pages.

    Implements Strategy B with caching: if a cached snapshot exists for this git_ref, it is loaded
    instead of re-introspecting.

    Parameters
    ----------
    dest_dir
        The version's build directory.
    project_root
        Project root (git repo root).
    entry
        The version entry with `git_ref` set.
    config
        Project configuration, forwarded to `_rebuild_api_from_snapshot` for
        rebuilding the inventory and interlinks index. Skipped when omitted.

    Returns
    -------
    list[str]
        Relative paths of generated API pages (as .html).
    """
    from great_docs._api_diff import (
        ApiSnapshot,
        _detect_package_name,
        snapshot_at_tag,
    )

    git_ref = entry.git_ref
    if not git_ref:
        return []

    # Security: validate that git_ref is an actual tag
    if not _validate_git_ref_is_tag(project_root, git_ref):
        import warnings

        warnings.warn(
            f"git_ref '{git_ref}' is not a valid tag in this repository. "
            f"Skipping API introspection for version {entry.tag}.",
            stacklevel=2,
        )
        return []

    # Check cache first
    cache_path = _snapshot_cache_path(project_root, git_ref)
    if cache_path.exists():
        snap = ApiSnapshot.load(cache_path)
    else:
        pkg_name = _detect_package_name(project_root)
        if not pkg_name:
            return []

        from great_docs.core import GreatDocs

        documented = GreatDocs(project_path=str(project_root)).documented_symbol_names(pkg_name)

        snap = snapshot_at_tag(project_root, git_ref, pkg_name, documented_names=documented or None)
        if snap is None:
            return []

        # Save to cache for future builds
        snap.save(cache_path)

    # Reuse the snapshot-based builder
    return _rebuild_api_from_snapshot(dest_dir, cache_path, entry, config)


# ---------------------------------------------------------------------------
# Phase 3: Inline version-badge expansion & version callouts
# ---------------------------------------------------------------------------

_VERSION_BADGE_RE = _re.compile(
    r"\[version-badge\s+(new|changed|deprecated)(?:\s+(\S+))?\]",
    _re.IGNORECASE,
)

_VERSION_NOTE_RE = _re.compile(
    r"^:::\s*\{\.version-note(?:\s+versions?=\"([^\"]*)\")?\}\s*$",
    _re.MULTILINE,
)

_VERSION_DEPRECATED_RE = _re.compile(
    r"^:::\s*\{\.version-deprecated(?:\s+versions?=\"([^\"]*)\")?\}\s*$",
    _re.MULTILINE,
)


def expand_version_badges(
    content: str,
    entry: VersionEntry,
    versions: list[VersionEntry] | None = None,
    expiry: "BadgeExpiry | None" = None,
) -> str:
    """
    Expand `[version-badge new]` and `[version-badge changed 0.3]` inline markers into HTML `<span>`
    badges.

    If no version is specified in the marker, the current entry's label is used.

    When *expiry* is provided and a `new` badge is expired, the marker is removed entirely (no HTML
    emitted). `changed` and `deprecated` badges are never affected by expiry.

    Parameters
    ----------
    content
        The `.qmd` file content.
    entry
        The version being built.
    versions
        The full ordered list of version entries (needed for expiry evaluation).
    expiry
        Badge expiry policy. `None` means never expire.

    Returns
    -------
    str
        Content with markers replaced by HTML spans.
    """
    from great_docs._versioning import BADGE_EXPIRY_NEVER, _find_entry, is_badge_expired

    effective_expiry = expiry or BADGE_EXPIRY_NEVER

    def _replace(m: _re.Match) -> str:
        badge_type = m.group(1).lower()
        version = m.group(2) or entry.label

        # Check expiry for "new" badges only
        if badge_type == "new" and versions and effective_expiry.mode != "never":
            if is_badge_expired(version, entry, versions, effective_expiry):
                return ""

        # Determine if badge version refers to a prerelease entry
        is_upcoming = False
        if badge_type == "new" and versions:
            badge_entry = _find_entry(version, versions)
            if badge_entry is None:
                # Try matching by label (author may write the label, e.g. "0.8")
                badge_entry = _find_entry(m.group(2) or entry.tag, versions)
            if badge_entry and badge_entry.prerelease and badge_entry.tag != entry.tag:
                is_upcoming = True

        if is_upcoming:
            css_class = "gd-badge gd-badge-upcoming"
            label = f"Upcoming in {version}"
        elif badge_type == "new":
            css_class = "gd-badge gd-badge-new"
            label = f"New in {version}"
        elif badge_type == "changed":
            css_class = "gd-badge gd-badge-changed"
            label = f"Changed in {version}"
        elif badge_type == "deprecated":
            css_class = "gd-badge gd-badge-deprecated"
            label = f"Deprecated in {version}"
        else:  # pragma: no cover
            css_class = f"gd-badge gd-badge-{badge_type}"  # pragma: no cover
            label = f"{badge_type} in {version}"  # pragma: no cover

        return f'<span class="{css_class}">{label}</span>'

    # Split content into code-block and non-code-block segments so that
    # version-badge markers inside fenced code examples are left untouched.
    _fence_re = _re.compile(r"^(`{3,}|~{3,})", _re.MULTILINE)
    parts: list[str] = []
    in_fence = False
    fence_marker = ""
    last_end = 0

    for m_fence in _fence_re.finditer(content):
        marker = m_fence.group(1)
        if not in_fence:
            # Opening fence — expand badges in the text before the fence
            parts.append(_VERSION_BADGE_RE.sub(_replace, content[last_end : m_fence.start()]))
            in_fence = True
            fence_marker = marker[0] * len(marker)
            last_end = m_fence.start()
        else:
            # Potential closing fence — must use same char and at least as many
            if marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                # Include through end of this line (closing fence)
                line_end = content.find("\n", m_fence.end())
                if line_end == -1:
                    line_end = len(content)
                else:
                    line_end += 1
                parts.append(content[last_end:line_end])
                last_end = line_end
                in_fence = False
                fence_marker = ""

    # Remaining text after the last fence (or all text if no fences)
    parts.append(_VERSION_BADGE_RE.sub(_replace, content[last_end:]))
    return "".join(parts)


def expand_version_callouts(content: str, entry: VersionEntry) -> str:
    """
    Convert `.version-note` and `.version-deprecated` fenced divs into Quarto callout blocks.

    Transforms::

        ::: {.version-note version="0.3"}
        This feature was added in 0.3.
        :::

    Into::

        ::: {.callout-note title="Added in 0.3"}
        This feature was added in 0.3.
        :::

    And::

        ::: {.version-deprecated version="0.2"}
        Use `new_func()` instead.
        :::

    Into::

        ::: {.callout-warning title="Deprecated since 0.2"}
        Use `new_func()` instead.
        :::

    Parameters
    ----------
    content
        The `.qmd` file content.
    entry
        The version being built.

    Returns
    -------
    str
        Content with version callouts converted to Quarto callouts.
    """

    def _replace_note(m: _re.Match) -> str:
        version = m.group(1) or entry.label
        return f'::: {{.callout-note title="Added in {version}"}}'

    def _replace_deprecated(m: _re.Match) -> str:
        version = m.group(1) or entry.label
        return f'::: {{.callout-warning title="Deprecated since {version}"}}'

    result = _VERSION_NOTE_RE.sub(_replace_note, content)
    result = _VERSION_DEPRECATED_RE.sub(_replace_deprecated, result)
    return result


def _rewrite_quarto_yml_for_version(
    dest_dir: Path,
    entry: VersionEntry,
    latest_tag: str,
    site_url: str | None = None,
) -> None:
    """
    Adjust the _quarto.yml in a version build directory.

    For non-latest versions, sets `site-url` with the version prefix so that relative paths and
    canonical URLs resolve correctly. Also injects canonical URL `<link>` tags pointing to the
    latest version so search engines prefer the latest docs.
    """
    from yaml12 import read_yaml, write_yaml

    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    with open(quarto_yml, "r") as f:
        config = read_yaml(f) or {}

    # For non-latest versions, set output-dir so Quarto writes to _site/
    # (it defaults to _site anyway, but be explicit)
    config.setdefault("project", {})["output-dir"] = "_site"

    # Adjust site-url for non-latest versions: append the /v/<tag>/ prefix
    # so that Quarto generates correct root-relative asset paths for versioned subpaths.
    existing_site_url = config.get("website", {}).get("site-url")
    if entry.tag != latest_tag and not entry.latest and existing_site_url:
        base = existing_site_url.rstrip("/")
        config.setdefault("website", {})["site-url"] = f"{base}/v/{entry.tag}/"

    # Set a version-specific title suffix
    if entry.tag != latest_tag and not entry.latest:
        title = config.get("website", {}).get("title", "")
        if title and f"({entry.label})" not in title:
            config.setdefault("website", {})["title"] = f"{title} ({entry.label})"

    # Canonical URL injection for non-latest versions
    if entry.tag != latest_tag and not entry.latest and site_url:
        # Inject a <link rel="canonical"> pointing to the latest version
        # This tells search engines to prefer the root (latest) URL
        base = site_url.rstrip("/")
        canonical_script = (
            "<script>"
            'document.addEventListener("DOMContentLoaded",function(){'
            f'var base="{base}";'
            "var path=window.location.pathname;"
            f'var prefix="/v/{entry.tag}/";'
            "if(path.startsWith(prefix)){path=path.slice(prefix.length-1)}"
            'var link=document.createElement("link");'
            'link.rel="canonical";'
            "link.href=base+path;"
            "document.head.appendChild(link)"
            "});"
            "</script>"
        )
        header_list = (
            config.setdefault("format", {})
            .setdefault("html", {})
            .setdefault("include-in-header", [])
        )
        if isinstance(header_list, str):
            header_list = [header_list]
            config["format"]["html"]["include-in-header"] = header_list
        header_list.append({"text": canonical_script})

    with open(quarto_yml, "w") as f:
        f.write(QUARTO_YML_HEADER)
        write_yaml(config, f)


# ---------------------------------------------------------------------------
# Stage 2: Parallel Quarto renders
# ---------------------------------------------------------------------------

_PAGE_RE = re.compile(r"\[\s*(\d+)/(\d+)\]\s+(.+)")


def _render_single_version(  # pragma: no cover
    build_dir: str,
    env_vars: dict[str, str] | None,
) -> tuple[str, int, str, str]:
    """
    Render a single version's Quarto project.

    This function is designed to be called in a subprocess pool. Returns
    `(build_dir, returncode, stdout, stderr)`.
    """
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    _TRANSIENT_PATTERNS = (
        "No such file or directory",
        "renameSync",
        "os error 2",
    )

    for attempt in range(2):
        try:
            result = subprocess.run(
                ["quarto", "render"],
                cwd=build_dir,
                capture_output=True,
                **TEXT_MODE_KWARGS,
                env=env,
                timeout=600,
            )
            # Retry once on transient filesystem race conditions
            if (
                result.returncode != 0
                and attempt == 0
                and any(p in result.stderr for p in _TRANSIENT_PATTERNS)
            ):
                continue
            return (build_dir, result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (build_dir, -1, "", "Quarto render timed out after 600 seconds")
        except Exception as e:
            return (build_dir, -1, "", str(e))

    return (build_dir, result.returncode, result.stdout, result.stderr)  # type: ignore[possibly-undefined]


def _render_single_version_streaming(  # pragma: no cover
    build_dir: str,
    env_vars: dict[str, str] | None,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[str, int, str, str, list[dict[str, Any]]]:
    """
    Render a single version with streaming progress.

    Like :func:`_render_single_version` but streams stderr to parse Quarto `[cur/total] page`
    progress lines and calls *on_progress(current, total)* for each update. Returns
    `(build_dir, returncode, stdout, stderr, page_timings)`.
    """
    import time as _time_mod

    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        proc = subprocess.Popen(
            ["quarto", "render"],
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **TEXT_MODE_KWARGS,
            env=env,
            bufsize=1,
        )
    except Exception as e:
        return (build_dir, -1, "", str(e), [])

    stderr_lines: list[str] = []
    # Each entry: (page_path, timestamp)
    _page_timestamps: list[tuple[str, float]] = []
    _ansi_re = re.compile(r"\033\[[0-9;]*m")

    def _read_stderr():
        for line in proc.stderr:  # type: ignore[union-attr]
            stderr_lines.append(line)
            m = _PAGE_RE.search(line)
            if m:
                page_path = _ansi_re.sub("", m.group(3)).strip()
                _page_timestamps.append((page_path, _time_mod.monotonic()))
                if on_progress:
                    on_progress(int(m.group(1)), int(m.group(2)))

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    stdout_data = proc.stdout.read() if proc.stdout else ""  # type: ignore[union-attr]
    proc.wait()
    stderr_thread.join(timeout=10)

    # Compute per-page durations from consecutive timestamps
    page_timings: list[dict[str, Any]] = []
    for i, (page_path, ts) in enumerate(_page_timestamps):
        if i + 1 < len(_page_timestamps):
            duration = _page_timestamps[i + 1][1] - ts
        else:
            duration = _time_mod.monotonic() - ts
        page_timings.append({"page": page_path, "seconds": round(duration, 3)})

    # Retry once on transient filesystem race conditions
    _TRANSIENT_PATTERNS = (
        "No such file or directory",
        "renameSync",
        "os error 2",
    )
    full_stderr = "".join(stderr_lines)
    if proc.returncode != 0 and any(p in full_stderr for p in _TRANSIENT_PATTERNS):
        # Reset and retry
        stderr_lines.clear()
        _page_timestamps.clear()

        try:
            proc = subprocess.Popen(
                ["quarto", "render"],
                cwd=build_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **TEXT_MODE_KWARGS,
                env=env,
                bufsize=1,
            )
        except Exception as e:
            return (build_dir, -1, "", str(e), [])

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()
        stdout_data = proc.stdout.read() if proc.stdout else ""  # type: ignore[union-attr]
        proc.wait()
        stderr_thread.join(timeout=10)

        page_timings = []
        for i, (page_path, ts) in enumerate(_page_timestamps):
            if i + 1 < len(_page_timestamps):
                duration = _page_timestamps[i + 1][1] - ts
            else:
                duration = _time_mod.monotonic() - ts
            page_timings.append({"page": page_path, "seconds": round(duration, 3)})

        return (build_dir, proc.returncode, stdout_data, "".join(stderr_lines), page_timings)

    return (build_dir, proc.returncode, stdout_data, full_stderr, page_timings)


def render_versions_parallel(
    build_dirs: list[Path],
    env_vars: dict[str, str] | None = None,
    max_workers: int | None = None,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> list[tuple[str, int, str, str, list[dict[str, Any]]]]:
    """
    Run `quarto render` in parallel for each version build directory.

    Parameters
    ----------
    build_dirs
        List of per-version build directories.
    env_vars
        Environment variables to pass to Quarto (e.g., QUARTO_PYTHON).
    max_workers
        Max parallel renders. Defaults to `min(cpu_count, 4)`.
    progress_callback
        Optional `(slot_index, current_page, total_pages)` callback. When provided, renders use
        streaming mode so progress lines can be reported in real time.

    Returns
    -------
    list[tuple[str, int, str, str, list[dict[str, Any]]]]
        List of `(build_dir, returncode, stdout, stderr, page_timings)` tuples in the same order
        as `build_dirs`.
    """
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 4)

    if progress_callback is None:
        # Original fire-and-forget mode (ProcessPoolExecutor)
        results: list[tuple[str, int, str, str, list[dict[str, Any]]]] = []

        if len(build_dirs) == 1:
            r = _render_single_version(str(build_dirs[0]), env_vars)
            # Non-streaming mode has no page timings
            results.append((*r, []))
            return results

        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_render_single_version, str(d), env_vars): d for d in build_dirs}
            for future in as_completed(futures):
                results.append((*future.result(), []))
        return results

    # Streaming mode: use threads so callbacks can update the parent process.
    dir_to_idx = {str(d): i for i, d in enumerate(build_dirs)}
    ordered_results: list[tuple[str, int, str, str, list[dict[str, Any]]] | None] = [None] * len(
        build_dirs
    )

    def _run(build_dir: Path) -> tuple[str, int, str, str, list[dict[str, Any]]]:
        idx = dir_to_idx[str(build_dir)]

        def _on_progress(current: int, total: int) -> None:
            progress_callback(idx, current, total)

        return _render_single_version_streaming(str(build_dir), env_vars, _on_progress)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run, d): d for d in build_dirs}
        for future in as_completed(futures):
            r = future.result()
            idx = dir_to_idx[r[0]]
            ordered_results[idx] = r

    return [r for r in ordered_results if r is not None]


# ---------------------------------------------------------------------------
# Stage 3: Assemble rendered output
# ---------------------------------------------------------------------------


def assemble_site(
    source_dir: Path,
    versions: list[VersionEntry],
    latest_tag: str,
    output_dir: Path,
) -> None:
    """
    Merge per-version rendered sites into the final output directory

    Preserve the latest version when it has rendered directly into
    `output_dir`. Merge historical versions under `v/<tag>/`. If the latest
    version rendered elsewhere, replace `output_dir` before merging all sites.

    Parameters
    ----------
    source_dir
        Quarto project directory for the latest version.
    versions
        The ordered version entries.
    latest_tag
        The tag of the latest version, which becomes the site root.
    output_dir
        Final output directory, normally `great-docs/_site/`.
    """
    # The latest version may have rendered directly into `output_dir`. Preserve
    # it because build setup removed stale output before rendering began.
    in_place = (source_dir / "_site").resolve() == output_dir.resolve()

    if not in_place and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for entry in versions:
        site_dir = _version_build_dir(source_dir, entry, latest_tag) / "_site"

        if not site_dir.exists():
            continue

        if entry.tag == latest_tag:
            if in_place:
                continue
            _merge_tree(site_dir, output_dir)
        else:
            dest = output_dir / "v" / entry.tag
            dest.mkdir(parents=True, exist_ok=True)
            _merge_tree(site_dir, dest)


def _merge_tree(src: Path, dst: Path) -> None:
    """Recursively copy *src* into *dst*, merging with existing content."""
    for item in src.iterdir():
        dest_item = dst / item.name
        if item.is_dir():
            dest_item.mkdir(exist_ok=True)
            _merge_tree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)


def create_version_aliases(
    output_dir: Path,
    versions: list[VersionEntry],
    latest_tag: str,
) -> None:
    """
    Create floating version alias directories with redirect stubs.

    Creates `v/latest/`, `v/stable/`, and `v/dev/` directories containing redirect HTML pages that
    point to the actual version.

    Parameters
    ----------
    output_dir
        The final `_site/` output directory.
    versions
        The ordered version entries.
    latest_tag
        The tag of the latest version.
    """
    latest = None
    dev = None
    for v in versions:
        if v.latest:
            latest = v
        if v.prerelease:
            dev = v

    aliases: dict[str, VersionEntry | None] = {
        "latest": latest,
        "stable": latest,  # stable = latest for now
    }
    if dev:
        aliases["dev"] = dev

    for alias_name, entry in aliases.items():
        if entry is None:
            continue

        # Don't create alias if it matches an actual version tag
        if any(v.tag == alias_name for v in versions):
            continue

        if entry.tag == latest_tag:
            target_prefix = "/"
        else:
            target_prefix = f"/v/{entry.tag}/"

        alias_dir = output_dir / "v" / alias_name
        alias_dir.mkdir(parents=True, exist_ok=True)

        # Write a redirect index.html
        redirect_html = _redirect_page(target_prefix)
        (alias_dir / "index.html").write_text(redirect_html, encoding="utf-8")


def _redirect_page(target_url: str) -> str:
    """Generate a minimal redirect HTML page."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0; url={target_url}">
  <link rel="canonical" href="{target_url}">
  <title>Redirecting…</title>
</head>
<body>
  <p>Redirecting to <a href="{target_url}">{target_url}</a>…</p>
</body>
</html>
"""


def write_version_map(
    output_dir: Path,
    versions: list[VersionEntry],
    pages_by_version: dict[str, list[str]],
    fallbacks: dict[str, str] | None = None,
) -> None:
    """Write `_version_map.json` to the site output directory."""
    manifest = build_version_map(versions, pages_by_version, fallbacks=fallbacks)
    out = output_dir / "_version_map.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Full orchestrator
# ---------------------------------------------------------------------------


def run_versioned_build(  # pragma: no cover
    source_dir: Path,
    project_root: Path,
    versions_config: list[Any],
    quarto_env: dict[str, str] | None = None,
    version_tags: list[str] | None = None,
    latest_only: bool = False,
    max_workers: int | None = None,
    site_url: str | None = None,
    progress_callback: Callable[[int, int, int], None] | None = None,
    on_renders_done: Callable[[], None] | None = None,
    badge_expiry_raw: str | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """
    Build and assemble the configured documentation versions

    Parameters
    ----------
    source_dir
        Prepared documentation tree before version-specific filtering.
    project_root
        Project root containing build and cache directories.
    versions_config
        Entries from the `versions` configuration.
    quarto_env
        Environment variables for Quarto processes.
    version_tags
        Version tags to build. Build every configured version when omitted.
    latest_only
        Whether to build only the latest version.
    max_workers
        Maximum number of parallel Quarto renders.
    site_url
        Base site URL used for canonical links.
    progress_callback
        Callback that receives the render slot, current page, and total pages.
    on_renders_done
        Callback invoked after rendering and before site assembly.
    badge_expiry_raw
        Global `new_is_old` configuration value.
    config
        Project configuration. A historical version built from a snapshot or
        git tag uses it to rebuild its own inventory and interlinks index;
        omitting it leaves such a version publishing the live checkout's.

    Returns
    -------
    Build result containing `success`, `versions_built`, `pages_by_version`,
    `timings_by_version`, `warnings`, and `errors`.
    """
    versions = parse_versions_config(versions_config)
    latest = get_latest_version(versions)
    latest_tag = latest.tag if latest else versions[0].tag

    # Parse badge expiry config
    from great_docs._versioning import parse_badge_expiry

    badge_expiry = parse_badge_expiry(badge_expiry_raw)

    # Filter versions based on CLI flags
    if latest_only:
        targets = [v for v in versions if v.tag == latest_tag]
    elif version_tags:
        tag_set = set(version_tags)
        targets = [v for v in versions if v.tag in tag_set]
    else:
        targets = list(versions)

    if not targets:
        return {
            "success": False,
            "versions_built": [],
            "pages_by_version": {},
            "warnings": [],
            "errors": ["No matching versions to build"],
        }

    _check_build_dir_collisions(source_dir, targets, latest_tag)

    # Unmarked directories may contain user files. Check them before cleanup so
    # an aborted build also preserves existing, marked version output.
    for entry in targets:
        ver_dir = _version_build_dir(source_dir, entry, latest_tag)
        if ver_dir == source_dir:
            continue
        if ver_dir.is_symlink():
            raise ValueError(
                f"Version {entry.tag!r} cannot use {ver_dir} as its build directory "
                "because the path is a symlink. Remove the symlink or replace it with "
                "a directory before building."
            )
        if ver_dir.exists() and not is_great_docs_build_dir(ver_dir):
            raise ValueError(
                f"Version {entry.tag!r} would build into {ver_dir}, which already exists "
                f"but does not contain a Great Docs-generated _quarto.yml. Move or delete "
                f"the directory before building."
            )

    warnings = _clean_stale_version_dirs(source_dir)

    # --- Stage 1: Preprocess each version ---
    pages_by_version: dict[str, list[str]] = {}
    errors: list[str] = []

    # Copy historical trees before pruning `source_dir` for the latest version;
    # otherwise, historical copies inherit the latest version's exclusions.
    ordered_targets = [e for e in targets if e.tag != latest_tag]
    ordered_targets += [e for e in targets if e.tag == latest_tag]

    dir_by_tag: dict[str, Path] = {}
    for entry in ordered_targets:
        ver_dir = _version_build_dir(source_dir, entry, latest_tag)
        pages = preprocess_version(
            source_dir,
            ver_dir,
            entry,
            versions,
            project_root=project_root,
            badge_expiry=badge_expiry,
            config=config,
        )
        _prune_missing_sidebar_pages(ver_dir)
        _rewrite_quarto_yml_for_version(ver_dir, entry, latest_tag, site_url=site_url)
        _sync_status_inline_script(ver_dir)
        pages_by_version[entry.tag] = pages
        dir_by_tag[entry.tag] = ver_dir

    # Restore the requested order so each progress slot keeps its version label.
    build_dirs = [dir_by_tag[e.tag] for e in targets]

    # Map build dir to version tag (for pre-render diagnostics)
    dir_to_tag_pre = {str(dir_by_tag[e.tag]): e.tag for e in targets}

    # --- Pre-render sanity check ---
    # Verify each build directory has renderable .qmd files and a valid _quarto.yml.
    # If not, report an error instead of silently producing an empty site.
    for ver_dir in build_dirs:
        qmd_count = sum(
            1 for _ in ver_dir.rglob("*.qmd") if not str(_.relative_to(ver_dir)).startswith("_")
        )
        quarto_yml = ver_dir / "_quarto.yml"
        if not quarto_yml.exists():
            tag = dir_to_tag_pre.get(str(ver_dir), str(ver_dir))
            errors.append(
                f"Version {tag}: _quarto.yml missing from build directory. "
                f"This indicates a preprocessing failure."
            )
        elif qmd_count == 0:
            tag = dir_to_tag_pre.get(str(ver_dir), str(ver_dir))
            errors.append(
                f"Version {tag}: No .qmd files found in build directory after preprocessing. "
                f"All pages may have been excluded by version scoping."
            )

    if errors:
        # All versions have fatal pre-render issues; abort early.
        if on_renders_done:
            on_renders_done()
        return {
            "success": False,
            "versions_built": [],
            "pages_by_version": pages_by_version,
            "timings_by_version": {},
            "warnings": warnings,
            "errors": errors,
        }

    # --- Stage 2: Parallel renders ---
    render_results = render_versions_parallel(
        build_dirs,
        env_vars=quarto_env,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )

    errors_render: list[str] = []
    versions_built: list[str] = []
    timings_by_version: dict[str, list[dict[str, Any]]] = {}

    # Map build dir back to version tag
    dir_to_tag = {str(dir_by_tag[e.tag]): e.tag for e in targets}

    for build_dir, returncode, stdout, stderr, page_timings in render_results:
        tag = dir_to_tag.get(build_dir, build_dir)
        if returncode == 0:
            # Post-render validation: verify Quarto actually produced HTML pages.
            # Quarto may exit 0 without rendering anything (e.g. if it cannot find
            # renderable files or has a configuration issue). Detect this and report
            # a meaningful error instead of silently producing an empty site.
            site_dir = Path(build_dir) / "_site"
            html_files = list(site_dir.rglob("*.html")) if site_dir.exists() else []
            if not html_files:
                # Gather diagnostic info
                qmd_files = list(Path(build_dir).rglob("*.qmd"))
                diag_parts = [
                    f"Version {tag}: Quarto exited successfully but produced no HTML pages.",
                    f"  Build directory: {build_dir}",
                    f"  .qmd files present: {len(qmd_files)}",
                ]
                if stderr.strip():
                    # Limit stderr to avoid flooding logs
                    stderr_preview = stderr.strip()[:500]
                    diag_parts.append(f"  Quarto stderr: {stderr_preview}")
                else:
                    diag_parts.append("  Quarto stderr: (empty)")
                diag_parts.append(
                    "  This may indicate a Quarto configuration issue, missing dependencies, "
                    "or an incompatibility with the build environment."
                )
                errors_render.append("\n".join(diag_parts))
            else:
                versions_built.append(tag)
                if page_timings:
                    timings_by_version[tag] = page_timings
        else:
            errors_render.append(
                f"Version {tag}: Quarto render failed (exit {returncode})\n{stderr}"
            )

    errors.extend(errors_render)

    # Notify caller that rendering is complete (e.g. to finish progress bars)
    if on_renders_done:
        on_renders_done()

    if not versions_built:
        return {
            "success": False,
            "versions_built": [],
            "pages_by_version": pages_by_version,
            "timings_by_version": {},
            "warnings": warnings,
            "errors": errors,
        }

    # --- Stage 3: Assemble ---
    output_dir = source_dir / "_site"
    assemble_site(source_dir, targets, latest_tag, output_dir)

    # Write version map
    write_version_map(output_dir, versions, pages_by_version)

    # Create floating aliases
    create_version_aliases(output_dir, versions, latest_tag)

    # Generate platform redirect files (Netlify _redirects, Vercel vercel.json)
    generate_redirect_files(output_dir, versions, latest_tag)

    return {
        "success": len(errors) == 0,
        "versions_built": versions_built,
        "pages_by_version": pages_by_version,
        "timings_by_version": timings_by_version,
        "warnings": warnings,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Platform redirect file generation
# ---------------------------------------------------------------------------


def generate_redirect_files(
    output_dir: Path,
    versions: list[VersionEntry],
    latest_tag: str,
) -> None:
    """
    Generate Netlify `_redirects` and Vercel `vercel.json` redirect files.

    Creates redirect rules for floating version aliases (`/v/latest/*`,
    `/v/stable/*`, `/v/dev/*`) that map to their target version paths.

    Parameters
    ----------
    output_dir
        The final `_site/` output directory.
    versions
        The ordered version entries.
    latest_tag
        The tag of the latest version.
    """
    latest = None
    dev = None
    for v in versions:
        if v.latest:
            latest = v
        if v.prerelease:
            dev = v

    aliases: dict[str, str] = {}
    if latest:
        target = "/" if latest.tag == latest_tag else f"/v/{latest.tag}/"
        aliases["latest"] = target
        aliases["stable"] = target
    if dev:
        target = "/" if dev.tag == latest_tag else f"/v/{dev.tag}/"
        aliases["dev"] = target

    # Skip aliases that collide with real version tags
    tag_set = {v.tag for v in versions}
    aliases = {k: v for k, v in aliases.items() if k not in tag_set}

    if not aliases:
        return

    # --- Netlify _redirects ---
    lines: list[str] = [
        "# Auto-generated by great-docs for version aliases",
        "# See: https://docs.netlify.com/routing/redirects/",
    ]
    for alias, target in sorted(aliases.items()):
        lines.append(f"/v/{alias}/*    {target}:splat    200")
    lines.append("")

    (output_dir / "_redirects").write_text("\n".join(lines), encoding="utf-8")

    # --- Vercel vercel.json ---
    rewrites = []
    for alias, target in sorted(aliases.items()):
        rewrites.append(
            {
                "source": f"/v/{alias}/:path*",
                "destination": f"{target}:path*",
            }
        )

    vercel_config: dict[str, Any] = {"rewrites": rewrites}
    (output_dir / "vercel.json").write_text(
        json.dumps(vercel_config, indent=2) + "\n", encoding="utf-8"
    )
