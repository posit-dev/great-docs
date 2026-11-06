"""
Logo discovery and favicon generation

Navbar and hero logos are discovered at conventional paths in the documentation source
directory when the corresponding `logo` or `hero.logo` setting is absent. Favicons are
generated from the configured favicon or the logo.
"""

from __future__ import annotations

import importlib
import io
import shutil
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from types import ModuleType

    from PIL import Image

__all__ = [
    "HERO_LOGO_CANDIDATES",
    "dark_variant",
    "detect_hero_logo",
    "detect_logo",
    "generate_favicons",
    "logo_candidates",
]

HERO_LOGO_CANDIDATES = (
    "logo-hero.svg",
    "logo-hero.png",
    "assets/logo-hero.svg",
    "assets/logo-hero.png",
    "logo-hero-light.svg",
    "logo-hero-light.png",
    "assets/logo-hero-light.svg",
    "assets/logo-hero-light.png",
)
"""The paths searched for a hero logo, in priority order"""

# Purpose, file name and side length of each square PNG favicon.
_RASTER_ICONS = (
    ("icon-16", "favicon-16x16.png", 16),
    ("icon-32", "favicon-32x32.png", 32),
    ("apple-touch-icon", "apple-touch-icon.png", 180),
)
_ICO_SIZES = [(16, 16), (32, 32), (48, 48)]


def logo_candidates(package_name: str | None) -> list[str]:
    """
    List the paths searched for a navbar logo, in priority order

    Parameters
    ----------
    package_name
        The distribution name. Candidates include `<name>_logo.*` for this name and for the
        name with hyphens replaced by underscores. `None` or an empty string adds no
        package-specific candidates.

    Returns
    -------
    :
        Paths relative to the documentation source directory.
    """
    candidates = [
        "logo.svg",
        "logo.png",
        "assets/logo.svg",
        "assets/logo.png",
    ]
    if package_name:
        for name in dict.fromkeys((package_name, package_name.replace("-", "_"))):
            candidates.extend(
                [
                    f"{name}_logo.svg",
                    f"{name}_logo.png",
                    f"assets/{name}_logo.svg",
                    f"assets/{name}_logo.png",
                ]
            )
    candidates.extend(["assets/logo-light.svg", "assets/logo-light.png"])
    return candidates


def dark_variant(light: str) -> str:
    """
    Name the dark-mode counterpart of a logo path

    The counterpart sits in the same directory, with any `-light` removed from the stem and
    `-dark` appended: `assets/logo-light.svg` pairs with `assets/logo-dark.svg`.

    Parameters
    ----------
    light
        A relative POSIX path to the light logo.

    Returns
    -------
    :
        The relative POSIX path of the dark logo, which may not exist.
    """
    path = PurePosixPath(light)
    return str(path.with_name(f"{path.stem.replace('-light', '')}-dark{path.suffix}"))


def _find_logo(source_dir: Path, candidates: Iterable[str]) -> dict[str, str] | None:
    """
    Find the first candidate file and its dark variant

    Parameters
    ----------
    source_dir
        The directory the candidates are relative to.
    candidates
        Relative paths in priority order.

    Returns
    -------
    :
        A logo mapping whose `light` key is the first existing candidate and whose `dark` key
        is its dark variant, or the same path when no dark variant exists. `None` when no
        candidate exists.
    """
    for candidate in candidates:
        if (source_dir / candidate).is_file():
            dark = dark_variant(candidate)
            return {
                "light": candidate,
                "dark": dark if (source_dir / dark).is_file() else candidate,
            }
    return None


def detect_logo(source_dir: Path, package_name: str | None) -> dict[str, str] | None:
    """
    Find the navbar logo at a conventional path

    Parameters
    ----------
    source_dir
        The documentation source directory.
    package_name
        The distribution name, which adds name-specific candidates (see `logo_candidates`).

    Returns
    -------
    :
        A mapping with `light` and `dark` paths relative to `source_dir`, or `None` when no
        candidate exists. Without a dark variant, both keys name the same file.
    """
    return _find_logo(source_dir, logo_candidates(package_name))


def detect_hero_logo(source_dir: Path) -> dict[str, str] | None:
    """
    Find the homepage hero logo at a conventional path

    The hero logo is a `logo-hero.*` or `logo-hero-light.*` file in the source directory or
    its `assets/` subdirectory.

    Parameters
    ----------
    source_dir
        The documentation source directory.

    Returns
    -------
    :
        A mapping with `light` and `dark` paths relative to `source_dir`, or `None` when no
        candidate exists. Without a dark variant, both keys name the same file.
    """
    return _find_logo(source_dir, HERO_LOGO_CANDIDATES)


def _import_cairosvg() -> ModuleType | None:
    """
    Import cairosvg, which the optional `svg` extra installs

    Returns
    -------
    :
        The module, or `None` when it is not installed or its Cairo library cannot be loaded.
    """
    try:
        return importlib.import_module("cairosvg")
    except (ImportError, OSError):
        return None


def _fit_to_square(img: Image.Image, size: int) -> Image.Image:
    """
    Centre an image on a transparent square canvas

    Parameters
    ----------
    img
        The image to fit. Its aspect ratio is preserved.
    size
        The side length of the canvas in pixels. A larger image is scaled down to fit.

    Returns
    -------
    :
        An RGBA image of `size` by `size` pixels.
    """
    from PIL import Image

    img = img.convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def _write_raster_icons(master: Image.Image, dest_dir: Path) -> dict[str, str]:
    """
    Write the PNG favicons and a multi-size `favicon.ico`

    Parameters
    ----------
    master
        A square image at least as large as the largest favicon.
    dest_dir
        The directory to write into.

    Returns
    -------
    :
        The file name of each icon, keyed by purpose in this order: `icon-16`, `icon-32`,
        `apple-touch-icon`, then `icon` for the ICO.
    """
    from PIL import Image

    icons: dict[str, str] = {}
    for purpose, name, size in _RASTER_ICONS:
        master.resize((size, size), Image.Resampling.LANCZOS).save(dest_dir / name, "PNG")
        icons[purpose] = name
    master.save(dest_dir / "favicon.ico", format="ICO", sizes=_ICO_SIZES)
    icons["icon"] = "favicon.ico"
    return icons


def generate_favicons(
    logo_src: Path,
    dest_dir: Path,
    *,
    report: Callable[[str], None],
) -> dict[str, str]:
    """
    Write favicons generated from a logo image

    An SVG source is copied as `favicon.svg` and, when cairosvg and its Cairo library can be
    loaded, rasterised for the PNG and ICO favicons. A PNG source is resized to produce the
    PNG and ICO favicons. A non-square source is centred on a transparent square. Other
    source formats produce no favicons.

    Parameters
    ----------
    logo_src
        The SVG or PNG source image.
    dest_dir
        The existing directory to write the favicons into.
    report
        A callback that receives the lines naming the source, the files written, and how to
        install cairosvg when an SVG source cannot be rasterised.

    Returns
    -------
    :
        A mapping from purpose to file name for the favicons written. Possible keys are
        `icon`, `icon-svg`, `icon-16`, `icon-32` and `apple-touch-icon`. `icon` names the
        primary favicon and uses the ICO when one was written. Key order is stable.
    """
    from PIL import Image

    result: dict[str, str] = {}
    suffix = logo_src.suffix.lower()

    report(f"Favicon: generating from {logo_src.name}")

    if suffix == ".svg":
        # Modern browsers use the SVG favicon directly.
        _ = shutil.copy2(logo_src, dest_dir / "favicon.svg")
        result["icon-svg"] = "favicon.svg"
        result["icon"] = "favicon.svg"

        cairosvg = _import_cairosvg()
        if cairosvg is None:
            report(
                "Favicon: cairosvg is not installed; skipping raster favicon "
                "generation from SVG. Install it with:\n"
                "  pip install 'great-docs[svg]'\n"
                "On Linux you also need: apt install libcairo2-dev\n"
                "On macOS (see installation notes): brew install cairo"
            )
            return result

        png_data = cairosvg.svg2png(url=str(logo_src), scale=4)
        master = _fit_to_square(Image.open(io.BytesIO(png_data)), 512)
        result.update(_write_raster_icons(master, dest_dir))
    elif suffix == ".png":
        raw = Image.open(logo_src)
        result.update(_write_raster_icons(_fit_to_square(raw, max(raw.size)), dest_dir))

    if result:
        files = ", ".join(dict.fromkeys(result.values()))
        report(f"Favicon: created {files}")

    return result
