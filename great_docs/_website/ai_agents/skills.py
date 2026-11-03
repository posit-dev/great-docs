"""
Publish AI agent skills and a browsable skills page for a documentation site
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..._layout import Layout
from ...config import Config
from .. import quarto_yml
from .skill_md import compose
from .skills_page import SkillsPageWriter
from .well_known import publish


@dataclass
class SkillsWriter:
    """
    Publisher for skill files, their discovery index and the site skills page
    """

    config: Config
    layout: Layout
    build_dir: Path
    distribution_name: str | None
    metadata: dict[str, Any]

    def write(self) -> None:
        """
        Publish the configured skills and a page for browsing them

        Copy authored or curated skills when available; otherwise generate a skill from
        package metadata and the API reference. Publish discovery files when enabled.
        """
        if not self.config.skill_enabled:
            return

        package_root = self.layout.package_root

        if self.config.skill_skills:
            self._write_multi(package_root)
            return

        if self.config.skill_file:
            src = self.layout.source_dir / self.config.skill_file
            if src.exists():
                dest = self.build_dir / "skill.md"
                _ = shutil.copy2(src, dest)
                print(f"Copied user SKILL.md from {src}")
                publish(self.build_dir, [(dest, None)], enabled=self.config.skill_well_known)
                SkillsPageWriter.make(self).write(dest, skill_dir=src.parent)
                return
            else:
                print(f"Warning: skill.file '{src}' not found, falling back to discovery")

        # Curated skills use the distribution name, which can differ from the import name.
        package_name_for_skill = self.distribution_name or ""
        install_name = package_name_for_skill.replace("_", "-") if package_name_for_skill else ""

        for candidate_name in [install_name, package_name_for_skill]:
            if not candidate_name:
                continue
            skills_path = package_root / "skills" / candidate_name / "SKILL.md"
            if skills_path.exists():
                dest = self.build_dir / "skill.md"
                _ = shutil.copy2(skills_path, dest)
                print(f"Using curated skill from {skills_path}")
                publish(self.build_dir, [(dest, None)], enabled=self.config.skill_well_known)
                SkillsPageWriter.make(self).write(dest, skill_dir=skills_path.parent)
                return

        if not quarto_yml.path(self.build_dir).exists():
            return

        config = quarto_yml.read(self.build_dir)

        skill_content = compose(
            self.config,
            self.layout,
            self.build_dir,
            self.distribution_name,
            self.metadata,
            config,
        )

        skill_path = self.build_dir / "skill.md"
        _ = skill_path.write_text(skill_content, encoding="utf-8")

        print(f"Created {skill_path}")

        publish(self.build_dir, [(skill_path, None)], enabled=self.config.skill_well_known)

        SkillsPageWriter.make(self).write(skill_path)

    def _write_multi(self, package_root: "Path") -> None:
        """
        Publish the named skills in `skill.skills`

        Each entry in `skill.skills` must have `name` and `file` keys. The first skill is also
        written to `<docs>/skill.md` and used for the skills page. All skills are aggregated into a
        single `.well-known/agent-skills/index.json` discovery manifest.
        """
        skill_entries = self.config.skill_skills
        if not skill_entries:
            return

        placed_skills: list[tuple["Path", "Path"]] = []

        for i, entry in enumerate(skill_entries):
            name = entry.get("name")
            file_path = entry.get("file")
            if not name or not file_path:
                print(f"Warning: skill.skills[{i}] missing 'name' or 'file', skipping")
                continue

            src = self.layout.source_dir / file_path
            if not src.exists():
                print(f"Warning: skill file '{src}' not found, skipping")
                continue

            if i == 0:
                dest = self.build_dir / "skill.md"
                _ = shutil.copy2(src, dest)
                print(f"Copied primary skill '{name}' from {src}")
                placed_skills.append((dest, src.parent))
            else:
                placed_skills.append((src, src.parent))

        if not placed_skills:
            return

        publish(self.build_dir, placed_skills, enabled=self.config.skill_well_known)

        primary_path, primary_dir = placed_skills[0]
        extra = placed_skills[1:] if len(placed_skills) > 1 else None
        SkillsPageWriter.make(self).write(primary_path, skill_dir=primary_dir, extra_skills=extra)
