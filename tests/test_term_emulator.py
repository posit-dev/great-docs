"""Tests for the _term_player.emulator module."""

from __future__ import annotations

import pytest

from great_docs._term_player.emulator import (
    ANSI_COLORS_16,
    Cell,
    CellStyle,
    ScreenState,
    TerminalEmulator,
    _parse_params,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _screen_text(emu: TerminalEmulator, row: int) -> str:
    """Extract visible text from a row, stripping trailing spaces."""
    state = emu.screen
    return "".join(cell.char for cell in state.cells[row]).rstrip()


def _full_screen_text(emu: TerminalEmulator) -> list[str]:
    """Get all rows as stripped strings."""
    return [_screen_text(emu, r) for r in range(emu.rows)]


# ---------------------------------------------------------------------------
# _parse_params
# ---------------------------------------------------------------------------


class TestParseParams:
    def test_empty_string(self):
        assert _parse_params("") == []

    def test_single_param(self):
        assert _parse_params("1") == [1]

    def test_multiple_params(self):
        assert _parse_params("1;2;3") == [1, 2, 3]

    def test_private_mode_prefix(self):
        assert _parse_params("?25") == [25]

    def test_invalid_param_becomes_zero(self):
        assert _parse_params("1;;3") == [1, 0, 3]


# ---------------------------------------------------------------------------
# Basic character output
# ---------------------------------------------------------------------------


class TestBasicOutput:
    def test_simple_text(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("Hello, world!")
        assert _screen_text(emu, 0) == "Hello, world!"

    def test_cursor_advances(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("ABC")
        state = emu.screen
        assert state.cursor_col == 3
        assert state.cursor_row == 0

    def test_newline(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("line1\r\nline2")
        assert _screen_text(emu, 0) == "line1"
        assert _screen_text(emu, 1) == "line2"

    def test_carriage_return(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("AAAA\rBB")
        assert _screen_text(emu, 0) == "BBAA"

    def test_crlf(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("line1\r\nline2")
        assert _screen_text(emu, 0) == "line1"
        assert _screen_text(emu, 1) == "line2"

    def test_tab(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("A\tB")
        # Tab stops at col 8
        assert _screen_text(emu, 0) == "A       B"

    def test_backspace(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("AB\x08C")
        # Backspace moves cursor left, then C overwrites B
        assert _screen_text(emu, 0) == "AC"

    def test_line_wrap(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("1234567890X")
        assert _screen_text(emu, 0) == "1234567890"
        assert _screen_text(emu, 1) == "X"


# ---------------------------------------------------------------------------
# Cursor movement
# ---------------------------------------------------------------------------


class TestCursorMovement:
    def test_cup_move_to_position(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[5;10H")  # Move to row 5, col 10 (1-based)
        state = emu.screen
        assert state.cursor_row == 4
        assert state.cursor_col == 9

    def test_cuu_cursor_up(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[10;1H")  # Move to row 10
        emu.feed("\x1b[3A")  # Up 3
        assert emu.screen.cursor_row == 6

    def test_cud_cursor_down(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[2B")  # Down 2
        assert emu.screen.cursor_row == 2

    def test_cuf_cursor_forward(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[5C")  # Forward 5
        assert emu.screen.cursor_col == 5

    def test_cub_cursor_back(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[10;10H\x1b[3D")  # Col 10, then back 3
        assert emu.screen.cursor_col == 6

    def test_cursor_clamps_to_bounds(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[100;200H")  # Beyond bounds
        state = emu.screen
        assert state.cursor_row == 23  # max row
        assert state.cursor_col == 79  # max col

    def test_cursor_up_clamps_at_zero(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[999A")
        assert emu.screen.cursor_row == 0

    def test_cha_horizontal_absolute(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("ABCDEF\x1b[3G")  # Move to col 3 (1-based)
        assert emu.screen.cursor_col == 2

    def test_vpa_vertical_absolute(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[5d")  # Move to row 5 (1-based)
        assert emu.screen.cursor_row == 4


# ---------------------------------------------------------------------------
# Erase operations
# ---------------------------------------------------------------------------


class TestErase:
    def test_erase_display_below(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("AAAAAAAAAA")  # Fill row 0
        emu.feed("\nBBBBBBBBBB")  # Fill row 1
        emu.feed("\x1b[1;5H")  # Move to row 1, col 5
        emu.feed("\x1b[0J")  # Erase below
        assert _screen_text(emu, 0)[:4] == "AAAA"
        # Row 0 cols 4+ should be blank
        state = emu.screen
        assert state.cells[0][4].char == " "
        assert _screen_text(emu, 1) == ""

    def test_erase_display_all(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("Hello")
        emu.feed("\x1b[2J")
        assert _screen_text(emu, 0) == ""

    def test_erase_line_to_right(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;4H")  # Row 1, col 4
        emu.feed("\x1b[0K")
        assert _screen_text(emu, 0) == "ABC"

    def test_erase_line_to_left(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;4H")  # Col 4
        emu.feed("\x1b[1K")
        # Cols 0-3 erased
        row_text = "".join(emu.screen.cells[0][c].char for c in range(10))
        assert row_text == "    EFGHIJ"

    def test_erase_entire_line(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;4H")
        emu.feed("\x1b[2K")
        assert _screen_text(emu, 0) == ""

    def test_ech_erase_characters(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;3H")  # Col 3
        emu.feed("\x1b[4X")  # Erase 4 chars
        row_text = "".join(emu.screen.cells[0][c].char for c in range(10))
        assert row_text == "AB    GHIJ"


# ---------------------------------------------------------------------------
# SGR (text styling)
# ---------------------------------------------------------------------------


class TestSGR:
    def test_bold(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[1mBold\x1b[0m")
        cell = emu.screen.cells[0][0]
        assert cell.style.bold is True
        # After reset
        emu.feed("Normal")
        cell_after = emu.screen.cells[0][4]
        assert cell_after.style.bold is False

    def test_italic(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[3mI\x1b[0m")
        assert emu.screen.cells[0][0].style.italic is True

    def test_underline(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[4mU\x1b[0m")
        assert emu.screen.cells[0][0].style.underline is True

    def test_inverse(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[7mR\x1b[0m")
        assert emu.screen.cells[0][0].style.inverse is True

    def test_foreground_color(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[31mR\x1b[0m")  # Red (index 1)
        assert emu.screen.cells[0][0].style.fg == "1"

    def test_background_color(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[44mB\x1b[0m")  # Blue bg (index 4)
        assert emu.screen.cells[0][0].style.bg == "4"

    def test_bright_foreground(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[91mR\x1b[0m")  # Bright red (index 9)
        assert emu.screen.cells[0][0].style.fg == "9"

    def test_256_color_foreground(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[38;5;196mR\x1b[0m")  # Color 196
        cell = emu.screen.cells[0][0]
        assert cell.style.fg is not None
        # Color 196 should be a hex string
        assert cell.style.fg.startswith("#")

    def test_truecolor_foreground(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[38;2;255;128;0mX\x1b[0m")
        cell = emu.screen.cells[0][0]
        assert cell.style.fg == "#ff8000"

    def test_truecolor_background(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[48;2;0;255;128mX\x1b[0m")
        cell = emu.screen.cells[0][0]
        assert cell.style.bg == "#00ff80"

    def test_reset_clears_all(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[1;3;4;31;44m")
        emu.feed("\x1b[0mX")
        cell = emu.screen.cells[0][0]
        assert cell.style.bold is False
        assert cell.style.italic is False
        assert cell.style.underline is False
        assert cell.style.fg is None
        assert cell.style.bg is None

    def test_default_fg_bg_reset(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[31;44m")
        emu.feed("\x1b[39;49mX")
        cell = emu.screen.cells[0][0]
        assert cell.style.fg is None
        assert cell.style.bg is None


# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------


class TestScrolling:
    def test_scroll_up_at_bottom(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("AAA\r\nBBB\r\nCCC\r\nDDD")
        # After filling 3 rows and one more line, row 0 scrolls off
        assert _screen_text(emu, 0) == "BBB"
        assert _screen_text(emu, 1) == "CCC"
        assert _screen_text(emu, 2) == "DDD"

    def test_scroll_up_csi(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("AAA\r\nBBB\r\nCCC")
        emu.feed("\x1b[1S")  # Scroll up 1
        assert _screen_text(emu, 0) == "BBB"
        assert _screen_text(emu, 1) == "CCC"
        assert _screen_text(emu, 2) == ""

    def test_scroll_down_csi(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("AAA\r\nBBB\r\nCCC")
        emu.feed("\x1b[1T")  # Scroll down 1
        assert _screen_text(emu, 0) == ""
        assert _screen_text(emu, 1) == "AAA"
        assert _screen_text(emu, 2) == "BBB"

    def test_scroll_region(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("\x1b[1;1HRow0\x1b[2;1HRow1\x1b[3;1HRow2\x1b[4;1HRow3\x1b[5;1HRow4")
        emu.feed("\x1b[2;4r")  # Set scroll region rows 2-4 (cursor resets to 1,1)
        emu.feed("\x1b[4;1H")  # Move to row 4 (bottom of region)
        emu.feed("\n")  # Should scroll within region
        # Row 0 (outside scroll region) is unchanged
        assert _screen_text(emu, 0) == "Row0"


# ---------------------------------------------------------------------------
# Alternate screen buffer
# ---------------------------------------------------------------------------


class TestAltScreen:
    def test_switch_to_alt_and_back(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("Main")
        emu.feed("\x1b[?1049h")  # Switch to alt
        assert _screen_text(emu, 0) == ""  # Alt is blank
        emu.feed("\x1b[1;1H")  # Move to home position
        emu.feed("Alt")
        assert _screen_text(emu, 0) == "Alt"
        emu.feed("\x1b[?1049l")  # Switch back
        assert _screen_text(emu, 0) == "Main"

    def test_cursor_visibility(self):
        emu = TerminalEmulator(cols=80, rows=24)
        assert emu.screen.cursor_visible is True
        emu.feed("\x1b[?25l")  # Hide
        assert emu.screen.cursor_visible is False
        emu.feed("\x1b[?25h")  # Show
        assert emu.screen.cursor_visible is True


# ---------------------------------------------------------------------------
# Insert / Delete operations
# ---------------------------------------------------------------------------


class TestInsertDelete:
    def test_delete_characters(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;3H")  # Col 3
        emu.feed("\x1b[2P")  # Delete 2 chars
        row_text = "".join(emu.screen.cells[0][c].char for c in range(10))
        assert row_text == "ABEFGHIJ  "

    def test_insert_characters(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("ABCDEFGHIJ")
        emu.feed("\x1b[1;3H")  # Col 3
        emu.feed("\x1b[2@")  # Insert 2 chars
        row_text = "".join(emu.screen.cells[0][c].char for c in range(10))
        assert row_text == "AB  CDEFGH"

    def test_insert_lines(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("\x1b[1;1HAAA\x1b[2;1HBBB\x1b[3;1HCCC\x1b[4;1HDDD\x1b[5;1HEEE")
        emu.feed("\x1b[2;1H")  # Row 2
        emu.feed("\x1b[1L")  # Insert 1 line
        assert _screen_text(emu, 0) == "AAA"
        assert _screen_text(emu, 1) == ""  # Inserted
        assert _screen_text(emu, 2) == "BBB"

    def test_delete_lines(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("\x1b[1;1HAAA\x1b[2;1HBBB\x1b[3;1HCCC\x1b[4;1HDDD\x1b[5;1HEEE")
        emu.feed("\x1b[2;1H")  # Row 2
        emu.feed("\x1b[1M")  # Delete 1 line
        assert _screen_text(emu, 0) == "AAA"
        assert _screen_text(emu, 1) == "CCC"  # BBB was deleted


# ---------------------------------------------------------------------------
# Resize
# ---------------------------------------------------------------------------


class TestResize:
    def test_grow(self):
        emu = TerminalEmulator(cols=5, rows=3)
        emu.feed("ABCDE\r\n12345\r\nXYZWV")
        emu.resize(10, 5)
        assert emu.cols == 10
        assert emu.rows == 5
        assert _screen_text(emu, 0) == "ABCDE"
        assert _screen_text(emu, 3) == ""

    def test_shrink(self):
        emu = TerminalEmulator(cols=10, rows=5)
        emu.feed("1234567890\nABCDEFGHIJ")
        emu.resize(5, 2)
        assert emu.cols == 5
        assert emu.rows == 2
        # Columns truncated
        row_text = "".join(emu.screen.cells[0][c].char for c in range(5))
        assert row_text == "12345"

    def test_cursor_clamped_on_shrink(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[20;70H")  # Row 20, col 70
        emu.resize(40, 10)
        state = emu.screen
        assert state.cursor_row == 9
        assert state.cursor_col == 39


# ---------------------------------------------------------------------------
# 256-color mapping
# ---------------------------------------------------------------------------


class TestColor256:
    def test_standard_colors(self):
        emu = TerminalEmulator()
        assert emu._color_256_to_hex(0) == "#000000"
        assert emu._color_256_to_hex(1) == "#aa0000"
        assert emu._color_256_to_hex(15) == "#ffffff"

    def test_cube_color(self):
        emu = TerminalEmulator()
        # Index 16 = rgb(0,0,0) of the cube
        assert emu._color_256_to_hex(16) == "#000000"
        # Index 196 = rgb(255,0,0)
        assert emu._color_256_to_hex(196) == "#ff0000"

    def test_grayscale(self):
        emu = TerminalEmulator()
        # Index 232 = darkest gray: v = 8 + (0)*10 = 8
        assert emu._color_256_to_hex(232) == "#080808"
        # Index 255 = lightest gray: v = 8 + (23)*10 = 238
        assert emu._color_256_to_hex(255) == "#eeeeee"


# ---------------------------------------------------------------------------
# Save/restore cursor
# ---------------------------------------------------------------------------


class TestSaveRestore:
    def test_save_restore_csi(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[5;10H")  # Move
        emu.feed("\x1b[s")  # Save
        emu.feed("\x1b[1;1H")  # Move away
        emu.feed("\x1b[u")  # Restore
        state = emu.screen
        assert state.cursor_row == 4
        assert state.cursor_col == 9

    def test_save_restore_dec(self):
        emu = TerminalEmulator(cols=80, rows=24)
        emu.feed("\x1b[5;10H")  # Move
        emu.feed("\x1b7")  # Save (DEC)
        emu.feed("\x1b[1;1H")
        emu.feed("\x1b8")  # Restore (DEC)
        state = emu.screen
        assert state.cursor_row == 4
        assert state.cursor_col == 9


# ---------------------------------------------------------------------------
# ScreenState / Cell copying
# ---------------------------------------------------------------------------


class TestScreenState:
    def test_screen_snapshot_is_independent(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("ABC")
        snap1 = emu.screen
        emu.feed("DEF")
        snap2 = emu.screen
        # snap1 should not be affected by later output
        assert snap1.cells[0][3].char == " "
        assert snap2.cells[0][3].char == "D"

    def test_cell_copy(self):
        cell = Cell(char="X", style=CellStyle(bold=True, fg="#ff0000"))
        clone = cell.copy()
        clone.style.bold = False
        assert cell.style.bold is True  # Original unchanged

    def test_screen_state_copy(self):
        emu = TerminalEmulator(cols=5, rows=2)
        emu.feed("Hello")
        state = emu.screen
        clone = state.copy()
        clone.cells[0][0] = Cell(char="Z")
        assert state.cells[0][0].char == "H"
