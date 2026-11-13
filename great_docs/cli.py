from __future__ import annotations

import re as re
import sys as sys
from functools import wraps as wraps
from pathlib import Path as Path
from typing import TYPE_CHECKING as TYPE_CHECKING
from typing import Any as Any
from typing import Callable as Callable

import click as click

from ._build import site as site
from ._build.steps import (
    PROJECT_ERRORS as PROJECT_ERRORS,
)
from ._build.steps import (
    USER_CODE_ERRORS as USER_CODE_ERRORS,
)
from ._build.steps import (
    BuildError as BuildError,
)
from ._cli import app as _app
from ._cli.app import OrderedGroup as OrderedGroup
from ._cli.app import cli as cli
from ._cli.build import build as build
from ._cli.build import freeze as freeze
from ._cli.build import freeze_cache as freeze_cache
from ._cli.build import os as os
from ._cli.build import preview as preview
from ._cli.build import print_warning as print_warning
from ._cli.build import quarto as quarto
from ._cli.build import repository as repository
from ._cli.build import serve as serve
from ._cli.build import timings as timings
from ._cli.build import zipfile as zipfile
from ._cli.checks import check_examples as check_examples
from ._cli.checks import check_links as check_links
from ._cli.checks import lint as lint
from ._cli.checks import proofread as proofread
from ._cli.checks import seo as seo
from ._cli.ci import ci as ci
from ._cli.ci import ci_notice as ci_notice
from ._cli.ci import ci_pr_comment as ci_pr_comment
from ._cli.ci import setup_github_pages as setup_github_pages
from ._cli.ci import setup_gitlab_pages as setup_gitlab_pages
from ._cli.evolution import api_diff_cmd as api_diff_cmd
from ._cli.evolution import api_snapshot_cmd as api_snapshot_cmd
from ._cli.evolution import versions as versions
from ._cli.project import changelog as changelog
from ._cli.project import changelog_page as changelog_page
from ._cli.project import config as config
from ._cli.project import init as init
from ._cli.project import migrate_layout as migrate_layout
from ._cli.project import scan as scan
from ._cli.project import uninstall as uninstall
from ._cli.skills import skill as skill
from ._cli.skills import skill_check as skill_check
from ._cli.skills import skill_install as skill_install
from ._cli.skills import skill_list as skill_list
from ._cli.termshow import term_assets as term_assets
from ._cli.termshow import term_check as term_check
from ._cli.termshow import term_edit as term_edit
from ._cli.termshow import term_export as term_export
from ._cli.termshow import term_import_cast as term_import_cast
from ._cli.termshow import term_import_tape as term_import_tape
from ._cli.termshow import term_play as term_play
from ._cli.termshow import term_record as term_record
from ._cli.termshow import term_render as term_render
from ._cli.termshow import term_snap as term_snap
from ._cli.termshow import term_transcript as term_transcript
from ._cli.termshow import term_validate as term_validate
from ._cli.termshow import termshow as termshow
from ._content import user_guide as user_guide
from ._project import Project as Project
from ._project.layout import CONVENTIONAL_DOC_DIRS as CONVENTIONAL_DOC_DIRS
from ._project.layout import Layout as Layout
from ._project.manifest import ManifestError as ManifestError
from ._project.remote import HttpRemote as HttpRemote
from ._project.scaffold import update_gitignore as update_gitignore
from ._reference.exports import Exports as Exports
from ._website import quarto_yml as quarto_yml
from .config import ConfigError as ConfigError
from .core import GreatDocs as GreatDocs

_app.register_commands()


def main() -> None:
    """Main CLI entry point for great-docs."""
    cli()


if __name__ == "__main__":
    main()
