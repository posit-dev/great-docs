from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._website.identity import Identity
from tests.support import write_config


def _write_quarto_yml(build_dir: Path, text: str) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "_quarto.yml").write_text(text, encoding="utf-8")


class TestName:
    def test_uses_the_site_title_from_quarto_yml(self, tmp_path):
        config = write_config(tmp_path, "display_name: Display\n")
        _write_quarto_yml(tmp_path / "build", "website:\n  title: Quarto Title\n")

        identity = Identity.make(config, tmp_path / "build", None, None, "pkg")

        assert identity.name == "Quarto Title"

    @pytest.mark.parametrize(
        "quarto_yml",
        [
            None,
            "website:\n  title: ''\n",
            "website:\n  title: 3\n",
            "website: [not, a, mapping]\n",
            "website: {unclosed\n",
        ],
        ids=["missing", "empty-title", "non-string-title", "non-mapping-website", "invalid"],
    )
    def test_falls_back_to_the_display_name(self, tmp_path, quarto_yml):
        config = write_config(tmp_path, "display_name: Display\n")
        if quarto_yml is not None:
            _write_quarto_yml(tmp_path / "build", quarto_yml)

        identity = Identity.make(config, tmp_path / "build", None, None, "pkg")

        assert identity.name == "Display"

    def test_falls_back_to_the_package_name(self, tmp_path):
        config = write_config(tmp_path)

        identity = Identity.make(config, tmp_path / "build", None, None, "pkg")

        assert identity.name == "pkg"

    def test_is_empty_without_any_source(self, tmp_path):
        config = write_config(tmp_path)

        identity = Identity.make(config, tmp_path / "build", None, None, None)

        assert identity.name == ""


class TestAddresses:
    def test_canonical_base_url_wins_over_site_url(self, tmp_path):
        config = write_config(
            tmp_path,
            "site_url: https://served.example.com/pkg\n"
            "seo:\n  canonical:\n    base_url: https://preferred.example.com/pkg\n",
        )

        identity = Identity.make(config, tmp_path / "build", "acme", "pkg", None)

        assert identity.url == "https://served.example.com/pkg"
        assert identity.base_url == "https://preferred.example.com/pkg/"

    def test_base_url_falls_back_to_github_pages(self, tmp_path):
        config = write_config(tmp_path)

        identity = Identity.make(config, tmp_path / "build", "acme", "pkg", None)

        assert identity.url is None
        assert identity.base_url == "https://acme.github.io/pkg/"
