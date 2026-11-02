"""
Publish AI agent skills and a browsable skills page for a documentation site
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

from ..._layout import Layout
from ..._yaml import split_front_matter
from ...config import Config
from .. import page_dates, quarto_yml
from ..scripts import script_tag
from ..seo import noindex
from . import llms_txt
from .well_known import publish


class SkillMeta(TypedDict):
    name: str
    description: str
    path: Path
    dir: Path | None


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
                self.write_page(dest, skill_dir=src.parent)
                return
            else:
                print(f"Warning: skill.file '{src}' not found, falling back to discovery")

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
                self.write_page(dest, skill_dir=skills_path.parent)
                return

        if not quarto_yml.path(self.build_dir).exists():
            return

        config = quarto_yml.read(self.build_dir)

        api_ref_config = config.get("api-reference", {})
        sections = api_ref_config.get("sections", [])
        package_name = api_ref_config.get("package", "")

        metadata = self.metadata
        description = metadata.get("description", "")
        license_text = metadata.get("license", "")
        requires_python = metadata.get("requires_python", "")

        urls = metadata.get("urls", {})
        site_url = urls.get("Documentation", "") or config.get("website", {}).get("site-url", "")
        if site_url and "#" in site_url:
            site_url = site_url.split("#")[0]  # pragma: no cover
        if site_url and not site_url.endswith("/"):
            site_url += "/"

        repo_url = urls.get("Repository", "") or urls.get("Source", "")

        install_name = package_name_for_skill or (
            package_name.replace("_", "-") if package_name else ""
        )

        skill_name = install_name.lower()[:64] if install_name else "package"

        lines = ["---"]
        lines.append(f"name: {skill_name}")

        desc_parts: list[str] = []
        if description:
            desc_parts.append(description.rstrip(".") + ".")
        if package_name:
            desc_parts.append(f"Use when writing Python code that uses the {package_name} package.")
        skill_desc = " ".join(desc_parts)[:1024] if desc_parts else f"Use the {skill_name} package."
        lines.append("description: >")
        lines.append(f"  {skill_desc}")

        if license_text:
            lines.append(f"license: {license_text}")
        if requires_python:
            lines.append(f"compatibility: Requires Python {requires_python}.")
        lines.append("---")
        lines.append("")

        display_name = self.config.display_name or package_name or skill_name
        lines.append(f"# {display_name}")
        lines.append("")
        if description:
            lines.append(description)
            lines.append("")

        if install_name:
            lines.append("## Installation")
            lines.append("")
            lines.append("```bash")
            lines.append(f"pip install {install_name}")
            lines.append("```")
            lines.append("")

        if sections:
            manual_rows = self.config.skill_decision_table

            if manual_rows:
                lines.append("## When to use what")
                lines.append("")
                lines.append("| Need | Use |")
                lines.append("|------|-----|")
                for row in manual_rows:
                    need = row.get("need", "")
                    use = row.get("use", "")
                    lines.append(f"| {need} | `{use}` |")
                lines.append("")

            lines.append("## API overview")
            lines.append("")

            for section in sections:
                section_title = section.get("title") or section.get("subtitle") or ""
                section_desc = section.get("desc", "")

                if section_title:
                    lines.append(f"### {section_title}")
                    if section_desc:
                        lines.append("")
                        lines.append(section_desc)
                    lines.append("")

                for item in section.get("contents", []):
                    if isinstance(item, str):
                        item_name = item
                    elif isinstance(item, dict):  # pragma: no cover
                        item_map = cast("dict[str, object]", item)
                        item_name = str(item_map.get("name", str(item_map)))  # pragma: no cover
                    else:
                        continue  # pragma: no cover

                    item_desc = llms_txt.docstring_summary(package_name, item_name)
                    if item_desc:
                        lines.append(f"- `{item_name}`: {item_desc}")  # pragma: no cover
                    else:
                        lines.append(f"- `{item_name}`")

                lines.append("")

        gotchas = self.config.skill_gotchas
        if gotchas:
            lines.append("## Gotchas")
            lines.append("")
            for i, gotcha in enumerate(gotchas, 1):
                lines.append(f"{i}. {gotcha}")
            lines.append("")

        best_practices = self.config.skill_best_practices
        if best_practices:
            lines.append("## Best practices")
            lines.append("")
            for practice in best_practices:
                lines.append(f"- {practice}")
            lines.append("")

        if self.config.skill_extra_body:
            extra_path = self.layout.source_dir / self.config.skill_extra_body
            if extra_path.exists():
                extra_content = extra_path.read_text(encoding="utf-8")
                lines.append(extra_content)
                lines.append("")

        lines.append("## Resources")
        lines.append("")
        if site_url:
            lines.append(f"- [Full documentation]({site_url})")
        if llms_txt.is_planned(self.build_dir):
            lines.append("- [llms.txt](llms.txt) — Indexed API reference for LLMs")
            lines.append("- [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs")
        if repo_url:
            lines.append(f"- [Source code]({repo_url})")
        lines.append("")

        skill_path = self.build_dir / "skill.md"
        with open(skill_path, "w", encoding="utf-8") as f:
            _ = f.write("\n".join(lines))

        print(f"Created {skill_path}")

        publish(self.build_dir, [(skill_path, None)], enabled=self.config.skill_well_known)

        self.write_page(skill_path)

    def write_page(
        self,
        skill_path: "Path",
        *,
        skill_dir: "Path | None" = None,
        extra_skills: "Sequence[tuple[Path, Path | None]] | None" = None,
    ) -> None:
        """
        Write a `skills.qmd` page with raw skill content and installation guidance

        Display companion files from curated skill directories. Add a switcher when
        `extra_skills` contains more skills for the page.

        Parameters
        ----------
        skill_path
            Path to the skill file to render.
        skill_dir
            Directory containing a curated skill and its companion files, when present.
        extra_skills
            Additional `(skill_path, skill_dir)` tuples to display as switchable panels.
        """
        import html

        from ..._translations import get_translation

        lang = self.config.lang

        def _t(key: str, fallback: str) -> str:
            return get_translation(key, lang) if lang != "en" else fallback

        if not skill_path.exists():
            return  # pragma: no cover

        all_skills: list[tuple["Path", "Path | None"]] = [(skill_path, skill_dir)]
        if extra_skills:
            all_skills.extend(extra_skills)
        multi_skill = len(all_skills) > 1

        skill_meta: list[SkillMeta] = []
        for sp, sd in all_skills:
            if not sp.exists():  # pragma: no cover
                continue  # pragma: no cover
            content = sp.read_text(encoding="utf-8")
            fm, _ = split_front_matter(content)
            skill_meta.append(
                {
                    "name": fm.string("name") or sp.stem,
                    "description": (fm.string("description") or "").strip(),
                    "path": sp,
                    "dir": sd,
                }
            )

        lines: list[str] = []
        lines.append("---")
        lines.append(f"title: {_t('skills_title', 'Skills')}")
        lines.append("toc: false")
        lines.append("sidebar: false")
        lines.append("page-layout: full")
        lines.append('body-classes: "gd-skills-page"')
        lines.append(f"{page_dates.AUTO_GENERATED}: true")
        lines.append("---")
        lines.append("")

        if multi_skill:
            lines.append(
                _t(
                    "skills_intro_multi",
                    "A skill is a package of structured files that teaches an AI "
                    "coding agent how to work with a specific tool or framework. "
                    "This project ships multiple skills — use the switcher below "
                    "to browse each one. Install a skill in your agent and it will "
                    "be able to run commands, edit configuration, write content, "
                    "and troubleshoot problems without step-by-step guidance from you.",
                )
            )
        elif not skill_dir:
            lines.append(
                _t(
                    "skills_intro",
                    "A skill is a package of structured files that teaches an AI "
                    "coding agent how to work with a specific tool or framework. "
                    "The skill below was generated by Great Docs from this "
                    "project's documentation. Install it in your agent and it will "
                    "be able to run commands, edit configuration, write content, "
                    "and troubleshoot problems without step-by-step guidance from you.",
                )
            )
        else:
            lines.append(
                _t(
                    "skills_intro_curated",
                    "A skill is a package of structured files that teaches an AI "
                    "coding agent how to work with a specific tool or framework. "
                    "Install it in your agent and it will be able to run commands, "
                    "edit configuration, write content, and troubleshoot problems "
                    "without step-by-step guidance from you.",
                )
            )
        lines.append("")

        metadata = self.metadata
        urls = metadata.get("urls", {})
        repo_url = urls.get("Repository", "") or urls.get("Source", "")
        github_owner_repo = ""
        if repo_url:
            gh_match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_url)
            if gh_match:
                github_owner_repo = gh_match.group(1)

        site_url = ""
        if quarto_yml.path(self.build_dir).exists():
            qconfig = quarto_yml.read(self.build_dir)
            site_url = urls.get("Documentation", "") or qconfig.get("website", {}).get(
                "site-url", ""
            )
            if site_url and not site_url.endswith("/"):
                site_url += "/"

        lines.append("```{=html}")
        lines.append('<div class="gd-skills-install">')
        lines.append(
            '  <button class="gd-skills-install-toggle" '
            'aria-expanded="false" aria-controls="gd-skills-install-body">'
        )
        _install_label = (
            _t("install_these_skills", "Install these skills")
            if multi_skill
            else _t("install_this_skill", "Install this skill")
        )
        lines.append('    <span class="gd-skills-install-icon">&#9654;</span>    ' + _install_label)
        lines.append("  </button>")
        lines.append('  <div class="gd-skills-install-body" id="gd-skills-install-body">')
        lines.append('    <div class="gd-skills-install-inner">')
        lines.append('      <div class="gd-skills-install-pad">')
        lines.append("```")
        lines.append("")

        if multi_skill:
            lines.append(
                f"**{_t('any_agent', 'Any agent')}** --- "
                f"{_t('install_all_with_npx', 'install all with')} "
                "[npx](https://github.com/vercel-labs/skills):"
            )
        else:
            lines.append(
                f"**{_t('any_agent', 'Any agent')}** --- "
                f"{_t('install_with_npx', 'install with')} "
                "[npx](https://github.com/vercel-labs/skills):"
            )
        lines.append("")
        if site_url:
            _npx_cmd = f"npx skills add {site_url}"
        elif github_owner_repo:
            _npx_cmd = f"npx skills add {github_owner_repo}"
        else:
            _npx_cmd = "npx skills add <site-url>"
        lines.append("```{=html}")
        lines.append(
            f'<div class="sourceCode"><pre class="sourceCode bash code-with-copy" style="padding-bottom: 0;">'
            f"<code>{_npx_cmd}</code></pre></div>"
        )
        lines.append("```")
        lines.append("")

        if multi_skill:
            _package_name = self.distribution_name or ""
            if _package_name:
                _install_name = _package_name.replace("_", "-")
                lines.append(
                    f"**{_t('cli_install', 'CLI')}** --- "
                    f"{_t('install_all_in_project', 'install all skills in a project')}:"
                )
                lines.append("")
                _cli_cmd = f"great-docs skill install {_install_name}"
                lines.append("```{=html}")
                lines.append(
                    f'<div class="sourceCode"><pre class="sourceCode bash code-with-copy" style="padding-bottom: 0;">'
                    f"<code>{_cli_cmd}</code></pre></div>"
                )
                lines.append("```")
                lines.append("")

            lines.append("**Codex / OpenCode**")
            lines.append("")
            _tell_line = _t("tell_the_agent_to_fetch", "Tell the agent to fetch these skill files")
            _skill_url_lines = [f"{_tell_line}:"]
            for meta in skill_meta:
                sname = meta["name"]
                if site_url:
                    _skill_url_lines.append(f"{site_url}.well-known/agent-skills/{sname}/SKILL.md")
                else:
                    _skill_url_lines.append(
                        f"&lt;site-url&gt;/.well-known/agent-skills/{sname}/SKILL.md"
                    )
            _url_list_html = "<br>".join(_skill_url_lines)
            lines.append("```{=html}")
            lines.append(
                f'<div class="sourceCode"><pre class="sourceCode text code-with-copy" style="padding-bottom: 0;">'
                f"<code>{_url_list_html}</code></pre></div>"
            )
            lines.append("```")
            lines.append("")
            _browse_label = _t("browse_skill_files", "Or browse the skill files below")
            lines.append("```{=html}")
            lines.append(f"<p>{_browse_label}.</p>")
            lines.append("```")
            lines.append("")

        else:
            skill_file_url = f"{site_url}skill.md" if site_url else ""
            lines.append("**Codex / OpenCode**")
            lines.append("")
            _tell_the_agent = _t("tell_the_agent", "Tell the agent")
            _fetch_verb = _t("fetch_skill_file_at", "Fetch the skill file at")
            _fetch_from_verb = _t("fetch_skill_file_from", "Fetch the skill file from")
            if skill_file_url:
                _follow = _t("and_follow_instructions", "and follow the instructions.")
                _prompt_text = f"{_fetch_verb} {skill_file_url} {_follow}"
            elif github_owner_repo:
                _follow = _t("and_follow_instructions", "and follow the instructions.")
                _prompt_text = (
                    f"{_fetch_from_verb} https://github.com/{github_owner_repo} {_follow}"
                )
            else:
                _follow = _t("and_follow_instructions", "and follow the instructions.")
                _prompt_text = f"{_fetch_verb} &lt;site-url&gt;/skill.md {_follow}"
            _code_content = f"{_tell_the_agent}:<br>{_prompt_text}"
            lines.append("```{=html}")
            lines.append(
                f'<div class="sourceCode"><pre class="sourceCode text code-with-copy" style="padding-bottom: 0;">'
                f"<code>{_code_content}</code></pre></div>"
            )
            lines.append("```")
            lines.append("")

            _download_label = _t("download_skill_file", "download the skill file")
            lines.append(f"**{_t('manual_download', 'Manual')}** --- {_download_label}:")
            lines.append("")
            if skill_file_url:
                _curl_cmd = f"curl -O {skill_file_url}"
            else:
                _curl_cmd = "curl -O &lt;site-url&gt;/skill.md"
            lines.append("```{=html}")
            lines.append(
                f'<div class="sourceCode"><pre class="sourceCode bash code-with-copy" style="padding-bottom: 0;">'
                f"<code>{_curl_cmd}</code></pre></div>"
            )
            lines.append("```")
            lines.append("")
            _browse_label = (
                f"{_t('browse_skill_file', 'Or browse the')} "
                '<a href="skill.md" class="gd-raw-link"><code>SKILL.md</code></a> '
                f"{_t('file_word', 'file')}"
            )
            lines.append("```{=html}")
            lines.append(f"<p>{_browse_label}.</p>")
            lines.append("```")
            lines.append("")

        lines.append("```{=html}")
        lines.append("      </div>")
        lines.append("    </div>")
        lines.append("  </div>")
        lines.append("</div>")
        lines.append("<script>")
        lines.append("(function() {")
        lines.append("  var btn = document.querySelector('.gd-skills-install-toggle');")
        lines.append("  var body = document.getElementById('gd-skills-install-body');")
        lines.append("  if (!btn || !body) return;")
        lines.append("  btn.addEventListener('click', function() {")
        lines.append("    var open = body.classList.toggle('gd-skills-install-open');")
        lines.append("    btn.setAttribute('aria-expanded', open);")
        lines.append("  });")
        lines.append("})();")
        lines.append("</script>")
        lines.append("```")
        lines.append("")

        if multi_skill:
            lines.append("```{=html}")
            lines.append(
                '<div class="gd-skill-switcher" role="tablist" aria-label="Skill selector">'
            )
            for idx, meta in enumerate(skill_meta):
                active_cls = " gd-skill-pill--active" if idx == 0 else ""
                selected = "true" if idx == 0 else "false"
                tabindex = "0" if idx == 0 else "-1"
                name = html.escape(meta["name"])
                desc = html.escape(meta["description"])
                title_attr = f' title="{desc}"' if desc else ""
                lines.append(
                    f'  <button class="gd-skill-pill{active_cls}" role="tab" '
                    f'aria-selected="{selected}" tabindex="{tabindex}"{title_attr}>'
                    f"{name}</button>"
                )
            lines.append("</div>")
            lines.append("```")
            lines.append("")

        for panel_idx, meta in enumerate(skill_meta):
            sp = meta["path"]
            sd = meta["dir"]

            if multi_skill:
                hidden_attr = " hidden" if panel_idx > 0 else ""
                lines.append("```{=html}")
                lines.append(f'<div class="gd-skill-panel"{hidden_attr}>')
                lines.append("```")
                lines.append("")

            self._append_panel(lines, sp, sd, _t, panel_prefix=meta["name"])

            if multi_skill:
                lines.append("```{=html}")
                lines.append("</div>")
                lines.append("```")
                lines.append("")

        if multi_skill:
            lines.append("```{=html}")
            lines.append(script_tag("skill-switcher.js"))
            lines.append("```")
            lines.append("")

        skills_page = self.build_dir / "skills.qmd"
        with open(skills_page, "w", encoding="utf-8") as f:
            _ = f.write(noindex.add_to_page(self.config, "\n".join(lines)))

    def _append_panel(
        self,
        lines: "list[str]",
        skill_path: "Path",
        skill_dir: "Path | None",
        _t: "Callable[[str, str], str]",
        *,
        panel_prefix: str = "",
    ) -> None:
        """
        Append one skill and its companion files to the page content
        """
        if not skill_path.exists():
            return  # pragma: no cover

        raw_content = skill_path.read_text(encoding="utf-8")

        def _fence(text: str, min_ticks: int = 4) -> str:
            """
            Return a backtick fence longer than any fence in `text`
            """
            runs = re.findall(r"`{3,}", text)
            max_run = max((len(r) for r in runs), default=0)
            return "`" * max(min_ticks, max_run + 1)

        def _neutralize_executable_cells(text: str) -> str:
            """
            Display Python Quarto cells without executing them

            Quarto extracts `{python}` cells before parsing Markdown fences, so a
            deeper fence cannot prevent execution. `{.python}` retains syntax
            highlighting while preventing execution.
            """
            return re.sub(r"\{python\}", "{.python}", text)

        raw_content = _neutralize_executable_cells(raw_content)

        companion_files: list[tuple[str, str, str]] = []  # (subdir/name, ext, content)
        _ALLOWED_SUBDIRS = ("references", "scripts", "assets")
        _RENDERABLE_EXTS = {".md", ".sh", ".yaml", ".yml", ".py"}

        if skill_dir and skill_dir.is_dir():
            for subdir_name in _ALLOWED_SUBDIRS:
                subdir = skill_dir / subdir_name
                if not subdir.is_dir():
                    continue
                for file_path in sorted(subdir.iterdir()):
                    if file_path.is_file() and file_path.suffix in _RENDERABLE_EXTS:
                        rel = f"{subdir_name}/{file_path.name}"
                        content = _neutralize_executable_cells(
                            file_path.read_text(encoding="utf-8")
                        )
                        companion_files.append((rel, file_path.suffix, content))

        anchor_pfx = f"{panel_prefix}-" if panel_prefix else ""

        if companion_files:
            dir_label = skill_dir.name if skill_dir else "skill"
            tree_lines = [f"{dir_label}/"]
            tree_lines.append("\u251c\u2500\u2500 SKILL.md")
            seen_subdirs: dict[str, list[str]] = {}
            for rel, _ext, _content in companion_files:
                parts = rel.split("/", 1)
                seen_subdirs.setdefault(parts[0], []).append(parts[1])
            subdir_items = list(seen_subdirs.items())
            for i, (sdir, files) in enumerate(subdir_items):
                is_last_dir = i == len(subdir_items) - 1
                branch = "\u2514\u2500\u2500" if is_last_dir else "\u251c\u2500\u2500"
                tree_lines.append(f"{branch} {sdir}/")
                for j, fname in enumerate(files):
                    is_last_file = j == len(files) - 1
                    prefix = "    " if is_last_dir else "\u2502   "
                    connector = "\u2514\u2500\u2500" if is_last_file else "\u251c\u2500\u2500"
                    anchor = f"{anchor_pfx}{sdir}/{fname}".replace("/", "-").replace(".", "-")
                    tree_lines.append(f'{prefix}{connector} <a href="#{anchor}">{fname}</a>')

            lines.append("```{=html}")
            lines.append(
                f'<h3 class="gd-skills-section-heading">{_t("skill_layout", "SKILL LAYOUT")}</h3>'
            )
            lines.append('<pre class="gd-skills-tree">')
            lines.append("\n".join(tree_lines))
            lines.append("</pre>")
            lines.append("```")
            lines.append("")

        lines.append("```{=html}")
        lines.append('<h3 class="gd-skills-file-heading">SKILL.md</h3>')
        lines.append('<pre class="gd-skills-raw">')
        lines.append("```")
        lines.append("")
        skill_fence = _fence(raw_content)
        lines.append(f"{skill_fence}markdown")
        lines.append(raw_content.rstrip("\n"))
        lines.append(skill_fence)
        lines.append("")
        lines.append("```{=html}")
        lines.append("</pre>")
        lines.append("```")
        lines.append("")

        for rel, ext, content in companion_files:
            anchor = f"{anchor_pfx}{rel}".replace("/", "-").replace(".", "-")
            lang_map = {
                ".md": "markdown",
                ".sh": "bash",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".py": "python",
            }
            lang_hint = lang_map.get(ext, "")

            lines.append("```{=html}")
            lines.append(f'<h3 id="{anchor}" class="gd-skills-file-heading">{rel}</h3>')
            lines.append('<pre class="gd-skills-raw">')
            lines.append("```")
            lines.append("")
            comp_fence = _fence(content)
            lines.append(f"{comp_fence}{lang_hint}")
            lines.append(content.rstrip("\n"))
            lines.append(comp_fence)
            lines.append("")
            lines.append("```{=html}")
            lines.append("</pre>")
            lines.append("```")
            lines.append("")

    def _write_multi(self, package_root: "Path") -> None:
        """
        Publish the named skills in `skill.skills`

        Each entry in `skill.skills` must have `name` and `file` keys. The first skill is
        written to `<docs>/skill.md` and used for the skills page. All skills are aggregated
        into a `.well-known/agent-skills/index.json` discovery manifest.
        """
        skill_entries = self.config.skill_skills
        if not skill_entries:  # pragma: no cover
            return  # pragma: no cover

        placed_skills: list[tuple["Path", "Path"]] = []

        for i, entry in enumerate(skill_entries):
            name = entry.get("name")
            file_path = entry.get("file")
            if not name or not file_path:  # pragma: no cover
                print(
                    f"Warning: skill.skills[{i}] missing 'name' or 'file', skipping"
                )  # pragma: no cover
                continue  # pragma: no cover

            src = self.layout.source_dir / file_path
            if not src.exists():  # pragma: no cover
                print(f"Warning: skill file '{src}' not found, skipping")  # pragma: no cover
                continue  # pragma: no cover

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
        self.write_page(primary_path, skill_dir=primary_dir, extra_skills=extra)
