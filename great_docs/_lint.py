from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


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
    all_checks = {"docstrings", "cross-refs", "style", "directives"}

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

    importable_name = docs._normalize_package_name(package_name)
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
        pkg = griffe.load(importable_name)
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
    config_style = docs._config.get("parser", "numpy")

    # Run selected checks
    if "docstrings" in checks:
        _check_missing_docstrings(pkg, importable_name, exports, result)

    if "cross-refs" in checks:
        _check_cross_references(pkg, importable_name, exports, result)

    if "style" in checks:
        _check_docstring_style(pkg, importable_name, exports, config_style, result)

    if "directives" in checks:
        _check_directive_consistency(pkg, importable_name, exports, result)

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
    result: LintResult,
) -> None:
    """Check %seealso directives for broken cross-references."""
    from ._directives import extract_directives

    # Build a set of all known public names (fully unqualified)
    known_names = set(exports)

    # Also add qualified class member names
    for name in exports:
        if name not in pkg.members:
            continue
        obj = pkg.members[name]
        try:
            if obj.kind.value == "class":
                for member_name, _ in _iter_public_members(obj):
                    known_names.add(f"{name}.{member_name}")
        except Exception:
            pass

    # Check each export's docstring for %seealso references
    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]
        docstring = _get_docstring(obj)
        if not docstring:
            continue

        directives = extract_directives(docstring)
        for ref_name, _ in directives.seealso:
            if ref_name not in known_names:
                result.issues.append(
                    LintIssue(
                        check="broken-xref",
                        severity="error",
                        symbol=name,
                        message=(
                            f"%%seealso references '{ref_name}' which is not a known public export."
                        ),
                    )
                )

        # Also check class methods
        try:
            if obj.kind.value == "class":
                for member_name, member in _iter_public_members(obj):
                    member_doc = _get_docstring(member)
                    if not member_doc:  # pragma: no cover
                        continue
                    member_directives = extract_directives(member_doc)
                    for ref_name, _ in member_directives.seealso:
                        if ref_name not in known_names:  # pragma: no cover
                            result.issues.append(
                                LintIssue(
                                    check="broken-xref",
                                    severity="error",
                                    symbol=f"{name}.{member_name}",
                                    message=(
                                        f"%%seealso references '{ref_name}' "
                                        f"which is not a known public export."
                                    ),
                                )
                            )
        except Exception:
            pass


# Patterns for detecting docstring styles
_NUMPY_SECTION = re.compile(
    r"^\s*(Parameters|Returns|Yields|Raises|Examples|Attributes|Methods|"
    r"See Also|Notes|References|Warnings)\s*\n\s*-{3,}",
    re.MULTILINE,
)

_GOOGLE_SECTION = re.compile(
    r"^\s*(Args|Arguments|Returns|Yields|Raises|Examples|Attributes|"
    r"Note|Notes|Todo|Warning|Warnings):\s*$",
    re.MULTILINE,
)

_SPHINX_FIELD = re.compile(
    r"^\s*:(param|type|returns|rtype|raises|var|ivar|cvar)\s",
    re.MULTILINE,
)


def _detect_style_of_docstring(docstring: str) -> str | None:
    """Detect which style a single docstring uses. Returns None if no sections found."""
    has_numpy = bool(_NUMPY_SECTION.search(docstring))
    has_google = bool(_GOOGLE_SECTION.search(docstring)) and not has_numpy
    has_sphinx = bool(_SPHINX_FIELD.search(docstring))

    styles_found = []
    if has_numpy:
        styles_found.append("numpy")
    if has_google:
        styles_found.append("google")
    if has_sphinx:
        styles_found.append("sphinx")

    if len(styles_found) == 1:
        return styles_found[0]
    if len(styles_found) > 1:
        # Mixed styles — return the first detected for reporting
        return styles_found[0]
    return None


def _check_docstring_style(
    pkg,
    package_name: str,
    exports: list[str],
    config_style: str,
    result: LintResult,
) -> None:
    """Enforce consistent docstring style across all exports."""

    def _check_one(symbol: str, docstring: str) -> None:
        detected = _detect_style_of_docstring(docstring)
        if detected is None:
            # No structured sections found — skip (short docstrings are fine)
            return
        if detected != config_style:
            result.issues.append(
                LintIssue(
                    check="style-mismatch",
                    severity="warning",
                    symbol=symbol,
                    message=(
                        f"Docstring appears to use '{detected}' style "
                        f"but project is configured for '{config_style}'."
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

_KNOWN_DIRECTIVES = {"seealso", "nodoc"}


def _check_directive_consistency(
    pkg,
    package_name: str,
    exports: list[str],
    result: LintResult,
) -> None:
    """Check for malformed or unknown directives in docstrings."""
    from ._directives import extract_directives

    def _check_one(symbol: str, docstring: str) -> None:
        # Find all %-prefixed tokens in the docstring
        for match in _MALFORMED_DIRECTIVE.finditer(docstring):
            directive_name = match.group(1).lower()
            if directive_name not in _KNOWN_DIRECTIVES:
                result.issues.append(
                    LintIssue(
                        check="unknown-directive",
                        severity="warning",
                        symbol=symbol,
                        message=(
                            f"Unknown directive '%{match.group(1)}'. "
                            f"Known directives: {', '.join(sorted('%' + d for d in _KNOWN_DIRECTIVES))}."
                        ),
                    )
                )

        # Validate that %seealso entries are non-empty
        directives = extract_directives(docstring)
        for ref_name, _ in directives.seealso:
            if not ref_name.strip():  # pragma: no cover
                result.issues.append(
                    LintIssue(
                        check="empty-seealso",
                        severity="warning",
                        symbol=symbol,
                        message="%%seealso contains an empty reference.",
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
