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

