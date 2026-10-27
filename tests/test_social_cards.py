from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._website import social_cards
from great_docs.config import Config


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    return tmp_path


def _make_config(tmp_path: Path, yaml_text: str) -> Config:
    (tmp_path / "great-docs.yml").write_text(yaml_text, encoding="utf-8")
    return Config(tmp_path)


class TestSocialCardsConfig:
    """Config property tests for social_cards."""

    def test_default_enabled(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_enabled is True

    def test_enabled_true_shorthand(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: true\n")
        assert cfg.social_cards_enabled is True

    def test_disabled_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: false\n")
        assert cfg.social_cards_enabled is False

    def test_disabled_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: null\n")
        assert cfg.social_cards_enabled is False

    def test_dict_enabled_true(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  enabled: true\n")
        assert cfg.social_cards_enabled is True

    def test_dict_enabled_false(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  enabled: false\n")
        assert cfg.social_cards_enabled is False

    def test_dict_defaults_to_enabled(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  image: assets/og.png\n")
        assert cfg.social_cards_enabled is True

    def test_image_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_image is None

    def test_image_custom(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards:\n  image: assets/social.png\n")
        assert cfg.social_cards_image == "assets/social.png"

    def test_twitter_card_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_twitter_card is None

    def test_twitter_card_custom(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            "social_cards:\n  twitter_card: summary\n",
        )
        assert cfg.social_cards_twitter_card == "summary"

    def test_twitter_site_default_none(self, tmp_project: Path):
        cfg = Config(tmp_project)
        assert cfg.social_cards_twitter_site is None

    def test_twitter_site_custom(self, tmp_project: Path):
        cfg = _make_config(
            tmp_project,
            'social_cards:\n  twitter_site: "@myhandle"\n',
        )
        assert cfg.social_cards_twitter_site == "@myhandle"

    def test_shorthand_true_image_is_none(self, tmp_project: Path):
        cfg = _make_config(tmp_project, "social_cards: true\n")
        assert cfg.social_cards_image is None
        assert cfg.social_cards_twitter_site is None


class TestRegister:
    """Site defaults for Open Graph and Twitter cards"""

    IMAGE = "https://docs.example.com/pkg/card.png"

    def test_enables_both_without_options(self, tmp_path: Path):
        quarto: dict = {}
        social_cards.register(quarto, Config(tmp_path), None, tmp_path)
        assert quarto["website"] == {"open-graph": True, "twitter-card": True}

    def test_image_and_twitter_options(self, tmp_path: Path):
        config = _make_config(
            tmp_path, "social_cards:\n  twitter_site: myhandle\n  twitter_card: summary\n"
        )
        quarto: dict = {"website": {"title": "Pkg"}}
        social_cards.register(quarto, config, self.IMAGE, tmp_path)
        assert quarto["website"] == {
            "title": "Pkg",
            "open-graph": {"image": self.IMAGE},
            "twitter-card": {"image": self.IMAGE, "card-style": "summary", "site": "@myhandle"},
        }

    def test_keeps_an_at_sign(self, tmp_path: Path):
        config = _make_config(tmp_path, 'social_cards:\n  twitter_site: "@myhandle"\n')
        quarto: dict = {}
        social_cards.register(quarto, config, None, tmp_path)
        assert quarto["website"]["twitter-card"] == {"site": "@myhandle"}

    def test_disabled(self, tmp_path: Path):
        quarto: dict = {}
        social_cards.register(
            quarto, _make_config(tmp_path, "social_cards: false\n"), None, tmp_path
        )
        assert quarto == {}

    def test_independent_of_seo(self, tmp_path: Path):
        quarto: dict = {}
        config = _make_config(tmp_path, "seo:\n  enabled: false\n")
        social_cards.register(quarto, config, None, tmp_path)
        assert quarto["website"]["open-graph"] is True

    @pytest.mark.parametrize("as_file", [False, True])
    def test_keeps_open_graph_tags_from_the_site_header(self, tmp_path: Path, as_file: bool):
        tag = '<meta property="og:title" content="Mine">'
        if as_file:
            (tmp_path / "head.html").write_text(tag, encoding="utf-8")
            entry: str | dict = "head.html"
        else:
            entry = {"text": tag}
        quarto: dict = {"format": {"html": {"include-in-header": [entry]}}}
        social_cards.register(quarto, Config(tmp_path), self.IMAGE, tmp_path)
        assert "website" not in quarto
        assert not social_cards.applies(quarto, Config(tmp_path), tmp_path)


class TestAddToRawPage:
    """Social card metadata for pages that bypass Quarto"""

    HEAD = "<html><head>{}</head><body></body></html>"

    def _add(self, tmp_path: Path, page: str, yaml: str = "", **kwargs) -> str:
        options = {"site_name": "Pkg", "default": "Default", "url": None, "image_url": None}
        options.update(kwargs)
        return social_cards.add_to_raw_page(page, _make_config(tmp_path, yaml), **options)

    def test_takes_the_page_title_and_description(self, tmp_path: Path):
        page = self.HEAD.format(
            '<title>A &amp; "B"</title><meta name="description" content="Mine &lt;3">'
        )
        result = self._add(tmp_path, page)
        assert '<meta property="og:title" content="A &amp; &quot;B&quot;">' in result
        assert '<meta name="twitter:description" content="Mine &lt;3">' in result

    def test_falls_back_to_the_site(self, tmp_path: Path):
        result = self._add(tmp_path, self.HEAD.format(""))
        assert '<meta property="og:title" content="Pkg">' in result
        assert '<meta property="og:description" content="Default">' in result
        assert "og:url" not in result

    def test_image_url_and_handle(self, tmp_path: Path):
        result = self._add(
            tmp_path,
            self.HEAD.format(""),
            "social_cards:\n  twitter_site: myhandle\n",
            url="https://x.test/w.html",
            image_url="https://x.test/card.png",
        )
        assert '<meta property="og:url" content="https://x.test/w.html">' in result
        assert '<meta property="og:image" content="https://x.test/card.png">' in result
        assert '<meta name="twitter:card" content="summary_large_image">' in result
        assert '<meta name="twitter:site" content="@myhandle">' in result

    def test_keeps_a_page_with_its_own_tags(self, tmp_path: Path):
        page = self.HEAD.format('<meta property="og:title" content="Mine">')
        assert self._add(tmp_path, page) == page

    def test_disabled(self, tmp_path: Path):
        page = self.HEAD.format("")
        assert self._add(tmp_path, page, "social_cards: false\n") == page
