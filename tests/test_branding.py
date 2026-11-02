import io
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from great_docs._website import branding

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
    '<rect width="64" height="64" fill="#318BFC"/>'
    "</svg>"
)


def _write_png(path: Path, size: tuple[int, int]) -> Path:
    """
    Write an opaque PNG

    Parameters
    ----------
    path
        The file to write.
    size
        The width and height in pixels.

    Returns
    -------
    :
        The path written.
    """
    Image.new("RGBA", size, (255, 0, 0, 255)).save(path, "PNG")
    return path


@pytest.fixture
def fake_cairosvg() -> Iterator[None]:
    """
    Provide a cairosvg replacement that rasterises any SVG to an opaque 256 by 128 PNG

    The rectangular image lets tests check that SVG favicons are padded to squares.

    Returns
    -------
    :
        No value. The replacement module remains installed for the duration of the test.
    """
    module = types.ModuleType("cairosvg")

    def svg2png(**kwargs: object) -> bytes:
        buffer = io.BytesIO()
        Image.new("RGBA", (256, 128), (0, 0, 255, 255)).save(buffer, format="PNG")
        return buffer.getvalue()

    module.svg2png = svg2png  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"cairosvg": module}):
        yield


def test_detect_logo_finds_root_svg(tmp_path: Path):
    (tmp_path / "logo.svg").write_text(_SVG)

    assert branding.detect_logo(tmp_path, None) == {"light": "logo.svg", "dark": "logo.svg"}


def test_detect_logo_finds_png_in_assets(tmp_path: Path):
    (tmp_path / "assets").mkdir()
    _write_png(tmp_path / "assets" / "logo.png", (8, 8))

    result = branding.detect_logo(tmp_path, "pkg")

    assert result == {"light": "assets/logo.png", "dark": "assets/logo.png"}


def test_detect_logo_pairs_dark_variant(tmp_path: Path):
    (tmp_path / "logo.svg").write_text(_SVG)
    (tmp_path / "logo-dark.svg").write_text(_SVG)

    assert branding.detect_logo(tmp_path, None) == {"light": "logo.svg", "dark": "logo-dark.svg"}


def test_detect_logo_returns_none_without_candidates(tmp_path: Path):
    (tmp_path / "other.svg").write_text(_SVG)

    assert branding.detect_logo(tmp_path, "pkg") is None


@pytest.mark.parametrize("file_name", ["my-pkg_logo.svg", "my_pkg_logo.svg"])
def test_detect_logo_finds_package_name_variants(tmp_path: Path, file_name: str):
    (tmp_path / file_name).write_text(_SVG)

    result = branding.detect_logo(tmp_path, "my-pkg")

    assert result is not None
    assert result["light"] == file_name


def test_detect_logo_prefers_generic_name(tmp_path: Path):
    (tmp_path / "pkg_logo.svg").write_text(_SVG)
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.svg").write_text(_SVG)

    result = branding.detect_logo(tmp_path, "pkg")

    assert result is not None
    assert result["light"] == "assets/logo.svg"


def test_logo_candidates_without_package_name():
    candidates = branding.logo_candidates(None)

    assert not any("_logo" in candidate for candidate in candidates)
    assert candidates == branding.logo_candidates("")


def test_detect_hero_logo_finds_root_svg(tmp_path: Path):
    (tmp_path / "logo-hero.svg").write_text(_SVG)

    result = branding.detect_hero_logo(tmp_path)

    assert result == {"light": "logo-hero.svg", "dark": "logo-hero.svg"}


def test_detect_hero_logo_pairs_light_and_dark(tmp_path: Path):
    (tmp_path / "logo-hero-light.svg").write_text(_SVG)
    (tmp_path / "logo-hero-dark.svg").write_text(_SVG)

    result = branding.detect_hero_logo(tmp_path)

    assert result == {"light": "logo-hero-light.svg", "dark": "logo-hero-dark.svg"}


def test_detect_hero_logo_finds_png_in_assets(tmp_path: Path):
    (tmp_path / "assets").mkdir()
    _write_png(tmp_path / "assets" / "logo-hero.png", (8, 8))

    result = branding.detect_hero_logo(tmp_path)

    assert result is not None
    assert result["light"] == "assets/logo-hero.png"


def test_detect_hero_logo_ignores_navbar_logo(tmp_path: Path):
    (tmp_path / "logo.svg").write_text(_SVG)

    assert branding.detect_hero_logo(tmp_path) is None


@pytest.mark.parametrize(
    ("light", "dark"),
    [
        ("logo.svg", "logo-dark.svg"),
        ("assets/logo-light.png", "assets/logo-dark.png"),
        ("logo-hero-light.svg", "logo-hero-dark.svg"),
    ],
)
def test_dark_variant(light: str, dark: str):
    assert branding.dark_variant(light) == dark


@pytest.mark.usefixtures("fake_cairosvg")
def test_generate_favicons_from_svg(tmp_path: Path):
    svg = tmp_path / "logo.svg"
    svg.write_text(_SVG)
    dest = tmp_path / "out"
    dest.mkdir()
    lines: list[str] = []

    result = branding.generate_favicons(svg, dest, report=lines.append)

    # Key order determines the order of favicon files in the site's resources.
    assert list(result.items()) == [
        ("icon-svg", "favicon.svg"),
        ("icon", "favicon.ico"),
        ("icon-16", "favicon-16x16.png"),
        ("icon-32", "favicon-32x32.png"),
        ("apple-touch-icon", "apple-touch-icon.png"),
    ]
    assert (dest / "favicon.svg").read_text() == _SVG
    assert (dest / "favicon.ico").is_file()
    assert lines == [
        "Favicon: generating from logo.svg",
        "Favicon: created favicon.svg, favicon.ico, favicon-16x16.png, "
        "favicon-32x32.png, apple-touch-icon.png",
    ]


@pytest.mark.usefixtures("fake_cairosvg")
def test_generate_favicons_pads_svg_raster_to_squares(tmp_path: Path):
    svg = tmp_path / "logo.svg"
    svg.write_text(_SVG)

    branding.generate_favicons(svg, tmp_path, report=lambda line: None)

    for name, size in [
        ("favicon-16x16.png", 16),
        ("favicon-32x32.png", 32),
        ("apple-touch-icon.png", 180),
    ]:
        assert Image.open(tmp_path / name).size == (size, size)
    icon = Image.open(tmp_path / "apple-touch-icon.png")
    assert icon.getpixel((0, 0)) == (0, 0, 0, 0)
    assert icon.getpixel((90, 90)) == (0, 0, 255, 255)


def test_generate_favicons_from_svg_without_cairosvg(tmp_path: Path):
    svg = tmp_path / "logo.svg"
    svg.write_text(_SVG)
    dest = tmp_path / "out"
    dest.mkdir()
    lines: list[str] = []

    with patch.dict(sys.modules, {"cairosvg": None}):
        result = branding.generate_favicons(svg, dest, report=lines.append)

    assert result == {"icon-svg": "favicon.svg", "icon": "favicon.svg"}
    assert sorted(path.name for path in dest.iterdir()) == ["favicon.svg"]
    assert "cairosvg is not installed" in lines[1]
    assert len(lines) == 2


def test_generate_favicons_from_png(tmp_path: Path):
    png = _write_png(tmp_path / "logo.png", (200, 100))
    dest = tmp_path / "out"
    dest.mkdir()
    lines: list[str] = []

    result = branding.generate_favicons(png, dest, report=lines.append)

    assert list(result.items()) == [
        ("icon-16", "favicon-16x16.png"),
        ("icon-32", "favicon-32x32.png"),
        ("apple-touch-icon", "apple-touch-icon.png"),
        ("icon", "favicon.ico"),
    ]
    assert sorted(path.name for path in dest.iterdir()) == [
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon.ico",
    ]
    icon = Image.open(dest / "apple-touch-icon.png")
    assert icon.size == (180, 180)
    assert icon.getpixel((0, 0)) == (0, 0, 0, 0)
    assert icon.getpixel((90, 90)) == (255, 0, 0, 255)
    assert lines[-1] == (
        "Favicon: created favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png, favicon.ico"
    )


def test_generate_favicons_ignores_other_formats(tmp_path: Path):
    gif = tmp_path / "logo.gif"
    gif.write_text("not a gif")
    dest = tmp_path / "out"
    dest.mkdir()
    lines: list[str] = []

    result = branding.generate_favicons(gif, dest, report=lines.append)

    assert result == {}
    assert list(dest.iterdir()) == []
    assert lines == ["Favicon: generating from logo.gif"]
