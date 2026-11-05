from __future__ import annotations

from pathlib import Path

from great_docs._website.identity import Identity
from tests.support import write_config

GO_SETTINGS = "go_cli:\n  enabled: true\n"
RUST_SETTINGS = "rust_cli:\n  enabled: true\n"


def _write_go_program(root: Path) -> None:
    (root / "go.mod").write_text("module example.com/gotool\n", encoding="utf-8")
    (root / "main.go").write_text("package main\n", encoding="utf-8")


def _write_rust_program(root: Path) -> None:
    (root / "Cargo.toml").write_text('[package]\nname = "rusttool"\n', encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")


class TestName:
    def test_uses_the_display_name(self, tmp_path: Path):
        config = write_config(tmp_path, "display_name: Display\n")

        identity = Identity.make(config, tmp_path, None, None, "pkg")

        assert identity.name == "Display"

    def test_falls_back_to_the_package_name(self, tmp_path: Path):
        _write_go_program(tmp_path)
        config = write_config(tmp_path, GO_SETTINGS)

        identity = Identity.make(config, tmp_path, None, None, "pkg")

        assert identity.name == "pkg"

    def test_falls_back_to_the_go_program_name(self, tmp_path: Path):
        _write_go_program(tmp_path)
        _write_rust_program(tmp_path)
        config = write_config(tmp_path, GO_SETTINGS + RUST_SETTINGS)

        identity = Identity.make(config, tmp_path, None, None, None)

        assert identity.name == "gotool"

    def test_falls_back_to_the_rust_program_name(self, tmp_path: Path):
        _write_rust_program(tmp_path)
        config = write_config(tmp_path, GO_SETTINGS + RUST_SETTINGS)

        identity = Identity.make(config, tmp_path, None, None, None)

        assert identity.name == "rusttool"

    def test_ignores_programs_whose_reference_is_disabled(self, tmp_path: Path):
        _write_go_program(tmp_path)
        _write_rust_program(tmp_path)
        config = write_config(tmp_path)

        identity = Identity.make(config, tmp_path, None, None, None)

        assert identity.name == ""


class TestAddresses:
    def test_canonical_base_url_wins_over_site_url(self, tmp_path: Path):
        config = write_config(
            tmp_path,
            "site_url: https://served.example.com/pkg\n"
            "seo:\n  canonical:\n    base_url: https://preferred.example.com/pkg\n",
        )

        identity = Identity.make(config, tmp_path, "acme", "pkg", None)

        assert identity.url == "https://served.example.com/pkg"
        assert identity.base_url == "https://preferred.example.com/pkg/"

    def test_base_url_falls_back_to_github_pages(self, tmp_path: Path):
        config = write_config(tmp_path)

        identity = Identity.make(config, tmp_path, "acme", "pkg", None)

        assert identity.url is None
        assert identity.base_url == "https://acme.github.io/pkg/"
