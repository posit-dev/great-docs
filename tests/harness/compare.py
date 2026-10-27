"""
Compare two harness recordings and report every difference

Compare exit statuses, file changes, step skeletons, warnings, handled exceptions, the
number of Python processes and calls to the stub `quarto`. Every difference fails the
comparison, including a handled exception that disappears, so each change requires review.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tests.harness.sides import environment_differences

# Limit report size by capping diff lines per file and the number of files with diffs.
DIFF_LINES = 60
DIFF_FILES = 8


@dataclass
class CaseResult:
    """
    The outcome of one build case

    Attributes
    ----------
    case :
        Case identifier.
    status :
        `match`, `differ`, or `missing` when one side has no manifest.
    findings :
        Report lines, one finding per line, with indented detail lines.
    """

    case: str
    status: str
    findings: list[str] = field(default_factory=list[str])


@dataclass
class Comparison:
    """
    The outcome of comparing two recordings

    Attributes
    ----------
    base, test :
        Recording directories.
    environment :
        Differences between the sides' facts that change build output.
    cases :
        One result per case recorded on either side.
    """

    base: str
    test: str
    environment: list[str]
    cases: list[CaseResult]

    @property
    def matches(self) -> bool:
        """Whether the environments agree and every case matches"""
        return not self.environment and all(c.status == "match" for c in self.cases)


def _load(path: Path) -> dict[str, Any]:
    """
    Read a recording file as JSON

    Parameters
    ----------
    path :
        The file.

    Returns
    -------
    :
        Its content.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _blob(recording: Path, digest: str) -> bytes:
    """
    Read normalised content from a recording's blob store

    Parameters
    ----------
    recording :
        A side's recording directory.
    digest :
        SHA-256 of the content.

    Returns
    -------
    :
        The content.
    """
    return (recording / "blobs" / digest[:2] / digest).read_bytes()


def file_diff(base: Path, test: Path, path: str, old: str, new: str) -> list[str]:
    """
    Show how a file's normalised content changed

    Parameters
    ----------
    base, test :
        Recording directories.
    path :
        Project-relative path of the file.
    old, new :
        SHA-256 of the content on each side.

    Returns
    -------
    :
        A unified diff cut to `DIFF_LINES` lines, or a size comparison for binary content.
    """
    before, after = _blob(base, old), _blob(test, new)
    try:
        a, b = before.decode("utf-8"), after.decode("utf-8")
    except UnicodeDecodeError:
        return [f"binary content differs ({len(before)} -> {len(after)} bytes)"]
    lines = list(
        difflib.unified_diff(
            a.splitlines(), b.splitlines(), f"base/{path}", f"test/{path}", n=2, lineterm=""
        )
    )
    if len(lines) > DIFF_LINES:
        lines = [*lines[:DIFF_LINES], f"... {len(lines) - DIFF_LINES} more diff lines"]
    return lines


def compare_files(
    base: Path, test: Path, old: Sequence[Mapping[str, Any]], new: Sequence[Mapping[str, Any]]
) -> list[str]:
    """
    Compare the files one command wrote on each side

    Parameters
    ----------
    base, test :
        Recording directories.
    old, new :
        File records of the command on each side.

    Returns
    -------
    :
        Findings: files written on one side only, then changed files with their diffs.
    """
    a = {r["path"]: r for r in old}
    b = {r["path"]: r for r in new}
    findings = [f"file only in base: {p} ({a[p]['change']})" for p in sorted(set(a) - set(b))]
    findings += [f"file only in test: {p} ({b[p]['change']})" for p in sorted(set(b) - set(a))]
    changed = [
        p
        for p in sorted(set(a) & set(b))
        if (a[p].get("change"), a[p].get("sha256")) != (b[p].get("change"), b[p].get("sha256"))
    ]
    for shown, path in enumerate(changed):
        if a[path].get("change") != b[path].get("change"):
            findings.append(
                f"file {path}: {a[path]['change']} in base, {b[path]['change']} in test"
            )
            continue
        findings.append(f"file changed: {path}")
        if shown < DIFF_FILES:
            diff = file_diff(base, test, path, a[path]["sha256"], b[path]["sha256"])
            findings += [f"    {line}" for line in diff]
    return findings


def _census_line(entry: Mapping[str, Any]) -> str:
    """
    Describe one census entry for the report

    Parameters
    ----------
    entry :
        The entry.

    Returns
    -------
    :
        Type, message, raising function and handlers on one line.
    """
    return (
        f"{entry['type']}: {entry['message']!r} raised in {entry['raised_in']} "
        f"({', '.join(entry['raised_at'])}), handled in {', '.join(entry['handlers'])}"
    )


def compare_census(old: Sequence[Mapping[str, Any]], new: Sequence[Mapping[str, Any]]) -> list[str]:
    """
    Compare the handled exceptions of one command

    Parameters
    ----------
    old, new :
        Census entries on each side.

    Returns
    -------
    :
        Findings for new entries, entries that disappeared and changed counts.
    """

    def keyed(
        entries: Sequence[Mapping[str, Any]],
    ) -> dict[tuple[str, str, str], Mapping[str, Any]]:
        return {(e["type"], e["message"], e["raised_in"]): e for e in entries}

    a, b = keyed(old), keyed(new)
    findings = [
        f"NEW handled exception: {_census_line(b[k])} x{b[k]['count']}"
        for k in sorted(set(b) - set(a))
    ]
    findings += [
        f"handled exception gone: {_census_line(a[k])} x{a[k]['count']}"
        for k in sorted(set(a) - set(b))
    ]
    findings += [
        f"handled exception count {a[k]['count']} -> {b[k]['count']}: {_census_line(b[k])}"
        for k in sorted(set(a) & set(b))
        if a[k]["count"] != b[k]["count"]
    ]
    return findings


def compare_lists(label: str, old: Sequence[str], new: Sequence[str]) -> list[str]:
    """
    Compare two lists of lines as a unified diff

    Parameters
    ----------
    label :
        What the lines are, for the finding.
    old, new :
        The lines on each side.

    Returns
    -------
    :
        No findings when the lists are equal; otherwise one finding and the diff.
    """
    if list(old) == list(new):
        return []
    diff = difflib.unified_diff(list(old), list(new), "base", "test", n=1, lineterm="")
    return [f"{label} differs", *(f"    {line}" for line in list(diff)[2:])]


def compare_warnings(old: Sequence[str], new: Sequence[str]) -> list[str]:
    """
    Compare the `[!!]` warnings of one command

    Parameters
    ----------
    old, new :
        Warning lines on each side.

    Returns
    -------
    :
        Findings for new warnings and warnings that disappeared.
    """
    findings = [f"NEW warning: {w}" for w in new if w not in old]
    findings += [f"warning gone: {w}" for w in old if w not in new]
    if not findings and list(old) != list(new):
        findings.append("warnings repeat or appear in a different order")
    return findings


def compare_command(
    base: Path, test: Path, old: Mapping[str, Any], new: Mapping[str, Any]
) -> list[str]:
    """
    Compare the records of one command

    Parameters
    ----------
    base, test :
        Recording directories.
    old, new :
        The command's record on each side.

    Returns
    -------
    :
        Findings, empty when the records agree.
    """
    findings: list[str] = []
    for key, label in (("status", "exit status"), ("python_processes", "Python processes")):
        if old.get(key) != new.get(key):
            findings.append(f"{label} {old.get(key)} -> {new.get(key)}")
    findings += compare_files(base, test, old.get("files", []), new.get("files", []))
    findings += compare_lists("step skeleton", old.get("skeleton", []), new.get("skeleton", []))
    findings += compare_warnings(old.get("warnings", []), new.get("warnings", []))
    findings += compare_census(old.get("census", []), new.get("census", []))
    findings += compare_lists(
        "quarto calls", old.get("quarto_calls", []), new.get("quarto_calls", [])
    )
    return findings


def compare_case(base: Path, test: Path, case: str) -> CaseResult:
    """
    Compare one build case between two recordings

    Parameters
    ----------
    base, test :
        Recording directories.
    case :
        Case identifier.

    Returns
    -------
    :
        The case's result.
    """
    a, b = base / "builds" / f"{case}.json", test / "builds" / f"{case}.json"
    if not (a.exists() and b.exists()):
        side = "test" if a.exists() else "base"
        return CaseResult(case, "missing", [f"no manifest in {side}"])
    old, new = _load(a), _load(b)
    findings: list[str] = []
    for name in dict.fromkeys([*old["commands"], *new["commands"]]):
        if name not in old["commands"] or name not in new["commands"]:
            findings.append(f"{name}: run on one side only")
            continue
        # Detail lines retain their indentation beneath the command-prefixed finding.
        for finding in compare_command(base, test, old["commands"][name], new["commands"][name]):
            findings.append(finding if finding.startswith(" ") else f"{name}: {finding}")
    return CaseResult(case, "differ" if findings else "match", findings)


def compare(base: Path, test: Path) -> Comparison:
    """
    Compare two recordings case by case

    Parameters
    ----------
    base, test :
        Recording directories of one side each.

    Returns
    -------
    :
        The comparison.
    """
    old, new = _load(base / "side.json"), _load(test / "side.json")
    cases = list(dict.fromkeys([*old["cases"], *new["cases"]]))
    return Comparison(
        str(base),
        str(test),
        environment_differences(old["facts"], new["facts"]),
        [compare_case(base, test, case) for case in cases],
    )


def render(
    comparison: Comparison, base_meta: Mapping[str, Any], test_meta: Mapping[str, Any]
) -> str:
    """
    Format the comparison as a plain-text report

    Parameters
    ----------
    comparison :
        The comparison.
    base_meta, test_meta :
        Contents of each side's `side.json`.

    Returns
    -------
    :
        The report, ending with a one-line verdict.
    """

    def side_line(meta: Mapping[str, Any]) -> str:
        facts = meta["facts"]
        dirty = ", local changes" if facts.get("local_changes") else ""
        return f"{meta['label']}: {facts['checkout']} @ {facts['commit'][:12]}{dirty}"

    facts = base_meta["facts"]
    tools = facts.get("tools", {})
    lines = [
        "Great Docs characterisation harness",
        side_line(base_meta),
        side_line(test_meta),
        f"python {facts.get('python')}, stub quarto {facts.get('stub_quarto_version')} "
        f"(real {tools.get('quarto')}), d2 {tools.get('d2')}, {tools.get('ruff')}",
        f"{len(comparison.cases)} cases; wall time {base_meta.get('wall_seconds')} s (base), "
        f"{test_meta.get('wall_seconds')} s (test)",
        "",
    ]
    if comparison.environment:
        lines += ["ENVIRONMENT DIFFERS", *(f"  {d}" for d in comparison.environment), ""]
    failing = [
        f"{c.case} (build exit {s})"
        for c in comparison.cases
        if (s := _build_status(Path(comparison.base), c.case)) not in (0, None)
    ]
    if failing:
        lines += [f"non-zero exit in base: {', '.join(failing)}", ""]
    for result in comparison.cases:
        if result.status == "match":
            continue
        lines.append(f"{result.case}: {result.status.upper()}")
        lines += [f"  {f}" for f in result.findings]
        lines.append("")
    differ = [c.case for c in comparison.cases if c.status != "match"]
    verdict = (
        f"MATCH: all {len(comparison.cases)} cases"
        if comparison.matches
        else f"DIFFER: {len(differ)} of {len(comparison.cases)} cases"
        + (", environment" if comparison.environment else "")
    )
    lines.append(verdict)
    return "\n".join(lines)


def _build_status(recording: Path, case: str) -> int | str | None:
    """
    Read the exit status of a case's build command

    Parameters
    ----------
    recording :
        A side's recording directory.
    case :
        Case identifier.

    Returns
    -------
    :
        The status, or `None` when the case has no manifest or no build command.
    """
    path = recording / "builds" / f"{case}.json"
    if not path.exists():
        return None
    return _load(path)["commands"].get("build", {}).get("status")


def write_reports(comparison: Comparison, directory: Path) -> str:
    """
    Write `report.txt` and `report.json` for a comparison

    Parameters
    ----------
    comparison :
        The comparison.
    directory :
        Destination directory.

    Returns
    -------
    :
        The text report.
    """
    base_meta = _load(Path(comparison.base) / "side.json")
    test_meta = _load(Path(comparison.test) / "side.json")
    text = render(comparison, base_meta, test_meta)
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / "report.txt").write_text(text + "\n", encoding="utf-8")
    payload = {"matches": comparison.matches, **asdict(comparison)}
    _ = (directory / "report.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return text
