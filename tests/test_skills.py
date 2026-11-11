"""
Tests for the skill files and Skills page that `skill.skills` publishes
"""

import contextlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from great_docs._build import generated
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
    docs.layout.build_dir.mkdir()

    SkillsWriter(
        docs._config,
        docs.layout,
        make_project(docs).name,
        make_project(docs).manifest,
    ).write(None)

    page = (docs.layout.build_dir / "skills.qmd").read_text(encoding="utf-8")
    assert 'href="skill.md"' in page
    assert (docs.layout.build_dir / "skill.md").read_text(encoding="utf-8") == reviewing.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(("well_known", "published"), [(True, True), (False, False)])
def test_the_skills_step_records_whether_it_published_the_index(
    tmp_path: Path, well_known: bool, published: bool
):
    _ = (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
    _ = (tmp_path / "great-docs.yml").write_text(
        f"skill:\n  well_known: {str(well_known).lower()}\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))
    docs.layout.build_dir.mkdir()
    project = make_project(docs)
    run = SimpleNamespace(project=project, api_block=None, has_skills=False)

    with contextlib.redirect_stdout(io.StringIO()):
        _ = generated.skills(run, docs._config, docs.layout)  # type: ignore[arg-type]

    assert run.has_skills is published
