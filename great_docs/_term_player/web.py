"""Files for using the Termshow player on any HTML page."""

from __future__ import annotations

import shutil
from pathlib import Path

PLAYER_DIR = Path(__file__).parent.parent / "assets" / "_extensions" / "termshow"

# The script and stylesheet, plus the fonts the stylesheet loads by relative URL
PLAYER_FILES = (
    "termshow.js",
    "termshow.css",
    "JetBrainsMono-Regular.subset.woff2",
    "JetBrainsMono-Bold.subset.woff2",
)


def copy_player(dest: str | Path) -> list[Path]:
    """Copy the player's script, stylesheet, and fonts into `dest`.

    Parameters
    ----------
    dest
        Directory to copy into. It's created if needed; files already there are replaced.

    Returns
    -------
    list[Path]
        The copied files.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(PLAYER_DIR / name, dest / name)) for name in PLAYER_FILES]


def player_snippet(player_url: str, src: str = "termshow/my-demo") -> str:
    """HTML that loads the player from `player_url` and embeds one recording.

    Parameters
    ----------
    player_url
        URL of the directory holding the player files, relative to the page.
    src
        The `src` for the example `<termshow-player>`: a render directory or a manifest URL.

    Returns
    -------
    str
        The `<link>` and `<script>` tags for the page's head, then the element.
    """
    base = player_url.rstrip("/") + "/" if player_url else ""
    return (
        f'<link rel="stylesheet" href="{base}termshow.css">\n'
        f'<script src="{base}termshow.js"></script>\n'
        "\n"
        f'<termshow-player src="{src}"></termshow-player>'
    )
