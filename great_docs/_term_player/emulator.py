"""Lightweight virtual terminal emulator for rendering terminal recordings.

Processes ANSI escape sequences and maintains a screen buffer that can be
snapshotted for SVG rendering. Handles:
- Cursor movement (CUP, CUU, CUD, CUF, CUB, etc.)
- SGR attributes (colors, bold, italic, underline, inverse)
- Screen operations (ED, EL, scroll)
- 256-color and truecolor (24-bit) SGR
- Alternative screen buffer
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class CellStyle:
    """Visual attributes for a single terminal cell."""

    fg: str | None = None  # Foreground color (hex or index)
    bg: str | None = None  # Background color (hex or index)
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    inverse: bool = False
    dim: bool = False

    def copy(self) -> CellStyle:
        return CellStyle(
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            strikethrough=self.strikethrough,
            inverse=self.inverse,
            dim=self.dim,
        )


@dataclass(slots=True)
class Cell:
    """A single character cell in the terminal grid."""

    char: str = " "
    style: CellStyle = field(default_factory=CellStyle)

    def copy(self) -> Cell:
        return Cell(char=self.char, style=self.style.copy())


@dataclass
class ScreenState:
    """Snapshot of the terminal screen at a point in time."""

    cols: int
    rows: int
    cells: list[list[Cell]]  # [row][col]
    cursor_row: int = 0
    cursor_col: int = 0
    cursor_visible: bool = True

    def copy(self) -> ScreenState:
        return ScreenState(
            cols=self.cols,
            rows=self.rows,
            cells=[[cell.copy() for cell in row] for row in self.cells],
            cursor_row=self.cursor_row,
            cursor_col=self.cursor_col,
            cursor_visible=self.cursor_visible,
        )


# Standard 16 ANSI colors (indices 0-15)
ANSI_COLORS_16 = [
    "#000000",
    "#aa0000",
    "#00aa00",
    "#aa5500",
    "#0000aa",
    "#aa00aa",
    "#00aaaa",
    "#aaaaaa",
    "#555555",
    "#ff5555",
    "#55ff55",
    "#ffff55",
    "#5555ff",
    "#ff55ff",
    "#55ffff",
    "#ffffff",
]

# Regex for CSI sequences: ESC [ (params) (intermediate) (final)
_CSI_RE = re.compile(r"\x1b\[([0-9;?]*)([^@-~]?)([A-Za-z@-~])")
# Regex for OSC sequences: ESC ] ... (ST or BEL)
_OSC_RE = re.compile(r"\x1b\].*?(?:\x1b\\|\x07)")
# Regex for simple escape sequences
_ESC_SIMPLE_RE = re.compile(r"\x1b[()][0-9A-B]|\x1b[=>DMEH78]")


class TerminalEmulator:
    """A minimal VT100/xterm terminal emulator.

    Processes output bytes and maintains a character grid with styles.
    Designed for offline rendering of recordings, not interactive use.
    """

    def __init__(self, cols: int = 80, rows: int = 24) -> None:
        self.cols = cols
        self.rows = rows
        self._cursor_row = 0
        self._cursor_col = 0
        self._cursor_visible = True
        self._style = CellStyle()
        self._saved_cursor: tuple[int, int] | None = None
        self._scroll_top = 0
        self._scroll_bottom = rows - 1

        # Main screen buffer
        self._screen = self._blank_screen()
        # Alternate screen buffer (for TUIs)
        self._alt_screen: list[list[Cell]] | None = None
        self._using_alt = False

    def _blank_screen(self) -> list[list[Cell]]:
        """Create a blank screen grid."""
        return [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]

    def _blank_row(self) -> list[Cell]:
        """Create a blank row."""
        return [Cell() for _ in range(self.cols)]

    @property
    def screen(self) -> ScreenState:
        """Current screen state snapshot."""
        return ScreenState(
            cols=self.cols,
            rows=self.rows,
            cells=[[cell.copy() for cell in row] for row in self._screen],
            cursor_row=self._cursor_row,
            cursor_col=self._cursor_col,
            cursor_visible=self._cursor_visible,
        )

    def feed(self, data: str) -> None:
        """Process terminal output data (a string of characters + escape sequences)."""
        i = 0
        n = len(data)

        while i < n:
            ch = data[i]

            # CSI sequence
            if ch == "\x1b" and i + 1 < n and data[i + 1] == "[":
                match = _CSI_RE.match(data, i)
                if match:
                    self._handle_csi(match.group(1), match.group(3))
                    i = match.end()
                    continue

            # OSC sequence (skip)
            if ch == "\x1b" and i + 1 < n and data[i + 1] == "]":
                match = _OSC_RE.match(data, i)
                if match:
                    i = match.end()
                    continue
                # Incomplete OSC, skip to end
                i = n
                continue

            # Simple escape sequences
            if ch == "\x1b":
                match = _ESC_SIMPLE_RE.match(data, i)
                if match:
                    self._handle_esc_simple(data[i + 1] if i + 1 < n else "")
                    i = match.end()
                    continue
                # Unknown escape, skip ESC + next char
                i += 2
                continue

            # Control characters
            if ch == "\r":
                self._cursor_col = 0
                i += 1
                continue

            if ch == "\n":
                self._linefeed()
                i += 1
                continue

            if ch == "\x08":  # Backspace
                if self._cursor_col > 0:
                    self._cursor_col -= 1
                i += 1
                continue

            if ch == "\t":  # Tab
                next_tab = ((self._cursor_col // 8) + 1) * 8
                self._cursor_col = min(next_tab, self.cols - 1)
                i += 1
                continue

            if ch == "\x07":  # Bell (ignore)
                i += 1
                continue

            # Skip other control chars
            if ord(ch) < 0x20:
                i += 1
                continue

            # Printable character
            self._put_char(ch)
            i += 1

    def _put_char(self, ch: str) -> None:
        """Place a character at the cursor position and advance."""
        if self._cursor_col >= self.cols:
            # Wrap to next line
            self._cursor_col = 0
            self._linefeed()

        row = self._cursor_row
        col = self._cursor_col
        self._screen[row][col] = Cell(char=ch, style=self._style.copy())
        self._cursor_col += 1

    def _linefeed(self) -> None:
        """Move cursor down one line, scrolling if at bottom of scroll region."""
        if self._cursor_row >= self._scroll_bottom:
            self._scroll_up(1)
        else:
            self._cursor_row += 1

    def _scroll_up(self, n: int) -> None:
        """Scroll the scroll region up by n lines."""
        for _ in range(n):
            del self._screen[self._scroll_top]
            self._screen.insert(self._scroll_bottom, self._blank_row())

    def _scroll_down(self, n: int) -> None:
        """Scroll the scroll region down by n lines."""
        for _ in range(n):
            del self._screen[self._scroll_bottom]
            self._screen.insert(self._scroll_top, self._blank_row())

    def _handle_esc_simple(self, ch: str) -> None:
        """Handle simple (non-CSI) escape sequences."""
        if ch == "7":
            self._saved_cursor = (self._cursor_row, self._cursor_col)
        elif ch == "8":
            if self._saved_cursor:
                self._cursor_row, self._cursor_col = self._saved_cursor
        elif ch == "M":  # Reverse index
            if self._cursor_row <= self._scroll_top:
                self._scroll_down(1)
            else:
                self._cursor_row -= 1
        elif ch == "D":  # Index (linefeed)
            self._linefeed()

    def _handle_csi(self, params_str: str, final: str) -> None:
        """Handle a CSI (Control Sequence Introducer) sequence."""
        # Parse parameters
        params = _parse_params(params_str)

        if final == "m":
            self._handle_sgr(params)
        elif final == "H" or final == "f":
            # CUP: Cursor Position
            row = max(0, (params[0] if params else 1) - 1)
            col = max(0, (params[1] if len(params) > 1 else 1) - 1)
            self._cursor_row = min(row, self.rows - 1)
            self._cursor_col = min(col, self.cols - 1)
        elif final == "A":
            # CUU: Cursor Up
            n = params[0] if params else 1
            self._cursor_row = max(0, self._cursor_row - n)
        elif final == "B":
            # CUD: Cursor Down
            n = params[0] if params else 1
            self._cursor_row = min(self.rows - 1, self._cursor_row + n)
        elif final == "C":
            # CUF: Cursor Forward
            n = params[0] if params else 1
            self._cursor_col = min(self.cols - 1, self._cursor_col + n)
        elif final == "D":
            # CUB: Cursor Back
            n = params[0] if params else 1
            self._cursor_col = max(0, self._cursor_col - n)
        elif final == "G":
            # CHA: Cursor Horizontal Absolute
            col = max(0, (params[0] if params else 1) - 1)
            self._cursor_col = min(col, self.cols - 1)
        elif final == "d":
            # VPA: Vertical Position Absolute
            row = max(0, (params[0] if params else 1) - 1)
            self._cursor_row = min(row, self.rows - 1)
        elif final == "J":
            # ED: Erase in Display
            mode = params[0] if params else 0
            self._erase_display(mode)
        elif final == "K":
            # EL: Erase in Line
            mode = params[0] if params else 0
            self._erase_line(mode)
        elif final == "L":
            # IL: Insert Lines
            n = params[0] if params else 1
            for _ in range(n):
                if self._cursor_row <= self._scroll_bottom:
                    del self._screen[self._scroll_bottom]
                    self._screen.insert(self._cursor_row, self._blank_row())
        elif final == "M":
            # DL: Delete Lines
            n = params[0] if params else 1
            for _ in range(n):
                if self._cursor_row <= self._scroll_bottom:
                    del self._screen[self._cursor_row]
                    self._screen.insert(self._scroll_bottom, self._blank_row())
        elif final == "P":
            # DCH: Delete Characters
            n = params[0] if params else 1
            row = self._screen[self._cursor_row]
            col = self._cursor_col
            del row[col : col + n]
            row.extend(Cell() for _ in range(n))
            # Trim back to cols
            self._screen[self._cursor_row] = row[: self.cols]
        elif final == "@":
            # ICH: Insert Characters
            n = params[0] if params else 1
            row = self._screen[self._cursor_row]
            col = self._cursor_col
            for _ in range(n):
                row.insert(col, Cell())
            self._screen[self._cursor_row] = row[: self.cols]
        elif final == "r":
            # DECSTBM: Set Top and Bottom Margins
            top = (params[0] if params else 1) - 1
            bottom = (params[1] if len(params) > 1 else self.rows) - 1
            self._scroll_top = max(0, top)
            self._scroll_bottom = min(self.rows - 1, bottom)
            self._cursor_row = 0
            self._cursor_col = 0
        elif final == "S":
            # SU: Scroll Up
            n = params[0] if params else 1
            self._scroll_up(n)
        elif final == "T":
            # SD: Scroll Down
            n = params[0] if params else 1
            self._scroll_down(n)
        elif final == "s":
            # Save cursor position
            self._saved_cursor = (self._cursor_row, self._cursor_col)
        elif final == "u":
            # Restore cursor position
            if self._saved_cursor:
                self._cursor_row, self._cursor_col = self._saved_cursor
        elif final == "h":
            # Set Mode
            if "?" in params_str:
                self._handle_dec_mode(params, set_mode=True)
        elif final == "l":
            # Reset Mode
            if "?" in params_str:
                self._handle_dec_mode(params, set_mode=False)
        elif final == "X":
            # ECH: Erase Characters
            n = params[0] if params else 1
            for c in range(self._cursor_col, min(self._cursor_col + n, self.cols)):
                self._screen[self._cursor_row][c] = Cell()

