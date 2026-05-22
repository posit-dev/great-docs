"""SVG renderer: converts terminal screen states into SVG frames."""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

from .emulator import ANSI_COLORS_16, Cell, ScreenState
from .parser import Theme

# Default rendering configuration
DEFAULT_FONT_FAMILY = "JetBrains Mono, Fira Code, SF Mono, Menlo, Consolas, monospace"
DEFAULT_FONT_SIZE = 14
DEFAULT_CELL_WIDTH = 8.4  # Approximate character width at 14px
DEFAULT_LINE_HEIGHT = 1.5  # Line height multiplier
DEFAULT_PADDING = 16  # Padding inside terminal frame


