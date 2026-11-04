"""
Tests for the site's brand: its title, logo, favicons, GitHub entry and latest release
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from great_docs._build.facts import Facts
from great_docs._github import GithubRepo
from great_docs._layout import Layout
from great_docs._website.identity import Identity
from great_docs._website.navigation import brand
from great_docs._website.navigation.release import Release
from tests.support import write_config

REPO = GithubRepo(owner="owner", name="repo")
IDENTITY = Identity(name="Pkg", url=None, base_url=None)


def _register(
    root: Path,
    settings: str = "",
    quarto_config: dict[str, Any] | None = None,
    *,
    identity: Identity = IDENTITY,
    repo: GithubRepo | None = None,
    facts: Facts | None = None,
    documentation_url: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Configure branding for a project named `pkg`

    Parameters
    ----------
    root
        The project directory.
    settings
        The contents of `great-docs.yml`.
    quarto_config
        The configuration to update, by default one with an empty HTML format.
    identity
        The site's name and address.
    repo
        The project's GitHub repository.
    facts
        The fetched GitHub data, or empty facts by default.
    documentation_url
        The project's documentation address.

    Returns
    -------
    :
        The updated Quarto configuration and reported messages.
    """
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    config = write_config(root, settings)
    layout = Layout.make(root)
    layout.build_dir.mkdir(parents=True, exist_ok=True)
    if quarto_config is None:
        quarto_config = {"project": {"type": "website"}, "format": {"html": {}}}
    reports: list[str] = []
    brand.register(
        quarto_config,
        config,
        layout,
        layout.build_dir,
        identity=identity,
        package_name="pkg",
        repo=repo,
        facts=facts or Facts(),
        documentation_url=documentation_url,
        report=reports.append,
    )
    return quarto_config, reports


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 64), (200, 30, 30, 255)).save(path, "PNG")


def _headers(quarto_config: dict[str, Any]) -> list[str]:
    headers = quarto_config["format"]["html"].get("include-in-header", [])
    return [entry["text"] for entry in headers]


class TestSite:
    def test_takes_the_address_and_title_from_the_identity(self, tmp_path: Path):
        identity = Identity(name="Pkg", url="https://example.org/pkg/", base_url=None)

        quarto_config, _ = _register(tmp_path, identity=identity)

        website = quarto_config["website"]
        assert website["site-url"] == "https://example.org/pkg/"
        assert website["page-navigation"] is True
        assert website["title"] == "Pkg"

    def test_keeps_the_title_and_page_navigation_already_set(self, tmp_path: Path):
        quarto_config: dict[str, Any] = {
            "website": {"title": "Mine", "page-navigation": False},
            "format": {"html": {}},
        }

        _register(tmp_path, quarto_config=quarto_config)

        assert quarto_config["website"]["title"] == "Mine"
        assert quarto_config["website"]["page-navigation"] is False


class TestNavbar:
    def test_creates_the_navbar_with_the_github_widget(self, tmp_path: Path):
        facts = Facts(github_stats={"stars": 5, "forks": 2})

        quarto_config, _ = _register(tmp_path, repo=REPO, facts=facts)

        navbar = quarto_config["website"]["navbar"]
        assert navbar["left"] == []
        [item] = navbar["right"]
        assert item["href"] == "https://github.com/owner/repo"
        assert 'data-stars="5"' in item["text"]

    def test_replaces_the_github_entry_and_drops_a_home_link(self, tmp_path: Path):
        reference = {"text": "Reference", "href": "reference/index.qmd"}
        quarto_config: dict[str, Any] = {
            "website": {
                "navbar": {
                    "left": [{"text": "Home", "href": "index.qmd"}, reference],
                    "right": [{"icon": "github", "href": "https://github.com/old/repo"}],
                }
            },
            "format": {"html": {}},
        }

        _register(tmp_path, "github_style: icon\n", quarto_config, repo=REPO)

        navbar = quarto_config["website"]["navbar"]
        assert navbar["left"] == [reference]
        assert navbar["right"] == [{"icon": "github", "href": "https://github.com/owner/repo"}]


class TestLogo:
    def test_replaces_the_title_with_the_logo_and_its_dark_variant(self, tmp_path: Path):
        _write_png(tmp_path / "assets" / "logo.png")
        _write_png(tmp_path / "assets" / "logo-dark.png")

        quarto_config, _ = _register(
            tmp_path, "logo:\n  light: assets/logo.png\n  dark: assets/logo-dark.png\n"
        )

        build_dir = tmp_path / "great-docs"
        navbar = quarto_config["website"]["navbar"]
        assert (navbar["logo"], navbar["logo-dark"]) == ("logo.png", "logo-dark.png")
        assert (build_dir / "logo.png").is_file() and (build_dir / "logo-dark.png").is_file()
        assert navbar["logo-alt"] == "pkg"
        assert navbar["title"] is False
        assert "logo-dark.png" in quarto_config["project"]["resources"]
        assert '<meta name="gd-logo-dark" content="logo-dark.png">' in _headers(quarto_config)

    def test_reports_a_missing_logo(self, tmp_path: Path):
        _, reports = _register(tmp_path, "logo:\n  light: missing.png\n")

        assert reports == [f"Warning: Logo file not found: {tmp_path / 'missing.png'}"]


class TestFavicons:
    def test_generates_favicons_from_the_logo_with_absolute_links(self, tmp_path: Path):
        _write_png(tmp_path / "logo.png")

        quarto_config, _ = _register(
            tmp_path, "logo: logo.png\n", documentation_url="https://example.org/docs#top"
        )

        assert quarto_config["website"]["favicon"] == "favicon.ico"
        assert "favicon.ico" in quarto_config["project"]["resources"]
        assert (tmp_path / "great-docs" / "favicon.ico").is_file()
        assert (
            '<link rel="icon" type="image/x-icon" href="https://example.org/docs/favicon.ico" '
            'sizes="48x48">'
        ) in _headers(quarto_config)

    def test_writes_no_links_without_a_site_address(self, tmp_path: Path):
        _write_png(tmp_path / "logo.png")

        quarto_config, _ = _register(tmp_path, "logo: logo.png\n")

        assert quarto_config["website"]["favicon"] == "favicon.ico"
        assert not any('rel="icon"' in text for text in _headers(quarto_config))

    def test_uses_the_configured_favicon_without_a_logo(self, tmp_path: Path):
        _write_png(tmp_path / "assets" / "icon.png")

        quarto_config, _ = _register(
            tmp_path, "favicon: assets/icon.png\n", documentation_url="https://example.org/"
        )

        assert quarto_config["website"]["favicon"] == "favicon.ico"
        assert "favicon.ico" in quarto_config["project"]["resources"]
        assert (
            '<link rel="icon" type="image/x-icon" href="https://example.org/favicon.ico" '
            'sizes="48x48">'
        ) in _headers(quarto_config)
        assert "logo" not in quarto_config["website"]["navbar"]


class TestRelease:
    def test_shows_the_latest_release_beside_the_title(self, tmp_path: Path):
        quarto_config: dict[str, Any] = {
            "website": {"title": "Pkg", "navbar": {}},
            "format": {"html": {}},
        }
        facts = Facts(latest_release=Release(version="1.2.0", date=None))

        brand.register_release(quarto_config, write_config(tmp_path), facts)

        assert "v1.2.0" in quarto_config["website"]["navbar"]["title"]
