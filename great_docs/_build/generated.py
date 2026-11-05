"""
Build steps for generated site files and page data

Write `llms.txt` files, agent skills, a changelog from GitHub Releases, a tags index and page
status badges, with their navbar links and page data. Warn if skill installation
instructions lack a site URL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._cliref import click as cli_click
from .._website import changelog as changelog_page
from .._website import inline_data, page_status, quarto_yml
from .._website import tags as page_tags
from .._website.ai_agents import llms_txt as llms_files
from .._website.ai_agents.skills import SkillsWriter
from .steps import Outcome, Skipped

if TYPE_CHECKING:
    from .._cliref.model import CliCommand
    from .._layout import Layout
    from .._remote import Remote
    from ..config import Config
    from .log import BuildLog
    from .pipeline import Run

__all__ = ["changelog", "check_site_url", "llms_txt", "page_statuses", "skills", "tags"]


def llms_txt(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write `llms.txt` and `llms-full.txt`

    `llms-full.txt` includes user guide pages and, when `cli.enabled` is set, Click
    command-line help.

    Parameters
    ----------
    run
        Build state containing the package's names and metadata and the discovered user guide.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    build_dir = layout.build_dir
    if not llms_files.is_planned(build_dir):
        return Skipped("no API reference")
    _ = llms_files.write_index(build_dir, run.project.manifest, report=print)

    cli: CliCommand | None = None
    package_name = run.project.name if config.cli_enabled else None
    module = run.project.importable_name
    if package_name and module:
        try:
            cli = cli_click.discover(
                module,
                layout.package_root,
                cli_module=config.cli_module,
                cli_name=config.cli_name,
                display_name=package_name,
                report=print,
            )
        except ImportError:
            # The CLI reference step reports the import failure. Continue without CLI help.
            pass
    _ = llms_files.write_full(build_dir, cli=cli, user_guide=run.user_guide, report=print)
    return "Created llms.txt + llms-full.txt"


def skills(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write the agent skill files and the skills page

    Parameters
    ----------
    run
        The current build, which supplies the package's name and metadata.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.skill_enabled:
        return Skipped("disabled in config")
    SkillsWriter(config, layout, layout.build_dir, run.project.name, run.project.manifest).write()
    return "Created skill.md"


def check_site_url(run: Run, config: Config, layout: Layout, log: BuildLog) -> Outcome:
    """
    Warn when the skills page has no site URL for its install instructions

    Parameters
    ----------
    run
        The current build, which supplies the package's project URLs.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log.

    Returns
    -------
    :
        `None`; the warning belongs to the previous step.
    """
    if not config.skill_enabled:
        return None
    urls = run.project.manifest["urls"]
    has_site_url = bool(config.site_url or urls.get("Documentation", ""))
    build_dir = layout.build_dir
    if not has_site_url and quarto_yml.path(build_dir).exists():
        website = quarto_yml.read(build_dir).get("website", {})
        has_site_url = bool(website.get("site-url", ""))
    if not has_site_url:
        log.warn(
            "No site URL found — skills page will show <site-url> placeholders. "
            "Set site_url in great-docs.yml or add a Documentation URL to "
            "[project.urls] in pyproject.toml."
        )
    return None


def changelog(run: Run, config: Config, layout: Layout, *, remote: Remote) -> Outcome:
    """
    Write the changelog page from GitHub Releases and link it from the navbar

    Parameters
    ----------
    run
        The current build, which supplies the project's GitHub repository.
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of the repository's releases.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.changelog_enabled:
        return Skipped("disabled in config")
    repo = run.project.github
    if repo is None:
        return Skipped("no GitHub repo info")
    build_dir = layout.build_dir
    contribution = changelog_page.write_page(config, build_dir, repo, remote, report=print)
    if contribution is None:
        return "No releases found; skipped"
    with quarto_yml.edit(build_dir) as quarto_config:
        quarto_yml.apply(quarto_config, contribution)
    return "Changelog from GitHub Releases"


def tags(config: Config, layout: Layout) -> Outcome:
    """
    Write the tags index, embed tag pill data and add the navbar link

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.tags_enabled:
        return Skipped("tags not enabled")
    output = page_tags.write(config, layout, report=print)
    if output is None:
        return Skipped("no tagged pages found")
    with quarto_yml.edit(layout.build_dir) as quarto_config:
        if output.page_data is not None:
            inline_data.add(
                quarto_config, "__GD_TAGS_DATA__", output.page_data, before="page-tags.js"
            )
        quarto_yml.apply(quarto_config, output.contribution)
    return "Tags processed"


def page_statuses(config: Config, layout: Layout) -> Outcome:
    """
    Write the status badge data for pages that declare a status

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.page_status_enabled:
        return Skipped("page status not enabled")
    if not page_status.process(config, layout, layout.build_dir):
        return Skipped("no pages with status")
    return "Status badges processed"
