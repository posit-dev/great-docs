"""Protect generated homepage links without accepting unrelated missing pages"""

from pathlib import Path

import pytest

from great_docs._layout import Layout
from great_docs._layout_migration import analyse, apply


@pytest.mark.parametrize("suffix", ["qmd", "html"])
def test_readme_homepage_keeps_published_identity(tmp_path: Path, suffix: str) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "sample"\n')
    (tmp_path / "great-docs.yml").write_text("module: sample\n")
    (tmp_path / "README.md").write_text("# Home\n")
    guide = tmp_path / "user_guide"
    guide.mkdir()
    original = f"[Home](../index.{suffix}?view=full#intro)\n"
    (guide / "01-guide.qmd").write_text(original)
    proposal = analyse(Layout.make(tmp_path), tmp_path / "docs")
    assert not proposal.blockers, proposal.blockers
    apply(proposal)
    assert (tmp_path / "docs/user_guide/01-guide.qmd").read_text() == original
    assert (tmp_path / "README.md").read_text() == "# Home\n"


@pytest.mark.parametrize(
    "target, readme",
    [("../index.qmd", False), ("../other/index.qmd", True), ("../missing.qmd", True)],
)
def test_missing_page_still_blocks(tmp_path: Path, target: str, readme: bool) -> None:
    (tmp_path / "great-docs.yml").write_text("module: sample\n")
    if readme:
        (tmp_path / "README.md").write_text("# Home\n")
    guide = tmp_path / "user_guide"
    guide.mkdir()
    original = f"[Missing]({target})\n"
    (guide / "01-guide.qmd").write_text(original)
    proposal = analyse(Layout.make(tmp_path), tmp_path / "docs")
    assert proposal.blockers
    assert (guide / "01-guide.qmd").read_text() == original
    assert not (tmp_path / "docs").exists()


def test_authored_homepage_takes_precedence(tmp_path: Path) -> None:
    (tmp_path / "great-docs.yml").write_text("module: sample\n")
    (tmp_path / "README.md").write_text("# Fallback\n")
    (tmp_path / "index.qmd").write_text("# Authored\n")
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "01-guide.qmd").write_text("[Home](../index.qmd)\n")
    proposal = analyse(Layout.make(tmp_path), tmp_path / "docs")
    assert not proposal.blockers, proposal.blockers
    apply(proposal)
    assert (tmp_path / "docs/index.qmd").read_text() == "# Authored\n"
    assert (tmp_path / "docs/user_guide/01-guide.qmd").read_text() == "[Home](../index.qmd)\n"
    assert (tmp_path / "README.md").read_text() == "# Fallback\n"
