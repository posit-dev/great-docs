"""
gdtest_termshow_tui — Check that termshow reproduces full-screen terminal apps faithfully.

Dimensions: A1, B1, C4, D2, E4, F1, G1, H3
Focus: Recordings of the kind a TUI produces, built so each known way of getting
       them wrong shows on screen:

       - a nyancat-style animation, written the way nyancat writes it (a 256-color
         background per pixel, set only when it changes, the counter erased to the
         end of the screen in the sky color) and split into 1024-character reads the
         way a PTY splits it, so escape sequences straddle events
       - a checklist of escape sequences termshow either handles or must drop,
         including some split across events on purpose
       - a grid of solid background blocks, for horizontal seams between rows

The nyancat page also plays the same recording in asciinema-player, loaded from a
CDN, for a side-by-side comparison.
"""

import json

# ── nyancat-style animation ──────────────────────────────────────────────────

_COLS, _ROWS = 80, 24
_FPS = 10
_SECONDS = 6
# The size of a PTY read, so frames are split wherever 1024 characters fall
_READ_SIZE = 1024

_SKY, _BLACK, _CREAM, _PINK, _SPRINKLE, _GREY, _WHITE = 17, 16, 230, 175, 162, 59, 231
_RAINBOW = (196, 214, 226, 118, 33, 19)
_STARS = ((5, 2), (30, 4), (18, 20), (36, 15), (10, 21), (26, 1))
_SPRINKLES = ((4, 3), (9, 2), (7, 6), (12, 4), (3, 7), (10, 8))


def _nyan_pixels(n: int) -> list[list[int]]:
    """Frame `n` as a 40 x 23 grid of 256-color indexes (each pixel is two cells wide)."""
    f = n % 6
    grid = [[_SKY] * (_COLS // 2) for _ in range(_ROWS - 1)]

    def put(x: int, y: int, color: int) -> None:
        if 0 <= x < len(grid[0]) and 0 <= y < len(grid):
            grid[y][x] = color

    for sx, sy in _STARS:
        put((sx - 2 * n) % len(grid[0]), sy, _WHITE)

    tx, ty = 14, 6 + (1 if f in (2, 3) else 0)
    # The rainbow waves in four-pixel steps
    for x in range(tx):
        wave = (x // 4 + f) % 2
        for band, color in enumerate(_RAINBOW):
            put(x, ty + wave + 2 * band, color)
            put(x, ty + wave + 2 * band + 1, color)
    # Tail
    put(tx - 1, ty + 6 + f % 2, _GREY)
    put(tx - 2, ty + 7 - f % 2, _GREY)
    # The pop-tart body
    for y in range(11):
        for x in range(16):
            if y in (0, 10) or x in (0, 15):
                color = _BLACK
            elif y in (1, 9) or x in (1, 14):
                color = _CREAM
            else:
                color = _SPRINKLE if (x, y) in _SPRINKLES else _PINK
            put(tx + x, ty + y, color)
    # Legs
    for lx in (1, 4, 10, 13):
        put(tx + lx + f % 2, ty + 11, _GREY)
        put(tx + lx + f % 2, ty + 12, _BLACK)
    # Head, with ears, eyes, cheeks and a mouth
    hx, hy = tx + 10 + (1 if f in (1, 2, 3) else 0), ty + 3
    for y in range(7):
        for x in range(9):
            put(hx + x, hy + y, _BLACK if y in (0, 6) or x in (0, 8) else _GREY)
    for x, y, color in (
        (1, -1, _BLACK),
        (7, -1, _BLACK),
        (2, 2, _WHITE),
        (6, 2, _WHITE),
        (1, 4, _PINK),
        (7, 4, _PINK),
        (3, 5, _BLACK),
        (4, 5, _BLACK),
        (5, 5, _BLACK),
    ):
        put(hx + x, hy + y, color)
    return grid


def _nyan_frame(n: int) -> str:
    """Frame `n` as nyancat writes it: from the top, a color only when it changes."""
    out = ["\x1b[H"]
    current = None
    for row in _nyan_pixels(n):
        for color in row:
            if color != current:
                out.append(f"\x1b[48;5;{color}m")
                current = color
            out.append("  ")
        out.append("\r\n")
    if current != _SKY:
        out.append(f"\x1b[48;5;{_SKY}m")
    # The counter, erased to the end of the screen while the sky color is set
    counter = f"You have nyaned for {n // _FPS} seconds!"
    out.append(" " * ((_COLS - len(counter)) // 2))
    out.append(f"\x1b[1;37m{counter}\x1b[J\x1b[0m")
    return "".join(out)


def _nyan_events() -> list[tuple[float, str]]:
    """The animation as `(interval, text)` output events, one PTY read each."""
    title = "Nyanyanyanyanyanyanya..."
    events = [
        (0.0, f"\x1bk{title}\x1b\\\x1b]1;{title}\x07\x1b]2;{title}\x07\x1b[H\x1b[2J\x1b[?25l")
    ]
    for n in range(_FPS * _SECONDS):
        frame = _nyan_frame(n)
        for start in range(0, len(frame), _READ_SIZE):
            interval = 1 / _FPS if start == 0 and n else 0.0
            events.append((round(interval, 3), frame[start : start + _READ_SIZE]))
    return events


def _nyan_termshow() -> str:
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": _COLS, "rows": _ROWS, "type": "xterm-256color"},
        "title": "nyancat",
    }
    lines = [json.dumps(header)] + [json.dumps([t, "o", d]) for t, d in _nyan_events()]
    return "\n".join(lines) + "\n"


def _nyan_cast() -> str:
    """The same recording in asciicast v2, which has absolute times."""
    lines = [json.dumps({"version": 2, "width": _COLS, "height": _ROWS})]
    now = 0.0
    for interval, data in _nyan_events():
        now += interval
        lines.append(json.dumps([round(now, 3), "o", data]))
    return "\n".join(lines) + "\n"


# ── Escape sequence checklist ────────────────────────────────────────────────

# Each row's label, then the output that follows it, as separate events. Every
# row should end in a clean word; any stray characters are a failed check.
_SEQUENCE_ROWS = (
    ("CSI split after ESC", ["\x1b", "[32mgreen\x1b[0m"]),
    ("CSI split in its parameters", ["\x1b[38;5;2", "08morange\x1b[0m"]),
    ("OSC title split", ["\x1b]2;Sequence ch", "ecks\x07plain"]),
    ("Charset designation split", ["\x1b(", "Bplain"]),
    ("modifyOtherKeys (>4;1m)", ["\x1b[>4;1mplain"]),
    ("kitty keyboard (=5u, ?1u)", ["\x1b[=5u\x1b[?1uplain"]),
    ("Cursor shape (2 q)", ["\x1b[2 qplain"]),
    ("Colon 256-color", ["\x1b[38:5:208morange\x1b[0m"]),
    ("Colon truecolor", ["\x1b[38:2::255:105:180mpink\x1b[0m"]),
    ("Curly underline (4:3)", ["\x1b[4:3munderlined\x1b[4:0m"]),
    ("Underline color (58:5:196)", ["\x1b[58:5:196mplain\x1b[59m"]),
    ("Erase line keeps the bg", ["\x1b[48;5;24m", " blue to the edge\x1b[K\x1b[0m"]),
)


def _sequences_termshow() -> str:
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": 64, "rows": 16, "type": "xterm-256color"},
        "title": "Escape sequences",
    }
    events: list[tuple[float, str]] = [
        (0.3, "\x1b[?25l\x1b[H\x1b[2J\x1b[1mEscape sequence checks\x1b[0m\r\n\r\n")
    ]
    for label, pieces in _SEQUENCE_ROWS:
        events.append((0.25, f"{label + ':':<30}"))
        events.extend((0.05, piece) for piece in pieces)
        events.append((0.0, "\r\n"))
    swatch = "".join(f"\x1b[48;5;{c}m    " for c in (17, 175, 214, 230)) + "\x1b[0m"
    events.append((0.25, f"\r\n{'256-color cube:':<30}{swatch}"))
    events.append((2.0, ""))
    lines = [json.dumps(header)] + [json.dumps([t, "o", d]) for t, d in events]
    return "\n".join(lines) + "\n"


# ── Background seams ─────────────────────────────────────────────────────────


def _seams_termshow() -> str:
    """A 6 x 6 grid of solid blocks from the color cube, each 12 columns by 3 rows."""
    header = {
        "version": 1,
        "format": "termshow",
        "term": {"cols": 72, "rows": 18, "type": "xterm-256color"},
        "title": "Background blocks",
    }
    rows = []
    for block_row in range(6):
        line = "".join(f"\x1b[48;5;{16 + 36 * block_row + 6 * g + 3}m{' ' * 12}" for g in range(6))
        rows.extend([line + "\x1b[0m"] * 3)
    events = [(0.3, "\x1b[?25l\x1b[H\x1b[2J" + "\r\n".join(rows)), (2.0, "")]
    lines = [json.dumps(header)] + [json.dumps([t, "o", d]) for t, d in events]
    return "\n".join(lines) + "\n"


_ASCIINEMA = "https://cdn.jsdelivr.net/npm/asciinema-player@3.9.0/dist/bundle/asciinema-player"


SPEC = {
    "name": "gdtest_termshow_tui",
    "description": "Termshow recordings of a TUI, checked against asciinema",
    "dimensions": ["A1", "B1", "C4", "D2", "E4", "F1", "G1", "H3"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-termshow-tui",
            "version": "1.0.0",
            "description": "A package for checking termshow recordings of full-screen apps",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_termshow_tui/__init__.py": (
            '"""A package whose docs hold recordings of full-screen terminal apps."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["nyan"]\n'
            "\n"
            "\n"
            "def nyan(seconds: int) -> str:\n"
            '    """Report how long the cat has flown.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    seconds\n"
            "        Seconds of flight.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        The counter line nyancat shows.\n"
            '    """\n'
            '    return f"You have nyaned for {seconds} seconds!"\n'
        ),
        # ── Terminal recordings ──────────────────────────────────────────
        "docs/demos/nyan.termshow": _nyan_termshow(),
        "docs/demos/sequences.termshow": _sequences_termshow(),
        "docs/demos/seams.termshow": _seams_termshow(),
        # ── User guide pages ─────────────────────────────────────────────
        "docs/user_guide/01-nyan.qmd": (
            "---\n"
            "title: Nyancat\n"
            "---\n"
            "\n"
            "A six-second, nyancat-style animation. Each frame is written the way nyancat\n"
            "writes it and split into 1024-character reads the way a PTY splits it, so\n"
            "many escape sequences are cut in two between events.\n"
            "\n"
            '{{< termshow file="demos/nyan" autoplay="true" loop="true" >}}\n'
            "\n"
            "Check that:\n"
            "\n"
            "- no text such as `48;5;175m` appears anywhere, and no rows are pushed out\n"
            "  of place\n"
            "- there are no thin horizontal lines between rows of the same color\n"
            "- the sky is navy (`#00005f`), and the counter's row is navy all the way\n"
            "  across\n"
            "- the counter reads *You have nyaned for N seconds!*, centered\n"
            "\n"
            "## In asciinema-player\n"
            "\n"
            "The same recording, for comparison (the player is loaded from a CDN).\n"
            "\n"
            "```{=html}\n"
            f'<link rel="stylesheet" href="{_ASCIINEMA}.min.css">\n'
            '<div id="gd-nyan-asciinema"></div>\n'
            f'<script src="{_ASCIINEMA}.min.js"></script>\n'
            "<script>\n"
            "AsciinemaPlayer.create(\n"
            f"  {{ data: {json.dumps(_nyan_cast())} }},\n"
            '  document.getElementById("gd-nyan-asciinema"),\n'
            '  { autoPlay: true, loop: true, fit: "width" }\n'
            ");\n"
            "</script>\n"
            "```\n"
        ),
        "docs/user_guide/02-escape-sequences.qmd": (
            "---\n"
            "title: Escape Sequences\n"
            "---\n"
            "\n"
            "Each row names an escape sequence, then shows the output that follows it.\n"
            "Some sequences are split across two events on purpose. Every row should end\n"
            "in a clean word, in the color it names; stray characters such as `>4;1m`,\n"
            "`5u`, `q` or `2::255` mean the sequence wasn't handled.\n"
            "\n"
            '{{< termshow file="demos/sequences" >}}\n'
            "\n"
            "The last row of the checklist should have a blue background all the way to the\n"
            "edge. The swatch below it should show `#00005f`, `#d787af`, `#ffaf00` and\n"
            "`#ffffd7`, the xterm colors for 17, 175, 214 and 230.\n"
        ),
        "docs/user_guide/03-background-blocks.qmd": (
            "---\n"
            "title: Background Blocks\n"
            "---\n"
            "\n"
            "Solid blocks of color, three rows tall. Each block should be one flat color,\n"
            "with no lines between its rows, at any zoom level.\n"
            "\n"
            '{{< termshow file="demos/seams" >}}\n'
        ),
    },
    "config": {
        "package_name": "gdtest_termshow_tui",
        "display_name": "Termshow TUI Checks",
        "description": "Recordings of full-screen terminal apps, checked for fidelity",
        "user_guide": True,
    },
    "expected": {
        "files_exist": [
            "user-guide/nyan.html",
            "user-guide/escape-sequences.html",
            "user-guide/background-blocks.html",
            "termshow/demos/nyan/manifest.json",
            "termshow/demos/sequences/manifest.json",
            "termshow/demos/seams/manifest.json",
        ],
        "files_contain": {
            "user-guide/nyan.html": ["gd-termshow", "gd-nyan-asciinema"],
        },
    },
}
