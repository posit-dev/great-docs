import shlex
from pathlib import Path

import pytest

from great_docs._layout import Layout
from great_docs._layout_migration.model import MigrationError
from great_docs._layout_notice import layout_notice
from great_docs.cli import cli


def project(root: Path) -> Path:
    (root / "pyproject.toml").write_text('[project]\nname = "sample"\nversion = "0.1"\n')
    (root / "great-docs.yml").write_text("reference: false\n")
    (root / "index.qmd").write_text("# Home\n")
    return root


def test_clean_root_notice_gives_an_applicable_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    root = tmp_path / "repo with spaces"
    root.mkdir()
    project(root)
    notice = layout_notice(Layout.make(root))

    assert notice is not None
    assert "great-docs migrate-layout" in notice
    assert "--project-path" in notice
    assert "--config" in notice
    assert "--to docs" in notice
    assert "Ask a coding agent" not in notice

    command = next(line for line in notice.splitlines() if line.startswith("great-docs "))
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli, [*shlex.split(command)[1:], "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Dry run complete" in result.output


def test_clean_root_notice_handles_directory_link_to_package_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    project(root)
    (root / "great-docs.yml").write_text("reference: false\nuser_guide: user_guide\n")
    (root / "user_guide").mkdir()
    (root / "user_guide" / "page.qmd").write_text("[Home](../)\n")

    notice = layout_notice(Layout.make(root))

    assert notice is not None
    assert "Migration check could not complete" not in notice
    assert "great-docs migrate-layout" in notice


def test_blocked_notice_gives_agent_prompt_and_selected_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    root = project(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("Other content\n")
    (root / "great-docs.yml").write_text("reference: false\nuser_guide: missing\n")
    before = (root / "great-docs.yml").read_bytes()

    notice = layout_notice(Layout.make(root))

    assert notice is not None
    assert "--to docs-website" in notice
    assert "Run the complete dry run" in notice
    assert "every blocker" in notice
    assert "Ask the repository owner" in notice
    assert "normal confirmation" in notice
    assert (root / "great-docs.yml").read_bytes() == before
    assert not (root / "docs-website").exists()

    command = next(line for line in notice.splitlines() if line.startswith("great-docs "))
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli, shlex.split(command)[1:])
    assert result.exit_code != 0
    assert "Documentation source does not exist" in result.output


def test_non_root_layout_has_no_notice(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "great-docs.yml").rename(root / "root-config.yml")
    (root / "docs").mkdir()
    (root / "docs" / "great-docs.yml").write_text("reference: false\n")

    assert layout_notice(Layout.make(root)) is None


def test_analysis_error_gives_diagnostic_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)

    def fail(_layout: Layout) -> Path:
        raise MigrationError("Cannot inspect ignore policy")

    monkeypatch.setattr("great_docs._layout_notice.select_destination", fail)
    notice = layout_notice(Layout.make(root))

    assert notice is not None
    assert "Migration check could not complete" in notice
    assert "--dry-run" in notice
    assert "Cannot inspect ignore policy" in notice
    assert "safe to migrate" not in notice


def test_analysis_error_keeps_a_selected_fallback_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    (root / "docs").mkdir()
    (root / "docs" / "README.md").write_text("Other content\n")

    def fail(_layout: Layout, _destination: Path) -> None:
        raise MigrationError("Cannot inspect source")

    monkeypatch.setattr("great_docs._layout_notice.analyse", fail)
    notice = layout_notice(Layout.make(root))

    assert notice is not None
    assert "--to docs-website --dry-run" in notice
