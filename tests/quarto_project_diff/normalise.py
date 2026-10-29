"""
Text normalisation and log summaries for recordings

Rules remove text that varies between runs or checkouts without a change in behaviour.
Each manifest counts replacements by rule.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

ISO_META_TAGS = ("gd-build-time", "gd-page-modified", "gd-page-created")


@dataclass(frozen=True)
class Rule:
    """
    A substitution that removes one source of noise from text

    Attributes
    ----------
    name :
        Identifier counted in manifests.
    pattern :
        What to replace.
    replacement :
        Replacement text; may refer to groups of `pattern`.
    scope :
        Path fragments the rule is limited to; empty for every path.
    """

    name: str
    pattern: re.Pattern[str]
    replacement: str
    scope: tuple[str, ...] = ()

    def apply(self, text: str, path: str) -> tuple[str, int]:
        """
        Apply the rule to the text of one file

        Parameters
        ----------
        text :
            File content.
        path :
            POSIX path of the file, matched against `scope`.

        Returns
        -------
        :
            The new text and the number of replacements.
        """
        if self.scope and not any(fragment in path for fragment in self.scope):
            return text, 0
        return self.pattern.subn(self.replacement, text)


FILE_RULES: tuple[Rule, ...] = (
    # A development checkout appends its own commit to the page footer. A YAML writer may
    # fold the footer, so a line break can stand for either space.
    Rule(
        "great-docs-commit",
        re.compile(
            r'\s+\(<a\s+href=\\?"https://github\.com/posit-dev/great-docs/commit/[0-9a-f]+\\?">'
            r"[0-9a-f]+</a>\)"
        ),
        "",
    ),
    # Replace timestamps only in the meta tags that `show_dates` writes; data files keep
    # their own timestamps for comparison.
    Rule(
        "iso-timestamp",
        re.compile(r'(name=\\?"(?:' + "|".join(ISO_META_TAGS) + r')\\?" content=\\?")[^"\\]*'),
        r"\g<1><TIMESTAMP>",
    ),
    # `marimo export` gives every UI element a random identifier, in the exported islands
    # and in the session file it leaves beside the notebook.
    Rule(
        "marimo-uuid",
        re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
        "<UUID>",
        scope=("_marimo_islands/", "__marimo__/session/"),
    ),
)

_ADDRESS = re.compile(r"0x[0-9a-fA-F]{6,}")


def path_rules(paths: Mapping[str, Path]) -> tuple[Rule, ...]:
    """
    Make rules that replace absolute paths with tokens

    Replace both the given and resolved forms, longest first. This preserves the token
    for a nested path when its parent also has a token.

    Parameters
    ----------
    paths :
        Mapping from each token, such as `<PKG>`, to the directory it represents.

    Returns
    -------
    :
        One rule per distinct path form.
    """
    forms: dict[str, str] = {}
    for token, path in paths.items():
        for form in (str(path), str(path.resolve())):
            _ = forms.setdefault(form, token)
    ordered = sorted(forms.items(), key=lambda item: len(item[0]), reverse=True)
    return tuple(
        Rule(f"path:{token}", re.compile(re.escape(form)), token) for form, token in ordered
    )


def normalise_text(text: str, path: str, rules: Iterable[Rule]) -> tuple[str, dict[str, int]]:
    """
    Apply rules to text in order

    Parameters
    ----------
    text :
        The text to normalise.
    path :
        POSIX path of the file the text comes from.
    rules :
        Rules to apply.

    Returns
    -------
    :
        The normalised text and the replacements per rule name.
    """
    counts: dict[str, int] = {}
    for rule in rules:
        text, n = rule.apply(text, path)
        if n:
            counts[rule.name] = counts.get(rule.name, 0) + n
    return text, counts


def normalise_bytes(data: bytes, path: str, rules: Iterable[Rule]) -> tuple[bytes, dict[str, int]]:
    """
    Apply rules to file content that decodes as UTF-8 text

    Parameters
    ----------
    data :
        File content.
    path :
        POSIX path of the file.
    rules :
        Rules to apply.

    Returns
    -------
    :
        The normalised content, unchanged for binary data, and the replacements per rule.
    """
    if b"\x00" in data:
        return data, {}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, {}
    text, counts = normalise_text(text, path, rules)
    return text.encode("utf-8"), counts


def normalise_message(text: str, rules: Iterable[Rule], limit: int = 200) -> str:
    """
    Normalise an exception message for comparison

    Parameters
    ----------
    text :
        Message as the observer recorded it.
    rules :
        Path rules for the build.
    limit :
        Maximum message length in characters.

    Returns
    -------
    :
        The message with paths and object addresses replaced, cut to `limit` characters.
    """
    text, _ = normalise_text(text, "", rules)
    return _ADDRESS.sub("0x<ADDR>", text)[:limit]


_STEP = re.compile(r"^-- (Step\s+\d+/\d+ - .*?)\s*-*$")
_MARKER = re.compile(r"\[(?:OK|--|!!|FAIL|\.\.)\]")
_ELAPSED = re.compile(r"\s+(?:<0\.1s|\d+h \d+m \d+s|\d+m \d+\.\d+s|\d+\.\d+s)$")


def log_skeleton(stdout: str, stderr: str) -> list[str]:
    """
    Reduce a command's output to the lines that show its step structure

    The skeleton keeps step titles, `[OK]`, `[--]`, `[!!]` and `[FAIL]` lines, the summary
    line of the closing box and `Error:` lines, without timings or padding. It records the
    order of the build steps and how each ended.

    Parameters
    ----------
    stdout, stderr :
        The command's normalised output streams.

    Returns
    -------
    :
        Skeleton lines, standard output first.
    """
    lines: list[str] = []
    for raw in [*stdout.splitlines(), *stderr.splitlines()]:
        line = raw.strip()
        if line.startswith("|") and line.endswith("|"):
            line = line.strip("|").strip()
            if not _MARKER.search(line):
                continue
        step = _STEP.match(line)
        if step:
            lines.append(step.group(1))
        elif _MARKER.match(line):
            lines.append(" ".join(_ELAPSED.sub("", line).split()))
        elif line.startswith("Error:"):
            lines.append(line)
    return lines


def log_warnings(*outputs: str) -> list[str]:
    """
    Collect the `[!!]` lines of command output

    Parameters
    ----------
    *outputs :
        Normalised output streams.

    Returns
    -------
    :
        The warning lines with timings and padding removed, in order.
    """
    return [
        " ".join(_ELAPSED.sub("", line.strip()).split())
        for text in outputs
        for line in text.splitlines()
        if "[!!]" in line
    ]
