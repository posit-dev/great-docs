"""
Base addresses, page addresses and canonical-link registration
"""

from pathlib import Path

import pytest

from great_docs._website import page_url
from great_docs.config import Config
from tests.support import write_config


class TestResolveBaseUrl:
    def test_base_url_alone(self, tmp_path):
        config = write_config(
            tmp_path, "seo:\n  canonical:\n    base_url: https://docs.example.com/pkg\n"
        )
        assert page_url.resolve_base_url(config, None, None) == "https://docs.example.com/pkg/"

    def test_base_url_overrides_site_url(self, tmp_path):
        config = write_config(
            tmp_path,
            "site_url: https://docs.example.com/pkg\n"
            "seo:\n  canonical:\n    base_url: https://example.org/docs\n",
        )
        assert page_url.resolve_base_url(config, "acme", "pkg") == "https://example.org/docs/"

    def test_site_url_beats_github(self, tmp_path):
        config = write_config(tmp_path, "site_url: https://docs.example.com/pkg/\n")
        assert page_url.resolve_base_url(config, "acme", "pkg") == "https://docs.example.com/pkg/"

    def test_github_when_nothing_is_configured(self, tmp_path):
        assert (
            page_url.resolve_base_url(write_config(tmp_path), "acme", "pkg")
            == "https://acme.github.io/pkg/"
        )

    def test_none_without_a_repository(self, tmp_path):
        assert page_url.resolve_base_url(write_config(tmp_path), None, None) is None


@pytest.mark.parametrize(
    ("page_path", "expected"),
    [
        ("index.html", "https://x.test/pkg/"),
        ("guide/index.html", "https://x.test/pkg/guide/"),
        ("guide/page.html", "https://x.test/pkg/guide/page.html"),
        ("myindex.html", "https://x.test/pkg/myindex.html"),
    ],
)
def test_address(page_path, expected):
    assert page_url.address("https://x.test/pkg/", page_path) == expected


class TestRegister:
    BASE = "https://docs.example.com/pkg/"

    def test_adds_the_filter_and_base_url(self, tmp_path):
        quarto: dict = {"filters": ["interlinks"]}
        page_url.register(quarto, write_config(tmp_path), self.BASE, tmp_path, og_url=False)
        assert quarto["filters"] == ["interlinks", "page-url"]
        assert quarto["gd-base-url"] == self.BASE
        assert quarto["gd-canonical"] is True
        assert quarto["gd-og-url"] is False

    @pytest.mark.parametrize("canonical", [True, False])
    @pytest.mark.parametrize("og_url", [True, False])
    def test_writes_each_switch(self, tmp_path, canonical, og_url):
        yaml = "" if canonical else "seo:\n  canonical:\n    enabled: false\n"
        quarto: dict = {}
        page_url.register(quarto, write_config(tmp_path, yaml), self.BASE, tmp_path, og_url=og_url)
        if not (canonical or og_url):
            assert quarto == {}
            return
        assert quarto["filters"] == ["page-url"]
        assert quarto["gd-canonical"] is canonical
        assert quarto["gd-og-url"] is og_url

    def test_og_url_without_seo(self, tmp_path):
        quarto: dict = {}
        config = write_config(tmp_path, "seo:\n  enabled: false\n")
        page_url.register(quarto, config, self.BASE, tmp_path, og_url=True)
        assert quarto["gd-canonical"] is False
        assert quarto["gd-og-url"] is True

    def test_registers_once(self, tmp_path):
        quarto: dict = {"filters": ["page-url"]}
        page_url.register(quarto, write_config(tmp_path), self.BASE, tmp_path, og_url=False)
        assert quarto["filters"] == ["page-url"]

    def test_disabled(self, tmp_path):
        config = write_config(tmp_path, "seo:\n  canonical:\n    enabled: false\n")
        quarto: dict = {"filters": []}
        page_url.register(quarto, config, self.BASE, tmp_path, og_url=False)
        assert quarto == {"filters": []}

    def test_without_a_base_url(self, tmp_path):
        quarto: dict = {}
        page_url.register(quarto, write_config(tmp_path), None, tmp_path, og_url=False)
        assert quarto == {}

    @pytest.mark.parametrize("as_file", [False, True])
    def test_keeps_a_canonical_link_from_the_site_header(self, tmp_path, as_file):
        link = '<link rel="canonical" href="https://example.org/custom">'
        if as_file:
            (tmp_path / "head.html").write_text(link, encoding="utf-8")
            entry: str | dict = "head.html"
        else:
            entry = {"text": link}
        quarto: dict = {"format": {"html": {"include-in-header": [entry]}}}
        page_url.register(quarto, write_config(tmp_path), self.BASE, tmp_path, og_url=False)
        assert "filters" not in quarto
        assert "gd-base-url" not in quarto

    def test_keeps_og_url_when_the_site_header_has_a_canonical_link(self, tmp_path):
        link = '<link rel="canonical" href="https://example.org/custom">'
        quarto: dict = {"format": {"html": {"include-in-header": [{"text": link}]}}}
        page_url.register(quarto, write_config(tmp_path), self.BASE, tmp_path, og_url=True)
        assert quarto["gd-canonical"] is False
        assert quarto["gd-og-url"] is True


class TestAddToRawPage:
    BASE = "https://docs.example.com/pkg/"
    HTML = "<html><head><title>W</title></head><body></body></html>"

    def test_adds_a_link_at_the_page_address(self, tmp_path):
        page = page_url.add_to_raw_page(
            self.HTML, write_config(tmp_path), self.BASE, "demos/w.html"
        )
        assert (
            '<link rel="canonical" href="https://docs.example.com/pkg/demos/w.html">\n</head>'
            in page
        )

    def test_keeps_an_existing_link(self, tmp_path):
        html = '<html><head><link rel="canonical" href="https://x.test/"></head></html>'
        page = page_url.add_to_raw_page(html, write_config(tmp_path), self.BASE, "w.html")
        assert page == html

    def test_leaves_a_fragment_unchanged(self, tmp_path):
        page = page_url.add_to_raw_page("<div>W</div>", write_config(tmp_path), self.BASE, "w.html")
        assert page == "<div>W</div>"

    def test_without_a_base_url(self, tmp_path):
        assert (
            page_url.add_to_raw_page(self.HTML, write_config(tmp_path), None, "w.html") == self.HTML
        )

    def test_disabled(self, tmp_path):
        config = write_config(tmp_path, "seo:\n  canonical:\n    enabled: false\n")
        assert page_url.add_to_raw_page(self.HTML, config, self.BASE, "w.html") == self.HTML
