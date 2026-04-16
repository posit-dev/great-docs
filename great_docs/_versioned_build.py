from __future__ import annotations

import json
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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


def preprocess_version(
    source_dir: Path,
    dest_dir: Path,
    entry: VersionEntry,
    all_versions: list[VersionEntry],
    project_root: Path | None = None,
    section_configs: list[dict] | None = None,
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
        if not page_matches_version(content, entry.tag):
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

    # 5. Expand inline [version-badge] markers and version callouts
    for qmd_file in _collect_qmd_files(dest_dir):
        content = qmd_file.read_text(encoding="utf-8", errors="replace")
        updated = expand_version_badges(content, entry)
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
    Regenerate API reference QMD pages from a snapshot JSON file.

    Replaces the API reference pages in *dest_dir* with pages generated from the snapshot. This
    implements Strategy A from the plan.

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
        Relative paths of generated API pages (as .html).
    """
    from great_docs._api_diff import ApiSnapshot

    snap = ApiSnapshot.load(snapshot_path)
    ref_dir = dest_dir / "reference"

    # Clear existing reference pages — the snapshot is the sole source of truth
    if ref_dir.exists():
        shutil.rmtree(ref_dir)
    ref_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    for name, sym in snap.symbols.items():
        qmd_path = ref_dir / f"{name}.qmd"

        # Build signature string
        sig = _format_signature(name, sym)

        # Build page content
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

    # Generate index page listing all symbols
    index_path = ref_dir / "index.qmd"
    index_lines = [
        "---",
        f'title: "API Reference ({entry.label})"',
        "---",
        "",
    ]

    # Group by kind
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


def expand_version_badges(content: str, entry: VersionEntry) -> str:
    """
    Expand `[version-badge new]` and `[version-badge changed 0.3]` inline markers into HTML
    `<span>` badges.

    If no version is specified in the marker, the current entry's label is used.

    Parameters
    ----------
    content
        The `.qmd` file content.
    entry
        The version being built.

    Returns
    -------
    str
        Content with markers replaced by HTML spans.
    """

    def _replace(m: _re.Match) -> str:
        badge_type = m.group(1).lower()
        version = m.group(2) or entry.label

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


def render_versions_parallel(
    build_dirs: list[Path],
    env_vars: dict[str, str] | None = None,
    max_workers: int | None = None,
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

    Returns
    -------
    list[tuple[str, int, str, str]]
        List of `(build_dir, returncode, stdout, stderr)` tuples.
    """
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 4)

    results: list[tuple[str, int, str, str]] = []

    if len(build_dirs) == 1:
        # No need for pool overhead with a single version
        r = _render_single_version(str(build_dirs[0]), env_vars)
        results.append(r)
        return results

    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_render_single_version, str(d), env_vars): d for d in build_dirs}
        for future in as_completed(futures):
            results.append(future.result())

    return results


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

    Returns
    -------
    dict[str, Any]
        Build result with keys: `"success"` (bool), `"versions_built"` (list of tags),
        `"pages_by_version"` (dict), `"errors"` (list).
    """
    versions = parse_versions_config(versions_config)
    latest = get_latest_version(versions)
    latest_tag = latest.tag if latest else versions[0].tag

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
        )
        _rewrite_quarto_yml_for_version(ver_dir, entry, latest_tag, site_url=site_url)
        pages_by_version[entry.tag] = pages
        build_dirs.append(ver_dir)

    # --- Stage 2: Parallel renders ---
    render_results = render_versions_parallel(
        build_dirs,
        env_vars=quarto_env,
        max_workers=max_workers,
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
