"""Convert VHS `.tape` files into Termshow scripts with `record:` and `steps:`.

Each tape command becomes a step, a `record` setting, or a render setting. Commands that have no
Termshow equivalent, such as `Output` or `Set FontSize`, are listed with their line numbers
instead of being dropped without a word.

VHS runs the shell with a `> ` prompt, and a bare `Wait` waits for it. The converted script sets
the same prompt, so the tape's waits still work, and `Type` + `Enter` + `Wait` becomes `run`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .steps import key_sequence

# VHS's prompt, and the pattern its bare `Wait` uses (adjusted for the trailing space, which
# Termshow keeps on the cursor's line)
VHS_PROMPT = "> "
VHS_PROMPT_PATTERN = "> $"

# VHS key commands and the Termshow key names they become
KEYS = {
    "Backspace": "backspace",
    "Delete": "delete",
    "Down": "down",
    "End": "end",
    "Enter": "enter",
    "Escape": "escape",
    "Home": "home",
    "Left": "left",
    "PageDown": "pagedown",
    "PageUp": "pageup",
    "Right": "right",
    "Space": "space",
    "Tab": "tab",
    "Up": "up",
}

# Shells started without their startup files, as VHS does, so the prompt is the one it sets
SHELLS = {
    "bash": "bash --noprofile --norc",
    "zsh": "zsh -f",
    "fish": "fish --no-config",
}
DEFAULT_SHELL = SHELLS["bash"]  # VHS's default

_WINDOW_BARS = {
    "colorful": "colorful",
    "colorfulright": "colorful",
    "rings": "minimal",
    "ringsright": "minimal",
}

# `Set` options that only change how VHS draws the video, and why they're not converted
_RENDER_ONLY = {
    "Width": "VHS sizes the terminal in pixels; set `record.cols` instead",
    "Height": "VHS sizes the terminal in pixels; set `record.rows` instead",
    "FontSize": "the player scales with the page",
    "LetterSpacing": "no equivalent",
    "Padding": "no equivalent",
    "Margin": "no equivalent",
    "MarginFill": "no equivalent",
    "BorderRadius": "no equivalent",
    "Framerate": "the player draws frames as they're needed",
    "LoopOffset": "no equivalent",
    "CursorBlink": "no equivalent",
}

_PALETTE_KEYS = ["black", "red", "green", "yellow", "blue", "purple", "cyan", "white"]

_COMMAND = re.compile(r"(?P<name>[A-Za-z]+)(?:\+(?P<scope>[A-Za-z]+))?(?:@(?P<time>\S+))?")
_TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|`([^`]*)`|/((?:\\.|[^/\\])*)/|(\S+)')
_DURATION = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m)?")


class TapeError(Exception):
    """A tape line that can't be read."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


@dataclass
class Skipped:
    """A tape command with no Termshow equivalent."""

    line: int
    text: str
    reason: str


@dataclass
class Token:
    kind: str  # "string", "regex", or "word"
    value: str


@dataclass
class TapeScript:
    """A converted tape: the sections of a `.termshow.yml` script."""

    settings: dict[str, Any] = field(default_factory=dict)
    record: dict[str, Any] = field(default_factory=dict)
    steps: list[Any] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)

    def to_yaml(self, source_name: str = "", script_name: str = "") -> str:
        """The script's text, with a comment listing what wasn't converted."""
        lines = []
        if source_name:
            lines.append(f"# Converted from {source_name} by `great-docs termshow import-tape`.")
        if script_name:
            lines.append(f"# Record it with: great-docs termshow record --steps {script_name}")
        if self.skipped:
            lines += ["#", "# Not converted:"] if lines else ["# Not converted:"]
            lines += [f"#   line {s.line}: {s.text} ({s.reason})" for s in self.skipped]
        if lines:
            lines.append("")
        if self.settings:
            lines += ["settings:", *_mapping(self.settings, 1), ""]
        lines += ["record:", *_mapping(self.record, 1), ""]
        lines.append("steps:")
        for step in self.steps:
            if isinstance(step, str):
                lines.append(f"  - {step}")
                continue
            first, *rest = _mapping(step, 2)
            lines.append(f"  - {first.lstrip()}")
            lines += rest
        return "\n".join(lines) + "\n"


def convert_tape(path: str | Path) -> TapeScript:
    """Convert a `.tape` file. See `parse_tape()`."""
    return parse_tape(Path(path).read_text(encoding="utf-8"))


def parse_tape(text: str) -> TapeScript:
    """Convert the text of a VHS tape into a Termshow script.

    Raises
    ------
    TapeError
        If a line can't be read, such as a `Type` with no string or a `Sleep` without a time.
    """
    converter = _Converter()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            converter.line(number, line)
    return converter.finish()


class _Converter:
    def __init__(self) -> None:
        self.script = TapeScript()
        self.shell = DEFAULT_SHELL
        self.env: dict[str, str] = {"PS1": VHS_PROMPT}
        self.wait_pattern: str | None = None
        self.copied: str | None = None
        self.number = 0
        self.text = ""

    def skip(self, reason: str) -> None:
        self.script.skipped.append(Skipped(self.number, self.text, reason))

    def error(self, message: str) -> TapeError:
        return TapeError(self.number, message)

    def line(self, number: int, text: str) -> None:
        self.number, self.text = number, text
        word, _, rest = text.partition(" ")
        rest = rest.strip()

        if re.fullmatch(r"(?:Ctrl|Alt|Shift)\+.+", word):
            return self.combo(word)
        match = _COMMAND.fullmatch(word)
        if not match:
            return self.skip("not a command Termshow knows")
        name, scope, at = match["name"], match["scope"], match["time"]

        if name in KEYS and not scope:
            return self.key(name, at, rest)
        if scope and name != "Wait":
            raise self.error(f"{name} doesn't take +{scope}")
        if at and name not in ("Type", "Wait"):
            raise self.error(f"{name} doesn't take @{at}")

        handler = getattr(self, f"cmd_{name.lower()}", None)
        if handler is None:
            return self.skip("not a command Termshow knows")
        if name == "Wait":
            return handler(scope, at, rest)
        if name == "Type":
            return handler(at, rest)
        return handler(rest)

    # Steps ------------------------------------------------------------------------------------

    def cmd_type(self, at: str | None, rest: str) -> None:
        strings = [t.value for t in _tokens(rest) if t.kind == "string"]
        if not strings:
            raise self.error('Type needs a string in quotes, like Type "ls -l"')
        step: dict[str, Any] = {"type": "".join(strings)}
        if at:
            step["delay"] = self.duration(at)
        self.script.steps.append(step)

    def key(self, name: str, at: str | None, rest: str) -> None:
        count = self.count(rest)
        key = KEYS[name]
        if key == "enter" and count == 1 and not at:
            self.script.steps.append("enter")
            return
        step: dict[str, Any] = {"key": key}
        if count != 1:
            step["count"] = count
        if at:
            step["delay"] = self.duration(at)
        self.script.steps.append(step)

    def combo(self, word: str) -> None:
        *modifiers, key = word.split("+")
        name = f"{modifiers[0].lower()}+{key.lower()}" if len(modifiers) == 1 else ""
        if len(key) == 1 and key.isalpha() and key_sequence(name):
            self.script.steps.append({"key": name})
        else:
            self.skip("Termshow only presses Ctrl or Alt with a letter")

    def cmd_sleep(self, rest: str) -> None:
        if not rest:
            raise self.error("Sleep needs a time, like Sleep 500ms or Sleep 2s")
        self.script.steps.append({"sleep": self.duration(rest)})

    def cmd_wait(self, scope: str | None, at: str | None, rest: str) -> None:
        if scope not in (None, "Screen", "Line"):
            raise self.error(f"Wait+{scope} should be Wait+Screen or Wait+Line")
        regexes = [t.value for t in _tokens(rest) if t.kind == "regex"]
        if rest and not regexes:
            raise self.error("Wait takes a pattern between slashes, like Wait /done/")
        pattern = regexes[0] if regexes else (self.wait_pattern or VHS_PROMPT_PATTERN)
        timeout = self.duration(at) if at else None
        steps = self.script.steps

        # `Type` + `Enter` + a bare `Wait` for the prompt is what `run` does
        if (
            not regexes
            and self.wait_pattern is None
            and scope != "Screen"
            and len(steps) >= 2
            and isinstance(steps[-2], dict)
            and set(steps[-2]) <= {"type", "delay"}
            and steps[-1] == "enter"
        ):
            typed = steps[-2]
            step: dict[str, Any] = {"run": typed["type"]}
            if "delay" in typed:
                step["delay"] = typed["delay"]
            if timeout is not None:
                step["timeout"] = timeout
            steps[-2:] = [step]
            return

        step = {"wait_for": pattern}
        if scope == "Screen":
            step["screen"] = True
        if timeout is not None:
            step["timeout"] = timeout
        steps.append(step)

    def cmd_hide(self, rest: str) -> None:
        self.script.steps.append("hide")

    def cmd_show(self, rest: str) -> None:
        self.script.steps.append("show")

    def cmd_copy(self, rest: str) -> None:
        strings = [t.value for t in _tokens(rest) if t.kind == "string"]
        if not strings:
            raise self.error('Copy needs a string in quotes, like Copy "text"')
        self.copied = "".join(strings)

    def cmd_paste(self, rest: str) -> None:
        if self.copied is None:
            self.skip("nothing was copied before it")
        else:
            # Pasting types what was copied
            self.script.steps.append({"type": self.copied})

    # The session ------------------------------------------------------------------------------

    def cmd_env(self, rest: str) -> None:
        tokens = _tokens(rest)
        if len(tokens) != 2 or tokens[0].kind != "word":
            raise self.error('Env needs a name and a value, like Env NAME "value"')
        self.env[tokens[0].value] = tokens[1].value

    def cmd_set(self, rest: str) -> None:
        option, _, value = rest.partition(" ")
        value = value.strip()
        if not option or not value:
            raise self.error("Set needs an option and a value, like Set Shell bash")
        tokens = _tokens(value)
        plain = tokens[0].value if len(tokens) == 1 else value
        record, settings = self.script.record, self.script.settings

        if option == "Shell":
            self.shell = SHELLS.get(plain, plain)
        elif option == "TypingSpeed":
            record["typing_delay"] = self.duration(plain)
        elif option == "WaitTimeout":
            record["timeout"] = self.duration(plain)
        elif option == "WaitPattern":
            self.wait_pattern = plain
        elif option == "Theme":
            self.theme(value, plain)
        elif option == "WindowBar":
            bar = _WINDOW_BARS.get(plain.lower())
            if bar:
                settings["window_chrome"] = bar
            else:
                self.skip("not a window bar Termshow has")
        elif option == "LineHeight":
            settings["line_height"] = self.number_value(plain)
        elif option == "FontFamily":
            settings["font_family"] = plain
        elif option == "PlaybackSpeed":
            settings["speed"] = self.number_value(plain)
        elif option in _RENDER_ONLY:
            self.skip(_RENDER_ONLY[option])
        else:
            self.skip("not a setting Termshow knows")

    def theme(self, value: str, name: str) -> None:
        from .themes import theme_names

        if value.startswith("{"):
            return self.theme_colors(value)
        squashed = re.sub(r"[\s_-]+", "", name.lower())
        for known in theme_names():
            if known.replace("-", "") == squashed:
                self.script.settings["theme"] = known
                return
        self.skip("not one of Termshow's themes; see `settings.theme` for the list")

    def theme_colors(self, value: str) -> None:
        try:
            colors = json.loads(value)
        except ValueError:
            raise self.error("Set Theme with braces needs a JSON object") from None
        colors = {k.lower(): v for k, v in colors.items()} if isinstance(colors, dict) else {}
        colors.setdefault("purple", colors.get("magenta"))
        colors.setdefault("brightpurple", colors.get("brightmagenta"))
        names = _PALETTE_KEYS + ["bright" + k for k in _PALETTE_KEYS]
        palette = [colors.get(k) for k in names]
        hex_color = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")
        wanted = [*palette, colors.get("foreground"), colors.get("background")]
        if not all(isinstance(c, str) and hex_color.fullmatch(c) for c in wanted):
            return self.skip("a theme needs 16 colors plus foreground and background, as #rrggbb")
        theme = {"fg": colors["foreground"], "bg": colors["background"]}
        if isinstance(colors.get("cursor"), str) and hex_color.fullmatch(colors["cursor"]):
            theme["cursor"] = colors["cursor"]
        theme["palette"] = palette
        self.script.settings["theme"] = theme

    # Commands with no equivalent --------------------------------------------------------------

    def cmd_output(self, rest: str) -> None:
        self.skip("the recording is saved next to the script; `termshow export` makes an SVG")

    def cmd_require(self, rest: str) -> None:
        self.skip("not checked; the step that uses it fails if it's missing")

    def cmd_source(self, rest: str) -> None:
        self.skip("convert that tape too and copy its steps in")

    def cmd_screenshot(self, rest: str) -> None:
        self.skip("no equivalent")

    # Values -----------------------------------------------------------------------------------

    def duration(self, text: str) -> float:
        match = _DURATION.fullmatch(text)
        if not match:
            raise self.error(f"{text!r} isn't a time, like 500ms, 2s, or 1.5")
        value = float(match[1]) * {"ms": 0.001, "s": 1, "m": 60, None: 1}[match[2]]
        return round(value, 3)

    def count(self, text: str) -> int:
        if not text:
            return 1
        if not text.isdigit() or int(text) < 1:
            raise self.error(f"{text!r} isn't a number of times to press the key")
        return int(text)

    def number_value(self, text: str) -> float:
        try:
            return float(text)
        except ValueError:
            raise self.error(f"{text!r} isn't a number") from None

    def finish(self) -> TapeScript:
        record = self.script.record
        settings = {"shell": self.shell, "env": self.env, "prompt_pattern": VHS_PROMPT_PATTERN}
        self.script.record = {**settings, **record}
        return self.script


def _tokens(text: str) -> list[Token]:
    tokens = []
    for match in _TOKEN.finditer(text):
        string = next((g for g in match.groups()[:3] if g is not None), None)
        if string is not None:
            tokens.append(Token("string", string))
        elif match[4] is not None:
            tokens.append(Token("regex", match[4]))
        else:
            tokens.append(Token("word", match[5]))
    return tokens


# YAML ---------------------------------------------------------------------------------------

_PLAIN = re.compile(r"[A-Za-z_][\w./=+,-]*(?: [\w./=+,-]+)*")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "y", "n", "~"}


def _scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    text = str(value)
    if _PLAIN.fullmatch(text) and text.lower() not in _RESERVED:
        return text
    if any(ch < " " or ch == "\x7f" for ch in text):
        return json.dumps(text, ensure_ascii=False)
    return "'" + text.replace("'", "''") + "'"


def _mapping(data: dict[str, Any], depth: int) -> list[str]:
    indent = "  " * depth
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{indent}{key}:")
            lines += _mapping(value, depth + 1)
        elif isinstance(value, list):
            lines.append(f"{indent}{key}: [{', '.join(_scalar(v) for v in value)}]")
        else:
            lines.append(f"{indent}{key}: {_scalar(value)}")
    return lines
