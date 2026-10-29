"""Tests for the _term_player.renderer module."""

from __future__ import annotations

import pytest

from great_docs._term_player.emulator import Cell, CellStyle, ScreenState, TerminalEmulator
from great_docs._term_player.parser import Theme
from great_docs._term_player.renderer import (
    _render_chrome,
    _chrome_height,
    _collect_bg_spans,
    _collect_text_spans,
    _index_to_color,
    _resolve_bg,
    _resolve_fg,
    _style_classes,
    render_frame,
    render_frames,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_screen(cols: int = 10, rows: int = 3, text: str = "") -> ScreenState:
    """Create a screen state, optionally with text on row 0."""
    emu = TerminalEmulator(cols=cols, rows=rows)
    if text:
        emu.feed(text)
    return emu.screen


def _styled_row(specs: list[tuple[str, CellStyle | None]]) -> list[Cell]:
    """Build a row from (char, style) specs. None style = default."""
    return [Cell(char=ch, style=style.copy() if style else CellStyle()) for ch, style in specs]


# ---------------------------------------------------------------------------
# _chrome_height
# ---------------------------------------------------------------------------


class TestChromeHeight:
    def test_none(self):
        assert _chrome_height("none") == 0.0

    def test_minimal(self):
        assert _chrome_height("minimal") == 36.0

    def test_colorful(self):
        assert _chrome_height("colorful") == 36.0


# ---------------------------------------------------------------------------
# _index_to_color
# ---------------------------------------------------------------------------


class TestIndexToColor:
    def test_hex_passthrough(self):
        theme = Theme()
        assert _index_to_color("#ff0000", theme) == "#ff0000"

    def test_palette_index(self):
        theme = Theme()
        # Index 0 = first palette color
        assert _index_to_color("0", theme) == theme.palette[0]

    def test_index_in_range(self):
        theme = Theme()
        assert _index_to_color("4", theme) == theme.palette[4]

    def test_invalid_string_returns_fg(self):
        theme = Theme()
        assert _index_to_color("invalid", theme) == theme.fg


# ---------------------------------------------------------------------------
# _resolve_fg / _resolve_bg
# ---------------------------------------------------------------------------


class TestResolveFg:
    def test_default_fg(self):
        theme = Theme()
        cell = Cell(char="X")
        assert _resolve_fg(cell, theme) == theme.fg

    def test_explicit_fg_color(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(fg="1"))
        assert _resolve_fg(cell, theme) == theme.palette[1]

    def test_bold_brightens_standard_color(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(fg="2", bold=True))
        # Standard color (0-7) + bold → bright (index + 8)
        assert _resolve_fg(cell, theme) == theme.palette[10]

    def test_inverse_swaps(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(inverse=True))
        # No bg set → use theme.bg as fg
        assert _resolve_fg(cell, theme) == theme.bg

    def test_inverse_with_bg(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(bg="3", inverse=True))
        assert _resolve_fg(cell, theme) == theme.palette[3]


class TestResolveBg:
    def test_no_bg_returns_none(self):
        theme = Theme()
        cell = Cell(char="X")
        assert _resolve_bg(cell, theme) is None

    def test_explicit_bg(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(bg="1"))
        assert _resolve_bg(cell, theme) == theme.palette[1]

    def test_bg_same_as_theme_returns_none(self):
        theme = Theme(bg="#ff0000")
        # If resolved bg matches theme.bg, returns None
        cell = Cell(char="X", style=CellStyle(bg="#ff0000"))
        # Hex pass-through, same as theme.bg → None
        assert _resolve_bg(cell, theme) is None

    def test_inverse_with_fg(self):
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(fg="5", inverse=True))
        assert _resolve_bg(cell, theme) == theme.palette[5]


# ---------------------------------------------------------------------------
# _style_classes
# ---------------------------------------------------------------------------


class TestStyleClasses:
    def test_no_styles(self):
        assert _style_classes(CellStyle()) == ""

    def test_bold(self):
        assert "gd-tp-bold" in _style_classes(CellStyle(bold=True))

    def test_italic(self):
        assert "gd-tp-italic" in _style_classes(CellStyle(italic=True))

    def test_multiple(self):
        classes = _style_classes(CellStyle(bold=True, underline=True, dim=True))
        assert "gd-tp-bold" in classes
        assert "gd-tp-underline" in classes
        assert "gd-tp-dim" in classes


# ---------------------------------------------------------------------------
# _collect_bg_spans
# ---------------------------------------------------------------------------


class TestCollectBgSpans:
    def test_no_bg_produces_empty(self):
        theme = Theme()
        row = [Cell(char="X") for _ in range(5)]
        spans = _collect_bg_spans(row, theme)
        assert spans == []

    def test_contiguous_bg_span(self):
        theme = Theme()
        style = CellStyle(bg="1")
        row = [Cell(char="A", style=style.copy()) for _ in range(5)]
        spans = _collect_bg_spans(row, theme)
        assert len(spans) == 1
        assert spans[0] == (0, 5, theme.palette[1])


# ---------------------------------------------------------------------------
# _collect_text_spans
# ---------------------------------------------------------------------------


class TestCollectTextSpans:
    def test_empty_row(self):
        theme = Theme()
        row = [Cell() for _ in range(10)]
        spans = _collect_text_spans(row, theme)
        assert spans == []

    def test_simple_text(self):
        theme = Theme()
        row = [Cell(char=c) for c in "Hello     "]
        spans = _collect_text_spans(row, theme)
        assert len(spans) >= 1
        full_text = "".join(s[1] for s in spans)
        assert full_text == "Hello"

    def test_different_styles_split(self):
        theme = Theme()
        row = [
            Cell(char="A", style=CellStyle(bold=True)),
            Cell(char="B", style=CellStyle(bold=True)),
            Cell(char="C", style=CellStyle(italic=True)),
        ] + [Cell() for _ in range(7)]
        spans = _collect_text_spans(row, theme)
        assert len(spans) >= 2

    def test_text_after_wide_char_starts_at_its_column(self):
        """The font may not draw an emoji two cells wide, so what follows
        it gets a span at its own column."""
        state = _simple_screen(cols=12, text="│ ok 🎉 │")
        spans = _collect_text_spans(state.cells[0], Theme())
        assert [(col, text) for col, text, *_ in spans] == [(0, "│ ok 🎉"), (7, " │")]

    def test_wide_char_at_the_end(self):
        state = _simple_screen(cols=6, text="ab中")
        spans = _collect_text_spans(state.cells[0], Theme())
        assert [(col, text) for col, text, *_ in spans] == [(0, "ab中")]

    def test_wide_chars_side_by_side(self):
        state = _simple_screen(cols=6, text="中文")
        spans = _collect_text_spans(state.cells[0], Theme())
        assert [(col, text) for col, text, *_ in spans] == [(0, "中"), (2, "文")]


# ---------------------------------------------------------------------------
# render_frame
# ---------------------------------------------------------------------------


class TestRenderFrame:
    def test_returns_svg(self):
        state = _simple_screen(10, 3, "Hello")
        svg = render_frame(state)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_contains_text(self):
        state = _simple_screen(10, 3, "Hello")
        svg = render_frame(state)
        assert "Hello" in svg

    def test_uses_theme_bg(self):
        state = _simple_screen(10, 3)
        theme = Theme(bg="#123456")
        svg = render_frame(state, theme)
        assert "#123456" in svg

    def test_custom_font_family(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, font_family="Courier New")
        assert "Courier New" in svg

    def test_no_cursor_when_disabled(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, show_cursor=False)
        # Cursor class is in the <style> block; check for the actual rect element
        assert 'class="gd-tp-cursor"' not in svg

    def test_cursor_present_by_default(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, show_cursor=True)
        assert 'class="gd-tp-cursor"' in svg

    def test_window_chrome_none(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, window_chrome="none")
        # No traffic light circles
        assert "circle" not in svg

    def test_window_chrome_colorful(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, window_chrome="colorful")

        # SVG should not contain chrome circles (in the CSS overlay)
        assert "circle" not in svg

    def test_window_chrome_minimal(self):
        state = _simple_screen(10, 3, "X")
        svg = render_frame(state, window_chrome="minimal")

        assert "circle" not in svg

    def test_xml_escapes_special_chars(self):
        state = _simple_screen(20, 3, "<script>&alert</script>")
        svg = render_frame(state)
        assert "<script>" not in svg
        assert "&lt;" in svg
        assert "&amp;" in svg

    def test_styled_text_has_css_classes(self):
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("\x1b[1mBold\x1b[0m")
        svg = render_frame(emu.screen)
        assert "gd-tp-bold" in svg

    def test_viewbox_dimensions(self):
        state = _simple_screen(80, 24)
        svg = render_frame(state)
        assert 'viewBox="0 0' in svg


# ---------------------------------------------------------------------------
# render_frames
# ---------------------------------------------------------------------------


class TestRenderFrames:
    def test_renders_multiple_states(self):
        state1 = _simple_screen(10, 3, "Frame1")
        state2 = _simple_screen(10, 3, "Frame2")
        results = render_frames([(0.0, state1), (1.5, state2)])
        assert len(results) == 2
        assert results[0][0] == 0.0
        assert results[1][0] == 1.5
        assert "Frame1" in results[0][1]
        assert "Frame2" in results[1][1]

    def test_empty_list(self):
        results = render_frames([])
        assert results == []


# render_frame with colored background cells


class TestRenderFrameBgSpans:
    def test_cell_with_bg_color_produces_rect(self):
        """Cells with non-default background produce <rect> elements."""
        emu = TerminalEmulator(cols=10, rows=3)

        # Set a green background on some text
        emu.feed("\x1b[42mHello\x1b[0m")
        svg = render_frame(emu.screen)

        # Should contain a rect for the background span (not the full-frame rect)
        # Count rects: one is the frame bg, additional ones are cell bgs
        assert svg.count("<rect") > 1

    def test_contiguous_bg_spans_merged(self):
        """Multiple cells with same bg produce one rect span."""
        emu = TerminalEmulator(cols=10, rows=3)
        emu.feed("\x1b[44mABC\x1b[0m")
        svg = render_frame(emu.screen, show_cursor=False)

        # Frame bg rect + one span rect for the 3-char blue background
        assert svg.count("<rect") == 2


# _render_chrome function (minimal and colorful)


class TestRenderChrome:
    def test_minimal_chrome(self):
        """Minimal chrome produces circles and rects."""
        theme = Theme()
        result = _render_chrome("minimal", 400.0, theme)

        assert "circle" in result
        assert "#585b70" in result
        assert "rect" in result

    def test_colorful_chrome(self):
        """Colorful chrome produces colored traffic light circles."""
        theme = Theme()
        result = _render_chrome("colorful", 400.0, theme)

        assert "circle" in result
        assert "#f38ba8" in result  # Close (red)
        assert "#f9e2af" in result  # Minimize (yellow)
        assert "#a6e3a1" in result  # Maximize (green)

    def test_none_chrome_returns_empty(self):
        """Style 'none' (or any other) returns empty string."""
        theme = Theme()
        result = _render_chrome("none", 400.0, theme)

        assert result == ""


# _collect_bg_spans — contiguous cells extending a span


class TestCollectBgSpansContiguous:
    def test_contiguous_same_bg_extends_span(self):
        """Multiple cells with same bg are merged into one span."""
        theme = Theme()
        style_bg = CellStyle(bg="#ff0000")
        row = [
            Cell(char="A", style=style_bg.copy()),
            Cell(char="B", style=style_bg.copy()),
            Cell(char="C", style=style_bg.copy()),
            Cell(char=" ", style=CellStyle()),
        ]
        spans = _collect_bg_spans(row, theme)

        assert len(spans) == 1
        assert spans[0] == (0, 3, "#ff0000")

    def test_different_bg_splits_spans(self):
        """Different bg colors produce separate spans."""
        theme = Theme()
        row = [
            Cell(char="A", style=CellStyle(bg="#ff0000")),
            Cell(char="B", style=CellStyle(bg="#00ff00")),
            Cell(char="C", style=CellStyle()),
        ]
        spans = _collect_bg_spans(row, theme)

        assert len(spans) == 2
        assert spans[0] == (0, 1, "#ff0000")
        assert spans[1] == (1, 1, "#00ff00")


# _resolve_bg with inverse mode


class TestResolveBgInverse:
    def test_inverse_with_explicit_fg(self):
        """Inverse mode with fg set uses fg color as background."""
        theme = Theme()
        cell = Cell(char="X", style=CellStyle(inverse=True, fg="#ff0000"))
        result = _resolve_bg(cell, theme)

        assert result == "#ff0000"

    def test_inverse_no_fg_uses_theme_fg(self):
        """Inverse mode with no fg uses theme's foreground as background."""
        theme = Theme(fg="#aabbcc", bg="#112233")
        cell = Cell(char="X", style=CellStyle(inverse=True))
        result = _resolve_bg(cell, theme)

        assert result == "#aabbcc"

    def test_inverse_fg_same_as_theme_bg_returns_none(self):
        """Inverse where resolved fg == theme bg returns None."""
        theme = Theme(fg="#aabbcc", bg="#112233")
        cell = Cell(char="X", style=CellStyle(inverse=True, fg="#112233"))
        result = _resolve_bg(cell, theme)

        assert result is None

    def test_inverse_no_fg_same_as_bg_returns_none(self):
        """Inverse where theme.fg == theme.bg returns None."""
        theme = Theme(fg="#111111", bg="#111111")
        cell = Cell(char="X", style=CellStyle(inverse=True))
        result = _resolve_bg(cell, theme)

        assert result is None


# _index_to_color — index >= palette but < 16, and fallback


class TestIndexToColorExtended:
    def test_index_beyond_palette_but_within_16(self):
        """Index >= palette length but < 16 uses ANSI_COLORS_16."""
        # Create theme with only 4 palette entries
        theme = Theme(palette=["#000", "#111", "#222", "#333"])
        result = _index_to_color("8", theme)
        from great_docs._term_player.emulator import ANSI_COLORS_16

        assert result == ANSI_COLORS_16[8]

    def test_index_beyond_16_returns_theme_fg(self):
        """Index >= 16 falls through to theme.fg."""
        theme = Theme(fg="#facade", palette=["#000"] * 4)
        result = _index_to_color("20", theme)

        assert result == "#facade"


# _style_classes — strikethrough


class TestStyleClassesStrikethrough:
    def test_strikethrough_class(self):
        """Strikethrough style produces the correct CSS class."""
        style = CellStyle(strikethrough=True)
        result = _style_classes(style)

        assert "gd-tp-strikethrough" in result

    def test_strikethrough_combined(self):
        """Strikethrough combined with other styles."""
        style = CellStyle(bold=True, strikethrough=True)
        result = _style_classes(style)

        assert "gd-tp-bold" in result
        assert "gd-tp-strikethrough" in result
