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
        List of `(skill_path, source_dir)` tuples. `source_dir` may be `None`
        and is used to copy additional reference files alongside the `SKILL.md`.
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
        if source_dir and source_dir.is_dir():
            for extra in source_dir.rglob("*"):
                if extra.is_file() and extra.name != SKILL_FILE:
                    rel = extra.relative_to(source_dir)
                    dest = agent_skills_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    _ = shutil.copy2(extra, dest)
                    extra_files.append(str(rel))

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
