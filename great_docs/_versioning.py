from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VersionEntry:
    """A single version declared in great-docs.yml."""

    tag: str
    label: str
    latest: bool = False
    prerelease: bool = False
    eol: bool = False
    api_snapshot: str | None = None
    git_ref: str | None = None

    # Positional index in the versions list (0 = newest).
    # Set by parse_versions_config after construction.
    _index: int = field(default=0, repr=False)


def parse_versions_config(raw: list[Any]) -> list[VersionEntry]:
    """
    Parse the `versions:` list from great-docs.yml.

    Accepts both the minimal form (list of strings) and the full form (list of dicts). Returns an
    ordered list of `VersionEntry` objects with positional indices assigned (0 = newest).

    Parameters
    ----------
    raw
        The raw `versions:` value from the config file.

    Returns
    -------
    list[VersionEntry]
        Parsed and validated version entries, newest first.

    Raises
    ------
    ValueError
        If the input is empty, contains duplicates, or has invalid entries.
    """
    if not raw:
        raise ValueError("versions: list must not be empty")

    entries: list[VersionEntry] = []
    seen_tags: set[str] = set()

    for i, item in enumerate(raw):
        if isinstance(item, str):
            entry = VersionEntry(tag=item, label=item)
        elif isinstance(item, dict):
            tag = str(item.get("tag", item.get("label", "")))
            label = str(item.get("label", tag))
            if not tag:
                raise ValueError(f"versions[{i}]: must have a 'tag' or 'label' key")
            entry = VersionEntry(
                tag=tag,
                label=label,
                latest=bool(item.get("latest", False)),
                prerelease=bool(item.get("prerelease", False)),
                eol=bool(item.get("eol", False)),
                api_snapshot=item.get("api_snapshot"),
                git_ref=item.get("git_ref"),
            )
        else:
            raise ValueError(f"versions[{i}]: expected a string or dict, got {type(item).__name__}")

        if entry.tag in seen_tags:
            raise ValueError(f"versions[{i}]: duplicate tag '{entry.tag}'")
        seen_tags.add(entry.tag)

        entry._index = i
        entries.append(entry)

    # If no entry is explicitly marked latest, the first non-prerelease entry is latest
    if not any(e.latest for e in entries):
        for e in entries:
            if not e.prerelease:
                e.latest = True
                break

    return entries


def get_latest_version(versions: list[VersionEntry]) -> VersionEntry | None:
    """Return the version marked as `latest`, or `None`."""
    for v in versions:
        if v.latest:
            return v
    return None


# ---------------------------------------------------------------------------
# Version expression evaluation
# ---------------------------------------------------------------------------

# Regex for a single version constraint: optional operator + tag
_CONSTRAINT_RE = re.compile(r"^(>=|<=|>|<|=)?(.+)$")


def _resolve_index(tag: str, versions: list[VersionEntry]) -> int | None:
    """Return the positional index of `tag` in `versions`, or None."""
    for v in versions:
        if v.tag == tag:
            return v._index
    return None


def evaluate_version_expr(
    expr: str,
    target_tag: str,
    versions: list[VersionEntry],
) -> bool:
    """
    Evaluate a version expression against a target version.

    Parameters
    ----------
    expr
        A version expression string, e.g. `">=0.3"`, `"0.1,0.2"`, `"*"`, `">0.1,<0.4"`.
    target_tag
        The tag of the version being built.
    versions
        The full ordered list of version entries (for resolving comparisons).

    Returns
    -------
    bool
        Whether the target version matches the expression.
    """
    expr = expr.strip()

    if expr == "*":
        return True

    target_idx = _resolve_index(target_tag, versions)
    if target_idx is None:
        return False

    # Split on comma — each part is a constraint
    parts = [p.strip() for p in expr.split(",")]

    # Determine mode: if ALL parts are bare tags (no operator), use OR logic
    # (set membership). Otherwise, use AND logic (range constraint).
    all_bare = all(not _CONSTRAINT_RE.match(p).group(1) for p in parts if _CONSTRAINT_RE.match(p))

    if all_bare:
        # OR mode: target must match at least one bare tag
        for part in parts:
            m = _CONSTRAINT_RE.match(part)
            if not m:
                continue
            ref_tag = m.group(2)
            ref_idx = _resolve_index(ref_tag, versions)
            if ref_idx is not None and target_idx == ref_idx:
                return True
        return False

    # AND mode: all constraints must be satisfied
    for part in parts:
        m = _CONSTRAINT_RE.match(part)
        if not m:
            return False

        op, ref_tag = m.group(1) or "", m.group(2)
        ref_idx = _resolve_index(ref_tag, versions)

        if ref_idx is None:
            return False

        # Note: index 0 is the *newest*, so "newer" means *smaller* index.
        # ">=" means "this version or newer" → target_idx <= ref_idx
        if op == "" or op == "=":
            if target_idx != ref_idx:
                return False
        elif op == ">=":
            if target_idx > ref_idx:
                return False
        elif op == "<=":
            if target_idx < ref_idx:
                return False
        elif op == ">":
            if target_idx >= ref_idx:
                return False
        elif op == "<":
            if target_idx <= ref_idx:
                return False

    return True


# ---------------------------------------------------------------------------
# Version fence preprocessing
# ---------------------------------------------------------------------------

# Matches opening ::: {.version-only ...} or ::: {.version-except ...}
_FENCE_OPEN_RE = re.compile(
    r"^:{3,}\s*\{\s*\.(version-only|version-except)\s+versions?=\"([^\"]+)\"\s*\}\s*$"
)

# Matches a closing ::: (exactly three or more colons, nothing else)
_FENCE_CLOSE_RE = re.compile(r"^:{3,}\s*$")


def process_version_fences(
    content: str,
    target_tag: str,
    versions: list[VersionEntry],
) -> str:
    """
    Process version fences in .qmd content for a specific target version.

    Evaluates `::: {.version-only versions="..."}` and `::: {.version-except versions="..."}` fenced
    divs. Matching blocks have their fence markers removed (content kept); non-matching blocks are
    removed entirely.

    Parameters
    ----------
    content
        The raw .qmd file content.
    target_tag
        The version tag being built.
    versions
        The full ordered list of version entries.

    Returns
    -------
    str
        The processed content with version fences resolved.
    """
    lines = content.split("\n")
    result: list[str] = []

    # Stack tracks nested fences: each entry is (include: bool, colon_count: int)
    stack: list[tuple[bool, int]] = []

    # Track fenced code blocks (``` or ````+) so we don't process
    # version fences that appear inside code examples.
    in_code_block = False
    code_fence_pattern = ""

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Toggle code block state on ``` or ```` lines
        if not in_code_block and (stripped.startswith("```") or stripped.startswith("~~~~")):
            marker = stripped[:3] if stripped.startswith("```") else stripped[:4]
            # Count the actual fence chars
            fence_char = marker[0]
            fence_len = 0
            for ch in stripped:
                if ch == fence_char:
                    fence_len += 1
                else:
                    break
            code_fence_pattern = fence_char * fence_len
            in_code_block = True
            if not stack or stack[-1][0]:
                result.append(line)
            i += 1
            continue
        elif in_code_block:
            if stripped.startswith(code_fence_pattern) and stripped.rstrip(code_fence_pattern[0]) == "":
                in_code_block = False
                code_fence_pattern = ""
            if not stack or stack[-1][0]:
                result.append(line)
            i += 1
            continue

        # Check for version fence opening
        m = _FENCE_OPEN_RE.match(line)
        if m:
            fence_type = m.group(1)  # "version-only" or "version-except"
            expr = m.group(2)

            matches = evaluate_version_expr(expr, target_tag, versions)
            include = matches if fence_type == "version-only" else not matches

            # If we're already inside an excluded block, this nested block is
            # also excluded regardless
            if stack and not stack[-1][0]:
                include = False

            # Count colons in opening fence for matching the close
            colon_count = len(line) - len(line.lstrip(":"))
            stack.append((include, colon_count))
            i += 1
            continue

        # Check for fence close
        close_m = _FENCE_CLOSE_RE.match(line)
        if close_m and stack:
            stack.pop()
            i += 1
            continue

        # Emit or skip line based on stack state
        if not stack or stack[-1][0]:
            result.append(line)

        i += 1

    return "\n".join(result)


# ---------------------------------------------------------------------------
# Page-level version scoping
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_VERSIONS_KEY_RE = re.compile(r"^versions:\s*\[([^\]]*)\]", re.MULTILINE)
_VERSIONS_SCALAR_RE = re.compile(r'^versions:\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)
_VERSIONS_LIST_RE = re.compile(r"^versions:\s*$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^\s*-\s*[\"']?([^\"'\s]+)[\"']?\s*$", re.MULTILINE)


def extract_page_versions(content: str) -> list[str] | None:
    """
    Extract the `versions:` list from a .qmd file's YAML frontmatter.

    Parameters
    ----------
    content
        The raw .qmd file content.

    Returns
    -------
    list[str] | None
        The list of version tags the page applies to, or `None` if no `versions:` key is present
        (meaning the page applies to all versions).
    """
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        return None

    frontmatter = fm_match.group(1)

    # Try inline list form: versions: ["0.3", "dev"]
    inline_match = _VERSIONS_KEY_RE.search(frontmatter)
    if inline_match:
        items_str = inline_match.group(1)
        items = [s.strip().strip("\"'") for s in items_str.split(",") if s.strip()]
        return items if items else None

    # Try scalar string form: versions: ">=0.7"
    scalar_match = _VERSIONS_SCALAR_RE.search(frontmatter)
    if scalar_match:
        return [scalar_match.group(1)]

    # Try block list form:
    # versions:
    #   - "0.3"
    #   - "dev"
    block_match = _VERSIONS_LIST_RE.search(frontmatter)
    if block_match:
        # Find list items after the versions: key
        rest = frontmatter[block_match.end() :]
        items = []
        for line in rest.split("\n"):
            item_match = _LIST_ITEM_RE.match(line)
            if item_match:
                items.append(item_match.group(1))
            elif line.strip() and not line.startswith(" "):
                break  # Next YAML key — stop
        return items if items else None

    return None


def page_matches_version(
    content: str,
    target_tag: str,
    versions: list[VersionEntry] | None = None,
) -> bool:
    """
    Check whether a page should be included for a given target version.

    Parameters
    ----------
    content
        The raw .qmd file content.
    target_tag
        The version tag being built.
    versions
        The full ordered list of version entries. When provided, version expressions
        (e.g. ``">=0.7"``) are evaluated; otherwise only bare tag matching is used.

    Returns
    -------
    bool
        `True` if the page should be included (no `versions:` key, or the target tag matches
        the expression).
    """
    page_versions = extract_page_versions(content)
    if page_versions is None:
        return True

    # Join all entries into a single expression and evaluate through the
    # expression engine. This handles both bare tags ("0.7,dev" → OR mode)
    # and operator expressions (">=0.7" → AND mode) uniformly.
    if versions is not None:
        expr = ",".join(page_versions)
        return evaluate_version_expr(expr, target_tag, versions)

    return target_tag in page_versions


# ---------------------------------------------------------------------------
# Version map manifest
# ---------------------------------------------------------------------------


def build_version_map(
    versions: list[VersionEntry],
    pages_by_version: dict[str, list[str]],
    fallbacks: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build the `_version_map.json` manifest consumed by the version selector.

    Parameters
    ----------
    versions
        The ordered list of version entries.
    pages_by_version
        Mapping from version tag to list of page paths (relative, e.g. `"user-guide/index.html"`).
    fallbacks
        Optional mapping from page path to its fallback page path.

    Returns
    -------
    dict
        The manifest structure ready for JSON serialization.
    """
    latest = get_latest_version(versions)
    latest_tag = latest.tag if latest else (versions[0].tag if versions else "")

    version_list = []
    for v in versions:
        entry: dict[str, Any] = {
            "tag": v.tag,
            "label": v.label,
        }
        if v.latest:
            entry["latest"] = True
            entry["path_prefix"] = ""
        else:
            entry["path_prefix"] = f"v/{v.tag}"
        if v.prerelease:
            entry["prerelease"] = True
        if v.eol:
            entry["eol"] = True
        version_list.append(entry)

    # Build pages map: page path -> list of version tags that include it
    all_pages: set[str] = set()
    for page_list in pages_by_version.values():
        all_pages.update(page_list)

    pages_map: dict[str, list[str]] = {}
    for page in sorted(all_pages):
        tags = [v.tag for v in versions if page in pages_by_version.get(v.tag, [])]
        if tags:
            pages_map[page] = tags

    manifest: dict[str, Any] = {
        "versions": version_list,
        "pages": pages_map,
    }

    if fallbacks:
        manifest["fallbacks"] = fallbacks

    return manifest
