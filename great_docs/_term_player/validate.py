"""Checks for a recording and its script (`great-docs termshow validate`).

Two kinds of problem are reported:

- errors: the file breaks the format. The recording has a malformed header or
  event line, or the script has an unknown key, a value of the wrong type or
  outside its allowed set, a cut that ends before it starts, a pattern that
  isn't a regular expression, or a step option that doesn't go with its action. The rules come from the published JSON Schemas
  in `schemas/`, read at run time, so the two can't drift apart.
- warnings: the file is valid but probably not what was meant. Something
  starts after the recording ends, two cuts or two copy buttons overlap,
  chapters are out of order, two annotations cover each other, or a `match`
  pattern never appears on screen while it's active.

Cuts and speed segments are on the recording's own timeline. Everything else
(chapters, annotations, highlights, snippets) is on the playback timeline,
after the cuts and speed changes, so those are checked against the length of
the played recording.
"""

from __future__ import annotations

import difflib
import json
import re
import shlex
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import Manifest, generate_manifest
from .parser import Recording, parse_asciicast_str, parse_termshow_str
from .script import Script, _parse_script_data, apply_script
from .themes import _normalize_name, resolve_theme_pair

ERROR = "error"
WARNING = "warning"

# Stretches without output longer than this (in playback seconds) are reported
IDLE_WARNING_SECONDS = 10.0
# Stop listing malformed event lines after this many
_MAX_EVENT_ERRORS = 10

_SCHEMA_DIR = Path(__file__).parent / "schemas"
_SCRIPT_SCHEMA: dict[str, Any] = json.loads(
    (_SCHEMA_DIR / "termshow-script.schema.json").read_text(encoding="utf-8")
)
_RECORDING_SCHEMA: dict[str, Any] = json.loads(
    (_SCHEMA_DIR / "termshow-recording.schema.json").read_text(encoding="utf-8")
)
_MANIFEST_SCHEMA: dict[str, Any] = json.loads(
    (_SCHEMA_DIR / "termshow-manifest.schema.json").read_text(encoding="utf-8")
)
_DEFS: dict[str, Any] = _SCRIPT_SCHEMA["$defs"]
THEME_NAMES: list[str] = list(_DEFS["themeName"]["enum"])

# Script sections that are lists of timed items, and the schema definition of each item
_SECTIONS = {
    "chapters": "chapter",
    "cuts": "cut",
    "speed_map": "speedSegment",
    "annotations": "annotation",
    "highlights": "highlight",
    "snippets": "snippet",
}

# Python regex syntax the player's JavaScript `RegExp` rejects or reads differently
_PYTHON_ONLY_REGEX = [
    (re.compile(r"\(\?P[<=>]"), "named groups are written (?<name>...) in JavaScript"),
    (re.compile(r"^\(\?[aiLmsux]+\)"), "JavaScript doesn't support inline flags like (?i)"),
    (re.compile(r"(?<!\\)(?:\\\\)*\\[AZ]"), r"\A and \Z are Python-only; use ^ and $"),
    (re.compile(r"\(\?>"), "JavaScript doesn't support atomic groups (?>...)"),
    (re.compile(r"\(\?#"), "JavaScript doesn't support (?#...) comments"),
    (re.compile(r"(?<!\\)[*+?}]\+"), "JavaScript doesn't support possessive quantifiers"),
]


@dataclass
class Problem:
    """One problem found in a recording or script."""

    file: str
    """Name of the file the problem is in."""
    where: str
    """Where in the file: `line 4`, `header.term.cols`, `annotations[2].position`, or empty."""
    message: str
    severity: str = ERROR
    """`"error"` or `"warning"`."""

    def __str__(self) -> str:
        return ": ".join(part for part in (self.file, self.where, self.message) if part)


Report = Callable[[str, str], None]


def validate(
    source: str | Path, script: str | Path | None = None, *, use_script: bool = True
) -> list[Problem]:
    """Check a recording and its script.

    Parameters
    ----------
    source
        A `.termshow` recording, or an asciinema `.cast` file (which is only
        checked for being readable). A bundle (`.termshow.json`) or a
        `manifest.json` is checked on its own, with no script.
    script
        The script to check with it. Defaults to the companion `.termshow.yml`
        next to the recording, if there is one.
    use_script
        Check the recording on its own, ignoring any script.

    Returns
    -------
    list[Problem]
        Errors and warnings, recording first, then script.
    """
    source = Path(source)
    problems: list[Problem] = []

    text = source.read_text(encoding="utf-8")
    if source.suffix == ".json":
        check_manifest_text(text, source.name, problems)
        return problems
    if source.suffix == ".cast":
        recording = _check_asciicast(text, source.name, problems)
    else:
        recording = check_recording_text(text, source.name, problems)

    data: dict[str, Any] | None = None
    script_name = ""
    if use_script:
        script_path = Path(script) if script else source.with_suffix(".termshow.yml")
        script_name = script_path.name
        if script_path.exists():
            data = check_script_text(script_path.read_text(encoding="utf-8"), script_name, problems)
        elif script:
            problems.append(Problem(script_name, "", "file not found"))

    if recording is not None:
        check_timeline(recording, data or {}, script_name or source.name, problems)
    return problems


# ---------------------------------------------------------------------------
# The recording
# ---------------------------------------------------------------------------


def check_recording_text(
    text: str, name: str, problems: list[Problem] | None = None
) -> Recording | None:
    """Check `.termshow` text against the recording format.

    Appends to `problems` and returns the parsed recording, or None if it has
    errors.
    """
    problems = [] if problems is None else problems
    start = len(problems)

    def error(where: str, message: str) -> None:
        problems.append(Problem(name, where, message))

    lines = [
        (n, line)
        for n, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        error("", "the file is empty (it needs a header line)")
        return None

    n, line = lines[0]
    try:
        header = json.loads(line)
    except json.JSONDecodeError as e:
        error(f"line {n}", f"the header isn't valid JSON ({e.msg})")
        return None
    if not isinstance(header, dict):
        error(f"line {n}", f"the header must be a JSON object, got {_describe(header)}")
        return None
    _check_value(header, _RECORDING_SCHEMA["$defs"]["header"], "header", error, _RECORDING_SCHEMA)

    event_errors = 0
    for n, line in lines[1:]:
        before = len(problems)
        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            error(f"line {n}", f"not valid JSON ({e.msg})")
        else:
            _check_event(event, f"line {n}", error)
        if len(problems) > before:
            event_errors += 1
            if event_errors == _MAX_EVENT_ERRORS:
                rest = sum(1 for m, _ in lines[1:] if m > n)
                if rest:
                    error(
                        "", f"stopped after {_MAX_EVENT_ERRORS} bad event lines ({rest} unchecked)"
                    )
                break

    if len(problems) > start:
        return None
    recording = parse_termshow_str(text)
    if not any(ev.code == "o" for ev in recording.events):
        problems.append(Problem(name, "", "the recording has no output", WARNING))
    return recording


def _check_event(event: Any, where: str, error: Report) -> None:
    if not isinstance(event, list) or len(event) != 3:
        error(where, f"an event must be [delay, code, data], got {_short(event)}")
        return
    delay, code, data = event
    if not _is_number(delay):
        error(where, f"the delay must be a number, got {_describe(delay)}")
    elif delay < 0:
        error(where, f"the delay can't be negative (got {delay})")
    if not isinstance(code, str) or not code:
        error(where, f"the event code must be a non-empty string, got {_describe(code)}")
    if not isinstance(data, str):
        error(where, f"the event data must be a string, got {_describe(data)}")
    elif code == "r" and not re.fullmatch(r"[0-9]+x[0-9]+", data):
        error(where, f"a resize event's data must look like '80x24', got {data!r}")
    elif code == "x" and not re.fullmatch(r"-?[0-9]+", data):
        error(where, f"an exit event's data must be a whole number, got {data!r}")


def _check_asciicast(text: str, name: str, problems: list[Problem]) -> Recording | None:
    try:
        return parse_asciicast_str(text)
    except (ValueError, KeyError, TypeError, IndexError) as e:
        problems.append(Problem(name, "", f"can't read this asciicast file ({e})"))
        return None


# ---------------------------------------------------------------------------
# The script: structure
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# A bundle or manifest
# ---------------------------------------------------------------------------

# Stop listing a manifest's errors after this many (a broken one can have thousands)
_MAX_MANIFEST_ERRORS = 20


def check_manifest_text(text: str, name: str, problems: list[Problem] | None = None) -> bool:
    """Check a bundle (`.termshow.json`) or a `manifest.json` against the manifest format.

    Beyond the schema, the references inside it are checked: keyframes point at frames that
    exist, in time order from 0, and frames point at rows that exist.

    Returns whether it has no errors.
    """
    problems = problems if problems is not None else []
    found: list[tuple[str, str]] = []

    def error(where: str, message: str) -> None:
        found.append((where, message))

    try:
        data = json.loads(text)
    except ValueError as e:
        error("", f"isn't valid JSON ({e})")
        data = None
    if data is not None and _check_value(data, _MANIFEST_SCHEMA, "", error, _MANIFEST_SCHEMA):
        _check_manifest_references(data, error)

    for where, message in found[:_MAX_MANIFEST_ERRORS]:
        problems.append(Problem(name, where, message))
    if len(found) > _MAX_MANIFEST_ERRORS:
        more = len(found) - _MAX_MANIFEST_ERRORS
        problems.append(Problem(name, "", f"{_plural(more, 'more error')} not shown"))
    return not found


def _check_manifest_references(data: dict[str, Any], error: Report) -> None:
    keyframes = data["keyframes"]
    if keyframes[0]["time"] != 0:
        error("keyframes[0].time", f"the first keyframe must be at 0 (got {keyframes[0]['time']})")
    for i in range(1, len(keyframes)):
        if keyframes[i]["time"] < keyframes[i - 1]["time"]:
            error(f"keyframes[{i}].time", "keyframes must be in time order")
    if data["version"] < 2:
        return

    frames, lines = data["frames"], data["lines"]
    for i, keyframe in enumerate(keyframes):
        if keyframe["frame"] >= len(frames):
            error(f"keyframes[{i}].frame", _missing(keyframe["frame"], frames, "frame"))
    for i, frame in enumerate(frames):
        for j, line in enumerate(frame["lines"]):
            if line >= len(lines):
                error(f"frames[{i}].lines[{j}]", _missing(line, lines, "row"))
    dark = data.get("dark")
    if dark is not None and len(dark["lines"]) != len(lines):
        error(
            "dark.lines",
            f"must have one row for each of lines ({len(lines)}), got {len(dark['lines'])}",
        )


def _missing(index: int, items: list, word: str) -> str:
    return f"there's no {word} {index} (there are {_plural(len(items), word)})"


def check_script_text(
    text: str, name: str, problems: list[Problem] | None = None
) -> dict[str, Any] | None:
    """Check `.termshow.yml` text against the script format.

    Appends to `problems` and returns the script data with every entry that
    has an error left out (so the timeline checks can still run on the rest),
    or None if the file can't be read at all.
    """
    from yaml12 import parse_yaml

    problems = [] if problems is None else problems
    try:
        data = parse_yaml(text)
    except ValueError as e:
        problems.append(Problem(name, "", str(e)))
        return None
    if data is None:
        return {}
    return check_script_data(data, name, problems)


def check_script_data(
    data: Any, name: str, problems: list[Problem] | None = None
) -> dict[str, Any] | None:
    """Check parsed script data. See `check_script_text()`."""
    problems = [] if problems is None else problems

    def error(where: str, message: str) -> None:
        problems.append(Problem(name, where, message))

    def warn(where: str, message: str) -> None:
        problems.append(Problem(name, where, message, WARNING))

    if not isinstance(data, dict):
        error("", f"a script must be a mapping of keys to values, got {_describe(data)}")
        return None

    clean: dict[str, Any] = {}
    for key in data:
        if key not in _SCRIPT_SCHEMA["properties"]:
            error("", _unknown_key(key, _SCRIPT_SCHEMA["properties"]))

    if "source" in data:
        if _check_value(data["source"], {"type": "string"}, "source", error):
            clean["source"] = data["source"]

    if "settings" in data:
        clean["settings"] = _check_settings(data["settings"], error, warn)

    if "record" in data:
        _check_record(data["record"], error)
    if "steps" in data:
        _check_steps(data["steps"], error)
    if "check" in data:
        _check_check(data["check"], error)

    for section, def_name in _SECTIONS.items():
        if section not in data:
            continue
        items = data[section]
        if not isinstance(items, list):
            error(section, f"must be a list, got {_describe(items)}")
            continue
        kept = []
        for i, item in enumerate(items):
            where = f"{section}[{i}]"
            ok = _check_value(item, {"$ref": f"#/$defs/{def_name}"}, where, error)
            if ok:
                ok = _check_item_extras(section, item, where, error, warn)
            # Keep the original index so later messages point at the right entry
            kept.append((i, item) if ok else None)
        clean[section] = kept
    return clean


def _check_record(record: Any, error: Report) -> None:
    if not _check_value(record, {"$ref": "#/$defs/record"}, "record", error) and not isinstance(
        record, dict
    ):
        return
    if isinstance(record.get("prompt_pattern"), str):
        # Matched by the recorder, so Python's regex syntax applies
        _check_regex(record["prompt_pattern"], "record.prompt_pattern", error, js=False)
    if isinstance(record.get("shell"), str):
        try:
            shlex.split(record["shell"])
        except ValueError as e:
            error("record.shell", f"can't be split into words ({e})")


def _check_check(check: Any, error: Report) -> None:
    if not _check_value(check, {"$ref": "#/$defs/check"}, "check", error) and not isinstance(
        check, dict
    ):
        return
    ignore = check.get("ignore")
    if isinstance(ignore, list):
        for i, pattern in enumerate(ignore):
            if isinstance(pattern, str) and pattern:
                # Matched by `termshow check`, so Python's regex syntax applies
                _check_regex(pattern, f"check.ignore[{i}]", error, js=False)


def _check_steps(steps: Any, error: Report) -> None:
    from .steps import ACTIONS

    if not isinstance(steps, list):
        error("steps", f"must be a list, got {_describe(steps)}")
        return
    for i, step in enumerate(steps):
        where = f"steps[{i}]"
        if not _check_value(step, {"$ref": "#/$defs/step"}, where, error) or isinstance(step, str):
            continue
        action = next(k for k in step if k in ACTIONS)
        for key in step:
            if key != action and key not in ACTIONS and key not in ACTIONS[action]:
                goes_with = [a for a, options in ACTIONS.items() if key in options]
                error(f"{where}.{key}", f"goes with {_or(goes_with)}, not {action!r}")
        if action == "wait_for":
            # Matched by the recorder, so Python's regex syntax applies
            _check_regex(step["wait_for"], f"{where}.wait_for", error, js=False)


def _check_settings(settings: Any, error: Report, warn: Report) -> dict[str, Any]:
    schema = _DEFS["settings"]
    if not isinstance(settings, dict):
        error("settings", f"must be a mapping, got {_describe(settings)}")
        return {}
    clean = {}
    for key, value in settings.items():
        where = f"settings.{key}"
        if key not in schema["properties"]:
            error("settings", _unknown_key(key, schema["properties"]))
            continue
        if key == "theme":
            ok = _check_theme(value, where, error, warn)
        else:
            ok = _check_value(value, schema["properties"][key], where, error)
            if ok and key == "prompt_pattern" and value is not None:
                # Used by Python when rendering, so Python's regex syntax applies
                ok = _check_regex(value, where, error, js=False)
        if ok:
            clean[key] = value
    return clean


def _check_theme(value: Any, where: str, error: Report, warn: Report) -> bool:
    if value == "auto":
        return True
    if isinstance(value, dict) and {"light", "dark"} & set(value):
        ok = True
        for key in value:
            if key not in ("light", "dark"):
                error(where, f"a light/dark pair has only 'light' and 'dark', not {key!r}")
                ok = False
        for side in ("light", "dark"):
            if side not in value:
                error(where, f"a light/dark pair needs {side!r} too")
                ok = False
            elif not _check_theme_spec(value[side], f"{where}.{side}", error, warn):
                ok = False
    else:
        ok = _check_theme_spec(value, where, error, warn)
    if ok:
        try:
            resolve_theme_pair(value)
        except ValueError as e:
            error(where, str(e))
            return False
    return ok


def _check_theme_spec(value: Any, where: str, error: Report, warn: Report) -> bool:
    if isinstance(value, str):
        return _check_theme_name(value, where, error, warn)
    if not isinstance(value, dict):
        error(where, f"must be a theme name or a mapping of colors, got {_describe(value)}")
        return False
    schema = _DEFS["themeSpec"]["oneOf"][1]
    ok = True
    for key, item in value.items():
        if key not in schema["properties"]:
            error(where, _unknown_key(key, schema["properties"]))
            ok = False
        elif key == "base":
            ok = _check_theme_name(item, f"{where}.base", error, warn) and ok
        else:
            ok = _check_value(item, schema["properties"][key], f"{where}.{key}", error) and ok
    return ok


def _check_theme_name(value: Any, where: str, error: Report, warn: Report) -> bool:
    if value in THEME_NAMES:
        return True
    if isinstance(value, str) and _normalize_name(value) in THEME_NAMES:
        warn(where, f"write {_normalize_name(value)!r}; the schema only allows the exact name")
        return True
    choices = (
        ["auto", *THEME_NAMES] if not where.endswith((".light", ".dark", ".base")) else THEME_NAMES
    )
    error(where, _not_one_of(value, choices))
    return False


def _check_item_extras(
    section: str, item: dict[str, Any], where: str, error: Report, warn: Report
) -> bool:
    """Checks on one script entry beyond what the schema says."""
    ok = True
    if section in ("cuts", "speed_map"):
        if item["from"] > item["to"]:
            error(where, f"ends ({_t(item['to'])}) before it starts ({_t(item['from'])})")
            ok = False
        elif item["from"] == item["to"]:
            warn(where, "is empty (from and to are the same)")
    elif section == "highlights":
        target = item.get("target", {})
        pattern = target.get("match")
        if pattern is not None:
            ok = _check_regex(pattern, f"{where}.target.match", error, warn=warn)
            group = target.get("group", 0)
            if ok and group > re.compile(pattern).groups:
                error(
                    f"{where}.target.group",
                    f"the pattern has {_plural(re.compile(pattern).groups, 'group')}, "
                    f"so there's no group {group}",
                )
                ok = False
    elif section == "snippets":
        if "match" in item:
            ok = _check_regex(item["match"], f"{where}.match", error, warn=warn)
    return ok


def _check_regex(
    pattern: str, where: str, error: Report, *, js: bool = True, warn: Report | None = None
) -> bool:
    try:
        re.compile(pattern)
    except re.error as e:
        error(where, f"isn't a valid regular expression ({e})")
        return False
    problem = _python_only(pattern) if js and warn is not None else None
    if problem:
        warn(where, f"the player matches with JavaScript regular expressions: {problem}")
    return True


def _python_only(pattern: str) -> str | None:
    """Why the player's JavaScript `RegExp` would read `pattern` differently, if it would."""
    return next((message for check, message in _PYTHON_ONLY_REGEX if check.search(pattern)), None)


# ---------------------------------------------------------------------------
# A small JSON Schema reader
# ---------------------------------------------------------------------------
#
# Enough of JSON Schema for the keywords the termshow schemas use, with
# messages written for people rather than for schema authors. `settings.theme`
# (a `oneOf` of shapes) is checked by hand above.


def _check_value(
    value: Any, schema: dict[str, Any], where: str, error: Report, root: dict | None = None
) -> bool:
    root = root or _SCRIPT_SCHEMA
    label = ""
    while "$ref" in schema:
        label = schema["$ref"].rsplit("/", 1)[-1]
        rest = {k: v for k, v in schema.items() if k != "$ref"}
        schema = {**root["$defs"][label], **rest}

    # `oneOf` of differently typed shapes: check against the one of this type
    typed = [b for b in schema.get("oneOf", []) if "type" in b]
    if typed and len(typed) == len(schema["oneOf"]):
        branch = next((b for b in typed if _is_type(value, b["type"])), None)
        if branch is None:
            error(
                where, f"must be {_type_words([b['type'] for b in typed])}, got {_describe(value)}"
            )
            return False
        rest = {k: v for k, v in schema.items() if k != "oneOf"}
        return _check_value(value, {**rest, **branch}, where, error, root)

    types = schema.get("type")
    if types is not None:
        types = [types] if isinstance(types, str) else types
        if not any(_is_type(value, t) for t in types):
            error(where, f"must be {_type_words(types)}, got {_describe(value)}")
            return False

    if "const" in schema and value != schema["const"]:
        error(where, f"must be {json.dumps(schema['const'])}, got {_describe(value)}")
        return False
    if "enum" in schema and value not in schema["enum"]:
        error(where, _not_one_of(value, schema["enum"]))
        return False

    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            if schema["minimum"] == 0:
                error(where, f"can't be negative (got {value})")
            else:
                error(where, f"must be at least {schema['minimum']} (got {value})")
            return False
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            error(where, f"must be greater than {schema['exclusiveMinimum']} (got {value})")
            return False
        if "maximum" in schema and value > schema["maximum"]:
            error(where, f"can't be more than {schema['maximum']} (got {value})")
            return False

    if isinstance(value, str):
        if schema.get("minLength", 0) > len(value):
            error(where, "can't be empty")
            return False
        if "pattern" in schema and not re.search(schema["pattern"], value):
            if label == "hexColor":
                error(where, f"must be a hex color like '#1e1e2e', got {value!r}")
            elif label == "keyName":
                message = f"must be a key like 'enter', 'up', or 'ctrl+c', got {value!r}"
                if re.search(schema["pattern"], value.lower()):
                    message += f" (keys are written in lower case: {value.lower()!r})"
                error(where, message)
            else:
                error(where, f"doesn't have the expected form, got {value!r}")
            return False

    ok = True
    for branch in schema.get("allOf", []):
        ok = _check_value(value, branch, where, error, root) and ok
    # `then` applies when the value matches `if`, which is checked quietly
    if "then" in schema and _check_value(value, schema.get("if", {}), where, _quiet, root):
        ok = _check_value(value, schema["then"], where, error, root) and ok

    if isinstance(value, list):
        return _check_array(value, schema, where, error, root) and ok
    if isinstance(value, dict):
        return _check_object(value, schema, where, error, root) and ok
    return ok


def _quiet(where: str, message: str) -> None:
    pass


def _check_array(
    value: list[Any], schema: dict[str, Any], where: str, error: Report, root: dict
) -> bool:
    # `oneOf` of exact lengths, as for an 8- or 16-color palette
    lengths = [
        b["minItems"]
        for b in schema.get("oneOf", [])
        if "minItems" in b and b.get("maxItems") == b["minItems"]
    ]
    if lengths and len(value) not in lengths:
        allowed = " or ".join(str(n) for n in lengths)
        error(where, f"must have {allowed} entries, got {len(value)}")
        return False
    if len(value) < schema.get("minItems", 0):
        error(
            where,
            "can't be empty" if schema["minItems"] == 1 else f"needs {schema['minItems']}+ entries",
        )
        return False
    if "maxItems" in schema and len(value) > schema["maxItems"]:
        error(where, f"can have at most {schema['maxItems']} entries, got {len(value)}")
        return False
    ok = True
    # `prefixItems` gives the first entries' schemas, and `items` the rest
    prefix = schema.get("prefixItems", [])
    for i, (item, item_schema) in enumerate(zip(value, prefix)):
        ok = _check_value(item, item_schema, f"{where}[{i}]", error, root) and ok
    if "items" in schema:
        for i, item in enumerate(value[len(prefix) :], start=len(prefix)):
            ok = _check_value(item, schema["items"], f"{where}[{i}]", error, root) and ok
    return ok


def _check_object(
    value: dict[str, Any], schema: dict[str, Any], where: str, error: Report, root: dict
) -> bool:
    props = schema.get("properties", {})
    ok = True
    extra = schema.get("additionalProperties")
    if extra is False:
        for key in value:
            if key not in props:
                error(where, _unknown_key(key, props))
                ok = False
    elif isinstance(extra, dict):
        for key, item in value.items():
            if key not in props:
                ok = _check_value(item, extra, f"{where}.{key}", error, root) and ok
    for key in schema.get("required", []):
        if key not in value:
            error(where, f"missing {key!r}")
            ok = False
    for keyword in ("oneOf", "anyOf"):
        # Branches that only say which keys are required: "needs X or Y"
        branches = schema.get(keyword, [])
        if branches and all(set(b) == {"required"} for b in branches):
            choices = [b["required"][0] for b in branches]
            present = [k for k in choices if k in value]
            if not present:
                error(where, f"needs {_or(choices)}")
                ok = False
            elif keyword == "oneOf" and len(present) > 1:
                error(where, f"can't have both {present[0]!r} and {present[1]!r}")
                ok = False
    for key, item in value.items():
        if key in props:
            ok = (
                _check_value(item, props[key], f"{where}.{key}" if where else key, error, root)
                and ok
            )
    return ok


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_type(value: Any, name: str) -> bool:
    if name == "number":
        return _is_number(value)
    if name == "integer":
        return _is_number(value) and float(value).is_integer()
    return {
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "null": value is None,
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(name, True)


def _type_words(types: list[str]) -> str:
    words = {
        "number": "a number",
        "integer": "a whole number",
        "string": "a string",
        "boolean": "true or false",
        "null": "null",
        "array": "a list",
        "object": "a mapping",
    }
    return " or ".join(words.get(t, t) for t in types)


def _describe(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return "a list" if isinstance(value, list) else "a mapping"
    return repr(value)


def _short(value: Any, limit: int = 40) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _unknown_key(key: Any, known: Iterable[str]) -> str:
    message = f"unknown key {key!r}"
    close = difflib.get_close_matches(str(key), list(known), n=1)
    return f"{message} (did you mean {close[0]!r}?)" if close else message


def _not_one_of(value: Any, choices: list[Any]) -> str:
    message = f"must be one of {', '.join(map(str, choices))}; got {_describe(value)}"
    if isinstance(value, str):
        close = difflib.get_close_matches(value, [str(c) for c in choices], n=1)
        if close:
            message += f" (did you mean {close[0]!r}?)"
    return message


def _or(words: list[str]) -> str:
    quoted = [repr(w) for w in words]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " or " + quoted[-1]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _t(seconds: float) -> str:
    """A time for messages: `41s`, `11.67s`."""
    return f"{round(seconds, 2):g}s"


# ---------------------------------------------------------------------------
# The script: timing and screen content
# ---------------------------------------------------------------------------


def check_timeline(
    recording: Recording,
    data: dict[str, Any],
    name: str,
    problems: list[Problem] | None = None,
) -> list[Problem]:
    """Warn about script entries that are valid but won't work as meant.

    `data` is what `check_script_data()` returns: each section is a list of
    `(index, entry)` pairs, with None for entries that had errors.
    """
    problems = [] if problems is None else problems

    def warn(where: str, message: str) -> None:
        problems.append(Problem(name, where, message, WARNING))

    sections = {
        section: [entry for entry in data.get(section) or [] if entry is not None]
        for section in _SECTIONS
    }
    raw_end = recording.duration

    # Cuts and speed segments, on the recording's own timeline
    for section in ("cuts", "speed_map"):
        spans = sorted(sections[section], key=lambda e: (e[1]["from"], e[0]))
        for i, item in spans:
            if item["from"] >= raw_end and raw_end > 0:
                warn(
                    f"{section}[{i}]",
                    f"starts at {_t(item['from'])}, after the end of the recording ({_t(raw_end)})",
                )
            if section == "cuts" and item["from"] <= 0 and item["to"] >= raw_end:
                warn(f"cuts[{i}]", "cuts the whole recording")
        for (i, a), (j, b) in zip(spans, spans[1:]):
            if b["from"] < a["to"]:
                kind = "cut" if section == "cuts" else "speed segment"
                warn(
                    f"{section}[{j}]",
                    f"overlaps {section}[{i}] ({_t(a['from'])}–{_t(a['to'])}); "
                    f"each moment can only be in one {kind}",
                )

    script = _script_from(data)
    played = apply_script(recording, script) if script is not None else recording
    end = played.duration

    _check_idle(recording, sections, script, warn)

    # Chapters
    previous: tuple[int, dict] | None = None
    labels: dict[str, int] = {}
    for i, ch in sections["chapters"]:
        if ch["at"] > end:
            warn(f"chapters[{i}]", f"at {_t(ch['at'])}, after the end of the recording ({_t(end)})")
        if previous is not None and ch["at"] < previous[1]["at"]:
            warn(
                f"chapters[{i}]",
                f"at {_t(ch['at'])}, before chapters[{previous[0]}] ({_t(previous[1]['at'])}); "
                "list chapters in time order",
            )
        elif previous is not None and ch["at"] == previous[1]["at"]:
            warn(f"chapters[{i}]", f"at the same time as chapters[{previous[0]}]")
        label = ch.get("label", "")
        if not label:
            warn(f"chapters[{i}]", "has no label")
        elif label in labels:
            warn(f"chapters[{i}]", f"has the same label as chapters[{labels[label]}] ({label!r})")
        else:
            labels[label] = i
        previous = (i, ch)

    # Annotations, highlights, and snippets: each shows for a stretch of playback
    defaults = {"annotations": 3.0, "highlights": 2.0, "snippets": 5.0}
    windows: dict[str, list[tuple[int, dict, float, float]]] = {}
    for section, default in defaults.items():
        windows[section] = []
        for i, item in sections[section]:
            start = item["at"]
            stop = start + item.get("duration", default)
            windows[section].append((i, item, start, stop))
            if start >= end and end > 0:
                warn(
                    f"{section}[{i}]",
                    f"starts at {_t(start)}, after the end of the recording ({_t(end)})",
                )
            elif stop == start:
                warn(f"{section}[{i}]", "has a duration of 0, so it never shows")
            if section == "annotations" and not str(item.get("text", "")).strip():
                warn(f"annotations[{i}]", "has no text")

    for (i, a, a0, a1), (j, b, b0, b1) in _overlapping(windows["annotations"]):
        pos = a.get("position", "bottom-right")
        if pos == b.get("position", "bottom-right"):
            warn(
                f"annotations[{j}]",
                f"covers annotations[{i}] ({pos}, {_t(max(a0, b0))}–{_t(min(a1, b1))}); "
                "move one or change its position",
            )
    for (i, _, a0, a1), (j, _, b0, b1) in _overlapping(windows["snippets"]):
        warn(
            f"snippets[{j}]",
            f"overlaps snippets[{i}] ({_t(max(a0, b0))}–{_t(min(a1, b1))}); "
            "only one copy button shows at a time, and the first listed wins",
        )

    _check_screen(played, script, windows, recording, warn)
    return problems


def _script_from(data: dict[str, Any]) -> Script | None:
    """A `Script` built from the entries that passed the structural checks."""
    if not data:
        return None
    plain: dict[str, Any] = {k: v for k, v in data.items() if k not in _SECTIONS}
    for section in _SECTIONS:
        if section in data:
            plain[section] = [entry[1] for entry in data[section] or [] if entry is not None]
    try:
        return _parse_script_data(plain)
    except (ValueError, TypeError):  # pragma: no cover - already reported
        return None


def _overlapping(windows: list[tuple[int, dict, float, float]]):
    """Pairs of entries whose stretches overlap, the earlier-listed one first."""
    for n, a in enumerate(windows):
        for b in windows[n + 1 :]:
            if a[2] < b[3] and b[2] < a[3] and a[3] > a[2] and b[3] > b[2]:
                yield a, b


def _check_idle(
    recording: Recording, sections: dict[str, list], script: Script | None, warn: Report
) -> None:
    """Long stretches with no output that no cut or speed segment touches."""
    speed = script.speed if script else 1.0
    covered = [(e["from"], e["to"]) for _, e in sections["cuts"] + sections["speed_map"]]
    times = [ev.time for ev in recording.events if ev.code == "o"]
    for a, b in zip(times, times[1:]):
        gap = (b - a) / speed
        if gap > IDLE_WARNING_SECONDS and not any(s < b and a < e for s, e in covered):
            warn(
                "",
                f"nothing happens for {gap:.1f}s from {_t(a)} in the recording; "
                f"a cut (from: {round(a + 0.5, 2):g}, to: {round(b - 0.5, 2):g}) would tighten it",
            )


def _check_screen(
    played: Recording,
    script: Script | None,
    windows: dict[str, list[tuple[int, dict, float, float]]],
    recording: Recording,
    warn: Report,
) -> None:
    """Highlights and snippets that point at text or cells that aren't there."""
    rows, cols = recording.term.rows, recording.term.cols
    needs_screen = False
    for i, hl, _, _ in windows["highlights"]:
        target = hl.get("target") or {"region": hl.get("region")}
        where = f"highlights[{i}].target" if "target" in hl else f"highlights[{i}].region"
        region = target.get("region")
        if region:
            if region["row"] + region["height"] > rows or region["col"] + region["width"] > cols:
                warn(where, f"reaches outside the {cols}x{rows} terminal")
        for line in target.get("lines") or []:
            if line >= rows:
                warn(where, f"line {line} is below the bottom of the {rows}-row terminal")
                break
        needs_screen = needs_screen or "match" in target
    needs_screen = needs_screen or any("match" in s for _, s, _, _ in windows["snippets"])
    if not needs_screen or not played.events:
        return

    manifest = generate_manifest(played, script)
    for i, hl, start, stop in windows["highlights"]:
        target = hl.get("target") or {}
        if "match" not in target or stop <= start or _python_only(target["match"]):
            continue
        pattern = re.compile(target["match"])
        group = target.get("group", 0)
        if not any(
            _row_match(pattern, group, row)
            for frame in _frames_between(manifest, start, stop)
            for row in _frame_rows(manifest, frame)
        ):
            warn(
                f"highlights[{i}].target.match",
                f"'{target['match']}' isn't on screen between {_t(start)} and {_t(stop)}",
            )
    for i, snip, start, stop in windows["snippets"]:
        if "match" not in snip or stop <= start or _python_only(snip["match"]):
            continue
        pattern = re.compile(snip["match"])
        if not any(
            pattern.search(_frame_text(manifest, frame))
            for frame in _frames_between(manifest, start, stop)
        ):
            fallback = " (the copy button falls back to 'text')" if snip.get("text") else ""
            warn(
                f"snippets[{i}].match",
                f"'{snip['match']}' isn't on screen between {_t(start)} and {_t(stop)}{fallback}",
            )


def _frames_between(manifest: Manifest, start: float, stop: float) -> list[int]:
    """The screens shown between two playback times."""
    frames: list[int] = []
    current = None
    for kf in manifest.keyframes:
        if kf.frame is None:
            continue
        if kf.time <= start + 1e-9:
            current = kf.frame
        elif kf.time <= stop:
            frames.append(kf.frame)
    if current is not None:
        frames.insert(0, current)
    return list(dict.fromkeys(frames))


def _frame_rows(manifest: Manifest, frame: int) -> list[str]:
    """Each row's text, with spans at their columns and gaps filled with spaces.

    Built the way the player's `frameRows()` does, for `target.match`.
    """
    out = []
    for line_id in manifest.frames[frame].lines:
        cells: dict[int, str] = {}
        for col, text, *_ in manifest.lines[line_id][1]:
            for k, ch in enumerate(text):
                cells[col + k] = ch
        width = max(cells) + 1 if cells else 0
        out.append("".join(cells.get(c, " ") for c in range(width)))
    return out


def _frame_text(manifest: Manifest, frame: int) -> str:
    """The screen's text as the player reads it for a snippet's `match`.

    Like the player's `extractSvgText()`: rows without text are left out, and
    each row is its spans joined in column order.
    """
    rows = []
    for line_id in manifest.frames[frame].lines:
        spans = sorted(manifest.lines[line_id][1], key=lambda s: s[0])
        if spans:
            rows.append("".join(s[1] for s in spans))
    return "\n".join(rows)


def _row_match(pattern: re.Pattern[str], group: int, row: str) -> bool:
    m = pattern.search(row)
    return bool(m and m.group(group))
