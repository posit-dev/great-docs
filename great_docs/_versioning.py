from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
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
    released: str | None = None
    version: str | None = None

    # Positional index in the versions list (0 = newest).
    # Set by parse_versions_config after construction.
    _index: int = field(default=0, repr=False)


@dataclass
class BadgeExpiry:
    """Controls when 'new' badges stop rendering."""

    mode: str  # "releases" | "minor_releases" | "version" | "date" | "days" | "never"
    value: int | str = 0  # count, version tag, ISO date string, or day count


# Sentinel for "never expire"
BADGE_EXPIRY_NEVER = BadgeExpiry(mode="never")


_BADGE_EXPIRY_RE = re.compile(r"^(\d+)\s+(releases?|minor\s+releases?)$", re.IGNORECASE)
_BADGE_EXPIRY_DAYS_RE = re.compile(r"^(\d+)\s+days?$", re.IGNORECASE)
_BADGE_EXPIRY_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_badge_expiry(raw: str | None) -> BadgeExpiry:
    """
    Parse a `new_is_old` value into a `BadgeExpiry`.

    Accepted forms::

        "never"            → BadgeExpiry("never")
        "3 releases"       → BadgeExpiry("releases", 3)
        "2 minor releases" → BadgeExpiry("minor_releases", 2)
        "0.8"              → BadgeExpiry("version", "0.8")
        "2026-06-01"       → BadgeExpiry("date", "2026-06-01")
        "180 days"         → BadgeExpiry("days", 180)
    """
    if raw is None or str(raw).strip().lower() == "never":
        return BADGE_EXPIRY_NEVER

    raw = str(raw).strip()

    # "3 releases" or "2 minor releases"
    m = _BADGE_EXPIRY_RE.match(raw)
    if m:
        count = int(m.group(1))
        kind = m.group(2).lower()
        if "minor" in kind:
            return BadgeExpiry(mode="minor_releases", value=count)
        return BadgeExpiry(mode="releases", value=count)

    # "180 days"
    m = _BADGE_EXPIRY_DAYS_RE.match(raw)
    if m:
        return BadgeExpiry(mode="days", value=int(m.group(1)))

    # "2026-06-01" (ISO date)
    if _BADGE_EXPIRY_DATE_RE.match(raw):
        return BadgeExpiry(mode="date", value=raw)

    # Bare version tag: "0.8", "v1.2", etc.
    return BadgeExpiry(mode="version", value=raw)


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
                released=item.get("released"),
                version=item.get("version"),
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
    # Fallback: try stripping or adding 'v' prefix
    alt = tag[1:] if tag.startswith("v") else f"v{tag}"
    for v in versions:
        if v.tag == alt:
            return v._index
    # Fallback: match against the version field (e.g. tag="dev", version="0.8")
    for v in versions:
        if v.version and v.version == tag:
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
# Badge expiry evaluation
# ---------------------------------------------------------------------------


def is_badge_expired(
    badge_version: str,
    target_entry: VersionEntry,
    versions: list[VersionEntry],
    expiry: BadgeExpiry,
) -> bool:
    """
    Determine whether a `[version-badge new VERSION]` should be suppressed.

    Parameters
    ----------
    badge_version
        The version tag written in the badge (e.g. `"0.5"`).
    target_entry
        The version currently being built.
    versions
        The full ordered list of version entries.
    expiry
        The badge expiry policy.

    Returns
    -------
    bool
        `True` if the badge should **not** be rendered (expired).
    """
    if expiry.mode == "never":
        return False

    if expiry.mode == "releases":
        badge_idx = _resolve_index(badge_version, versions)
        if badge_idx is None:
            return False
        distance = badge_idx - target_entry._index  # positive = target is newer
        return distance >= int(expiry.value)

    if expiry.mode == "minor_releases":
        # Filter out prerelease entries for counting
        non_pre = [v for v in versions if not v.prerelease]
        badge_idx = _resolve_index(badge_version, non_pre)
        target_idx = _resolve_index(target_entry.tag, non_pre)
        # Prerelease target (e.g. dev) isn't in non_pre — fall back to
        # the latest non-prerelease so dev expires at least as much as latest.
        if target_idx is None and non_pre:
            target_idx = non_pre[0]._index
        if badge_idx is None or target_idx is None:
            return False
        distance = badge_idx - target_idx
        return distance >= int(expiry.value)

    if expiry.mode == "version":
        # Expire when building the threshold version or later
        threshold_idx = _resolve_index(str(expiry.value), versions)
        if threshold_idx is None:
            return False
        return target_entry._index <= threshold_idx

    if expiry.mode == "date":
        try:
            cutoff = date.fromisoformat(str(expiry.value))
        except ValueError:
            return False
        return date.today() >= cutoff

    if expiry.mode == "days":
        badge_entry = _find_entry(badge_version, versions)
        if badge_entry is None or not badge_entry.released:
            return False  # fail open
        try:
            released = date.fromisoformat(str(badge_entry.released)[:10])
        except ValueError:
            return False
        elapsed = (date.today() - released).days
        return elapsed >= int(expiry.value)

    return False


def _find_entry(tag: str, versions: list[VersionEntry]) -> VersionEntry | None:
    """Find a VersionEntry by tag, with v-prefix and version field fallbacks."""
    for v in versions:
        if v.tag == tag:
            return v
    alt = tag[1:] if tag.startswith("v") else f"v{tag}"
    for v in versions:
        if v.tag == alt:
            return v
    # Fallback: match against the version field
    for v in versions:
        if v.version and v.version == tag:
            return v
    return None


# ---------------------------------------------------------------------------
# Version fence preprocessing
# ---------------------------------------------------------------------------

# Matches opening ::: {.version-only ...} or ::: {.version-except ...}
_FENCE_OPEN_RE = re.compile(
    r"^:{3,}\s*\{\s*\.(version-only|version-except)\s+versions?=\"([^\"]+)\"\s*\}\s*$"
)

# Matches a closing ::: (exactly three or more colons, nothing else)
_FENCE_CLOSE_RE = re.compile(r"^:{3,}\s*$")

# Matches a heading line (e.g., "## Title")
_HEADING_RE = re.compile(r"^(#{1,6})\s")

# Matches a heading with a [version-badge new VERSION] marker
_HEADING_BADGE_NEW_RE = re.compile(r"^(#{1,6})\s+.*\[version-badge\s+new\s+([^\]]+)\]")


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

    Headings with `[version-badge new VERSION]` act as implicit section fences: when the target
    version is older than VERSION, the heading and all content until the next heading at the same or
    higher level are removed. This prevents orphan headings that appear with no content below them.

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

    # Stack tracks nested fences: (include: bool, colon_count: int, is_version_fence: bool)
    # Version fence markers are stripped from output; generic div markers are preserved.
    stack: list[tuple[bool, int, bool]] = []

    # Track fenced code blocks (``` or ````+) so we don't process
    # version fences that appear inside code examples.
    in_code_block = False
    code_fence_pattern = ""

    # Track heading-badge implicit fencing: when a heading has
    # [version-badge new VERSION] and the target is older, skip everything
    # until the next heading at the same or higher level.
    skip_heading_level = 0
    skip_div_depth = 0  # nested ::: div depth inside skipped section

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
            if skip_heading_level == 0 and (not stack or stack[-1][0]):
                result.append(line)
            i += 1
            continue
        elif in_code_block:
            if (
                stripped.startswith(code_fence_pattern)
                and stripped.rstrip(code_fence_pattern[0]) == ""
            ):
                in_code_block = False
                code_fence_pattern = ""
            if skip_heading_level == 0 and (not stack or stack[-1][0]):
                result.append(line)
            i += 1
            continue

        # Heading-level skip mode: skip lines until a same-or-higher-level heading
        # that is NOT inside a ::: fenced div (e.g., callout boxes contain headings
        # that should not terminate the skip).
        if skip_heading_level > 0:
            # Track ::: div nesting inside the skipped section
            if not in_code_block:
                if stripped.startswith(":::") and not _FENCE_CLOSE_RE.match(stripped):
                    skip_div_depth += 1
                elif _FENCE_CLOSE_RE.match(stripped) and skip_div_depth > 0:
                    skip_div_depth -= 1

            hm = _HEADING_RE.match(line)
            if hm and len(hm.group(1)) <= skip_heading_level and skip_div_depth == 0:
                # This heading ends the skip — fall through to normal processing
                skip_heading_level = 0
            else:
                i += 1
                continue

        # Check for heading with [version-badge new VERSION]
        hb = _HEADING_BADGE_NEW_RE.match(line)
        if hb:
            heading_level = len(hb.group(1))
            badge_version = hb.group(2).strip()
            expr = ">=" + badge_version
            if not evaluate_version_expr(expr, target_tag, versions):
                skip_heading_level = heading_level
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
            stack.append((include, colon_count, True))
            i += 1
            continue

        # Check for generic ::: div opening (callouts, panels, etc.)
        # These need stack tracking so their closing ::: doesn't pop a
        # version fence.
        if stripped.startswith(":::") and not _FENCE_CLOSE_RE.match(stripped):
            include = not stack or stack[-1][0]
            colon_count = len(line) - len(line.lstrip(":"))
            stack.append((include, colon_count, False))
            if include:
                result.append(line)
            i += 1
            continue

        # Check for fence close
        close_m = _FENCE_CLOSE_RE.match(line)
        if close_m and stack:
            entry = stack.pop()
            # Generic divs (not version fences) need their closing ::: emitted
            if not entry[2] and entry[0]:
                result.append(line)
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


def is_page_upcoming(content: str, versions: list[VersionEntry]) -> bool:
    """
    Check whether a page is scoped exclusively to prerelease versions.

    A page is "upcoming" when it has a `versions:` frontmatter key and every version it matches is
    marked `prerelease: True`.  Pages with no `versions:` key (visible in all versions) are never
    considered upcoming.

    Parameters
    ----------
    content
        The raw `.qmd` file content.
    versions
        The full ordered list of version entries.

    Returns
    -------
    bool
        `True` if the page only targets prerelease versions.
    """
    page_versions = extract_page_versions(content)
    if page_versions is None:
        return False

    # Resolve which version entries the page actually matches
    matched = []
    for v in versions:
        expr = ",".join(page_versions)
        if evaluate_version_expr(expr, v.tag, versions):
            matched.append(v)

    if not matched:
        return False

    return all(v.prerelease for v in matched)


def is_page_upcoming_for_version(
    upcoming_value: str,
    target_tag: str,
    versions: list[VersionEntry],
) -> bool:
    """
    Check whether the `upcoming` frontmatter key applies to the current build.

    Returns `True` when the page declares `upcoming: "0.8"` and the current build target is
    **older** than 0.8 (i.e. the feature hasn't shipped yet for this version).

    Parameters
    ----------
    upcoming_value
        The raw value of the `upcoming:` frontmatter key (a version tag or semantic version).
    target_tag
        The version tag currently being built.
    versions
        The full ordered list of version entries.

    Returns
    -------
    bool
        `True` if the current build is older than the upcoming version.
    """
    upcoming_idx = _resolve_index(upcoming_value, versions)
    target_idx = _resolve_index(target_tag, versions)

    if upcoming_idx is None or target_idx is None:
        return False

    # Lower index = newer. If target is older (higher index) than the upcoming
    # version, the page is "upcoming" for this build.
    return target_idx > upcoming_idx


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
        (e.g. `">=0.7"`) are evaluated; otherwise only bare tag matching is used.

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
