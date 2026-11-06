"""
Tests for the skill files and Skills page that `skill.skills` publishes
"""

from pathlib import Path

from great_docs._website.ai_agents.skills import SkillsWriter
from great_docs.core import GreatDocs
from tests.support import make_project


def test_skill_md_comes_from_first_published_skill_when_first_entry_is_skipped(tmp_path: Path):
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
    reviewing = tmp_path / "skills" / "reviewing" / "SKILL.md"
    reviewing.parent.mkdir(parents=True)
    _ = reviewing.write_text("---\nname: reviewing\n---\n\n# Reviewing\n")
    _ = (tmp_path / "great-docs.yml").write_text(
        "skill:\n"
        "  skills:\n"
        "    - name: authoring\n"
        "      file: skills/authoring/SKILL.md\n"
        "    - name: reviewing\n"
        "      file: skills/reviewing/SKILL.md\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir()

    SkillsWriter(
        docs._config,
        docs.layout,
        make_project(docs).name,
        make_project(docs).manifest,
    ).write(None)

    page = (docs.build_dir / "skills.qmd").read_text(encoding="utf-8")
    assert 'href="skill.md"' in page
    assert (docs.build_dir / "skill.md").read_text(encoding="utf-8") == reviewing.read_text(
        encoding="utf-8"
    )
