"""Lightweight virtual terminal emulator for rendering terminal recordings.

Processes ANSI escape sequences and maintains a screen buffer that can be
snapshotted for SVG rendering. Handles:
- Cursor movement (CUP, CUU, CUD, CUF, CUB, etc.)
- SGR attributes (colors, bold, italic, underline, inverse)
- Screen operations (ED, EL, scroll)
- 256-color and truecolor (24-bit) SGR
- Alternative screen buffer
- Wide (CJK, emoji) and zero-width (combining, joiner) characters
"""

from __future__ import annotations

import re
import unicodedata
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
    """A single character cell in the terminal grid.

    A wide character fills two cells: its own, then one whose `char` is
    `""`. A cell's `char` can also hold several code points, when combining
    marks or a zero-width joiner sequence follow the first.
    """

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

# The levels of each channel in the 256-color palette's 6x6x6 cube. They're
# xterm's, which asciinema and most terminals share, not evenly spaced
_CUBE_LEVELS = (0x00, 0x5F, 0x87, 0xAF, 0xD7, 0xFF)

# Regex for CSI sequences: ESC [ (params) (intermediates) (final), with the
# byte ranges ECMA-48 gives each part
_CSI_RE = re.compile(r"\x1b\[([0-?]*)([ -/]*)([@-~])")
# The start of a CSI sequence that has no final byte yet
_CSI_START_RE = re.compile(r"\x1b\[[0-?]*[ -/]*")
# Regex for string sequences, which run to ST (or BEL, for OSC): OSC (ESC ]),
# DCS (ESC P), SOS (ESC X), PM (ESC ^) and APC (ESC _)
_STRING_RE = re.compile(r"\x1b(?:\].*?(?:\x1b\\|\x07)|[PX^_].*?\x1b\\)", re.S)
# Regex for other escape sequences: ESC (intermediates) (final)
_ESC_RE = re.compile(r"\x1b([ -/]*)([0-~])")
_ESC_START_RE = re.compile(r"\x1b[ -/]*")

_ZWJ = "\u200d"
# Besides combining marks, these take no column: the zero-width space,
# non-joiner and joiner, and the BOM. So do the variation selectors
_ZERO_WIDTH = {"\u200b", "\u200c", _ZWJ, "\ufeff"}


def char_width(ch: str) -> int:
    """Return the number of terminal columns a character takes: 0, 1 or 2.

    Wide characters are the ones Unicode gives an East Asian Width of wide
    or fullwidth, which takes in CJK and most emoji. This is the same rule
    that `great_docs._build.log` pads its boxes with.
    """
    if " " <= ch <= "~":
        return 1
    if ch in _ZERO_WIDTH or "\ufe00" <= ch <= "\ufe0f" or "\U000e0100" <= ch <= "\U000e01ef":
        return 0
    if unicodedata.category(ch) in ("Mn", "Me"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def _is_wide(cell: Cell) -> bool:
    """Whether a cell holds a wide character (the first of its two cells)."""
    return bool(cell.char) and char_width(cell.char[0]) == 2


def _repair_wide(row: list[Cell]) -> None:
    """Blank any half of a wide character whose other half is gone.

    Erasing, inserting or deleting cells can split a wide character. Like
    xterm, the half that's left over becomes a blank.
    """
    last = len(row) - 1
    for c, cell in enumerate(row):
        if cell.char == "":
            if c == 0 or not _is_wide(row[c - 1]):
                row[c] = Cell(style=cell.style)
        elif _is_wide(cell) and (c == last or row[c + 1].char != ""):
            row[c] = Cell(style=cell.style)


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
        # An escape sequence that the last feed ended partway through
        self._pending = ""

    def _blank_screen(self) -> list[list[Cell]]:
        """Create a blank screen grid."""
        return [[Cell() for _ in range(self.cols)] for _ in range(self.rows)]

    def _blank(self) -> Cell:
        """Create a blank cell for erasing or inserting.

        Like xterm (whose terminfo entries declare `bce`, background color
        erase), the cell keeps the current background color, so a program can
        paint a colored background by erasing.
        """
        if self._style.bg is None:
            return Cell()
        return Cell(style=CellStyle(bg=self._style.bg))

    def _blank_row(self) -> list[Cell]:
        """Create a blank row."""
        return [self._blank() for _ in range(self.cols)]

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
        """Process terminal output data (a string of characters + escape sequences).

        A recording splits output wherever a read of the terminal ended, which
        can be partway through an escape sequence. The emulator holds on to an
        unfinished sequence and completes it with the next feed.
        """
        data = self._pending + data
        self._pending = ""
        i = 0
        n = len(data)

        while i < n:
            ch = data[i]

            if ch == "\x1b":
                end = self._escape(data, i)
                if end is None:
                    self._pending = data[i:]
                    return
                i = end
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

    def _escape(self, data: str, i: int) -> int | None:
        """Handle the escape sequence that starts at `data[i]`.

        Returns the index just past the sequence, or `None` when `data` ends
        before the sequence does.
        """
        n = len(data)
        if i + 1 >= n:
            return None
        kind = data[i + 1]

        if kind == "[":
            match = _CSI_RE.match(data, i)
            if match:
                params, intermediates, final = match.groups()
                # Sequences with intermediates (such as `CSI SP q`) and private
                # sequences other than DEC modes (such as `CSI > 4 ; 1 m`) aren't
                # modelled, so they're dropped rather than taken for others
                marker = params[:1]
                if not intermediates and (
                    marker not in ("<", "=", ">", "?") or (marker == "?" and final in "hl")
                ):
                    self._handle_csi(params, final)
                return match.end()
            start = _CSI_START_RE.match(data, i)
            assert start is not None
            if start.end() == n:
                return None
            # A character that can't continue the sequence cancels it
            return start.end()

        if kind in "]PX^_":
            match = _STRING_RE.match(data, i)
            return match.end() if match else None

        match = _ESC_RE.match(data, i)
        if match:
            if not match.group(1):
                self._handle_esc_simple(match.group(2))
            return match.end()
        start = _ESC_START_RE.match(data, i)
        assert start is not None
        if start.end() == n:
            return None
        # An ESC that nothing valid follows is dropped
        return start.end()

    def _put_char(self, ch: str) -> None:
        """Place a character at the cursor position and advance."""
        # A zero-width character, or anything after a zero-width joiner,
        # joins the character before the cursor
        prev = self._prev_cell()
        width = char_width(ch)
        if prev is not None and (width == 0 or prev.char.endswith(_ZWJ)):
            prev.char += ch
            return
        if width == 0:
            return
        if self.cols < 2:
            width = 1

        if self._cursor_col + width > self.cols:
            # Wrap to next line. A wide character that would only half fit
            # wraps too
            self._cursor_col = 0
            self._linefeed()

        row = self._screen[self._cursor_row]
        col = self._cursor_col
        # Overwriting either half of a wide character blanks the other half
        for c in range(col, col + width):
            if row[c].char == "" and c > 0:
                row[c - 1] = Cell(style=row[c - 1].style)
            if c + 1 < self.cols and row[c + 1].char == "":
                row[c + 1] = Cell(style=row[c + 1].style)
        row[col] = Cell(char=ch, style=self._style.copy())
        if width == 2:
            row[col + 1] = Cell(char="", style=self._style.copy())
        self._cursor_col += width

    def _prev_cell(self) -> Cell | None:
        """The cell of the character just before the cursor, if any."""
        col = min(self._cursor_col, self.cols) - 1
        if col < 0:
            return None
        row = self._screen[self._cursor_row]
        if row[col].char == "" and col > 0:
            col -= 1
        return row[col]

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
            self._handle_sgr(_sgr_params(params_str))
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
            row.extend(self._blank() for _ in range(n))
            # Trim back to cols
            self._screen[self._cursor_row] = row[: self.cols]
            _repair_wide(self._screen[self._cursor_row])
        elif final == "@":
            # ICH: Insert Characters
            n = params[0] if params else 1
            row = self._screen[self._cursor_row]
            col = self._cursor_col
            for _ in range(n):
                row.insert(col, self._blank())
            self._screen[self._cursor_row] = row[: self.cols]
            _repair_wide(self._screen[self._cursor_row])
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
                self._screen[self._cursor_row][c] = self._blank()
            _repair_wide(self._screen[self._cursor_row])

    def _handle_dec_mode(self, params: list[int], *, set_mode: bool) -> None:
        """Handle DEC private mode set/reset."""
        for p in params:
            if p == 25:
                # DECTCEM: Cursor visibility
                self._cursor_visible = set_mode
            elif p == 1049:
                # Alt screen buffer, saving the cursor on entry and
                # restoring it on exit
                if set_mode and not self._using_alt:
                    self._saved_cursor = (self._cursor_row, self._cursor_col)
                    self._alt_screen = self._screen
                    self._screen = self._blank_screen()
                    self._using_alt = True
                elif not set_mode and self._using_alt:
                    self._screen = self._alt_screen or self._blank_screen()
                    self._alt_screen = None
                    self._using_alt = False
                    if self._saved_cursor:
                        self._cursor_row, self._cursor_col = self._saved_cursor
            elif p == 47 or p == 1047:
                # Also alt screen (without save/restore cursor)
                if set_mode and not self._using_alt:
                    self._alt_screen = self._screen
                    self._screen = self._blank_screen()
                    self._using_alt = True
                elif not set_mode and self._using_alt:
                    self._screen = self._alt_screen or self._blank_screen()
                    self._alt_screen = None
                    self._using_alt = False

    def _handle_sgr(self, params: list[int]) -> None:
        """Handle SGR (Select Graphic Rendition) parameters."""
        if not params:
            params = [0]

        i = 0
        while i < len(params):
            p = params[i]

            if p == 0:
                self._style = CellStyle()
            elif p == 1:
                self._style.bold = True
            elif p == 2:
                self._style.dim = True
            elif p == 3:
                self._style.italic = True
            elif p == 4:
                self._style.underline = True
            elif p == 7:
                self._style.inverse = True
            elif p == 9:
                self._style.strikethrough = True
            elif p == 22:
                self._style.bold = False
                self._style.dim = False
            elif p == 23:
                self._style.italic = False
            elif p == 24:
                self._style.underline = False
            elif p == 27:
                self._style.inverse = False
            elif p == 29:
                self._style.strikethrough = False
            elif 30 <= p <= 37:
                self._style.fg = str(p - 30)
            elif p == 38:
                # Extended foreground color
                color, consumed = self._parse_extended_color(params[i + 1 :])
                if color is not None:
                    self._style.fg = color
                i += consumed
            elif p == 39:
                self._style.fg = None
            elif 40 <= p <= 47:
                self._style.bg = str(p - 40)
            elif p == 48:
                # Extended background color
                color, consumed = self._parse_extended_color(params[i + 1 :])
                if color is not None:
                    self._style.bg = color
                i += consumed
            elif p == 49:
                self._style.bg = None
            elif p == 58:
                # Underline color isn't drawn, but its parameters still go
                _, consumed = self._parse_extended_color(params[i + 1 :])
                i += consumed
            elif 90 <= p <= 97:
                # Bright foreground
                self._style.fg = str(p - 90 + 8)
            elif 100 <= p <= 107:
                # Bright background
                self._style.bg = str(p - 100 + 8)

            i += 1

    def _parse_extended_color(self, params: list[int]) -> tuple[str | None, int]:
        """Parse 256-color or truecolor sequences.

        Returns (color_string, number_of_params_consumed).
        """
        if not params:
            return None, 0

        if params[0] == 5 and len(params) >= 2:
            # 256-color: index
            idx = params[1]
            return self._color_256_to_hex(idx), 2
        elif params[0] == 2 and len(params) >= 4:
            # Truecolor: r, g, b
            r, g, b = params[1], params[2], params[3]
            return f"#{r:02x}{g:02x}{b:02x}", 4

        return None, 0

    def _color_256_to_hex(self, idx: int) -> str:
        """Convert a 256-color index to a hex color string."""
        if idx < 16:
            return ANSI_COLORS_16[idx]
        elif idx < 232:
            # 216-color cube: 6x6x6, at xterm's levels
            idx -= 16
            b = _CUBE_LEVELS[idx % 6]
            idx //= 6
            g = _CUBE_LEVELS[idx % 6]
            idx //= 6
            r = _CUBE_LEVELS[idx]
            return f"#{r:02x}{g:02x}{b:02x}"
        else:
            # Grayscale ramp: 24 shades
            v = 8 + (idx - 232) * 10
            return f"#{v:02x}{v:02x}{v:02x}"

    def _erase_display(self, mode: int) -> None:
        """Erase in display."""
        if mode == 0:
            # Erase below (including current position)
            for c in range(self._cursor_col, self.cols):
                self._screen[self._cursor_row][c] = self._blank()
            for r in range(self._cursor_row + 1, self.rows):
                self._screen[r] = self._blank_row()
            _repair_wide(self._screen[self._cursor_row])
        elif mode == 1:
            # Erase above (including current position)
            for r in range(self._cursor_row):
                self._screen[r] = self._blank_row()
            for c in range(min(self._cursor_col + 1, self.cols)):
                self._screen[self._cursor_row][c] = self._blank()
            _repair_wide(self._screen[self._cursor_row])
        elif mode == 2 or mode == 3:
            # Erase all
            self._screen = [self._blank_row() for _ in range(self.rows)]

    def _erase_line(self, mode: int) -> None:
        """Erase in line."""
        row = self._cursor_row
        if mode == 0:
            # Erase to right
            for c in range(self._cursor_col, self.cols):
                self._screen[row][c] = self._blank()
            _repair_wide(self._screen[row])
        elif mode == 1:
            # Erase to left
            for c in range(min(self._cursor_col + 1, self.cols)):
                self._screen[row][c] = self._blank()
            _repair_wide(self._screen[row])
        elif mode == 2:
            # Erase entire line
            self._screen[row] = self._blank_row()

    def resize(self, cols: int, rows: int) -> None:
        """Resize the terminal."""
        old_rows = self.rows
        old_cols = self.cols
        self.cols = cols
        self.rows = rows
        self._scroll_bottom = rows - 1

        # Extend or trim rows
        if rows > old_rows:
            for _ in range(rows - old_rows):
                self._screen.append(self._blank_row())
        elif rows < old_rows:
            self._screen = self._screen[:rows]

        # Extend or trim columns
        if cols != old_cols:
            for r in range(len(self._screen)):
                row = self._screen[r]
                if cols > old_cols:
                    row.extend(Cell() for _ in range(cols - old_cols))
                else:
                    self._screen[r] = row[:cols]
                    _repair_wide(self._screen[r])

        # Clamp cursor
        self._cursor_row = min(self._cursor_row, rows - 1)
        self._cursor_col = min(self._cursor_col, cols - 1)


def _parse_params(params_str: str) -> list[int]:
    """Parse CSI parameter string into list of integers."""
    # Remove '?' prefix for private sequences
    cleaned = params_str.lstrip("?")
    if not cleaned:
        return []
    return [_int(p) for p in cleaned.split(";")]


def _sgr_params(params_str: str) -> list[int]:
    """Parse SGR parameters, rewriting colon sub-parameters in semicolon form.

    `38:5:n` and `38:2::r:g:b` (or `38:2:r:g:b`) become `38;5;n` and
    `38;2;r;g;b`, and likewise for 48 and 58. An underline style, `4:n`,
    becomes `4`, or `24` for `4:0`.
    """
    if not params_str:
        return []
    result: list[int] = []
    for part in params_str.split(";"):
        if ":" not in part:
            result.append(_int(part))
            continue
        head, *subs = part.split(":")
        code = _int(head)
        if code in (38, 48, 58):
            # Truecolor may carry a color space ID before the components
            if subs[:1] == ["2"] and len(subs) == 5:
                subs = [subs[0], *subs[2:]]
            result.extend([code, *(_int(s) for s in subs)])
        elif code == 4:
            result.append(24 if subs[:1] == ["0"] else 4)
        else:
            result.append(code)
    return result


def _int(param: str) -> int:
    """Read one numeric parameter, taking an empty or malformed one as 0."""
    try:
        return int(param)
    except ValueError:
        return 0
