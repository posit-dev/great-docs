"""
Compose a generated agent skill from package and documentation facts
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from yaml12 import format_yaml

from ..._layout import Layout
from ..._manifest import Manifest
from ...config import Config
from . import llms_txt


def compose(
    config: Config,
    layout: Layout,
    distribution_name: str | None,
    metadata: Manifest,
    api_block: Mapping[str, Any] | None,
) -> str:
    """
    Compose a `SKILL.md` file for the documented package

    The generated front matter is valid YAML even when metadata contains punctuation.

    Parameters
    ----------
    config
        The project's configuration, including the site URL and the skill settings.
    layout
        The project's directories, including the source of the skill's extra body.
    distribution_name
        The name under which the package is installed, or `None` when unknown.
    metadata
        The package metadata: description, licence, Python requirement and URLs.
    api_block
        The API reference configuration for the skill's overview, or `None` to omit
        the overview.

    Returns
    -------
    :
        The skill's Markdown with its front matter.
    """
    package_name_for_skill = distribution_name or ""
    api_ref_config = api_block or {}
    sections = api_ref_config.get("sections", [])
    package_name = api_ref_config.get("package", "")

    description = metadata.get("description", "")
    license_text = metadata.get("license", "")
    requires_python = metadata.get("requires_python", "")

    urls = metadata.get("urls", {})
    site_url = urls.get("Documentation", "") or config.site_url or ""
    if site_url and "#" in site_url:
        site_url = site_url.split("#")[0]
    if site_url and not site_url.endswith("/"):
        site_url += "/"

    repo_url = urls.get("Repository", "") or urls.get("Source", "")

    # Use the distribution name for installation when it differs from the importable module.
    # Fall back to the module name when the project has no distribution metadata.
    install_name = package_name_for_skill or (
        package_name.replace("_", "-") if package_name else ""
    )

    skill_name = install_name.lower()[:64] if install_name else "package"

    desc_parts: list[str] = []
    if description:
        desc_parts.append(description.rstrip(".") + ".")
    if package_name:
        desc_parts.append(f"Use when writing Python code that uses the {package_name} package.")
    skill_desc = " ".join(desc_parts)[:1024] if desc_parts else f"Use the {skill_name} package."
    front_matter = {"name": skill_name, "description": skill_desc}
    if license_text:
        front_matter["license"] = license_text
    if requires_python:
        front_matter["compatibility"] = f"Requires Python {requires_python}."
    lines = ["---", *format_yaml(front_matter).rstrip().splitlines(), "---", ""]

    display_name = config.display_name or package_name or skill_name
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
        manual_rows = config.skill_decision_table

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
                elif isinstance(item, dict):
                    item_map = cast("dict[str, object]", item)
                    item_name = str(item_map.get("name", str(item_map)))
                else:
                    continue

                item_desc = llms_txt.docstring_summary(package_name, item_name)
                if item_desc:
                    lines.append(f"- `{item_name}`: {item_desc}")
                else:
                    lines.append(f"- `{item_name}`")

            lines.append("")

    gotchas = config.skill_gotchas
    if gotchas:
        lines.append("## Gotchas")
        lines.append("")
        for i, gotcha in enumerate(gotchas, 1):
            lines.append(f"{i}. {gotcha}")
        lines.append("")

    best_practices = config.skill_best_practices
    if best_practices:
        lines.append("## Best practices")
        lines.append("")
        for practice in best_practices:
            lines.append(f"- {practice}")
        lines.append("")

    if config.skill_extra_body:
        extra_path = layout.source_dir / config.skill_extra_body
        if extra_path.exists():
            extra_content = extra_path.read_text(encoding="utf-8")
            lines.append(extra_content)
            lines.append("")

    lines.append("## Resources")
    lines.append("")
    if site_url:
        lines.append(f"- [Full documentation]({site_url})")
    if llms_txt.is_planned(api_block):
        lines.append("- [llms.txt](llms.txt) — Indexed API reference for LLMs")
        lines.append("- [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs")
    if repo_url:
        lines.append(f"- [Source code]({repo_url})")
    lines.append("")

    return "\n".join(lines)
