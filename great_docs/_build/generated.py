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
from .._website import page_status
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
        Build state containing the package's names and metadata, the API reference
        configuration and the discovered user guide.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The result line or skip reason.
    """
    api_block = run.api_block
    if not llms_files.is_planned(api_block):
        return Skipped("no API reference")
    _ = llms_files.write_index(
        layout, api_block, run.project.manifest, site_url=config.site_url, report=print
    )

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
        except (ImportError, RuntimeError):
            # The CLI reference step reports import and Typer conversion failures.
            # Omit CLI help here so `llms-full.txt` is still written.
            pass
    _ = llms_files.write_full(layout, api_block, cli=cli, user_guide=run.user_guide, report=print)
    return "Created llms.txt + llms-full.txt"


def skills(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write the agent skill files and the skills page

    Parameters
    ----------
    run
        The current build, which supplies the package's name and metadata and the API
        reference configuration.
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
    SkillsWriter(config, layout, run.project.name, run.project.manifest).write(run.api_block)
    return "Created skill.md"


def check_site_url(run: Run, config: Config, log: BuildLog) -> Outcome:
    """
    Warn when the skills page has no site URL for its install instructions

    Parameters
    ----------
    run
        The current build, which supplies the package's project URLs.
    config
        The project's configuration, which supplies the site URL.
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
    if not (config.site_url or urls.get("Documentation", "")):
        log.warn(
            "No site URL found — skills page will show <site-url> placeholders. "
            "Set site_url in great-docs.yml or add a Documentation URL to "
            "[project.urls] in pyproject.toml."
        )
    return None


def changelog(run: Run, config: Config, layout: Layout, *, remote: Remote) -> Outcome:
    """
    Write the changelog page from GitHub Releases and record its navbar link

    Parameters
    ----------
    run
        The current build, which supplies the project's GitHub repository and records the
        navbar link.
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
    contribution = changelog_page.write_page(config, layout, repo, remote, report=print)
    if contribution is None:
        return "No releases found; skipped"
    run.contributions.append(contribution)
    return "Changelog from GitHub Releases"


def tags(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write the tags index and pill data, and record the navbar link and data to embed

    Parameters
    ----------
    run
        The current build, which records the navbar link and data to embed.
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
    contribution = page_tags.write(config, layout, report=print)
    if contribution is None:
        return Skipped("no tagged pages found")
    run.contributions.append(contribution)
    return "Tags processed"


def page_statuses(run: Run, config: Config, layout: Layout) -> Outcome:
    """
    Write the page status data and record it for embedding

    Parameters
    ----------
    run
        The current build, which records the page data.
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
    contribution = page_status.process(config, layout)
    if contribution is None:
        return Skipped("no pages with status")
    run.contributions.append(contribution)
    return "Status badges processed"
