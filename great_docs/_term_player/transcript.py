"""Transcripts: a recording's text, for screen readers, search, and Markdown pages.

The session is replayed through the emulator, keeping every line that scrolls
off the top or is cleared away, so the transcript holds everything the player
shows, as plain text without colors or escape codes. A full-screen program
(one that switches to the terminal's alternate screen, like `less` or `vim`)
keeps only its last screen.

A script's chapters split the text into sections, its annotations become notes
where they show, and its prompt replacement is applied. Cuts and speed changes
only change timing, so the text is the same with or without them.

Captions are written as WebVTT: the annotations as caption cues, or the
chapters as a chapters track, on the playback timeline.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from .emulator import Cell, ScreenState, TerminalEmulator
from .manifest import (
    _PROMPT_CHARS,
    _apply_prompt_pattern_substitution,
    _apply_prompt_substitution,
    _detect_prompt_prefix,
)
from .parser import Recording
from .script import Script, apply_script

Row = list[Cell]


@dataclass
class _Item:
    """Something placed between the lines: a chapter label, a note, or a full screen."""

    kind: str  # "chapter", "note", or "screen"
    line: int  # it goes just before this line of the transcript
    text: str = ""
    rows: list[Row] = field(default_factory=list)


class _TranscriptEmulator(TerminalEmulator):
    """An emulator that keeps the lines the screen loses.

    Lines are numbered from the start of the session: a line that scrolls off the top keeps its
    number, and the screen's top row is always line `len(self.history)`.

    Items go on the cursor's line, or below it when the cursor has moved back up to redraw text
    in place, as menus and progress bars do: an item never splits text that was already shown.
    """

    def __init__(self, cols: int, rows: int) -> None:
        super().__init__(cols, rows)
        self.history: list[Row] = []
        self.items: list[_Item] = []
        self._full_screen: _Item | None = None
        self._furthest = 0  # the furthest line the cursor has reached

    def cursor_line(self) -> int:
        return len(self.history) + self._cursor_row

    def add(self, kind: str, text: str) -> None:
        # While a full-screen program runs, everything goes after its screen
        if self._full_screen:
            line = self._full_screen.line
        else:
            line = max(self.cursor_line(), self._furthest)
        self.items.append(_Item(kind, line, text))

    def main_rows(self) -> list[Row]:
        """The main screen's rows, down to the last one with text."""
        rows = self._alt_screen if self._using_alt and self._alt_screen else self._screen
        return _trim(rows)

    def finish(self) -> None:
        """Keep the last screen of a full-screen program that's still running."""
        if self._using_alt:
            self._keep_full_screen()

    # Keeping lines ----------------------------------------------------------------------------

    def feed(self, data: str) -> None:
        super().feed(data)
        if self._using_alt:
            self._keep_full_screen()
        else:
            self._furthest = max(self._furthest, self.cursor_line())

    def _scroll_up(self, n: int) -> None:
        if self._scroll_top != 0 or self._using_alt:
            super()._scroll_up(n)
            return
        for _ in range(n):
            self.history.append(self._screen[0])
            super()._scroll_up(1)

    def _erase_display(self, mode: int) -> None:
        clears = mode in (2, 3) or (mode == 0 and self._cursor_row == self._cursor_col == 0)
        if clears and self._using_alt:
            self._keep_full_screen()
        elif clears:
            self._push_screen()
        super()._erase_display(mode)

    def _push_screen(self) -> None:
        """Move the screen's text into the history before it's cleared."""
        kept = len(self.history) + len(_trim(self._screen))
        self.history.extend(list(row) for row in _trim(self._screen))
        # Whatever was placed on a blank row now goes before the next screen's first line
        for item in self.items:
            item.line = min(item.line, kept)
        self._furthest = min(self._furthest, kept)

    def _handle_dec_mode(self, params: list[int], *, set_mode: bool) -> None:
        for p in params:
            if p in (47, 1047, 1049):
                if set_mode and not self._using_alt:
                    line = max(self.cursor_line(), self._furthest)
                    self._full_screen = _Item("screen", line)
                    self.items.append(self._full_screen)
                elif not set_mode and self._using_alt:
                    self._keep_full_screen()
                    self._full_screen = None
            super()._handle_dec_mode([p], set_mode=set_mode)

    def _keep_full_screen(self) -> None:
        rows = _trim(self._screen)
        if rows and self._full_screen is not None:
            self._full_screen.rows = [list(row) for row in rows]


def _trim(rows: list[Row]) -> list[Row]:
    """The rows down to the last one with text."""
    end = len(rows)
    while end and not _text(rows[end - 1]):
        end -= 1
    return rows[:end]


def _text(row: Row) -> str:
    return "".join(c.char for c in row).rstrip()


def _substitute_prompts(rows: list[Row], recording: Recording, script: Script) -> list[str]:
    """The rows as text, with the script's prompt replacement applied."""
    width = max((len(r) for r in rows), default=0)
    if not script.prompt or not width:
        return [_text(r) for r in rows]
    state = ScreenState(
        cols=width,
        rows=len(rows),
        cells=[list(r) + [Cell() for _ in range(width - len(r))] for r in rows],
    )
    prefix = _detect_prompt_prefix(recording)
    if prefix:
        state = _apply_prompt_substitution(state, prefix, script.prompt, script.prompt_pattern)
    elif script.prompt_pattern:
        state = _apply_prompt_pattern_substitution(state, script.prompt_pattern, script.prompt)
    return [_text(r) for r in state.cells]


def _is_bare_prompt(line: str, recording: Recording) -> bool:
    prefix = (_detect_prompt_prefix(recording) or "").rstrip()
    return bool(line) and (line == prefix or line in _PROMPT_CHARS)


def _blocks(recording: Recording, script: Script | None) -> list[tuple[str, object]]:
    """The transcript as a list of `("chapter", label)`, `("note", text)` and
    `("code", lines)` blocks, in order."""
    script = script or Script()
    played = apply_script(recording, script)
    emu = _TranscriptEmulator(recording.term.cols, recording.term.rows)

    def due(time: float, event_time: float, *, before: bool) -> bool:
        # Chapters start before the output at their time; notes show after it
        t, e = round(time, 3), round(event_time, 3)
        return t <= e if before else t < e

    chapters = sorted(script.chapters, key=lambda c: c.time)
    notes = sorted(script.annotations, key=lambda a: a.time)
    for event in played.events:
        while chapters and due(chapters[0].time, event.time, before=True):
            emu.add("chapter", chapters.pop(0).label)
        while notes and due(notes[0].time, event.time, before=False):
            emu.add("note", notes.pop(0).text)
        if event.code == "o":
            emu.feed(event.data)
        elif event.code == "r":
            cols, _, rows = event.data.partition("x")
            if cols.isdigit() and rows.isdigit():
                emu.resize(int(cols), int(rows))
        elif event.code == "m" and not script.chapters:
            emu.add("chapter", event.data)
    for chapter in chapters:
        emu.add("chapter", chapter.label)
    for note in notes:
        emu.add("note", note.text)
    emu.finish()

    rows = emu.history + emu.main_rows()
    lines = _substitute_prompts(rows, recording, script)
    # Leave out the idle prompt the session ends on
    if lines and emu.cursor_line() == len(lines) - 1 and _is_bare_prompt(lines[-1], recording):
        lines.pop()

    blocks: list[tuple[str, object]] = []
    code: list[str] = []

    def end_code() -> None:
        # Leave out blank lines at the edges, and blocks with no text at all
        while code and not code[-1]:
            code.pop()
        start = next((i for i, line in enumerate(code) if line), len(code))
        if code[start:]:
            blocks.append(("code", code[start:]))
        code.clear()

    # `sorted` is stable, so items at the same line stay in the order they happened
    items = sorted(emu.items, key=lambda item: item.line)
    n = 0
    for i, line in enumerate(lines + [None]):
        while n < len(items) and (items[n].line <= i or line is None):
            item = items[n]
            n += 1
            if item.kind == "screen":
                if item.rows:
                    end_code()
                    code.extend(_text(r) for r in item.rows)
                    end_code()
            elif item.text.strip():
                end_code()
                blocks.append((item.kind, item.text.strip()))
        if line is not None:
            code.append(line)
    end_code()
    return blocks


def transcript_markdown(recording: Recording, script: Script | None = None) -> str:
    """The text of a recording, as Markdown.

    Parameters
    ----------
    recording
        The recording, on its own timeline.
    script
        A script whose chapters, annotations and prompt replacement are applied. Its chapters
        replace the recording's markers, as they do in the player.

    Returns
    -------
    str
        Each chapter's label in bold, the terminal text in fenced `console` blocks, and each
        annotation as a block quote. Empty when the recording shows no text.
    """
    parts = []
    for kind, value in _blocks(recording, script):
        if kind == "chapter":
            parts.append(f"**{_escape_md(value)}**")
        elif kind == "note":
            parts.append("\n".join(f"> {_escape_md(line)}".rstrip() for line in value.split("\n")))
        else:
            text = "\n".join(value)
            fence = "`" * max(3, _longest_backtick_run(text) + 1)
            parts.append(f"{fence}console\n{text}\n{fence}")
    return "\n\n".join(parts) + "\n" if parts else ""


# The name starts with "_" so Quarto doesn't render it as a page of the site
TRANSCRIPT_FILE = "_transcript.md"


def write_transcript(recording: Recording, script: Script | None, output_dir: str | Path) -> bool:
    """Write the transcript next to a rendered recording's manifest, as `_transcript.md`.

    The Termshow shortcode embeds it after the player, hidden from view but read by screen
    readers, and the page's Markdown version shows it. The file is removed instead when the
    recording shows no text.

    Returns
    -------
    bool
        Whether the file was written.
    """
    path = Path(output_dir) / TRANSCRIPT_FILE
    text = transcript_markdown(recording, script)
    if text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return bool(text)


_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>])")


def _escape_md(text: str) -> str:
    """Show Markdown's special characters as themselves."""
    return re.sub(r"^#", r"\#", _MD_SPECIAL.sub(r"\\\1", text))


def _longest_backtick_run(text: str) -> int:
    return max((len(m) for m in re.findall(r"`+", text)), default=0)


# ---------------------------------------------------------------------------
# WebVTT
# ---------------------------------------------------------------------------


def transcript_vtt(
    recording: Recording, script: Script | None = None, *, chapters: bool = False
) -> str:
    """Captions for a recording, as WebVTT.

    Parameters
    ----------
    recording
        The recording, on its own timeline.
    script
        The script whose annotations (or chapters) become cues. Its cuts and speed changes set
        the length of the playback timeline.
    chapters
        Write a chapters track instead: one cue per chapter, lasting until the next one (or the
        end). The chapters are the script's, or else the recording's markers.

    Returns
    -------
    str
        The WebVTT file's text. It has no cues when there's nothing to caption.
    """
    script = script or Script()
    played = apply_script(recording, script)
    if chapters:
        marks = [(c.time, c.label) for c in script.chapters] or [
            (e.time, e.data) for e in played.events if e.code == "m"
        ]
        marks.sort(key=lambda m: m[0])
        ends = [m[0] for m in marks[1:]] + [played.duration]
        cues = [(start, end, label) for (start, label), end in zip(marks, ends)]
    else:
        cues = [
            (a.time, a.time + a.duration, a.text)
            for a in sorted(script.annotations, key=lambda a: a.time)
        ]

    out = ["WEBVTT", ""]
    number = 0
    for start, end, text in cues:
        # A blank line would end the cue early
        lines = [html.escape(line.strip(), quote=False) for line in text.split("\n")]
        lines = [line for line in lines if line]
        if end <= start or not lines:
            continue
        number += 1
        out += [str(number), f"{_vtt_time(start)} --> {_vtt_time(end)}", *lines, ""]
    return "\n".join(out)


def _vtt_time(seconds: float) -> str:
    ms = round(max(seconds, 0.0) * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
