"""
Publish skills at stable discovery paths for agent installers
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path

from ..._yaml import split_front_matter

WELL_KNOWN_ROOT = ".well-known/agent-skills"
INDEX_FILE = "index.json"
SKILL_FILE = "SKILL.md"
LEGACY_DIR = ".well-known/skills/default"


def companion_files(skill_dir: Path) -> list[Path]:
    """
    List a skill's companion files relative to its directory

    Include files at any depth under `skill_dir`, except files named `SKILL.md`
    and files with a path component starting with `.`. The Skills page and the
    published `.well-known` copy include the same companion files.

    Parameters
    ----------
    skill_dir
        Directory containing the skill and its companion files, separate from shared
        project files.

    Returns
    -------
    :
        Sorted paths relative to `skill_dir`.
    """
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        rel = path.relative_to(skill_dir)
        hidden = any(part.startswith(".") for part in rel.parts)
        if path.is_file() and path.name != SKILL_FILE and not hidden:
            files.append(rel)
    return sorted(files)


def publish(
    build_dir: Path, skill_entries: Sequence[tuple[Path, Path | None]], *, enabled: bool
) -> None:
    """
    Publish skills and their discovery index at `.well-known` paths

    Copy each skill and its companion files under `.well-known/agent-skills/{name}/`,
    write a combined `index.json`, and retain the legacy path for the first skill.

    Parameters
    ----------
    skill_entries
        Skills to publish as `(skill_path, source_dir)` tuples. Copy companion files
        from `source_dir` alongside `SKILL.md`. Set `source_dir` to `None` when the
        skill shares its directory with the project or has no companion directory.
    """
    if not enabled:
        return

    index_skills: list[dict[str, str | list[str]]] = []

    for skill_path, source_dir in skill_entries:
        content = skill_path.read_text(encoding="utf-8")
        fm, _ = split_front_matter(content)
        skill_name = fm.string("name") or "default"
        skill_description = (fm.string("description") or "").strip()

        agent_skills_dir = build_dir / WELL_KNOWN_ROOT / skill_name
        agent_skills_dir.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(skill_path, agent_skills_dir / SKILL_FILE)

        extra_files = [SKILL_FILE]
        if source_dir:
            for rel in companion_files(source_dir):
                dest = agent_skills_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(source_dir / rel, dest)
                extra_files.append(rel.as_posix())

        index_skills.append(
            {
                "name": skill_name,
                "description": skill_description,
                "files": extra_files,
            }
        )

    if index_skills:
        index_data = {"skills": index_skills}
        index_path = build_dir / WELL_KNOWN_ROOT / INDEX_FILE
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2)
            _ = f.write("\n")

    if skill_entries:
        first_skill_path = skill_entries[0][0]
        well_known_dir = build_dir / LEGACY_DIR
        well_known_dir.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(first_skill_path, well_known_dir / SKILL_FILE)
