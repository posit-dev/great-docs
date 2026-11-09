"""
Publish AI agent skills and a browsable skills page for a documentation site
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..._project.layout import Layout
from ..._project.manifest import Manifest
from ...config import Config
from .skill_md import compose
from .skills_page import SkillsPageWriter
from .well_known import publish


@dataclass
class SkillsWriter:
    """
    Publisher for skill files, their discovery index and the site skills page

    `layout` supplies the source directory for configured skill files, the package
    root for curated skills and the build directory for published skills, discovery
    files and `skills.qmd`.
    """

    config: Config
    layout: Layout
    distribution_name: str | None
    metadata: Manifest

    def write(self, api_block: Mapping[str, Any] | None) -> None:
        """
        Publish the configured skills and a page for browsing them

        Copy authored or curated skills when available; otherwise generate a skill from
        package metadata and the API reference. Publish discovery files when enabled.

        Parameters
        ----------
        api_block
            The API reference configuration for a generated skill, or `None` when the site
            has none.

        Returns
        -------
        :
        """
        if not self.config.skill_enabled:
            return

        package_root = self.layout.package_root
        build_dir = self.layout.build_dir

        if self.config.skill_skills:
            self._write_multi(package_root)
            return

        if self.config.skill_file:
            src = self.layout.source_dir / self.config.skill_file
            if src.exists():
                dest = build_dir / "skill.md"
                _ = shutil.copy2(src, dest)
                print(f"Copied user SKILL.md from {src}")
                own_dir = self._own_directory(src)
                publish(build_dir, [(dest, own_dir)], enabled=self.config.skill_well_known)
                SkillsPageWriter.make(self).write(
                    dest, skill_dir=src.parent, companions=own_dir is not None
                )
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
                dest = build_dir / "skill.md"
                _ = shutil.copy2(skills_path, dest)
                print(f"Using curated skill from {skills_path}")
                own_dir = self._own_directory(skills_path)
                publish(build_dir, [(dest, own_dir)], enabled=self.config.skill_well_known)
                SkillsPageWriter.make(self).write(
                    dest, skill_dir=skills_path.parent, companions=own_dir is not None
                )
                return

        skill_content = compose(
            self.config, self.layout, self.distribution_name, self.metadata, api_block
        )

        skill_path = build_dir / "skill.md"
        _ = skill_path.write_text(skill_content, encoding="utf-8")

        print(f"Created {skill_path}")

        publish(build_dir, [(skill_path, None)], enabled=self.config.skill_well_known)

        SkillsPageWriter.make(self).write(skill_path)

    def _write_multi(self, package_root: "Path") -> None:
        """
        Publish the named skills in `skill.skills`

        Each entry in `skill.skills` must have `name` and `file` keys; entries without them, or
        whose file is missing, are skipped. The first published skill is also written to
        `<docs>/skill.md` and leads the skills page. All skills are aggregated into a single
        `.well-known/agent-skills/index.json` discovery manifest.
        """
        skill_entries = self.config.skill_skills
        if not skill_entries:
            return

        build_dir = self.layout.build_dir
        placed_skills: list[tuple["Path", "Path | None"]] = []

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

            if not placed_skills:
                dest = build_dir / "skill.md"
                _ = shutil.copy2(src, dest)
                print(f"Copied primary skill '{name}' from {src}")
                placed_skills.append((dest, self._own_directory(src)))
            else:
                placed_skills.append((src, self._own_directory(src)))

        if not placed_skills:
            return

        publish(build_dir, placed_skills, enabled=self.config.skill_well_known)

        primary_path, primary_dir = placed_skills[0]
        extra = placed_skills[1:] if len(placed_skills) > 1 else None
        SkillsPageWriter.make(self).write(primary_path, skill_dir=primary_dir, extra_skills=extra)

    def _own_directory(self, skill_file: Path) -> Path | None:
        """
        Return the skill's directory unless it is shared with the project

        Treat the project root, the docs source directory and all ancestors of the
        docs source directory as shared. Skills in these directories have no companion
        files.

        Parameters
        ----------
        skill_file
            Path to the skill's `SKILL.md`.

        Returns
        -------
        :
            The skill's parent directory, or `None` for a shared directory.
        """
        directory = skill_file.parent.resolve()
        shared = directory == self.layout.package_root.resolve() or (
            self.layout.source_dir.resolve().is_relative_to(directory)
        )
        return None if shared else skill_file.parent
