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
from typing import Any, Callable

from great_docs._versioning import (
    VersionEntry,
    build_version_map,
    get_latest_version,
    page_matches_version,
    parse_versions_config,
    process_version_fences,
)

# ---------------------------------------------------------------------------
# Stage 1: Preprocess — create version-specific build directories
# ---------------------------------------------------------------------------


def _version_build_dir(build_root: Path, entry: VersionEntry, latest_tag: str) -> Path:
    """Return the isolated build directory for a version."""
    if entry.tag == latest_tag:
        return build_root / "_root"
    # Replace dots/slashes with underscores for safe directory names
    safe = entry.tag.replace(".", "_").replace("/", "_")
    return build_root / f"v__{safe}"


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
    # CliCommandInfo.subcommands holds the actual commands; the group itself
    # maps to `index.qmd`.
    valid_stems: set[str] = {"index"}
    valid_names: set[str] = set()
    for sub in getattr(cli_commands, "subcommands", []):
        # Click command names use hyphens; file stems use underscores
        valid_stems.add(sub.name.replace("-", "_"))
        valid_names.add(sub.name)

    # Remove QMD files for commands not present at this version
    for qmd_file in list(cli_ref_dir.iterdir()):
        if qmd_file.suffix not in (".qmd", ".md"):
            continue
        if qmd_file.stem not in valid_stems:
            qmd_file.unlink()

    # Rewrite the index.qmd to remove stale commands from the help text
    index_qmd = cli_ref_dir / "index.qmd"
    if index_qmd.exists() and valid_names:
        _rewrite_cli_index(index_qmd, valid_names)

    # Prune the CLI sidebar in _quarto.yml
    _prune_quarto_cli_sidebar(dest_dir, valid_stems)


def _rewrite_cli_index(index_qmd: Path, valid_names: set[str]) -> None:
    """Remove lines for non-existent commands from the CLI index help block."""
    content = index_qmd.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines: list[str] = []
    in_commands_block = False

    for line in lines:
        stripped = line.strip()

        # Detect the "Commands:" header in the help text
        if stripped == "Commands:":
            in_commands_block = True
            new_lines.append(line)
            continue

        if in_commands_block:
            # End of commands block: blank line or closing fence
            if not stripped or stripped.startswith("```") or stripped.startswith(":::"):
                in_commands_block = False
                new_lines.append(line)
                continue

            # Each command line looks like "  command-name   Description text..."
            # Extract the command name (first non-whitespace token)
            tokens = stripped.split()
            if tokens and tokens[0] in valid_names:
                new_lines.append(line)
            # Skip lines for commands not in valid_names
            continue

        new_lines.append(line)

    index_qmd.write_text("\n".join(new_lines), encoding="utf-8")


def _prune_quarto_cli_sidebar(dest_dir: Path, valid_stems: set[str]) -> None:
    """Remove CLI sidebar entries from _quarto.yml for pruned commands."""
    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    try:
        import yaml

        content = yaml.safe_load(quarto_yml.read_text(encoding="utf-8"))
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
            yaml.dump(
                content,
                quarto_yml.open("w", encoding="utf-8"),
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
    except Exception:
        pass  # Best-effort


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
    except Exception:
        pass  # Best-effort; don't break the build


def preprocess_version(
    source_dir: Path,
    dest_dir: Path,
    entry: VersionEntry,
    all_versions: list[VersionEntry],
    project_root: Path | None = None,
    section_configs: list[dict] | None = None,
    badge_expiry: "BadgeExpiry | None" = None,
) -> list[str]:
    """
    Preprocess the documentation source for a single version.

    Copies the entire source tree to *dest_dir*, then:

    1. Removes pages whose frontmatter `versions:` list excludes this version.
    2. Removes pages in sections whose `versions:` list excludes this version.
    3. Processes version fences in all remaining `.qmd` files.
    4. Expands inline `[version-badge]` markers and version callouts.
    5. If the version has an `api_snapshot`, regenerates API reference pages from the snapshot
       (Strategy A).
    6. If the version has a `git_ref`, introspects the package at that tag and generates API
       reference pages (Strategy B).

    Parameters
    ----------
    source_dir
        The ephemeral `great-docs/` build directory (already populated by the normal build steps
        1-14).
    dest_dir
        The isolated per-version build directory.
    entry
        The version being built.
    all_versions
        The full ordered list of version entries.
    project_root
        Project root directory (needed for resolving snapshot paths).
    section_configs
        Section configurations from `great-docs.yml`, each a dict with at least `"dir"` and
        optionally `"versions"` keys.

    Returns
    -------
    list[str]
        Relative paths (from *dest_dir*) of pages included in this version, with `.qmd` -> `.html`
        extension mapping.
    """
    # Build a set of directories excluded by section-level version scoping
    excluded_dirs = _compute_excluded_section_dirs(entry.tag, section_configs)

    # Copy the full source tree
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(source_dir, dest_dir, dirs_exist_ok=False)

    included_pages: list[str] = []

    for qmd_file in _collect_qmd_files(dest_dir):
        rel = qmd_file.relative_to(dest_dir)

        # Skip internal files
        if str(rel).startswith("_"):
            continue

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
        if processed != content:
            qmd_file.write_text(processed, encoding="utf-8")

        # Track included page (convert .qmd → .html for the manifest)
        html_rel = str(rel).replace(".qmd", ".html").replace(".md", ".html")
        included_pages.append(html_rel)

    # 3. Strategy A: regenerate API reference from snapshot if configured
    if entry.api_snapshot and project_root:
        snap_path = project_root / entry.api_snapshot
        if snap_path.exists():
            api_pages = _rebuild_api_from_snapshot(dest_dir, snap_path, entry)
            included_pages.extend(api_pages)

    # 4. Strategy B: git-ref introspection with caching
    elif entry.git_ref and project_root:
        api_pages = _rebuild_api_from_git_ref(dest_dir, project_root, entry)
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
) -> list[str]:
    """
    Rebuild API reference pages from a snapshot, pruning pages not in the snapshot.

    When the source tree already contains reference pages (e.g. from the main build), pages for
    symbols in the snapshot are regenerated from the snapshot data and pages for symbols *not* in
    the snapshot are removed. When no reference directory exists, pages are generated from scratch.

    Parameters
    ----------
    dest_dir
        The version's build directory.
    snapshot_path
        Path to the snapshot JSON file.
    entry
        The version being built.

    Returns
    -------
    list[str]
        Relative paths of API pages (as .html).
    """
    from great_docs._api_diff import ApiSnapshot

    snap = ApiSnapshot.load(snapshot_path)
    ref_dir = dest_dir / "reference"

    snapshot_symbols = set(snap.symbols.keys())
    snapshot_classes = {name for name, sym in snap.symbols.items() if sym.kind == "class"}

    # --- Prune existing pages not in the snapshot ---
    if ref_dir.exists():
        for qmd_file in list(ref_dir.iterdir()):
            if qmd_file.is_dir():
                continue
            if qmd_file.suffix not in (".qmd", ".md"):
                continue
            stem = qmd_file.stem
            if stem == "index":
                continue
            if not _is_valid_ref_name(stem, snapshot_symbols, snapshot_classes):
                qmd_file.unlink()
    else:
        ref_dir.mkdir(parents=True, exist_ok=True)

    # --- Generate / overwrite pages for each symbol in the snapshot ---
    generated: list[str] = []

    for name, sym in snap.symbols.items():
        qmd_path = ref_dir / f"{name}.qmd"
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

    # Detect whether the existing index is a rich renderer-generated page (has Pandoc
    # attribute classes like {.doc-label ...}) vs. a plain placeholder.  Rich pages are
    # preserved and pruned; plain/missing pages are regenerated from the snapshot.
    _has_rich_index = False
    if index_path.exists():
        _idx_content = index_path.read_text(encoding="utf-8")
        _has_rich_index = "{.doc-" in _idx_content

    if _has_rich_index:
        # Preserve the styled index — just remove entries for symbols not in this version
        _prune_reference_index(index_path, snapshot_symbols, snapshot_classes)
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
    _prune_quarto_sidebar(dest_dir, "reference", snapshot_symbols, snapshot_classes)

    return generated


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


def _is_valid_ref_name(name: str, valid_symbols: set[str], valid_classes: set[str]) -> bool:
    """Check if a symbol or method name is valid for this version."""
    if name == "index" or name in valid_symbols:
        return True
    # Method page: `ClassName.method` (check the class prefix)
    if "." in name:
        class_name = name.split(".")[0]
        return class_name in valid_classes
    return False


def _prune_reference_index(
    index_qmd: Path, valid_symbols: set[str], valid_classes: set[str]
) -> None:
    """Remove links/rows for symbols not in the snapshot from reference/index.qmd."""
    content = index_qmd.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for definition-list or link-style entries referencing a .qmd file
        # Patterns: "- [SymbolName](SymbolName.qmd)" or link with anchor
        import re

        qmd_ref = re.search(r"\(([^)]+)\.qmd(?:#[^)]*)?\)", stripped)
        if qmd_ref:
            symbol_name = qmd_ref.group(1)
            if not _is_valid_ref_name(symbol_name, valid_symbols, valid_classes):
                continue  # Skip this line

        # Also check for bare .qmd references like "  - Name.qmd"
        bare_ref = re.match(r"^\s*-\s+(\S+)\.qmd\s*$", stripped)
        if bare_ref:
            symbol_name = bare_ref.group(1)
            if not _is_valid_ref_name(symbol_name, valid_symbols, valid_classes):
                continue

        new_lines.append(line)

    index_qmd.write_text("\n".join(new_lines), encoding="utf-8")


def _prune_quarto_sidebar(
    dest_dir: Path, section: str, valid_symbols: set[str], valid_classes: set[str]
) -> None:
    """Remove sidebar entries for missing symbols/commands from _quarto.yml."""
    quarto_yml = dest_dir / "_quarto.yml"
    if not quarto_yml.exists():
        return

    try:
        import yaml

        content = yaml.safe_load(quarto_yml.read_text(encoding="utf-8"))
        if not content:
            return

        sidebars = content.get("website", {}).get("sidebar", [])
        modified = False

        for sidebar in sidebars:
            contents = sidebar.get("contents", [])
            if not contents:
                continue

            # Check if this sidebar references our section
            has_section_ref = any(
                (isinstance(c, str) and c.startswith(f"{section}/")) for c in contents
            )
            if not has_section_ref:
                continue

            new_contents = []
            for item in contents:
                if isinstance(item, str) and item.startswith(f"{section}/"):
                    # e.g. "reference/GreatDocs.qmd" → "GreatDocs"
                    # e.g. "reference/cli/api_diff.qmd" → keep (handled by CLI pruning)
                    if "/" in item.replace(f"{section}/", "", 1):
                        # Sub-path like reference/cli/... — keep, CLI pruning handles it
                        new_contents.append(item)
                    else:
                        stem = Path(item).stem
                        if _is_valid_ref_name(stem, valid_symbols, valid_classes):
                            new_contents.append(item)
                        else:
                            modified = True
                else:
                    new_contents.append(item)

            if modified:
                sidebar["contents"] = new_contents

        if modified:
            yaml.dump(
                content,
                quarto_yml.open("w", encoding="utf-8"),
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
    except Exception:
        pass  # Best-effort


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
            text=True,
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

        snap = snapshot_at_tag(project_root, git_ref, pkg_name)
        if snap is None:
            return []

        # Save to cache for future builds
        snap.save(cache_path)

    # Reuse the snapshot-based builder
    return _rebuild_api_from_snapshot(dest_dir, cache_path, entry)


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
    Expand `[version-badge new]` and `[version-badge changed 0.3]` inline markers into HTML
    `<span>` badges.

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
    from great_docs._versioning import BADGE_EXPIRY_NEVER, is_badge_expired

    effective_expiry = expiry or BADGE_EXPIRY_NEVER

    def _replace(m: _re.Match) -> str:
        badge_type = m.group(1).lower()
        version = m.group(2) or entry.label

        # Check expiry for "new" badges only
        if badge_type == "new" and versions and effective_expiry.mode != "never":
            if is_badge_expired(version, entry, versions, effective_expiry):
                return ""

        css_class = f"gd-badge gd-badge-{badge_type}"
        if badge_type == "new":
            label = f"New in {version}"
        elif badge_type == "changed":
            label = f"Changed in {version}"
        elif badge_type == "deprecated":
            label = f"Deprecated in {version}"
        else:
            label = f"{badge_type} in {version}"

        return f'<span class="{css_class}">{label}</span>'

    return _VERSION_BADGE_RE.sub(_replace, content)


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
        write_yaml(config, f)


# ---------------------------------------------------------------------------
# Stage 2: Parallel Quarto renders
# ---------------------------------------------------------------------------

_PAGE_RE = re.compile(r"\[\s*(\d+)/(\d+)\]")


def _render_single_version(
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

    try:
        result = subprocess.run(
            ["quarto", "render"],
            cwd=build_dir,
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        return (build_dir, result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (build_dir, -1, "", "Quarto render timed out after 600 seconds")
    except Exception as e:
        return (build_dir, -1, "", str(e))


def _render_single_version_streaming(
    build_dir: str,
    env_vars: dict[str, str] | None,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[str, int, str, str]:
    """
    Render a single version with streaming progress.

    Like :func:`_render_single_version` but streams stderr to parse Quarto `[cur/total]` progress
    lines and calls *on_progress(current, total)* for each update. Returns the same
    `(build_dir, returncode, stdout, stderr)` tuple.
    """
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    try:
        proc = subprocess.Popen(
            ["quarto", "render"],
            cwd=build_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=1,
        )
    except Exception as e:
        return (build_dir, -1, "", str(e))

    stderr_lines: list[str] = []

    def _read_stderr():
        for line in proc.stderr:  # type: ignore[union-attr]
            stderr_lines.append(line)
            if on_progress:
                m = _PAGE_RE.search(line)
                if m:
                    on_progress(int(m.group(1)), int(m.group(2)))

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    stdout_data = proc.stdout.read() if proc.stdout else ""  # type: ignore[union-attr]
    proc.wait()
    stderr_thread.join(timeout=10)

    return (build_dir, proc.returncode, stdout_data, "".join(stderr_lines))


def render_versions_parallel(
    build_dirs: list[Path],
    env_vars: dict[str, str] | None = None,
    max_workers: int | None = None,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> list[tuple[str, int, str, str]]:
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
    list[tuple[str, int, str, str]]
        List of `(build_dir, returncode, stdout, stderr)` tuples in the same order as `build_dirs`.
    """
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 4)

    if progress_callback is None:
        # Original fire-and-forget mode (ProcessPoolExecutor)
        results: list[tuple[str, int, str, str]] = []

        if len(build_dirs) == 1:
            r = _render_single_version(str(build_dirs[0]), env_vars)
            results.append(r)
            return results

        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_render_single_version, str(d), env_vars): d for d in build_dirs}
            for future in as_completed(futures):
                results.append(future.result())
        return results

    # Streaming mode: use threads so callbacks can update the parent process.
    dir_to_idx = {str(d): i for i, d in enumerate(build_dirs)}
    ordered_results: list[tuple[str, int, str, str] | None] = [None] * len(build_dirs)

    def _run(build_dir: Path) -> tuple[str, int, str, str]:
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
    build_root: Path,
    versions: list[VersionEntry],
    latest_tag: str,
    output_dir: Path,
) -> None:
    """
    Merge per-version rendered sites into the final output directory.

    - `_root/_site/*` -> `output_dir/`
    - `v__X_Y/_site/*` -> `output_dir/v/X.Y/`

    Parameters
    ----------
    build_root
        Parent directory containing per-version build dirs.
    versions
        The ordered version entries.
    latest_tag
        The tag of the latest version (becomes site root).
    output_dir
        Final output directory (e.g., `great-docs/_site/`).
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for entry in versions:
        ver_dir = _version_build_dir(build_root, entry, latest_tag)
        site_dir = ver_dir / "_site"

        if not site_dir.exists():
            continue

        if entry.tag == latest_tag:
            # Latest version goes to site root
            _merge_tree(site_dir, output_dir)
        else:
            # Historical versions go under /v/<tag>/
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


def run_versioned_build(
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
) -> dict[str, Any]:
    """
    Orchestrate a full multi-version build.

    This is the main entry point called by `GreatDocs.build()` when `versions:` config is present.

    Parameters
    ----------
    source_dir
        The ephemeral `great-docs/` build directory (steps 1-14 complete).
    project_root
        The project root directory.
    versions_config
        The raw `versions:` list from config.
    quarto_env
        Environment variables for Quarto subprocesses.
    version_tags
        If provided, only build these specific version tags.
    latest_only
        If True, build only the latest version.
    max_workers
        Max parallel Quarto renders.
    site_url
        The site's base URL (for canonical URL injection).
    progress_callback
        Optional `(slot_index, current_page, total_pages)` callback for real-time progress reporting
        during parallel renders.
    on_renders_done
        Optional callback fired after all Quarto renders complete but before site assembly begins.
        Useful for finishing progress bars.

    Returns
    -------
    dict[str, Any]
        Build result with keys: `"success"` (bool), `"versions_built"` (list of tags),
        `"pages_by_version"` (dict), `"errors"` (list).
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
            "errors": ["No matching versions to build"],
        }

    build_root = project_root / ".great-docs-build"
    if build_root.exists():
        shutil.rmtree(build_root)
    build_root.mkdir(parents=True)

    # --- Stage 1: Preprocess each version ---
    pages_by_version: dict[str, list[str]] = {}
    build_dirs: list[Path] = []

    for entry in targets:
        ver_dir = _version_build_dir(build_root, entry, latest_tag)
        pages = preprocess_version(
            source_dir,
            ver_dir,
            entry,
            versions,
            project_root=project_root,
            badge_expiry=badge_expiry,
        )
        _prune_missing_sidebar_pages(ver_dir)
        _rewrite_quarto_yml_for_version(ver_dir, entry, latest_tag, site_url=site_url)
        pages_by_version[entry.tag] = pages
        build_dirs.append(ver_dir)

    # --- Stage 2: Parallel renders ---
    render_results = render_versions_parallel(
        build_dirs,
        env_vars=quarto_env,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )

    errors: list[str] = []
    versions_built: list[str] = []

    # Map build dir back to version tag
    dir_to_tag = {str(_version_build_dir(build_root, e, latest_tag)): e.tag for e in targets}

    for build_dir, returncode, stdout, stderr in render_results:
        tag = dir_to_tag.get(build_dir, build_dir)
        if returncode == 0:
            versions_built.append(tag)
        else:
            errors.append(f"Version {tag}: Quarto render failed (exit {returncode})\n{stderr}")

    # Notify caller that rendering is complete (e.g. to finish progress bars)
    if on_renders_done:
        on_renders_done()

    if not versions_built:
        return {
            "success": False,
            "versions_built": [],
            "pages_by_version": pages_by_version,
            "errors": errors,
        }

    # --- Stage 3: Assemble ---
    output_dir = source_dir / "_site"
    assemble_site(build_root, targets, latest_tag, output_dir)

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
