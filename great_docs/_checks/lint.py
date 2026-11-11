from __future__ import annotations

import contextlib
import io
import logging
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import griffe as gf

from .._build.ownership import is_in_great_docs_build_dir
from .._build.steps import USER_CODE_ERRORS
from .._builtin.directives import DIRECTIVES
from .._content import authored
from .._interlinks import AliasClaims, LoadedSources, build_index, load_sources
from .._project import Project
from .._project.layout import Layout
from .._reference.exports import Exports
from .._utils import fenced_lines, parse_seealso
from .._website.homepage import source as homepage_source
from .._yaml import YamlMapping, YamlValue, split_front_matter
from ..config import _PARSERS

if TYPE_CHECKING:
    from .._apiref.inventory import InventoryItem
    from .._interlinks import Index
    from ..config import Config


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
    *,
    config_path: str | None = None,
) -> LintResult:
    """
    Run documentation lint checks on a package

    Parameters
    ----------
    project_root
        Path to the project root directory.
    checks
        Set of check names to run. If None, all checks are run.
        Valid names: "config", "docstrings", "cross-refs", "style",
        "directives", "stale-versions", "descriptions".
    quiet
        If True, suppress discovery/introspection print output.
    config_path
        Configuration file, resolved from the current working directory.

    Returns
    -------
    LintResult
        Aggregated lint results.
    """
    result = LintResult()
    all_checks = {
        "config",
        "docstrings",
        "cross-refs",
        "style",
        "directives",
        "stale-versions",
        "descriptions",
        "front-matter",
    }

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

    # Discovery and introspection print their progress; quiet mode discards it.
    with contextlib.redirect_stdout(io.StringIO()) if quiet else contextlib.nullcontext():
        layout = Layout.make(project_root, Path(config_path) if config_path else None)
        package_exports = Exports.make(layout)
        config = package_exports.config
        project = package_exports.project

        # Configuration problems are reported even if the package cannot be loaded.
        if "config" in checks:
            _check_config_keys(config.user_settings, result)

        # The config check reads only great-docs.yml, so it also works on projects
        # without a Python package.
        if checks <= {"config"}:
            return result

        importable_name = project.importable_name
        if not project.name or not importable_name:
            result.issues.append(
                LintIssue(
                    check="config",
                    severity="error",
                    symbol="",
                    message="Could not detect package name. Is this a Python project?",
                )
            )
            return result

        result.package_name = importable_name

        try:
            pkg = package_exports.package(importable_name)
        except USER_CODE_ERRORS as e:
            result.issues.append(
                LintIssue(
                    check="config",
                    severity="error",
                    symbol="",
                    message=f"Could not load package '{importable_name}': {type(e).__name__}: {e}",
                )
            )
            return result

        exports = package_exports.names(importable_name) or []

    result.exports_count = len(exports)

    # Get configured docstring style
    config_style = config["parser"]

    # Run selected checks
    if "docstrings" in checks:
        _check_missing_docstrings(pkg, importable_name, exports, result)

    if "cross-refs" in checks:
        from .._apiref.inventory import create_inventory
        from .._reference import documented as documented_reference

        documented = documented_reference.objects(
            config,
            importable_name=importable_name,
            search_paths=project.search_paths(),
            create_sections=package_exports.sections,
        )
        # No documented objects means both checks are no-ops, so skip source
        # loading and any inventory download.
        sources = load_sources(config) if documented else LoadedSources()
        # Use the index the build writes so both checks apply render resolution.
        index = build_index(
            create_inventory(importable_name, "", documented),
            AliasClaims.make(documented),
            sources.read,
        )
        _check_cross_references(
            pkg, importable_name, exports, documented, index, sources.unread, result
        )
        prose = _gather_prose(documented, project_root, layout)
        _check_ambiguous_references(
            index.dropped,
            prose,
            result,
            autolinked=_published_origins(prose, documented, config, layout, project_root),
        )

    if "style" in checks:
        _check_docstring_style(pkg, importable_name, exports, config_style, result)

    if "directives" in checks:
        _check_directive_consistency(pkg, importable_name, exports, result)

    if "stale-versions" in checks:
        _check_stale_versions(config, project_root, result, layout)

    if "descriptions" in checks:
        _check_page_descriptions(config, layout, project_root, result)

    if "front-matter" in checks:
        _check_front_matter(config, layout, project_root, result)

    return result


def _check_config_keys(user_config: dict[str, Any], result: LintResult) -> None:
    """
    Report language keys that great-docs reads under another name or not at all

    `site.language` still works but is spelled `site.lang`, Quarto's key. A
    top-level `language` string is ignored. A top-level `language` mapping is
    left alone, since that is the shape of Quarto's own `language` key.

    Parameters
    ----------
    user_config
        The configuration as written in `great-docs.yml`.
    result
        The lint result to append issues to.
    """
    site = user_config.get("site")
    if isinstance(site, dict) and "language" in site:
        result.issues.append(
            LintIssue(
                check="config-key",
                severity="warning",
                symbol="site.language",
                message="Rename `site.language` to `site.lang`.",
            )
        )
    if isinstance(user_config.get("language"), str):
        result.issues.append(
            LintIssue(
                check="config-key",
                severity="warning",
                symbol="language",
                message="The top-level `language` key is ignored. Set the site language with `site.lang`.",
            )
        )


def _get_docstring(obj: gf.Object | gf.Alias) -> str | None:
    """
    Return an object's docstring text when available

    Parameters
    ----------
    obj
        The griffe object or alias to read.

    Returns
    -------
    :
        The docstring text, or `None` if it is absent or griffe cannot resolve
        the alias.
    """
    try:
        docstring = obj.docstring
    except (gf.AliasResolutionError, gf.CyclicAliasError):
        return None
    return docstring.value if docstring else None


def _iter_public_members(obj):
    """Yield (name, member) pairs for public members of a griffe object."""
    for name, member in obj.members.items():
        if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
            continue
        # Skip __init__ and similar constructor dunders
        if name in {"__init__", "__new__", "__init_subclass__"}:
            continue
        yield name, member


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
        if obj.kind.value == "class":
            for member_name, member in _iter_public_members(obj):
                # An alias griffe cannot resolve has kind `alias`, so it is skipped.
                if member.kind.value not in ("function", "method"):
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


def _check_cross_references(
    pkg,
    package_name: str,
    exports: list[str],
    documented: list[InventoryItem],
    index: Index,
    unread_sources: tuple[str, ...],
    result: LintResult,
) -> None:
    """
    Check `%seealso` directives for unresolved cross-references

    The build resolves each entry against its index. Use the same index here.
    A locally ambiguous name reports `ambiguous-xref` even if a source is
    unread, because only local claims create ambiguity. Report another
    unresolved name as broken only after every configured source is read.

    Check only docstrings the reference renders. A `%seealso` in a hidden
    member, such as one from a class configured `members: false`, has no page
    where a reader can act on its finding.

    Read directives from the Griffe tree, where `%seealso` remains written.
    The rendered reference replaces it with a See Also section. Documented
    objects identify which of those source docstrings reach a page.

    Parameters
    ----------
    pkg :
        The package loaded by Griffe, whose docstrings contain directives.
    package_name :
        Importable package name used in documented object paths.
    exports :
        Public export names whose documented objects are considered.
    documented :
        The objects the reference documents. Empty when it cannot be resolved,
        in which case the check reports nothing rather than calling every
        reference broken.
    index :
        The index the build resolves references against.
    unread_sources :
        Sources whose inventory could not be read. A name one of them
        publishes cannot be told from a misspelling. Do not report unresolved
        names as broken for this run. Still report locally ambiguous names.
    result :
        Aggregated results to append to.
    """
    if not documented:
        return

    if unread_sources:
        result.issues.append(
            LintIssue(
                check="unread-source",
                severity="info",
                symbol="",
                message=(
                    f"Could not read the inventory of {', '.join(unread_sources)}, so "
                    "'%seealso' references were not checked this run."
                ),
            )
        )

    def check(text: str, symbol: str) -> None:
        """
        Report unresolved `%seealso` names in a docstring

        Parameters
        ----------
        text :
            The docstring to scan.
        symbol :
            The documented object named in any reported issue.

        Returns
        -------
        :
        """
        for ref_name, _ in parse_seealso(text):
            claimants = index.dropped.get(ref_name)
            if claimants is not None:
                result.issues.append(
                    LintIssue(
                        check="ambiguous-xref",
                        severity="error",
                        symbol=symbol,
                        message=(
                            f"%seealso references '{ref_name}', which is claimed by "
                            f"{' and '.join(claimants)}, so it stays unlinked. Qualify it."
                        ),
                    )
                )
            elif not unread_sources and not index.resolves(ref_name):
                result.issues.append(
                    LintIssue(
                        check="broken-xref",
                        severity="error",
                        symbol=symbol,
                        message=(
                            f"%seealso references '{ref_name}', which neither the API "
                            "reference nor a source it links to documents."
                        ),
                    )
                )

    documented_paths = {item.name for item in documented}

    for name in exports:
        if name not in pkg.members:
            continue

        obj = pkg.members[name]
        docstring = _get_docstring(obj)
        if docstring and f"{package_name}.{name}" in documented_paths:
            check(docstring, name)

        if obj.kind.value == "class":
            for member_name, member in _iter_public_members(obj):
                if f"{package_name}.{name}.{member_name}" not in documented_paths:
                    continue
                member_doc = _get_docstring(member)
                if member_doc:
                    check(member_doc, f"{name}.{member_name}")


_NOT_AUTHORED = {"node_modules"}
"""Directories that do not contain author-written pages"""


_INTERLINK_RE = re.compile(r"\[[^\]]*\]\(`(~?)([\w.]+)`\)")
"""An explicit reference written as `[text](`~pkg.Name`)`"""

_CODE_SPAN_RE = re.compile(r"(`{2,})(?:(?!\1).)*?\1", re.DOTALL)
"""A multi-backtick span that Markdown renders as literal text"""

_AUTOLINK_RE = re.compile(
    r"(?<!`)`(?:~~\.?)?([A-Za-z_][\w.]*)(?:\(\))?`(?!`)(?!\{[^}\n]*\.gd-no-link\b)"
)
"""A code span the build links when it names a documented object, as `name()` or `~~pkg.name`"""

_LINK_RE = re.compile(r"\[[^\]]*\]\([^)\s]*\)")
"""A Markdown link, whose text the build leaves as written"""


_LIST_MARKER_RE = re.compile(r"(?:[-*+]|\d+[.)])\s")
"""The start of a Markdown list item"""


def _indented_code(lines: list[str]) -> list[bool]:
    """
    Mark the lines Markdown renders as an indented code block

    Four spaces of indentation after a blank line opens a code block, and
    further indented or blank lines continue it. The exception is indentation
    under a list item, which continues the item's own prose, so a reference
    written there is one the page really makes.

    Parameters
    ----------
    lines
        Markdown source lines, with any fenced block already removed.

    Returns
    -------
    :
        Whether each line is part of an indented code block.
    """
    code = [False] * len(lines)
    in_code = False
    after_blank = True
    in_list = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            after_blank = True
            continue

        indent = len(line) - len(line.lstrip(" "))
        if in_code:
            if indent >= 4:
                code[i] = True
                after_blank = False
                continue
            in_code = False

        if indent >= 4 and after_blank and not in_list:
            in_code = True
            code[i] = True
        elif indent < 4:
            in_list = _LIST_MARKER_RE.match(stripped) is not None
        after_blank = False

    return code


def _strip_code(text: str) -> str:
    """
    Remove code blocks and multi-backtick code spans from Markdown

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
        The text with fenced blocks, indented blocks and multi-backtick spans
        removed.
    """
    lines, fenced = fenced_lines(text)
    unfenced = [line for line, is_fenced in zip(lines, fenced) if not is_fenced]
    indented = _indented_code(unfenced)
    prose = "\n".join(line for line, is_code in zip(unfenced, indented) if not is_code)
    return _CODE_SPAN_RE.sub("", prose)


def _gather_prose(
    items: list[InventoryItem], project_root: Path, layout: Layout | None = None
) -> dict[str, str]:
    """
    Gather the text the ambiguity check scans

    Read the docstring of every object the reference documents, and the pages
    an author writes under the project root. An object documented under both
    its public path and its module path is read once, under the path that
    claims short names, so a docstring's findings are not reported twice and a
    docstring can be matched to the object it documents.

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
    project_root = project_root.resolve()

    seen = set()
    for item in sorted(items, key=lambda item: not item.aliases):
        docstring = _get_docstring(item.obj)
        if not docstring:
            continue
        try:
            obj = item.obj.canonical_path
        except (gf.AliasResolutionError, gf.CyclicAliasError):
            obj = item.name
        if obj not in seen:
            seen.add(obj)
            prose[item.name] = docstring

    for dirpath, dirnames, filenames in os.walk(project_root):
        here = Path(dirpath)
        # Prune rather than filter afterwards. Quarto renders no path beginning
        # with an underscore, so those pages carry no reference the site can show,
        # and another project's `great-docs.yml` marks pages that must be
        # checked against that project's names. Keep the selected source root.
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith((".", "_"))
            and d not in _NOT_AUTHORED
            and (
                (layout is not None and here / d == layout.source_dir)
                or not (here / d / "great-docs.yml").exists()
            )
            and not is_in_great_docs_build_dir(
                (here / d).relative_to(project_root).parts, project_root, layout
            )
        ]
        for filename in sorted(filenames):
            if not filename.endswith((".qmd", ".md")):
                continue
            path = here / filename
            prose[str(path.relative_to(project_root))] = path.read_text(encoding="utf-8")

    return prose


def _published_origins(
    prose: dict[str, str],
    documented: list[InventoryItem],
    config: Config,
    layout: Layout,
    project_root: Path,
) -> set[str]:
    """
    Pick out the prose the site renders, whose code spans the build links

    Parameters
    ----------
    prose :
        The prose gathered for the ambiguity check, keyed by symbol or file.
    documented :
        The objects the reference documents.
    config :
        The project's configuration.
    layout :
        The project's directories.
    project_root :
        Root of the project, which the files in `prose` are relative to.

    Returns
    -------
    :
        The keys of `prose` for documented docstrings and for the pages the site publishes.
        Notes and plans elsewhere in the project are left out.
    """
    root = project_root.resolve()
    pages = set()
    for path in authored.find_pages(config, layout, report=lambda _: None):
        try:
            pages.add(str(path.resolve().relative_to(root)))
        except ValueError:
            continue
    names = {item.name for item in documented}
    return {origin for origin in prose if origin in names or origin in pages}


def _check_ambiguous_references(
    dropped: dict[str, tuple[str, ...]],
    prose: dict[str, str],
    result: LintResult,
    *,
    autolinked: set[str] | None = None,
) -> None:
    """
    Check prose for references to a short name that two objects claim

    An explicit reference such as `[](`flush`)` is an error. A code span such as
    `` `flush()` `` is a warning: the build would link it if one object claimed the
    name, but the span may be plain code, like a dictionary key, rather than a
    reference. A docstring naming its own object is not reported, and neither is a
    span marked `{.gd-no-link}` or one inside the text of a link, which the build
    leaves alone.

    Parameters
    ----------
    dropped :
        Each short name two objects claim, and the objects claiming it.
    prose :
        Text to scan, keyed by the symbol or file it came from.
    result :
        Aggregated results to append to.
    autolinked :
        The keys of `prose` whose code spans are checked: the docstrings and pages the site
        renders. `None` checks every key.
    """
    if not dropped:
        return

    for origin, text in prose.items():
        text = _strip_code(text)
        for _, name in _INTERLINK_RE.findall(text):
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
        if autolinked is not None and origin not in autolinked:
            continue
        for name in _AUTOLINK_RE.findall(_LINK_RE.sub("", text)):
            targets = dropped.get(name)
            if targets is None or origin in targets:
                continue
            result.issues.append(
                LintIssue(
                    check="ambiguous-autolink",
                    severity="warning",
                    symbol=origin,
                    message=(
                        f"`{name}` is claimed by {' and '.join(targets)}, so the code span "
                        f"stays unlinked. Qualify it, as in `~~{targets[0]}`, or mark it "
                        "`{.gd-no-link}` if it isn't a reference."
                    ),
                )
            )


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
    for style in _PARSERS:
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
        if obj.kind.value == "class":
            for member_name, member in _iter_public_members(obj):
                member_doc = _get_docstring(member)
                if member_doc:
                    _check_one(f"{name}.{member_name}", member_doc)


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
        if obj.kind.value == "class":
            for member_name, member in _iter_public_members(obj):
                member_doc = _get_docstring(member)
                if member_doc:
                    _check_one(f"{name}.{member_name}", member_doc)


# ---------------------------------------------------------------------------
# Stale version annotations
# ---------------------------------------------------------------------------

# Default thresholds (used when no config overrides)
_DEFAULT_BADGE_THRESHOLD = 3  # releases behind latest
_DEFAULT_CALLOUT_THRESHOLD = 4  # releases behind latest


def _check_stale_versions(
    config: Config, project_root: Path, result: LintResult, layout: Layout | None = None
) -> None:
    """
    Flag stale version annotations in `.qmd` files

    Checks for:
      - `[version-badge new X]` where X is many releases behind latest
      - `::: {.version-note version="X"}` / `::: {.version-deprecated version="X"}`
        where X is very old
      - `upcoming: "X"` frontmatter where X is already released

    Parameters
    ----------
    config
        The project's configuration, whose `versions`, `new_is_old` and
        `lint.stale_versions` settings drive the check. Without versions the
        check reports nothing.
    project_root
        The project root containing the pages to scan.
    result
        The lint result to which findings are appended.
    layout
        The project layout used to exclude generated build copies.
    """
    project_root = project_root.resolve()
    raw_config = config.user_settings

    versions_raw = raw_config.get("versions", [])
    if not versions_raw:
        return

    from .._versions.model import parse_versions_config

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
    from .._versions.model import is_badge_expired, parse_badge_expiry

    badge_expiry = parse_badge_expiry(raw_config.get("new_is_old"))

    # Build set of released version identifiers for upcoming check
    released_versions: set[str] = set()
    for v in versions:
        if not v.prerelease:
            released_versions.add(v.tag)
            if v.version:
                released_versions.add(v.version)

    # Match the version markup recognised by versioned builds.
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
        if is_in_great_docs_build_dir(parts, project_root, layout):
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
    from .._versions.model import _find_entry

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


def _site_page_sources(config: Config, layout: Layout) -> list[Path]:
    """
    List the Markdown pages an author writes for the site

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The Markdown homepage source, followed by pages in the user guide, sections and
        custom page directories. Paths with a component starting with `_` or `.` below
        their source directory are excluded because Quarto does not render them.
    """

    def report(message: str) -> None:
        print(f"   ⚠️  {message}")

    return authored.find_pages(config, layout, report=report)


def _check_page_descriptions(
    config: Config, layout: Layout, project_root: Path, result: LintResult
) -> None:
    """
    Flag pages whose search description falls back to the site default

    A page is described by its own `description`, else by its opening
    paragraph. A page that opens with anything else, such as code or a
    callout, gets the default description, or none when the site has no
    default. Generated pages are not checked, because their authors cannot
    change them.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    project_root
        Root of the project, against which page paths are reported.
    result
        Aggregated results to append to.
    """
    from .._website.homepage import hero
    from .._website.seo import description

    if not config.seo_enabled:
        return

    homepage = next(iter(homepage_source.find(layout)), None)
    manifest = Project.make(config, layout).manifest
    has_default = description.default_description(config, manifest["description"]) is not None
    for path in _site_page_sources(config, layout):
        front_matter, body = split_front_matter(path.read_text(encoding="utf-8"))
        if any(key in front_matter for key in description.PAGE_KEYS):
            continue
        if path == homepage:
            # The homepage is described after badges and hero elements are removed
            found = hero.find(config, layout.source_dir, body)
            if found is not None and found.body is not None:
                body = found.body
        citations = description.resolves_citations(front_matter, config)
        fallback = description.first_paragraph(body, citations=citations).fallback
        if fallback is None:
            continue

        symbol = _page_symbol(path, project_root)
        if has_default:
            outcome, remedy = "uses the default description", ""
        else:
            outcome = "has no description, as the site has no default"
            remedy = ", or set `seo.default_description`"
        result.issues.append(
            LintIssue(
                check="default-description",
                severity="info" if has_default else "warning",
                symbol=symbol,
                message=(
                    f"The page {fallback}, so it {outcome}. Open it with "
                    f"a sentence or add `description` to its front matter{remedy}."
                ),
            )
        )


def _page_symbol(path: Path, project_root: Path) -> str:
    """
    Return a page path for a lint issue

    Parameters
    ----------
    path
        The page's source file.
    project_root
        Root of the project.

    Returns
    -------
    :
        The path relative to `project_root`, or the full path for a page
        outside it.
    """
    try:
        return str(path.relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


FrontMatterForm: TypeAlias = Literal["string", "number", "strings", "sequence", "mapping"]
"""An accepted front matter value form"""

_FORM_READERS: dict[
    FrontMatterForm, Callable[[YamlMapping, str], YamlValue | list[str] | YamlMapping]
] = {
    "string": YamlMapping.string,
    "number": YamlMapping.number,
    "strings": YamlMapping.strings,
    "sequence": YamlMapping.sequence,
    "mapping": YamlMapping.mapping,
}

_FORM_NAMES: dict[FrontMatterForm, str] = {
    "string": "a string",
    "number": "a number",
    "strings": "a string or a list of strings",
    "sequence": "a list",
    "mapping": "a mapping",
}

GREAT_DOCS_KEYS: dict[str, tuple[FrontMatterForm, ...]] = {
    "date_created": ("string",),
    "guide-section": ("string",),
    "last_update": ("mapping",),
    "last_update.author": ("string",),
    "last_update.date": ("string",),
    "scale-to-fit": ("string", "sequence"),
    "scale-to-fit-min-scale": ("string", "number"),
    "status": ("string",),
    "tag-location": ("string",),
    "tags": ("sequence",),
}
"""
Great Docs front matter keys and their accepted value forms

Use dotted paths for nested keys. Exclude keys validated by Quarto and
keys that Great Docs reads directly from the source text.
"""


def _accepts(front_matter: YamlMapping, key: str, form: FrontMatterForm, value: YamlValue) -> bool:
    """
    Check whether a value matches an accepted form

    Parameters
    ----------
    front_matter
        The mapping that holds the value.
    key
        The value's key in `front_matter`.
    form
        The expected value form.
    value
        The value.

    Returns
    -------
    :
        `True` when the accessor accepts the value, including an empty
        list or mapping of the expected form.
    """
    read = _FORM_READERS[form](front_matter, key)
    if isinstance(read, YamlMapping):
        return bool(read) or value == {}
    if isinstance(read, list):
        return bool(read) or value == []
    return read is not None


def _wrong_type(front_matter: YamlMapping, path: str, forms: tuple[FrontMatterForm, ...]) -> bool:
    """
    Check whether a page sets a key to a value the build ignores

    Parameters
    ----------
    front_matter
        The page's front matter.
    path
        The dotted path of the key.
    forms
        The forms the build accepts.

    Returns
    -------
    :
        `True` when the key has a value that no form accepts. An absent key,
        `null`, and a key under a parent of the wrong type are not reported.
    """
    *parents, key = path.split(".")
    for parent in parents:
        front_matter = front_matter.mapping(parent)
    value = front_matter.get(key)
    if value is None:
        return False
    return not any(_accepts(front_matter, key, form, value) for form in forms)


def _check_front_matter(
    config: Config, layout: Layout, project_root: Path, result: LintResult
) -> None:
    """
    Flag Great Docs front matter values with unsupported types

    The build ignores such a value, so the page renders as if the key were
    unset.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    project_root
        Root of the project, against which page paths are reported.
    result
        Aggregated results to append to.
    """
    for path in _site_page_sources(config, layout):
        front_matter, _ = split_front_matter(path.read_text(encoding="utf-8"))
        for key, forms in GREAT_DOCS_KEYS.items():
            if not _wrong_type(front_matter, key, forms):
                continue
            expected = " or ".join(_FORM_NAMES[form] for form in forms)
            result.issues.append(
                LintIssue(
                    check="front-matter",
                    severity="warning",
                    symbol=_page_symbol(path, project_root),
                    message=f"`{key}` should be {expected}; the value is ignored.",
                )
            )
