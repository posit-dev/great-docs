from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ._builtin.directives import DIRECTIVES
from ._interlinks import AliasClaims, resolve_aliases
from ._utils import fenced_lines, is_in_great_docs_build_dir, parse_seealso

if TYPE_CHECKING:
    from ._apiref.inventory import InventoryItem
    from ._interlinks import AliasResolution


@dataclass
class LintIssue:
    """A single documentation lint finding."""

    check: str  # e.g., "missing-docstring", "broken-xref"
    severity: str  # "error", "warning", "info"
    symbol: str  # Fully qualified name, e.g., "MyClass.my_method"
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LintResult:
    """Aggregated results from all lint checks."""

    issues: list[LintIssue] = field(default_factory=list)
    package_name: str = ""
    exports_count: int = 0

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "info"]

    @property
    def status(self) -> str:
        if self.errors:
            return "fail"
        if self.warnings:
            return "warn"
        return "pass"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "package": self.package_name,
            "exports_checked": self.exports_count,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": len(self.infos),
            },
            "issues": [i.to_dict() for i in self.issues],
        }


def run_lint(
    project_root: Path,
    checks: set[str] | None = None,
    quiet: bool = False,
) -> LintResult:
    """
    Run documentation lint checks on a package.

    Parameters
    ----------
    project_root
        Path to the project root directory.
    checks
        Set of check names to run. If None, all checks are run.
        Valid names: "docstrings", "cross-refs", "style", "directives".
    quiet
        If True, suppress discovery/introspection print output.

    Returns
    -------
    LintResult
        Aggregated lint results.
    """
    import io
    import sys

    from .core import GreatDocs

    result = LintResult()
    all_checks = {"docstrings", "cross-refs", "style", "directives", "stale-versions"}

    if checks is None:
        checks = all_checks
    else:
        invalid = checks - all_checks
        if invalid:
            result.issues.append(
                LintIssue(
                    check="config",
                    severity="error",
                    symbol="",
                    message=f"Unknown check(s): {', '.join(sorted(invalid))}",
                )
            )
            return result

    # Initialize GreatDocs to access config and package info
    # Suppress print output from griffe discovery when in quiet mode
    if quiet:
        _saved_stdout = sys.stdout
        sys.stdout = io.StringIO()

    try:
        docs = GreatDocs(project_path=str(project_root))
        package_name = docs._detect_package_name()
    except Exception:
        if quiet:
            sys.stdout = _saved_stdout
        raise

    if not package_name:
        if quiet:
            sys.stdout = _saved_stdout
        result.issues.append(
            LintIssue(
                check="config",
                severity="error",
                symbol="",
                message="Could not detect package name. Is this a Python project?",
            )
        )
        return result

    importable_name = docs._resolve_importable_name(package_name)
    result.package_name = importable_name

    # Load package via griffe for introspection
    try:
        import griffe
    except ImportError:
        if quiet:
            sys.stdout = _saved_stdout
        result.issues.append(
            LintIssue(
                check="config",
                severity="error",
                symbol="",
                message="griffe is required for lint checks but is not installed.",
            )
        )
        return result

    try:
        pkg = griffe.load(importable_name, search_paths=docs._griffe_search_paths())
    except Exception as e:
        if quiet:
            sys.stdout = _saved_stdout
        result.issues.append(
            LintIssue(
                check="config",
                severity="error",
                symbol="",
                message=f"Could not load package '{importable_name}': {type(e).__name__}: {e}",
            )
        )
        return result

    # Discover exports (also noisy with prints)
    exports = docs._get_package_exports(importable_name)

    if quiet:
        sys.stdout = _saved_stdout
    if exports is None:
        exports = []

    result.exports_count = len(exports)

    # Get configured docstring style
    config_style = docs._config["parser"]

    # Run selected checks
    if "docstrings" in checks:
        _check_missing_docstrings(pkg, importable_name, exports, result)

    if "cross-refs" in checks:
        documented = docs.documented_objects(package_name)
        # Resolve aliases once so both checks judge each reference identically.
        resolution = resolve_aliases(AliasClaims.make(documented))
        _check_cross_references(pkg, importable_name, exports, documented, resolution, result)
        _check_ambiguous_references(resolution, _gather_prose(documented, project_root), result)

    if "style" in checks:
        _check_docstring_style(pkg, importable_name, exports, config_style, result)

    if "directives" in checks:
        _check_directive_consistency(pkg, importable_name, exports, result)

    if "stale-versions" in checks:
        _check_stale_versions(project_root, result)

    return result


def _get_docstring(obj) -> str | None:
    """Safely extract docstring text from a griffe object."""
    try:
        if hasattr(obj, "docstring") and obj.docstring:
            return obj.docstring.value
    except Exception:
        pass
    return None


def _iter_public_members(obj):
    """Yield (name, member) pairs for public members of a griffe object."""
    try:
        for name, member in obj.members.items():
            if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
                continue
            # Skip __init__ and similar constructor dunders
            if name in {"__init__", "__new__", "__init_subclass__"}:
                continue
            yield name, member
    except Exception:
        return


def _check_missing_docstrings(
    pkg,
    package_name: str,
    exports: list[str],
    result: LintResult,
) -> None:
    """Check for public exports and their members missing docstrings."""
    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]

        # Check if the export itself has a docstring
        docstring = _get_docstring(obj)
        if not docstring or not docstring.strip():
            result.issues.append(
                LintIssue(
                    check="missing-docstring",
                    severity="error",
                    symbol=name,
                    message=f"Public export '{name}' has no docstring.",
                )
            )
            continue

        # For classes, check public methods too
        try:
            if obj.kind.value == "class":
                for member_name, member in _iter_public_members(obj):
                    try:
                        if member.kind.value not in ("function", "method"):
                            continue
                    except Exception:
                        continue

                    member_doc = _get_docstring(member)
                    if not member_doc or not member_doc.strip():
                        result.issues.append(
                            LintIssue(
                                check="missing-docstring",
                                severity="warning",
                                symbol=f"{name}.{member_name}",
                                message=f"Public method '{name}.{member_name}' has no docstring.",
                            )
                        )
        except Exception:
            pass


def _check_cross_references(
    pkg,
    package_name: str,
    exports: list[str],
    documented: list[InventoryItem],
    resolution: AliasResolution,
    result: LintResult,
) -> None:
    """
    Check `%seealso` directives for unresolved cross-references

    The build resolves `%seealso` entries against its index. A documented name
    or an alias claimed by one object resolves. A shared alias is ambiguous,
    and an undocumented name is broken. Each leaves the rendered link
    unlinked, but requires a different correction.

    Parameters
    ----------
    pkg :
        The package loaded by griffe, whose docstrings are scanned.
    package_name :
        Importable name of the package.
    exports :
        Public export names to scan.
    documented :
        The objects the reference documents. Empty when it cannot be resolved,
        in which case the check reports nothing rather than calling every
        reference broken.
    resolution :
        The short names the build resolves, and the ambiguous ones it drops.
    result :
        Aggregated results to append to.
    """
    if not documented:
        return

    # Shared aliases are absent from `kept` and present in `dropped`.
    known_names = {item.name for item in documented if item.name} | set(resolution.kept)

    def check(text: str, symbol: str) -> None:
        """
        Report unresolved `%seealso` names in one docstring

        Parameters
        ----------
        text :
            The docstring to scan.
        symbol :
            The object the docstring belongs to, named in any issue raised.

        Returns
        -------
        :
        """
        for ref_name, _ in parse_seealso(text):
            claimants = resolution.dropped.get(ref_name)
            if claimants is not None:
                result.issues.append(
                    LintIssue(
                        check="ambiguous-xref",
                        severity="error",
                        symbol=symbol,
                        message=(
                            f"%%seealso references '{ref_name}', which is claimed by "
                            f"{' and '.join(claimants)}, so it stays unlinked. Qualify it."
                        ),
                    )
                )
            elif ref_name not in known_names:
                result.issues.append(
                    LintIssue(
                        check="broken-xref",
                        severity="error",
                        symbol=symbol,
                        message=(
                            f"%%seealso references '{ref_name}' "
                            "which the API reference does not document."
                        ),
                    )
                )

    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]
        docstring = _get_docstring(obj)
        if docstring:
            check(docstring, name)

        try:
            if obj.kind.value == "class":
                for member_name, member in _iter_public_members(obj):
                    member_doc = _get_docstring(member)
                    if member_doc:
                        check(member_doc, f"{name}.{member_name}")
        except Exception:
            pass


_NOT_AUTHORED = {"node_modules"}
"""Directories that do not contain author-written pages"""


_INTERLINK_RE = re.compile(r"\[[^\]]*\]\(`(~?)([\w.]+)`\)")
"""An explicit reference written as `[text](`~pkg.Name`)`"""

_CODE_SPAN_RE = re.compile(r"(`{2,})(?:(?!\1).)*?\1", re.DOTALL)
"""A multi-backtick span that Markdown renders as literal text"""


def _strip_code(text: str) -> str:
    """
    Remove fenced code blocks and multi-backtick code spans from Markdown

    Markdown renders references inside these constructs as example text. A
    single-backtick span cannot contain the backticks around an interlink
    target, so multi-backtick spans are sufficient here.

    Parameters
    ----------
    text
        Markdown source to scan.

    Returns
    -------
    :
        The text with fenced and multi-backtick spans removed.
    """
    lines, fenced = fenced_lines(text)
    unfenced = "\n".join(line for line, is_fenced in zip(lines, fenced) if not is_fenced)
    return _CODE_SPAN_RE.sub("", unfenced)


def _gather_prose(items: list[InventoryItem], project_root: Path) -> dict[str, str]:
    """
    Gather the text the ambiguity check scans

    Read the docstring of every object the reference documents, and the pages
    an author writes under the project root.

    Parameters
    ----------
    items :
        The objects the reference documents.
    project_root :
        Root of the project, whose pages are scanned alongside the docstrings.

    Returns
    -------
    :
        The prose, keyed by the symbol or file it came from.
    """
    prose: dict[str, str] = {}

    for item in items:
        docstring = _get_docstring(item.obj)
        if docstring:
            prose[item.name] = docstring

    for dirpath, dirnames, filenames in os.walk(project_root):
        here = Path(dirpath)
        # Prune rather than filter afterwards. Quarto renders no path beginning
        # with an underscore, so those pages carry no reference the site can show,
        # and a nested `great-docs.yml` marks a separate documentation project,
        # whose pages are checked against its own names rather than ours.
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith((".", "_"))
            and d not in _NOT_AUTHORED
            and not (here / d / "great-docs.yml").exists()
            and not is_in_great_docs_build_dir(
                (here / d).relative_to(project_root).parts, project_root
            )
        ]
        for filename in sorted(filenames):
            if not filename.endswith((".qmd", ".md")):
                continue
            path = here / filename
            prose[str(path.relative_to(project_root))] = path.read_text(encoding="utf-8")

    return prose


def _check_ambiguous_references(
    resolution: AliasResolution,
    prose: dict[str, str],
    result: LintResult,
) -> None:
    """
    Check prose for references to a short name that two objects claim

    Parameters
    ----------
    resolution :
        The short names the build resolves, and the ambiguous ones it drops.
    prose :
        Text to scan, keyed by the symbol or file it came from.
    result :
        Aggregated results to append to.
    """
    dropped = resolution.dropped
    if not dropped:
        return

    for origin, text in prose.items():
        for _, name in _INTERLINK_RE.findall(_strip_code(text)):
            targets = dropped.get(name)
            if targets is None:
                continue
            result.issues.append(
                LintIssue(
                    check="ambiguous-xref",
                    severity="error",
                    symbol=origin,
                    message=(
                        f"'{name}' is claimed by {' and '.join(targets)}, so the "
                        "reference stays unlinked. Qualify it."
                    ),
                )
            )


_STYLES = ("numpy", "google", "sphinx")
"""The docstring styles a project can be configured for"""


def _section_kinds(docstring: str, style: str) -> set[str]:
    """
    Return the kinds of structured section a style's parser finds in a docstring

    Plain text is not a structured section, so a docstring that a parser cannot
    read at all yields the empty set. The docstring is parsed detached from any
    object: with a parent, griffe additionally reports mismatches against the
    signature, which are not this check's concern.

    The check parses each docstring under styles it was not written in, so
    griffe's complaints about the text it cannot read are expected and stay
    silenced rather than reaching the user as lint output.

    Parameters
    ----------
    docstring
        The docstring text.
    style
        The style whose parser reads the text.

    Returns
    -------
    The section kinds found, named as griffe names them.
    """
    import griffe

    logger = logging.getLogger("griffe")
    previous_disabled = logger.disabled
    previous_propagate = logger.propagate
    # disabled suppresses records sent directly to this logger; propagate=False
    # stops child-logger records from reaching root handlers via propagation.
    logger.disabled = True
    logger.propagate = False
    try:
        parsed = griffe.Docstring(  # pyright: ignore[reportArgumentType]
            docstring, parser=style
        ).parsed
    finally:
        logger.disabled = previous_disabled
        logger.propagate = previous_propagate
    return {section.kind.value for section in parsed if section.kind.value != "text"}


def _lost_sections(docstring: str, config_style: str) -> dict[str, set[str]]:
    """
    Find the structure the configured parser drops but another parser would read

    Parameters
    ----------
    docstring
        The docstring text.
    config_style
        The style the project is configured for.

    Returns
    -------
    Each rival style mapped to the section kinds it finds and the configured
    style misses, empty when the configured style reads everything.
    """
    configured = _section_kinds(docstring, config_style)
    lost: dict[str, set[str]] = {}
    for style in _STYLES:
        if style == config_style:
            continue
        missed = _section_kinds(docstring, style) - configured
        if missed:
            lost[style] = missed
    return lost


def _check_docstring_style(
    pkg,
    package_name: str,
    exports: list[str],
    config_style: str,
    result: LintResult,
) -> None:
    """Enforce consistent docstring style across all exports."""
    if config_style not in _STYLES:
        result.issues.append(
            LintIssue(
                check="config",
                severity="error",
                symbol="great-docs.yml",
                message=(
                    f"parser: {config_style!r} is not one of {', '.join(_STYLES)}, "
                    f"so docstring style cannot be checked."
                ),
            )
        )
        return

    def _check_one(symbol: str, docstring: str) -> None:
        lost = _lost_sections(docstring, config_style)
        if not lost:
            return
        detail = "; ".join(
            f"{style} reads {', '.join(sorted(kinds))}" for style, kinds in sorted(lost.items())
        )
        result.issues.append(
            LintIssue(
                check="style-mismatch",
                severity="warning",
                symbol=symbol,
                message=(
                    f"The '{config_style}' parser does not read some of this "
                    f"docstring's structure: {detail}."
                ),
            )
        )

    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]
        docstring = _get_docstring(obj)
        if docstring:
            _check_one(name, docstring)

        # Check class method docstrings too
        try:
            if obj.kind.value == "class":
                for member_name, member in _iter_public_members(obj):
                    member_doc = _get_docstring(member)
                    if member_doc:
                        _check_one(f"{name}.{member_name}", member_doc)
        except Exception:
            pass


# Pattern matching malformed directives (common mistakes)
_MALFORMED_DIRECTIVE = re.compile(
    r"^\s*%(\w+)",
    re.MULTILINE,
)


def _check_directive_consistency(
    pkg,
    package_name: str,
    exports: list[str],
    result: LintResult,
) -> None:
    """Check for malformed or unknown directives in docstrings."""

    def _check_one(symbol: str, docstring: str) -> None:
        # Find all %-prefixed tokens in the docstring
        for match in _MALFORMED_DIRECTIVE.finditer(docstring):
            directive_name = match.group(1)
            if directive_name not in DIRECTIVES:
                result.issues.append(
                    LintIssue(
                        check="unknown-directive",
                        severity="warning",
                        symbol=symbol,
                        message=(
                            f"Unknown directive '%{match.group(1)}'. "
                            f"Known directives: {', '.join(sorted('%' + d for d in DIRECTIVES))}."
                        ),
                    )
                )

    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]
        docstring = _get_docstring(obj)
        if docstring:
            _check_one(name, docstring)

        # Check class method docstrings too
        try:
            if obj.kind.value == "class":
                for member_name, member in _iter_public_members(obj):
                    member_doc = _get_docstring(member)
                    if member_doc:
                        _check_one(f"{name}.{member_name}", member_doc)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Stale version annotations
# ---------------------------------------------------------------------------

# Default thresholds (used when no config overrides)
_DEFAULT_BADGE_THRESHOLD = 3  # releases behind latest
_DEFAULT_CALLOUT_THRESHOLD = 4  # releases behind latest


def _check_stale_versions(project_root: Path, result: LintResult) -> None:
    """
    Flag stale version-annotated content in .qmd files.

    Checks for:
      - `[version-badge new X]` where X is many releases behind latest
      - `::: {.version-note version="X"}` / `::: {.version-deprecated version="X"}`
        where X is very old
      - `upcoming: "X"` frontmatter where X is already released
    """
    from yaml12 import read_yaml

    # Load great-docs.yml for versions list and optional lint config
    config_path = project_root / "great-docs.yml"
    if not config_path.exists():
        return

    try:
        raw_config = read_yaml(config_path) or {}
    except Exception:
        return

    versions_raw = raw_config.get("versions", [])
    if not versions_raw:
        return

    from ._versioning import parse_versions_config

    versions = parse_versions_config(versions_raw)
    if not versions:
        return

    # Determine the latest non-prerelease version
    latest_entry = None
    for v in versions:
        if v.latest:
            latest_entry = v
            break
    if latest_entry is None:
        for v in versions:
            if not v.prerelease:
                latest_entry = v
                break
    if latest_entry is None:
        return

    # Optional config overrides
    lint_cfg = raw_config.get("lint", {}) or {}
    stale_cfg = lint_cfg.get("stale_versions", {}) or {}
    badge_threshold = int(stale_cfg.get("badge_threshold", _DEFAULT_BADGE_THRESHOLD))
    callout_threshold = int(stale_cfg.get("callout_threshold", _DEFAULT_CALLOUT_THRESHOLD))

    # Parse the real badge expiry config (new_is_old)
    from ._versioning import is_badge_expired, parse_badge_expiry

    badge_expiry = parse_badge_expiry(raw_config.get("new_is_old"))

    # Build set of released version identifiers for upcoming check
    released_versions: set[str] = set()
    for v in versions:
        if not v.prerelease:
            released_versions.add(v.tag)
            if v.version:
                released_versions.add(v.version)

    # Compiled patterns (same as in _versioned_build)
    badge_re = re.compile(
        r"\[version-badge\s+(new|changed|deprecated)(?:\s+(\S+))?\]",
        re.IGNORECASE,
    )
    note_re = re.compile(
        r'^:::\s*\{\.version-note(?:\s+versions?="([^"]*)")?\}\s*$',
        re.MULTILINE,
    )
    deprecated_re = re.compile(
        r'^:::\s*\{\.version-deprecated(?:\s+versions?="([^"]*)")?\}\s*$',
        re.MULTILINE,
    )

    # Ignore generated build copies at the project root. Nested directories
    # with similar names remain part of the user's source tree.
    qmd_files = []
    for qmd in project_root.rglob("*.qmd"):
        rel = qmd.relative_to(project_root)
        parts = rel.parts
        if any(p.startswith("_") or p.startswith(".") for p in parts):
            continue
        if is_in_great_docs_build_dir(parts, project_root):
            continue
        qmd_files.append(qmd)

    for qmd_file in sorted(qmd_files):
        try:
            content = qmd_file.read_text(encoding="utf-8")
        except OSError:
            continue

        rel_path = str(qmd_file.relative_to(project_root))

        # --- Check stale badges ---
        for m in badge_re.finditer(content):
            badge_type = m.group(1).lower()
            badge_version = m.group(2)
            if not badge_version:
                continue
            distance = _version_distance(badge_version, latest_entry, versions)
            if distance is not None and distance >= badge_threshold:
                lineno = content[: m.start()].count("\n") + 1

                # For "new" badges, check whether it truly no longer displays
                # using the project's actual new_is_old expiry setting
                if badge_type == "new":
                    expired = is_badge_expired(badge_version, latest_entry, versions, badge_expiry)
                    if expired:
                        advice = "consider removing badge since it no longer displays"
                    else:
                        advice = (
                            "badge still displays but is getting old; "
                            "consider whether it's still useful"
                        )
                else:
                    # changed/deprecated badges always display regardless of
                    # new_is_old config
                    advice = (
                        "badge still displays in all versions; consider whether it's still useful"
                    )

                result.issues.append(
                    LintIssue(
                        check="stale-badge",
                        severity="warning",
                        symbol=f"{rel_path}:{lineno}",
                        message=(
                            f"[version-badge {badge_type} {badge_version}] is "
                            f"{distance} releases behind latest; {advice}"
                        ),
                    )
                )

        # --- Check stale callouts ---
        for m in note_re.finditer(content):
            callout_version = m.group(1)
            if not callout_version:
                continue
            distance = _version_distance(callout_version, latest_entry, versions)
            if distance is not None and distance >= callout_threshold:
                lineno = content[: m.start()].count("\n") + 1
                result.issues.append(
                    LintIssue(
                        check="stale-callout",
                        severity="info",
                        symbol=f"{rel_path}:{lineno}",
                        message=(
                            f'::: {{.version-note version="{callout_version}"}} is '
                            f"{distance} releases old; "
                            f"consider consolidating into main text"
                        ),
                    )
                )

        for m in deprecated_re.finditer(content):
            callout_version = m.group(1)
            if not callout_version:
                continue
            distance = _version_distance(callout_version, latest_entry, versions)
            if distance is not None and distance >= callout_threshold:
                lineno = content[: m.start()].count("\n") + 1
                result.issues.append(
                    LintIssue(
                        check="stale-callout",
                        severity="info",
                        symbol=f"{rel_path}:{lineno}",
                        message=(
                            f'::: {{.version-deprecated version="{callout_version}"}} is '
                            f"{distance} releases old; "
                            f"consider consolidating into main text"
                        ),
                    )
                )

        # --- Check stale upcoming frontmatter ---
        upcoming_val = _extract_frontmatter_upcoming(content)
        if upcoming_val and upcoming_val in released_versions:
            result.issues.append(
                LintIssue(
                    check="stale-upcoming",
                    severity="warning",
                    symbol=f"{rel_path}:1",
                    message=(
                        f'upcoming: "{upcoming_val}" references an already-released version; '
                        f"remove the upcoming frontmatter"
                    ),
                )
            )


def _version_distance(
    badge_version: str,
    latest_entry,
    versions: list,
) -> int | None:
    """
    Count how many non-prerelease positions *badge_version* is behind *latest_entry*.

    Returns None if the version is not found in the list.
    """
    from ._versioning import _find_entry

    entry = _find_entry(badge_version, versions)
    if entry is None:
        return None
    non_pre = [v for v in versions if not v.prerelease]
    badge_idx = None
    latest_idx = None
    for i, v in enumerate(non_pre):
        if v.tag == entry.tag:
            badge_idx = i
        if v.tag == latest_entry.tag:
            latest_idx = i
    if badge_idx is None or latest_idx is None:
        return None
    # non_pre is ordered newest-first, so badge_idx > latest_idx means older
    return badge_idx - latest_idx


def _extract_frontmatter_upcoming(content: str) -> str | None:
    """Extract the `upcoming:` value from YAML frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not fm_match:
        return None
    fm = fm_match.group(1)
    m = re.search(r"^upcoming\s*:\s*(.+)$", fm, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")
