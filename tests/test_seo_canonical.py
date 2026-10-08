"""
Canonical links: base address, page addresses, registration and raw pages
"""

from pathlib import Path

import pytest

from great_docs._website.seo import canonical
from great_docs.config import Config


def _config(tmp_path: Path, yaml: str = "") -> Config:
    (tmp_path / "great-docs.yml").write_text(yaml, encoding="utf-8")
    return Config(tmp_path)


class TestResolveBaseUrl:
    def test_base_url_alone(self, tmp_path):
        config = _config(
            tmp_path, "seo:\n  canonical:\n    base_url: https://docs.example.com/pkg\n"
        )
        assert canonical.resolve_base_url(config, None, None) == "https://docs.example.com/pkg/"

    def test_base_url_overrides_site_url(self, tmp_path):
        config = _config(
            tmp_path,
            "site_url: https://docs.example.com/pkg\n"
            "seo:\n  canonical:\n    base_url: https://example.org/docs\n",
        )
        assert canonical.resolve_base_url(config, "acme", "pkg") == "https://example.org/docs/"

    def test_site_url_beats_github(self, tmp_path):
        config = _config(tmp_path, "site_url: https://docs.example.com/pkg/\n")
        assert canonical.resolve_base_url(config, "acme", "pkg") == "https://docs.example.com/pkg/"

    def test_github_when_nothing_is_configured(self, tmp_path):
        assert (
            canonical.resolve_base_url(_config(tmp_path), "acme", "pkg")
            == "https://acme.github.io/pkg/"
        )

    def test_none_without_a_repository(self, tmp_path):
        assert canonical.resolve_base_url(_config(tmp_path), None, None) is None


@pytest.mark.parametrize(
    ("page_path", "expected"),
    [
        ("index.html", "https://x.test/pkg/"),
        ("guide/index.html", "https://x.test/pkg/guide/"),
        ("guide/page.html", "https://x.test/pkg/guide/page.html"),
        ("myindex.html", "https://x.test/pkg/myindex.html"),
    ],
)
def test_page_url(page_path, expected):
    assert canonical.page_url("https://x.test/pkg/", page_path) == expected


class TestRegister:
    BASE = "https://docs.example.com/pkg/"

    def test_adds_the_filter_and_base_url(self, tmp_path):
        quarto: dict = {"filters": ["interlinks"]}
        canonical.register(quarto, _config(tmp_path), self.BASE)
        assert quarto["filters"] == ["interlinks", "canonical"]
        assert quarto["gd-canonical-base-url"] == self.BASE

    def test_registers_once(self, tmp_path):
        quarto: dict = {"filters": ["canonical"]}
        canonical.register(quarto, _config(tmp_path), self.BASE)
        assert quarto["filters"] == ["canonical"]

    def test_disabled(self, tmp_path):
        config = _config(tmp_path, "seo:\n  canonical:\n    enabled: false\n")
        quarto: dict = {"filters": []}
        canonical.register(quarto, config, self.BASE)
        assert quarto == {"filters": []}

    def test_without_a_base_url(self, tmp_path):
        quarto: dict = {}
        canonical.register(quarto, _config(tmp_path), None)
        assert quarto == {}

    def test_unregister_reverses_register(self, tmp_path):
        quarto: dict = {"filters": ["interlinks"]}
        canonical.register(quarto, _config(tmp_path), self.BASE)
        canonical.unregister(quarto)
        assert quarto == {"filters": ["interlinks"]}


class TestAddToRawPage:
    BASE = "https://docs.example.com/pkg/"
    HTML = "<html><head><title>W</title></head><body></body></html>"

    def test_adds_a_link_at_the_page_address(self, tmp_path):
        page = canonical.add_to_raw_page(self.HTML, _config(tmp_path), self.BASE, "demos/w.html")
        assert (
            '<link rel="canonical" href="https://docs.example.com/pkg/demos/w.html">\n</head>'
            in page
        )

    def test_keeps_an_existing_link(self, tmp_path):
        html = '<html><head><link rel="canonical" href="https://x.test/"></head></html>'
        page = canonical.add_to_raw_page(html, _config(tmp_path), self.BASE, "w.html")
        assert page == html

    def test_leaves_a_fragment_unchanged(self, tmp_path):
        page = canonical.add_to_raw_page("<div>W</div>", _config(tmp_path), self.BASE, "w.html")
        assert page == "<div>W</div>"

    def test_without_a_base_url(self, tmp_path):
        assert canonical.add_to_raw_page(self.HTML, _config(tmp_path), None, "w.html") == self.HTML

    def test_disabled(self, tmp_path):
        config = _config(tmp_path, "seo:\n  canonical:\n    enabled: false\n")
        assert canonical.add_to_raw_page(self.HTML, config, self.BASE, "w.html") == self.HTML
