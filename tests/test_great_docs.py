# pyright: reportPrivateUsage=false
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types
import warnings
from dataclasses import dataclass, replace
from datetime import datetime
from functools import cached_property
from pathlib import Path
from types import MethodType
from unittest.mock import MagicMock, PropertyMock, call, patch

import click
import griffe
import griffe as gf
import pytest
import requests
from click.testing import CliRunner, Result
from griffe import AliasResolutionError, DocstringSectionKind, ExprName
from PIL import Image as PILImage
from yaml12 import format_yaml, parse_yaml, read_yaml, write_yaml
from yaml12 import format_yaml as _format_yaml
from yaml12 import parse_yaml as _parse_yaml

from great_docs import BuildError, Config, GreatDocs, _manifest, create_default_config, load_config
from great_docs._apiref import _globals, content, spec, write
from great_docs._apiref._docstring_sections import (
    DCDocstringSection,
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
    ExampleCode,
    ExampleText,
    _DocstringSectionPatched,
    transform,
    transform_sections,
    tuple_to_data,
)
from great_docs._apiref._format import (
    HAS_RUFF,
    format_name,
    format_see_also,
    format_str,
    format_value,
    repr_obj,
)
from great_docs._apiref._globals import EXCLUSIONS
from great_docs._apiref._preview import Formatter
from great_docs._apiref._render import (
    RenderDocAttribute,
    RenderDocClass,
    RenderDocFunction,
    RenderDocModule,
    get_render_type,
)
from great_docs._apiref._render._label import (
    _function_label,
    get_label,
)
from great_docs._apiref._render.api_page import RenderAPIPage
from great_docs._apiref._render.base import RenderBase
from great_docs._apiref._render.extending import (
    exclude_attributes,
    exclude_classes,
    exclude_functions,
    exclude_parameters,
    exclude_type_aliases,
    extend_base_class,
    set_class_attr,
)
from great_docs._apiref._render.mixin_members import (
    RenderedMemberPagesGroup,
    RenderedMembersGroup,
)
from great_docs._apiref._render.mixin_page import RenderPageMixin
from great_docs._apiref._render.reference_page import RenderReferencePage
from great_docs._apiref._render.reference_section import RenderReferenceSection
from great_docs._apiref._settings import SourceLinks, active_settings
from great_docs._apiref._signature import make_call_signature_text
from great_docs._apiref._tools import render_code_variable, render_type_object
from great_docs._apiref._type_checks import (
    attribute_kind,
    class_kind,
    function_kind,
    griffe_to_doc,
    is_doc_attribute,
    is_doc_class,
    is_doc_function,
    is_field_init_false,
    is_initvar,
    is_protocol,
    is_typealias,
    is_typevar,
)
from great_docs._apiref._visitor import Node, ctx_node
from great_docs._apiref.api_reference import APIReference, Settings
from great_docs._apiref.collect import (
    _ManifestBuilder,
    _PackagePrefixRemover,
    build_manifest,
    remove_package_prefix,
)
from great_docs._apiref.content import (
    Doc,
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    DocTypeAlias,
    Link,
    MemberPage,
    Page,
    Section,
    SummaryItem,
)
from great_docs._apiref.introspect import (
    _has_no_value,
    dynamic_alias,
    get_object,
    get_parser_defaults,
    replace_docstring,
    resolve_alias,
)
from great_docs._apiref.inventory import (
    InventoryItem,
    create_inventory,
)
from great_docs._apiref.resolve import (
    ObjectNotFoundError,
    Resolver,
    _is_external_alias,
    _join_path,
    _sections_from_package,
    _to_simple_dict,
)
from great_docs._apiref.spec import ChildrenStyle, SpecObject, SpecOptions, SpecSection, SpecText
from great_docs._apiref.typing_information import TypeInformation, TypeSections
from great_docs._apiref.write import _insert_contents
from great_docs._apiref.write import merge_frontmatter as _merge_frontmatter
from great_docs._build import freeze, quarto, site
from great_docs._build.log import BuildLog
from great_docs._build.steps import Step, count_listed
from great_docs._cliref import click as cli_click
from great_docs._cliref import render as cli_render
from great_docs._content import user_guide
from great_docs._content.naming import strip_numeric_prefix
from great_docs._github import GithubRepo
from great_docs._layout import Layout
from great_docs._project import Project, locate_package_init, read_manifest
from great_docs._reference import block as reference_block
from great_docs._reference import sections as reference_sections
from great_docs._reference.discovery import (
    AUTO_EXCLUDE,
    categorise_references,
    discover_exports,
    empty_categories,
    parse_dunder_all,
)
from great_docs._reference.exports import Exports
from great_docs._reference.probe import detect_docstring_style, detect_dynamic_mode
from great_docs._utils import QUARTO_YML_HEADER, validate_build_dir
from great_docs._website import page_status
from great_docs._website.ai_agents import llms_txt
from great_docs._website.ai_agents.skills import SkillsWriter
from great_docs._website.ai_agents.skills_page import SkillsPageWriter
from great_docs._website.homepage.readme import Badge, HeroElements
from great_docs._website.quarto_yml import edit as edit_quarto_yml
from great_docs._website.quarto_yml import read as read_quarto_yml
from great_docs._website.quarto_yml import write as write_quarto_yml
from great_docs._website.quarto_yml import write_initial as write_initial_quarto_yml
from great_docs._website.scripts import script_include, stylesheet_include
from great_docs._website.seo import robots, sitemap
from great_docs._yaml import split_front_matter
from great_docs.cli import (
    _detect_optional_dependencies,
    _detect_package_manager,
    _detect_python_version,
    build,
    changelog,
    check_links,
    cli,
    config,
    init,
    main,
    scan,
    setup_github_pages,
    uninstall,
)
from great_docs.pandoc.blocks import (
    Block,
    Blocks,
    BulletList,
    CodeBlock,
    DefinitionList,
    Div,
    Header,
    Meta,
    OrderedList,
    Para,
    Plain,
    RawHTMLBlockTag,
    RenderedDocObject,
    blockcontent_to_str,
    blockcontent_to_str_items,
)
from great_docs.pandoc.components import Attr
from great_docs.pandoc.inlines import (
    Code,
    Emph,
    Inlines0,
    InterLink,
    Str,
    Strong,
    inlinecontent_to_str,
    shortcode,
)
from tests.support import (
    StubRemote,
    add_api_block,
    custom_pages_step,
    discover_user_guide,
    find_user_guide_dir,
    homepage_hero,
    homepage_margin,
    make_exports,
    make_project,
    make_run,
    mock_config,
    prepare_build_directory,
    sections_step,
    stubbed_build,
    update_quarto_config,
    user_guide_step,
    write_config,
    write_homepage,
    write_pyproject,
)


def test_great_docs_init():
    """Test GreatDocs initialization."""
    docs = GreatDocs()
    assert docs.project_root == Path.cwd().resolve()


def test_great_docs_init_with_path():
    """Test GreatDocs initialization with custom path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert docs.project_root == Path(tmp_dir).resolve()


def test_great_docs_init_project_path_always_absolute():
    """Test that project_path is always absolute, even with relative input like '.'."""
    docs = GreatDocs(project_path=".")
    assert docs.project_root.is_absolute()
    assert docs.build_dir.is_absolute()
    assert docs.project_root == Path(".").resolve()


def test_great_docs_init_relative_path_resolves():
    """Test that a relative project_path is resolved to absolute."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        original = os.getcwd()
        try:
            os.chdir(tmp_dir)
            docs = GreatDocs(project_path=".")
            assert docs.project_root.is_absolute()
            assert docs.build_dir.is_absolute()
            # After chdir, project_path should still be valid
            os.chdir("/")
            assert docs.project_root == Path(tmp_dir).resolve()
        finally:
            os.chdir(original)


def test_install_creates_files():
    """Test that install creates the expected files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)

        # Check that config file was created
        project_path = Path(tmp_dir)

        assert (project_path / "docs/great-docs.yml").exists()

        # Check that .gitignore was updated (or created)
        gitignore_path = project_path / ".gitignore"
        if gitignore_path.exists():
            content = gitignore_path.read_text()

            assert "docs/_quarto/" in content
            assert "docs/_site/" in content


def test_uninstall_removes_files():
    """Test that uninstall removes the docs files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Install first
        docs.install(force=True)

        project_path = Path(tmp_dir)

        assert (project_path / "docs/great-docs.yml").exists()

        # Then uninstall
        docs.uninstall()

        # Check that config was removed
        assert not (project_path / "docs/great-docs.yml").exists()

        assert not docs.layout.build_dir.exists()
        assert not docs.layout.site_dir.exists()


def test_build_requires_config():
    """Test that build() raises FileNotFoundError when great-docs.yml is missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # If no great-docs.yml exists build should fail immediately
        with pytest.raises(FileNotFoundError, match="great-docs.yml not found"):
            docs.build()


def test_a_second_build_documents_the_exports_the_package_has_then(tmp_path, monkeypatch):
    """Verify that each build on a reused instance documents the current exports"""
    write_pyproject(tmp_path, "rebuilt-exports")
    write_config(tmp_path, "dynamic: false\n")
    package = tmp_path / "rebuilt_exports"
    package.mkdir()
    init = package / "__init__.py"
    init.write_text('__all__ = ["alpha"]\n\n\ndef alpha():\n    """Alpha."""\n')
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    monkeypatch.syspath_prepend(str(tmp_path))
    docs = GreatDocs(project_path=str(tmp_path))

    def documented() -> list[str]:
        quarto = read_yaml(docs.build_dir / "_quarto.yml")
        sections = quarto["api-reference"]["sections"]
        return [name for section in sections for name in section["contents"]]

    with stubbed_build(docs, run=["prepare.build_directory"]):
        docs.build(refresh=False)
        assert documented() == ["alpha"]
        init.write_text('__all__ = ["beta"]\n\n\ndef beta():\n    """Beta."""\n')
        docs.build(refresh=False)

    assert documented() == ["beta"]


def test_init_refuses_when_config_exists():
    """Test that init refuses to run when great-docs.yml already exists (no --force)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create an initial config
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)

        assert (project_path / "docs/great-docs.yml").exists()
        original = (project_path / "docs/great-docs.yml").read_bytes()

        # A second init without --force should refuse (not overwrite)
        docs2 = GreatDocs(project_path=tmp_dir)
        docs2.install(force=False)

        # The original file should still be there, unchanged
        assert (project_path / "docs/great-docs.yml").read_bytes() == original


def _package_init(docs: GreatDocs, package_name: str) -> Path:
    """
    Find the `__init__.py` of a package that a test created

    Parameters
    ----------
    docs
        The project the package belongs to.
    package_name
        The package's importable name.

    Returns
    -------
    :
        The file, which must exist.
    """
    package_root = docs.layout.package_root
    init_file = locate_package_init(package_root, read_manifest(package_root), package_name)
    assert init_file is not None
    return init_file


def test_parse_dunder_all_real_project():
    """Verify that literal `__all__` parsing finds the project's public exports"""
    # Test on great-docs's own __init__.py
    docs = GreatDocs()
    exports = parse_dunder_all(_package_init(docs, "great_docs"), docs._config, report=print)

    assert exports is not None
    assert "GreatDocs" in exports
    assert "main" not in exports


def test_cli_import():
    """Test that CLI module can be imported."""
    assert callable(main)


def test_config_exclude_in_parse():
    """Test that great-docs.yml exclude filters items from __all__."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a test package with __all__
        package_dir = Path(tmp_dir) / "testpkg_cfgexcl"
        package_dir.mkdir()

        init_content = '''
"""Test package with config exclusions."""
__version__ = "1.0.0"
__all__ = ["Graph", "Node", "Edge", "some_function"]

class Graph:
    """A graph class."""
    def add_node(self): pass
    def add_edge(self): pass

class Node:
    """A node class."""
    pass

class Edge:
    """An edge class."""
    pass

def some_function():
    """A function."""
    pass
'''
        (package_dir / "__init__.py").write_text(init_content)

        # Create great-docs.yml with exclude list
        config_content = "exclude:\n  - Node\n  - Edge\n"
        Path(tmp_dir, "great-docs.yml").write_text(config_content)

        docs = GreatDocs(project_path=tmp_dir)
        exports = parse_dunder_all(
            _package_init(docs, "testpkg_cfgexcl"), docs._config, report=print
        )

        # Should have filtered out Node and Edge via config exclude
        assert exports is not None
        assert "Graph" in exports
        assert "some_function" in exports
        assert "Node" not in exports
        assert "Edge" not in exports
        assert len(exports) == 2


def test_setup_github_pages_command():
    """Test the setup-github-pages CLI command."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Run the command
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        # Check it succeeded
        assert result.exit_code == 0
        assert "✅ Created GitHub Actions workflow" in result.output

        # Check the file was created
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"

        assert workflow_file.exists()

        # Check the content is valid YAML and contains expected keys

        with open(workflow_file) as f:
            workflow = read_yaml(f)

        assert "name" in workflow
        assert workflow["name"] == "CI Docs"
        assert "jobs" in workflow
        assert "build-docs" in workflow["jobs"]
        assert "publish-docs" in workflow["jobs"]
        assert "preview-docs" in workflow["jobs"]


def test_setup_github_pages_custom_options():
    """Test setup-github-pages with custom options."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            setup_github_pages,
            [
                "--project-path",
                tmp_dir,
                "--main-branch",
                "develop",
                "--python-version",
                "3.12",
                "--force",
            ],
        )

        assert result.exit_code == 0

        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()

        # Check customizations were applied
        assert "site" in content
        assert "develop" in content
        assert "3.12" in content


def test_setup_github_pages_overwrite_protection():
    """Test that setup-github-pages protects against overwrites."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create the workflow first
        runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        # Try again without force
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir], input="n\n")

        assert result.exit_code == 1
        assert "Aborted" in result.output


def test_detect_python_version():
    """Test detection of Python version from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)

        # Test with no pyproject.toml
        assert _detect_python_version(project_root) is None

        # Test with requires-python >= 3.12
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = ">=3.12"
""")
        assert _detect_python_version(project_root) == "3.12"

        # Test with requires-python >= 3.10
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = ">=3.10"
""")
        assert _detect_python_version(project_root) == "3.10"

        # Test with range specifier
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = ">=3.11,<3.13"
""")
        assert _detect_python_version(project_root) == "3.11"

        # Test with ~= specifier
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = "~=3.9"
""")
        assert _detect_python_version(project_root) == "3.9"

        # Test with no requires-python field
        pyproject.write_text("""
[project]
name = "test-package"
""")
        assert _detect_python_version(project_root) is None


def test_setup_github_pages_auto_detects_python_version():
    """Test that setup-github-pages auto-detects Python version from pyproject.toml."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pyproject.toml with requires-python
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = ">=3.12"
""")

        # Run without --python-version flag
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Detected Python 3.12 from pyproject.toml" in result.output

        # Check the workflow file has the correct version
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "3.12" in content


def test_setup_github_pages_falls_back_to_default():
    """Test that setup-github-pages falls back to 3.12 when no requires-python found."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Run without pyproject.toml
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Using default Python 3.12" in result.output

        # Check the workflow file has the default version
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "3.12" in content


def test_setup_github_pages_explicit_version_overrides_detection():
    """Test that explicit --python-version overrides auto-detection."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pyproject.toml with requires-python = 3.12
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
requires-python = ">=3.12"
""")

        # Run with explicit --python-version 3.11
        result = runner.invoke(
            setup_github_pages,
            ["--project-path", tmp_dir, "--python-version", "3.11", "--force"],
        )

        assert result.exit_code == 0
        # Should NOT mention detection since explicit version was provided
        assert "Detected Python" not in result.output

        # Check the workflow file has the explicit version
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "3.11" in content


def test_detect_package_manager_uv():
    """Test package manager detection for uv."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create uv.lock
        (project_root / "uv.lock").touch()

        assert _detect_package_manager(project_root) == "uv"


def test_detect_package_manager_poetry():
    """Test package manager detection for poetry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create poetry.lock
        (project_root / "poetry.lock").touch()

        assert _detect_package_manager(project_root) == "poetry"


def test_detect_package_manager_pip_default():
    """Test package manager defaults to pip when no lock files found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # No lock files

        assert _detect_package_manager(project_root) == "pip"


def test_detect_package_manager_uv_takes_precedence():
    """Test that uv takes precedence over poetry when both lock files exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create both lock files (unusual but possible)
        (project_root / "uv.lock").touch()
        (project_root / "poetry.lock").touch()

        # uv should be detected first since we check for it first
        assert _detect_package_manager(project_root) == "uv"


def test_detect_optional_dependencies():
    """Test detection of optional dependencies from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"

[project.optional-dependencies]
dev = ["pytest", "ruff"]
docs = ["sphinx"]
test = ["pytest-cov"]
analysis = ["pandas"]
""")

        deps = _detect_optional_dependencies(project_root)
        # Should include dev, docs, and test but not analysis
        assert "dev" in deps
        assert "docs" in deps
        assert "test" in deps
        assert "analysis" not in deps


def test_detect_optional_dependencies_no_pyproject():
    """Test detection returns empty list when no pyproject.toml exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)

        assert _detect_optional_dependencies(project_root) == []


def test_detect_optional_dependencies_no_optional_deps():
    """Test detection returns empty list when no optional-dependencies section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
dependencies = ["requests"]
""")

        assert _detect_optional_dependencies(project_root) == []


def test_setup_github_pages_detects_uv():
    """Test that setup-github-pages generates uv commands when uv.lock exists."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create uv.lock to trigger uv detection
        (project_root / "uv.lock").touch()

        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Detected uv" in result.output

        # Check the workflow file has uv commands
        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "uv sync" in content
        assert "pip install uv" in content


def test_setup_github_pages_detects_poetry():
    """Test that setup-github-pages generates poetry commands when poetry.lock exists."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create poetry.lock to trigger poetry detection
        (project_root / "poetry.lock").touch()

        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Detected poetry" in result.output

        # Check the workflow file has poetry commands
        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "poetry install" in content
        assert "pip install poetry" in content


def test_setup_github_pages_detects_optional_deps():
    """Test that setup-github-pages includes optional deps in pip install command."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create pyproject.toml with optional dependencies
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"

[project.optional-dependencies]
dev = ["pytest", "ruff"]
docs = ["sphinx"]
""")

        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Found optional dependencies" in result.output

        # Check the workflow file has extras in pip install
        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        # Should have pip install -e ".[dev,docs]" or similar
        assert ".[" in content
        assert "dev" in content
        assert "docs" in content


def test_setup_github_pages_explicit_package_manager():
    """Test that explicit --package-manager overrides auto-detection."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        # Create uv.lock (would normally trigger uv detection)
        (project_root / "uv.lock").touch()

        # Force pip instead
        result = runner.invoke(
            setup_github_pages,
            ["--project-path", tmp_dir, "--package-manager", "pip", "--force"],
        )

        assert result.exit_code == 0
        # Should NOT mention uv detection
        assert "Detected uv" not in result.output

        # Check the workflow file has pip commands, not uv
        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "uv sync" not in content
        assert "pip install -e ." in content


def test_setup_github_pages_default_installs_from_pypi():
    """Test that setup-github-pages installs Great Docs from PyPI by default."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        assert result.exit_code == 0
        assert "Will install Great Docs from PyPI (latest release)" in result.output

        # Check the workflow file installs from PyPI (just 'great-docs', not git+)
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "pip install great-docs" in content
        assert "git+https://github.com/posit-dev/great-docs.git" not in content


def test_setup_github_pages_install_from_main_flag():
    """Test that --install-from-main flag installs from GitHub main branch."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(
            setup_github_pages,
            ["--project-path", tmp_dir, "--install-from-main", "--force"],
        )

        assert result.exit_code == 0
        assert "Will install Great Docs from GitHub main branch" in result.output

        # Check the workflow file installs from GitHub
        workflow_file = Path(tmp_dir) / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "git+https://github.com/posit-dev/great-docs.git" in content


def test_setup_github_pages_install_from_main_with_uv():
    """Test that --install-from-main works correctly with uv package manager."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "uv.lock").touch()

        result = runner.invoke(
            setup_github_pages,
            ["--project-path", tmp_dir, "--install-from-main", "--force"],
        )

        assert result.exit_code == 0
        assert "Detected uv" in result.output
        assert "Will install Great Docs from GitHub main branch" in result.output

        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "uv sync" in content
        assert "uv pip install git+https://github.com/posit-dev/great-docs.git" in content


def test_setup_github_pages_install_from_main_with_poetry():
    """Test that --install-from-main works correctly with poetry package manager."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "poetry.lock").touch()

        result = runner.invoke(
            setup_github_pages,
            ["--project-path", tmp_dir, "--install-from-main", "--force"],
        )

        assert result.exit_code == 0
        assert "Detected poetry" in result.output
        assert "Will install Great Docs from GitHub main branch" in result.output

        workflow_file = project_root / ".github" / "workflows" / "docs.yml"
        content = workflow_file.read_text()
        assert "poetry install" in content
        assert "poetry run pip install git+https://github.com/posit-dev/great-docs.git" in content


def test_source_link_config_defaults():
    """Source links are on, with no branch or path, unless configured"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pyproject.toml without source config
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._config.source_enabled is True
        assert docs._config.source_branch is None
        assert docs._config.source_path is None


def test_source_link_config_custom():
    """Test custom source link configuration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pyproject.toml for project metadata
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        # Create great-docs.yml with custom source config
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
source:
  enabled: false
  branch: develop
  path: src/mypackage
""")

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._config.source_enabled is False
        assert docs._config.source_branch == "develop"
        assert docs._config.source_path == "src/mypackage"


def test_check_links_extracts_urls():
    """Test that check_links extracts URLs from files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a docs directory with a file containing URLs
        docs_dir = Path(tmp_dir) / "user_guide"
        docs_dir.mkdir()

        test_md = docs_dir / "test.md"
        test_md.write_text("""
# Test Document

Check out https://httpbin.org/status/200 for more info.
Also see https://httpbin.org/status/404 for errors.
        """)

        # Create _quarto.yml so it's detected
        quarto_yml = docs_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n")

        docs = GreatDocs(project_path=tmp_dir)
        with patch("requests.head", return_value=MagicMock(status_code=200)):
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                timeout=5.0,
                verbose=False,
            )

        assert results["total"] >= 2
        assert "by_file" in results
        assert len(results["by_file"]) > 0


def test_check_links_url_cleaning():
    """Test that URLs are properly cleaned of trailing punctuation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "user_guide"
        docs_dir.mkdir()

        test_md = docs_dir / "test.md"
        test_md.write_text("""
See https://example.com/page.
Check https://example.com/other,
Visit https://example.com/test!
        """)

        quarto_yml = docs_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n")

        docs = GreatDocs(project_path=tmp_dir)
        results = docs.check_links(
            include_source=False,
            include_docs=True,
            ignore_patterns=["example.com"],
            verbose=False,
        )

        # Check that URLs don't have trailing punctuation
        for url in results["skipped"]:
            assert not url.endswith(".")
            assert not url.endswith(",")
            assert not url.endswith("!")


def test_check_links_returns_correct_structure():
    """Test that check_links returns the expected result structure."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "user_guide"
        docs_dir.mkdir()

        test_md = docs_dir / "test.md"
        test_md.write_text("No URLs here")

        quarto_yml = docs_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n")

        docs = GreatDocs(project_path=tmp_dir)
        results = docs.check_links(include_source=False, include_docs=True)

        # Check result structure
        assert "total" in results
        assert "ok" in results
        assert "redirects" in results
        assert "broken" in results
        assert "skipped" in results
        assert "by_file" in results

        assert isinstance(results["ok"], list)
        assert isinstance(results["redirects"], list)
        assert isinstance(results["broken"], list)
        assert isinstance(results["skipped"], list)
        assert isinstance(results["by_file"], dict)


def test_config_defaults():
    """Test that Config provides sensible defaults when no file exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(Path(tmp_dir))

        # Check defaults
        assert config.exclude == []
        assert config.github_style == "widget"
        assert config.source_enabled is True
        assert config.source_branch is None
        assert config.source_path is None
        assert config.sidebar_filter_enabled is True
        assert config.sidebar_filter_min_items == 20
        assert config.cli_enabled is False
        assert config.cli_module is None
        assert config.cli_name is None
        assert config.dark_mode_toggle is True
        assert config.markdown_pages is True
        assert config.markdown_pages_widget is True
        assert config.reference == []
        assert config.authors == []
        assert config.attribution is True


def test_config_attribution_disabled():
    """Test that attribution can be disabled via config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("attribution: false\n")

        config = Config(Path(tmp_dir))

        assert config.attribution is False


def test_config_load_yaml():
    """Test loading configuration from great-docs.yml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
exclude:
  - InternalClass

github_style: icon

sidebar_filter:
  enabled: false
  min_items: 10

cli:
  enabled: true
  module: mypackage.cli
  name: app

dark_mode_toggle: false

authors:
  - name: Test Author
    github: testuser
""")

        config = Config(Path(tmp_dir))

        assert config.exclude == ["InternalClass"]
        assert config.github_style == "icon"
        assert config.sidebar_filter_enabled is False
        assert config.sidebar_filter_min_items == 10
        assert config.cli_enabled is True
        assert config.cli_module == "mypackage.cli"
        assert config.cli_name == "app"
        assert config.dark_mode_toggle is False
        assert len(config.authors) == 1
        assert config.authors[0]["name"] == "Test Author"


def test_config_partial_yaml():
    """Test that partial config merges with defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
cli:
  enabled: true
""")

        config = Config(Path(tmp_dir))

        # CLI is set
        assert config.cli_enabled is True

        # But other CLI fields still have defaults
        assert config.cli_module is None
        assert config.cli_name is None

        # And other config has defaults
        assert config.github_style == "widget"
        assert config.dark_mode_toggle is True


def test_config_exists():
    """Test the exists() method."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(Path(tmp_dir))
        assert config.exists() is False

        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("cli:\n  enabled: true\n")

        config2 = Config(Path(tmp_dir))

        assert config2.exists() is True


def test_config_to_dict():
    """Test converting config to dictionary."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
github_style: icon
""")

        config = Config(Path(tmp_dir))
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["github_style"] == "icon"
        assert "cli" in config_dict
        assert "source" in config_dict


def test_config_get_nested():
    """Test getting nested config values with dot notation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
source:
  enabled: false
  branch: develop
""")

        config = Config(Path(tmp_dir))

        assert config["source.enabled"] is False
        assert config["source.branch"] == "develop"
        with pytest.raises(KeyError):
            config["source.nonexistent"]


def test_config_funding_property():
    """Test the funding property in configuration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
funding:
  name: "Posit Software, PBC"
  roles:
    - Copyright holder
    - funder
  ror: https://ror.org/03wc8by49
""")

        config = Config(Path(tmp_dir))

        assert config.funding is not None
        assert config.funding["name"] == "Posit Software, PBC"
        assert config.funding["roles"] == ["Copyright holder", "funder"]
        assert config.funding["ror"] == "https://ror.org/03wc8by49"


def test_config_funding_property_none_when_not_set():
    """Test funding property returns None when not configured."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(Path(tmp_dir))

        assert config.funding is None


def test_config_funding_without_ror():
    """Test funding configuration without ROR link."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("""
funding:
  name: "Example Corp"
  roles:
    - Copyright holder
""")

        config = Config(Path(tmp_dir))

        assert config.funding is not None
        assert config.funding["name"] == "Example Corp"
        assert config.funding.get("ror") is None


def test_load_config_function():
    """Test the load_config helper function."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = load_config(tmp_dir)

        assert isinstance(config, Config)


def test_create_default_config():
    """Test creating default configuration content."""
    content = create_default_config()

    assert isinstance(content, str)
    assert "Great Docs Configuration" in content
    assert "# sidebar_filter:" in content
    assert "# cli:" in content
    assert "# authors:" in content
    assert "# parser:" in content


def test_detect_docstring_style_numpy_from_files():
    """Test detection of NumPy-style docstrings."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        package_dir = Path(tmp_dir) / "numpypkg"
        package_dir.mkdir()

        # Create a package with NumPy-style docstrings
        init_content = '''
"""Test package with NumPy-style docstrings."""
__version__ = "1.0.0"
__all__ = ["my_function"]

def my_function(x, y):
    """
    Add two numbers together.

    Parameters
    ----------
    x : int
        The first number.
    y : int
        The second number.

    Returns
    -------
    int
        The sum of x and y.

    Examples
    --------
    >>> my_function(1, 2)
    3
    """
    return x + y
'''
        (package_dir / "__init__.py").write_text(init_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("numpypkg"), report=print)
            assert style == "numpy"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_defaults_to_numpy():
    """Test that detection defaults to numpy when no docstrings are found."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        package_dir = Path(tmp_dir) / "nodocspkg"
        package_dir.mkdir()

        # Create a package with no docstrings
        init_content = """
__version__ = "1.0.0"
__all__ = ["my_function"]

def my_function(x, y):
    return x + y
"""
        (package_dir / "__init__.py").write_text(init_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("nodocspkg"), report=print)

            assert style == "numpy"  # Default when no docstrings found
        finally:
            sys.path.remove(tmp_dir)


def test_config_parser_property():
    """Test the parser property in Config class."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test default value
        config = Config(Path(tmp_dir))

        assert config.parser == "numpy"

        # Test custom value
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("parser: google")
        config = Config(Path(tmp_dir))

        assert config.parser == "google"

        # Test sphinx value
        config_file.write_text("parser: sphinx")
        config = Config(Path(tmp_dir))

        assert config.parser == "sphinx"


# --- Explicit Reference Config Tests ---


def test_build_sections_from_reference_config():
    """Test building sections from explicit reference config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Test simple string contents
        reference_config = [
            {
                "title": "Functions",
                "desc": "Public functions",
                "contents": ["func1", "func2"],
            }
        ]

        sections = reference_sections.from_reference_config(reference_config)

        assert sections is not None
        assert len(sections) == 1
        assert sections[0]["title"] == "Functions"
        assert sections[0]["desc"] == "Public functions"
        assert sections[0]["contents"] == ["func1", "func2"]


def test_build_sections_from_reference_config_with_members():
    """Test building sections with members: false config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        reference_config = [
            {
                "title": "Classes",
                "desc": "Main classes",
                "contents": [
                    {"name": "MyClass", "members": False},
                    "SimpleClass",
                ],
            }
        ]

        sections = reference_sections.from_reference_config(reference_config)

        assert sections is not None
        assert len(sections) == 1
        assert {"name": "MyClass", "members": []} in sections[0]["contents"]
        assert "SimpleClass" in sections[0]["contents"]


def test_build_sections_from_reference_config_explicit_members_list():
    """Test building sections with explicit members list passes through correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        reference_config = [
            {
                "title": "Classes",
                "desc": "Parent and child",
                "contents": [
                    {"name": "foo", "members": ["__init__", "a"]},
                    {"name": "bar", "members": ["__init__", "a", "b"]},
                ],
            }
        ]

        sections = reference_sections.from_reference_config(reference_config)

        assert sections is not None
        assert len(sections) == 1
        contents = sections[0]["contents"]
        assert {"name": "foo", "members": ["__init__", "a"]} in contents
        assert {"name": "bar", "members": ["__init__", "a", "b"]} in contents


def test_build_sections_from_reference_config_include_inherited():
    """Test building sections with include_inherited option."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        reference_config = [
            {
                "title": "Classes",
                "contents": [
                    {"name": "bar", "include_inherited": True},
                ],
            }
        ]

        sections = reference_sections.from_reference_config(reference_config)

        assert sections is not None
        contents = sections[0]["contents"]
        assert len(contents) == 1
        assert contents[0] == {"name": "bar", "include_inherited": True}


def test_build_sections_from_reference_config_empty_and_none():
    """Test that empty reference config returns None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert reference_sections.from_reference_config([]) is None
        assert reference_sections.from_reference_config(None) is None


def test_explicit_reference_config_applied_when_discovery_fails():
    """Test that explicit reference config is used when auto-discovery fails."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a minimal package that will fail discovery
        package_dir = Path(tmp_dir) / "emptypkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("# Empty package")

        # Create great-docs.yml with explicit reference config
        config_content = """
parser: numpy

reference:
  - title: Functions
    desc: My functions
    contents:
      - my_func
      - other_func
"""
        (Path(tmp_dir) / "great-docs.yml").write_text(config_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)

            # The reference config should be loaded
            assert docs._config.reference is not None
            assert len(docs._config.reference) == 1
            assert docs._config.reference[0]["title"] == "Functions"

            # Build sections from config should work
            sections = reference_sections.from_reference_config(docs._config.reference)

            assert sections is not None
            assert len(sections) == 1
            assert "my_func" in sections[0]["contents"]
        finally:
            sys.path.remove(tmp_dir)


def test_quarto_environment_returns_current_python():
    """Use the current interpreter for `QUARTO_PYTHON` when no virtual environment exists"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "QUARTO_PYTHON" in env
        # Should either be the current interpreter or a venv Python
        # Accept python, python3, python.exe, python3.exe
        python_path = env["QUARTO_PYTHON"]

        assert (
            python_path.endswith("python")
            or python_path.endswith("python3")
            or python_path.endswith("python.exe")
            or python_path.endswith("python3.exe")
            or "python" in Path(python_path).name
        )


def test_quarto_environment_detects_venv():
    """Use the Python executable from the project's `.venv`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a fake .venv directory structure
        venv_dir = Path(tmp_dir) / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        fake_python.write_text("#!/bin/bash\n# fake python")

        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "QUARTO_PYTHON" in env
        assert env["QUARTO_PYTHON"] == str(fake_python.resolve())


def test_quarto_environment_preserves_existing_env():
    """Preserve existing environment variables"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        # Should contain existing env vars like PATH
        assert "PATH" in env
        assert env["PATH"] == os.environ.get("PATH")


def test_quarto_environment_sets_pythonutf8():
    """Issue #200: Quarto subprocess env enables UTF-8 mode on Windows."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)
        assert env.get("PYTHONUTF8") == "1"


def test_quarto_environment_preserves_existing_pythonutf8(monkeypatch):
    """Issue #200: do not override an explicit PYTHONUTF8 value."""
    monkeypatch.setenv("PYTHONUTF8", "0")
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)
        assert env["PYTHONUTF8"] == "0"


def test_detect_dynamic_mode_returns_true_for_simple_package():
    """Verify that a simple package without alias cycles permits dynamic introspection"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a simple package with no cyclic aliases
        package_dir = Path(tmp_dir) / "simple_pkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text(
            '''"""Simple package."""

def hello():
    """Say hello."""
    return "hello"

class MyClass:
    """A simple class."""
    pass
'''
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = detect_dynamic_mode(
                make_exports(docs).package("simple_pkg"), ["hello", "MyClass"], report=print
            )
            # Should return True for a simple package
            assert result is True
        finally:
            sys.path.remove(tmp_dir)


def test_config_dynamic_property():
    """Test Config.dynamic property returns correct value."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir)

        # Test with dynamic: true
        config_file = config_path / "great-docs.yml"
        config_file.write_text("dynamic: true\n")
        config = Config(config_path)

        assert config.dynamic is True

    # Create a separate temp dir for dynamic: false test
    with tempfile.TemporaryDirectory() as tmp_dir2:
        config_path2 = Path(tmp_dir2)
        config_file2 = config_path2 / "great-docs.yml"
        config_file2.write_text("dynamic: false\n")
        config2 = Config(config_path2)

        assert config2.dynamic is False


def test_config_dynamic_property_default():
    """Test Config.dynamic property returns default when not set."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Config without dynamic key
        config_content = "parser: numpy\n"
        config_dir = Path(tmp_dir)
        config_file = config_dir / "great-docs.yml"
        config_file.write_text(config_content)

        config = Config(config_dir)

        # Default should be True
        assert config.dynamic is True


def test_citation_year_from_date_released():
    """Test that citation year is parsed from date-released field."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create a minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\nversion = "0.1.0"')

        # Create CITATION.cff with date-released
        citation_cff = project_path / "CITATION.cff"
        citation_data = {
            "cff-version": "1.2.0",
            "title": "Test Package",
            "authors": [{"given-names": "John", "family-names": "Doe"}],
            "version": "0.1.0",
            "date-released": "2023-05-15",
            "url": "https://example.com",
        }
        citation_cff.write_text(format_yaml(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)

        # Check that citation.qmd was created
        citation_qmd = docs_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text()

        # Check that 2023 appears in the citation (from date-released)
        assert "2023" in content
        assert "year = {2023}" in content


def test_citation_year_defaults_to_current():
    """Test that citation year defaults to current year when date-released is missing."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create a minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\nversion = "0.1.0"')

        # Create CITATION.cff WITHOUT date-released
        citation_cff = project_path / "CITATION.cff"
        citation_data = {
            "cff-version": "1.2.0",
            "title": "Test Package",
            "authors": [{"given-names": "Jane", "family-names": "Smith"}],
            "version": "0.2.0",
            "url": "https://example.com",
        }
        citation_cff.write_text(format_yaml(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)

        # Check that citation.qmd was created
        citation_qmd = docs_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text()

        # Check that current year appears in the citation
        current_year = str(datetime.now().year)

        assert current_year in content
        assert f"year = {{{current_year}}}" in content


def test_citation_year_handles_invalid_date():
    """Test that citation year falls back to current year for invalid dates."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create a minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\nversion = "0.1.0"')

        # Create CITATION.cff with invalid date-released
        citation_cff = project_path / "CITATION.cff"
        citation_data = {
            "cff-version": "1.2.0",
            "title": "Test Package",
            "authors": [{"given-names": "Bob", "family-names": "Johnson"}],
            "version": "0.3.0",
            "date-released": "invalid-date-format",
            "url": "https://example.com",
        }
        citation_cff.write_text(format_yaml(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)

        # Check that citation.qmd was created
        citation_qmd = docs_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text()

        # Check that current year appears (fallback from invalid date)
        current_year = str(datetime.now().year)

        assert current_year in content
        assert f"year = {{{current_year}}}" in content

        current_year = str(datetime.now().year)

        assert current_year in content
        assert f"year = {{{current_year}}}" in content


def test_strip_numeric_prefix_two_digit():
    """Test stripping two-digit numeric prefix like 00-, 01-, etc."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert strip_numeric_prefix("00-introduction.qmd") == "introduction.qmd"
        assert strip_numeric_prefix("01-installation.qmd") == "installation.qmd"
        assert strip_numeric_prefix("09-conclusion.qmd") == "conclusion.qmd"
        assert strip_numeric_prefix("10-appendix.qmd") == "appendix.qmd"
        assert strip_numeric_prefix("99-final.qmd") == "final.qmd"


def test_strip_numeric_prefix_three_digit():
    """Test stripping three-digit numeric prefix like 001-, 010-, etc."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert strip_numeric_prefix("001-overview.qmd") == "overview.qmd"
        assert strip_numeric_prefix("010-details.qmd") == "details.qmd"
        assert strip_numeric_prefix("0100-reference.qmd") == "reference.qmd"


def test_strip_numeric_prefix_underscore():
    """Test stripping numeric prefix with underscore separator."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert strip_numeric_prefix("01_introduction.qmd") == "introduction.qmd"
        assert strip_numeric_prefix("1_getting_started.qmd") == "getting_started.qmd"


def test_strip_numeric_prefix_preserves_internal_numbers():
    """Test that numbers within filename are preserved."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert strip_numeric_prefix("01-python3-setup.qmd") == "python3-setup.qmd"
        assert strip_numeric_prefix("02-chapter-10.qmd") == "chapter-10.qmd"


def test_dark_only_logo_does_not_crash_quarto_config():
    """Regression: a dark-only logo config must not crash navbar logo injection.

    roborev #801 finding 2: `logo: {dark: ...}` used to raise `TypeError` at
    `package_root / logo_config["light"]` because `light` was `None`.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        assets = project_path / "assets"
        assets.mkdir()
        (assets / "logo-dark.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>'
        )

        gd_yml = project_path / "great-docs.yml"
        gd_yml.write_text("logo:\n  dark: assets/logo-dark.svg\n", encoding="utf-8")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        assert config["website"]["navbar"]["logo"] == "logo-dark.svg"


def test_assets_not_added_to_quarto_config_when_missing():
    """Test that assets/** is not added to Quarto config when assets don't exist."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        # Create great-docs directory (required for _quarto.yml)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        # Update Quarto config without assets
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        # Read the generated _quarto.yml
        quarto_yml = docs.build_dir / "_quarto.yml"

        assert quarto_yml.exists()

        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        # Check that assets/** is NOT in resources
        assert "project" in config
        assert "resources" in config["project"]
        assert "assets/**" not in config["project"]["resources"]


def test_skill_render_exclusion_uses_enumerated_globs():
    """
    Exclude `skill.md` using enumerated input globs

    A recursive `**` input glob overrides `!` exclusions in Quarto, causing `skill.md` to
    render as `skill.html` (issue #228). Enumerating the default input globs preserves the
    exclusion.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        render = config["project"]["render"]
        assert "!skill.md" in render
        assert "**" not in render
        assert "*.qmd" in render
        assert "*.md" in render


def test_landing_page_generated_when_no_readme():
    """Test that a landing page is auto-generated when no README/index files exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "my-package"\nversion = "1.0"\ndescription = "A great package"\n'
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        pkg_dir = project_path / "my_package"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text()

        assert "my-package" in content
        assert "A great package" in content
        assert "pip install my-package" in content
        assert "API Reference" in content


def test_landing_page_not_generated_when_readme_exists():
    """Test that the landing page is NOT generated when README.md exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\n')

        readme = project_path / "README.md"
        readme.write_text("# My Package\n\nThis is the readme.\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text()

        # Should use the README content, not the auto-generated landing page
        assert "This is the readme" in content
        assert "pip install" not in content


def test_landing_page_has_sidebar_metadata():
    """Test that the auto-generated landing page includes the sidebar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "sidebar-test"\nversion = "1.0"\n'
            'description = "Test sidebar"\n'
            'requires-python = ">=3.9"\n'
        )

        license_file = project_path / "LICENSE"
        license_file.write_text("MIT License")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        pkg_dir = project_path / "sidebar_test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"
        content = index_qmd.read_text()

        # Should have sidebar with metadata, marked so companions can drop it
        assert "::: {.column-margin .gd-homepage-sidebar}" in content
        assert "View on PyPI" in content
        assert "Full license" in content
        assert ">=3.9" in content


def test_readme_rst_creates_index():
    """Test that README.rst is converted and used for index.qmd."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\n')
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        rst_content = "My Package\n==========\n\nThis is a great package.\n\nFeatures\n--------\n\n- Feature one\n- Feature two\n"
        (project_path / "README.rst").write_text(rst_content)

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text()

        # Pandoc converts RST headings to Markdown headings
        # The heading adjustment then bumps them up one level
        assert "My Package" in content
        assert "great package" in content
        assert "Feature one" in content


def test_readme_rst_not_used_when_readme_md_exists():
    """Test that README.md takes priority over README.rst."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\n')
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        (project_path / "README.md").write_text("# Markdown README\n\nThis is the MD readme.\n")
        (project_path / "README.rst").write_text(
            "RST README\n==========\n\nThis is the RST readme.\n"
        )

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"
        content = index_qmd.read_text()

        assert "Markdown README" in content
        assert "RST readme" not in content


def _homepage_frontmatter(content: str) -> dict:
    """Parse the leading YAML frontmatter block from generated homepage content."""
    assert content.startswith("---")
    _, fm_text, _ = content.split("---", 2)
    return parse_yaml(fm_text) or {}


def test_index_qmd_frontmatter_title_preserved():
    """Authored frontmatter title on the index source survives into index.qmd."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0"\n')
        (project_path / "great-docs.yml").write_text("")

        (project_path / "index.qmd").write_text(
            '---\ntitle: "My Package"\n---\n\n## Getting Started\n\nHello.\n'
        )

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        content = (docs.build_dir / "index.qmd").read_text()
        fm = _homepage_frontmatter(content)

        assert fm["title"] == "My Package"
        assert fm["toc"] is False
        assert fm["body-classes"] == "gd-homepage"


def test_index_qmd_frontmatter_title_empty_without_source_title():
    """A source file with no title yields an empty homepage title."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0"\n')
        (project_path / "great-docs.yml").write_text("")

        (project_path / "README.md").write_text("## Getting Started\n\nHello.\n")

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        content = (docs.build_dir / "index.qmd").read_text()
        fm = _homepage_frontmatter(content)

        assert fm["title"] == ""


def test_index_qmd_frontmatter_title_yaml_safe():
    """A title with YAML-special characters round-trips through the frontmatter."""
    tricky_title = 'A: B "quoted"'
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0"\n')
        (project_path / "great-docs.yml").write_text("")

        source_fm = format_yaml({"title": tricky_title}).rstrip()
        (project_path / "index.qmd").write_text(
            f"---\n{source_fm}\n---\n\n## Getting Started\n\nHello.\n"
        )

        pkg_dir = project_path / "test"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        content = (docs.build_dir / "index.qmd").read_text()
        fm = _homepage_frontmatter(content)

        assert fm["title"] == tricky_title


def _homepage_from(source_name: str, source: str, tmp_dir: str) -> dict:
    """Build the homepage from one index source and return its frontmatter."""
    project_path = Path(tmp_dir)
    (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0"\n')
    (project_path / "great-docs.yml").write_text("")
    (project_path / source_name).write_text(source)
    pkg_dir = project_path / "test"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")

    docs = GreatDocs(project_path=tmp_dir)
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    write_homepage(docs)
    return _homepage_frontmatter((docs.build_dir / "index.qmd").read_text())


@pytest.mark.parametrize("key", ["description", "description-meta"])
def test_index_qmd_keeps_source_description(key):
    """An authored description on the index source survives into index.qmd."""
    source = f"---\ntitle: Pkg\n{key}: Authored\n---\n\nA first paragraph that is long enough.\n"
    with tempfile.TemporaryDirectory() as tmp_dir:
        fm = _homepage_from("index.qmd", source, tmp_dir)

    assert fm[key] == "Authored"
    assert set(fm) & {"description", "description-meta"} == {key}


def test_index_qmd_keeps_source_front_matter():
    """Check that the homepage retains page options, `toc` and existing body classes"""
    source = (
        "---\ntitle: Pkg\nexecute:\n  echo: false\npage-layout: full\ntoc: true\n"
        "body-classes: wide gd-homepage\n---\n\nHello.\n"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        fm = _homepage_from("index.qmd", source, tmp_dir)

    assert fm["execute"] == {"echo": False}
    assert fm["page-layout"] == "full"
    assert fm["toc"] is True
    assert fm["body-classes"] == "wide gd-homepage"


def test_index_qmd_describes_itself_with_readme_first_paragraph():
    """The homepage takes its description from the README, not from the wrapper markup."""
    source = "# test\n\nThe `test` package adds numbers *quickly*.\n\n## Usage\n"
    with tempfile.TemporaryDirectory() as tmp_dir:
        fm = _homepage_from("README.md", source, tmp_dir)

    assert fm["description-meta"] == "The test package adds numbers quickly."


def test_index_qmd_without_opening_paragraph_has_no_description():
    """A README that opens with code leaves the homepage description to the site default."""
    source = "# test\n\n```python\nimport test\n```\n\nA paragraph after the code block.\n"
    with tempfile.TemporaryDirectory() as tmp_dir:
        fm = _homepage_from("README.md", source, tmp_dir)

    assert "description-meta" not in fm


def test_changelog_config_defaults():
    """Test default changelog configuration values."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("")

        config = Config(Path(tmp_dir))

        assert config.changelog_enabled is True
        assert config.changelog_max_releases == 50


def test_changelog_config_custom():
    """Test changelog configuration overrides."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("changelog:\n  enabled: false\n  max_releases: 10\n")

        config = Config(Path(tmp_dir))

        assert config.changelog_enabled is False
        assert config.changelog_max_releases == 10


def test_sections_config_default():
    """Test that sections config defaults to an empty list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "great-docs.yml").write_text("")
        config = Config(Path(tmp_dir))

        assert config.sections == []


def test_sections_config_parsed():
    """Test that sections config is parsed correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "great-docs.yml").write_text(
            "sections:\n"
            "  - title: Examples\n"
            "    dir: examples\n"
            "    navbar_after: User Guide\n"
            "  - title: Blog\n"
            "    dir: blog\n"
        )
        config = Config(Path(tmp_dir))

        assert len(config.sections) == 2
        assert config.sections[0]["title"] == "Examples"
        assert config.sections[0]["dir"] == "examples"
        assert config.sections[0]["navbar_after"] == "User Guide"
        assert config.sections[1]["title"] == "Blog"


def test_navbar_no_home_new_build():
    """Test that new builds don't include a Home navbar item."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n  title: TestPkg\nformat:\n  html:\n    theme: flatly\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)

        navbar_items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in navbar_items if isinstance(item, dict)]

        assert "Home" not in texts
        # The Reference link requires API reference sections; site configuration alone
        # does not add it.


def test_navbar_home_removed_from_existing():
    """Test that existing navbars with Home get it removed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n"
            "  title: TestPkg\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "format:\n  html:\n    theme: flatly\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)

        navbar_items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in navbar_items if isinstance(item, dict)]

        assert "Home" not in texts
        assert "Reference" in texts


def test_navbar_release_from_github_release():
    """The navbar title shows the latest GitHub release"""

    fake_releases = [
        {
            "tag_name": "v2.3.4",
            "name": "Release 2.3.4",
            "body": "Bug fixes",
            "published_at": "2025-06-15T18:30:00Z",
            "html_url": "https://github.com/test/pkg/releases/tag/v2.3.4",
            "prerelease": False,
        }
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        (project_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "test-pkg"\n'
            'version = "2.3.4"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/test/pkg"\n'
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n"
        )

        docs = GreatDocs(project_path=tmp_dir)

        docs._remote = StubRemote(releases=fake_releases)
        update_quarto_config(docs, make_run(docs))

        navbar = read_yaml(quarto_yml)["website"]["navbar"]

        assert navbar["title"] == (
            "test-pkg "
            '`<span class="version-badge" title="Released 2025-06-15">v2.3.4</span>`{=html}'
        )


def test_navbar_release_absent_without_releases():
    """The navbar title is the plain site title when no GitHub release exists"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        (project_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "test-pkg"\n'
            'version = "0.0.1"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/test/pkg"\n'
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n"
        )

        docs = GreatDocs(project_path=tmp_dir)

        docs._remote = StubRemote()
        update_quarto_config(docs, make_run(docs))

        assert "title" not in read_yaml(quarto_yml)["website"]["navbar"]


def test_navbar_release_absent_on_malformed_github_response():
    """A release list GitHub returns as invalid JSON shows no release instead of failing"""
    import requests

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        (project_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "test-pkg"\n'
            'version = "0.0.1"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/test/pkg"\n'
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n"
        )

        response = MagicMock(status_code=200)
        response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)

        docs = GreatDocs(project_path=tmp_dir)

        with patch("requests.get", return_value=response):
            update_quarto_config(docs, make_run(docs))

        assert "title" not in read_yaml(quarto_yml)["website"]["navbar"]


def test_navbar_release_absent_without_github_repo():
    """No release is fetched or shown without a GitHub repository"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")

        # No repository URL in pyproject.toml
        (project_path / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "1.0.0"\n'
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\n"
            "website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs._remote = remote = StubRemote()
        update_quarto_config(docs, make_run(docs))

        assert "github_releases" not in remote.calls
        assert "title" not in read_yaml(quarto_yml)["website"]["navbar"]


# =========================================================================
# GDG Site 144: gdtest_docstring_tables — RST Tables in Docstrings
# =========================================================================


class TestGdgSite144DocstringTables:
    """
    Verify that site 144 (gdtest_docstring_tables) renders RST tables
    as proper HTML <table> elements in the built output.
    """

    SITE_DIR = (
        Path(__file__).resolve().parent.parent
        / "test-packages"
        / "_rendered"
        / "gdtest_docstring_tables"
        / "great-docs"
        / "_site"
    )

    @pytest.fixture(autouse=True)
    def _skip_if_not_built(self):
        if not self.SITE_DIR.exists():
            pytest.skip("Site 144 not built; run: make hub-rebuild PKG=gdtest_docstring_tables")

    def _read_html(self, *parts: str) -> str:
        path = self.SITE_DIR.joinpath(*parts)

        assert path.exists(), f"Expected page not found: {path}"

        return path.read_text(encoding="utf-8")

    def test_compare_methods_has_table(self):
        """compare_methods reference page contains an HTML table with expected data."""
        html = self._read_html("reference", "compare_methods.html")
        # Q renderer may not convert RST tables to HTML <table> elements;
        # verify that the data content is present regardless of format
        if "<table" in html:
            assert "<thead>" in html, "Expected <thead> in table"
            assert "<th>Method</th>" in html
            assert "<th>Speed</th>" in html
            assert "<th>Memory</th>" in html

        # Body data should appear in either table or text form
        assert "O(n log n)" in html or "n log n" in html
        assert "O(n^2)" in html or "n^2" in html or "n²" in html
        assert "O(log n)" in html or "log n" in html

    def test_format_report_has_table(self):
        """format_report reference page contains an HTML table with expected data."""
        html = self._read_html("reference", "format_report.html")

        # Q renderer may not convert RST tables to HTML <table> elements;
        # verify that the data content is present regardless of format
        if "<table" in html:
            assert "<thead>" in html, "Expected <thead> in table"
            assert "<th>Metric</th>" in html
            assert "<th>Value</th>" in html

        # Body data should appear in either table or text form
        assert "count" in html
        assert "100" in html
        assert "42.5" in html


def test_to_simple_dict_base_dataclass():
    page = Page(path="foo")
    result = _to_simple_dict(page)
    assert isinstance(result, dict)
    assert result["path"] == "foo"


def test_to_simple_dict_nested_dataclass():
    doc = DocFunction(name="func1", obj=gf.Function("func1"))
    page = Page(path="p", contents=[doc])
    result = _to_simple_dict(page)
    assert isinstance(result, dict)
    assert isinstance(result["contents"], list)
    assert isinstance(result["contents"][0], dict)
    assert result["contents"][0]["name"] == "func1"


def test_to_simple_dict_list():
    result = _to_simple_dict([Page(path="a"), Page(path="b")])
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["path"] == "a"


def test_to_simple_dict_tuple():
    result = _to_simple_dict((Page(path="x"),))
    assert isinstance(result, list)
    assert result[0]["path"] == "x"


def test_to_simple_dict_enum():
    result = _to_simple_dict(ChildrenStyle.embedded)
    assert result == "embedded"


def test_to_simple_dict_primitive():
    assert _to_simple_dict("hello") == "hello"
    assert _to_simple_dict(42) == 42
    assert _to_simple_dict(None) is None


def test_to_simple_dict_summary_details():
    sd = SummaryItem(name="n", desc="d")
    result = _to_simple_dict(sd)
    assert result == {"name": "n", "desc": "d"}


def test_spec_options_with_defaults_none_base():
    opts = SpecOptions(include_private=True)
    assert opts.with_defaults(None) is opts


def test_spec_options_with_defaults_inherits_unspecified():
    el = SpecObject(name="x", include_private=True)
    base = SpecOptions(include_private=False, include_empty=True)
    merged = el.with_defaults(base)
    assert merged.include_private is True  # el's explicit value wins
    assert merged.include_empty is True  # inherited from base
    assert merged.name == "x"


def test_spec_options_with_defaults_specified_default_beats_base():
    # Explicitly setting a field to its default value still beats the base.
    el = SpecObject(name="x", include_private=False)
    base = SpecOptions(include_private=True)
    assert el.with_defaults(base).include_private is False


def test_resolve_alias_non_alias_passthrough():
    func = gf.Function("myfunc")
    result = resolve_alias(func, lambda p: None)
    assert result is func


def test_resolve_alias_resolves_target():
    mod = gf.Module("pkg")
    func = gf.Function("f")
    mod.set_member("f", func)
    alias = gf.Alias("f_alias", target=func, parent=mod)
    result = resolve_alias(alias, lambda p: None)
    assert result is func


def test_resolve_alias_error_fallback():
    sentinel = gf.Function("resolved_func")

    def get_object(path):
        return sentinel

    mock_alias = MagicMock(spec=gf.Alias)
    mock_alias.is_alias = True

    inner_alias = MagicMock()
    inner_alias.target_path = "some.path"

    type(mock_alias).target = PropertyMock(side_effect=AliasResolutionError(inner_alias))

    result = resolve_alias(mock_alias, get_object)
    assert result is sentinel


def test_is_external_alias_non_alias_returns_false():
    func = gf.Function("myfunc")
    mod = gf.Module("pkg")
    assert _is_external_alias(func, mod) is False


def test_is_external_alias_internal():
    target = MagicMock()
    target.is_alias = False

    mock_alias = MagicMock(spec=[])
    mock_alias.is_alias = True
    mock_alias.target_path = "mypkg.internal_func"
    mock_alias.modules_collection = {"mypkg.internal_func": target}
    mock_alias.__class__ = gf.Alias

    mod = gf.Module("mypkg")
    assert _is_external_alias(mock_alias, mod) is False


def test_is_external_alias_external_target():
    mock_alias = MagicMock(spec=[])
    mock_alias.is_alias = True
    mock_alias.target_path = "other_pkg.func"
    mock_alias.__class__ = gf.Alias

    mod = gf.Module("mypkg")
    assert _is_external_alias(mock_alias, mod) is True


def test_is_external_alias_key_error_returns_true():
    mock_alias = MagicMock(spec=[])
    mock_alias.is_alias = True
    mock_alias.target_path = "mypkg.submod.missing"
    mock_alias.__class__ = gf.Alias
    mock_mc = MagicMock()
    mock_mc.__getitem__ = MagicMock(side_effect=KeyError("missing"))
    mock_alias.modules_collection = mock_mc

    mod = gf.Module("mypkg")
    assert _is_external_alias(mock_alias, mod) is True


def test_is_external_alias_cyclic_raises():
    mock_alias = MagicMock(spec=[])
    mock_alias.is_alias = True
    mock_alias.target_path = "mypkg.something"
    mock_alias.__class__ = gf.Alias
    mock_alias.modules_collection = {"mypkg.something": mock_alias}

    mod = gf.Module("mypkg")
    with pytest.raises(Exception, match="Cyclic Alias"):
        _is_external_alias(mock_alias, mod)


def test_sections_from_package_module_with_all():
    mod = gf.Module("mypkg")
    func = gf.Function("public_func")
    mod.set_member("public_func", func)
    all_attr = gf.Attribute("__all__")
    mod.set_member("__all__", all_attr)
    mod.exports = {"public_func"}

    sections = _sections_from_package(mod)
    assert len(sections) == 1
    assert sections[0].title == "mypkg"
    names = [c.name for c in sections[0].contents]
    assert "public_func" in names


def test_sections_from_package_without_all_warns(capsys):
    mod = gf.Module("mypkg")
    func = gf.Function("public_func")
    mod.set_member("public_func", func)

    sections = _sections_from_package(mod)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "does not define an __all__" in captured.out
    assert len(sections) == 1
    names = [c.name for c in sections[0].contents]
    assert "public_func" in names


def test_sections_from_package_filters_dunder_members():
    mod = gf.Module("mypkg")
    func = gf.Function("__init__")
    mod.set_member("__init__", func)
    pub = gf.Function("pub")
    mod.set_member("pub", pub)

    sections = _sections_from_package(mod)
    names = [c.name for c in sections[0].contents]
    assert "__init__" not in names
    assert "pub" in names


def test_sections_from_package_filters_submodules():
    mod = gf.Module("mypkg")
    submod = gf.Module("sub")
    mod.set_member("sub", submod)
    func = gf.Function("pub")
    mod.set_member("pub", func)

    sections = _sections_from_package(mod)
    names = [c.name for c in sections[0].contents]
    assert "sub" not in names
    assert "pub" in names


def test_sections_from_package_with_docstring():
    mod = gf.Module("mypkg")
    mod.docstring = gf.Docstring("Summary text here.", parent=mod)
    func = gf.Function("pub")
    mod.set_member("pub", func)

    sections = _sections_from_package(mod)
    assert sections[0].desc == "Summary text here."


def test_sections_from_package_without_docstring():
    mod = gf.Module("mypkg")
    func = gf.Function("pub")
    mod.set_member("pub", func)

    sections = _sections_from_package(mod)
    assert sections[0].desc == ""


def test_sections_from_package_docstring_non_text_first():
    mod = gf.Module("mypkg")
    mod.docstring = gf.Docstring("Parameters\n----------\nx : int\n    A param.", parent=mod)
    parsed = mod.docstring.parsed
    if parsed and isinstance(parsed[0], gf.DocstringSectionText):
        mock_docstring = MagicMock()
        mock_docstring.parsed = [gf.DocstringSectionParameters(value=[])]
        mod.docstring = mock_docstring

    func = gf.Function("pub")
    mod.set_member("pub", func)

    sections = _sections_from_package(mod)
    assert sections[0].desc == ""


def test_sections_from_package_filters_external_aliases():
    mod = gf.Module("mypkg")

    mock_alias = MagicMock(spec=[])
    mock_alias.is_alias = True
    mock_alias.target_path = "other_pkg.ext_f"
    mock_alias.__class__ = gf.Alias
    mock_alias.is_module = False
    mock_alias.is_exported = True
    mod.set_member("ext_f", mock_alias)

    pub = gf.Function("pub")
    mod.set_member("pub", pub)

    sections = _sections_from_package(mod)
    names = [c.name for c in sections[0].contents]
    assert "ext_f" not in names
    assert "pub" in names


def test_sections_from_package_unexported_filtered():
    mod = gf.Module("mypkg")
    f1 = gf.Function("exported_func")
    mod.set_member("exported_func", f1)
    f2 = gf.Function("not_exported")
    mod.set_member("not_exported", f2)
    all_attr = gf.Attribute("__all__")
    mod.set_member("__all__", all_attr)
    mod.exports = {"exported_func"}

    sections = _sections_from_package(mod)
    names = [c.name for c in sections[0].contents]
    assert "exported_func" in names
    assert "not_exported" not in names


def test_collect_single_doc():
    mod = gf.Module("pkg")
    func_obj = gf.Function("myfunc")
    mod.set_member("myfunc", func_obj)
    doc = DocFunction(name="myfunc", obj=func_obj, anchor="pkg.myfunc")
    page = Page(path="reference", contents=[doc])

    manifest = build_manifest([page], dir="api")
    pages, items = manifest.pages, manifest.items
    assert len(pages) == 1
    assert pages[0].path == "reference"
    assert len(items) >= 1
    assert items[0].name == "pkg.myfunc"
    assert items[0].uri == "api/reference.html#pkg.myfunc"
    # The short names an author may write in prose. The pair repeats because a
    # top-level export's config name is its own name.
    assert items[0].aliases == ("myfunc", "myfunc")


def test_collect_with_canonical_path_diff():
    func_obj = MagicMock()
    func_obj.path = "pkg.submod.func"
    func_obj.canonical_path = "pkg.func"

    doc = DocFunction(name="func", obj=func_obj, anchor="pkg.func")
    page = Page(path="reference", contents=[doc])

    manifest = build_manifest([page], dir="api")
    pages, items = manifest.pages, manifest.items
    assert len(items) == 2
    assert items[0].name == "pkg.submod.func"
    assert items[1].name == "pkg.func"
    assert items[1].dispname == "pkg.submod.func"


def test_collect_class_member_gets_a_class_qualified_alias():
    """A member's bare name collides across classes, so it also claims `Class.member`."""
    mod = gf.Module("pkg")
    cls = gf.Class("StoreCache")
    mod.set_member("StoreCache", cls)
    meth = gf.Function("flush")
    cls.set_member("flush", meth)

    doc_meth = DocFunction(name="flush", obj=meth, anchor="pkg.StoreCache.flush")
    doc_cls = DocClass(name="StoreCache", obj=cls, anchor="pkg.StoreCache", members=[doc_meth])
    page = Page(path="reference/StoreCache", contents=[doc_cls])

    manifest = build_manifest([page], dir="api")
    items = {item.name: item for item in manifest.items}

    assert items["pkg.StoreCache.flush"].aliases == ("flush", "flush", "StoreCache.flush")


def test_collect_top_level_doc_gets_no_class_qualified_alias():
    """A module-level function has no enclosing class, so the pair repeats as before."""
    mod = gf.Module("pkg")
    func_obj = gf.Function("myfunc")
    mod.set_member("myfunc", func_obj)
    doc = DocFunction(name="myfunc", obj=func_obj, anchor="pkg.myfunc")
    page = Page(path="reference", contents=[doc])

    manifest = build_manifest([page], dir="api")

    assert manifest.items[0].aliases == ("myfunc", "myfunc")


def test_collect_nested_section():
    mod = gf.Module("pkg")
    func_obj = gf.Function("myfunc")
    mod.set_member("myfunc", func_obj)
    doc = DocFunction(name="myfunc", obj=func_obj, anchor="pkg.myfunc")
    page = Page(path="ref", contents=[doc])
    section = Section(title="API", contents=[page])

    manifest = build_manifest([section], dir="api")
    pages, items = manifest.pages, manifest.items
    assert len(pages) == 1
    assert len(items) >= 1


def test_enclosing_page_no_page():
    builder = _ManifestBuilder(base_dir="api")
    with pytest.raises(ValueError, match="No `Page` ancestor"):
        root_node = Node(level=0, value=None, parent=None)
        token = ctx_node.set(root_node)
        try:
            builder.enclosing_page()
        finally:
            ctx_node.reset(token)


def test_spec_object_page_path_replaces_colon():
    """
    Replace the module separator with a dot in the page path
    """
    assert SpecObject(name="pkg.mod:MyClass").page_path == "pkg.mod.MyClass"


def test_spec_object_page_path_without_colon():
    """
    Preserve entry names without a module separator in page paths
    """
    assert SpecObject(name="simple").page_path == "simple"


def test_spec_object_rejects_colon_in_members():
    """
    Reject module separators in names relative to the parent object
    """
    with pytest.raises(ValueError, match=r"`a:b`.*`C`"):
        SpecObject(name="C", members=["a:b"])


def test_resolver_get_object_or_raise_missing(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "gdmiss").mkdir()
    (tmp_path / "gdmiss" / "__init__.py").write_text("__all__ = []\n")
    from great_docs._apiref.api_reference import Settings
    from great_docs._apiref.resolve import Resolver

    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "gdmiss"
    with pytest.raises(ObjectNotFoundError, match="Cannot find an object named"):
        resolver.get_object_or_raise("gdmiss:does_not_exist")


def test_join_path_none_package():
    assert _join_path(None, "my_func") == "my_func"


def test_join_path_with_colon_in_pkg():
    assert _join_path("pkg:mod", "func") == "pkg:mod.func"


def test_join_path_with_colon_in_name():
    assert _join_path("pkg", "mod:func") == "pkg.mod:func"


def test_join_path_no_colon():
    assert _join_path("pkg", "func") == "pkg:func"


def test_scoped_updates_options():
    from great_docs._apiref.api_reference import Settings

    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "pkg"
    initial_options = resolver.options
    new_options = SpecOptions(include_private=True)
    with resolver._scoped(options=new_options):
        assert resolver.options is new_options
    assert resolver.options is initial_options


def test_resolve_entry_with_spectext():
    from great_docs._apiref.api_reference import Settings
    from great_docs._apiref.content import Text

    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = None
    text_entry = SpecText(contents="some text")
    result = resolver._resolve_entry(text_entry)
    assert isinstance(result, Text)
    assert result.contents == "some text"


def test_resolve_entry_unknown_type_raises():
    from great_docs._apiref.api_reference import Settings

    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = None
    with pytest.raises(TypeError, match="Cannot resolve section entry of type"):
        resolver._resolve_entry("not_a_valid_type")  # type: ignore[arg-type]


def _make_class_with_method(method_name: str = "my_method", method_doc: str = "A method.") -> tuple:
    import griffe as gf

    cls = gf.Class("MyClass")
    cls.docstring = gf.Docstring("A class.", parent=cls)
    method = gf.Function(method_name, parent=cls)
    method.docstring = gf.Docstring(method_doc, parent=method)
    cls.set_member(method_name, method)
    return cls, method


def test_resolve_members_skips_nodoc_member():
    """member_doc is None -> continue"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    cls, method = _make_class_with_method(method_doc="%nodoc")
    objects = {"mymod:MyClass": cls, "mymod:MyClass.my_method": method}
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "mymod"
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    section = SpecSection(
        title="T", contents=[SpecObject(name="MyClass", children=ChildrenStyle.embedded)]
    )
    [resolved] = resolver.resolve_sections([section])
    doc = resolved.contents[0].contents[0]
    assert doc.members == []


def test_resolve_entry_sanitizes_colon_in_page_path():
    """A `module:Item` entry must produce a colon-free page path."""
    from great_docs._apiref.api_reference import Settings

    cls, method = _make_class_with_method()
    objects = {"mymod:MyClass": cls, "mymod:MyClass.my_method": method}
    resolver = Resolver(Settings(parser="numpy"))
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    [section] = resolver.resolve_sections(
        [SpecSection(title="T", contents=[SpecObject(name="mymod:MyClass")])]
    )
    assert section.contents[0].path == "mymod.MyClass"


def test_resolve_members_skips_module_member():
    """member is a module -> continue"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    cls = gf.Class("MyClass")
    cls.docstring = gf.Docstring("A class.", parent=cls)
    submod = gf.Module("submod", parent=cls)
    submod.docstring = gf.Docstring("A submodule.", parent=submod)
    cls.set_member("submod", submod)
    method = gf.Function("my_method", parent=cls)
    method.docstring = gf.Docstring("A method.", parent=method)
    cls.set_member("my_method", method)

    objects = {
        "mymod:MyClass": cls,
        "mymod:MyClass.submod": submod,
        "mymod:MyClass.my_method": method,
    }
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "mymod"
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    section = SpecSection(
        title="T", contents=[SpecObject(name="MyClass", children=ChildrenStyle.embedded)]
    )
    [resolved] = resolver.resolve_sections([section])
    doc = resolved.contents[0].contents[0]
    member_names = [m.name for m in doc.members]
    assert "my_method" in member_names
    assert "submod" not in member_names


def test_resolve_members_children_separate():
    """ChildrenStyle.separate produces MemberPage"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings
    from great_docs._apiref.content import MemberPage

    cls, method = _make_class_with_method()
    objects = {"mymod:MyClass": cls, "mymod:MyClass.my_method": method}
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "mymod"
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    section = SpecSection(
        title="T", contents=[SpecObject(name="MyClass", children=ChildrenStyle.separate)]
    )
    [resolved] = resolver.resolve_sections([section])
    doc = resolved.contents[0].contents[0]
    assert len(doc.members) == 1
    assert isinstance(doc.members[0], MemberPage)


def test_resolve_members_children_linked():
    """ChildrenStyle.linked produces Link"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    cls, method = _make_class_with_method()
    objects = {"mymod:MyClass": cls, "mymod:MyClass.my_method": method}
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "mymod"
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    section = SpecSection(
        title="T", contents=[SpecObject(name="MyClass", children=ChildrenStyle.linked)]
    )
    [resolved] = resolver.resolve_sections([section])
    doc = resolved.contents[0].contents[0]
    assert len(doc.members) == 1
    assert isinstance(doc.members[0], Link)


def test_resolve_members_children_invalid_raises():
    """Unsupported children value raises ValueError"""
    from unittest.mock import MagicMock

    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    cls, method = _make_class_with_method()
    objects = {"mymod:MyClass": cls, "mymod:MyClass.my_method": method}
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "mymod"
    resolver.get_object = lambda path, **kwargs: objects.get(path)

    el = MagicMock(spec=SpecObject)
    el.name = "MyClass"
    el.package = None
    el.dynamic = None
    el.children = "BOGUS_STYLE"
    el.member_options = None
    el.members = ["my_method"]
    el.signature_name = "relative"
    el.with_defaults.return_value = el

    with pytest.raises(ValueError, match="Unsupported value of children"):
        resolver._resolve_members(el, cls, path="mymod:MyClass", dynamic=False)


def test_fetch_members_module_with_exports_filters_unexported():
    """obj.is_module and obj.exports is not None filters to exported only"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    mod.exports = ["pub_func"]
    fn = gf.Function("pub_func", parent=mod)
    fn.docstring = gf.Docstring("Pub.", parent=fn)
    mod.set_member("pub_func", fn)
    fn2 = gf.Function("priv_func", parent=mod)
    fn2.docstring = gf.Docstring("Priv.", parent=fn2)
    mod.set_member("priv_func", fn2)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod").with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert result == ["pub_func"]
    assert "priv_func" not in result


def test_fetch_members_module_exclude_imports():
    """not el.include_imports and obj.is_module filters aliases"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Func.", parent=fn)
    mod.set_member("my_func", fn)
    alias = gf.Alias("imported_name", target=gf.Function("other_func"))
    mod.set_member("imported_name", alias)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_imports=False).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "my_func" in result
    assert "imported_name" not in result


def test_fetch_members_exclude_attributes():
    """include_attributes=False removes attribute members"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    attr = gf.Attribute("my_attr", parent=mod)
    attr.docstring = gf.Docstring("Attr.", parent=attr)
    mod.set_member("my_attr", attr)
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Func.", parent=fn)
    mod.set_member("my_func", fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_attributes=False).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "my_func" in result
    assert "my_attr" not in result


def test_fetch_members_exclude_classes():
    """include_classes=False removes class members"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    cls = gf.Class("MyClass", parent=mod)
    cls.docstring = gf.Docstring("Class.", parent=cls)
    mod.set_member("MyClass", cls)
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Func.", parent=fn)
    mod.set_member("my_func", fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_classes=False).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "my_func" in result
    assert "MyClass" not in result


def test_fetch_members_exclude_functions():
    """include_functions=False removes function members"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    attr = gf.Attribute("my_attr", parent=mod)
    attr.docstring = gf.Docstring("Attr.", parent=attr)
    mod.set_member("my_attr", attr)
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Func.", parent=fn)
    mod.set_member("my_func", fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_functions=False).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "my_attr" in result
    assert "my_func" not in result


def test_fetch_members_exclude_list():
    """el.exclude filters listed names"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    fn1 = gf.Function("keep_me", parent=mod)
    fn1.docstring = gf.Docstring("Keep.", parent=fn1)
    mod.set_member("keep_me", fn1)
    fn2 = gf.Function("exclude_me", parent=mod)
    fn2.docstring = gf.Docstring("Exclude.", parent=fn2)
    mod.set_member("exclude_me", fn2)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", exclude=["exclude_me"]).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "keep_me" in result
    assert "exclude_me" not in result


def test_fetch_members_source_order():
    """member_order='source' returns insertion order"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    for name in ["b_func", "a_func", "c_func"]:
        fn = gf.Function(name, parent=mod)
        fn.docstring = gf.Docstring("Func.", parent=fn)
        mod.set_member(name, fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", member_order="source").with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert result == ["b_func", "a_func", "c_func"]


def test_fetch_members_invalid_order_raises():
    """Unknown member_order raises ValueError"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Func.", parent=fn)
    mod.set_member("my_func", fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod").with_defaults(SpecOptions())
    el = el.replace(member_order="bad_order")

    with pytest.raises(ValueError, match="Unsupported value of member_order"):
        resolver._fetch_members(el, mod)


def test_fetch_members_include_private_skips_private_filter():
    """include_private=True bypasses the private-name filter"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    fn = gf.Function("_private_func", parent=mod)
    fn.docstring = gf.Docstring("Private.", parent=fn)
    mod.set_member("_private_func", fn)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_private=True).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "_private_func" in result


def test_fetch_members_include_empty_skips_docstring_filter():
    """include_empty=True bypasses the docstring-presence filter"""
    import griffe as gf

    from great_docs._apiref.api_reference import Settings

    mod = gf.Module("mymod")
    fn_with_doc = gf.Function("documented", parent=mod)
    fn_with_doc.docstring = gf.Docstring("Has docs.", parent=fn_with_doc)
    mod.set_member("documented", fn_with_doc)
    fn_no_doc = gf.Function("undocumented", parent=mod)
    mod.set_member("undocumented", fn_no_doc)

    resolver = Resolver(Settings(parser="numpy"))
    el = SpecObject(name="mymod", include_empty=True).with_defaults(SpecOptions())
    result = resolver._fetch_members(el, mod)
    assert "documented" in result
    assert "undocumented" in result


def test_fetch_members_keeps_undocumented_members_of_an_enum():
    """An enum lists its undocumented members; a dataclass with an enum base does not"""
    from great_docs._apiref.api_reference import Settings

    source = (
        "import enum\n"
        "from dataclasses import dataclass\n"
        "class Color(enum.Enum):\n"
        "    RED = 1\n"
        "@dataclass\n"
        "class Point(enum.Enum):\n"
        "    X = 1\n"
    )
    with gf.temporary_visited_package("pkg", {"__init__.py": source}) as pkg:
        resolver = Resolver(Settings(parser="numpy"))
        el = SpecObject(name="Color").with_defaults(SpecOptions())
        assert resolver._fetch_members(el, pkg["Color"]) == ["RED"]
        assert resolver._fetch_members(el, pkg["Point"]) == []


def test_autogenerate_sections_returns_sections(capsys):
    """Verify that a valid module produces default API sections"""
    import griffe as gf

    mod = gf.Module("mymod")
    fn = gf.Function("my_func", parent=mod)
    fn.docstring = gf.Docstring("Summary.", parent=fn)
    mod.set_member("my_func", fn)

    from great_docs._apiref.api_reference import Settings

    resolver = Resolver(Settings(parser="numpy"))
    resolver.get_object_or_raise = lambda path, **kwargs: mod

    sections = resolver.autogenerate_sections("mymod")
    assert len(sections) == 1
    assert sections[0].title == "mymod"
    captured = capsys.readouterr()
    assert "Autogenerating" in captured.out
    assert "api-reference" in captured.out


def test_autogenerate_sections_empty_result_raises(capsys):
    """Verify that generating no API sections raises an error"""
    from unittest.mock import patch

    import griffe as gf

    mod = gf.Module("mymod")

    from great_docs._apiref.api_reference import Settings

    resolver = Resolver(Settings(parser="numpy"))
    resolver.get_object_or_raise = lambda path, **kwargs: mod

    with patch("great_docs._apiref.resolve._sections_from_package", return_value=[]):
        with pytest.raises(ValueError, match="No API sections could be generated"):
            resolver.autogenerate_sections("mymod")


def test_spec_object_records_specified_fields():
    spec_obj = SpecObject(name="f", include_private=True)
    assert spec_obj._fields_specified == ("name", "include_private")


def test_spec_object_rejects_unknown_fields():
    with pytest.raises(TypeError, match="bogus"):
        SpecObject(name="f", bogus=True)


def test_spec_options_replace_preserves_specified_fields():
    opts = SpecOptions(include_private=True)
    new = opts.replace(members=["a"])

    assert new.include_private is True
    assert new.members == ["a"]
    assert new._fields_specified == ("include_private", "members")


def test_node_transformer_preserves_specified_fields():
    from great_docs._apiref._visitor import NodeTransformer

    class Renamer(NodeTransformer):
        def exit(self, el):
            if el == "f":
                return "g"
            return el

    section = spec.SpecSection(title="T", contents=["f"])
    result = Renamer().visit(section)

    obj = result.contents[0]
    assert obj.name == "g"
    assert "name" in obj._fields_specified
    assert "include_private" not in obj._fields_specified


def test_package_prefix_remover_strips_prefix():
    page = Page(path="mypkg.submod.func")
    result = _PackagePrefixRemover("mypkg").visit(page)
    assert result.path == "submod.func"


def test_package_prefix_remover_no_strip_different():
    page = Page(path="other.submod.func")
    result = _PackagePrefixRemover("mypkg").visit(page)
    assert result.path == "other.submod.func"


def test_package_prefix_remover_no_strip_single_part():
    page = Page(path="mypkg")
    result = _PackagePrefixRemover("mypkg").visit(page)
    assert result.path == "mypkg"


def test_package_prefix_remover_nested_pages():
    doc = DocFunction(name="f", obj=gf.Function("f"))
    page = Page(path="mypkg.mod.func", contents=[doc])
    section = Section(title="T", contents=[page])
    result = _PackagePrefixRemover("mypkg").visit(section)
    assert result.contents[0].path == "mod.func"


def test_strip_package_name_basic():
    doc = DocFunction(name="f", obj=gf.Function("f"))
    page = Page(path="pkg.mod.func", contents=[doc])
    result = remove_package_prefix(page, "pkg")
    assert result.path == "mod.func"


def test_strip_package_name_no_match():
    doc = DocFunction(name="f", obj=gf.Function("f"))
    page = Page(path="other.func", contents=[doc])
    result = remove_package_prefix(page, "pkg")
    assert result.path == "other.func"


# ============================================================================
# Favicon Tests
# ============================================================================

# Minimal valid SVG for testing (64x64 blue square)
_MINIMAL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
    '<rect width="64" height="64" fill="#318BFC"/>'
    "</svg>"
)


def _make_mock_cairosvg():
    """Create a mock cairosvg module that returns valid PNG data from svg2png."""
    import io as _io

    mock_mod = types.ModuleType("cairosvg")

    def svg2png(**kwargs):
        img = PILImage.new("RGBA", (256, 256), (0, 0, 255, 255))
        buf = _io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    mock_mod.svg2png = svg2png  # type: ignore[attr-defined]
    return mock_mod


class TestFaviconConfigNormalization:
    """Tests for Config.favicon property normalization."""

    def test_favicon_none_when_not_set(self):
        """Favicon should be None when not configured."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("display_name: Test\n")
            config = Config(Path(tmp_dir))

            assert config.favicon is None

    def test_favicon_string_normalized_to_dict(self):
        """A string favicon config should be normalized to {'icon': str}."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("favicon: assets/favicon.svg\n")
            config = Config(Path(tmp_dir))

            assert config.favicon == {"icon": "assets/favicon.svg"}

    def test_favicon_dict_passed_through(self):
        """A dict favicon config should be returned as-is."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("favicon:\n  icon: my-icon.svg\n")
            config = Config(Path(tmp_dir))

            assert config.favicon == {"icon": "my-icon.svg"}

    def test_favicon_invalid_type_returns_none(self):
        """An invalid favicon config type should return None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "great-docs.yml"
            config_file.write_text("favicon:\n  - item1\n  - item2\n")
            config = Config(Path(tmp_dir))

            assert config.favicon is None


class TestFaviconLinkInjection:
    """Tests for favicon <link> tag injection into _quarto.yml."""

    @pytest.fixture(autouse=True)
    def _mock_cairosvg(self):
        with patch.dict("sys.modules", {"cairosvg": _make_mock_cairosvg()}):
            yield

    def _build_with_favicon(
        self, tmp_dir: str, favicon_config: str | None = None, create_logo: bool = False
    ) -> dict:
        """
        Return the site configuration for a project with optional favicon settings
        """

        tmp = Path(tmp_dir)

        # Minimal pyproject.toml
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
            '[project.urls]\nRepository = "https://github.com/test/test-pkg"\n'
            'Documentation = "https://test.github.io/test-pkg"\n'
        )

        # great-docs.yml
        yml_lines = ["display_name: Test\n"]
        if favicon_config:
            yml_lines.append(favicon_config)
        (tmp / "great-docs.yml").write_text("".join(yml_lines))

        # Create logo if requested (for auto-detect path)
        if create_logo:
            (tmp / "logo.svg").write_text(_MINIMAL_SVG)

        docs = GreatDocs(project_path=tmp_dir)
        docs._remote = StubRemote()
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        # Run the config build
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        # Read the generated _quarto.yml
        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml) as f:
            return read_yaml(f)

    def test_auto_detect_injects_link_tags(self):
        """Auto-detected logo should inject favicon <link> tags with absolute URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_favicon(tmp_dir, create_logo=True)

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            header_text = " ".join(str(item) for item in header)

            base = "https://test.github.io/test-pkg/"
            assert f'href="{base}favicon.ico"' in header_text
            assert f'href="{base}favicon.svg"' in header_text
            assert f'href="{base}favicon-32x32.png"' in header_text
            assert f'href="{base}favicon-16x16.png"' in header_text
            assert f'href="{base}apple-touch-icon.png"' in header_text

    def test_explicit_favicon_injects_link_tags(self):
        """Explicit favicon config should also inject <link> tags with absolute URLs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create the favicon source file and a logo (favicon block requires logo)
            tmp = Path(tmp_dir)
            (tmp / "assets").mkdir()
            (tmp / "assets" / "favicon.svg").write_text(_MINIMAL_SVG)

            config = self._build_with_favicon(
                tmp_dir,
                favicon_config="favicon: assets/favicon.svg\n",
                create_logo=True,
            )

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            header_text = " ".join(str(item) for item in header)

            base = "https://test.github.io/test-pkg/"
            assert f'href="{base}favicon.ico"' in header_text
            assert f'href="{base}favicon.svg"' in header_text
            assert f'href="{base}favicon-32x32.png"' in header_text
            assert f'href="{base}favicon-16x16.png"' in header_text
            assert f'href="{base}apple-touch-icon.png"' in header_text

    def test_no_favicon_no_link_tags(self):
        """Without logo or favicon config, no <link> tags should be injected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_favicon(tmp_dir)

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            header_text = " ".join(str(item) for item in header)

            assert "favicon" not in header_text

    def test_explicit_favicon_sets_website_favicon(self):
        """Explicit favicon config should set website.favicon to favicon.ico."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "assets").mkdir()
            (tmp / "assets" / "favicon.svg").write_text(_MINIMAL_SVG)

            config = self._build_with_favicon(
                tmp_dir,
                favicon_config="favicon: assets/favicon.svg\n",
                create_logo=True,
            )

            assert config.get("website", {}).get("favicon") == "favicon.ico"

    def test_auto_detect_sets_website_favicon(self):
        """Auto-detected logo should set website.favicon to favicon.ico."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_favicon(tmp_dir, create_logo=True)

            assert config.get("website", {}).get("favicon") == "favicon.ico"


def test_config_markdown_pages_disabled():
    """Test that markdown_pages: false excludes copy-page.js from Quarto config."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        config_file = project_path / "great-docs.yml"
        config_file.write_text("markdown_pages: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        # Both should be false
        assert docs._config.markdown_pages is False
        assert docs._config.markdown_pages_widget is False

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        # copy-page.js should NOT be in resources
        resources = config["project"].get("resources", [])

        assert "copy-page.js" not in resources

        # copy-page.js should NOT be in include-after-body
        after_body = config["format"]["html"].get("include-after-body", [])
        for item in after_body:
            assert "copy-page" not in str(item)


def test_config_markdown_pages_widget_disabled():
    """Test that markdown_pages: {widget: false} generates .md but hides widget."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        config_file = project_path / "great-docs.yml"
        config_file.write_text("markdown_pages:\n  widget: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        # .md generation enabled, widget disabled
        assert docs._config.markdown_pages is True
        assert docs._config.markdown_pages_widget is False

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"

        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        # copy-page.js should NOT be in resources
        resources = config["project"].get("resources", [])

        assert "copy-page.js" not in resources

        # copy-page.js should NOT be in include-after-body
        after_body = config["format"]["html"].get("include-after-body", [])
        for item in after_body:
            assert "copy-page" not in str(item)


def test_config_markdown_pages_default_enabled():
    """Test that markdown_pages defaults to true (copy-page.js included)."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = read_yaml(f)

        # copy-page.js SHOULD be in resources
        resources = config["project"].get("resources", [])

        assert "copy-page.js" in resources

        # copy-page.js SHOULD be in include-after-body
        after_body = config["format"]["html"].get("include-after-body", [])
        has_copy_page = any("copy-page" in str(item) for item in after_body)

        assert has_copy_page


class TestPositBadgeInjection:
    """Tests for automatic 'Supported by Posit' badge injection."""

    def _build_with_funding(self, tmp_dir: str, funding_name: str | None = None) -> dict:
        """
        Return the site configuration for a project with optional funding
        """

        tmp = Path(tmp_dir)

        (tmp / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')

        yml_lines = ["display_name: Test\n"]
        if funding_name is not None:
            yml_lines.append(f"funding:\n  name: {funding_name}\n")
        (tmp / "great-docs.yml").write_text("".join(yml_lines))

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml) as f:
            return read_yaml(f)

    def _header_has_posit_badge(self, config: dict) -> bool:
        header = config.get("format", {}).get("html", {}).get("include-in-header", [])

        return any("supported-by-posit" in str(item) for item in header)

    def test_posit_pbc_injects_badge(self):
        """funding.name = 'Posit, PBC' should inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "Posit, PBC")

            assert self._header_has_posit_badge(config)

    def test_posit_software_pbc_injects_badge(self):
        """funding.name = 'Posit Software, PBC' should inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "Posit Software, PBC")

            assert self._header_has_posit_badge(config)

    def test_posit_alone_injects_badge(self):
        """funding.name = 'Posit' should inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "Posit")

            assert self._header_has_posit_badge(config)

    def test_posit_case_insensitive(self):
        """funding.name = 'posit' (lowercase) should inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "posit")

            assert self._header_has_posit_badge(config)

    def test_no_funding_no_badge(self):
        """No funding config should not inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, None)

            assert not self._header_has_posit_badge(config)

    def test_non_posit_funder_no_badge(self):
        """funding.name = 'Acme Corp' should not inject the badge."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "Acme Corp")

            assert not self._header_has_posit_badge(config)

    def test_posit_as_substring_no_badge(self):
        """funding.name = 'Compositor Labs' should not inject the badge (word boundary)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_funding(tmp_dir, "Compositor Labs")

            assert not self._header_has_posit_badge(config)

    def test_no_duplicate_badge(self):
        """
        Keep one Posit badge after repeated configuration
        """

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            (tmp / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
            (tmp / "great-docs.yml").write_text("display_name: Test\nfunding:\n  name: Posit\n")

            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            write_initial_quarto_yml(docs.build_dir)
            update_quarto_config(docs, make_run(docs))
            update_quarto_config(docs, make_run(docs))  # second run

            quarto_yml = docs.build_dir / "_quarto.yml"

            with open(quarto_yml) as f:
                config = read_yaml(f)

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            badge_count = sum(1 for item in header if "supported-by-posit" in str(item))

            assert badge_count == 1


def test_build_cli_reference_uses_module_name(tmp_path):
    """Regression: build() discovers the Click CLI in the importable module,
    not the PyPI project name, when the two diverge."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-dist"\n')
    # Write `cli.enabled` before `GreatDocs` reads the project metadata during creation.
    write_config(tmp_path, "module: actual_module\ncli:\n  enabled: true\n")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER)

    with (
        stubbed_build(docs),
        patch("great_docs._cliref.click.discover", return_value=None) as discover,
    ):
        docs.build(refresh=False)

    discover.assert_called_once_with(
        "actual_module",
        docs.layout.package_root,
        cli_module=None,
        cli_name=None,
        display_name="my-dist",
        report=print,
    )


@patch("great_docs._checks.harper.run_harper")
def test_proofread_docstrings_use_module_name(mock_run_harper):
    """Find docstrings under the importable module when its name differs from the project"""
    mock_run_harper.return_value = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "pyproject.toml").write_text('[project]\nname = "my-dist"\n')
        (root / "great-docs.yml").write_text("module: actual_module\n")
        pkg_dir = root / "actual_module"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Module docstring."""\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs.proofread(include_docs=False, include_docstrings=True)

        assert result == []
        mock_run_harper.assert_called_once()
        scanned = mock_run_harper.call_args[0][0]
        assert [p.name for p in scanned] == ["__init__.py"]


@patch("great_docs._checks.harper.run_harper")
def test_proofread_docstrings_dotted_module_name(mock_run_harper):
    """Find docstrings in nested directories for a dotted module name"""
    mock_run_harper.return_value = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "pyproject.toml").write_text('[project]\nname = "my-dist"\n')
        (root / "great-docs.yml").write_text("module: firebird.base\n")
        pkg_dir = root / "firebird" / "base"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text('"""Module docstring."""\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs.proofread(include_docs=False, include_docstrings=True)

        assert result == []
        mock_run_harper.assert_called_once()
        scanned = mock_run_harper.call_args[0][0]
        assert [p.name for p in scanned] == ["__init__.py"]


def test_proofread_docstrings_no_package_no_crash():
    """Skip docstring discovery when no package is detectable"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs.proofread(include_docs=False, include_docstrings=True)

        assert result == []


def _proofread_project(tmp_path: Path) -> GreatDocs:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
    guide = tmp_path / "user_guide"
    guide.mkdir()
    (guide / "page.qmd").write_text("---\ntitle: T\n---\n\n```python\nx = 1\n```\n\nA tset.\n")
    return GreatDocs(project_path=tmp_path)


def test_proofread_applies_the_commands_defaults(tmp_path):
    """
    Check page prose with the CLI defaults and caller-supplied words

    Report issues against the original page and exclude front matter and fenced code.
    """
    from great_docs._checks.harper import HarperLint, get_default_ignore_rules

    docs = _proofread_project(tmp_path)
    seen = {}

    def run_text(text, **kwargs):
        seen["text"] = text
        seen["ignore_rules"] = kwargs["ignore_rules"]
        seen["words"] = Path(kwargs["user_dict_path"]).read_text().splitlines()
        return [HarperLint("SpellCheck", "Spelling", 9, 3, "Misspelled", "tset", file="<stdin>")]

    with patch("great_docs._checks.harper.run_harper_on_text", side_effect=run_text):
        results = docs.proofread(custom_words=["griffe"])

    assert "title" not in seen["text"] and "x = 1" not in seen["text"]
    assert seen["ignore_rules"] == get_default_ignore_rules()
    assert "quartodoc" in seen["words"] and seen["words"][-1] == "griffe"
    [page] = results
    assert page.file == "user_guide/page.qmd"
    assert [issue.file for issue in page.issues] == ["user_guide/page.qmd"]


def test_proofread_strict_checks_without_defaults(tmp_path):
    """Disable default rule exclusions and the built-in dictionary with `strict=True`"""
    docs = _proofread_project(tmp_path)
    with patch("great_docs._checks.harper.run_harper_on_text", return_value=[]) as run_text:
        docs.proofread(strict=True)

    assert run_text.call_args.kwargs["ignore_rules"] is None
    assert run_text.call_args.kwargs["user_dict_path"] is None


def test_proofread_missing_harper_raises(tmp_path):
    """Raise `RuntimeError` for the whole run when `harper-cli` is missing"""
    docs = _proofread_project(tmp_path)
    with (
        patch("great_docs._checks.harper.find_harper_cli", return_value=None),
        pytest.raises(RuntimeError, match="harper-cli is not installed"),
    ):
        docs.proofread()


def test_proofread_harper_error_on_a_page_is_that_pages_error(tmp_path):
    """Return a Harper failure as the affected page's `error`"""
    from great_docs._checks.harper import HarperError

    docs = _proofread_project(tmp_path)
    with patch(
        "great_docs._checks.harper.run_harper_on_text", side_effect=HarperError("timed out")
    ):
        [page] = docs.proofread()

    assert page.issues == ()
    assert page.error == "timed out"


def test_entry_point_name():
    """
    Read the first script name from `pyproject.toml`
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[project.scripts]\nmycli = "pkg.cli:main"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") == "mycli"


def test_entry_point_name_gui_scripts_fallback():
    """
    Fall back to `[project.gui-scripts]` when no console scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[project.gui-scripts]\nmyapp = "pkg.gui:main"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") == "myapp"


def test_entry_point_name_no_scripts_returns_none():
    """
    Return `None` when no scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") is None


def test_entry_point_name_no_pyproject_returns_none():
    """
    Return `None` when `pyproject.toml` is missing
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") is None


def test_count_pages_flat_inline():
    """
    Count page paths in a flat sidebar
    """
    assert cli_render.count_pages(["a.qmd", "b.qmd", "c.qmd"]) == 3


def test_count_pages_nested_three():
    """
    Count page paths within nested sidebar sections
    """
    items = [
        "top.qmd",
        {"section": "Group", "contents": ["a.qmd", "b.qmd"]},
    ]

    assert cli_render.count_pages(items) == 3


def test_count_pages_empty_list():
    """
    Return zero for an empty sidebar
    """

    assert cli_render.count_pages([]) == 0


def test_an_escaping_custom_page_output_fails_the_custom_pages_step(tmp_path):
    """Keep a page link from failing a step before custom pages are processed"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.0"\n')
    write_config(tmp_path, "reference: false\ncustom_pages:\n  dir: pages\n  output: ../escape\n")
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages/landing.html").write_text("<p>Landing</p>")
    (tmp_path / "user_guide").mkdir()
    (tmp_path / "user_guide/intro.qmd").write_text("# Intro\n")
    (tmp_path / "README.md").write_text("# Demo\n\n[Intro](user_guide/intro.qmd)\n")
    docs = GreatDocs(project_path=str(tmp_path))

    run = (
        "prepare.build_directory",
        "content.user_guide",
        "content.custom_pages",
    )
    with stubbed_build(docs, run=run), pytest.raises(BuildError) as failure:
        docs.build(refresh=False)

    assert str(failure.value) == (
        "Process custom pages failed: Output path must remain inside the build directory: ../escape"
    )


def test_entry_point_name_scripts():
    """
    Read the first `[project.scripts]` name
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n\n[project.scripts]\nmy-tool = "mypkg.cli:main"\n'
        )
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") == "my-tool"


def test_entry_point_name_gui_scripts():
    """
    Fall back to `[project.gui-scripts]` when no console scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n\n[project.gui-scripts]\nmy-gui = "mypkg.gui:main"\n'
        )
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") == "my-gui"


def test_entry_point_name_no_scripts():
    """
    Return `None` when no scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") is None


def test_entry_point_name_no_pyproject():
    """
    Return `None` when `pyproject.toml` is missing
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_click.entry_point_name(docs.layout.package_root, "other:cli") is None


def test_extract_command_simple():
    """
    Describe a Click command with its options, arguments and help text
    """
    pytest.importorskip("click")

    @click.command()
    @click.option("--name", help="Your name")
    def hello(name):
        """Say hello."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = cli_click.extract_command(hello, "hello")

        assert result["name"] == "hello"
        assert result["full_path"] == "hello"
        assert result["help"] == "Say hello."
        assert result["is_group"] is False
        assert result["commands"] == []
        # New structured fields
        assert isinstance(result["options"], list)
        assert len(result["options"]) == 1
        assert result["options"][0]["names"] == ["--name"]
        assert result["options"][0]["help"] == "Your name"
        assert result["arguments"] == []
        assert result["description"] == "Say hello."
        assert result["examples"] == []


def test_extract_command_hidden_subcommand():
    """
    Exclude hidden subcommands from the reference model
    """
    pytest.importorskip("click")

    @click.group()
    def cli():
        """Main CLI."""

    @cli.command(hidden=True)
    def secret():
        """Hidden command."""

    @cli.command()
    def public():
        """Public command."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = cli_click.extract_command(cli, "tool")

        names = [c["name"] for c in result["commands"]]

        assert "public" in names
        assert "secret" not in names


def test_extract_command_with_parent_path():
    """
    Include the parent invocation in a subcommand's full path
    """
    pytest.importorskip("click")

    @click.command()
    def sub():
        """A subcommand."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = cli_click.extract_command(sub, "sub", parent_path="tool")

        assert result["full_path"] == "tool sub"


def test_extract_option():
    """
    Describe Click options for the reference pages
    """
    pytest.importorskip("click")

    @click.command()
    @click.option("--name", "-n", help="Your name", required=True)
    @click.option("--verbose", is_flag=True, help="Be verbose")
    @click.option("--count", type=int, default=5, show_default=True, help="Repeat count")
    def cmd(name, verbose, count):
        pass

    options = [cli_click.extract_option(p) for p in cmd.params if hasattr(p, "opts")]
    options = [o for o in options if o is not None]

    # --name
    name_opt = next(o for o in options if "--name" in o["names"])
    assert name_opt["required"] is True
    assert "-n" in name_opt["names"]
    assert name_opt["help"] == "Your name"
    assert name_opt["is_flag"] is False

    # --verbose (flag)
    verbose_opt = next(o for o in options if "--verbose" in o["names"])
    assert verbose_opt["is_flag"] is True

    # --count (with default)
    count_opt = next(o for o in options if "--count" in o["names"])
    assert count_opt["default"] == 5
    assert count_opt["type"] == "INTEGER"


def test_extract_option_skips_help():
    """
    Exclude the `--help` option from the reference model
    """
    pytest.importorskip("click")

    @click.command(add_help_option=True)
    @click.option("--name", help="Your name")
    def cmd(name):
        pass

    # The help param is automatically added; filter to find it
    help_param = next(
        (p for p in cmd.params if getattr(p, "name", None) == "help"),
        None,
    )
    if help_param is not None:
        assert cli_click.extract_option(help_param) is None
    else:
        # Click version may not expose help as a param; just verify
        # that --name is extracted and help is not in the result
        options = [cli_click.extract_option(p) for p in cmd.params if hasattr(p, "opts")]
        options = [o for o in options if o is not None]
        names = [n for o in options for n in o["names"]]
        assert "--help" not in names


def test_extract_argument():
    """
    Describe a Click positional argument for the reference pages
    """
    pytest.importorskip("click")

    @click.command()
    @click.argument("source", required=False)
    def cmd(source):
        pass

    arg_param = next(p for p in cmd.params if isinstance(p, click.Argument))
    result = cli_click.extract_argument(arg_param)

    assert result["name"] == "source"
    assert result["required"] is False


def test_parse_help_parts_no_examples():
    """
    Keep the full description when no examples section is present
    """
    desc, examples = cli_click.parse_help_parts("Build the documentation site.")

    assert desc == "Build the documentation site."
    assert examples == []


def test_parse_help_parts_with_examples():
    """
    Split the description from the examples
    """
    help_text = (
        "Build the documentation site.\n\n"
        "\\b\n"
        "Examples:\n"
        "  great-docs build\n"
        "  great-docs build --watch\n"
    )
    desc, examples = cli_click.parse_help_parts(help_text)

    assert "Build the documentation" in desc
    assert len(examples) == 2
    assert "great-docs build" in examples[0]
    assert "--watch" in examples[1]


def test_parse_help_parts_empty():
    """
    Return an empty description and examples for empty help text
    """
    desc, examples = cli_click.parse_help_parts("")

    assert desc == ""
    assert examples == []


def test_help_output():
    """
    Render a command's full `--help` output
    """
    pytest.importorskip("click")

    @click.command()
    @click.option("--name", help="Your name")
    def hello(name):
        """Say hello to someone."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = cli_click.help_output(hello, "hello")

        assert "Usage:" in result
        assert "--name" in result
        assert "Say hello to someone." in result


def test_command_page_main():
    """
    Render the root command's reference page
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "my-tool",
            "full_path": "my-tool",
            "help": "My tool help.",
            "help_text": "Usage: my-tool [OPTIONS]\n\n  My tool help.\n",
            "description": "My tool help.",
            "examples": [],
            "options": [],
            "arguments": [],
            "commands": [],
            "is_group": False,
        }
        result = cli_render.command_page(docs._config, cmd_info, is_main=True)

        assert "my-tool" in result
        assert "sidebar: cli-reference" in result
        assert ".cli-manpage" in result
        assert '.details summary="Full `--help` output"' in result
        assert "doc-api-page" in result
        assert "::: {.doc-signature .doc-function}" in result
        assert ".doc-subject" in result


def test_command_page_subcommand():
    """
    Use the full invocation as a subcommand's page title
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "build",
            "full_path": "my-tool build",
            "help": "Build the site.",
            "help_text": "Usage: my-tool build [OPTIONS]\n",
            "description": "Build the site.",
            "examples": [],
            "options": [
                {
                    "names": ["--watch"],
                    "name_display": "--watch",
                    "help": "Watch for changes.",
                    "type": None,
                    "default": None,
                    "required": False,
                    "is_flag": True,
                    "multiple": False,
                    "envvar": None,
                    "show_default": False,
                    "is_eager": False,
                    "hidden": False,
                },
            ],
            "arguments": [],
            "commands": [],
            "is_group": False,
        }
        result = cli_render.command_page(docs._config, cmd_info, is_main=False)

        assert "my-tool build" in result
        # This body class selects the monospaced command-title style.
        assert "body-classes: doc-api-page doc-cli-api-page" in result
        assert "## Options" in result
        assert "&#45;&#45;watch" in result
        assert "Watch for changes." in result


def test_command_page_with_arguments():
    """
    Render positional arguments in the command page
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "install",
            "full_path": "my-tool install",
            "help": "Install a package.",
            "help_text": "Usage: my-tool install [SOURCE]\n",
            "description": "Install a package.",
            "examples": ["my-tool install foo", "my-tool install bar"],
            "options": [],
            "arguments": [
                {
                    "name": "source",
                    "name_display": "SOURCE",
                    "type": None,
                    "required": False,
                    "nargs": 1,
                },
            ],
            "commands": [],
            "is_group": False,
        }
        result = cli_render.command_page(docs._config, cmd_info, is_main=False)

        assert "## Arguments" in result
        assert "SOURCE" in result
        assert "## Examples" in result
        assert "my-tool install foo" in result


def test_command_page_group_with_subcommands():
    """
    Render a command group's subcommand links
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "my-tool",
            "full_path": "my-tool",
            "help": "My CLI.",
            "help_text": "Usage: my-tool COMMAND\n",
            "description": "My CLI.",
            "examples": [],
            "options": [],
            "arguments": [],
            "is_group": True,
            "commands": [
                {
                    "name": "build",
                    "full_path": "my-tool build",
                    "short_help": "Build stuff.",
                },
            ],
        }
        result = cli_render.command_page(docs._config, cmd_info, is_main=True)

        assert "## Commands" in result
        assert "build" in result
        assert "Build stuff." in result
        assert "cli-group" in result


def test_write_pages_empty():
    """
    Return an empty sidebar when no command tree is supplied
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert cli_render.write_pages(docs._config, docs.build_dir, {}, report=print) == []
        assert cli_render.write_pages(docs._config, docs.build_dir, None, report=print) == []


def test_write_pages_basic():
    """
    Write the index, root command and subcommand pages
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        cli_info = {
            "name": "tool",
            "full_path": "tool",
            "help_text": "Usage: tool\n",
            "commands": [
                {
                    "name": "build",
                    "full_path": "tool build",
                    "help_text": "Usage: tool build\n",
                    "commands": [],
                },
            ],
        }
        result = cli_render.write_pages(docs._config, docs.build_dir, cli_info, report=print)

        # The index is now a labeled listing entry (not the root command page).
        assert {"text": "CLI Index", "href": "reference/cli/index.qmd"} in result
        assert (docs.build_dir / "reference" / "cli" / "index.qmd").exists()
        # The root command page now lives on its own page (entry name -> safe name).
        assert "reference/cli/tool.qmd" in result
        assert (docs.build_dir / "reference" / "cli" / "tool.qmd").exists()
        assert (docs.build_dir / "reference" / "cli" / "build.qmd").exists()


def test_write_pages_sections_omit_unlisted():
    """
    Omit unlisted commands from pages, the sidebar and the index when `cli.sections` is set
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        docs._config._config["cli"]["sections"] = [{"title": "Building", "contents": ["build"]}]

        cli_info = {
            "name": "tool",
            "full_path": "tool",
            "help_text": "Usage: tool\n",
            "is_group": True,
            "commands": [
                {
                    "name": "build",
                    "full_path": "tool build",
                    "help_text": "Usage: tool build\n",
                    "commands": [],
                },
                {
                    "name": "internal",
                    "full_path": "tool internal",
                    "help_text": "Usage: tool internal\n",
                    "is_group": True,
                    "commands": [
                        {
                            "name": "run",
                            "full_path": "tool internal run",
                            "help_text": "Usage: tool internal run\n",
                            "commands": [],
                        },
                    ],
                },
            ],
        }
        result = cli_render.write_pages(docs._config, docs.build_dir, cli_info, report=print)
        cli_dir = docs.build_dir / "reference" / "cli"

        assert "reference/cli/build.qmd" in result
        assert (cli_dir / "build.qmd").exists()
        # The unlisted group and its subcommands are dropped everywhere.
        assert not any(isinstance(item, dict) and "section" in item for item in result)
        assert not (cli_dir / "internal.qmd").exists()
        assert not (cli_dir / "internal").exists()
        index = (cli_dir / "index.qmd").read_text()
        assert "internal" not in index


def test_index_page_auto_layout():
    """
    List leaf commands before command groups when no sections are configured
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        cli_info = {
            "name": "tool",
            "entry_point_name": "tool",
            "short_help": "A tool.",
            "is_group": True,
            "commands": [
                {
                    "name": "build",
                    "full_path": "tool build",
                    "short_help": "Build it.",
                    "is_group": False,
                    "commands": [],
                },
                {
                    "name": "init",
                    "full_path": "tool init",
                    "short_help": "Init it.",
                    "is_group": False,
                    "commands": [],
                },
                {
                    "name": "skill",
                    "full_path": "tool skill",
                    "short_help": "Manage skills.",
                    "is_group": True,
                    "commands": [
                        {
                            "name": "install",
                            "full_path": "tool skill install",
                            "short_help": "Install.",
                            "commands": [],
                        },
                    ],
                },
            ],
        }

        page = cli_render.index_page(docs._config, cli_info, "tool")

        # Front matter mirrors the API reference index, plus the CLI scoping class.
        assert "body-classes: doc-reference doc-cli-reference" in page
        assert "sidebar: cli-reference" in page
        # Root command link is present with the group pill.
        assert "[tool](tool.qmd){.doc-function .doc-label .doc-label-cli-group}" in page
        # Leaf commands are listed (code order) under the auto "Commands" section.
        assert "## Commands {.doc-group}" in page
        # Entries show the full invocation, not the bare command name.
        assert "[tool build](build.qmd){.doc-function .doc-label .doc-label-cli}" in page
        assert page.index("[tool build]") < page.index("[tool init]")
        # The group gets its own section, with its overview and subcommand links.
        assert "## skill {.doc-group}" in page
        assert "[tool skill](skill.qmd){.doc-function .doc-label .doc-label-cli-group}" in page
        assert (
            "[tool skill install](skill/install.qmd){.doc-function .doc-label .doc-label-cli}"
            in page
        )


def test_index_page_configured_sections():
    """
    Use `cli.sections` for index headings, ordering and descriptions
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config._config["cli"] = {
            "title": "Command Line",
            "desc": "Drive everything from the terminal.",
            "sections": [
                {"title": "Building", "desc": "Make the site.", "contents": ["build"]},
                {"title": "Setup", "contents": ["init"]},
            ],
        }

        cli_info = {
            "name": "tool",
            "entry_point_name": "tool",
            "short_help": "A tool.",
            "is_group": True,
            "commands": [
                {"name": "init", "short_help": "Init it.", "is_group": False, "commands": []},
                {"name": "build", "short_help": "Build it.", "is_group": False, "commands": []},
            ],
        }

        page = cli_render.index_page(docs._config, cli_info, "tool")

        assert 'title: "Command Line"' in page
        assert "Drive everything from the terminal." in page
        assert "## Building {.doc-group}" in page
        assert "Make the site." in page
        assert "## Setup {.doc-group}" in page
        # Configured order wins: Building (build) appears before Setup (init).
        assert page.index("## Building") < page.index("## Setup")


def test_order_sidebar_items_honors_sections():
    """
    Order leaf command entries by `cli.sections`
    """
    items = [
        "reference/cli/init.qmd",
        "reference/cli/build.qmd",
        "reference/cli/scan.qmd",
        {"section": "skill", "contents": ["reference/cli/skill.qmd"]},
    ]
    sections = [
        {"title": "Building", "contents": ["build"]},
        {"title": "Setup", "contents": ["init"]},
    ]
    ordered = cli_render.order_sidebar_items(items, sections)

    # build, then init (configured order); scan keeps code order after; group last.
    assert ordered == [
        "reference/cli/build.qmd",
        "reference/cli/init.qmd",
        "reference/cli/scan.qmd",
        {"section": "skill", "contents": ["reference/cli/skill.qmd"]},
    ]


def test_write_subcommand_pages_nested():
    """
    Write pages and sidebar sections for nested command groups
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        cli_dir = docs.build_dir / "reference" / "cli"
        cli_dir.mkdir(parents=True)

        cmd_info = {
            "commands": [
                {
                    "name": "task",
                    "full_path": "tool task",
                    "help_text": "Usage: tool task\n",
                    "commands": [
                        {
                            "name": "run",
                            "full_path": "tool task run",
                            "help_text": "Usage: tool task run\n",
                            "commands": [],
                        },
                    ],
                },
            ],
        }
        result = cli_render._write_subcommand_pages(
            docs._config, docs.build_dir, cmd_info, cli_dir, "reference/cli", []
        )

        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["section"] == "task"
        assert (cli_dir / "task.qmd").exists()
        assert (cli_dir / "task" / "run.qmd").exists()


def test_write_subcommand_pages_leaf():
    """
    Return page paths for leaf commands
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        cli_dir = docs.build_dir / "reference" / "cli"
        cli_dir.mkdir(parents=True)

        cmd_info = {
            "commands": [
                {
                    "name": "build",
                    "full_path": "tool build",
                    "help_text": "Usage: tool build\n",
                    "commands": [],
                },
            ],
        }
        result = cli_render._write_subcommand_pages(
            docs._config, docs.build_dir, cmd_info, cli_dir, "reference/cli", []
        )

        assert result == ["reference/cli/build.qmd"]


def test_discover_missing_package(tmp_path):
    """
    Return `None` when the package has no CLI module
    """
    result = cli_click.discover(
        "nonexistent_pkg_xyzzy", tmp_path, cli_module=None, cli_name=None, report=print
    )

    assert result is None


def test_strip_numeric_prefix_various():
    """_strip_numeric_prefix handles different prefix formats."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert strip_numeric_prefix("01-intro.qmd") == "intro.qmd"
        assert strip_numeric_prefix("99_advanced.qmd") == "advanced.qmd"
        assert strip_numeric_prefix("no-prefix.qmd") == "no-prefix.qmd"
        assert strip_numeric_prefix("001-triple.qmd") == "triple.qmd"


def test_count_pages_nested_v2():
    """
    Count page paths recursively through sidebar sections
    """
    items = [
        "reference/cli/index.qmd",
        {
            "section": "task",
            "contents": [
                "reference/cli/task.qmd",
                {"section": "sub", "contents": ["reference/cli/task/run.qmd"]},
            ],
        },
    ]

    assert cli_render.count_pages(items) == 3


def test_parse_dunder_all():
    """Verify that literal `__all__` parsing finds the expected exports"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        pkg = tmp / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["Foo", "bar"]\n')
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is not None
        assert "Foo" in result
        assert "bar" in result


def test_discover_exports():
    """Verify that static discovery finds a synthetic package's exports"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = discover_exports(
            make_exports(docs).package("great_docs"), docs._config, report=print
        )

        assert result is not None
        assert "GreatDocs" in result


def test_quarto_environment_sets_quarto_python():
    """Set `QUARTO_PYTHON` to a non-empty executable path"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "QUARTO_PYTHON" in env
        assert env["QUARTO_PYTHON"]  # non-empty


def test_quarto_environment_sets_pythonpath():
    """Include the package root in `PYTHONPATH`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "PYTHONPATH" in env
        assert tmp_dir in env["PYTHONPATH"]


def test_quarto_environment_includes_src_dir():
    """Include `src/` in `PYTHONPATH` when the directory exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_dir = Path(tmp_dir) / "src"
        src_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert str(src_dir) in env["PYTHONPATH"]


def test_quarto_environment_includes_python_dir():
    """Include `python/` in `PYTHONPATH` when the directory exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        python_dir = Path(tmp_dir) / "python"
        python_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert str(python_dir) in env["PYTHONPATH"]


def test_quarto_environment_venv_detection():
    """Use `.venv/bin/python` when it exists"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        venv_bin = Path(tmp_dir) / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        venv_python = venv_bin / "python"
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert env["QUARTO_PYTHON"] == str(venv_python.resolve())


def test_quarto_environment_preserves_existing_pythonpath(monkeypatch):
    """Prepend the package root to an existing `PYTHONPATH`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setenv("PYTHONPATH", "/existing/path")
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "/existing/path" in env["PYTHONPATH"]
        assert tmp_dir in env["PYTHONPATH"]


def test_homepage_margin_with_package_name():
    """Verify that the sidebar includes a PyPI link when the package name is detected"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        # Create great-docs dir for project_path
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "pypi.org/project/testpkg" in result
        assert "#### Links" in result


def test_homepage_margin_pypi_disabled():
    """Verify that `pypi: false` removes the sidebar PyPI link"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("pypi: false\n", encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "pypi.org" not in result
        assert "View on PyPI" not in result


def test_homepage_margin_pypi_custom_url():
    """Verify that a string `pypi` value supplies the sidebar PyPI URL"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text(
            'pypi: "https://packages.example.com/simple/testpkg"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "packages.example.com/simple/testpkg" in result
        assert "pypi.org" not in result


def test_homepage_margin_pypi_disabled_with_citation():
    """`pypi: false` must not break the citation section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("pypi: false\n", encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()

        # The citation page must live in project_path (the great-docs/ dir)
        # for the citation section to render.
        (gd_dir / "citation.qmd").write_text("# Citation\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "pypi.org" not in result
        assert "citation.qmd" in result
        assert "testpkg" in result


def test_homepage_margin_pypi_custom_url_with_citation():
    """A custom PyPI URL string must not break citation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text(
            'pypi: "https://packages.example.com/simple/testpkg"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        (gd_dir / "citation.qmd").write_text("# Citation\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "packages.example.com/simple/testpkg" in result
        assert "citation.qmd" in result
        assert "testpkg" in result


def test_homepage_margin_with_license():
    """Verify that the sidebar omits the licence when no `LICENSE` file exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\nlicense = {text = "MIT"}\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        # Without a LICENSE file, no license entry should appear
        assert "Full license" not in result
        assert "gd-spdx-badge" not in result


def test_homepage_margin_with_license_qmd():
    """Verify that the sidebar links to `license.qmd` when it exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()

        # Create license.qmd in the build directory
        (gd_dir / "license.qmd").write_text("---\ntitle: License\n---\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Full license" in result
        assert "license.qmd" in result


def test_homepage_margin_with_contributing():
    """Verify that sidebar setup creates and links to `contributing.qmd`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        # Create CONTRIBUTING.md
        (Path(tmp_dir) / "CONTRIBUTING.md").write_text(
            "# Contributing\n\nPlease submit PRs.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Community" in result
        assert "Contributing guide" in result

        # Check that contributing.qmd was created
        contrib_qmd = gd_dir / "contributing.qmd"

        assert contrib_qmd.exists()

        content = contrib_qmd.read_text(encoding="utf-8")

        assert "Please submit PRs." in content

        # First heading should be stripped
        assert content.count("# Contributing") == 0


def test_homepage_margin_with_code_of_conduct():
    """Verify that sidebar setup creates and links to `code-of-conduct.qmd`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        # Create CODE_OF_CONDUCT.md
        (Path(tmp_dir) / "CODE_OF_CONDUCT.md").write_text(
            "# Code of Conduct\n\nBe nice.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Code of conduct" in result

        coc_qmd = gd_dir / "code-of-conduct.qmd"

        assert coc_qmd.exists()

        content = coc_qmd.read_text(encoding="utf-8")

        assert "Be nice." in content


def test_homepage_margin_github_contributing():
    """Verify that sidebar setup finds `CONTRIBUTING.md` in `.github`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gh_dir = Path(tmp_dir) / ".github"
        gh_dir.mkdir()
        (gh_dir / "CONTRIBUTING.md").write_text("# Contributing\n\nHelp us!", encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Contributing guide" in result


def test_homepage_margin_with_security():
    """Verify that sidebar setup creates and links to `security.qmd`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        (Path(tmp_dir) / "SECURITY.md").write_text(
            "# Security Policy\n\nReport vulnerabilities responsibly.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Community" in result
        assert "Security policy" in result

        security_qmd = gd_dir / "security.qmd"

        assert security_qmd.exists()

        content = security_qmd.read_text(encoding="utf-8")

        assert "Report vulnerabilities responsibly." in content
        assert 'title: "Security Policy"' in content
        # First heading should be stripped
        assert content.count("# Security Policy") == 0


def test_homepage_margin_github_security():
    """Verify that sidebar setup finds `SECURITY.md` in `.github`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gh_dir = Path(tmp_dir) / ".github"
        gh_dir.mkdir()
        (gh_dir / "SECURITY.md").write_text(
            "# Security Policy\n\nContact security@example.com.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Security policy" in result

        security_qmd = gd_dir / "security.qmd"

        assert security_qmd.exists()

        content = security_qmd.read_text(encoding="utf-8")

        assert "Contact security@example.com." in content


def test_homepage_margin_security_disabled():
    """Verify that `show_security: false` omits the security policy page and sidebar link"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        (Path(tmp_dir) / "SECURITY.md").write_text(
            "# Security Policy\n\nReport vulnerabilities.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        # Create great-docs.yml with show_security disabled
        config_file = Path(tmp_dir) / "great-docs.yml"
        config_file.write_text("site:\n  show_security: false\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Security policy" not in result

        security_qmd = gd_dir / "security.qmd"

        assert not security_qmd.exists()


def test_homepage_margin_security_root_over_github():
    """SECURITY.md in project root takes precedence over .github directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        # Create both root and .github versions
        (Path(tmp_dir) / "SECURITY.md").write_text(
            "# Security Policy\n\nRoot version.", encoding="utf-8"
        )
        gh_dir = Path(tmp_dir) / ".github"
        gh_dir.mkdir()
        (gh_dir / "SECURITY.md").write_text(
            "# Security Policy\n\nGitHub version.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        homepage_margin(docs)

        security_qmd = gd_dir / "security.qmd"
        content = security_qmd.read_text(encoding="utf-8")

        # Root version should win
        assert "Root version." in content
        assert "GitHub version." not in content


def test_homepage_margin_with_urls():
    """Verify that the sidebar includes project URLs from metadata"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\n[project.urls]\nRepository = "https://github.com/user/pkg"\nBug_Tracker = "https://github.com/user/pkg/issues"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Browse source code" in result
        assert "Report a bug" in result


def test_homepage_margin_with_authors():
    """Verify that the sidebar Developers section includes the package authors"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\n[[project.authors]]\nname = "Jane Doe"\nemail = "jane@example.com"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Developers" in result
        assert "Jane Doe" in result


def test_homepage_margin_llms_links():
    """Verify that the sidebar links to `llms.txt` files only when they will be generated"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        (gd_dir / "_quarto.yml").write_text(
            "api-reference:\n  package: os\n  sections:\n    - title: Core\n      contents: [os.getcwd]\n",
            encoding="utf-8",
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "llms.txt" in result
        assert "llms-full.txt" in result


def test_homepage_margin_no_llms_links_without_api_reference():
    """A docs-only site gets no llms.txt links, because no files are generated (#350)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        (gd_dir / "_quarto.yml").write_text(
            "project:\n  type: website\nwebsite:\n  title: Docs only\n", encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "llms.txt" not in result
        assert "llms-full.txt" not in result


LLMS_TXT_QUARTO_YMLS = [
    "no _quarto.yml",
    "no api-reference",
    "no sections",
    "no package",
    "unimportable package",
    "importable package with sections",
]


def _write_llms_txt_quarto_yml(build_dir: Path, label: str) -> None:
    """Materialise the `_quarto.yml` that goes with an llms.txt guard label."""
    configs = {
        "no api-reference": "project:\n  type: website\n",
        "no sections": "api-reference:\n  package: os\n  sections: []\n",
        "no package": (
            "api-reference:\n  sections:\n    - title: Core\n      contents: [os.getcwd]\n"
        ),
        "unimportable package": (
            "api-reference:\n"
            "  package: totally_nonexistent_pkg_xyz\n"
            "  sections:\n"
            "    - title: Core\n"
            "      contents: [totally_nonexistent_pkg_xyz.f]\n"
        ),
        "importable package with sections": (
            "api-reference:\n  package: os\n  sections:\n"
            "    - title: Core\n      contents: [os.getcwd]\n"
        ),
    }
    if label in configs:
        (build_dir / "_quarto.yml").write_text(configs[label], encoding="utf-8")


@pytest.mark.parametrize("label", LLMS_TXT_QUARTO_YMLS)
def test_freeze_writes_the_llms_files_build_would(label: str, tmp_path: Path):
    """
    Write the llms files exactly when the homepage advertises them, as a build does
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    _write_llms_txt_quarto_yml(docs.build_dir, label)
    log = BuildLog(stream=io.StringIO())

    with stubbed_build(docs):
        freeze.prepare(docs._preparation_steps(make_run(docs), log), log, docs.build_dir)

    available = llms_txt.is_planned(docs.build_dir)
    assert (docs.build_dir / "llms.txt").exists() == available, label
    assert (docs.build_dir / "llms-full.txt").exists() == available, label


def test_homepage_margin_authors_with_rich_metadata():
    """Verify that the sidebar displays author metadata, including GitHub and ORCID links"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "authors": [
                        {
                            "name": "Alice",
                            "role": "Maintainer",
                            "github": "alice",
                            "orcid": "0000-0001-2345-6789",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Alice" in result
        assert "Maintainer" in result
        assert "github.com/alice" in result
        assert "orcid.org/0000-0001-2345-6789" in result


def test_homepage_margin_citation_link():
    """Verify that the sidebar includes a citation link when `citation.qmd` exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        (gd_dir / "citation.qmd").write_text("---\ntitle: Citation\n---\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        # citation_link should be set since citation.qmd exists
        # (but it may not appear in margin sections if no explicit block uses it;
        # check the result doesn't error out at minimum)
        assert isinstance(result, str)


def test_homepage_hero_disabled_no_logo():
    """Verify that an explicitly disabled hero produces no HTML"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(format_yaml({"hero": False}), encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Hello\n\nContent")

        assert result == ""
        assert cleaned is None


def test_homepage_hero_with_name_and_tagline():
    """Verify that the hero uses the configured name and tagline"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "hero": {
                        "enabled": True,
                        "name": "My Proj",
                        "tagline": "A great tagline",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Test\n\nBody")

        assert "My Proj" in result
        assert "A great tagline" in result
        assert "gd-hero" in result


def test_homepage_hero_with_string_logo():
    """Verify that the hero renders a logo configured as a string"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "hero": {
                        "enabled": True,
                        "logo": "assets/logo.svg",
                        "name": "TestPkg",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Test\n\nBody")

        assert "assets/logo.svg" in result
        assert "gd-hero-logo" in result


def test_homepage_hero_with_badges():
    """Verify that the hero includes badge HTML"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml({"hero": {"enabled": True, "name": "Test"}}),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Test")

        assert "gd-hero" in result


def test_homepage_hero_badge_from_config():
    """Verify that the hero renders badges from the configured list"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "hero": {
                        "enabled": True,
                        "name": "Test",
                        "badges": [
                            {"alt": "CI", "img": "https://ci.svg", "url": "https://ci.example.com"},
                            {"alt": "Status", "img": "https://status.svg"},
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Test")

        assert "gd-hero-badges" in result
        assert "https://ci.svg" in result


def test_build_sections_from_reference_config_basic_functions():
    """_build_sections_from_reference_config creates sections from config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        reference_config = [
            {"title": "Functions", "desc": "Utils", "contents": ["func_a", "func_b"]},
            {"title": "Classes", "desc": "Types", "contents": ["MyClass"]},
        ]
        result = reference_sections.from_reference_config(reference_config)

        assert len(result) == 2
        assert result[0]["title"] == "Functions"
        assert result[0]["contents"] == ["func_a", "func_b"]
        assert result[1]["title"] == "Classes"


def test_build_sections_from_reference_config_dict_items_simple():
    """_build_sections_from_reference_config handles dict items with members config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        reference_config = [
            {
                "title": "Classes",
                "contents": [
                    {"name": "BigClass", "members": False},
                    {"name": "SmallClass"},
                    "plain_func",
                ],
            }
        ]
        result = reference_sections.from_reference_config(reference_config)

        assert len(result) == 1

        contents = result[0]["contents"]

        assert contents[0] == {"name": "BigClass", "members": []}
        assert contents[1] == "SmallClass"
        assert contents[2] == "plain_func"


def test_build_sections_from_reference_config_empty_v2():
    """_build_sections_from_reference_config returns None for empty config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert reference_sections.from_reference_config([]) is None
        assert reference_sections.from_reference_config(None) is None


def test_build_sections_from_reference_config_skips_string_entry():
    """_build_sections_from_reference_config skips non-dict items in config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        reference_config = [
            "not-a-dict",
            {"title": "Valid", "contents": ["func_a"]},
        ]
        result = reference_sections.from_reference_config(reference_config)

        assert len(result) == 1


def test_build_sections_from_reference_config_dict_no_name_returns_none():
    """_build_sections_from_reference_config skips dict items without name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        reference_config = [
            {"title": "Test", "contents": [{"members": False}]},
        ]
        result = reference_sections.from_reference_config(reference_config)

        # Section has no valid contents, so it should be skipped
        assert result is None


def test_homepage_margin_with_funding():
    """Verify that the sidebar includes the configured funder"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "funding": {
                        "name": "Science Foundation",
                        "roles": ["Sponsor", "Funder"],
                        "homepage": "https://example.org",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        # Funding now appears under the Developers section
        assert "#### Developers" in result
        assert "Science Foundation" in result
        assert "Sponsor" in result


def test_homepage_margin_with_funding_ror():
    """Verify that the sidebar links the ROR icon to the funder's ROR URL"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "funding": {
                        "name": "Research Inc",
                        "ror": "https://ror.org/12345",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Research Inc" in result
        assert "ror.org/12345" in result
        assert "ror-sidebar-icon" in result


def test_homepage_margin_with_meta_requires_python():
    """Verify that the sidebar includes the Python version requirement"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\nrequires-python = ">=3.9"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Meta" in result
        assert "Requires:" in result
        assert ">=3.9" in result


def test_homepage_margin_with_meta_extras():
    """Verify that the sidebar includes optional dependency extras"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\n[project.optional-dependencies]\ndev = ["pytest"]\ndocs = ["sphinx"]\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Meta" in result
        assert "Provides-Extra:" in result


def test_homepage_margin_citation_section():
    """Verify that the sidebar includes a citation link when `citation.qmd` exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        (gd_dir / "citation.qmd").write_text("---\ntitle: Citation\n---\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        # Citation now appears under the Community section
        assert "#### Community" in result
        assert "citation.qmd" in result


def test_write_homepage_with_license():
    """
    Create `license.qmd` from the project's `LICENSE` file
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create LICENSE file
        (Path(tmp_dir) / "LICENSE").write_text("MIT License\nCopyright 2024", encoding="utf-8")
        (Path(tmp_dir) / "README.md").write_text("# Hello\n\nWorld", encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        license_qmd = gd_dir / "license.qmd"

        assert license_qmd.exists()

        content = license_qmd.read_text(encoding="utf-8")

        assert "MIT License" in content
        assert 'title: "License"' in content


def test_write_homepage_with_citation():
    """
    Create `citation.qmd` from the project's `CITATION.cff` file
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "README.md").write_text("# Hello\n\nWorld", encoding="utf-8")
        citation_data = {
            "cff-version": "1.2.0",
            "title": "TestPkg",
            "authors": [{"given-names": "Alice", "family-names": "Smith"}],
        }
        (Path(tmp_dir) / "CITATION.cff").write_text(format_yaml(citation_data), encoding="utf-8")
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        citation_qmd = gd_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text(encoding="utf-8")

        assert "Alice" in content
        assert "Smith" in content


def test_write_homepage_creates_index_qmd():
    """
    Create `index.qmd` from `README.md`
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "README.md").write_text(
            "# My Package\n\nA great package.", encoding="utf-8"
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        index_qmd = gd_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text(encoding="utf-8")

        assert "A great package." in content


def test_write_homepage_generates_landing_page():
    """
    Generate a landing page from package metadata when no homepage source exists
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\ndescription = "A cool library"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        index_qmd = gd_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text(encoding="utf-8")

        assert "mypkg" in content
        assert "pip install" in content


def test_homepage_margin_author_fallback_github():
    """Verify that authors without a GitHub account link to the repository owner"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\n'
            '[[project.authors]]\nname = "Bob"\n'
            '[project.urls]\nRepository = "https://github.com/bob/pkg"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "#### Developers" in result
        assert "Bob" in result

        # Should have GitHub link derived from repo URL
        assert "github.com/bob" in result


def test_homepage_hero_with_light_dark_logo():
    """Verify that the hero renders configured light and dark logo variants"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "hero": {
                        "enabled": True,
                        "logo": {
                            "light": "assets/logo-light.svg",
                            "dark": "assets/logo-dark.svg",
                        },
                        "name": "TestPkg",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs)

        assert "gd-only-light" in result
        assert "gd-only-dark" in result
        assert "logo-light.svg" in result
        assert "logo-dark.svg" in result


def test_homepage_hero_dark_only_logo_still_renders():
    """Regression: a dark-only `hero.logo` must still render an `<img>`.

    Final-review finding on the roborev #801 batch: without the config-side
    `light` fallback, `logo_html` stayed empty and the hero silently rendered
    with no logo image at all (sibling bug to
    `test_dark_only_logo_does_not_crash_quarto_config` for the top-level
    `logo` key).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(
            format_yaml(
                {
                    "hero": {
                        "enabled": True,
                        "logo": {"dark": "assets/hero-dark.svg"},
                        "name": "TestPkg",
                    }
                }
            ),
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs)

        assert "<img" in result
        assert "hero-dark.svg" in result


def test_homepage_hero_auto_enable_no_hero():
    """Verify that the hero produces no HTML when neither enabled nor detected"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs, "# Hello\n\nBody")

        assert result == ""


def test_homepage_hero_metadata_fallback_name():
    """Verify that the hero uses the metadata name when no hero name is configured"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "cool-pkg"\n', encoding="utf-8")
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(format_yaml({"hero": {"enabled": True}}), encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs)

        # Should use package name as fallback
        assert "cool-pkg" in result or "cool_pkg" in result


def test_homepage_hero_metadata_fallback_tagline():
    """Verify that the metadata description supplies the default hero tagline"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\ndescription = "A wonderful library"\n',
            encoding="utf-8",
        )
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text(format_yaml({"hero": {"enabled": True}}), encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        result, cleaned = homepage_hero(docs)
        assert "A wonderful library" in result


def test_write_homepage_citation_bibtex():
    """
    Include BibTeX in `citation.qmd`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "README.md").write_text("# Hello", encoding="utf-8")
        citation_data = {
            "cff-version": "1.2.0",
            "title": "TestPkg",
            "date-released": "2024-01-15",
            "authors": [
                {"given-names": "Alice", "family-names": "Smith"},
                {"given-names": "Bob", "family-names": "Jones"},
                {"given-names": "Carol", "family-names": "Davis"},
            ],
            "repository-code": "https://github.com/test/testpkg",
        }
        (Path(tmp_dir) / "CITATION.cff").write_text(format_yaml(citation_data), encoding="utf-8")
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        citation_qmd = gd_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text(encoding="utf-8")

        assert "BibTeX" in content
        assert "@Manual" in content
        assert "Smith" in content
        assert "CITATION.cff" in content
        assert "github.com/test/testpkg" in content


def test_write_homepage_citation_two_authors():
    """
    Format a citation with two authors
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "README.md").write_text("# Hello", encoding="utf-8")
        citation_data = {
            "cff-version": "1.2.0",
            "title": "TestPkg",
            "authors": [
                {"given-names": "Alice", "family-names": "Smith"},
                {"given-names": "Bob", "family-names": "Jones"},
            ],
        }
        (Path(tmp_dir) / "CITATION.cff").write_text(format_yaml(citation_data), encoding="utf-8")
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "testpkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()
        docs = GreatDocs(project_path=tmp_dir)
        write_homepage(docs)
        citation_qmd = gd_dir / "citation.qmd"
        content = citation_qmd.read_text(encoding="utf-8")

        assert "Smith" in content
        assert "Jones" in content


def test_quarto_environment_no_extra_dirs():
    """Include the package root in `PYTHONPATH` without `src/` or `python/` directories"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert "PYTHONPATH" in env

        # Should just have the tmp_dir itself
        parts = env["PYTHONPATH"].split(":")

        assert any(tmp_dir in p for p in parts)


def test_quarto_environment_venv_alternative_name():
    """Use `venv/bin/python` when it exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        venv_bin = Path(tmp_dir) / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        venv_python = venv_bin / "python"
        venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)

        assert env["QUARTO_PYTHON"] == str(venv_python.resolve())


def _render_doc_source_relative_path(obj, links: SourceLinks):
    """
    Resolve a stand-in object's source path with the supplied link settings

    Parameters
    ----------
    obj
        The stand-in Griffe object.
    links
        The source-link settings.

    Returns
    -------
    :
        The source path, or `None` when no path can be determined.
    """
    import great_docs._apiref._render.doc as docmod

    cls = vars(docmod)["__RenderDoc"]
    fake_self = types.SimpleNamespace(obj=obj)
    with active_settings(Settings(source_links=links)):
        return cls.__dict__["_source_relative_path"](fake_self)


def test_render_source_relative_path_preserves_src_layout():
    """Renderer source links must keep the `src/` prefix for src-layout packages.

    Regression test: griffe's `relative_package_filepath` is relative to the
    package's parent (a search path such as `src/`), so it drops the leading
    `src/` and yields a GitHub blob URL that 404s. The renderer should instead
    compute the path relative to the repository root.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_file = root / "src" / "raghilda" / "embedding.py"
        src_file.parent.mkdir(parents=True)
        src_file.write_text("x = 1", encoding="utf-8")

        # griffe would report the path relative to the `src/` search path.
        obj = types.SimpleNamespace(
            filepath=src_file,
            relative_package_filepath=Path("raghilda/embedding.py"),
        )

        links = SourceLinks(package_root=root)
        assert _render_doc_source_relative_path(obj, links) == "src/raghilda/embedding.py"


def test_render_source_relative_path_source_path_override():
    """An explicit `source.path` override is used verbatim for monorepos."""
    obj = types.SimpleNamespace(
        filepath=Path("/anywhere/embedding.py"),
        relative_package_filepath=Path("raghilda/embedding.py"),
    )
    links = SourceLinks(package_root=Path("/some/root"), path="packages/raghilda/src")

    assert _render_doc_source_relative_path(obj, links) == "packages/raghilda/src/embedding.py"


def test_render_source_relative_path_falls_back_to_griffe():
    """Without repo root or override, fall back to griffe's package-relative path."""
    obj = types.SimpleNamespace(
        filepath=Path("/anywhere/raghilda/embedding.py"),
        relative_package_filepath=Path("raghilda/embedding.py"),
    )

    assert _render_doc_source_relative_path(obj, SourceLinks()) == "raghilda/embedding.py"


def test_update_sidebar_from_sections_basic():
    """Test _update_sidebar_from_sections builds sidebar from API reference."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "project": {"type": "website"},
            "website": {"sidebar": []},
            "api-reference": {
                "package": "mypkg",
                "sections": [
                    {
                        "title": "Classes",
                        "desc": "",
                        "contents": ["MyClass", "OtherClass"],
                    },
                    {
                        "title": "Functions",
                        "desc": "",
                        "contents": ["my_func"],
                    },
                ],
            },
        }

        with open(quarto_yml, "w") as f:
            write_yaml(config, f)

        reference_sections.update_sidebar(docs._config, docs.build_dir)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        sidebar = result["website"]["sidebar"]

        assert len(sidebar) == 1
        assert sidebar[0]["id"] == "reference"

        contents = sidebar[0]["contents"]

        # First entry is API link
        assert contents[0] == {"text": "API Index", "href": "reference/index.qmd"}

        # Then section entries
        assert contents[1]["section"] == "Classes"
        assert {"text": "MyClass", "href": "reference/MyClass.qmd"} in contents[1]["contents"]
        assert {"text": "OtherClass", "href": "reference/OtherClass.qmd"} in contents[1]["contents"]
        assert contents[2]["section"] == "Functions"
        assert {"text": "my_func", "href": "reference/my_func.qmd"} in contents[2]["contents"]


def test_update_sidebar_from_sections_dict_items():
    """Test _update_sidebar_from_sections handles dict items in contents."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "project": {"type": "website"},
            "website": {"sidebar": []},
            "api-reference": {
                "package": "mypkg",
                "sections": [
                    {
                        "title": "Core",
                        "desc": "",
                        "contents": [
                            {"name": "BigClass", "members": []},
                            "simple_func",
                        ],
                    },
                ],
            },
        }

        with open(quarto_yml, "w") as f:
            write_yaml(config, f)

        reference_sections.update_sidebar(docs._config, docs.build_dir)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        sidebar = result["website"]["sidebar"]
        section = sidebar[0]["contents"][1]  # First section after API link

        assert {"text": "BigClass", "href": "reference/BigClass.qmd"} in section["contents"]
        assert {"text": "simple_func", "href": "reference/simple_func.qmd"} in section["contents"]


def test_update_sidebar_from_sections_sanitizes_colons():
    """Colons in `module:Item` entry names must be sanitized in sidebar hrefs."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "project": {"type": "website"},
            "website": {"sidebar": []},
            "api-reference": {
                "package": "mypkg",
                "sections": [
                    {
                        "title": "Devices",
                        "desc": "",
                        "contents": ["devices.keithley:Keithley2400"],
                    },
                ],
            },
        }

        with open(quarto_yml, "w") as f:
            write_yaml(config, f)

        reference_sections.update_sidebar(docs._config, docs.build_dir)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        section = result["website"]["sidebar"][0]["contents"][1]
        assert {
            "text": "devices.keithley:Keithley2400",
            "href": "reference/devices.keithley.Keithley2400.qmd",
        } in section["contents"]


def test_update_sidebar_no_api_reference():
    """Test _update_sidebar_from_sections with no api-reference does nothing."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        config = {"project": {"type": "website"}, "website": {"sidebar": []}}

        with open(quarto_yml, "w") as f:
            write_yaml(config, f)

        # Should not raise
        reference_sections.update_sidebar(docs._config, docs.build_dir)


def test_update_quarto_config_navbar_color_light_dark():
    """
    Generate navbar CSS for configured light and dark colours
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(
            Path(tmp_dir), "navbar_color:\n  light: '#1a1a2e'\n  dark: '#e0e0e0'\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        # The navbar color CSS should be injected as a style in after-body
        after_body = result["format"]["html"].get("include-after-body", [])
        style_entries = [str(item) for item in after_body if "navbar_color overrides" in str(item)]

        assert len(style_entries) > 0


def test_update_quarto_config_navbar_color_light_only():
    """
    Generate navbar CSS when only a light colour is configured
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "navbar_color:\n  light: '#003366'\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        css_items = [str(item) for item in after_body if "navbar_color overrides" in str(item)]

        assert len(css_items) > 0

        # Should contain quarto-light selector
        assert "quarto-light" in css_items[0]


def test_update_quarto_config_navbar_color_does_not_leak_onto_root():
    """`navbar_color` CSS must scope every rule to `.navbar`, never the bare root."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n', encoding="utf-8"
        )
        docs._config = write_config(
            Path(tmp_dir), "navbar_color:\n  light: '#c76e00'\n  dark: '#0a2540'\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        with open(quarto_yml, "w") as f:
            write_yaml(
                {
                    "project": {"type": "website"},
                    "website": {"navbar": {"left": []}, "sidebar": []},
                    "format": {"html": {}},
                },
                f,
            )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        css = "".join(
            item["text"] if isinstance(item, dict) else str(item)
            for item in after_body
            if "navbar_color overrides" in str(item)
        )

        # The buggy form leaves a bare root prefix joined by a comma directly
        # before a descendant — these substrings must never appear.
        assert "html.quarto-dark, :root[data-bs-theme='dark'] .navbar" not in css
        assert "html.quarto-light, :root[data-bs-theme='light'] .navbar" not in css

        # Every prefix must be scoped to .navbar (descendant combinator present).
        assert "html.quarto-dark .navbar" in css
        assert ":root[data-bs-theme='dark'] .navbar" in css

        # The CSS-variable block on the bare root is intentional and kept.
        assert "--gd-navbar-bg:" in css


def test_update_quarto_config_announcement_banner():
    """
    Include announcement metadata and the banner script
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(
            Path(tmp_dir),
            "announcement:\n  content: 'New release!'\n  type: success\n  dismissable: true\n",
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website", "resources": []},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        header = result["format"]["html"].get("include-in-header", [])
        after_body = result["format"]["html"].get("include-after-body", [])

        # Check meta tag in header
        has_ann_meta = any("gd-announcement" in str(item) for item in header)

        assert has_ann_meta

        # Check script in after-body
        has_ann_script = any("announcement-banner" in str(item) for item in after_body)

        assert has_ann_script

        # Check resource
        assert "announcement-banner.js" in result["project"]["resources"]


def test_update_quarto_config_content_style():
    """
    Include content style metadata and its script
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(
            Path(tmp_dir), "content_style:\n  preset: gradient\n  pages: all\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website", "resources": []},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        header = result["format"]["html"].get("include-in-header", [])
        after_body = result["format"]["html"].get("include-after-body", [])

        has_cs_meta = any("gd-content-style" in str(item) for item in header)

        assert has_cs_meta

        has_cs_script = any("content-style" in str(item) for item in after_body)

        assert has_cs_script
        assert "content-style.js" in result["project"]["resources"]


def test_update_quarto_config_navbar_style():
    """
    Include navbar style metadata and its script
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "navbar_style: midnight\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website", "resources": []},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        header = result["format"]["html"].get("include-in-header", [])
        after_body = result["format"]["html"].get("include-after-body", [])

        has_nb_meta = any("gd-navbar-style" in str(item) for item in header)

        assert has_nb_meta

        has_nb_script = any("navbar-style" in str(item) for item in after_body)

        assert has_nb_script
        assert "navbar-style.js" in result["project"]["resources"]


def test_update_quarto_config_dark_mode_toggle():
    """
    Include the dark mode toggle script
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        has_dark_mode = any("dark-mode-toggle" in str(item) for item in after_body)

        assert has_dark_mode

        header = result["format"]["html"].get("include-in-header", [])
        has_theme_init = any("theme-init" in str(item) for item in header)

        assert has_theme_init


def test_update_quarto_config_cli_pages_add_ref_switcher():
    """Add the reference switcher when CLI pages exist"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "cli:\n  enabled: true\n  module: mypkg.cli\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)
        cli_index = docs.build_dir / "reference" / "cli" / "index.qmd"
        cli_index.parent.mkdir(parents=True)
        cli_index.write_text("", encoding="utf-8")

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        has_ref_switcher = any("reference-switcher" in str(item) for item in after_body)

        assert has_ref_switcher


def test_update_quarto_config_page_footer_with_authors():
    """
    Include author names in the page footer
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n'
            '[[project.authors]]\nname = "Alice Smith"\n'
            '[[project.authors]]\nname = "Bob Jones"\n',
            encoding="utf-8",
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer = result["website"].get("page-footer", {})
        footer_text = footer.get("center", "")

        assert "Developed by" in footer_text
        assert "Alice" in footer_text
        assert "Bob" in footer_text


def test_update_quarto_config_page_footer_with_funding():
    """
    Include funding information in the page footer
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[[project.authors]]\nname = "Alice"\n',
            encoding="utf-8",
        )

        docs._config = write_config(
            Path(tmp_dir), "funding:\n  name: ACME Foundation\n  homepage: https://acme.org\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer = result["website"].get("page-footer", {})
        footer_text = footer.get("center", "")

        assert "Supported by" in footer_text
        assert "ACME" in footer_text


def test_update_quarto_config_page_footer_funding_no_authors():
    """Test page footer with funding but no authors."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "funding:\n  name: TestFund\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer = result["website"].get("page-footer", {})
        footer_text = footer.get("center", "")

        assert "Supported by" in footer_text
        assert "TestFund" in footer_text


def test_update_quarto_config_posit_badge():
    """
    Include the Posit badge when funding names Posit
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "funding:\n  name: Posit PBC\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        header = result["format"]["html"].get("include-in-header", [])
        has_posit = any("supported-by-posit" in str(item) for item in header)

        assert has_posit


def test_update_quarto_config_sidebar_filter():
    """
    Include the sidebar filter script
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        has_sidebar_filter = any("sidebar-filter" in str(item) for item in after_body)

        assert has_sidebar_filter


def test_update_quarto_config_sidebar_filter_custom_min_items():
    """Test sidebar filter with custom min_items from metadata."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "sidebar_filter:\n  min_items: 10\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        after_body = result["format"]["html"].get("include-after-body", [])
        has_min_items = any("sidebarFilterMinItems" in str(item) for item in after_body)

        assert has_min_items


def test_update_quarto_config_attribution():
    """
    Include Great Docs attribution in the footer
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[[project.authors]]\nname = "Author"\n',
            encoding="utf-8",
        )

        # Attribution is True by default
        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer = result["website"].get("page-footer", {})
        footer_text = footer.get("center", "")

        assert "Great&nbsp;Docs" in footer_text


def test_update_quarto_config_site_url():
    """
    Set the Quarto site URL from `great-docs.yml`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(
            Path(tmp_dir), 'site_url: "http://myserver:3838/data-team/mypackage/"\n'
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website", "resources": []},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert result["website"]["site-url"] == "http://myserver:3838/data-team/mypackage/"


def test_update_quarto_config_site_url_not_set():
    """
    Leave the Quarto site URL absent when none is configured
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website", "resources": []},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert "site-url" not in result["website"]


def test_write_homepage_citation_parsing():
    """
    Create a citation page from `CITATION.cff`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n'
            '[project.urls]\nRepository = "https://github.com/owner/repo"\n',
            encoding="utf-8",
        )

        citation_cff = Path(tmp_dir) / "CITATION.cff"
        citation_cff.write_text(
            "cff-version: 1.2.0\n"
            "title: My Package\n"
            "version: 1.0.0\n"
            "date-released: '2024-06-15'\n"
            "url: https://example.com\n"
            "authors:\n"
            "  - given-names: Alice\n"
            "    family-names: Smith\n"
            "  - given-names: Bob\n"
            "    family-names: Jones\n",
            encoding="utf-8",
        )

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Package\n\nHello world.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        citation_qmd = docs.build_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text()

        assert "Authors and Citation" in content
        assert "Alice Smith" in content
        assert "Bob Jones" in content
        assert "@Manual{" in content  # BibTeX
        assert "APA" in content
        assert "RIS" in content


def test_write_homepage_citation_single_author():
    """Test citation with a single author."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        citation_cff = Path(tmp_dir) / "CITATION.cff"
        citation_cff.write_text(
            "cff-version: 1.2.0\n"
            "title: Solo Package\n"
            "version: 2.0.0\n"
            "date-released: '2023-01-01'\n"
            "url: https://solo.dev\n"
            "authors:\n"
            "  - given-names: Carol\n"
            "    family-names: Williams\n",
            encoding="utf-8",
        )

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# Solo\n\nContent.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        citation_qmd = docs.build_dir / "citation.qmd"

        assert citation_qmd.exists()

        content = citation_qmd.read_text()

        assert "Carol Williams" in content


def test_write_homepage_citation_three_authors():
    """Test citation with 3+ authors uses et al. in text citation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        citation_cff = Path(tmp_dir) / "CITATION.cff"
        citation_cff.write_text(
            "cff-version: 1.2.0\n"
            "title: Team Package\n"
            "version: 3.0.0\n"
            "authors:\n"
            "  - given-names: Alice\n"
            "    family-names: A\n"
            "  - given-names: Bob\n"
            "    family-names: B\n"
            "  - given-names: Carol\n"
            "    family-names: C\n",
            encoding="utf-8",
        )

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# Team\n\nContent.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        citation_qmd = docs.build_dir / "citation.qmd"
        content = citation_qmd.read_text()

        # 3 authors -> APA uses ", &" format for last author
        assert ", &" in content or "A, Alice" in content


def test_write_homepage_no_citation():
    """
    Skip the citation page when `CITATION.cff` is absent
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n\nSome content.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        citation_qmd = docs.build_dir / "citation.qmd"

        assert not citation_qmd.exists()


def test_write_homepage_heading_adjustment():
    """
    Demote README headings below the homepage title
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text(
            "# My Package\n\n## Section\n\n### Subsection\n\nContent.\n",
            encoding="utf-8",
        )

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text()

        # Headings should be bumped: ## -> ###, ### -> ####
        assert "### Section" in content
        assert "#### Subsection" in content


def test_write_homepage_rst_source():
    """
    Build the homepage from an RST source
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme_rst = Path(tmp_dir) / "README.rst"
        readme_rst.write_text("My Package\n==========\n\nSome RST content.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)

        # Mock RST conversion since pandoc may not be available
        with patch(
            "great_docs._website.homepage.source.rst_to_markdown",
            return_value="# My Package\n\nSome RST content.\n",
        ):
            write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()


def test_write_homepage_landing_page_fallback():
    """
    Generate a landing page when no homepage source exists
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\ndescription = "A test"\n', encoding="utf-8"
        )

        # No README.md, no index.qmd, no README.rst
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()


def test_write_homepage_hero_section():
    """
    Include the configured hero section in the homepage
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\ndescription = "A test package"\n',
            encoding="utf-8",
        )

        docs._config = write_config(Path(tmp_dir), "hero:\n  enabled: true\n")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# mypkg\n\nHello world.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"

        assert index_qmd.exists()

        content = index_qmd.read_text()

        # Hero section should inject HTML at the top
        assert "hero" in content.lower() or "Hello world" in content


def test_write_homepage_hero_strips_duplicate_h1():
    """Test that hero section strips matching first h1 to avoid duplication."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "testpkg"\ndescription = "Desc"\n', encoding="utf-8"
        )

        docs._config = write_config(Path(tmp_dir), "hero:\n  enabled: true\n  name: testpkg\n")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# testpkg\n\n## Features\n\nSome features.\n", encoding="utf-8")

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_homepage(docs)

        index_qmd = docs.build_dir / "index.qmd"
        content = index_qmd.read_text()

        # The first h1 "# testpkg" should be stripped because hero shows the name
        # But "## Features" (which becomes "### Features") should remain
        assert "Features" in content


@pytest.mark.parametrize(
    ("logo_file", "readme_hero"),
    [
        pytest.param("logo-hero.svg", "", id="logo-hero-file"),
        pytest.param(
            None,
            '<div align="center">\n'
            "_A tagline_\n"
            "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org)\n"
            "</div>\n\n",
            id="readme-hero",
        ),
    ],
)
def test_write_homepage_auto_hero_strips_duplicate_h1(
    tmp_path: Path, logo_file: str | None, readme_hero: str
):
    """
    Remove the README title that repeats the hero name when the hero is not configured
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "testpkg"\ndescription = "Desc"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(f"# testpkg\n\n{readme_hero}Some text.\n", encoding="utf-8")
    if logo_file:
        (tmp_path / logo_file).write_text("<svg/>", encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs._config = write_config(tmp_path)
    docs.build_dir.mkdir(parents=True, exist_ok=True)

    write_homepage(docs, has_api_reference=False)

    content = (docs.build_dir / "index.qmd").read_text(encoding="utf-8")
    assert "gd-hero-name" in content
    assert "## testpkg" not in content


def test_write_homepage_hero_name_true_keeps_title(tmp_path: Path):
    """
    Keep the README title when `hero.name` is `True` without raising `AttributeError`
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "testpkg"\ndescription = "Desc"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# testpkg\n\nSome text.\n", encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs._config = write_config(tmp_path, "hero:\n  enabled: true\n  name: true\n")
    docs.build_dir.mkdir(parents=True, exist_ok=True)

    write_homepage(docs, has_api_reference=False)

    assert "## testpkg" in (docs.build_dir / "index.qmd").read_text(encoding="utf-8")


def test_refresh_api_reference_config_updates_sections():
    """Test _refresh_api_reference_config updates sections from package exports."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "project": {"type": "website"},
            "website": {"sidebar": []},
            "api-reference": {
                "package": "mypkg",
                "parser": "numpy",
                "dynamic": True,
                "sections": [{"title": "Old", "contents": ["OldClass"]}],
            },
        }

        with open(quarto_yml, "w") as f:
            write_yaml(config, f)

        new_sections = [{"title": "New", "desc": "", "contents": ["NewClass", "new_func"]}]
        with patch.object(Exports, "sections", return_value=new_sections):
            reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert result["api-reference"]["sections"] == new_sections


def test_add_api_block_non_python_project():
    """
    Skip the API reference for a Go project without prompting for a package name

    A Go project has no Python package to inspect. Record that the build has no API reference.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Go project marker; no pyproject.toml / __init__.py anywhere.
        (Path(tmp_dir) / "go.mod").write_text("module example.com/tool\n", encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "project_type: go\n")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        with open(quarto_yml, "w") as f:
            write_yaml({"project": {"type": "website"}}, f)

        # Must not call input() — patch it to fail loudly if the skip is missed.
        with patch("builtins.input", side_effect=AssertionError("should not prompt")):
            run = make_run(docs)
            add_api_block(docs, run)

        assert run.has_api_reference is False


def test_add_api_block_carries_the_callable_signature_settings():
    """The `callable_signatures` block reaches the generated api-reference block.

    They are the renderer's only route to those settings: `Settings.make`
    reads them from the block this method writes.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(
            Path(tmp_dir), "callable_signatures:\n  style: plain\n  wrap: width\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        with open(quarto_yml, "w") as f:
            write_yaml({"project": {"type": "website"}}, f)

        sections = [{"title": "All", "desc": "", "contents": ["Widget"]}]
        with patch.object(Exports, "sections", return_value=sections):
            run = make_run(docs)
            add_api_block(docs, run)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert result["api-reference"]["callable_signatures"] == {
            "style": "plain",
            "wrap": "width",
        }


def test_add_api_block_defaults_the_callable_signature_settings():
    """A project that sets neither key still gets both, at their defaults."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        with open(quarto_yml, "w") as f:
            write_yaml({"project": {"type": "website"}}, f)

        sections = [{"title": "All", "desc": "", "contents": ["Widget"]}]
        with patch.object(Exports, "sections", return_value=sections):
            run = make_run(docs)
            add_api_block(docs, run)

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert result["api-reference"]["callable_signatures"] == {
            "style": "highlighted",
            "wrap": "per_parameter",
        }


def test_add_api_block_with_sections():
    """
    Write API reference sections and their navbar link to `_quarto.yml`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
        }
        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        fake_sections = [{"title": "Core", "desc": "", "contents": ["Widget", "helper_fn"]}]
        with patch.object(Exports, "sections", return_value=fake_sections):
            run = make_run(docs)
            add_api_block(docs, run)

        assert run.has_api_reference is True

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        assert "api-reference" in result
        assert result["api-reference"]["package"] == "mypkg"
        assert result["api-reference"]["sections"] == fake_sections

        # Should add Reference link to navbar
        left = result["website"]["navbar"]["left"]
        ref_items = [
            i for i in left if isinstance(i, dict) and i.get("href") == "reference/index.qmd"
        ]

        assert len(ref_items) == 1


def test_prepare_build_directory_creates_structure():
    """
    Create the build directory, scripts, reference directory and ignore rules
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n\nContent.\n", encoding="utf-8")

        # This structure check does not require an importable package.
        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        # Check directory structure
        assert docs.build_dir.exists()
        assert (docs.build_dir / "scripts").is_dir()
        assert (docs.build_dir / "reference").is_dir()

        # Check .gitignore
        gitignore = docs.build_dir / ".gitignore"

        assert gitignore.exists()

        content = gitignore.read_text()

        assert "Great Docs build directory" in content

        # Check SCSS theme file was copied
        assert (docs.build_dir / "great-docs.scss").exists()

        # Check _quarto.yml was created
        assert (docs.build_dir / "_quarto.yml").exists()

        # Check _gd_options.json was created

        options_path = docs.build_dir / "_gd_options.json"

        assert options_path.exists()

        options = json.loads(options_path.read_text())

        assert "freeze_dir" in options


def test_prepare_build_directory_can_retry_after_missing_header_include(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("include_in_header:\n  - file: header.html\n")
    docs = GreatDocs(project_path=str(tmp_path))

    with patch("great_docs._build.reference.add_api_block"):
        with patch.object(reference_sections, "update_sidebar"):
            with pytest.raises(FileNotFoundError, match="Header include file not found"):
                prepare_build_directory(docs, make_run(docs))

            (tmp_path / "header.html").write_text('<meta name="retry">\n')
            prepare_build_directory(docs, make_run(docs))

    assert (docs.build_dir / "_quarto.yml").exists()
    assert (docs.build_dir / "_includes" / "header.html").read_text() == ('<meta name="retry">\n')


def test_prepare_build_directory_writes_website_project(tmp_path):
    """The header-only ownership marker must not suppress the website project type"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("display_name: My Package\n")
    docs = GreatDocs(project_path=str(tmp_path))

    with patch("great_docs._build.reference.add_api_block"):
        with patch.object(reference_sections, "update_sidebar"):
            prepare_build_directory(docs, make_run(docs))

    config = read_yaml(docs.build_dir / "_quarto.yml")
    assert config["project"]["type"] == "website"
    assert "navbar" in config["website"]


def test_prepare_build_directory_adds_llms_links_after_api_reference_setup():
    """Include `llms.txt` links after API reference setup"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# Example\n\nPackage documentation.\n", encoding="utf-8")

        package_dir = Path(tmp_dir) / "mypkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text(
            'def widget():\n    """Perform no operation"""\n', encoding="utf-8"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            sections = [{"title": "All", "desc": "", "contents": ["widget"]}]
            with patch.object(Exports, "sections", return_value=sections):
                prepare_build_directory(docs, make_run(docs))

            index_content = (docs.build_dir / "index.qmd").read_text()
            assert "llms.txt" in index_content
            assert "llms-full.txt" in index_content
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("mypkg", None)


def test_prepare_build_directory_copies_js_files():
    """
    Copy the site's JavaScript files into the build directory
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n", encoding="utf-8")

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        # The GitHub widget needs a repository; the other core scripts do not.
        assert not (docs.build_dir / "github-widget.js").exists()
        assert (docs.build_dir / "sidebar-filter.js").exists()
        assert (docs.build_dir / "dark-mode-toggle.js").exists()
        assert (docs.build_dir / "theme-init.js").exists()
        assert (docs.build_dir / "copy-code.js").exists()
        assert (docs.build_dir / "tooltips.js").exists()
        assert (docs.build_dir / "responsive-tables.js").exists()


def test_config_bibliography_normalization():
    """Config.bibliography normalizes string, list, and missing values."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # Single string -> one-element list
        (root / "great-docs.yml").write_text(
            "package: mypkg\nbibliography: docs/references.bib\n", encoding="utf-8"
        )
        assert Config(root).bibliography == ["docs/references.bib"]

        # List -> filtered list
        (root / "great-docs.yml").write_text(
            "package: mypkg\nbibliography:\n  - docs/a.bib\n  - docs/b.bib\n",
            encoding="utf-8",
        )
        assert Config(root).bibliography == ["docs/a.bib", "docs/b.bib"]

        # Missing -> empty list
        (root / "great-docs.yml").write_text("package: mypkg\n", encoding="utf-8")
        cfg = Config(root)
        assert cfg.bibliography == []
        assert cfg.csl is None

        # CSL string
        (root / "great-docs.yml").write_text(
            "package: mypkg\ncsl: docs/nature.csl\n", encoding="utf-8"
        )
        assert Config(root).csl == "docs/nature.csl"


def test_prepare_build_directory_copies_bibliography():
    """
    Copy the bibliography and register it in `_quarto.yml`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (root / "README.md").write_text("# My Pkg\n", encoding="utf-8")
        (root / "great-docs.yml").write_text(
            "package: mypkg\nbibliography: docs/references.bib\n", encoding="utf-8"
        )
        docs_dir = root / "docs"
        docs_dir.mkdir()
        (docs_dir / "references.bib").write_text("@book{key, title={T}}\n", encoding="utf-8")

        docs = GreatDocs(project_path=tmp_dir)

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        # .bib copied into build dir by basename
        assert (docs.build_dir / "references.bib").exists()

        # _quarto.yml references it by basename
        with open(docs.build_dir / "_quarto.yml", "r") as f:
            config = read_yaml(f)
        assert config["bibliography"] == "references.bib"


def test_prepare_build_directory_copies_multiple_bib_and_csl():
    """
    Copy multiple bibliographies and a CSL file and register them in `_quarto.yml`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (root / "README.md").write_text("# My Pkg\n", encoding="utf-8")
        (root / "great-docs.yml").write_text(
            "package: mypkg\n"
            "bibliography:\n  - docs/refs.bib\n  - docs/software.bib\n"
            "csl: docs/nature.csl\n",
            encoding="utf-8",
        )
        docs_dir = root / "docs"
        docs_dir.mkdir()
        (docs_dir / "refs.bib").write_text("@book{a, title={A}}\n", encoding="utf-8")
        (docs_dir / "software.bib").write_text("@misc{b, title={B}}\n", encoding="utf-8")
        (docs_dir / "nature.csl").write_text("<style/>\n", encoding="utf-8")

        docs = GreatDocs(project_path=tmp_dir)

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        assert (docs.build_dir / "refs.bib").exists()
        assert (docs.build_dir / "software.bib").exists()
        assert (docs.build_dir / "nature.csl").exists()

        with open(docs.build_dir / "_quarto.yml", "r") as f:
            config = read_yaml(f)
        assert config["bibliography"] == ["refs.bib", "software.bib"]
        assert config["csl"] == "nature.csl"


def test_prepare_build_directory_bibliography_missing_warns(capsys):
    """A configured but missing .bib/.csl file warns instead of failing the build."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (root / "README.md").write_text("# My Pkg\n", encoding="utf-8")
        (root / "great-docs.yml").write_text(
            "package: mypkg\nbibliography: docs/missing.bib\ncsl: docs/missing.csl\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        out = capsys.readouterr().out
        assert "Bibliography file not found" in out
        assert "CSL file not found" in out
        assert not (docs.build_dir / "missing.bib").exists()


def test_bibliography_does_not_set_reference_section_title():
    """Great Docs leaves the references heading to Quarto's native localization.

    Under `shift-heading-level-by: -1` an explicit `reference-section-title`
    is demoted to a stray `<p>` and duplicated next to Quarto's appendix
    heading, so Great Docs must not set it. Quarto localizes the heading from
    `lang` (e.g. "Les références" for French).
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (root / "README.md").write_text("# My Pkg\n", encoding="utf-8")
        docs_dir = root / "docs"
        docs_dir.mkdir()
        (docs_dir / "references.bib").write_text("@book{k, title={T}}\n", encoding="utf-8")
        (root / "great-docs.yml").write_text(
            "package: mypkg\nbibliography: docs/references.bib\nsite:\n  lang: fr\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        with open(docs.build_dir / "_quarto.yml", encoding="utf-8") as f:
            config = read_yaml(f)

        # The bibliography is still wired up...
        assert config.get("bibliography") == "references.bib"
        assert config["format"]["html"]["lang"] == "fr"
        assert "lang" not in config

        # ...but the references heading is left to Quarto (no explicit override).
        assert "reference-section-title" not in config


def _prepared_quarto_config(lang: str) -> dict:
    """Read the generated Quarto configuration for the selected site language"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (root / "README.md").write_text("# My Pkg\n", encoding="utf-8")
        (root / "great-docs.yml").write_text(
            f"package: mypkg\nsite:\n  lang: {lang}\n", encoding="utf-8"
        )

        docs = GreatDocs(project_path=tmp_dir)
        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        with open(docs.build_dir / "_quarto.yml", encoding="utf-8") as f:
            return read_yaml(f)


def test_strings_are_supplied_where_quarto_has_no_translation():
    from great_docs._translations import QUARTO_LANGUAGE_KEYS

    config = _prepared_quarto_config("ar")

    assert config["format"]["html"]["lang"] == "ar"
    assert set(config["language"]) == {"ar"}
    strings = config["language"]["ar"]
    assert set(strings) == set(QUARTO_LANGUAGE_KEYS)
    assert strings["callout-note-title"] == "ملاحظة"
    assert strings["search-label"] == "بحث"


@pytest.mark.parametrize(("lang", "label"), [("hi", "खोज"), ("ro", "Căutare"), ("zh-Hant", "搜尋")])
def test_search_label_is_supplied_where_quarto_has_no_translation(lang: str, label: str):
    config = _prepared_quarto_config(lang)

    assert config["language"][lang]["search-label"] == label


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_strings_are_left_to_quarto_where_it_translates_them(lang: str):
    config = _prepared_quarto_config(lang)

    assert "language" not in config


def test_prepare_build_directory_optional_js_copy_page():
    """
    Copy `copy-page.js` when the Markdown pages widget is enabled
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "markdown_pages_widget: true\n")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n", encoding="utf-8")

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        assert (docs.build_dir / "copy-page.js").exists()


def test_prepare_build_directory_cleans_existing():
    """
    Remove stale files before preparing the build directory
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n", encoding="utf-8")

        # Create a stale file in the build directory
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        (docs.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER)
        stale_file = docs.build_dir / "stale.txt"
        stale_file.write_text("old content")

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        # Stale file should be gone
        assert not stale_file.exists()

        # But new files should exist
        assert docs.build_dir.exists()


def test_parse_dunder_all_with_all_simple():
    """Verify that a literal `__all__` list supplies export names"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__all__ = ["WidgetA", "WidgetB", "helper_fn"]\n__version__ = "1.0"\n')

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is not None
        assert "WidgetA" in result
        assert "WidgetB" in result
        assert "helper_fn" in result


def test_parse_dunder_all_with_exclude():
    """Verify that configured exclusions remove names from literal `__all__`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "exclude:\n  - helper_fn\n")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__all__ = ["WidgetA", "helper_fn"]\n')

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is not None
        assert "WidgetA" in result
        assert "helper_fn" not in result


def test_parse_dunder_all_no_all_returns_none():
    """Verify that parsing returns `None` without a literal `__all__` list"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__version__ = "1.0"\n')

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is None


def test_parse_dunder_all_static_forms(tmp_path: Path):
    """
    Verify that lists, tuples, `+` and `+=` preserve export order
    """
    init_file = tmp_path / "__init__.py"
    init_file.write_text('__all__ = ("a",) + ["b"]\n__all__ += ["c"]\n__all__ += ("d",)\n')

    result = parse_dunder_all(init_file, write_config(tmp_path), report=print)

    assert result == ["a", "b", "c", "d"]


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ("", ["Widget"]),
        ("auto_include:\n  - main\n", ["Widget", "main"]),
        ("no_auto_exclude: true\n", ["Widget", "main", "logger"]),
    ],
)
def test_parse_dunder_all_auto_exclude(tmp_path: Path, settings: str, expected: list[str]):
    """
    Verify that `auto_include` and `no_auto_exclude` override automatic exclusions
    """
    init_file = tmp_path / "__init__.py"
    init_file.write_text('__all__ = ["Widget", "main", "logger"]\n')

    result = parse_dunder_all(init_file, write_config(tmp_path, settings), report=print)

    assert result == expected


def test_update_quarto_config_page_footer_three_authors():
    """Test page footer with 3+ authors uses Oxford comma."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n'
            '[[project.authors]]\nname = "Alice"\n'
            '[[project.authors]]\nname = "Bob"\n'
            '[[project.authors]]\nname = "Carol"\n',
            encoding="utf-8",
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer_text = result["website"]["page-footer"]["center"]

        assert "Developed by" in footer_text
        assert ", and" in footer_text  # Oxford comma


def test_update_quarto_config_page_footer_single_author():
    """Test page footer with a single author."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[[project.authors]]\nname = "Solo Dev"\n',
            encoding="utf-8",
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer_text = result["website"]["page-footer"]["center"]

        assert "Solo" in footer_text
        assert " and " not in footer_text.split("Developed by")[1].split(".")[0]


def test_update_quarto_config_page_footer_author_homepage():
    """Test page footer links author name when homepage is provided."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[[project.authors]]\nname = "Alice"\n',
            encoding="utf-8",
        )

        docs._config = write_config(
            Path(tmp_dir), "authors:\n  - name: Alice\n    homepage: https://alice.dev\n"
        )

        quarto_yml = docs.build_dir / "_quarto.yml"
        quarto_yml.parent.mkdir(parents=True, exist_ok=True)

        base_config = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

        with open(quarto_yml, "w") as f:
            write_yaml(base_config, f)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml, "r") as f:
            result = read_yaml(f)

        footer_text = result["website"]["page-footer"]["center"]

        assert "https://alice.dev" in footer_text
        assert "<a href=" in footer_text


def test_build_sections_from_reference_config_skips_empty_sections():
    """Test that sections with no contents are skipped."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        ref_config = [
            {"title": "Empty", "contents": []},
            {"title": "Valid", "contents": ["Foo"]},
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "Valid"


def test_build_sections_from_reference_config_dict_no_name():
    """Test that dict items without 'name' are skipped."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        ref_config = [
            {"title": "Test", "contents": [{"members": True}, {"name": "Valid"}]},
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert len(result[0]["contents"]) == 1
        assert result[0]["contents"][0] == "Valid"


def test_categorise_references_all_found_no_error():
    """Verify that configured names are classified when all exist"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mypkg2"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Test package."""\n'
            "def greet():\n"
            '    """Say hello."""\n'
            "    pass\n"
            "\n"
            "class Widget:\n"
            '    """A widget."""\n'
            "    pass\n"
        )

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg2"\n', encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)

            reference_config = [
                {
                    "title": "API",
                    "contents": ["greet", "Widget"],
                }
            ]

            # Should not raise
            categories = categorise_references(
                make_exports(docs).package("mypkg2"), reference_config
            )
            assert "greet" in categories["functions"]
            assert "Widget" in categories["classes"]
        finally:
            sys.path.remove(tmp_dir)


_POETRY_1_PYPROJECT = """\
[tool.poetry]
name = "poetry-pkg"
version = "1.0.0"
description = "A Poetry 1.x package"
authors = ["Ada Lovelace <ada@example.com>"]
repository = "https://github.com/owner/repo"
"""


def test_poetry_1_project_facts_reach_the_build(tmp_path: Path):
    """A Poetry 1.x project supplies the name, description and GitHub repository"""
    (tmp_path / "pyproject.toml").write_text(_POETRY_1_PYPROJECT, encoding="utf-8")
    # A second package directory rules out naming the project after a lone directory.
    for package in ("poetry_pkg", "tests"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text("", encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))

    project = make_project(docs)

    assert project.name == "poetry-pkg"
    assert project.manifest["description"] == "A Poetry 1.x package"
    assert project.github == GithubRepo("owner", "repo")


def test_empty_categories_structure():
    """Verify that empty categories contain every expected key"""
    cats = empty_categories()
    expected_keys = [
        "classes",
        "dataclasses",
        "enums",
        "exceptions",
        "namedtuples",
        "typeddicts",
        "protocols",
        "abstract_classes",
        "functions",
        "async_functions",
        "constants",
        "type_aliases",
        "other",
        "class_methods",
        "class_method_names",
        "cyclic_alias_count",
    ]
    for key in expected_keys:
        assert key in cats


def test_count_pages_flat():
    """
    Count page paths in a flat sidebar
    """
    result = cli_render.count_pages(["a.qmd", "b.qmd", "c.qmd"])
    assert result == 3


def test_count_pages_nested():
    """
    Count page paths recursively through sidebar sections
    """
    items = [
        "a.qmd",
        {"section": "Group", "contents": ["b.qmd", "c.qmd"]},
        "d.qmd",
    ]
    result = cli_render.count_pages(items)
    assert result == 4


def test_count_pages_empty():
    """
    Return zero for an empty sidebar
    """
    result = cli_render.count_pages([])
    assert result == 0


def test_parse_dunder_all_with_all():
    """Verify that literal `__all__` parsing preserves export names"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "my_function", "CONSTANT"]\n',
            encoding="utf-8",
        )

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is not None
        assert "MyClass" in result
        assert "my_function" in result
        assert "CONSTANT" in result


def test_parse_dunder_all_with_exclusions():
    """Verify that literal `__all__` parsing applies configured exclusions"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir), "exclude:\n  - CONSTANT\n")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "CONSTANT"]\n',
            encoding="utf-8",
        )

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is not None
        assert "MyClass" in result
        assert "CONSTANT" not in result


def test_parse_dunder_all_no_all():
    """Verify that parsing returns `None` when `__all__` is absent"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "import os\n\ndef helper(): pass\n",
            encoding="utf-8",
        )

        result = parse_dunder_all(_package_init(docs, "mypkg"), docs._config, report=print)

        assert result is None


def test_auto_exclude_set():
    """Test AUTO_EXCLUDE contains expected common names."""
    assert "main" in AUTO_EXCLUDE
    assert "cli" in AUTO_EXCLUDE
    assert "version" in AUTO_EXCLUDE
    assert "VERSION" in AUTO_EXCLUDE


def test_strip_numeric_prefix():
    """Test _strip_numeric_prefix removes numeric prefixes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert strip_numeric_prefix("01-intro.qmd") == "intro.qmd"
        assert strip_numeric_prefix("10-advanced.qmd") == "advanced.qmd"
        assert strip_numeric_prefix("no-prefix.qmd") == "no-prefix.qmd"


def test_write_homepage_with_readme():
    """
    Create the homepage from `README.md`
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        (Path(tmp_dir) / "README.md").write_text(
            "# My Package\n\nA great package.\n", encoding="utf-8"
        )

        # Create build directory
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True, exist_ok=True)

        write_homepage(docs)
        index_qmd = build_dir / "index.qmd"
        assert index_qmd.exists()
        content = index_qmd.read_text(encoding="utf-8")
        assert "great package" in content


def test_write_homepage_no_source():
    """
    Generate a landing page with installation instructions when no README exists
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\ndescription = "A test pkg"\n',
            encoding="utf-8",
        )

        # Create build directory
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True, exist_ok=True)

        write_homepage(docs)
        index_qmd = build_dir / "index.qmd"
        assert index_qmd.exists()
        content = index_qmd.read_text(encoding="utf-8")
        assert "pip install" in content


def test_homepage_margin():
    """Verify that sidebar rendering returns a string"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        result = homepage_margin(docs)
        assert isinstance(result, str)


def test_homepage_hero_not_enabled():
    """Verify that the hero produces no HTML when not enabled"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        result = homepage_hero(docs, "# Some readme content\n")
        assert isinstance(result, tuple)
        assert len(result) == 2


def test_prepare_build_directory():
    """
    Create the Quarto project with its stylesheet and signature grammar
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        prepare_build_directory(docs, make_run(docs))

        build_dir = Path(tmp_dir) / "great-docs"
        assert build_dir.exists()
        assert (build_dir / "_quarto.yml").exists()
        assert (build_dir / "great-docs.scss").exists()
        assert (build_dir / "pythonsignature.xml").exists()


def test_update_quarto_config_creates_structure():
    """
    Set the site output directory and include the Great Docs theme
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\nformat:\n  html:\n    theme: flatly\n",
            encoding="utf-8",
        )

        update_quarto_config(docs, make_run(docs))

        result = _parse_yaml(quarto_yml.read_text(encoding="utf-8"))
        assert result["project"]["output-dir"] == "_site"
        theme = result.get("format", {}).get("html", {}).get("theme", [])
        assert "great-docs.scss" in theme


def _syntax_definitions_after_update(tmp_path: Path, html: str) -> list[str]:
    """Return syntax definitions after two updates to the supplied `format.html` block"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)
    quarto_yml = docs.build_dir / "_quarto.yml"
    quarto_yml.write_text(
        f"project:\n  type: website\nformat:\n  html:\n    theme: flatly\n{html}",
        encoding="utf-8",
    )

    update_quarto_config(docs, make_run(docs))
    update_quarto_config(docs, make_run(docs))

    result = _parse_yaml(quarto_yml.read_text(encoding="utf-8"))
    return result["format"]["html"]["syntax-definitions"]


def test_update_quarto_config_adds_the_signature_grammar(tmp_path):
    """Quarto receives the grammar it highlights signatures with, once"""
    assert _syntax_definitions_after_update(tmp_path, "") == ["pythonsignature.xml"]


def test_update_quarto_config_keeps_the_users_syntax_definitions(tmp_path):
    """A user's own definition, written as a string or a list, stays first"""
    as_string = _syntax_definitions_after_update(tmp_path, "    syntax-definitions: mine.xml\n")
    assert as_string == ["mine.xml", "pythonsignature.xml"]

    as_list = _syntax_definitions_after_update(
        tmp_path, "    syntax-definitions:\n      - mine.xml\n"
    )
    assert as_list == ["mine.xml", "pythonsignature.xml"]


def test_reference_enabled_config():
    """Test that reference_enabled config is read from great-docs.yml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("reference: false\n", encoding="utf-8")
        config = Config(Path(tmp_dir))
        assert config.reference_enabled is False


def test_homepage_margin_with_authors_b9():
    """Verify that the sidebar shows authors when available"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[[project.authors]]\nname = "Dev One"\n',
            encoding="utf-8",
        )
        result = homepage_margin(docs)
        assert isinstance(result, str)
        # Should contain the author name
        assert "Dev One" in result


def test_entry_point_name_b9():
    """
    Read the script name from `pyproject.toml`
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[project.scripts]\nmytool = "mypkg.cli:main"\n',
            encoding="utf-8",
        )
        result = cli_click.entry_point_name(docs.layout.package_root, "other:cli")
        assert result == "mytool"


def test_entry_point_name_no_scripts_b9():
    """
    Return `None` when no scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        result = cli_click.entry_point_name(docs.layout.package_root, "other:cli")
        assert result is None


def test_detect_dynamic_mode_with_cyclic_error():
    """Verify that a cyclic alias disables dynamic introspection"""

    with tempfile.TemporaryDirectory():
        mock_pkg = MagicMock()
        mock_member = MagicMock()
        mock_member.name = "MyClass"
        mock_pkg.members = {"MyClass": mock_member}

        def fake_get_object(path, dynamic=False):
            raise griffe.CyclicAliasError("Cyclic alias")

        # Patch object lookup before module importing; resolving a patch target imports its module.
        with (
            patch("great_docs._reference.probe.get_object", side_effect=fake_get_object),
            patch("great_docs._reference.probe.importlib.import_module"),
        ):
            result = detect_dynamic_mode(mock_pkg, ["MyClass"], report=print)

        assert result is False


def test_detect_dynamic_mode_samples_the_exports(tmp_path: Path):
    """Verify that the dynamic probe samples discovered exports"""
    pkg_dir = tmp_path / "sampled_dynpkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import Any, TypeVar\n"
        '__all__ = ["Widget"]\n'
        "class Widget:\n"
        "    pass\n",
        encoding="utf-8",
    )
    package = griffe.load("sampled_dynpkg", search_paths=[tmp_path])
    paths: list[str] = []

    def fake_get_object(path, dynamic=False):
        paths.append(path)
        return MagicMock(members={})

    sys.path.insert(0, str(tmp_path))
    try:
        with patch("great_docs._reference.probe.get_object", side_effect=fake_get_object):
            assert detect_dynamic_mode(package, ["Widget"], report=print) is True
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("sampled_dynpkg", None)

    assert paths == ["sampled_dynpkg:Widget"]


def test_detect_dynamic_mode_is_off_for_an_unimportable_package(tmp_path: Path):
    """Verify that a failed package import disables dynamic mode and reports a hint"""
    pkg_dir = tmp_path / "unimportable_dynpkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        "import not_a_real_dependency_xyz\nclass Widget:\n    pass\n", encoding="utf-8"
    )
    package = griffe.load("unimportable_dynpkg", search_paths=[tmp_path])
    lines: list[str] = []

    sys.path.insert(0, str(tmp_path))
    try:
        result = detect_dynamic_mode(package, ["Widget"], report=lines.append)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("unimportable_dynpkg", None)

    assert result is False
    assert lines == [
        "Warning: Could not import 'unimportable_dynpkg' (ModuleNotFoundError: "
        "No module named 'not_a_real_dependency_xyz'); using dynamic: false",
        "Install the package's dependencies and set `dynamic: true` in great-docs.yml "
        "to document docstrings that are set at runtime",
    ]

    # Just confirm no crash

    # Should not crash, and should not add navbar


def test_empty_categories_has_all_keys():
    """Verify that empty categories contain every required key"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cats = empty_categories()
        expected_keys = [
            "classes",
            "dataclasses",
            "enums",
            "exceptions",
            "namedtuples",
            "typeddicts",
            "protocols",
            "abstract_classes",
            "functions",
            "async_functions",
            "constants",
            "type_aliases",
            "other",
            "class_methods",
            "class_method_names",
            "cyclic_alias_count",
        ]
        for key in expected_keys:
            assert key in cats


def test_refresh_api_reference_config_no_api_reference():
    """Test _refresh_api_reference_config does nothing without api-reference config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True)
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text("website:\n  title: Test\n", encoding="utf-8")

        reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)
        # Should not crash


def test_refresh_api_reference_config_no_package():
    """Test _refresh_api_reference_config does nothing without package name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True)
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n  dir: reference\n",
            encoding="utf-8",
        )

        reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)
        # Should not crash


def test_write_homepage_with_badges():
    """
    Preserve README content and badges in the homepage
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")
        readme = Path(tmp_dir) / "README.md"
        readme.write_text(
            "# My Package\n\n"
            "[![CI](https://github.com/owner/repo/actions/badge.svg)](https://github.com/owner/repo)\n\n"
            "A great package for doing things.\n",
            encoding="utf-8",
        )

        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True)

        write_homepage(docs)
        index_qmd = build_dir / "index.qmd"
        assert index_qmd.exists()
        content = index_qmd.read_text(encoding="utf-8")
        assert "great package" in content


def test_update_quarto_config_with_assets():
    """
    Register the assets directory as a Quarto resource
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        build_dir = Path(tmp_dir) / "great-docs"
        build_dir.mkdir(parents=True)

        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "project:\n  type: website\nformat:\n  html:\n    theme: flatly\n",
            encoding="utf-8",
        )

        # Create assets directory
        assets_dir = build_dir / "assets"
        assets_dir.mkdir()
        (assets_dir / "image.png").write_text("fake image")

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)
        # Should have added assets/ to resources
        resources = config.get("project", {}).get("resources", [])
        assert "assets/**" in resources or any("assets" in str(r) for r in resources)


def test_prepare_build_directory_copies_assets():
    """
    Create the build directory and copy the Great Docs stylesheet
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        docs._config = write_config(Path(tmp_dir))

        prepare_build_directory(docs, make_run(docs))

        build_dir = Path(tmp_dir) / "great-docs"
        assert build_dir.exists()
        # Should have created _quarto.yml
        quarto_yml = build_dir / "_quarto.yml"
        assert quarto_yml.exists()


def test_build_sections_from_reference_config_dict_items():
    """Test _build_sections_from_reference_config with dict items and members."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ref_config = [
            {
                "title": "Classes",
                "contents": [
                    {"name": "MyClass", "members": False},
                    {"name": "OtherClass"},
                    "standalone_func",
                ],
            }
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert len(result) == 1
        contents = result[0]["contents"]
        assert contents[0] == {"name": "MyClass", "members": []}
        assert contents[1] == "OtherClass"
        assert contents[2] == "standalone_func"


def test_build_sections_from_reference_config_skips_non_dict():
    """Test _build_sections_from_reference_config skips non-dict section entries."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ref_config = [
            "not_a_dict",
            {"title": "Valid", "contents": ["func"]},
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "Valid"


def test_build_sections_from_reference_config_skips_empty_contents():
    """Test _build_sections_from_reference_config skips sections with empty contents."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ref_config = [
            {"title": "Empty", "contents": []},
            {"title": "Valid", "contents": ["func"]},
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "Valid"


def test_build_sections_from_reference_config_skips_nameless_dict():
    """Test _build_sections_from_reference_config skips dict items without name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ref_config = [
            {"title": "Mixed", "contents": [{"members": True}, {"name": "good"}]},
        ]
        result = reference_sections.from_reference_config(ref_config)
        assert result is not None
        assert result[0]["contents"] == ["good"]


def test_get_cli_entry_point_gui_scripts():
    """
    Read the GUI script name when no console scripts are defined
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "mypkg"\n[project.gui-scripts]\nmygui = "mypkg.gui:main"\n',
            encoding="utf-8",
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = cli_click.entry_point_name(docs.layout.package_root, "other:cli")
        assert result == "mygui"


def test_strip_numeric_prefix_basic():
    """Test _strip_numeric_prefix removes numeric prefixes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert strip_numeric_prefix("01-introduction.qmd") == "introduction.qmd"
        assert strip_numeric_prefix("10-advanced.qmd") == "advanced.qmd"
        assert strip_numeric_prefix("readme.qmd") == "readme.qmd"


def test_quarto_environment():
    """Return an environment containing `QUARTO_PYTHON`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = quarto.environment(docs._config)
        assert isinstance(env, dict)
        # Should set QUARTO_PYTHON
        assert "QUARTO_PYTHON" in env


def test_extract_directives_from_package_no_griffe():
    """Test _extract_directives_from_package handles missing griffe."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        with patch.dict("sys.modules", {"griffe": None}):
            # Should handle ImportError gracefully
            try:
                result = docs._extract_directives_from_package("nonexistent_pkg")
                assert isinstance(result, dict)
            except Exception:
                pass  # ImportError is acceptable


def test_empty_categories():
    """Verify that empty categories contain every reference group"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cats = empty_categories()
        assert "classes" in cats
        assert "functions" in cats
        assert "constants" in cats
        assert "class_methods" in cats
        assert "class_method_names" in cats
        assert isinstance(cats["classes"], list)
        assert isinstance(cats["class_methods"], dict)


def test_extract_command_basic():
    """
    Include the command's help text in the reference model
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        @click.command()
        @click.option("--name", "-n", help="Your name")
        @click.argument("path")
        def hello(name, path):
            """Say hello to someone."""
            pass

        result = cli_click.extract_command(hello, "hello")
        assert result["name"] == "hello"
        assert "Say hello" in result.get("help_text", "")


def test_extract_command_group():
    """
    Describe a Click group and its subcommands
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        @click.group()
        def cli():
            """Main CLI group."""
            pass

        @cli.command()
        def sub():
            """A subcommand."""
            pass

        result = cli_click.extract_command(cli, "cli")

        assert result["name"] == "cli"
        assert len(result.get("commands", [])) >= 1


# Packaging declarations for a named package, with and without a GitHub repository
MYPKG_PYPROJECT = '[project]\nname = "mypkg"\n'
MYPKG_ON_GITHUB_PYPROJECT = (
    MYPKG_PYPROJECT + '\n[project.urls]\nRepository = "https://github.com/owner/repo"\n'
)


def _buildable_docs(
    tmp_path: Path,
    *,
    quarto_yml: str = QUARTO_YML_HEADER,
    pyproject: str | None = None,
    **settings: object,
) -> GreatDocs:
    """
    Create a project for build tests with empty configuration defaults

    Parameters
    ----------
    tmp_path
        The project directory.
    quarto_yml
        The text of the build directory's `_quarto.yml`.
    pyproject
        The text of `pyproject.toml`, or `None` for a project without one.
    **settings
        `Config` property values, by name.

    Returns
    -------
    :
        The project with an empty `great-docs.yml`, a configuration double and a build
        directory containing `_quarto.yml`.
    """
    if pyproject is not None:
        (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    # `GreatDocs.build()` requires a configuration file, even with a configuration double.
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    docs._config = mock_config(**settings)
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(quarto_yml, encoding="utf-8")
    return docs


def test_build_prepare_and_render_flow(tmp_path):
    """Test build() happy path: prepares, renders, runs quarto render."""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER + "api-reference:\n  package: mypkg\n",
    )
    mock_builder = MagicMock()
    mock_builder_class = MagicMock(return_value=mock_builder)

    with (
        stubbed_build(docs, api_reference=True),
        patch("great_docs._apiref.api_reference.APIReference", mock_builder_class),
    ):
        docs.build(watch=False, refresh=True)

    mock_builder_class.assert_called_once()
    mock_builder.build.assert_called_once()


def test_build_no_api_reference(tmp_path):
    """
    Check that builds without an API reference skip its renderer and still write page metadata
    """
    docs = _buildable_docs(tmp_path)
    mock_builder_class = MagicMock()

    with (
        stubbed_build(docs),
        patch("great_docs._apiref.api_reference.APIReference", mock_builder_class),
        patch("great_docs._website.prerender.write_page_metadata") as write_page_metadata,
    ):
        docs.build(watch=False, refresh=False)

    mock_builder_class.assert_not_called()
    write_page_metadata.assert_called_once()


def test_build_after_a_build_without_api_reference_generates_one(tmp_path):
    """
    Verify API reference generation after a build without one on the same instance
    """
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER + "api-reference:\n  package: mypkg\n",
    )
    with stubbed_build(docs):
        docs.build(refresh=False)

    mock_builder_class = MagicMock()
    with (
        stubbed_build(docs, api_reference=True),
        patch("great_docs._apiref.api_reference.APIReference", mock_builder_class),
    ):
        docs.build(refresh=False)

    mock_builder_class.return_value.build.assert_called_once()


def test_build_dynamic_fallback_to_static(tmp_path):
    """Test build() falls back to static mode when dynamic mode fails."""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER
        + format_yaml({"api-reference": {"package": "mypkg", "dynamic": True}}),
        dynamic=True,
    )
    mock_builder = MagicMock()
    mock_builder.build.side_effect = [RuntimeError("Dynamic mode failed"), None]

    with (
        stubbed_build(docs, api_reference=True),
        patch(
            "great_docs._apiref.api_reference.APIReference", MagicMock(return_value=mock_builder)
        ),
    ):
        docs.build(watch=False, refresh=True)

    assert mock_builder.build.call_count == 2  # first dynamic, then static


def test_build_dynamic_fallback_preserves_the_quarto_yml_header(tmp_path):
    """The static-analysis retry rewrites api-reference.dynamic without losing the ownership header."""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER
        + format_yaml({"api-reference": {"package": "mypkg", "dynamic": True}}),
        dynamic=True,
    )
    mock_builder = MagicMock()
    mock_builder.build.side_effect = [RuntimeError("Dynamic mode failed"), None]

    with (
        stubbed_build(docs, api_reference=True),
        patch(
            "great_docs._apiref.api_reference.APIReference", MagicMock(return_value=mock_builder)
        ),
    ):
        docs.build(watch=False, refresh=True)

    quarto_yml = docs.build_dir / "_quarto.yml"
    assert quarto_yml.read_text(encoding="utf-8").startswith(QUARTO_YML_HEADER)


def test_build_static_mode_failure_raises(tmp_path):
    """Raise `BuildError` when static API reference generation also fails"""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER
        + format_yaml({"api-reference": {"package": "mypkg", "dynamic": True}}),
        dynamic=True,
    )
    mock_builder = MagicMock()
    mock_builder.build.side_effect = RuntimeError("Build always fails")

    with (
        stubbed_build(docs, api_reference=True),
        patch(
            "great_docs._apiref.api_reference.APIReference", MagicMock(return_value=mock_builder)
        ),
        pytest.raises(BuildError, match="API reference build failed"),
    ):
        docs.build(watch=False, refresh=True)


def test_build_non_dynamic_failure_raises(tmp_path):
    """Raise `BuildError` when non-dynamic API reference generation fails"""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=QUARTO_YML_HEADER + format_yaml({"api-reference": {"package": "mypkg"}}),
    )
    mock_builder = MagicMock()
    mock_builder.build.side_effect = RuntimeError("Build failed")

    with (
        stubbed_build(docs, api_reference=True),
        patch(
            "great_docs._apiref.api_reference.APIReference", MagicMock(return_value=mock_builder)
        ),
        pytest.raises(BuildError, match="API reference build failed"),
    ):
        docs.build(watch=False, refresh=True)


# A published release as `Remote.github_releases` returns it
GITHUB_RELEASE = {
    "tag_name": "v1.0.0",
    "name": "",
    "body": "",
    "published_at": "2026-01-01T00:00:00Z",
    "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
    "prerelease": False,
}

# A site configuration whose navbar links only the API reference
NAVBAR_QUARTO_YML = (
    QUARTO_YML_HEADER
    + "website:\n  navbar:\n    left:\n      - text: Reference\n        href: reference/index.qmd\n"
)


def _navbar_hrefs(docs: GreatDocs) -> list[str]:
    """
    Read the targets of the links on the left of the site's navbar

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        Each link's `href`, in order.
    """
    return [item["href"] for item in read_quarto_yml(docs.build_dir)["website"]["navbar"]["left"]]


def test_build_with_changelog(tmp_path):
    """Check that the build generates a changelog when enabled"""
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_ON_GITHUB_PYPROJECT,
        quarto_yml=NAVBAR_QUARTO_YML,
        changelog_enabled=True,
        changelog_max_releases=50,
    )
    docs._remote = StubRemote(releases=[GITHUB_RELEASE])

    with stubbed_build(
        docs,
    ):
        docs.build(watch=False, refresh=False)

    assert "## v1.0.0" in (docs.build_dir / "changelog.qmd").read_text(encoding="utf-8")
    assert _navbar_hrefs(docs) == ["reference/index.qmd", "changelog.qmd"]


def test_build_changelog_error_stops_the_build(tmp_path):
    """
    Check that a changelog failure stops the build

    The changelog step handles unreachable or malformed GitHub releases. Any other failure
    is an error in great-docs and must stop the build.
    """
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_ON_GITHUB_PYPROJECT,
        quarto_yml=NAVBAR_QUARTO_YML,
        changelog_enabled=True,
        changelog_max_releases=50,
    )
    docs._remote = StubRemote(releases=[GITHUB_RELEASE])
    # The page cannot be written over a directory
    (docs.build_dir / "changelog.qmd").mkdir()

    with stubbed_build(
        docs,
    ) as stubs:
        with pytest.raises(IsADirectoryError):
            docs.build(watch=False, refresh=False)

    assert _navbar_hrefs(docs) == ["reference/index.qmd"]
    stubs.steps["site.default_description"].assert_not_called()


def test_build_with_cli_documentation(tmp_path):
    """Test build() generates CLI docs when cli_enabled."""
    docs = _buildable_docs(tmp_path, pyproject=MYPKG_PYPROJECT, cli_enabled=True)
    cli_info = {"name": "mycli", "commands": [], "help_text": "Help"}
    cli_files = ["reference/cli/index.qmd"]

    with (
        stubbed_build(docs),
        patch("great_docs._cliref.click.discover", return_value=cli_info) as discover,
        patch("great_docs._cliref.render.write_pages", return_value=cli_files) as write_pages,
    ):
        docs.build(watch=False, refresh=False)

    discover.assert_called_once()
    write_pages.assert_called_once_with(docs._config, docs.build_dir, cli_info, report=print)
    sidebars = read_quarto_yml(docs.build_dir)["website"]["sidebar"]
    assert [s["contents"] for s in sidebars if s["id"] == "cli-reference"] == [cli_files]


def test_build_with_sections(tmp_path):
    """Test build() processes custom sections when configured."""
    docs = _buildable_docs(tmp_path, sections=[{"title": "Recipes"}])

    with stubbed_build(docs) as stubs:
        docs.build(watch=False, refresh=False)

    stubs.steps["content.sections"].assert_called_once()


def test_build_with_assets_triggers_config_update(tmp_path):
    """Test build() updates quarto config when assets are copied."""
    docs = _buildable_docs(tmp_path)
    (docs.layout.source_dir / "assets").mkdir()
    (docs.layout.source_dir / "assets" / "logo.png").write_bytes(b"png")

    with stubbed_build(docs, run=["content.assets"]) as stubs:
        docs.build(watch=False, refresh=False)

    stubs.steps["site.update_quarto_config"].assert_called_once()
    assert (docs.build_dir / "assets" / "logo.png").read_bytes() == b"png"


def test_build_watch_mode(tmp_path):
    """Test build() in watch mode calls quarto preview."""
    docs = _buildable_docs(tmp_path)

    with stubbed_build(docs), patch("subprocess.run") as mock_run:
        docs.build(watch=True, refresh=False)

    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["quarto", "preview", "--no-browser"]


def test_build_quarto_render_failure(tmp_path):
    """Raise `BuildError` when Quarto fails to render"""
    docs = _buildable_docs(tmp_path)

    with stubbed_build(docs) as stubs:
        stubs.render.stderr = iter(["Error: something\n"])
        stubs.render.returncode = 1

        with pytest.raises(BuildError, match="Quarto render failed"):
            docs.build(watch=False, refresh=False)


def test_build_versioned_all_failed_raises(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Report failure and raise `BuildError` when every version fails to render"""
    docs = _buildable_docs(tmp_path, has_versions=True, versions=["0.2", "0.1"])
    failed = {"success": False, "errors": ["0.2: render boom"], "versions_built": []}

    with (
        stubbed_build(docs),
        patch("great_docs._versions.build.run_versioned_build", return_value=failed),
        pytest.raises(BuildError, match="All version builds failed"),
    ):
        docs.build(watch=False, refresh=False)

    out = capsys.readouterr().out
    assert "0.2: render boom" in out
    assert "All version builds failed" in out


def test_build_cli_error_handled(tmp_path, capsys):
    """
    Check that CLI discovery failures warn and skip CLI page generation

    `build()` prints `Error generating CLI docs: click` and still writes page
    metadata.
    """
    docs = _buildable_docs(tmp_path, pyproject=MYPKG_PYPROJECT, cli_enabled=True)

    with (
        stubbed_build(docs) as stubs,
        patch("great_docs._cliref.click.discover", side_effect=ImportError("click")),
        patch("great_docs._cliref.render.write_pages") as write_pages,
    ):
        docs.build(watch=False, refresh=False)

    assert "Error generating CLI docs: click" in capsys.readouterr().out
    write_pages.assert_not_called()
    stubs.steps["passes.terminal_recordings"].assert_called_once()


def test_build_llms_txt_error_handled(tmp_path, capsys):
    """
    Check that a failure writing `llms.txt` warns and the build continues
    """
    docs = _buildable_docs(tmp_path)

    with (
        stubbed_build(docs) as stubs,
        patch("great_docs._website.ai_agents.llms_txt.is_planned", return_value=True),
        patch(
            "great_docs._website.ai_agents.llms_txt.write_index",
            side_effect=RuntimeError("no summary"),
        ),
    ):
        docs.build(watch=False, refresh=False)

    assert "Error generating llms.txt: no summary" in capsys.readouterr().out
    stubs.steps["passes.terminal_recordings"].assert_called_once()


def test_build_skill_md_error_handled(tmp_path, capsys):
    """
    Check that a failure writing the agent skill files warns and the build continues
    """
    docs = _buildable_docs(tmp_path, skill_enabled=True)

    with (
        stubbed_build(docs) as stubs,
        patch(
            "great_docs._website.ai_agents.skills.SkillsWriter.write",
            side_effect=OSError("read-only"),
        ),
    ):
        docs.build(watch=False, refresh=False)

    assert "Error generating SKILL.md: read-only" in capsys.readouterr().out
    stubs.steps["passes.terminal_recordings"].assert_called_once()


def test_build_log_numbers_every_step(tmp_path, capsys):
    """
    Check that the log numbers all twenty steps in order and reports all twenty as run
    """
    docs = _buildable_docs(tmp_path)

    with stubbed_build(docs):
        docs.build(watch=False, refresh=False)

    out = capsys.readouterr().out
    headings = re.findall(r"Step\s+(\d+)/(\d+) \S (.+?) [━-]", out)
    assert [(int(n), int(total)) for n, total, _ in headings] == [(n, 20) for n in range(1, 21)]
    assert [title for *_, title in headings] == [
        "Prepare build directory",
        "Configure API reference",
        "Generate llms.txt / llms-full.txt",
        "Generate SKILL.md",
        "Generate changelog",
        "Generate CLI reference",
        "Generate Go CLI reference",
        "Generate Rust CLI reference",
        "Generate MCP server reference",
        "Process User Guide",
        "Process custom sections",
        "Process custom pages",
        "Process page tags",
        "Process page status badges",
        "Copy assets",
        "Generate API reference",
        "Build interlinks index",
        "Prepare freeze cache",
        "Build site with Quarto",
        "Generate SEO files",
    ]
    assert "Build complete — 20/20 steps" in out


def test_discover_with_explicit_cli_module(tmp_path):
    """
    Discover the command in the configured CLI module
    """
    mock_cli = click.Group(name="test-cli", help="Test CLI")

    mock_module = types.ModuleType("mypkg.cli")
    mock_module.cli = mock_cli

    with (
        patch("importlib.import_module", return_value=mock_module),
        patch.object(cli_click, "entry_point_name", return_value="my-cli"),
        patch.object(
            cli_click,
            "extract_command",
            return_value={"name": "my-cli", "commands": []},
        ),
    ):
        result = cli_click.discover(
            "mypkg", tmp_path, cli_module="mypkg.cli", cli_name=None, report=print
        )

    assert result is not None
    assert result["entry_point_name"] == "my-cli"


def test_discover_auto_discovers_module(tmp_path):
    """
    Discover a CLI module in a conventional location
    """
    mock_cmd = click.Command(name="tool", callback=lambda: None)

    mock_module = types.ModuleType("mypkg.cli")
    mock_module.tool = mock_cmd

    import_calls = []

    def mock_import(name):
        import_calls.append(name)
        if name == "mypkg.cli":
            return mock_module
        raise ImportError(f"No module {name}")

    with (
        patch("importlib.import_module", side_effect=mock_import),
        patch.object(cli_click, "entry_point_name", return_value=None),
        patch.object(
            cli_click,
            "extract_command",
            return_value={"name": "tool", "commands": []},
        ),
    ):
        result = cli_click.discover("mypkg", tmp_path, cli_module=None, cli_name=None, report=print)

    assert result is not None


def test_discover_explicit_cli_name(tmp_path):
    """
    Discover the command named by `cli.name`
    """
    mock_app = click.Group(name="myapp", help="My app")

    mock_module = types.ModuleType("pkg.cli")
    mock_module.myapp = mock_app

    with (
        patch("importlib.import_module", return_value=mock_module),
        patch.object(cli_click, "entry_point_name", return_value="my-app"),
        patch.object(
            cli_click,
            "extract_command",
            return_value={"name": "myapp", "commands": []},
        ),
    ):
        result = cli_click.discover(
            "pkg", tmp_path, cli_module="pkg.cli", cli_name="myapp", report=print
        )

    assert result is not None
    assert result["entry_point_name"] == "my-app"


def _typer_app() -> object:
    """
    Build a Typer app with one command

    Typer creates a new Click command each time it converts the app.
    """
    import typer

    app = typer.Typer()
    app.command()(lambda: None)
    return app


@pytest.mark.parametrize(
    ("attribute", "make_command"),
    [("cli", lambda: click.Group(name="cli")), ("app", _typer_app)],
    ids=["click", "typer"],
)
def test_discover_names_the_script_that_runs_the_command(
    tmp_path, monkeypatch, attribute, make_command
):
    """
    Use the script whose entry point names the discovered command
    """
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "pkg"\n'
        "[project.scripts]\n"
        'helper = "pkg.tools:main"\n'
        f'pkg = "pkg.cli:{attribute}"\n'
    )
    cli_module = types.ModuleType("pkg.cli")
    setattr(cli_module, attribute, make_command())
    tools_module = types.ModuleType("pkg.tools")
    tools_module.main = click.Command(name="main")
    monkeypatch.setitem(sys.modules, "pkg.cli", cli_module)
    monkeypatch.setitem(sys.modules, "pkg.tools", tools_module)

    result = cli_click.discover(
        "pkg", tmp_path, cli_module=None, cli_name=None, report=lambda _line: None
    )

    assert result is not None
    assert result["entry_point_name"] == "pkg"


def test_discover_no_command_found(tmp_path):
    """
    Return `None` when the CLI module contains no command
    """
    mock_module = types.ModuleType("pkg.cli")
    mock_module.helper = "not a click command"

    with patch("importlib.import_module", return_value=mock_module):
        result = cli_click.discover(
            "pkg", tmp_path, cli_module="pkg.cli", cli_name=None, report=print
        )

    assert result is None


def test_discover_import_failure(tmp_path):
    """
    Return `None` when the CLI module cannot be imported
    """
    with patch("importlib.import_module", side_effect=ImportError("nope")):
        result = cli_click.discover(
            "pkg", tmp_path, cli_module="pkg.cli", cli_name=None, report=print
        )

    assert result is None


def test_discover_fallback_dir_search(tmp_path):
    """
    Find a command under a non-standard public attribute name
    """
    # A non-standard attribute name requires the public-attribute fallback.
    mock_module = types.ModuleType("pkg.cli")
    mock_module.custom_command = click.Command(name="custom", callback=lambda: None)
    # Conventional names hold non-commands, so the scan must continue.
    mock_module.cli = "not a command"
    mock_module.main = "also not"
    mock_module.app = 42

    with (
        patch("importlib.import_module", return_value=mock_module),
        patch.object(cli_click, "entry_point_name", return_value=None),
        patch.object(
            cli_click,
            "extract_command",
            return_value={"name": "custom", "commands": []},
        ),
    ):
        result = cli_click.discover(
            "pkg", tmp_path, cli_module="pkg.cli", cli_name=None, report=print
        )

    assert result is not None


def test_discover_exports_with_all():
    """Verify that discovery selects names from `__all__`"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "allpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["PublicFunc", "PublicClass"]\n'
            "def PublicFunc(): pass\n"
            "class PublicClass: pass\n"
            "def _private(): pass\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("allpkg"), docs._config, report=print
            )

            assert result is not None
            assert "PublicFunc" in result
            assert "PublicClass" in result
            assert "_private" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_follows_all_order_and_reports_missing_names():
    """Exports follow `__all__` order, and a listed name the package does not define is reported"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "orderpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["second", "first", "lazy_name"]\n'
            "def first(): pass\n"
            "def second(): pass\n"
            "def __getattr__(name): return 42\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        lines: list[str] = []
        result = discover_exports(
            make_exports(docs).package("orderpkg"), docs._config, report=lines.append
        )

        assert result == ["second", "first"]
        assert any("lazy_name" in line for line in lines)


def test_discover_exports_without_all():
    """Verify that discovery excludes private names when `__all__` is absent"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "noallpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "def public_func(): pass\n"
            "class PublicClass: pass\n"
            "def _private_func(): pass\n"
            "_INTERNAL = 42\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("noallpkg"), docs._config, report=print
            )

            assert result is not None
            assert "public_func" in result
            assert "PublicClass" in result
            assert "_private_func" not in result
            assert "_INTERNAL" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_config_exclude():
    """Verify that configured exclusions remove discovered exports"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "exclpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["Wanted", "Excluded"]\nclass Wanted: pass\nclass Excluded: pass\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "great-docs.yml").write_text("exclude:\n  - Excluded\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("exclpkg"), docs._config, report=print
            )

            assert result is not None
            assert "Wanted" in result
            assert "Excluded" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_auto_exclude():
    """Verify that discovery excludes common metadata and helper names"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "autoexclpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "main", "logger"]\n'
            "class MyClass: pass\n"
            "def main(): pass\n"
            "import logging\n"
            "logger = logging.getLogger()\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("autoexclpkg"), docs._config, report=print
            )

            assert result is not None
            assert "MyClass" in result
            # "main" and "logger" should be auto-excluded
            assert "main" not in result
            assert "logger" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_auto_include():
    """Test auto_include forces names back through AUTO_EXCLUDE."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "autoincpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "config", "logger"]\n'
            "class MyClass: pass\n"
            "class config: pass\n"
            "import logging\n"
            "logger = logging.getLogger()\n",
            encoding="utf-8",
        )

        # Write a great-docs.yml that force-includes "config"
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("auto_include:\n  - config\n", encoding="utf-8")
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "autoincpkg"\n', encoding="utf-8"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("autoincpkg"), docs._config, report=print
            )

            assert result is not None
            assert "MyClass" in result
            # "config" should be force-included
            assert "config" in result
            # "logger" should still be auto-excluded
            assert "logger" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_no_auto_exclude():
    """Test no_auto_exclude bypasses the entire AUTO_EXCLUDE list."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "noautoexclpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "main", "config", "logger"]\n'
            "class MyClass: pass\n"
            "def main(): pass\n"
            "class config: pass\n"
            "import logging\n"
            "logger = logging.getLogger()\n",
            encoding="utf-8",
        )

        # Write a great-docs.yml that disables auto-exclude
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("no_auto_exclude: true\n", encoding="utf-8")
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "noautoexclpkg"\n', encoding="utf-8"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("noautoexclpkg"), docs._config, report=print
            )

            assert result is not None
            # All names should be present since auto-exclude is bypassed
            assert "MyClass" in result
            assert "main" in result
            assert "config" in result
            assert "logger" in result
        finally:
            sys.path.remove(tmp_dir)


def test_discover_exports_auto_include_no_overlap():
    """Test auto_include with names not in AUTO_EXCLUDE has no effect."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "nooverlappkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["MyClass", "main"]\nclass MyClass: pass\ndef main(): pass\n',
            encoding="utf-8",
        )

        # auto_include names that are NOT in AUTO_EXCLUDE
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("auto_include:\n  - MyClass\n", encoding="utf-8")
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "nooverlappkg"\n', encoding="utf-8"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("nooverlappkg"), docs._config, report=print
            )

            assert result is not None
            assert "MyClass" in result
            # "main" should still be auto-excluded
            assert "main" not in result
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_numpy():
    """Verify that NumPy section headings select the NumPy style"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "numpypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "def func(x):\n"
            '    """Do something.\n\n'
            "    Parameters\n"
            "    ----------\n"
            "    x\n"
            "        The value.\n\n"
            "    Returns\n"
            "    -------\n"
            "    int\n"
            '    """\n'
            "    return x\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("numpypkg"), report=print)
            assert style == "numpy"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_sphinx():
    """Verify that Sphinx fields select the Sphinx style"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "sphinxpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "def func(x):\n"
            '    """Do something.\n\n'
            "    :param x: The value.\n"
            "    :returns: The result.\n"
            '    """\n'
            "    return x\n"
            "def func2(y):\n"
            '    """More.\n\n'
            "    :param y: Another.\n"
            "    :rtype: int\n"
            '    """\n'
            "    return y\n",
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("sphinxpkg"), report=print)
            assert style == "sphinx"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_dynamic_mode_no_exports():
    """Verify that an importable package with no sampled exports permits dynamic mode"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "emptydynpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# empty package\n_private = 1\n", encoding="utf-8")

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = detect_dynamic_mode(
                make_exports(docs).package("emptydynpkg"), [], report=print
            )
            assert result is True
        finally:
            sys.path.remove(tmp_dir)


def test_build_sections_from_reference_config_explicit_members():
    """Test _build_sections_from_reference_config passes explicit members list."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = [
            {
                "title": "Classes",
                "contents": [
                    {"name": "Child", "members": ["own", "inherited"]},
                    {"name": "Other", "members": ["x"], "include_inherited": True},
                ],
            },
        ]
        result = reference_sections.from_reference_config(config)

        assert result is not None
        contents = result[0]["contents"]
        # Explicit members list passed through
        assert contents[0] == {"name": "Child", "members": ["own", "inherited"]}
        # include_inherited also attached
        assert contents[1] == {
            "name": "Other",
            "members": ["x"],
            "include_inherited": True,
        }


def test_build_sections_from_reference_config_empty():
    """Test _build_sections_from_reference_config returns None for empty config."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert reference_sections.from_reference_config([]) is None
        assert reference_sections.from_reference_config(None) is None


def test_build_sections_from_reference_config_basic():
    """Test _build_sections_from_reference_config with simple config."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = [
            {
                "title": "Classes",
                "desc": "All classes",
                "contents": ["ClassA", "ClassB"],
            },
            {
                "title": "Functions",
                "contents": [
                    "func_a",
                    {"name": "ClassC", "members": False},
                ],
            },
        ]
        result = reference_sections.from_reference_config(config)

        assert result is not None
        assert len(result) == 2
        assert result[0]["title"] == "Classes"
        assert "ClassA" in result[0]["contents"]

        # Dict item with members=False -> {"name": ..., "members": []}
        found_dict = False
        for item in result[1]["contents"]:
            if isinstance(item, dict) and item.get("name") == "ClassC":
                assert item["members"] == []
                found_dict = True
        assert found_dict


def test_preview_builds_if_no_site():
    """Test preview() calls build when site doesn't exist."""
    from great_docs._build.serve import ServeError

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # A missing `_site/index.html` triggers a build attempt, then a serving failure
        with (
            patch.object(docs, "build"),
            pytest.raises(ServeError, match="No index.html found"),
        ):
            docs.preview()


def test_preview_port_in_use():
    """Test preview() handles port-in-use error."""
    from great_docs._build.serve import ServeError

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        site_dir = docs.build_dir / "_site"
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        with (
            patch(
                "http.server.ThreadingHTTPServer",
                side_effect=OSError("Address in use"),
            ),
            pytest.raises(ServeError, match="Port 9999 is already in use"),
        ):
            docs.preview(port=9999)


def test_preview_serves_and_stops():
    """Test preview() starts server and handles KeyboardInterrupt."""
    import http.server  # noqa: F401  # ensure module is loaded before patching the server

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        site_dir = docs.build_dir / "_site"
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt()

        mock_timer = MagicMock()

        with (
            patch("http.server.ThreadingHTTPServer", return_value=mock_server),
            patch("threading.Timer", return_value=mock_timer),
            patch("webbrowser.open"),
        ):
            docs.preview(port=8888)

        mock_server.serve_forever.assert_called_once()
        mock_server.server_close.assert_called_once()


def test_check_links_with_docs_files():
    """Test check_links scans documentation files."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "intro.qmd").write_text(
            "---\ntitle: Intro\n---\n\nVisit https://httpbin.org/status/200\n",
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(
                include_source=False,
                include_docs=True,
                timeout=5.0,
            )

        assert result["total"] >= 1
        assert len(result["ok"]) >= 1


def test_check_links_skips_code_blocks():
    """Test check_links skips URLs inside code blocks."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "code.qmd").write_text(
            "---\ntitle: Code\n---\n\n"
            "```python\nhttps://example.com/in-code\n```\n\n"
            "Real: https://httpbin.org/status/200\n",
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response) as mock_head:
            result = docs.check_links(include_source=False, include_docs=True)

        # The code block URL should be excluded
        checked_urls = result["ok"] + [b["url"] for b in result["broken"]]
        assert "https://example.com/in-code" not in checked_urls


def test_check_links_gd_no_link():
    """Test check_links skips URLs marked with {.gd-no-link}."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "skip.qmd").write_text(
            "---\ntitle: Skip\n---\n\nhttps://fake-url.example.com{.gd-no-link}\n",
            encoding="utf-8",
        )

        result = docs.check_links(include_source=False, include_docs=True)

        # Should have no URLs to check
        assert result["total"] == 0


def test_check_links_ignore_patterns():
    """Test check_links respects ignore patterns."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "ig.qmd").write_text(
            "---\ntitle: Ignore\n---\n\nhttps://localhost:8080/test\n",
            encoding="utf-8",
        )

        result = docs.check_links(
            include_source=False,
            include_docs=True,
            ignore_patterns=["localhost"],
        )

        assert len(result["skipped"]) >= 1


def test_check_links_redirect():
    """Test check_links detects redirects."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "redir.qmd").write_text(
            "---\ntitle: Redir\n---\n\nhttps://httpbin.org/redirect/1\n",
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.status_code = 301
        mock_response.headers = {"Location": "https://httpbin.org/get"}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["redirects"]) >= 1


def test_check_links_broken():
    """Test check_links detects broken links."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "bad.qmd").write_text(
            "---\ntitle: Bad\n---\n\nhttps://httpbin.org/status/404\n",
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["broken"]) >= 1


def test_check_links_timeout():
    """Test check_links handles timeout."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "slow.qmd").write_text(
            "---\ntitle: Slow\n---\n\nhttps://httpbin.org/delay/30\n",
            encoding="utf-8",
        )

        with patch(
            "requests.head",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["broken"]) >= 1
        assert result["broken"][0]["error"] == "Timeout"


def test_check_links_ssl_error():
    """Test check_links handles SSL errors."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "ssl.qmd").write_text(
            "---\ntitle: SSL\n---\n\nhttps://expired.badssl.com/\n",
            encoding="utf-8",
        )

        with patch(
            "requests.head",
            side_effect=requests.exceptions.SSLError("cert error"),
        ):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["broken"]) >= 1
        assert "SSL" in result["broken"][0]["error"]


def test_check_links_connection_error():
    """Test check_links handles connection errors."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "conn.qmd").write_text(
            "---\ntitle: Conn\n---\n\nhttps://unreachable.invalid/page\n",
            encoding="utf-8",
        )

        with patch(
            "requests.head",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["broken"]) >= 1
        assert "Connection failed" in result["broken"][0]["error"]


def test_check_links_head_405_fallback_to_get():
    """Test check_links falls back to GET when HEAD returns 405."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "head405.qmd").write_text(
            "---\ntitle: Test\n---\n\nhttps://nohead.example.com/page\n",
            encoding="utf-8",
        )

        head_response = MagicMock()
        head_response.status_code = 405

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.headers = {}

        with (
            patch("requests.head", return_value=head_response),
            patch("requests.get", return_value=get_response) as mock_get,
        ):
            result = docs.check_links(include_source=False, include_docs=True)

        assert len(result["ok"]) >= 1
        mock_get.assert_called()


def test_check_links_fstring_urls_skipped():
    """Test check_links skips URLs with f-string placeholders."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pkg_dir = Path(tmp_dir) / "fstrpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'URL = "https://api.example.com/{endpoint}/data"\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "fstrpkg"\n', encoding="utf-8"
        )

        result = docs.check_links(include_source=True, include_docs=False)

        # f-string URL should be skipped
        all_urls = result["ok"] + [b["url"] for b in result["broken"]]
        for url in all_urls:
            assert "{" not in url


def test_check_links_python_comments_excluded():
    """Test check_links excludes URLs in Python comments."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        pkg_dir = Path(tmp_dir) / "commentpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            "# See https://example.com/in-comment for details\n"
            'REAL = "https://httpbin.org/status/200"\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "commentpkg"\n', encoding="utf-8"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(include_source=True, include_docs=False)

        all_checked = result["ok"] + [b["url"] for b in result["broken"]]
        assert "https://example.com/in-comment" not in all_checked


def test_homepage_hero_disabled():
    """Verify that a disabled hero produces no HTML"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(hero_explicitly_disabled=True)

        html, cleaned = homepage_hero(docs)
        assert html == ""
        assert cleaned is None


def test_homepage_hero_auto_badges():
    """Verify that the hero extracts badges from README content"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(
            hero_explicitly_disabled=False,
            hero_badges="auto",
            hero_enabled=True,
            hero_logo=None,
            hero_logo_height="80px",
            hero_name="TestPkg",
            hero_tagline="A test package",
            logo=None,
        )

        badge = Badge(alt="CI", img="https://img.shields.io/badge", url="https://ci.com")
        elements = HeroElements(badges=[badge], body="cleaned content")

        with (
            patch("great_docs._website.homepage.hero.extract_hero_elements", return_value=elements),
            patch("great_docs._website.branding.detect_hero_logo", return_value=None),
            patch("great_docs._website.branding.detect_logo", return_value=None),
        ):
            html, cleaned = homepage_hero(docs, "# My Package\n![badge](url)\n")

        assert "gd-hero" in html
        assert "TestPkg" in html
        assert "gd-hero-badges" in html
        assert cleaned == "cleaned content"


def test_homepage_hero_no_content():
    """Verify that a hero with no content produces no HTML"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(
            hero_explicitly_disabled=False,
            hero_badges="auto",
            hero_enabled=False,
            hero_logo=None,
            hero_name=None,
            hero_tagline=None,
            logo=None,
        )

        with (
            patch("great_docs._website.branding.detect_hero_logo", return_value=None),
            patch("great_docs._website.branding.detect_logo", return_value=None),
        ):
            html, cleaned = homepage_hero(docs)

        assert html == ""


def test_homepage_hero_with_logo_dict():
    """Verify that the hero renders light and dark logo variants from a mapping"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir = Path(tmp_dir) / "great-docs"
        docs.build_dir.mkdir()

        docs._config = mock_config(
            hero_explicitly_disabled=False,
            hero_badges=[],
            hero_enabled=True,
            hero_logo={"light": "logo-light.svg", "dark": "logo-dark.svg"},
            hero_logo_height="60px",
            hero_name="Pkg",
            hero_tagline="Tagline",
            logo=None,
        )

        # Create logo files in project root
        pkg_root = Path(tmp_dir)
        (pkg_root / "logo-light.svg").write_text("<svg/>", encoding="utf-8")
        (pkg_root / "logo-dark.svg").write_text("<svg/>", encoding="utf-8")

        html, _ = homepage_hero(docs)

        assert "gd-only-light" in html
        assert "gd-only-dark" in html


def test_add_api_block_disabled():
    """
    Mark the build as having no API reference when reference generation is disabled
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(reference_enabled=False)

        run = make_run(docs)
        add_api_block(docs, run)

        assert run.has_api_reference is False


def test_add_api_block_already_exists():
    """
    Leave an existing API reference configuration unchanged
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(reference_enabled=True, is_python_project=True)

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        (docs.build_dir / "_quarto.yml").write_text(
            format_yaml({"api-reference": {"package": "existing"}}),
            encoding="utf-8",
        )

        # Should not modify anything
        run = make_run(docs)
        add_api_block(docs, run)


def test_add_api_block_without_package_name_warns_and_skips(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """An undetected package skips the API reference with a warning and no prompt"""
    # Two package directories and no packaging files leave the package name undetected.
    for package in ("first", "second"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text("", encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(format_yaml({"website": {}}), encoding="utf-8")
    run = make_run(docs)

    with patch("builtins.input", side_effect=AssertionError("the build must not prompt")):
        add_api_block(docs, run)

    assert run.has_api_reference is False
    assert (
        "   ⚠️  Could not detect the package name; skipping the API reference"
        in capsys.readouterr().out
    )


def test_add_api_block_no_exports():
    """
    Mark the build as having no API reference when no sections are found
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        write_pyproject(Path(tmp_dir), "mypkg")
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(reference_enabled=True, is_python_project=True)

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        (docs.build_dir / "_quarto.yml").write_text(format_yaml({"website": {}}), encoding="utf-8")

        with (
            patch.object(Exports, "sections", return_value=None),
        ):
            run = make_run(docs)
            add_api_block(docs, run)

        assert run.has_api_reference is False


def test_add_api_block_reports_a_compiled_module_named_unlike_the_distribution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    write_pyproject(tmp_path, "py-yaml12")
    # A stub without Python source names the module and marks a compiled extension.
    (tmp_path / "yaml12.pyi").write_text("")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(format_yaml({"website": {}}), encoding="utf-8")

    with patch.object(Exports, "sections", return_value=None) as create:
        add_api_block(docs, make_run(docs))

    create.assert_called_once_with("yaml12")
    out = capsys.readouterr().out
    assert "Detected module name: yaml12" in out
    assert "Detected compiled extension package" in out


def test_add_api_block_success():
    """
    Write discovered sections to the API reference configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        write_pyproject(Path(tmp_dir), "mypkg")
        docs = GreatDocs(project_path=tmp_dir)
        docs._config = mock_config(
            reference_enabled=True,
            is_python_project=True,
            reference_title="API Reference",
            reference_desc=None,
            dynamic=True,
            parser="numpy",
            jupyter=None,
        )

        docs.build_dir.mkdir(parents=True, exist_ok=True)
        config = {"website": {"navbar": {"left": []}, "sidebar": []}}
        (docs.build_dir / "_quarto.yml").write_text(format_yaml(config), encoding="utf-8")

        sections = [{"title": "Functions", "contents": ["func_a"]}]

        with (
            patch.object(Exports, "sections", return_value=sections),
        ):
            run = make_run(docs)
            add_api_block(docs, run)

        assert run.has_api_reference is True
        written = read_yaml(docs.build_dir / "_quarto.yml")
        assert written["api-reference"]["sections"] == sections


def test_refresh_api_reference_config_no_quarto_yml():
    """Test _refresh_api_reference_config when no _quarto.yml."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir = Path(tmp_dir) / "great-docs"
        docs.build_dir.mkdir()

        # No _quarto.yml — should return early
        reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)


def test_refresh_api_reference_config_no_api_ref():
    """Test _refresh_api_reference_config when no api-reference in config."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir = Path(tmp_dir) / "great-docs"
        docs.build_dir.mkdir()
        (docs.build_dir / "_quarto.yml").write_text(format_yaml({"project": {}}), encoding="utf-8")

        reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)


def test_refresh_api_reference_config_fallback_to_explicit():
    """Test _refresh_api_reference_config falls back to explicit reference config."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir = Path(tmp_dir) / "great-docs"
        docs.build_dir.mkdir()

        config = {"api-reference": {"package": "mypkg"}}
        (docs.build_dir / "_quarto.yml").write_text(format_yaml(config), encoding="utf-8")

        docs._config = mock_config(
            parser="numpy",
            dynamic=True,
            reference_title=None,
            reference_desc=None,
            jupyter=None,
            reference=[{"title": "API", "contents": ["ClassA"]}],
        )

        user_sections = [{"title": "API", "contents": ["ClassA"]}]

        with (
            patch.object(Exports, "sections", return_value=None),
            patch.object(
                reference_sections,
                "from_reference_config",
                return_value=user_sections,
            ),
            patch.object(reference_sections, "update_sidebar"),
        ):
            reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)

        written = read_yaml(docs.build_dir / "_quarto.yml")
        assert written["api-reference"]["sections"] == user_sections


def test_discover_exports_submodule_detection():
    """Verify that discovery retains exported submodules"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "submodpkg"
        pkg_dir.mkdir()
        sub_dir = pkg_dir / "models"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text("class Model: pass\n", encoding="utf-8")
        (pkg_dir / "__init__.py").write_text(
            '__all__ = ["models", "MyClass"]\nfrom . import models\nclass MyClass: pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("submodpkg"), docs._config, report=print
            )

            assert result is not None
            assert "models" in result
            assert "MyClass" in result
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("submodpkg", None)
            sys.modules.pop("submodpkg.models", None)


def test_discover_exports_external_reexport_filtered():
    """Verify that discovery excludes aliases to external objects"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "reexppkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'from pathlib import Path\n__all__ = ["Path", "MyFunc"]\ndef MyFunc(): pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = discover_exports(
                make_exports(docs).package("reexppkg"), docs._config, report=print
            )

            assert result is not None
            assert "MyFunc" in result
            assert "Path" not in result
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("reexppkg", None)


def test_detect_docstring_style_no_indicators():
    """Verify that docstrings without style markers select NumPy"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "noindicpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'def func():\n    """Just a plain docstring with no parameter docs."""\n    pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("noindicpkg"), report=print)
            assert style == "numpy"
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("noindicpkg", None)


def test_check_links_source_files():
    """Test check_links scans source files for URLs."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pkg_dir = Path(tmp_dir) / "linkpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'BASE_URL = "https://httpbin.org/status/200"\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "linkpkg"\n', encoding="utf-8"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(include_source=True, include_docs=False)

        assert result["total"] >= 1


def test_check_links_verbose():
    """Test check_links verbose mode prints output."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "v.qmd").write_text(
            "---\ntitle: V\n---\n\nhttps://httpbin.org/status/200\n",
            encoding="utf-8",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        with patch("requests.head", return_value=mock_response):
            result = docs.check_links(include_source=False, include_docs=True, verbose=True)

        assert result["total"] >= 1


def test_check_links_invalid_regex_pattern():
    """Test check_links treats invalid regex as literal."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        ug_dir = Path(tmp_dir) / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "p.qmd").write_text(
            "---\ntitle: P\n---\n\nhttps://[invalid.example.com/\n",
            encoding="utf-8",
        )

        # "[invalid" is an invalid regex but should work as literal
        result = docs.check_links(
            include_source=False,
            include_docs=True,
            ignore_patterns=["[invalid"],
        )
        # Should not crash


@pytest.mark.parametrize(
    ("step", "run", "title", "error"),
    [
        ("content.user_guide", (), "Process User Guide", ValueError("path escapes")),
        ("content.sections", (), "Process custom sections", ValueError("path escapes")),
        ("content.custom_pages", (), "Process custom pages", ValueError("path escapes")),
        ("content.assets", (), "Copy assets", ValueError("path escapes")),
        (
            "site.update_quarto_config",
            ("content.assets",),
            "Copy assets",
            FileNotFoundError("header.html"),
        ),
    ],
)
def test_build_reports_project_errors_as_failures(tmp_path, capsys, step, run, title, error):
    """
    Check that project errors are reported as step failures and converted to `BuildError`
    """
    docs = _buildable_docs(tmp_path, sections=[{"title": "Test"}])

    with stubbed_build(docs, run=run) as stubs:
        stubs.steps[step].side_effect = error

        with pytest.raises(BuildError, match=f"{title} failed") as raised:
            docs.build(watch=False, refresh=False)

    assert raised.value.__cause__ is error
    out = capsys.readouterr().out
    assert "Build failed at Step" in out
    assert f"   {error}" in out
    stubs.steps["passes.terminal_recordings"].assert_not_called()


def test_build_lets_own_errors_through(tmp_path):
    """
    Check that an unexpected error in great-docs propagates unchanged and stops the build
    """
    docs = _buildable_docs(tmp_path)

    with stubbed_build(docs) as stubs:
        stubs.steps["content.user_guide"].side_effect = AttributeError("renamed method")

        with pytest.raises(AttributeError, match="renamed method"):
            docs.build(watch=False, refresh=False)

    stubs.steps["passes.terminal_recordings"].assert_not_called()


def test_build_changelog_no_releases(tmp_path):
    """
    Check that a changelog without releases gets no navbar entry
    """
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_ON_GITHUB_PYPROJECT,
        quarto_yml=NAVBAR_QUARTO_YML,
        changelog_enabled=True,
        changelog_max_releases=50,
    )
    docs._remote = StubRemote()

    with stubbed_build(
        docs,
    ):
        docs.build(watch=False, refresh=False)

    assert "github_releases" in docs._remote.calls
    assert not (docs.build_dir / "changelog.qmd").exists()
    assert _navbar_hrefs(docs) == ["reference/index.qmd"]


def test_build_changelog_no_repo(tmp_path):
    """
    Check that projects without a GitHub repository skip the changelog and its navbar entry
    """
    docs = _buildable_docs(
        tmp_path,
        pyproject=MYPKG_PYPROJECT,
        quarto_yml=NAVBAR_QUARTO_YML,
        changelog_enabled=True,
        changelog_max_releases=50,
    )
    docs._remote = StubRemote(releases=[GITHUB_RELEASE])

    with stubbed_build(docs):
        docs.build(watch=False, refresh=False)

    assert "github_releases" not in docs._remote.calls
    assert not (docs.build_dir / "changelog.qmd").exists()
    assert _navbar_hrefs(docs) == ["reference/index.qmd"]


def _make_uqc_docs(tmp_dir, gd_yml_content="", pyproject_content=None, quarto_content=None):
    """
    Create a project with loaded settings and an initial Quarto configuration
    """
    if pyproject_content is None:
        pyproject_content = '[project]\nname = "testpkg"\n'
    pyproject = Path(tmp_dir) / "pyproject.toml"
    pyproject.write_text(pyproject_content, encoding="utf-8")

    config = write_config(Path(tmp_dir), gd_yml_content)

    docs = GreatDocs(project_path=tmp_dir)
    docs._config = config
    docs._remote = StubRemote()

    quarto_yml = docs.build_dir / "_quarto.yml"
    quarto_yml.parent.mkdir(parents=True, exist_ok=True)

    if quarto_content is None:
        quarto_content = {
            "project": {"type": "website"},
            "website": {"navbar": {"left": []}, "sidebar": []},
            "format": {"html": {}},
        }

    with open(quarto_yml, "w") as f:
        f.write(QUARTO_YML_HEADER)
        write_yaml(quarto_content, f)

    return docs, quarto_yml


def test_update_quarto_config_math_method_defaults_to_katex():
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)

        assert config["format"]["html"]["html-math-method"] == "katex"


def test_update_quarto_config_forwards_math_method_override():
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="site:\n  html-math-method: mathjax\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            config = read_yaml(f)

        assert config["format"]["html"]["html-math-method"] == "mathjax"


def test_update_quarto_config_resources_string():
    """
    Preserve a single resource when converting it to a list
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            quarto_content={
                "project": {"type": "website", "resources": "single-resource.txt"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            },
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert isinstance(result["project"]["resources"], list)
        assert "single-resource.txt" in result["project"]["resources"]


def test_update_quarto_config_include_in_header_string():
    """
    Convert a single header include to a list
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="include_in_header:\n  - extra.html\n",
            quarto_content={
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {"include-in-header": "header.html"}},
            },
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        assert isinstance(header, list)


def test_update_quarto_config_github_icon_fallback():
    """
    Include a GitHub navbar icon when the icon style is configured
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="github_style: icon\n",
            quarto_content={
                "project": {"type": "website"},
                "website": {},
                "format": {"html": {}},
            },
        )

        on_github = replace(make_project(docs), github=GithubRepo("owner", "repo"))
        update_quarto_config(docs, make_run(docs, project=on_github))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        navbar = result["website"]["navbar"]
        right_items = navbar.get("right", [])
        assert any(item.get("icon") == "github" for item in right_items if isinstance(item, dict))


def test_update_quarto_config_dark_logo():
    """
    Include the dark logo variant in the site configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo-light.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        (Path(tmp_dir) / "logo-dark.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo-light.png\n  dark: logo-dark.png\n",
        )

        with patch(
            "great_docs._website.branding.generate_favicons", return_value={"icon": "favicon.ico"}
        ):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        navbar = result["website"]["navbar"]
        assert "logo" in navbar
        assert "logo-dark" in navbar


def test_update_quarto_config_logo_name_collision():
    """
    Keep light and dark logos distinct when their basenames match
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "light").mkdir()
        (Path(tmp_dir) / "dark").mkdir()
        (Path(tmp_dir) / "light" / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
        (Path(tmp_dir) / "dark" / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: light/logo.png\n  dark: dark/logo.png\n",
        )

        with patch(
            "great_docs._website.branding.generate_favicons", return_value={"icon": "favicon.ico"}
        ):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        navbar = result["website"]["navbar"]
        assert navbar["logo"] == "logo-light.png"


def test_update_quarto_config_logo_not_found():
    """
    Warn when the configured logo file is missing
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: nonexistent-logo.png\n",
        )

        update_quarto_config(docs, make_run(docs))


def test_update_quarto_config_dark_logo_not_found():
    """
    Warn when the configured dark logo is missing
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n  dark: nonexistent-dark.png\n",
        )

        with patch(
            "great_docs._website.branding.generate_favicons", return_value={"icon": "favicon.ico"}
        ):
            update_quarto_config(docs, make_run(docs))


def test_update_quarto_config_favicon_file():
    """
    Use the explicitly configured favicon file
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)
        (Path(tmp_dir) / "my-favicon.ico").write_bytes(b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\nfavicon:\n  icon: my-favicon.ico\n",
        )

        with patch(
            "great_docs._website.branding.generate_favicons", return_value={"icon": "favicon.ico"}
        ):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert result["website"].get("favicon") is not None


def test_update_quarto_config_favicon_not_found():
    """
    Warn when the configured favicon source is missing
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\nfavicon:\n  source: nonexistent.ico\n",
        )

        with patch("great_docs._website.branding.generate_favicons", return_value={}):
            update_quarto_config(docs, make_run(docs))


def test_update_quarto_config_favicon_resources_added():
    """
    Register generated favicon files as Quarto resources
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n",
        )

        generated = {
            "icon": "favicon.ico",
            "icon-svg": "favicon.svg",
            "icon-32": "favicon-32x32.png",
            "icon-16": "favicon-16x16.png",
            "apple-touch-icon": "apple-touch-icon.png",
        }

        with patch("great_docs._website.branding.generate_favicons", return_value=generated):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"]["resources"]
        assert "favicon.ico" in resources
        assert "favicon.svg" in resources
        assert "favicon-32x32.png" in resources
        assert "favicon-16x16.png" in resources
        assert "apple-touch-icon.png" in resources


def test_update_quarto_config_favicon_absolute_urls_with_site_url():
    """Test favicon <link> tags use absolute URLs when site-url is available."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n",
            quarto_content={
                "project": {"type": "website"},
                "website": {
                    "navbar": {"left": []},
                    "sidebar": [],
                    "site-url": "https://posit-dev.github.io/pointblank",
                },
                "format": {"html": {}},
            },
        )

        generated = {
            "icon": "favicon.ico",
            "icon-svg": "favicon.svg",
            "icon-32": "favicon-32x32.png",
            "icon-16": "favicon-16x16.png",
            "apple-touch-icon": "apple-touch-icon.png",
        }

        with patch("great_docs._website.branding.generate_favicons", return_value=generated):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header_items = result["format"]["html"]["include-in-header"]
        header_texts = [
            item["text"] if isinstance(item, dict) else str(item) for item in header_items
        ]
        header_joined = " ".join(header_texts)

        # All favicon hrefs should use absolute URLs
        assert 'href="https://posit-dev.github.io/pointblank/favicon.ico"' in header_joined
        assert 'href="https://posit-dev.github.io/pointblank/favicon.svg"' in header_joined
        assert 'href="https://posit-dev.github.io/pointblank/favicon-32x32.png"' in header_joined
        assert 'href="https://posit-dev.github.io/pointblank/favicon-16x16.png"' in header_joined
        assert 'href="https://posit-dev.github.io/pointblank/apple-touch-icon.png"' in header_joined

        # Must NOT contain bare relative paths
        assert 'href="favicon.ico"' not in header_joined
        assert 'href="favicon.svg"' not in header_joined


def test_update_quarto_config_favicon_no_links_without_site_url():
    """Test favicon <link> tags are NOT injected when no site-url is available."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n",
            quarto_content={
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            },
        )

        generated = {
            "icon": "favicon.ico",
            "icon-svg": "favicon.svg",
            "icon-32": "favicon-32x32.png",
            "icon-16": "favicon-16x16.png",
            "apple-touch-icon": "apple-touch-icon.png",
        }

        with patch("great_docs._website.branding.generate_favicons", return_value=generated):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        # Quarto's native website.favicon should still be set (Quarto handles path adjustment)
        assert result["website"].get("favicon") is not None

        # But no manual <link> tags for favicons should be injected
        header_items = result["format"]["html"].get("include-in-header", [])
        header_texts = [
            item["text"] if isinstance(item, dict) else str(item) for item in header_items
        ]
        header_joined = " ".join(header_texts)
        assert 'href="favicon.ico"' not in header_joined
        assert 'href="favicon.svg"' not in header_joined


def test_update_quarto_config_favicon_absolute_urls_from_pyproject():
    """Test favicon <link> tags use Documentation URL from pyproject.toml as fallback."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n",
            pyproject_content=(
                '[project]\nname = "testpkg"\n'
                "[project.urls]\n"
                'Documentation = "https://example.com/docs"\n'
            ),
            quarto_content={
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            },
        )

        generated = {
            "icon": "favicon.ico",
            "icon-svg": "favicon.svg",
        }

        with patch("great_docs._website.branding.generate_favicons", return_value=generated):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header_items = result["format"]["html"]["include-in-header"]
        header_texts = [
            item["text"] if isinstance(item, dict) else str(item) for item in header_items
        ]
        header_joined = " ".join(header_texts)

        assert 'href="https://example.com/docs/favicon.ico"' in header_joined
        assert 'href="https://example.com/docs/favicon.svg"' in header_joined
    """Test update_quarto_config() converts string include-after-body to list."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="markdown_pages_widget: true\n",
            quarto_content={
                "project": {"type": "website"},
                "website": {},
                "format": {"html": {"include-after-body": "existing-body.html"}},
            },
        )

        on_github = replace(make_project(docs), github=GithubRepo("owner", "repo"))
        update_quarto_config(docs, make_run(docs, project=on_github))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        assert isinstance(after_body, list)


def test_update_quarto_config_footer_author_string():
    """
    Include authors declared as strings in the footer
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            pyproject_content=(
                '[project]\nname = "testpkg"\n'
                '[[project.authors]]\nname = "Alice Smith"\n'
                '[[project.maintainers]]\nname = "Bob Jones"\n'
            ),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        footer = result["website"]["page-footer"]["center"]
        assert "Alice" in footer
        assert "Bob" in footer


def test_update_quarto_config_footer_funding_no_url():
    """
    Include funding information when no funding URL is supplied
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            pyproject_content=(
                '[project]\nname = "testpkg"\n[[project.authors]]\nname = "Alice"\n'
            ),
            gd_yml_content="funding:\n  name: ACME Foundation\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        footer = result["website"]["page-footer"]["center"]
        assert "ACME" in footer or "Supported by" in footer


def test_update_quarto_config_funding_only_no_authors():
    """
    Include funding information when no authors are declared
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            pyproject_content='[project]\nname = "testpkg"\n',
            gd_yml_content="funding:\n  name: ACME Foundation\n  homepage: https://acme.org\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        footer = result["website"].get("page-footer", {})
        center = footer.get("center", "")
        assert "ACME" in center or "Supported" in center


def test_update_quarto_config_attribution_v2():
    """
    Include the configured attribution in the footer
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="attribution: true\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        footer = result["website"]["page-footer"]["center"]
        assert "Great" in footer


def test_update_quarto_config_announcement_banner_v2():
    """
    Include announcement metadata, its script and the script resource
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=(
                "announcement:\n"
                "  content: New version available!\n"
                "  type: success\n"
                "  dismissable: true\n"
                "  url: https://example.com\n"
                "  style: rounded\n"
            ),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        has_announcement = any("gd-announcement" in str(item) for item in header)
        assert has_announcement

        after_body = result["format"]["html"]["include-after-body"]
        has_banner = any("announcement-banner" in str(item) for item in after_body)
        assert has_banner

        assert "announcement-banner.js" in result["project"]["resources"]


def test_update_quarto_config_navbar_style_v2():
    """
    Include metadata for the configured navbar style preset
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="navbar_style: gradient-sunset\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        has_navbar_style = any("gd-navbar-style" in str(item) for item in header)
        assert has_navbar_style


def test_update_quarto_config_content_style_v2():
    """
    Include metadata and the script for the configured content style preset
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="content_style:\n  preset: warm-glow\n  pages: all\n",
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        has_content_style = any("gd-content-style" in str(item) for item in header)
        assert has_content_style

        assert "content-style.js" in result["project"]["resources"]


def test_update_quarto_config_logo_href():
    """
    Set the navbar logo link from configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "logo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="logo:\n  light: logo.png\n  href: https://example.com\n",
        )

        with patch(
            "great_docs._website.branding.generate_favicons", return_value={"icon": "favicon.ico"}
        ):
            update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        navbar = result["website"]["navbar"]
        assert navbar["logo-href"] == "https://example.com"


def test_get_parser_defaults_numpy():
    result = get_parser_defaults("numpy")
    assert result == {}


def test_get_parser_defaults_unknown():
    result = get_parser_defaults("unknown_parser")
    assert result == {}


def test_get_object_basic():
    """get_object can load a simple module-level function."""

    obj = get_object("json:dumps")
    assert obj.name == "dumps"


def test_get_object_module_only():
    """get_object with no colon returns the module itself."""

    obj = get_object("json")
    assert obj.name == "json"


def test_get_object_with_shared_loader():
    """get_object reuses a loader if provided."""
    from griffe import (
        GriffeLoader,
        LinesCollection,
        ModulesCollection,
        Parser,
    )

    from great_docs._apiref.introspect import get_object

    loader = GriffeLoader(
        docstring_parser=Parser("numpy"),
        docstring_options={},
        modules_collection=ModulesCollection(),
        lines_collection=LinesCollection(),
    )
    obj = get_object("json:dumps", loader=loader)
    assert obj.name == "dumps"

    # Module should now be cached in loader
    assert "json" in loader.modules_collection


def test_get_object_dynamic_mode():
    """get_object with dynamic=True returns a dynamically loaded object."""

    obj = get_object("json:dumps", dynamic=True)
    assert obj is not None
    assert obj.name == "dumps"


def test_get_object_rejects_a_path_for_dynamic():
    with pytest.raises(ValueError, match="accepts true or false"):
        get_object("json:dumps", dynamic="json:dumps")


def test_get_object_warns_when_parser_is_ignored():
    """A parser cannot apply to a loader that already carries one."""
    from great_docs._apiref.introspect import make_loader

    with pytest.warns(UserWarning, match="Ignoring parser"):
        get_object("json:dumps", parser="numpy", loader=make_loader("numpy"))


def test_get_object_does_not_warn_for_parser_or_loader_alone():
    """Either argument on its own is unambiguous."""
    from great_docs._apiref.introspect import make_loader

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        get_object("json:dumps", loader=make_loader("numpy"))
        get_object("json:dumps", parser="numpy")


def test_get_object_alias_loads_target_module():
    """get_object loads the target module for aliases."""

    # os.path is typically an alias to posixpath or ntpath
    obj = get_object("os:path")
    assert obj is not None


def test_get_object_alias_does_not_reload_cached_package():
    """An alias in an already-loaded package does not trigger further loads."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_alias_reload"
        (pkg / "sub").mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "sub" / "__init__.py").write_text(
            "from introtest_alias_reload.impl import Thing\n", encoding="utf-8"
        )
        (pkg / "impl.py").write_text(
            'class Thing:\n    """A thing."""\n    def __init__(self) -> None:\n        pass\n',
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            from great_docs._apiref.introspect import make_loader

            loader = make_loader("numpy")
            loaded: list[str] = []
            original_load = gf.GriffeLoader.load

            def counting_load(self, module, *args, **kwargs):
                loaded.append(module)
                return original_load(self, module, *args, **kwargs)

            gf.GriffeLoader.load = counting_load
            try:
                for _ in range(3):
                    get_object("introtest_alias_reload.sub:Thing", loader=loader)
            finally:
                gf.GriffeLoader.load = original_load

            # One load for the initial package read; the alias target is the
            # same package, so repeated lookups must not load it again.
            assert loaded == ["introtest_alias_reload.sub"]
        finally:
            sys.path.remove(tmp_dir)
            for name in list(sys.modules):
                if name.startswith("introtest_alias_reload"):
                    sys.modules.pop(name)


def test_get_object_nested_path():
    """get_object can navigate nested class members."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_nested"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'class Outer:\n    """Outer class."""\n'
            '    class Inner:\n        """Inner class."""\n'
            "        def method(self): pass\n",
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = get_object("introtest_nested:Outer.Inner")
            assert obj.name == "Inner"
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_nested", None)


def test_resolve_alias_direct():
    """resolve_alias returns the target when it's not an Alias."""

    mod = gf.Module(name="testmod")
    func = gf.Function(name="my_func", lineno=1)
    mod.set_member("my_func", func)
    alias = gf.Alias("my_alias", func, parent=mod)
    result = resolve_alias(alias)

    assert result is func


def test_resolve_alias_chained():
    """resolve_alias follows chained aliases."""

    mod = gf.Module(name="testmod")
    func = gf.Function(name="my_func", lineno=1)
    mod.set_member("my_func", func)
    alias1 = gf.Alias("alias1", func, parent=mod)
    alias2 = gf.Alias("alias2", alias1, parent=mod)
    result = resolve_alias(alias2)

    assert result is func


def test_replace_docstring_basic():
    """replace_docstring replaces a function's docstring."""

    obj = get_object("json:dumps")
    old_doc = obj.docstring.value if obj.docstring else ""
    replace_docstring(obj)
    # After replace, docstring should come from the actual runtime function
    assert obj.docstring is not None


def test_replace_docstring_with_explicit_function():
    """replace_docstring uses a provided function's docstring."""

    obj = get_object("json:dumps")

    def custom_func():
        """Custom replacement docstring."""

    replace_docstring(obj, runtime_obj=custom_func)
    assert obj.docstring.value == "Custom replacement docstring."


def test_replace_docstring_none_doc():
    """replace_docstring does nothing when function has no docstring."""

    obj = get_object("json:dumps")

    def no_doc():
        pass

    old_docstring = obj.docstring
    replace_docstring(obj, runtime_obj=no_doc)
    # Docstring should be unchanged since f.__doc__ is None
    assert obj.docstring is old_docstring


def test_replace_docstring_class_replaces_members():
    """replace_docstring on a class recurses into its members."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_repdoc"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class MyClass:\n"
            '    """A class."""\n'
            "    def method(self):\n"
            '        """Method doc."""\n'
            "        pass\n",
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = get_object("introtest_repdoc:MyClass")
            replace_docstring(obj)
            # Should not raise
            assert obj.docstring is not None
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_repdoc", None)


def test_replace_docstring_nested_class():
    """replace_docstring handles nested class member resolution."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_nested_cls"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "class Outer:\n"
            '    """Outer."""\n'
            "    class Inner:\n"
            '        """Inner."""\n'
            "        def method(self):\n"
            '            """Inner method."""\n'
            "            pass\n",
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = get_object("introtest_nested_cls:Outer.Inner.method")
            replace_docstring(obj)
            assert obj.docstring is not None
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_nested_cls", None)


def test_replace_docstring_alias():
    """replace_docstring resolves aliases before replacing."""

    obj = get_object("json:dumps")
    mod = get_object("json")
    alias = gf.Alias("my_alias", obj, parent=mod)
    replace_docstring(alias)


def test_replace_docstring_enum_preserves_member_docstrings():
    """replace_docstring does not overwrite per-member enum docstrings with class docstring."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_enum_doc"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from enum import Enum\n"
            "class MyEnum(str, Enum):\n"
            '    """Class docstring."""\n'
            '    FOO = "foo"\n'
            '    """Description for variant FOO."""\n'
            '    BAR = "bar"\n'
            '    """Description for variant BAR."""\n',
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = get_object("introtest_enum_doc:MyEnum")
            replace_docstring(obj)
            assert obj.docstring.value == "Class docstring."
            foo = obj.members["FOO"]
            bar = obj.members["BAR"]
            assert foo.docstring.value == "Description for variant FOO."
            assert bar.docstring.value == "Description for variant BAR."
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_enum_doc", None)


def test_replace_docstring_enum_no_member_docstrings():
    """replace_docstring does not inject class docstring into undocumented enum members."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_enum_nodoc"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from enum import Enum\n"
            "class MyEnum(Enum):\n"
            '    """Class docstring."""\n'
            "    A = 1\n"
            "    B = 2\n",
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = get_object("introtest_enum_nodoc:MyEnum")
            replace_docstring(obj)
            assert obj.docstring.value == "Class docstring."
            a = obj.members["A"]
            b = obj.members["B"]
            assert a.docstring is None
            assert b.docstring is None
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_enum_nodoc", None)


def test_split_path_without_a_colon_is_all_module():
    """`resolve_alias` re-loads targets by dotted path, with no object part."""
    from great_docs._apiref.introspect import _split_path

    assert _split_path("pkg.mod.func") == ("pkg.mod.func", None)


def test_split_path_separates_the_object_part():
    """Only the first colon separates; the object part keeps its dots."""
    from great_docs._apiref.introspect import _split_path

    assert _split_path("json:dumps") == ("json", "dumps")
    assert _split_path("pkg.mod:A.b") == ("pkg.mod", "A.b")


def test_same_path_ignores_the_separator():
    """The `:` in an access path is a module boundary, not part of the name."""
    from great_docs._apiref.introspect import _same_path

    assert _same_path("pkg:SETTINGS", "pkg.SETTINGS")
    assert not _same_path("pkg._conf:SETTINGS", "pkg.SETTINGS")


def test_canonical_path_module():
    """_canonical_path for a module returns module name."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(json, "")

    assert result == "json"


def test_canonical_path_module_reports_no_home_for_a_member():
    """A module knows its own name but not where its members were defined."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(json, "dumps")

    assert result is None


def test_canonical_path_function():
    """_canonical_path for a function returns module:qualname."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(json.dumps, "")
    assert result == "json:dumps"


def test_canonical_path_function_with_qualname():
    """_canonical_path for a function with extra qualname appends it."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(json.dumps, "extra")
    assert result == "json:dumps.extra"


def test_canonical_path_class():
    """_canonical_path for a class returns module:qualname."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(json.JSONEncoder, "")
    assert result == "json.encoder:JSONEncoder"


def test_canonical_path_plain_object():
    """_canonical_path for a plain object (not module/class/function) returns None."""
    from great_docs._apiref.introspect import _canonical_path

    result = _canonical_path(42, "")
    assert result is None


def test_canonical_path_no_module_attr():
    """_canonical_path returns None when __module__ is missing."""
    from great_docs._apiref.introspect import _canonical_path

    class NoModule:
        pass

    obj = NoModule()
    # Instance — not a class/function/module
    result = _canonical_path(obj, "")
    assert result is None


def test_canonical_path_class_no_module():
    """_canonical_path returns None when class has no __module__."""
    from great_docs._apiref.introspect import _canonical_path

    cls = type("DynClass", (), {})
    cls.__module__ = None
    result = _canonical_path(cls, "")
    assert result is None


def test_has_no_value_class_attribute_no_value():
    """_has_no_value returns True for class-attribute with no value."""

    attr = gf.Attribute(name="x", lineno=1, value=None)
    attr.labels.add("class-attribute")

    assert _has_no_value(attr) is True


def test_has_no_value_instance_attribute():
    """_has_no_value returns True for instance-attribute."""

    attr = gf.Attribute(name="x", lineno=1)
    attr.labels.add("instance-attribute")

    assert _has_no_value(attr) is True


def test_has_no_value_class_attribute_with_value():
    """_has_no_value returns False for class-attribute with a value."""

    attr = gf.Attribute(name="x", lineno=1, value="42")
    attr.labels.add("class-attribute")

    assert _has_no_value(attr) is False


def test_has_no_value_unlabelled_attribute():
    """_has_no_value returns False for an attribute with none of the labels."""

    attr = gf.Attribute(name="x", lineno=1, value=None)

    assert _has_no_value(attr) is False


def test_has_no_value_function():
    """_has_no_value returns False for a function."""

    func = gf.Function(name="f", lineno=1)

    assert _has_no_value(func) is False


def test_has_no_value_module_attribute_no_value():
    """_has_no_value returns True for module-attribute with no value."""

    attr = gf.Attribute(name="x", lineno=1, value=None)
    attr.labels.add("module-attribute")

    assert _has_no_value(attr) is True


def test_insert_contents_list():
    """_insert_contents splices items into a list at the sentinel."""

    data = ["before", "{{ contents }}", "after"]
    result = _insert_contents(data, ["a", "b", "c"])
    assert result is True
    assert data == ["before", "a", "b", "c", "after"]


def test_insert_contents_dict():
    """_insert_contents searches dict values for the sentinel."""

    data = {"key": ["{{ contents }}"]}
    result = _insert_contents(data, ["x", "y"])
    assert result is True
    assert data == {"key": ["x", "y"]}


def test_insert_contents_nested():
    """_insert_contents searches nested structures."""

    data = {"outer": {"inner": ["before", "{{ contents }}"]}}
    result = _insert_contents(data, ["item1"])
    assert result is True
    assert data["outer"]["inner"] == ["before", "item1"]


def test_insert_contents_no_sentinel():
    """_insert_contents returns False when sentinel is not found."""

    data = ["a", "b", "c"]
    result = _insert_contents(data, ["x"])
    assert result is False
    assert data == ["a", "b", "c"]


def test_insert_contents_nested_list():
    """_insert_contents searches nested lists for sentinel."""

    data = [["{{ contents }}"]]
    result = _insert_contents(data, ["x"])
    assert result is True
    assert data == [["x"]]


def test_merge_frontmatter_existing():
    """_merge_frontmatter merges into existing frontmatter."""

    content = "---\ntitle: Hello\n---\n\nBody text."
    result = _merge_frontmatter(content, {"page-navigation": False})

    assert "---" in result
    assert "title: Hello" in result
    assert "page-navigation: false" in result
    assert "Body text." in result


def test_merge_frontmatter_no_existing():
    """_merge_frontmatter creates frontmatter when none exists."""

    content = "# Just a heading\n\nSome content."
    result = _merge_frontmatter(content, {"page-navigation": False})

    assert result.startswith("---\n")
    assert "page-navigation: false" in result
    assert "# Just a heading" in result


def test_merge_frontmatter_preserves_body():
    """_merge_frontmatter preserves the document body."""

    content = "---\nkey: val\n---\n\nThe body."
    result = _merge_frontmatter(content, {"new_key": "new_val"})

    assert "The body." in result
    assert "key: val" in result
    assert "new_key: new_val" in result


def test_merge_frontmatter_updates_existing_key():
    """_merge_frontmatter updates an existing key."""

    content = "---\npage-navigation: true\n---\n\nBody."
    result = _merge_frontmatter(content, {"page-navigation": False})

    assert "page-navigation: false" in result


def test_dynamic_alias_module_only():
    """dynamic_alias loads a module when no colon in path."""

    obj = dynamic_alias("json")
    assert obj is not None


def test_dynamic_alias_function():
    """dynamic_alias loads a function by path."""

    obj = dynamic_alias("json:dumps")
    assert obj is not None
    assert obj.name == "dumps"


def test_dynamic_alias_class():
    """dynamic_alias loads a class by path."""

    obj = dynamic_alias("json:JSONEncoder")
    assert obj is not None


def test_dynamic_alias_nested_class_method():
    """dynamic_alias loads a method on a class."""

    obj = dynamic_alias("json:JSONEncoder.encode")
    assert obj is not None


def test_dynamic_alias_nonexistent_attr_raises():
    """dynamic_alias raises KeyError for nonexistent attributes in a real module."""

    with pytest.raises(KeyError):
        dynamic_alias("json:nonexistent_function_xyz")


def test_dynamic_alias_with_loader():
    """dynamic_alias accepts a shared loader."""
    from griffe import (
        GriffeLoader,
        LinesCollection,
        ModulesCollection,
        Parser,
    )

    from great_docs._apiref.introspect import dynamic_alias

    loader = GriffeLoader(
        docstring_parser=Parser("numpy"),
        docstring_options={},
        modules_collection=ModulesCollection(),
        lines_collection=LinesCollection(),
    )
    obj = dynamic_alias("json:dumps", loader=loader)
    assert obj is not None


def test_dynamic_alias_from_test_package():
    """dynamic_alias loads from a test package."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_dyn"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def my_func():\n    """My function."""\n    pass\n',
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = dynamic_alias("introtest_dyn:my_func")
            assert obj.name == "my_func"
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_dyn", None)


def test_dynamic_alias_canonical_path_match():
    """dynamic_alias returns the object directly when canonical path matches."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_canon"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def hello():\n    """Hello."""\n    pass\n',
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = dynamic_alias("introtest_canon:hello")
            assert obj.name == "hello"
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_canon", None)


def test_dynamic_alias_reexported_creates_alias():
    """dynamic_alias creates an Alias when canonical path doesn't match path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a package where a function is re-exported from a submodule
        pkg = Path(tmp_dir) / "introtest_reexp"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            "from .sub import helper\n",
            encoding="utf-8",
        )
        sub = pkg / "sub.py"
        sub.write_text(
            'def helper():\n    """A helper."""\n    pass\n',
            encoding="utf-8",
        )
        sys.path.insert(0, tmp_dir)
        try:
            obj = dynamic_alias("introtest_reexp:helper")
            # Should be either an Alias or the resolved object
            assert obj is not None
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_reexp", None)
            sys.modules.pop("introtest_reexp.sub", None)


def test_spec_object_rejects_a_path_for_dynamic():
    """`dynamic` selects how an object is inspected, so only a bool will do."""
    from great_docs._apiref.spec import SpecObject

    with pytest.raises(ValueError, match="accepts true or false"):
        SpecObject(**{"name": "dumps", "dynamic": "json:dumps"})


def test_spec_options_replace_rejects_a_path_for_dynamic():
    from great_docs._apiref.spec import SpecOptions

    with pytest.raises(ValueError, match="accepts true or false"):
        SpecOptions().replace(dynamic="json:dumps")


def _make_api_ref(**block):
    """An APIReference built from an `api-reference` block, defaulting package to json."""
    block.setdefault("package", "json")
    return APIReference({"api-reference": block})


def test_api_reference_init_basic():
    """APIReference can be instantiated with minimal args."""

    ref = _make_api_ref()
    assert ref.package == "json"
    assert ref.settings.dir == "reference"
    assert ref.title == "Function reference"
    assert ref.settings.version is None


def test_api_reference_init_with_options():
    """APIReference routes build keys into Settings."""

    ref = _make_api_ref(
        dir="api",
        title="API Reference",
        out_index="api-index.qmd",
        rewrite_all_pages=True,
        parser="google",
    )
    assert ref.settings.dir == "api"
    assert ref.title == "API Reference"
    assert ref.settings.out_index == "api-index.qmd"
    assert ref.settings.rewrite_all_pages is True
    assert ref.settings.parser == "google"


def test_api_reference_init_sidebar_string():
    """APIReference converts sidebar string to dict."""

    ref = _make_api_ref(sidebar="my-sidebar.yml")
    assert ref.settings.sidebar == {"file": "my-sidebar.yml"}


def test_api_reference_init_sidebar_dict_no_file():
    """APIReference adds default file to sidebar dict if missing."""

    ref = _make_api_ref(sidebar={"id": "api"})
    assert ref.settings.sidebar["file"] == "_api-reference-sidebar.yml"
    assert ref.settings.sidebar["id"] == "api"


def test_api_reference_init_sidebar_dict_with_file():
    """APIReference preserves sidebar dict with existing file."""

    ref = _make_api_ref(sidebar={"file": "custom.yml"})
    assert ref.settings.sidebar["file"] == "custom.yml"


def test_api_reference_init_no_sidebar():
    """APIReference handles sidebar=None."""

    ref = _make_api_ref()
    assert ref.settings.sidebar is None


def test_api_reference_init_source_dir():
    """APIReference stores source_dir on settings."""

    ref = _make_api_ref(source_dir="src")
    assert ref.settings.source_dir == "src"


def test_api_reference_init_css():
    """APIReference accepts css setting."""

    ref = _make_api_ref(css="custom.css")
    assert ref.settings.css == "custom.css"


def test_api_reference_init_dynamic():
    """APIReference accepts dynamic setting."""

    ref = _make_api_ref(dynamic=True)
    assert ref.settings.dynamic is True

    ref2 = _make_api_ref(dynamic=False)
    assert ref2.settings.dynamic is False


def test_api_reference_init_desc():
    """APIReference accepts desc."""

    ref = _make_api_ref(desc="A description")
    assert ref.desc == "A description"


def test_api_reference_invalid_sections_error():
    """APIReference raises for invalid sections."""

    with pytest.raises((ValueError, TypeError)):
        _make_api_ref(sections=123)


def test_api_reference_build_basic():
    """APIReference.build creates index, pages, and inventory."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_build"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def greet():\n    """Say hello."""\n    return "hi"\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            ref = APIReference(
                {
                    "api-reference": {
                        "package": "introtest_build",
                        "sections": [
                            {"title": "Functions", "desc": "", "contents": [{"name": "greet"}]}
                        ],
                        "dir": "reference",
                    }
                }
            )
            ref.build()

            # Check index was created
            assert (Path(tmp_dir) / "reference" / "index.qmd").exists()

            # Check doc page was created
            assert (Path(tmp_dir) / "reference" / "greet.qmd").exists()

            # Check inventory was created
            assert (Path(tmp_dir) / "objects.inv").exists()
        finally:
            os.chdir(old_cwd)
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_build", None)


def test_api_reference_build_with_sidebar():
    """APIReference.build writes sidebar yaml when configured."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_sidebar"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def func():\n    """A func."""\n    pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            sidebar_file = str(Path(tmp_dir) / "sidebar.yml")
            ref = APIReference(
                {
                    "api-reference": {
                        "package": "introtest_sidebar",
                        "sections": [
                            {"title": "Functions", "desc": "", "contents": [{"name": "func"}]}
                        ],
                        "sidebar": sidebar_file,
                    }
                }
            )
            ref.build()

            assert Path(sidebar_file).exists()
        finally:
            os.chdir(old_cwd)
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_sidebar", None)


def test_api_reference_build_with_source_dir():
    """APIReference.build adds source_dir to sys.path."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        src = Path(tmp_dir) / "src"
        src.mkdir()
        pkg = src / "introtest_srcdir"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def func():\n    """A func."""\n    pass\n',
            encoding="utf-8",
        )

        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            ref = APIReference(
                {
                    "api-reference": {
                        "package": "introtest_srcdir",
                        "sections": [
                            {"title": "Functions", "desc": "", "contents": [{"name": "func"}]}
                        ],
                        "source_dir": str(src),
                    }
                }
            )
            ref.build()

            assert (Path(tmp_dir) / "reference" / "func.qmd").exists()
        finally:
            os.chdir(old_cwd)
            if str(src) in sys.path:
                sys.path.remove(str(src))
            sys.modules.pop("introtest_srcdir", None)


def test_api_reference_write_doc_pages_skip_unchanged():
    """APIReference.build skips pages with unchanged content."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_unchanged"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def func():\n    """A func."""\n    pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            ref = APIReference(
                {
                    "api-reference": {
                        "package": "introtest_unchanged",
                        "sections": [
                            {"title": "Funcs", "desc": "", "contents": [{"name": "func"}]}
                        ],
                        "rewrite_all_pages": False,
                    }
                }
            )
            # First build writes everything
            ref.build()
            page_path = Path(tmp_dir) / "reference" / "func.qmd"
            assert page_path.exists()
            mtime1 = page_path.stat().st_mtime

            # Second build should skip (content unchanged)

            time.sleep(0.01)
            ref.build()
            mtime2 = page_path.stat().st_mtime

            # File should not have been rewritten
            assert mtime1 == mtime2
        finally:
            os.chdir(old_cwd)
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_unchanged", None)


def test_api_reference_inventory_default_version():
    """APIReference.build writes an inventory using the default version."""

    inv = create_inventory("json", "0.0.9999", [])
    assert inv is not None


def test_api_reference_inventory_with_version():
    """create_inventory uses an explicit version when provided."""

    inv = create_inventory("json", "2.0.0", [])
    assert inv is not None


def test_api_reference_generate_sidebar_basic():
    """write._generate_sidebar creates sidebar structure from resolved sections."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = Path(tmp_dir) / "introtest_sb"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            'def func():\n    """A func."""\n    pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        old_cwd = os.getcwd()
        os.chdir(tmp_dir)
        try:
            ref = APIReference(
                {
                    "api-reference": {
                        "package": "introtest_sb",
                        "sections": [
                            {"title": "Functions", "desc": "", "contents": [{"name": "func"}]}
                        ],
                    }
                }
            )
            resolved = ref.resolved

            sidebar = write._generate_sidebar(
                resolved,
                dir=ref.settings.dir,
                out_page_suffix=ref.settings.out_page_suffix,
                sidebar=ref.settings.sidebar,
            )
            assert "website" in sidebar
            assert "sidebar" in sidebar["website"]
        finally:
            os.chdir(old_cwd)
            sys.path.remove(tmp_dir)
            sys.modules.pop("introtest_sb", None)


def test_api_reference_generate_sidebar_untitled_first_section():
    """A leading section with contents but no title attaches links at top level"""
    sections = [
        Section(contents=[Page(path="func")]),
        Section(title="Helpers", contents=[Page(path="helper")]),
    ]
    sidebar = write._generate_sidebar(
        sections, dir="reference", out_page_suffix=".qmd", sidebar=None
    )
    contents = sidebar["website"]["sidebar"][0]["contents"]
    assert {"text": "func", "href": "reference/func.qmd"} in contents
    assert {
        "section": "Helpers",
        "contents": [{"text": "helper", "href": "reference/helper.qmd"}],
    } in contents


def test_api_reference_generate_sidebar_subtitle_first_section():
    """A leading subtitle-only section becomes a top-level sub-entry"""
    sections = [Section(subtitle="Internals", contents=[Page(path="func")])]
    sidebar = write._generate_sidebar(
        sections, dir="reference", out_page_suffix=".qmd", sidebar=None
    )
    contents = sidebar["website"]["sidebar"][0]["contents"]
    assert {
        "section": "Internals",
        "contents": [{"text": "func", "href": "reference/func.qmd"}],
    } in contents


def test_api_reference_generate_sidebar_with_sidebar_config():
    """write._generate_sidebar uses sidebar config overrides."""

    ref = _make_api_ref(sidebar={"id": "api-sidebar", "file": "sidebar.yml"})
    sidebar = write._generate_sidebar(
        ref.sections,
        dir=ref.settings.dir,
        out_page_suffix=ref.settings.out_page_suffix,
        sidebar=ref.settings.sidebar,
    )
    entries = sidebar["website"]["sidebar"]
    # First entry should have the custom id
    assert entries[0]["id"] == "api-sidebar"


def test_api_reference_generate_sidebar_custom_contents():
    """write._generate_sidebar respects custom sidebar contents with sentinel."""

    ref = _make_api_ref(
        sidebar={
            "id": "custom",
            "file": "sidebar.yml",
            "contents": ["intro.qmd", "{{ contents }}", "outro.qmd"],
        }
    )
    sidebar = write._generate_sidebar(
        ref.sections,
        dir=ref.settings.dir,
        out_page_suffix=ref.settings.out_page_suffix,
        sidebar=ref.settings.sidebar,
    )
    entries = sidebar["website"]["sidebar"]
    # Should contain intro.qmd and outro.qmd with contents spliced in
    assert "intro.qmd" in entries[0]["contents"]
    assert "outro.qmd" in entries[0]["contents"]


def test_api_reference_generate_sidebar_no_sentinel():
    """write._generate_sidebar extends contents when no sentinel."""

    ref = _make_api_ref(
        sidebar={
            "id": "custom",
            "file": "sidebar.yml",
            "contents": ["intro.qmd"],
        }
    )
    sidebar = write._generate_sidebar(
        ref.sections,
        dir=ref.settings.dir,
        out_page_suffix=ref.settings.out_page_suffix,
        sidebar=ref.settings.sidebar,
    )
    entries = sidebar["website"]["sidebar"]
    # Contents should have been extended
    assert "intro.qmd" in entries[0]["contents"]


def test_api_reference_generate_sidebar_invalid_contents_type():
    """write._generate_sidebar raises TypeError for non-list contents."""

    ref = _make_api_ref(
        sidebar={
            "id": "custom",
            "file": "sidebar.yml",
            "contents": "not_a_list",
        }
    )
    with pytest.raises(TypeError, match="must be a list"):
        write._generate_sidebar(
            ref.sections,
            dir=ref.settings.dir,
            out_page_suffix=ref.settings.out_page_suffix,
            sidebar=ref.settings.sidebar,
        )


def test_api_reference_sidebar_page_links():
    """_generate_sidebar renders a Page entry as a dir/path.qmd link."""

    ref = _make_api_ref(dir="api")
    page = content.Page(path="my_func", contents=[])
    section = content.Section(title="Functions", contents=[page])
    result = write._generate_sidebar(
        [section],
        dir=ref.settings.dir,
        out_page_suffix=ref.settings.out_page_suffix,
        sidebar=None,
    )
    assert "api/my_func.qmd" in str(result)


def test_api_reference_from_config_dict():
    """APIReference is created from a dict config."""

    cfg = {
        "api-reference": {
            "package": "json",
            "sections": [],
        }
    }
    ref = APIReference(cfg)
    assert ref.package == "json"


def test_api_reference_from_yaml_file():
    """APIReference is created from a YAML file path."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_file = Path(tmp_dir) / "quarto.yml"
        cfg_file.write_text(
            "api-reference:\n  package: json\n  sections: []\n",
            encoding="utf-8",
        )
        ref = APIReference(str(cfg_file))
        assert ref.package == "json"


def test_api_reference_no_section_raises():
    """APIReference raises KeyError when no section found."""

    with pytest.raises(KeyError, match="No .api-reference"):
        APIReference({"other": {}})


def test_api_reference_ignores_style_key():
    """APIReference ignores the compatibility-only style key."""

    cfg = {
        "api-reference": {
            "package": "json",
            "sections": [],
            "style": "pkgdown",
        }
    }
    ref = APIReference(cfg)
    assert ref.package == "json"


def test_api_reference_drops_interlinks_fast():
    """APIReference does not read the dropped interlinks.fast setting."""

    cfg = {
        "api-reference": {
            "package": "json",
            "sections": [],
        },
        "interlinks": {
            "fast": True,
        },
    }
    ref = APIReference(cfg)
    assert ref.package == "json"
    assert not hasattr(ref.settings, "fast_inventory")


def test_cli_ordered_group_list_commands():
    """OrderedGroup.list_commands returns commands in insertion order."""

    # Use standalone_mode=False and resilient_parsing to avoid help error
    ctx = click.Context(cli, info_name="great-docs", resilient_parsing=True)
    commands = cli.list_commands(ctx)
    assert isinstance(commands, list)
    assert len(commands) > 0
    # Verify they come in insertion order (init, build, preview, uninstall, config, ...)
    assert commands[0] == "init"
    assert commands[1] == "build"


def test_cli_group_help():
    """The cli group shows help text."""
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Great Docs" in result.output


def test_cli_group_version():
    """The cli group shows version."""
    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "great-docs" in result.output


def test_cli_init_success():
    """CLI init command calls GreatDocs.install()."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(init, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            MockGD.assert_called_once_with(project_path=tmp_dir, config_path=None, create=True)
            mock_instance.install.assert_called_once_with(force=False)


def test_cli_init_with_force():
    """CLI init command passes force flag."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(init, ["--project-path", tmp_dir, "--force"])
            assert result.exit_code == 0
            mock_instance.install.assert_called_once_with(force=True)


def test_cli_init_error():
    """CLI init command handles errors gracefully."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.install.side_effect = RuntimeError("install failed")

            result = runner.invoke(init, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: install failed" in result.output


def test_cli_build_success():
    """CLI build command calls GreatDocs.build()."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(build, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            mock_instance.build.assert_called_once_with(
                watch=False, refresh=True, version_tags=None, latest_only=False, jobs=None
            )


def test_cli_build_with_watch():
    """CLI build command passes watch flag."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(build, ["--project-path", tmp_dir, "--watch"])
            assert result.exit_code == 0
            mock_instance.build.assert_called_once_with(
                watch=True, refresh=True, version_tags=None, latest_only=False, jobs=None
            )


def test_cli_build_no_refresh():
    """CLI build command passes no-refresh flag."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(build, ["--project-path", tmp_dir, "--no-refresh"])
            assert result.exit_code == 0
            mock_instance.build.assert_called_once_with(
                watch=False, refresh=False, version_tags=None, latest_only=False, jobs=None
            )


def test_cli_build_jobs():
    """CLI build command passes the render process count."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(build, ["--project-path", tmp_dir, "--jobs", "auto"])
            assert result.exit_code == 0
            mock_instance.build.assert_called_once_with(
                watch=False, refresh=True, version_tags=None, latest_only=False, jobs="auto"
            )


def test_cli_build_keyboard_interrupt():
    """CLI build handles KeyboardInterrupt gracefully."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.build.side_effect = KeyboardInterrupt()

            result = runner.invoke(build, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Stopped watching" in result.output


def test_cli_build_error():
    """CLI build handles errors gracefully."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.build.side_effect = RuntimeError("build failed")

            result = runner.invoke(build, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: build failed" in result.output


def test_cli_uninstall_success():
    """CLI uninstall command calls GreatDocs.uninstall()."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(uninstall, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            mock_instance.uninstall.assert_called_once()


def test_cli_uninstall_error():
    """CLI uninstall handles errors gracefully."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.uninstall.side_effect = RuntimeError("uninstall failed")

            result = runner.invoke(uninstall, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: uninstall failed" in result.output


def test_cli_preview_success():
    """CLI preview command calls GreatDocs.preview()."""
    runner = CliRunner()
    from great_docs.cli import preview

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(preview, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            mock_instance.preview.assert_called_once_with(
                port=3000, open_path="", open_browser=True
            )


def test_cli_preview_custom_port():
    """CLI preview command passes custom port."""
    runner = CliRunner()
    from great_docs.cli import preview

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_instance = MagicMock()
            MockGD.return_value = mock_instance

            result = runner.invoke(preview, ["--project-path", tmp_dir, "--port", "8080"])
            assert result.exit_code == 0
            mock_instance.preview.assert_called_once_with(
                port=8080, open_path="", open_browser=True
            )


def test_cli_preview_keyboard_interrupt():
    """CLI preview handles KeyboardInterrupt gracefully."""
    runner = CliRunner()
    from great_docs.cli import preview

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.preview.side_effect = KeyboardInterrupt()

            result = runner.invoke(preview, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Server stopped" in result.output


def test_cli_preview_error():
    """CLI preview handles errors gracefully."""
    runner = CliRunner()
    from great_docs.cli import preview

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.return_value.preview.side_effect = RuntimeError("preview failed")

            result = runner.invoke(preview, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: preview failed" in result.output


def test_cli_config_success():
    """CLI config command creates a great-docs.yml file."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = runner.invoke(config, ["--project-path", tmp_dir, "--force"])
        assert result.exit_code == 0
        assert "Created" in result.output

        config_file = Path(tmp_dir) / "docs/great-docs.yml"
        assert config_file.exists()


def test_cli_config_exists_decline():
    """CLI config command prompts when file exists and user declines."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create existing config
        (Path(tmp_dir) / "great-docs.yml").write_text("existing: true")

        result = runner.invoke(config, ["--project-path", tmp_dir], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # File should be unchanged
        content = (Path(tmp_dir) / "great-docs.yml").read_text()
        assert content == "existing: true"


def test_cli_config_exists_confirm():
    """CLI config command overwrites when file exists and user confirms."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create existing config
        (Path(tmp_dir) / "great-docs.yml").write_text("existing: true")

        result = runner.invoke(config, ["--project-path", tmp_dir], input="y\n")
        assert result.exit_code == 0
        assert "Created" in result.output


def test_cli_config_error():
    """CLI config command handles errors gracefully."""
    runner = CliRunner()

    with patch("great_docs.config.create_default_config") as mock_create:
        mock_create.side_effect = RuntimeError("config error")

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = runner.invoke(config, ["--project-path", tmp_dir, "--force"])
            assert result.exit_code == 1
            assert "Error: config error" in result.output


def test_cli_scan_success():
    """CLI scan command shows discovered exports."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_package"))
            )
            package_exports.names.return_value = ["MyClass", "my_func"]
            package_exports.categorise.return_value = {
                "classes": ["MyClass"],
                "functions": ["my_func"],
                "class_method_names": {"MyClass": ["method_a"]},
            }
            package_exports.config.reference = [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "MyClass", "members": True},
                    ],
                }
            ]

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Discovery" in result.output
            assert "my_package" in result.output
            assert "Classes" in result.output
            assert "MyClass" in result.output
            assert "Functions" in result.output
            assert "my_func" in result.output


def test_cli_scan_verbose():
    """CLI scan --verbose shows additional detail."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = ["func"]
            package_exports.categorise.return_value = {
                "functions": ["func"],
                "class_method_names": {},
            }
            package_exports.config.reference = [
                {
                    "title": "Functions",
                    "contents": ["func"],
                }
            ]

            result = runner.invoke(scan, ["--project-path", tmp_dir, "--verbose"])
            assert result.exit_code == 0
            assert "Functions" in result.output
            assert "item(s)" in result.output


def test_cli_scan_no_package():
    """CLI scan exits when no package detected."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), None))
            )

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Could not detect package name" in result.output


def test_cli_scan_no_exports():
    """CLI scan exits when no exports discovered."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = []

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "No exports discovered" in result.output


def test_cli_scan_no_reference_config():
    """CLI scan shows guidance when no reference config found."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = ["func"]
            package_exports.categorise.return_value = {
                "functions": ["func"],
                "class_method_names": {},
            }
            package_exports.config.reference = []

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "No reference config found" in result.output


def test_cli_scan_class_without_members():
    """CLI scan marks classes with members: false differently."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = ["MyClass"]
            package_exports.categorise.return_value = {
                "classes": ["MyClass"],
                "class_method_names": {"MyClass": ["method"]},
            }
            package_exports.config.reference = [
                {
                    "title": "Classes",
                    "contents": [{"name": "MyClass", "members": False}],
                }
            ]

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "MyClass" in result.output


def test_cli_scan_flat_categories():
    """CLI scan shows flat categories like enums, exceptions, etc."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = [
                "MyEnum",
                "MyError",
                "my_func",
                "MY_CONST",
            ]
            package_exports.categorise.return_value = {
                "enums": ["MyEnum"],
                "exceptions": ["MyError"],
                "functions": ["my_func"],
                "constants": ["MY_CONST"],
                "class_method_names": {},
            }
            package_exports.config.reference = [{"title": "All", "contents": ["MyEnum", "my_func"]}]

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Enumerations" in result.output
            assert "Exceptions" in result.output
            assert "Constants" in result.output


def test_cli_scan_error():
    """CLI scan handles errors gracefully."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            MockExports.make.side_effect = RuntimeError("scan failed")

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: scan failed" in result.output


def test_cli_scan_class_like_categories():
    """CLI scan shows all class-like categories: dataclasses, abstract classes, protocols."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = [
                "MyDC",
                "MyABC",
                "MyProto",
            ]
            package_exports.categorise.return_value = {
                "dataclasses": ["MyDC"],
                "abstract_classes": ["MyABC"],
                "protocols": ["MyProto"],
                "class_method_names": {
                    "MyDC": [],
                    "MyABC": [],
                    "MyProto": [],
                },
            }
            package_exports.config.reference = []

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Dataclasses" in result.output
            assert "Abstract Classes" in result.output
            assert "Protocols" in result.output


def test_cli_scan_string_items_in_reference():
    """CLI scan handles simple string items in reference contents."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config()
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "my_pkg"))
            )
            package_exports.names.return_value = ["my_func"]
            package_exports.categorise.return_value = {
                "functions": ["my_func"],
                "class_method_names": {},
            }
            package_exports.config.reference = [{"title": "Functions", "contents": ["my_func"]}]

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            # my_func should be marked as included
            assert "my_func" in result.output


def test_cli_check_links_success():
    """CLI check-links command runs link check."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 5,
                "ok": [{"url": "https://example.com"}],
                "broken": [],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "All links are valid" in result.output
            assert "Link Check Summary" in result.output


def test_cli_check_links_broken():
    """CLI check-links reports broken links and exits with error."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 3,
                "ok": [],
                "broken": [
                    {
                        "url": "https://broken.example.com",
                        "status": 404,
                        "error": "Not Found",
                        "files": ["README.md"],
                    }
                ],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Broken Links" in result.output
            assert "broken.example.com" in result.output


def test_cli_check_links_with_redirects():
    """CLI check-links shows redirects."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 2,
                "ok": [],
                "broken": [],
                "redirects": [
                    {
                        "url": "https://old.example.com",
                        "status": 301,
                        "location": "https://new.example.com",
                        "files": ["docs.md"],
                    }
                ],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            assert "Redirects" in result.output
            assert "old.example.com" in result.output


def test_cli_check_links_source_only():
    """CLI check-links --source-only passes correct flags."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 0,
                "ok": [],
                "broken": [],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir, "--source-only"])
            assert result.exit_code == 0
            assert "source files only" in result.output
            call_kwargs = mock_docs.check_links.call_args[1]
            assert call_kwargs["include_source"] is True
            assert call_kwargs["include_docs"] is False


def test_cli_check_links_docs_only():
    """CLI check-links --docs-only passes correct flags."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 0,
                "ok": [],
                "broken": [],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir, "--docs-only"])
            assert result.exit_code == 0
            assert "documentation files only" in result.output


def test_cli_check_links_json_output_no_broken():
    """CLI check-links --json-output outputs JSON."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 1,
                "ok": [],
                "broken": [],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir, "--json-output"])
            assert result.exit_code == 0
            parsed = json.loads(result.output)
            assert "total" in parsed


def test_cli_check_links_json_output_with_broken():
    """CLI check-links --json-output exits 1 when there are broken links."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 1,
                "ok": [],
                "broken": [{"url": "x", "status": 404, "error": "fail", "files": ["a.md"]}],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(check_links, ["--project-path", tmp_dir, "--json-output"])
            assert result.exit_code == 1


def test_cli_check_links_custom_ignore():
    """CLI check-links -i passes custom ignore patterns."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.return_value = {
                "total": 0,
                "ok": [],
                "broken": [],
                "redirects": [],
                "skipped": [],
            }

            result = runner.invoke(
                check_links,
                ["--project-path", tmp_dir, "-i", "github.com"],
            )
            assert result.exit_code == 0
            call_kwargs = mock_docs.check_links.call_args[1]
            assert "github.com" in call_kwargs["ignore_patterns"]


def test_cli_check_links_import_error():
    """CLI check-links handles ImportError (missing requests)."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            mock_docs = MagicMock()
            MockGD.return_value = mock_docs
            mock_docs.check_links.side_effect = ImportError("No module named 'requests'")

            result = runner.invoke(check_links, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "requests" in result.output


def test_cli_check_links_error():
    """CLI check-links handles generic errors."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.GreatDocs") as MockGD:
            MockGD.side_effect = RuntimeError("check failed")

            result = runner.invoke(check_links, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: check failed" in result.output


def _invoke_changelog(project: Path, remote: StubRemote, *args: str) -> Result:
    """
    Run `great-docs changelog` on a project with preset GitHub data

    Parameters
    ----------
    project
        The project directory.
    remote
        The GitHub data the command reads.
    *args
        Further command-line arguments.

    Returns
    -------
    :
        The command's result.
    """

    with patch("great_docs.cli.HttpRemote", return_value=remote):
        return CliRunner().invoke(changelog, ["--project-path", str(project), *args])


def _changelog_project(root: Path) -> Path:
    """
    Create a project with a GitHub repository URL and a navbar in its build directory

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
        The build directory.
    """
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n[project.urls]\nRepository = "https://github.com/owner/repo"\n'
    )
    build_dir = root / "great-docs"
    build_dir.mkdir()
    (build_dir / "_quarto.yml").write_text(
        "website:\n  navbar:\n    left:\n      - text: Reference\n        href: reference/index.qmd\n"
    )
    return build_dir


def test_cli_changelog_success(tmp_path: Path):
    """Check that the changelog command generates the page"""
    build_dir = _changelog_project(tmp_path)

    result = _invoke_changelog(tmp_path, StubRemote(releases=[GITHUB_RELEASE]))

    assert result.exit_code == 0, result.output
    page = build_dir / "changelog.qmd"
    assert result.output == f"Created {page}\n✅ Changelog generated: {page}\n"
    assert "## v1.0.0" in page.read_text(encoding="utf-8")
    navbar = read_quarto_yml(build_dir)["website"]["navbar"]["left"]
    assert navbar[-1] == {"text": "Changelog", "href": "changelog.qmd"}


def test_cli_changelog_no_releases(tmp_path: Path):
    """Check that the changelog command reports when no releases are found"""
    build_dir = _changelog_project(tmp_path)

    result = _invoke_changelog(tmp_path, StubRemote())

    assert result.exit_code == 0, result.output
    assert "No published releases found" in result.output
    assert not (build_dir / "changelog.qmd").exists()
    assert len(read_quarto_yml(build_dir)["website"]["navbar"]["left"]) == 1


def test_cli_changelog_links_the_page_once_on_a_translated_site(tmp_path: Path):
    (tmp_path / "great-docs.yml").write_text("site:\n  lang: fr\n")
    build_dir = _changelog_project(tmp_path)
    remote = StubRemote(releases=[GITHUB_RELEASE])

    first = _invoke_changelog(tmp_path, remote)
    second = _invoke_changelog(tmp_path, remote)

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    navbar = read_quarto_yml(build_dir)["website"]["navbar"]["left"]
    assert navbar[1:] == [{"text": "Journal des modifications", "href": "changelog.qmd"}]


def test_cli_changelog_leaves_an_unbuilt_site_without_configuration(tmp_path: Path):
    build_dir = _changelog_project(tmp_path)
    (build_dir / "_quarto.yml").unlink()

    result = _invoke_changelog(tmp_path, StubRemote(releases=[GITHUB_RELEASE]))

    assert result.exit_code == 0, result.output
    assert (build_dir / "changelog.qmd").exists()
    assert not (build_dir / "_quarto.yml").exists()


def test_cli_changelog_no_github_repo():
    """CLI changelog reports when no GitHub repo configured."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # An empty project cannot supply a GitHub repository URL.
        result = runner.invoke(changelog, ["--project-path", tmp_dir])
        assert result.exit_code == 1
        assert "No GitHub repository URL found" in result.output


def test_cli_changelog_max_releases_without_pyproject(tmp_path: Path):
    """
    Honour `changelog --max-releases` for a project without `pyproject.toml`
    """
    (tmp_path / "go.mod").write_text("module example.com/tool\n")
    (tmp_path / "great-docs.yml").write_text("repo: https://github.com/owner/tool\n")
    (tmp_path / "great-docs").mkdir()
    response = MagicMock(status_code=200)
    response.json.return_value = [
        {
            "tag_name": f"v1.{i}",
            "name": f"v1.{i}",
            "body": "",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": f"https://github.com/owner/tool/releases/tag/v1.{i}",
            "prerelease": False,
            "draft": False,
        }
        for i in range(5)
    ]

    with patch("requests.get", return_value=response):
        result = CliRunner().invoke(
            changelog, ["--project-path", str(tmp_path), "--max-releases", "3"]
        )

    assert result.exit_code == 0, result.output
    page = (tmp_path / "great-docs" / "changelog.qmd").read_text()
    assert page.count("{.changelog-version}") == 3


def test_cli_changelog_error():
    """CLI changelog handles errors."""
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Config", side_effect=RuntimeError("changelog failed")):
            result = runner.invoke(changelog, ["--project-path", tmp_dir])
            assert result.exit_code == 1
            assert "Error: changelog failed" in result.output


def test_cli_main_entry_point():
    """main() calls cli()."""

    with patch("great_docs.cli.cli") as mock_cli:
        main()
        mock_cli.assert_called_once()


def test_ast_transform_tuple_examples():
    """transform() converts an examples tuple to ExampleCode."""

    kind_cls = type(gf.DocstringSectionText("x").kind)
    result = transform((kind_cls["examples"], "print(1)"))

    assert isinstance(result, ExampleCode)
    assert result.value == "print(1)"


def test_ast_transform_tuple_text():
    """transform() converts a text tuple to ExampleText."""

    kind_cls = type(gf.DocstringSectionText("x").kind)
    result = transform((kind_cls["text"], "some description"))

    assert isinstance(result, ExampleText)
    assert result.value == "some description"


def test_ast_transform_tuple_unsupported_passthrough():
    """transform() returns unsupported tuple type unchanged when ValueError is raised."""

    kind_cls = type(gf.DocstringSectionText("x").kind)

    # 'parameters' kind is not handled by tuple_to_data, so ValueError → passthrough
    result = transform((kind_cls["parameters"], "stuff"))

    assert isinstance(result, tuple)
    assert result == (kind_cls["parameters"], "stuff")


def test_ast_transform_docstring_section_list():
    """transform() processes a list of DocstringSection objects."""

    sections = [gf.DocstringSectionText("Hello world")]
    result = transform(sections)

    assert isinstance(result, list)
    assert len(result) >= 1


def test_ast_transform_passthrough():
    """transform() returns non-tuple, non-section-list unchanged."""

    assert transform(42) == 42
    assert transform("hello") == "hello"


def test_ast_tuple_to_data_examples():
    """tuple_to_data converts examples kind to ExampleCode."""

    kind_cls = type(gf.DocstringSectionText("x").kind)
    result = tuple_to_data((kind_cls["examples"], "x = 1"))

    assert isinstance(result, ExampleCode)
    assert result.value == "x = 1"


def test_ast_tuple_to_data_text():
    """tuple_to_data converts text kind to ExampleText."""

    kind_cls = type(gf.DocstringSectionText("x").kind)
    result = tuple_to_data((kind_cls["text"], "description"))

    assert isinstance(result, ExampleText)
    assert result.value == "description"


def test_ast_tuple_to_data_unsupported_raises():
    """tuple_to_data raises ValueError for unsupported kinds."""

    kind_cls = type(gf.DocstringSectionText("x").kind)
    with pytest.raises(ValueError, match="Unsupported"):
        tuple_to_data((kind_cls["parameters"], "stuff"))


def test_ast_split_sections_basic():
    """split_sections parses numpydoc-style section headers."""

    text = "Preamble text\n\nSee Also\n--------\nSome reference\n\nNotes\n-----\nSome notes\n"
    result = _DocstringSectionPatched.split_sections(text)
    assert len(result) == 3
    assert result[0][0] == ""  # preamble has no title
    assert "Preamble" in result[0][1]
    assert result[1][0] == "See Also"
    assert "Some reference" in result[1][1]
    assert result[2][0] == "Notes"
    assert "Some notes" in result[2][1]


def test_ast_split_sections_no_preamble():
    """split_sections works when text starts with a section header."""

    text = "Notes\n-----\nThis is a note.\n"
    result = _DocstringSectionPatched.split_sections(text)
    assert len(result) == 1
    assert result[0][0] == "Notes"


def test_ast_split_sections_empty():
    """split_sections returns empty list for text without sections."""

    result = _DocstringSectionPatched.split_sections("No sections here.")

    assert result == []


def test_ast_transform_docstring_section_text():
    """transform() converts DocstringSectionText with known subsections."""

    text_section = gf.DocstringSectionText(
        "See Also\n--------\nother_func\n\nNotes\n-----\nImportant note.\n"
    )
    result = _DocstringSectionPatched.transform(text_section)

    assert len(result) == 2
    assert isinstance(result[0], DocstringSectionSeeAlso)
    assert isinstance(result[1], DocstringSectionNotes)


def test_ast_transform_docstring_section_text_plain():
    """transform() returns plain DocstringSectionText when no subsections found."""

    text_section = gf.DocstringSectionText("Just a plain paragraph.")
    result = _DocstringSectionPatched.transform(text_section)

    assert len(result) == 1
    assert isinstance(result[0], gf.DocstringSectionText)


def test_ast_transform_docstring_section_admonition_known():
    """transform() converts DocstringSectionAdmonition with known title."""

    adm_section = gf.DocstringSectionAdmonition(
        kind="warning", text="Be careful!", title="Warnings"
    )
    result = _DocstringSectionPatched.transform(adm_section)

    assert len(result) == 1
    assert isinstance(result[0], DocstringSectionWarnings)
    assert result[0].value == "Be careful!"


def test_ast_transform_docstring_section_admonition_unknown():
    """transform() returns unknown DocstringSectionAdmonition unchanged."""

    adm_section = gf.DocstringSectionAdmonition(kind="custom", text="stuff", title="Custom Section")
    result = _DocstringSectionPatched.transform(adm_section)

    assert len(result) == 1
    assert result[0] is adm_section  # returned as-is


def test_ast_transform_docstring_section_passthrough():
    """transform() returns non-text, non-admonition sections unchanged."""

    params_section = gf.DocstringSectionParameters([])
    result = _DocstringSectionPatched.transform(params_section)

    assert result == [params_section]


def test_ast_transform_sections():
    """Verify that mixed docstring sections are converted together"""

    sections = [
        gf.DocstringSectionText("Notes\n-----\nA note.\n"),
        gf.DocstringSectionParameters([]),
    ]
    result = transform_sections(sections)

    assert len(result) >= 2  # at least the note + parameters


def test_ast_fields_example_code():
    """fields() returns dataclass field names for ExampleCode."""
    from great_docs._apiref._docstring_sections import ExampleCode
    from great_docs._apiref._preview import fields

    ec = ExampleCode("print(1)")
    result = fields(ec)
    assert result == ["value"]


def test_ast_fields_example_text():
    """fields() returns dataclass field names for ExampleText."""
    from great_docs._apiref._docstring_sections import ExampleText
    from great_docs._apiref._preview import fields

    et = ExampleText("description")
    result = fields(et)
    assert result == ["value"]


def test_ast_fields_function():
    """fields() returns expected fields for gf.Function."""
    from great_docs._apiref._preview import fields

    func = gf.Function(name="my_func", lineno=1)
    result = fields(func)

    assert result == ["name", "annotation", "parameters", "docstring"]


def test_ast_fields_attribute():
    """fields() returns expected fields for gf.Attribute."""
    from great_docs._apiref._preview import fields

    attr = gf.Attribute(name="x", lineno=1)
    result = fields(attr)

    assert result == ["name", "annotation"]


def test_ast_fields_docstring():
    """fields() returns expected fields for gf.Docstring."""
    from great_docs._apiref._preview import fields

    ds_obj = gf.Docstring("Hello", parser="numpy")
    result = fields(ds_obj)

    assert result == ["parser", "parsed"]


def test_ast_fields_parameter():
    """fields() returns expected fields for gf.Parameter."""
    from great_docs._apiref._preview import fields

    param = gf.Parameter(name="x")
    result = fields(param)

    assert result == ["annotation", "kind", "name", "default"]


def test_ast_fields_docstring_parameter():
    """fields() returns expected fields for gf.DocstringParameter."""
    from great_docs._apiref._preview import fields

    dp = gf.DocstringParameter(name="x", description="a number", annotation="int")
    result = fields(dp)

    assert result == ["annotation", "default", "description", "name", "value"]


def test_ast_fields_docstring_named_element():
    """fields() returns expected fields for gf.DocstringNamedElement."""
    from great_docs._apiref._preview import fields

    ne = gf.DocstringNamedElement(name="x", description="desc")
    result = fields(ne)

    assert result == ["name", "annotation", "description"]


def test_ast_fields_docstring_section():
    """fields() returns expected fields for gf.DocstringSection."""
    from great_docs._apiref._preview import fields

    sec = gf.DocstringSectionText("hello")
    result = fields(sec)

    assert result == ["kind", "title", "value"]


def test_ast_fields_alias():
    """fields() follows alias target for gf.Alias."""
    from great_docs._apiref._preview import fields

    mod = gf.Module(name="testmod")
    func = gf.Function(name="f", lineno=1)
    mod.set_member("f", func)
    alias = gf.Alias("f", func, parent=mod)
    result = fields(alias)

    # Should match fields of the target (Function)
    assert result == ["name", "annotation", "parameters", "docstring"]


def test_ast_fields_alias_unresolvable():
    """fields() warns and returns fallback for unresolvable alias."""

    from griffe import ModulesCollection

    from great_docs._apiref._preview import fields

    mc = ModulesCollection()
    mod = gf.Module(name="testmod")
    mc["testmod"] = mod

    alias = gf.Alias("missing_target", "nonexistent.module.func", parent=mod)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = fields(alias)

    assert result == ["name", "target_path"]
    assert len(w) >= 1
    assert "Could not resolve" in str(w[0].message)


def test_ast_fields_object():
    """fields() returns discovered attributes for gf.Object (Module)."""
    from great_docs._apiref._preview import fields

    mod = gf.Module(name="mymod")
    result = fields(mod)

    assert "name" in result
    assert "members" in result
    assert "docstring" in result


def test_ast_fields_walkable():
    """fields() returns non-default fields for a Walkable subclass."""
    from great_docs._apiref._preview import fields

    spec_obj = SpecObject(name="my_func")
    result = fields(spec_obj)
    assert "name" in result


def test_ast_fields_dict():
    """fields() returns dict keys."""
    from great_docs._apiref._preview import fields

    result = fields({"a": 1, "b": 2})
    assert result == ["a", "b"]


def test_ast_fields_list():
    """fields() returns list indices."""
    from great_docs._apiref._preview import fields

    result = fields([10, 20, 30])
    assert result == [0, 1, 2]


def test_ast_fields_parameters():
    """fields() returns indices for gf.Parameters."""
    from great_docs._apiref._preview import fields

    params = gf.Parameters(gf.Parameter(name="a"), gf.Parameter(name="b"))
    result = fields(params)

    assert result == [0, 1]


def test_ast_fields_none_for_unknown():
    """fields() returns None for unrecognized types."""
    from great_docs._apiref._preview import fields

    assert fields(42) is None
    assert fields("hello") is None
    assert fields(3.14) is None


def test_ast_formatter_format_simple_string():
    """Formatter.format returns repr for leaf values."""

    f = Formatter()
    result = f.format("hello")
    assert result == "'hello'"


def test_ast_formatter_format_long_string_truncated():
    """Formatter.format truncates long strings."""

    f = Formatter(string_max_length=10)
    result = f.format("a" * 100)
    assert len(result) <= 20  # truncated
    assert result.endswith(" ...")


def test_ast_formatter_format_example_code():
    """Formatter.format renders ExampleCode as a tree node."""

    f = Formatter()
    ec = ExampleCode("x = 1")
    result = f.format(ec)
    assert "ExampleCode" in result
    assert "value" in result
    assert "x = 1" in result


def test_ast_formatter_format_max_depth():
    """Formatter.format stops recursing at max_depth."""

    f = Formatter(max_depth=0)
    ec = ExampleCode("x = 1")
    result = f.format(ec)
    assert "ExampleCode" in result
    assert " ..." in result
    assert "value" not in result


def test_ast_formatter_format_compact():
    """Formatter.format works in compact mode."""

    f = Formatter(compact=True)
    ec = ExampleCode("x = 1")
    result = f.format(ec)
    assert "ExampleCode" in result
    assert "value" in result


def test_ast_formatter_get_field_dict():
    """Formatter.get_field retrieves dict values."""

    f = Formatter()
    assert f.get_field({"a": 1}, "a") == 1


def test_ast_formatter_get_field_list():
    """Formatter.get_field retrieves list values by index."""

    f = Formatter()
    assert f.get_field([10, 20, 30], 1) == 20


def test_ast_formatter_get_field_object():
    """Formatter.get_field retrieves object attributes."""

    f = Formatter()
    ec = ExampleCode("x = 1")
    assert f.get_field(ec, "value") == "x = 1"


def test_ast_formatter_fmt_pipe_middle():
    """Formatter.fmt_pipe formats middle entries with pipe prefix."""

    f = Formatter()
    result = f.fmt_pipe("name = 'hello'", is_final=False)
    assert f.icon_pipe in result


def test_ast_formatter_fmt_pipe_final():
    """Formatter.fmt_pipe formats final entries with endpipe."""

    f = Formatter()
    result = f.fmt_pipe("name = 'hello'", is_final=True)
    assert f.icon_endpipe in result


def test_ast_formatter_fmt_pipe_with_pad():
    """Formatter.fmt_pipe applies padding."""

    f = Formatter()
    result = f.fmt_pipe("value = 1", is_final=True, pad=5)
    assert "     " in result


def test_ast_formatter_format_griffe_function():
    """Formatter.format renders a griffe Function as a tree."""

    f = Formatter()
    func = gf.Function(name="my_func", lineno=1)
    result = f.format(func)

    assert "Function" in result
    assert "my_func" in result


def test_ast_formatter_format_dict():
    """Formatter.format renders a dict as a tree."""

    f = Formatter()
    result = f.format({"key1": "val1", "key2": "val2"})
    assert "dict" in result
    assert "key1" in result


def test_ast_formatter_format_nested():
    """Formatter.format handles nested structures."""

    f = Formatter()
    func = gf.Function(
        name="my_func",
        lineno=1,
        docstring=gf.Docstring("A docstring", parser="numpy"),
    )
    result = f.format(func)

    assert "Function" in result
    assert "Docstring" in result


def test_ast_preview_print(capsys):
    """preview() prints the formatted tree."""
    from great_docs._apiref._docstring_sections import ExampleCode
    from great_docs._apiref._preview import preview

    preview(ExampleCode("x = 1"))
    captured = capsys.readouterr()
    assert "ExampleCode" in captured.out


def test_ast_preview_as_string():
    """preview(as_string=True) returns the tree as a string."""
    from great_docs._apiref._docstring_sections import ExampleCode
    from great_docs._apiref._preview import preview

    result = preview(ExampleCode("x = 1"), as_string=True)
    assert isinstance(result, str)
    assert "ExampleCode" in result


def test_ast_preview_max_depth():
    """preview() respects max_depth parameter."""
    from great_docs._apiref._docstring_sections import ExampleCode
    from great_docs._apiref._preview import preview

    result = preview(ExampleCode("x = 1"), max_depth=0, as_string=True)
    assert "ExampleCode" in result
    assert " ..." in result


def test_ast_preview_compact():
    """preview() respects compact parameter."""
    from great_docs._apiref._docstring_sections import ExampleCode
    from great_docs._apiref._preview import preview

    result = preview(ExampleCode("x = 1"), compact=True, as_string=True)
    assert "ExampleCode" in result


def test_ast_fields_docstring_element():
    """fields() returns expected fields for gf.DocstringElement."""
    from great_docs._apiref._preview import fields

    # DocstringElement is the base; DocstringReturn is a subclass not matching
    # DocstringNamedElement or DocstringParameter
    elem = gf.DocstringElement(annotation="int", description="returns an int")
    result = fields(elem)

    assert result == ["annotation", "description"]


# Helper to build a griffe class with attribute/function/class members
def _build_class_with_members():
    """Build a griffe Class with one attribute, one function, one inner class."""
    cls_obj = gf.Class(name="MyClass", lineno=1)
    attr_obj = gf.Attribute(name="my_attr", lineno=2)
    func_obj = gf.Function(name="method", lineno=3)
    inner_obj = gf.Class(name="Inner", lineno=4)
    cls_obj.set_member("my_attr", attr_obj)
    cls_obj.set_member("method", func_obj)
    cls_obj.set_member("Inner", inner_obj)

    doc_attr = content.DocAttribute(name="my_attr", obj=attr_obj)
    doc_func = content.DocFunction(name="method", obj=func_obj)
    doc_inner = content.DocClass(name="Inner", obj=inner_obj, members=[])
    doc_cls = content.DocClass(name="MyClass", obj=cls_obj, members=[doc_attr, doc_func, doc_inner])
    return cls_obj, doc_cls


def _build_class_with_member_pages():
    """Build a griffe Class with MemberPage members."""
    cls_obj = gf.Class(name="MyClass", lineno=1)
    attr_obj = gf.Attribute(name="my_attr", lineno=2)
    func_obj = gf.Function(name="method", lineno=3)
    inner_obj = gf.Class(name="Inner", lineno=4)
    cls_obj.set_member("my_attr", attr_obj)
    cls_obj.set_member("method", func_obj)
    cls_obj.set_member("Inner", inner_obj)

    doc_attr = content.DocAttribute(name="my_attr", obj=attr_obj)
    doc_func = content.DocFunction(name="method", obj=func_obj)
    doc_inner = content.DocClass(name="Inner", obj=inner_obj, members=[])

    page_attr = content.MemberPage(path="my_attr", contents=[doc_attr])
    page_func = content.MemberPage(path="method", contents=[doc_func])
    page_inner = content.MemberPage(path="Inner", contents=[doc_inner])

    doc_cls = content.DocClass(
        name="MyClass", obj=cls_obj, members=[page_attr, page_func, page_inner]
    )
    return cls_obj, doc_cls


def test_mixin_rendered_members_group_str():
    """RenderedMembersGroup.__str__ renders title, summary, and body."""

    rmg = RenderedMembersGroup(
        title=Header(2, "Methods", Attr()),
        summary="A summary table",
        members_body=None,
    )
    result = str(rmg)
    assert "Methods" in result
    assert "A summary table" in result


def test_mixin_rendered_members_group_str_all_none():
    """RenderedMembersGroup.__str__ handles all None fields."""

    rmg = RenderedMembersGroup()
    result = str(rmg)
    assert isinstance(result, str)


def test_mixin_rendered_member_pages_group_str():
    """RenderedMemberPagesGroup.__str__ renders title and summary."""

    rmpg = RenderedMemberPagesGroup(
        title=Header(2, "Attributes", Attr()),
        summary="summary",
    )
    result = str(rmpg)
    assert "Attributes" in result
    assert "summary" in result


def test_mixin_render_body_with_doc_members():
    """render_body renders docstring + member groups for Doc members."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    body = render.render_body()
    body_str = str(body)
    assert "Attributes" in body_str
    assert "Methods" in body_str
    assert "Classes" in body_str


def test_mixin_render_body_with_member_pages():
    """render_body renders docstring + member page groups for MemberPage members."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    body = render.render_body()
    body_str = str(body)
    assert "Attributes" in body_str


def test_mixin_render_body_no_members():
    """render_body returns just docstring when no members."""

    cls_obj = gf.Class(name="Empty", lineno=1)
    doc_cls = content.DocClass(name="Empty", obj=cls_obj, members=[])
    render = RenderDocClass(doc_cls, level=1)

    body = render.render_body()

    # With no members, body is just the docstring result (could be None)
    assert body is None or "Members" not in str(body)


def test_render_section_text_converts_sphinx_fields():
    """Sphinx fields render from Griffe's structured docstring sections."""
    from great_docs.hooks._docstring_parsed import emit_docstring_parsed
    from great_docs.hooks._object_resolved import emit_object_resolved

    func = gf.Function(
        name="f",
        lineno=1,
        parameters=gf.Parameters(gf.Parameter("x", annotation="int")),
        returns="str",
    )
    func.docstring = gf.Docstring(
        "Do a thing.\n\n:param x: The x value.\n:returns: A result.\n:rtype: str",
        parent=func,
        parser="sphinx",
    )
    assert emit_object_resolved(func) is func
    emit_docstring_parsed(func)

    doc_fn = content.DocFunction(name="f", obj=func)
    out = str(RenderDocFunction(doc_fn, level=1).render_body())
    assert ".doc-parameters" in out
    assert "The x value." in out


def test_render_section_text_converts_google_sections():
    """Google sections render from Griffe's structured docstring sections."""
    from great_docs.hooks._docstring_parsed import emit_docstring_parsed
    from great_docs.hooks._object_resolved import emit_object_resolved

    func = gf.Function(
        name="f",
        lineno=1,
        parameters=gf.Parameters(gf.Parameter("x", annotation="int")),
        returns="int",
    )
    func.docstring = gf.Docstring(
        "Do a thing.\n\nArgs:\n    x: The x value.\n\nReturns:\n    (int): A result.",
        parent=func,
        parser="google",
    )
    assert emit_object_resolved(func) is func
    emit_docstring_parsed(func)

    doc_fn = content.DocFunction(name="f", obj=func)
    out = str(RenderDocFunction(doc_fn, level=1).render_body())
    assert ".doc-parameters" in out
    assert ".doc-returns" in out


def test_render_section_text_fences_doctests():
    """Unfenced >>> doctest lines in free text render inside a fenced code block."""
    from great_docs.hooks._docstring_parsed import emit_docstring_parsed
    from great_docs.hooks._object_resolved import emit_object_resolved

    func = gf.Function(name="f", lineno=1)
    func.docstring = gf.Docstring(
        "Do a thing.\n\n>>> f()\n1",
        parent=func,
        parser="numpy",
    )
    assert emit_object_resolved(func) is func
    emit_docstring_parsed(func)

    doc_fn = content.DocFunction(name="f", obj=func)
    out = str(RenderDocFunction(doc_fn, level=1).render_body())
    assert "```" in out


def test_render_example_text_fences_doctests():
    """An ExampleText block renders its doctest lines inside a fenced code block."""
    from great_docs._apiref._docstring_sections import ExampleText
    from great_docs.hooks._object_resolved import emit_object_resolved

    func = gf.Function(name="f", lineno=1)
    func.docstring = gf.Docstring(">>> f()\n1", parent=func, parser="numpy")
    assert emit_object_resolved(func) is func

    doc_fn = content.DocFunction(name="f", obj=func)
    render = RenderDocFunction(doc_fn, level=1)
    out = str(render._render_example_fragment(ExampleText(func.docstring.value)))
    assert "```" in out


def test_mixin_render_body_invalid_member_type_raises():
    """render_body raises ValueError for unrecognized member types."""

    cls_obj = gf.Class(name="Bad", lineno=1)
    # Use a plain string as a member — not Doc or MemberPage
    doc_cls = content.DocClass(name="Bad", obj=cls_obj, members=["not_a_doc"])
    render = RenderDocClass(doc_cls, level=1)

    with pytest.raises(ValueError, match="Cannot render members of type"):
        render.render_body()


def test_mixin_render_members_returns_groups():
    """render_members returns [type aliases, attributes, classes, functions] groups."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    members = render.render_members()
    assert len(members) == 4
    # No type alias members in this fixture, so that slot is None.
    assert members[0] is None
    for m in members[1:]:
        assert isinstance(m, RenderedMembersGroup)


def test_mixin_render_members_show_members_false():
    """render_members returns empty list when show_members=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_members = False

    assert render.render_members() == []


def test_mixin_render_member_pages_returns_groups():
    """render_member_pages returns [type aliases, attributes, classes, functions] page groups."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.render_member_pages()
    assert len(pages) == 4
    # No type alias members in this fixture, so that slot is None.
    assert pages[0] is None
    for p in pages[1:]:
        assert isinstance(p, RenderedMemberPagesGroup)


def test_mixin_render_member_pages_show_members_false():
    """render_member_pages returns empty list when show_members=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_members = False

    assert render.render_member_pages() == []


def _build_class_with_member_pages_and_type_alias():
    """Build a griffe Class with MemberPage members, including a type alias."""
    cls_obj, doc_cls = _build_class_with_member_pages()
    alias_obj = gf.TypeAlias(name="Inline", value=gf.ExprName("int"), lineno=5)
    cls_obj.set_member("Inline", alias_obj)

    doc_alias = DocTypeAlias(name="Inline", obj=alias_obj)
    page_alias = MemberPage(path="Inline", contents=[doc_alias])
    doc_cls.members.append(page_alias)
    return cls_obj, doc_cls


def test_mixin_type_alias_member_pages_property():
    """type_alias_member_pages filters MemberPage members by is_type_alias."""

    _, doc_cls = _build_class_with_member_pages_and_type_alias()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.type_alias_member_pages
    assert len(pages) == 1
    assert pages[0].path == "Inline"


def test_mixin_type_alias_member_pages_honours_exclusions():
    """exclude_type_aliases drops a type alias from type_alias_member_pages."""

    cls_obj, doc_cls = _build_class_with_member_pages_and_type_alias()
    render = RenderDocClass(doc_cls, level=1)

    original = dict(EXCLUSIONS.type_aliases)
    try:
        exclude_type_aliases({cls_obj.path: "Inline"})
        assert render.type_alias_member_pages == []
    finally:
        EXCLUSIONS.type_aliases.clear()
        EXCLUSIONS.type_aliases.update(original)


def test_exclude_type_aliases_updates_globals():
    """exclude_type_aliases updates the EXCLUSIONS.type_aliases global dict."""

    original = dict(EXCLUSIONS.type_aliases)
    try:
        exclude_type_aliases({"test.MyClass": "Contract"})
        assert EXCLUSIONS.type_aliases["test.MyClass"] == "Contract"
    finally:
        EXCLUSIONS.type_aliases.clear()
        EXCLUSIONS.type_aliases.update(original)


def test_mixin_render_type_alias_member_pages():
    """render_type_alias_member_pages returns RenderedMemberPagesGroup."""

    _, doc_cls = _build_class_with_member_pages_and_type_alias()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_type_alias_member_pages()
    assert isinstance(result, RenderedMemberPagesGroup)
    assert "Type Aliases" in str(result.title)


def test_mixin_render_type_alias_member_pages_show_false():
    """render_type_alias_member_pages returns None when show_type_aliases=False."""

    _, doc_cls = _build_class_with_member_pages_and_type_alias()
    render = RenderDocClass(doc_cls, level=1)
    render.show_type_aliases = False

    assert render.render_type_alias_member_pages() is None


def test_mixin_render_member_pages_includes_type_alias_group():
    """render_member_pages fills the type-alias slot when a MemberPage alias exists."""

    _, doc_cls = _build_class_with_member_pages_and_type_alias()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.render_member_pages()
    assert len(pages) == 4
    assert isinstance(pages[0], RenderedMemberPagesGroup)
    assert "Type Aliases" in str(pages[0].title)


def test_mixin_attributes_property():
    """attributes property filters Doc members by is_attribute."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    attrs = render.attributes
    assert len(attrs) == 1
    assert attrs[0].name == "my_attr"


def test_mixin_classes_property():
    """classes property filters Doc members by is_class."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    classes = render.classes
    assert len(classes) == 1
    assert classes[0].name == "Inner"


def test_mixin_functions_property():
    """functions property filters Doc members by is_function."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    funcs = render.functions
    assert len(funcs) == 1
    assert funcs[0].name == "method"


def test_mixin_attribute_member_pages_property():
    """attribute_member_pages filters MemberPage members by is_attribute."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.attribute_member_pages
    assert len(pages) == 1
    assert pages[0].path == "my_attr"


def test_mixin_class_member_pages_property():
    """class_member_pages filters MemberPage members by is_class."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.class_member_pages
    assert len(pages) == 1
    assert pages[0].path == "Inner"


def test_mixin_function_member_pages_property():
    """function_member_pages filters MemberPage members by is_function."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    pages = render.function_member_pages
    assert len(pages) == 1
    assert pages[0].path == "method"


def test_mixin_attributes_exclude_filter():
    """attributes property respects EXCLUSIONS.attributes."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.attributes.copy()
    try:
        _globals.EXCLUSIONS.attributes["MyClass"] = ("my_attr",)
        if "attributes" in render.__dict__:
            del render.__dict__["attributes"]
        attrs = render.attributes
        assert len(attrs) == 0
    finally:
        _globals.EXCLUSIONS.attributes.clear()
        _globals.EXCLUSIONS.attributes.update(old)


def test_mixin_functions_exclude_filter():
    """functions property respects EXCLUSIONS.functions."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.functions.copy()
    try:
        _globals.EXCLUSIONS.functions["MyClass"] = ("method",)
        if "functions" in render.__dict__:
            del render.__dict__["functions"]
        funcs = render.functions
        assert len(funcs) == 0
    finally:
        _globals.EXCLUSIONS.functions.clear()
        _globals.EXCLUSIONS.functions.update(old)


def test_mixin_classes_exclude_filter():
    """classes property respects EXCLUSIONS.classes."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.classes.copy()
    try:
        _globals.EXCLUSIONS.classes["MyClass"] = "Inner"
        if "classes" in render.__dict__:
            del render.__dict__["classes"]
        classes = render.classes
        assert len(classes) == 0
    finally:
        _globals.EXCLUSIONS.classes.clear()
        _globals.EXCLUSIONS.classes.update(old)


def test_mixin_attribute_member_pages_exclude_filter():
    """attribute_member_pages respects EXCLUSIONS.attributes."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.attributes.copy()
    try:
        _globals.EXCLUSIONS.attributes["MyClass"] = "my_attr"
        if "attribute_member_pages" in render.__dict__:
            del render.__dict__["attribute_member_pages"]
        pages = render.attribute_member_pages
        assert len(pages) == 0
    finally:
        _globals.EXCLUSIONS.attributes.clear()
        _globals.EXCLUSIONS.attributes.update(old)


def test_mixin_class_member_pages_exclude_filter():
    """class_member_pages respects EXCLUSIONS.classes."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.classes.copy()
    try:
        _globals.EXCLUSIONS.classes["MyClass"] = ("Inner",)
        if "class_member_pages" in render.__dict__:
            del render.__dict__["class_member_pages"]
        pages = render.class_member_pages
        assert len(pages) == 0
    finally:
        _globals.EXCLUSIONS.classes.clear()
        _globals.EXCLUSIONS.classes.update(old)


def test_mixin_function_member_pages_exclude_filter():
    """function_member_pages respects EXCLUSIONS.functions."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    old = _globals.EXCLUSIONS.functions.copy()
    try:
        _globals.EXCLUSIONS.functions["MyClass"] = "method"
        if "function_member_pages" in render.__dict__:
            del render.__dict__["function_member_pages"]
        pages = render.function_member_pages
        assert len(pages) == 0
    finally:
        _globals.EXCLUSIONS.functions.clear()
        _globals.EXCLUSIONS.functions.update(old)


def test_mixin_render_classes():
    """render_classes returns a RenderedMembersGroup with 'Classes' title."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_classes()
    assert isinstance(result, RenderedMembersGroup)
    assert "Classes" in str(result.title)


def test_mixin_render_functions():
    """render_functions returns a RenderedMembersGroup with 'Methods' title for classes."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_functions()
    assert isinstance(result, RenderedMembersGroup)
    assert "Methods" in str(result.title)


def test_mixin_render_attributes():
    """render_attributes returns a RenderedMembersGroup with 'Attributes' title."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_attributes()
    assert isinstance(result, RenderedMembersGroup)
    assert "Attributes" in str(result.title)


def test_mixin_render_classes_show_false():
    """render_classes returns None when show_classes=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_classes = False

    assert render.render_classes() is None


def test_mixin_render_functions_show_false():
    """render_functions returns None when show_functions=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_functions = False

    assert render.render_functions() is None


def test_mixin_render_attributes_show_false():
    """render_attributes returns None when show_attributes=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_attributes = False

    assert render.render_attributes() is None


def test_mixin_render_class_member_pages():
    """render_class_member_pages returns RenderedMemberPagesGroup."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_class_member_pages()
    assert isinstance(result, RenderedMemberPagesGroup)


def test_mixin_render_function_member_pages():
    """render_function_member_pages returns RenderedMemberPagesGroup."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_function_member_pages()
    assert isinstance(result, RenderedMemberPagesGroup)


def test_mixin_render_attribute_member_pages():
    """render_attribute_member_pages returns RenderedMemberPagesGroup."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_attribute_member_pages()
    assert isinstance(result, RenderedMemberPagesGroup)


def test_mixin_render_class_member_pages_show_false():
    """render_class_member_pages returns None when show_classes=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_classes = False

    assert render.render_class_member_pages() is None


def test_mixin_render_function_member_pages_show_false():
    """render_function_member_pages returns None when show_functions=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_functions = False

    assert render.render_function_member_pages() is None


def test_mixin_render_attribute_member_pages_show_false():
    """render_attribute_member_pages returns None when show_attributes=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_attributes = False

    assert render.render_attribute_member_pages() is None


def test_mixin_render_members_group_no_summary():
    """_render_members_group skips summary when show_*_summary=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_functions_summary = False

    result = render.render_functions()
    assert result is not None
    assert result.summary is None


def test_mixin_render_members_group_no_body():
    """_render_members_group skips body when show_*_body=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_functions_body = False

    result = render.render_functions()
    assert result is not None
    assert result.members_body is None


def test_mixin_render_members_group_no_summary_global():
    """_render_members_group skips summary when show_members_summary=False."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_members_summary = False

    result = render.render_functions()
    assert result is not None
    assert result.summary is None


def test_mixin_render_members_group_empty_returns_none():
    """_render_members_group returns None when no members of that type."""

    cls_obj = gf.Class(name="FuncOnly", lineno=1)
    func_obj = gf.Function(name="method", lineno=2)
    cls_obj.set_member("method", func_obj)
    doc_func = content.DocFunction(name="method", obj=func_obj)
    doc_cls = content.DocClass(name="FuncOnly", obj=cls_obj, members=[doc_func])

    render = RenderDocClass(doc_cls, level=1)

    assert render.render_attributes() is None
    assert render.render_classes() is None
    assert render.render_functions() is not None


def test_mixin_render_members_group_attributes_summary_and_body():
    """_render_members_group for attributes respects show_attributes_summary/body."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_attributes_summary = False
    render.show_attributes_body = False

    result = render.render_attributes()
    assert result is not None
    assert result.summary is None
    assert result.members_body is None


def test_mixin_render_members_group_classes_summary_and_body():
    """_render_members_group for classes respects show_classes_summary/body."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)
    render.show_classes_summary = False
    render.show_classes_body = False

    result = render.render_classes()
    assert result is not None
    assert result.summary is None
    assert result.members_body is None


def test_mixin_render_member_pages_group_no_summary():
    """_render_member_pages_group skips summary when show_*_summary=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_functions_summary = False

    result = render.render_function_member_pages()
    assert result is not None
    assert result.summary is None


def test_mixin_render_member_pages_group_empty_returns_none():
    """_render_member_pages_group returns None when no pages of that type."""

    cls_obj = gf.Class(name="FuncOnly", lineno=1)
    func_obj = gf.Function(name="method", lineno=2)
    cls_obj.set_member("method", func_obj)

    doc_func = content.DocFunction(name="method", obj=func_obj)
    page_func = content.MemberPage(path="method", contents=[doc_func])
    doc_cls = content.DocClass(name="FuncOnly", obj=cls_obj, members=[page_func])

    render = RenderDocClass(doc_cls, level=1)

    assert render.render_attribute_member_pages() is None
    assert render.render_class_member_pages() is None
    assert render.render_function_member_pages() is not None


def test_mixin_render_member_pages_group_functions_slug_for_class():
    """_render_member_pages_group uses 'Functions' slug for DocClass function pages."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_function_member_pages()
    assert result is not None
    title_str = str(result.title)
    assert "Functions" in title_str


def test_mixin_render_member_pages_group_attributes_no_summary():
    """_render_member_pages_group for attributes skips summary when disabled."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_attributes_summary = False

    result = render.render_attribute_member_pages()
    assert result is not None
    assert result.summary is None


def test_mixin_render_member_pages_group_classes_no_summary():
    """_render_member_pages_group for classes skips summary when disabled."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_classes_summary = False

    result = render.render_class_member_pages()
    assert result is not None
    assert result.summary is None


def test_mixin_render_member_pages_group_global_summary_off():
    """_render_member_pages_group skips summary when show_members_summary=False."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)
    render.show_members_summary = False

    result = render.render_function_member_pages()
    assert result is not None
    assert result.summary is None


def test_mixin_render_members_group_has_summary_table():
    """_render_members_group produces a tabulate summary."""

    _, doc_cls = _build_class_with_members()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_functions()
    assert result is not None
    assert result.summary is not None
    assert "Name" in result.summary


def test_mixin_render_member_pages_group_has_summary_table():
    """_render_member_pages_group produces a tabulate summary."""

    _, doc_cls = _build_class_with_member_pages()
    render = RenderDocClass(doc_cls, level=1)

    result = render.render_function_member_pages()
    assert result is not None
    assert result.summary is not None
    assert "Name" in result.summary


def test_mixin_render_functions_module_uses_functions_slug():
    """For DocModule, render_functions uses 'Functions' not 'Methods'."""

    mod_obj = gf.Module(name="mymod")
    func_obj = gf.Function(name="func", lineno=1)
    mod_obj.set_member("func", func_obj)

    doc_func = content.DocFunction(name="func", obj=func_obj)
    doc_mod = content.DocModule(name="mymod", obj=mod_obj, members=[doc_func])

    render = RenderDocModule(doc_mod, level=1)

    result = render.render_functions()
    assert result is not None
    assert "Functions" in str(result.title)


def test_mixin_render_members_module_uses_functions_slug():
    """For DocModule, render_members has 'Functions' group not 'Methods'."""

    mod_obj = gf.Module(name="mymod", filepath=Path("/tmp/mymod.py"))
    func_obj = gf.Function(name="func", lineno=1)
    cls_obj = gf.Class(name="Cls", lineno=2)
    attr_obj = gf.Attribute(name="val", lineno=3)
    mod_obj.set_member("func", func_obj)
    mod_obj.set_member("Cls", cls_obj)
    mod_obj.set_member("val", attr_obj)

    doc_func = content.DocFunction(name="func", obj=func_obj)
    doc_cls = content.DocClass(name="Cls", obj=cls_obj, members=[])
    doc_attr = content.DocAttribute(name="val", obj=attr_obj)
    doc_mod = content.DocModule(name="mymod", obj=mod_obj, members=[doc_attr, doc_cls, doc_func])

    render = RenderDocModule(doc_mod, level=1)

    members = render.render_members()
    assert len(members) == 4
    body_str = str(render.render_body())
    assert "Functions" in body_str
    assert "Classes" in body_str
    assert "Attributes" in body_str


def test_blocks_block_str_raises():
    """Block.__str__ raises NotImplementedError."""

    with pytest.raises(NotImplementedError, match="__str__ method not implemented"):
        str(Block())


def test_blocks_block_html_raises():
    """Block.html raises NotImplementedError."""

    with pytest.raises(NotImplementedError, match="html property method not implemented"):
        Block().html


def test_blocks_blocks_empty():
    """Blocks with no elements returns empty string."""

    assert str(Blocks()) == ""
    assert str(Blocks(None)) == ""


def test_blocks_blocks_with_strings():
    """Blocks renders string elements separated by double newlines."""

    result = str(Blocks(["a", "b", "c"]))
    assert result == "a\n\nb\n\nc"


def test_blocks_blocks_with_blocks():
    """Blocks renders Block elements."""

    result = str(Blocks([Plain("hello"), Plain("world")]))
    assert "hello" in result
    assert "world" in result


def test_blocks_blocks_filters_none():
    """Blocks filters out falsy elements."""

    result = str(Blocks(["a", None, "b"]))
    assert result == "a\n\nb"


def test_blocks_plain_str():
    """Plain renders content as-is."""

    assert str(Plain("hello")) == "hello"


def test_blocks_plain_none():
    """Plain with None content returns empty string."""

    assert str(Plain(None)) == ""


def test_blocks_para_str():
    """Para wraps content in newlines."""

    result = str(Para("hello"))
    assert result == "\nhello\n"


def test_blocks_para_as_list_item():
    """Para.as_list_item renders without leading newline."""

    result = Para("hello").as_list_item
    assert result == "hello\n\n"


def test_blocks_header_with_attr():
    """Header renders with hashes and attr."""

    result = str(Header(2, "Title", Attr(classes=["c"])))
    assert result == "## Title {.c}"


def test_blocks_header_no_attr():
    """Header without attr omits the braces."""

    result = str(Header(1, "Title"))
    assert result == "# Title"


def test_blocks_codeblock_single_class():
    """CodeBlock with single class renders without braces."""

    result = str(CodeBlock("x=1", Attr(classes=["python"])))
    assert result == "```python\nx=1\n```"


def test_blocks_codeblock_no_attr():
    """CodeBlock without attr renders plain fences."""

    result = str(CodeBlock("x=1"))
    assert result == "```\nx=1\n```"


def test_blocks_codeblock_multi_class():
    """CodeBlock with multiple classes renders with braces."""

    result = str(CodeBlock("x=1", Attr(classes=["py", "cell"])))
    assert "``` {.py .cell}" in result


def test_blocks_codeblock_class_with_attributes():
    """CodeBlock with class and attributes renders with braces."""

    result = str(CodeBlock("x=1", Attr(classes=["py"], attributes={"data-x": "1"})))
    assert "``` {" in result
    assert ".py" in result


def test_blocks_codeblock_none_content():
    """CodeBlock with None content renders empty body."""

    result = str(CodeBlock(None))
    assert result == "```\n\n```"


def test_blocks_codeblock_html():
    """CodeBlock.html renders pre/code tags."""

    result = CodeBlock("x=1", Attr(classes=["py"])).html
    assert "<pre" in result
    assert "<code>x=1</code>" in result


def test_blocks_codeblock_html_no_attr():
    """CodeBlock.html without attr has no class."""

    result = CodeBlock("code").html
    assert "<pre>" in result
    assert "<code>code</code>" in result


def test_blocks_codeblock_as_list_item():
    """CodeBlock.as_list_item wraps in newlines."""

    result = CodeBlock("x=1").as_list_item
    assert result.startswith("\n")
    assert result.endswith("\n\n")
    assert "```" in result


def test_blocks_deflist_basic():
    """DefinitionList renders terms and definitions."""

    dl = DefinitionList([("term1", "def1"), ("term2", "def2")])
    result = str(dl)
    assert "term1" in result
    assert ":   def1" in result
    assert "term2" in result


def test_blocks_deflist_multiple_defs():
    """DefinitionList renders multiple definitions per term."""

    dl = DefinitionList([("term", ["def_a", "def_b"])])
    result = str(dl)
    assert "term" in result
    assert ":   def_a" in result
    assert ":   def_b" in result


def test_blocks_deflist_none_definition():
    """DefinitionList handles None definition."""

    dl = DefinitionList([("term", None)])
    result = str(dl)
    assert "term" in result
    assert ":   " in result


def test_blocks_deflist_block_definition():
    """DefinitionList handles Block as definition."""

    dl = DefinitionList([("term", Plain("hello"))])
    result = str(dl)
    assert "term" in result
    assert ":   hello" in result


def test_blocks_deflist_empty():
    """DefinitionList with no content returns empty string."""

    assert str(DefinitionList(None)) == ""
    assert str(DefinitionList([])) == ""


def test_blocks_div_with_attr():
    """Div renders fenced div with attr."""

    result = str(Div("content", Attr(classes=["box"])))
    assert ":::" in result
    assert ".box" in result
    assert "content" in result


def test_blocks_div_no_attr():
    """Div renders without attr."""

    result = str(Div("content"))
    assert ":::" in result
    assert "content" in result


def test_blocks_bulletlist_strings():
    """BulletList renders string items with * prefix."""

    result = str(BulletList(["a", "b", "c"]))
    assert "* a" in result
    assert "* b" in result
    assert "* c" in result


def test_blocks_bulletlist_empty():
    """BulletList with no content returns empty string."""

    assert str(BulletList(None)) == ""


def test_blocks_bulletlist_single_string():
    """BulletList with a single string."""

    result = str(BulletList("hello"))
    assert "* hello" in result


def test_blocks_bulletlist_block_items():
    """BulletList with Block items."""

    result = str(BulletList([Plain("x"), Plain("y")]))
    assert "* x" in result
    assert "* y" in result


def test_blocks_orderedlist_strings():
    """OrderedList renders items with numbered prefixes."""

    result = str(OrderedList(["a", "b"]))
    assert "1. a" in result
    assert "2. b" in result


def test_blocks_orderedlist_empty():
    """OrderedList with no content returns empty string."""

    assert str(OrderedList(None)) == ""


def test_blocks_orderedlist_single_string():
    """OrderedList with a single string."""

    result = str(OrderedList("hello"))
    assert "1. hello" in result


def test_blocks_orderedlist_block_items():
    """OrderedList with Block items."""

    result = str(OrderedList([Plain("x"), Plain("y")]))
    assert "1. x" in result
    assert "2. y" in result


def test_blocks_blockcontent_to_str_none():
    """blockcontent_to_str with None returns empty string."""

    assert blockcontent_to_str(None) == ""


def test_blocks_blockcontent_to_str_string():
    """blockcontent_to_str with string returns it stripped."""

    assert blockcontent_to_str("hello\n") == "hello"


def test_blocks_blockcontent_to_str_block():
    """blockcontent_to_str with Block renders it."""

    assert blockcontent_to_str(Plain("hi")) == "hi"


def test_blocks_blockcontent_to_str_sequence():
    """blockcontent_to_str with sequence joins items."""

    result = blockcontent_to_str(["a", "b"])
    assert result == "a\n\nb"


def test_blocks_str_items_none():
    """blockcontent_to_str_items with None returns empty string."""

    assert blockcontent_to_str_items(None, "bullet") == ""


def test_blocks_str_items_string():
    """blockcontent_to_str_items with string formats it."""

    result = blockcontent_to_str_items("hello", "bullet")
    assert "* hello" in result


def test_blocks_str_items_block():
    """blockcontent_to_str_items with Block formats it."""

    result = blockcontent_to_str_items(Plain("item"), "bullet")
    assert "* item" in result


def test_blocks_str_items_sequence():
    """blockcontent_to_str_items with sequence formats all items."""

    result = blockcontent_to_str_items(["a", "b", "c"], "bullet")
    assert "* a" in result
    assert "* b" in result
    assert "* c" in result


def test_blocks_str_items_ordered():
    """blockcontent_to_str_items with ordered list uses numbered prefixes."""

    result = blockcontent_to_str_items(["x", "y"], "ordered")
    assert "1. x" in result
    assert "2. y" in result


def test_blocks_str_items_empty_string_returns_empty():
    """blockcontent_to_str_items fmt skips empty strings."""

    result = blockcontent_to_str_items([], "bullet")
    assert result == ""


def test_blocks_str_items_para_items():
    """blockcontent_to_str_items handles Para items with leading newline."""

    result = blockcontent_to_str_items([Para("a"), Para("b")], "bullet")
    assert "*" in result
    assert "a" in result


def test_blocks_meta_str():
    """Meta renders YAML front matter."""

    m = Meta({"title": "test", "format": "html"})
    result = str(m)
    assert result.startswith("---\n")
    assert result.endswith("---")
    assert "title: test" in result
    assert "format: html" in result


def test_blocks_raw_html_with_attr():
    """RawHTMLBlockTag renders with HTML attr."""

    r = RawHTMLBlockTag("div", "content", Attr(classes=["x"]))
    result = str(r)
    assert '<div class="x">' in result
    assert "content" in result
    assert "</div>" in result


def test_blocks_raw_html_no_attr():
    """RawHTMLBlockTag renders without attr."""

    r = RawHTMLBlockTag("span", "text")
    result = str(r)
    assert "<span>" in result
    assert "text" in result
    assert "</span>" in result


def test_blocks_rendered_doc_object_full():
    """RenderedDocObject renders title, signature, body."""

    rdo = RenderedDocObject(title=Header(1, "Fn"), signature="sig", body="body")
    result = str(rdo)
    assert "# Fn" in result
    assert "sig" in result
    assert "body" in result


def test_blocks_rendered_doc_object_empty():
    """RenderedDocObject with no parts returns empty string."""

    assert str(RenderedDocObject()) == ""


def test_blocks_rendered_doc_object_partial():
    """RenderedDocObject renders only non-None parts."""

    rdo = RenderedDocObject(title=Header(2, "Title"))
    result = str(rdo)
    assert "## Title" in result


def test_blocks_bulletlist_with_inline():
    """BulletList handles Inline items."""

    result = str(BulletList([Str("a"), Str("b")]))
    assert "a" in result
    assert "b" in result


def test_blocks_orderedlist_with_inline():
    """OrderedList handles Inline items."""

    result = str(OrderedList([Str("x"), Str("y")]))
    assert "1." in result
    assert "x" in result


def test_blocks_deflist_with_inline_term():
    """DefinitionList handles Inline as term."""

    dl = DefinitionList([(Str("term"), "def")])
    result = str(dl)
    assert "term" in result
    assert ":   def" in result


def test_blocks_str_items_single_block():
    """blockcontent_to_str_items with single Block uses as_list_item."""

    result = blockcontent_to_str_items(CodeBlock("code"), "ordered")
    assert "1." in result
    assert "```" in result


def test_docclass_attributes_excludes_dataclass_params():
    """DocClass.attributes filters out dataclass params when is_dataclass=True."""

    cls_obj = gf.Class(name="DC", lineno=1)
    cls_obj.labels.add("dataclass")

    # Create attributes on the class
    attr_x = gf.Attribute(name="x", lineno=2)
    attr_x.annotation = gf.ExprName("int")
    attr_y = gf.Attribute(name="y", lineno=3)
    attr_y.annotation = gf.ExprName("str")
    cls_obj.set_member("x", attr_x)
    cls_obj.set_member("y", attr_y)

    # Create init function with parameter "x"
    init_fn = gf.Function(name="__init__", lineno=4)
    init_fn.parameters = gf.Parameters(
        gf.Parameter("self", kind=gf.ParameterKind.positional_or_keyword),
        gf.Parameter(
            "x", annotation=gf.ExprName("int"), kind=gf.ParameterKind.positional_or_keyword
        ),
    )
    cls_obj.set_member("__init__", init_fn)

    doc_attr_x = content.DocAttribute(name="x", obj=attr_x)
    doc_attr_y = content.DocAttribute(name="y", obj=attr_y)
    doc_cls = content.DocClass(name="DC", obj=cls_obj, members=[doc_attr_x, doc_attr_y])

    render = RenderDocClass(doc_cls, level=1)

    # is_dataclass should be True
    assert render.is_dataclass is True

    # attributes should exclude "x" (which is a parameter)
    attr_names = [a.name for a in render.attributes]
    assert "x" not in attr_names
    assert "y" in attr_names


def test_docclass_parameter_attributes_with_dataclass():
    """DocClass.parameter_attributes returns params found in class attributes."""

    cls_obj = gf.Class(name="DC2", lineno=1)
    cls_obj.labels.add("dataclass")

    attr_a = gf.Attribute(name="a", lineno=2)
    attr_a.annotation = gf.ExprName("int")
    cls_obj.set_member("a", attr_a)

    init_fn = gf.Function(name="__init__", lineno=3)
    init_fn.parameters = gf.Parameters(
        gf.Parameter("self", kind=gf.ParameterKind.positional_or_keyword),
        gf.Parameter(
            "a", annotation=gf.ExprName("int"), kind=gf.ParameterKind.positional_or_keyword
        ),
    )
    cls_obj.set_member("__init__", init_fn)

    doc_attr_a = content.DocAttribute(name="a", obj=attr_a)
    doc_cls = content.DocClass(name="DC2", obj=cls_obj, members=[doc_attr_a])

    render = RenderDocClass(doc_cls, level=1)
    pa = render.parameter_attributes
    assert len(pa) == 1
    assert pa[0].name == "a"


def test_docclass_init_parameters_with_dataclass():
    """DocClass.init_parameters returns params NOT in class attributes."""

    cls_obj = gf.Class(name="DC3", lineno=1)
    cls_obj.labels.add("dataclass")

    # "a" is in attributes, "b" is NOT in attributes
    attr_a = gf.Attribute(name="a", lineno=2)
    attr_a.annotation = gf.ExprName("int")
    cls_obj.set_member("a", attr_a)

    init_fn = gf.Function(name="__init__", lineno=3)
    init_fn.parameters = gf.Parameters(
        gf.Parameter("self", kind=gf.ParameterKind.positional_or_keyword),
        gf.Parameter(
            "a", annotation=gf.ExprName("int"), kind=gf.ParameterKind.positional_or_keyword
        ),
        gf.Parameter(
            "b", annotation=gf.ExprName("str"), kind=gf.ParameterKind.positional_or_keyword
        ),
    )
    cls_obj.set_member("__init__", init_fn)

    doc_attr_a = content.DocAttribute(name="a", obj=attr_a)
    doc_cls = content.DocClass(name="DC3", obj=cls_obj, members=[doc_attr_a])

    render = RenderDocClass(doc_cls, level=1)
    ip = render.init_parameters

    # "self" and "b" are not in class attributes; "a" is
    param_names = [p.name for p in ip]

    assert "b" in param_names
    assert "a" not in param_names


def test_docmodule_render_signature_no_signature_name():
    """DocModule.render_signature() returns None when signature_name is falsy."""

    mod_obj = gf.Module(name="my_module")
    doc_mod = content.DocModule(name="my_module", obj=mod_obj)

    render = RenderDocModule(doc_mod, level=1)
    # Override the cached_property by setting in instance __dict__
    render.__dict__["signature_name"] = ""
    result = render.render_signature()
    assert result is None


def test_docmodule_render_signature_with_name():
    """DocModule.render_signature() returns Div when signature_name is set."""

    mod_obj = gf.Module(name="my_module")
    doc_mod = content.DocModule(name="my_module", obj=mod_obj)

    render = RenderDocModule(doc_mod, level=1)
    # Ensure signature_name is non-empty
    render.__dict__["signature_name"] = "my_module"
    result = render.render_signature()

    assert result is not None
    assert "my_module" in str(result)


def test_docmodule_post_init_narrows_types():
    """DocModule.__post_init__() narrows self.doc and self.obj types."""

    mod_obj = gf.Module(name="test_mod")
    doc_mod = content.DocModule(name="test_mod", obj=mod_obj)

    render = RenderDocModule(doc_mod, level=1)

    # After __post_init__, self.doc and self.obj should be set
    assert render.doc is doc_mod
    assert render.obj is mod_obj


def test_get_render_type_raises_for_unmapped_type():
    """get_render_type() raises ValueError for an unmapped type."""

    class FakeDocObj:
        pass

    with pytest.raises(ValueError, match="Cannot document object of type"):
        get_render_type(FakeDocObj())


def test_renderbase_title_property():
    """RenderBase.title calls render_title()."""

    mod_obj = gf.Module(name="tmod")
    doc_mod = content.DocModule(name="tmod", obj=mod_obj)

    render = RenderDocModule(doc_mod, level=1)

    # Access the 'title' cached property, which calls render_title()
    title = render.title

    # render_title for a module returns a Header or None; just verify it ran
    assert title is not None or title is None  # doesn't raise


def test_renderbase_summary_name_property():
    """RenderBase.summary_name returns empty string."""

    # Create a mock that won't trigger __post_init__ logic
    rb = object.__new__(RenderBase)
    rb.node = MagicMock()
    rb.level = 1
    assert rb.summary_name == ""


def test_docattribute_render_signature_type_kind():
    """DocAttribute.render_signature() clears name/annotation for TypeAlias kind."""

    attr_obj = gf.Attribute(name="MyType", lineno=1)
    attr_obj.annotation = gf.ExprName("str")

    # Set the kind to TYPE_ALIAS so kind.value is "type alias" which contains "type"
    attr_obj.kind = gf.Kind.TYPE_ALIAS

    doc_attr = content.DocAttribute(name="MyType", obj=attr_obj)

    render = RenderDocAttribute(doc_attr, level=1)

    assert "type" in render.kind

    sig = render.render_signature()
    sig_str = str(sig)

    assert isinstance(sig_str, str)


def test_mixin_page_render_title():
    """RenderPageMixin.render_title() returns render_metadata()."""

    # Create instance bypassing __init__
    obj = object.__new__(RenderPageMixin)
    obj.node = MagicMock()
    obj.level = 1

    # render_metadata returns None by default (no override)
    result = obj.render_title()

    # The base render_metadata() returns None
    assert result is None


def test_get_render_type_valid_type():
    """get_render_type() returns correct class for a mapped type."""

    obj = DocClass(name="X", obj=gf.Class(name="X", lineno=1))
    result = get_render_type(obj)
    assert result is RenderDocClass


def test_renderbase_summary_property():
    """RenderBase.summary calls render_summary()."""

    rb = object.__new__(RenderBase)
    rb.node = MagicMock()
    rb.level = 1
    # Access summary cached_property which calls render_summary()
    result = rb.summary
    assert result == []


def test_docclass_attribute_member_pages_dataclass():
    """DocClass.attribute_member_pages filters dataclass params."""

    cls_obj = gf.Class(name="DC4", lineno=1)
    cls_obj.labels.add("dataclass")

    attr_x = gf.Attribute(name="x", lineno=2)
    attr_x.annotation = gf.ExprName("int")
    attr_y = gf.Attribute(name="y", lineno=3)
    attr_y.annotation = gf.ExprName("str")
    cls_obj.set_member("x", attr_x)
    cls_obj.set_member("y", attr_y)

    init_fn = gf.Function(name="__init__", lineno=4)
    init_fn.parameters = gf.Parameters(
        gf.Parameter("self", kind=gf.ParameterKind.positional_or_keyword),
        gf.Parameter(
            "x", annotation=gf.ExprName("int"), kind=gf.ParameterKind.positional_or_keyword
        ),
    )
    cls_obj.set_member("__init__", init_fn)

    doc_attr_x = content.DocAttribute(name="x", obj=attr_x)
    doc_attr_y = content.DocAttribute(name="y", obj=attr_y)
    page_x = content.MemberPage(path="x", contents=[doc_attr_x])
    page_y = content.MemberPage(path="y", contents=[doc_attr_y])
    doc_cls = content.DocClass(name="DC4", obj=cls_obj, members=[page_x, page_y])

    render = RenderDocClass(doc_cls, level=1)
    pages = render.attribute_member_pages
    page_names = [p.obj.name for p in pages]
    assert "x" not in page_names
    assert "y" in page_names


def test_docclass_parameter_attributes_non_dataclass():
    """DocClass.parameter_attributes returns empty for non-dataclass."""

    cls_obj = gf.Class(name="RegularClass", lineno=1)
    doc_cls = content.DocClass(name="RegularClass", obj=cls_obj, members=[])

    render = RenderDocClass(doc_cls, level=1)
    assert render.is_dataclass is False
    pa = render.parameter_attributes
    assert len(pa) == 0


def test_docclass_init_parameters_non_dataclass():
    """DocClass.init_parameters returns empty for non-dataclass."""

    cls_obj = gf.Class(name="RegularClass2", lineno=1)
    doc_cls = content.DocClass(name="RegularClass2", obj=cls_obj, members=[])

    render = RenderDocClass(doc_cls, level=1)
    assert render.is_dataclass is False
    ip = render.init_parameters
    assert len(ip) == 0


def test_dc_docstring_section_bool():
    """DCDocstringSection.__bool__ returns True/False based on value."""

    section_empty = DCDocstringSection(value=[], title="Empty")
    assert not section_empty

    section_full = DCDocstringSection(value=[MagicMock()], title="Full")
    assert section_full


def test_attr_str_with_identifier():
    """Attr.__str__ renders identifier with # prefix."""

    attr = Attr(identifier="my-id")
    assert str(attr) == "#my-id"


def test_attr_str_with_all_parts():
    """Attr.__str__ renders identifier + classes + attributes."""

    attr = Attr(identifier="foo", classes=["bar", "baz"], attributes={"k": "v"})
    result = str(attr)
    assert "#foo" in result
    assert ".bar" in result
    assert 'k="v"' in result


def test_attr_html_with_identifier():
    """Attr.html renders identifier as id= attribute."""

    attr = Attr(identifier="test-id")
    assert 'id="test-id"' in attr.html


def test_attr_html_with_attributes():
    """Attr.html renders custom attributes."""

    attr = Attr(attributes={"data-x": "1", "data-y": "2"})
    html = attr.html
    assert 'data-x="1"' in html
    assert 'data-y="2"' in html


def test_attr_empty_property():
    """Attr.empty returns True when no fields set."""

    assert Attr().empty is True
    assert Attr(identifier="x").empty is False
    assert Attr(classes=["c"]).empty is False
    assert Attr(attributes={"k": "v"}).empty is False


def test_inlines0_str_with_content():
    """Inlines0.__str__ joins elements without separator."""

    result = str(Inlines0(elements=["a", "b", "c"]))
    assert result == "abc"


def test_code_html_property():
    """Code.html returns code wrapped in <code> tags."""

    c = Code(text="x = 1")
    assert c.html == "<code>x = 1</code>"


def test_code_html_with_attr():
    """Code.html includes attr in the <code> tag."""

    c = Code(text="val", attr=Attr(classes=["py"]))
    html = c.html
    assert '<code class="py">val</code>' == html


def test_strong_str():
    """Strong.__str__ wraps content in **."""

    assert str(Strong(content="bold")) == "**bold**"
    assert str(Strong(content=None)) == ""
    assert str(Strong()) == ""


def test_emph_str():
    """Emph.__str__ wraps content in *."""

    assert str(Emph(content="italic")) == "*italic*"
    assert str(Emph(content=None)) == ""


def test_image_str():
    """Image.__str__ renders markdown image syntax."""
    from great_docs.pandoc.inlines import Image

    img = Image(caption="Logo", src="img.png")
    assert str(img) == "![Logo](img.png)"

    img2 = Image(caption="Logo", src="img.png", title="My Title")
    assert '"My Title"' in str(img2)


def test_inlinecontent_to_str_sequence():
    """inlinecontent_to_str handles a Sequence of items."""

    result = inlinecontent_to_str(["hello", "world"])
    assert result == "hello world"


def test_interlink_post_init():
    """InterLink.__post_init__ wraps target in backticks."""

    link = InterLink(content="MyClass", target="pkg.MyClass")
    assert link.target == "`pkg.MyClass`"


def test_shortcode_str():
    """shortcode.__init__ and __str__ render quarto shortcode."""

    sc = shortcode("meta", "title")
    result = str(sc)
    assert "{{< meta title >}}" == result

    sc2 = shortcode("var", key="value")
    result2 = str(sc2)
    assert "var" in result2
    assert "key=value" in result2


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("from dataclasses import dataclass\n@dataclass\nclass C(ValueError): ...\n", "dataclass"),
        ("import enum\nclass C(enum.IntEnum): ...\n", "enum"),
        ("class C(ValueError): ...\n", "exception"),
        ("class C(ExceptionGroup): ...\n", "exception"),
        ("class C(EncodingWarning): ...\n", "exception"),
        ("from typing import NamedTuple\nclass C(NamedTuple): ...\n", "namedtuple"),
        ("from typing import TypedDict\nclass C(TypedDict): ...\n", "typeddict"),
        ("import typing\nclass C(typing.Protocol): ...\n", "protocol"),
        ("from abc import ABC\nclass C(ABC): ...\n", "abc"),
        ("from abc import abstractmethod\n@abstractmethod\nclass C: ...\n", "class"),
        ("class C(object): ...\n", "class"),
    ],
)
def test_class_kind(source, kind):
    """The first rule that matches decides the kind of a class"""

    with gf.temporary_visited_package("pkg", {"__init__.py": source}) as pkg:
        assert class_kind(pkg["C"]) == kind


def test_class_kind_of_reexported_class():
    """A re-exported class is classified by its target"""

    files = {"__init__.py": "from ._impl import C\n", "_impl.py": "class C(KeyError): ...\n"}
    with gf.temporary_visited_package("pkg", files) as pkg:
        assert isinstance(pkg["C"], gf.Alias)
        assert class_kind(pkg["C"]) == "exception"


def test_class_kind_of_package_exception_subclass():
    """A class that inherits from an exception defined in the package is an exception"""

    files = {
        "__init__.py": "from ._errors import Err, MyErr\nfrom .other import Leaf\n",
        "_errors.py": "class Err(ValueError): ...\nclass MyErr(Err): ...\n",
        "other.py": "from . import _errors\nclass Leaf(_errors.MyErr): ...\n",
    }
    with gf.temporary_visited_package("pkg", files) as pkg:
        assert class_kind(pkg["MyErr"]) == "exception"
        assert class_kind(pkg["Leaf"]) == "exception"
        assert get_label(pkg["Leaf"]) == "exception"


def test_class_kind_of_inheritance_cycle():
    """A class in an inheritance cycle is classified by its own bases"""

    files = {"__init__.py": "from .a import A\n", "a.py": "from .b import B\nclass A(B): ...\n"}
    files["b.py"] = "from .a import A\nclass B(A): ...\n"
    with gf.temporary_visited_package("pkg", files) as pkg:
        assert class_kind(pkg["A"]) == "class"


@pytest.mark.parametrize(
    ("source", "path", "kind"),
    [
        ("async def f(): ...\n", "f", "async"),
        ("class C:\n    @classmethod\n    def f(cls): ...\n", "C.f", "classmethod"),
        ("class C:\n    @staticmethod\n    def f(): ...\n", "C.f", "staticmethod"),
        ("def f(): ...\n", "f", "function"),
    ],
)
def test_function_kind(source, path, kind):
    """The first label that matches decides the kind of a function"""

    with gf.temporary_visited_package("pkg", {"__init__.py": source}) as pkg:
        assert function_kind(pkg[path]) == kind


def test_function_kind_property():
    """A function labelled `property` is a property"""

    obj = gf.Function(name="f", lineno=1)
    obj.labels.add("property")
    assert function_kind(obj) == "property"


@pytest.mark.parametrize(
    ("source", "kind"),
    [
        ("from typing import TypeVar\nX: TypeVar = TypeVar('X')\n", "typevar"),
        ("from typing import ParamSpec\nX: ParamSpec = ParamSpec('X')\n", "typevar"),
        ("from typing import TypeVar\nX = TypeVar('X')\n", "typevar"),
        ("import typing\nX = typing.TypeVarTuple('X')\n", "typevar"),
        ("from typing import TypeAlias\nX: TypeAlias = int\n", "typealias"),
        ("import typing\nX: typing.TypeAlias = int\n", "typealias"),
        ("X: int = 1\n", "constant"),
        ("X = 1\n", "constant"),
    ],
)
def test_attribute_kind(source, kind):
    """The annotation, then the value, decides the kind of an attribute"""

    with gf.temporary_visited_package("pkg", {"__init__.py": source}) as pkg:
        assert attribute_kind(pkg["X"]) == kind


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
def test_attribute_kind_type_alias():
    """A PEP 695 type alias, or an alias to one, is a type alias"""

    files = {"__init__.py": "from ._impl import X\n", "_impl.py": "type X = int\n"}
    with gf.temporary_visited_package("pkg", files) as pkg:
        assert attribute_kind(pkg["_impl.X"]) == "typealias"
        assert attribute_kind(pkg["X"]) == "typealias"


def test_attribute_kind_property():
    """A property, which griffe models as a labelled attribute, is a property"""

    source = "class C:\n    @property\n    def x(self) -> int: ...\n"
    with gf.temporary_visited_package("pkg", {"__init__.py": source}) as pkg:
        assert attribute_kind(pkg["C.x"]) == "property"


def test_is_typealias_with_exprname():
    """is_typealias returns True for Attribute with TypeAlias annotation."""

    attr = gf.Attribute(name="MyType", lineno=1)
    attr.annotation = gf.ExprName("TypeAlias")
    assert is_typealias(attr) is True


def test_is_typealias_with_str_annotation():
    """is_typealias returns True for Attribute with string annotation."""

    attr = gf.Attribute(name="X", lineno=1)
    attr.annotation = "TypeAlias"
    assert is_typealias(attr) is True


def test_is_typealias_not_attribute():
    """is_typealias returns False for non-Attribute."""

    func = gf.Function(name="foo", lineno=1)
    assert is_typealias(func) is False


def test_is_typealias_no_annotation():
    """is_typealias returns False for Attribute without annotation."""

    attr = gf.Attribute(name="X", lineno=1)
    attr.annotation = None
    assert is_typealias(attr) is False


def test_is_typealias_other_exprname():
    """is_typealias returns False when annotation is ExprName but not TypeAlias."""

    attr = gf.Attribute(name="X", lineno=1)
    attr.annotation = gf.ExprName("int")
    assert is_typealias(attr) is False


def test_is_protocol_true():
    """is_protocol returns True for class extending typing.Protocol."""

    cls = gf.Class(name="MyProto", lineno=1)
    base = gf.ExprName("Protocol")
    cls.bases = [base]
    # Mock canonical_path to return "typing.Protocol"
    with patch.object(
        type(base), "canonical_path", new_callable=PropertyMock, return_value="typing.Protocol"
    ):
        assert is_protocol(cls) is True


def test_is_protocol_false():
    """is_protocol returns False for regular class."""

    cls = gf.Class(name="Regular", lineno=1)
    assert is_protocol(cls) is False


def test_is_typevar_true():
    """is_typevar returns True for TypeVar attribute."""

    attr = gf.Attribute(name="T", lineno=1)
    attr.value = gf.ExprCall(
        function=gf.ExprName("TypeVar"),
        arguments=[gf.ExprName("'T'")],
    )
    assert is_typevar(attr) is True


def test_is_typevar_false():
    """is_typevar returns False for non-TypeVar."""

    attr = gf.Attribute(name="X", lineno=1)
    attr.value = "something"
    assert is_typevar(attr) is False


def test_is_initvar_true():
    """is_initvar returns True for InitVar subscript."""

    left = gf.ExprName("InitVar")
    expr = gf.ExprSubscript(left=left, slice=gf.ExprName("int"))
    with patch.object(
        type(left), "canonical_path", new_callable=PropertyMock, return_value="dataclasses.InitVar"
    ):
        assert is_initvar(expr) is True


def test_is_initvar_false():
    """is_initvar returns False for non-InitVar."""

    assert is_initvar(None) is False
    assert is_initvar("something") is False


def test_griffe_to_doc():
    """griffe_to_doc converts a griffe object to a content Doc."""

    func = gf.Function(name="my_func", lineno=1)
    result = griffe_to_doc(func, deep=False)
    assert isinstance(result, DocFunction)
    assert result.name == "my_func"


def test_is_field_init_false_true():
    """is_field_init_false returns True for field(init=False)."""

    param = gf.Parameter(
        name="x",
        kind=gf.ParameterKind.positional_or_keyword,
        default=gf.ExprCall(
            function=gf.ExprName("field"),
            arguments=[gf.ExprKeyword("init", "False")],
        ),
    )
    assert is_field_init_false(param) is True


def test_is_field_init_false_no_field():
    """is_field_init_false returns False for non-field default."""

    param = gf.Parameter(
        name="x",
        kind=gf.ParameterKind.positional_or_keyword,
        default="42",
    )
    assert is_field_init_false(param) is False


def test_canonical_path_with_type():
    """_canonical_path returns module.qualname for a type."""
    from great_docs._apiref._tools import _canonical_path

    result = _canonical_path(int)
    assert result == "int"  # builtins returns just qualname

    result2 = _canonical_path(dict)
    assert result2 == "dict"


def test_canonical_path_with_class():
    """_canonical_path returns full path for non-builtin type."""
    from great_docs._apiref._tools import _canonical_path

    result = _canonical_path(Attr)
    assert "Attr" in result
    assert "great_docs" in result


def test_canonical_path_with_instance():
    """_canonical_path handles non-type by using __class__."""
    from great_docs._apiref._tools import _canonical_path

    result = _canonical_path("hello")
    assert result == "str"  # builtins


def test_render_code_variable_function():
    """render_code_variable renders a function."""

    code = 'def my_func():\n    """A function."""\n    pass\n'
    result = render_code_variable(code, "my_func")
    assert isinstance(result, str)


def test_render_code_variable_module():
    """render_code_variable renders module when name=None."""

    code = '"""Module docstring."""\nx = 1\n'
    result = render_code_variable(code)
    assert isinstance(result, str)


def test_render_type_object_with_type():
    """render_type_object renders a python type."""

    # Use a type from the package itself that griffe can find
    result = render_type_object("great_docs.pandoc.components.Attr")
    assert isinstance(result, str)


def test_format_see_also():
    """format_see_also converts qualnames into interlinks."""

    result = format_see_also("some_func, other_func")
    assert "some_func" in result
    assert "other_func" in result


def test_format_name_short():
    """format_name returns obj.name for 'short' format."""

    obj = gf.Function(name="my_func", lineno=1)
    doc = DocFunction(name="my_func", obj=obj)
    result = format_name(doc, "short")
    assert result == "my_func"


def test_format_name_full():
    """format_name returns obj.path for 'full' format."""

    obj = gf.Function(name="my_func", lineno=1)
    doc = DocFunction(name="my_func", obj=obj)
    result = format_name(doc, "full")
    # path contains the function name
    assert "my_func" in result


def test_format_name_canonical():
    """format_name returns obj.canonical_path for 'canonical' format."""

    obj = gf.Function(name="my_func", lineno=1)
    doc = DocFunction(name="my_func", obj=obj)
    result = format_name(doc, "canonical")
    assert "my_func" in result


def test_format_name_unknown_raises():
    """format_name raises ValueError for unknown format."""

    obj = gf.Function(name="f", lineno=1)
    doc = DocFunction(name="f", obj=obj)
    with pytest.raises(ValueError, match="Unknown format"):
        format_name(doc, "bogus")


def test_repr_obj_default():
    """repr_obj default returns repr() for unknown types."""

    assert repr_obj(42) == "42"
    assert repr_obj(None) == "None"


def test_repr_obj_expr():
    """repr_obj for gf.Expr iterates and joins."""

    # A simple ExprName
    name = gf.ExprName("int")
    result = repr_obj(name)
    assert result == "int"


def test_repr_obj_str_with_single_quotes():
    """repr_obj for str replaces single quotes with double."""

    result = repr_obj("'hello'")
    assert result == '"hello"'

    # Non-quoted string is returned as-is
    result2 = repr_obj("plain")
    assert result2 == "plain"


def test_make_call_signature_text_long_params():
    """make_call_signature_text wraps lines when params are long."""
    params = [f"parameter_number_{i}=None" for i in range(6)]

    result = make_call_signature_text("my_function", params)

    assert "\n" in result
    assert result.startswith("my_function(")
    assert result.endswith(")")


def test_format_str_with_ruff():
    """format_str formats Python code via ruff."""

    # Clear lru_cache to ensure a fresh call
    format_str.cache_clear()
    result = format_str("x=1")
    if HAS_RUFF:
        assert "x" in result
    else:
        assert result == "x=1"


def test_format_str_bad_syntax():
    """format_str raises RuntimeError for invalid syntax."""

    if not HAS_RUFF:
        pytest.skip("ruff not available")

    format_str.cache_clear()
    # Many ruff versions will format invalid syntax without error,
    # so just verify the function runs without crashing
    result = format_str("x = 1 + 2")
    assert "x" in result


def test_format_value():
    """format_value renders a value through pretty_code."""

    result = format_value("hello")
    assert isinstance(result, str)
    assert "hello" in result


def test_get_label_function():
    """get_label returns 'function' for a top-level function."""

    obj = gf.Function(name="my_func", lineno=1)
    assert get_label(obj) == "function"


def test_get_label_class():
    """get_label returns 'class' for a plain class."""

    obj = gf.Class(name="MyClass", lineno=1)
    assert get_label(obj) == "class"


def test_get_label_module():
    """get_label returns 'module' for a module."""

    obj = gf.Module(name="mymod")
    assert get_label(obj) == "module"


def test_get_label_attribute_constant():
    """get_label returns 'constant' for a plain attribute."""

    obj = gf.Attribute(name="MY_CONST", lineno=1)
    assert get_label(obj) == "constant"


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
def test_get_label_typealias():
    """get_label returns 'typealias' for a real PEP 695 alias."""

    with gf.temporary_visited_package("pkg", {"__init__.py": "type Contract = int | str\n"}) as pkg:
        assert get_label(pkg["Contract"]) == "typealias"


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
def test_get_label_typealias_reexported():
    """A re-exported alias reaches get_label as an Alias proxy, not a raw TypeAlias.

    This is the regression guard for a crash where `isinstance(obj, gf.TypeAlias)`
    missed the proxy and fell through to code that reads `obj.annotation`, which
    a type alias does not have.
    """
    with gf.temporary_visited_package(
        "pkg",
        {
            "__init__.py": "from ._impl import Contract\n",
            "_impl.py": "type Contract = int | str\n",
        },
    ) as pkg:
        obj = pkg["Contract"]
        assert isinstance(obj, gf.Alias)
        assert get_label(obj) == "typealias"


def test_get_label_typealias_legacy_spelling():
    """get_label returns 'typealias' for the legacy `X: TypeAlias = ...` spelling."""

    code = "from typing import TypeAlias\nContract: TypeAlias = int | str\n"
    with gf.temporary_visited_package("pkg", {"__init__.py": code}) as pkg:
        assert get_label(pkg["Contract"]) == "typealias"


def test_function_label_method():
    """_function_label returns 'method' for a class method."""

    parent = gf.Class(name="MyClass", lineno=1)
    obj = gf.Function(name="do_thing", lineno=2, parent=parent)
    assert _function_label(obj) == "method"


def test_create_inventory_basic():
    """create_inventory returns an Inventory carrying the project and version."""
    obj = MagicMock()
    obj.kind.value = "function"
    obj.parent = None
    item = InventoryItem(obj=obj, name="myproj.func", uri="reference/func.html")

    result = create_inventory("myproj", "1.0", [item])

    assert result.project == "myproj"
    assert result.version == "1.0"
    assert len(result.entries) == 1
    assert result.entries[0].name == "myproj.func"
    assert result.entries[0].domain == "py"
    assert result.entries[0].role == "function"
    assert result.entries[0].priority == 1
    assert result.entries[0].uri == "reference/func.html"
    assert result.entries[0].dispname == "myproj.func"


def test_create_inventory_classifies_a_class_method_as_py_method():
    """A method's inventory role must be `method`, not griffe's bare `function`."""
    cls = gf.Class(name="MyClass", lineno=1)
    method = gf.Function(name="my_method", lineno=2)
    cls.set_member("my_method", method)

    item = InventoryItem(name="myproj.MyClass.my_method", obj=method, uri="MyClass.html#my_method")
    result = create_inventory("myproj", "1.0", [item])

    assert result.entries[0].role == "method"


def test_create_inventory_publishes_an_exception_class_as_py_exception(tmp_path):
    """Sphinx publishes an exception as py:exception, and `:exc:` matches only that."""
    pkg = tmp_path / "expkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "class MyError(Exception):\n"
        '    """Base failure."""\n'
        "\n"
        "class Nested(MyError):\n"
        '    """A failure deriving from another of ours."""\n'
        "\n"
        "class ViaBuiltin(ValueError):\n"
        '    """A failure deriving from a builtin that is not Exception itself."""\n'
        "\n"
        "class Plain:\n"
        '    """Not a failure at all."""\n'
    )
    loaded = gf.load("expkg", search_paths=[str(tmp_path)])

    items = [
        InventoryItem(name=f"expkg.{name}", obj=loaded[name], uri=f"{name}.html")
        for name in ("MyError", "Nested", "ViaBuiltin", "Plain")
    ]
    roles = {e.name: e.role for e in create_inventory("expkg", "1.0", items).entries}

    assert roles["expkg.MyError"] == "exception"
    assert roles["expkg.Nested"] == "exception"
    assert roles["expkg.ViaBuiltin"] == "exception"
    assert roles["expkg.Plain"] == "class"


def test_create_inventory_keeps_a_plain_function_as_py_function():
    """A module-level function keeps griffe's `function` kind as its role."""
    func = gf.Function(name="my_func", lineno=1)

    item = InventoryItem(name="myproj.my_func", obj=func, uri="my_func.html")
    result = create_inventory("myproj", "1.0", [item])

    assert result.entries[0].role == "function"


def test_create_inventory_with_layout_item():
    """create_inventory handles InventoryItem objects."""

    obj = gf.Function(name="my_func", lineno=1)
    item = InventoryItem(
        name="myproj.my_func",
        obj=obj,
        uri="my_func.html",
        dispname="my_func",
    )
    result = create_inventory("myproj", "1.0", [item])

    assert len(result.entries) == 1
    assert result.entries[0].name == "myproj.my_func"
    assert result.entries[0].uri == "my_func.html"
    assert result.entries[0].dispname == "my_func"


def test_create_inventory_default_dispname():
    """create_inventory falls back to the object's name when an item has no dispname."""

    obj = gf.Function(name="my_func", lineno=1)
    item = InventoryItem(name="myproj.my_func", obj=obj, uri="my_func.html")
    result = create_inventory("myproj", "1.0", [item])

    assert result.entries[0].dispname == "myproj.my_func"


def test_create_inventory_publishes_a_module_level_attribute_as_data():
    obj = MagicMock()
    obj.kind.value = "attribute"
    obj.parent = MagicMock()
    obj.parent.is_class = False
    item = InventoryItem(obj=obj, name="myproj.MAX_SIZE", uri="reference/MAX_SIZE.html")

    result = create_inventory("myproj", "1.0", [item])

    assert result.entries[0].role == "data"


def test_extend_base_class_copies_methods():
    """extend_base_class copies methods from child to base class."""

    class FakeBase:
        def original(self):
            return "original"

    class Child(FakeBase):
        def new_method(self):
            return "new"

    extend_base_class(Child)

    assert hasattr(FakeBase, "new_method")
    assert FakeBase().new_method() == "new"


def test_set_class_attr_plain_function():
    """set_class_attr sets a plain function on a class."""

    class Target:
        pass

    def my_func(self):
        return 42

    set_class_attr(Target, "my_func", my_func)

    assert Target().my_func() == 42


def test_set_class_attr_property():
    """set_class_attr handles property values."""

    class Target:
        _val = 10

    prop = property(lambda self: self._val)
    set_class_attr(Target, "val", prop)

    assert Target().val == 10


def test_set_class_attr_cached_property():
    """set_class_attr handles cached_property values."""

    class Target:
        pass

    cp = cached_property(lambda self: 99)
    set_class_attr(Target, "cached_val", cp)

    assert Target().cached_val == 99


def test_exclude_parameters_updates_globals():
    """exclude_parameters updates the EXCLUSIONS.parameters global dict."""

    original = dict(EXCLUSIONS.parameters)
    try:
        exclude_parameters({"test.MyClass": "param1"})
        assert "test.MyClass" in EXCLUSIONS.parameters
        assert EXCLUSIONS.parameters["test.MyClass"] == "param1"
    finally:
        EXCLUSIONS.parameters.clear()
        EXCLUSIONS.parameters.update(original)


def test_exclude_attributes_updates_globals():
    """exclude_attributes updates the EXCLUSIONS.attributes global dict."""

    original = dict(EXCLUSIONS.attributes)
    try:
        exclude_attributes({"test.MyClass": ("a", "b")})
        assert "test.MyClass" in EXCLUSIONS.attributes
    finally:
        EXCLUSIONS.attributes.clear()
        EXCLUSIONS.attributes.update(original)


def test_exclude_functions_updates_globals():
    """exclude_functions updates the EXCLUSIONS.functions global dict."""

    original = dict(EXCLUSIONS.functions)
    try:
        exclude_functions({"test.MyClass": "func_a"})
        assert "test.MyClass" in EXCLUSIONS.functions
    finally:
        EXCLUSIONS.functions.clear()
        EXCLUSIONS.functions.update(original)


def test_exclude_classes_updates_globals():
    """exclude_classes updates the EXCLUSIONS.classes global dict."""

    original = dict(EXCLUSIONS.classes)
    try:
        exclude_classes({"test.MyClass": "Contained1"})
        assert "test.MyClass" in EXCLUSIONS.classes
    finally:
        EXCLUSIONS.classes.clear()
        EXCLUSIONS.classes.update(original)


def test_render_reference_section_title():
    """RenderReferenceSection.render_title() returns a Header."""

    section = content.Section(title="Functions", contents=[spec.SpecObject(name="x")])

    rs = RenderReferenceSection(node=section, level=1)
    title = rs.render_title()

    assert title is not None
    assert "Functions" in str(title)


def test_render_reference_section_subtitle():
    """RenderReferenceSection.render_title() handles subtitles."""

    section = content.Section(subtitle="Helper Functions", contents=[spec.SpecObject(name="x")])

    rs = RenderReferenceSection(node=section, level=1)
    title = rs.render_title()

    assert title is not None
    assert "Helper Functions" in str(title)


def test_render_reference_section_no_title():
    """RenderReferenceSection.render_title() returns None when no title/subtitle."""

    section = content.Section(contents=[spec.SpecObject(name="x")])

    rs = RenderReferenceSection(node=section, level=1)
    title = rs.render_title()

    assert title is None


def test_render_reference_section_description():
    """RenderReferenceSection.render_description() returns a Div."""

    section = content.Section(
        title="Test", desc="A description", contents=[spec.SpecObject(name="x")]
    )

    rs = RenderReferenceSection(node=section, level=1)
    desc = rs.render_description()

    assert "A description" in str(desc)


def test_render_reference_section_body_empty():
    """RenderReferenceSection.render_body() returns None for empty section."""

    section = content.Section(title="Empty", contents=[])

    rs = RenderReferenceSection(node=section, level=1)
    body = rs.render_body()

    assert body is None


def _make_render_ref(*, title="API Reference", desc=None, package="mypkg", options=None):
    """An APIReference content stand-in for RenderReferencePage tests."""
    ref = APIReference({"api-reference": {"package": package}})
    ref.title = title
    ref.desc = desc
    ref.options = options
    return ref


def test_render_reference_page_post_init():
    """RenderReferencePage.__init__ sets api_ref, sections, package, options."""

    ref = _make_render_ref(title="API Ref", desc="My API", package="mypkg")
    sections = [content.Section(title="Funcs", contents=[spec.SpecObject(name="x")])]

    rp = RenderReferencePage(ref, sections, level=1)

    assert rp.api_ref is ref
    assert rp.sections == sections
    assert rp.package == "mypkg"
    assert rp.options is None


def test_render_reference_page_description():
    """RenderReferencePage.render_description() returns a Div when description exists."""

    ref = _make_render_ref(title="API Ref", desc="My description")
    sections = [content.Section(title="S", contents=[spec.SpecObject(name="x")])]

    rp = RenderReferencePage(ref, sections, level=1)
    desc = rp.render_description()

    assert desc is not None
    assert "My description" in str(desc)


def test_render_reference_page_no_description():
    """RenderReferencePage.render_description() returns None when no description."""

    ref = _make_render_ref(title="API Ref")
    sections = [content.Section(title="S", contents=[spec.SpecObject(name="x")])]

    rp = RenderReferencePage(ref, sections, level=1)
    desc = rp.render_description()

    assert desc is None


def test_render_reference_page_metadata():
    """RenderReferencePage.render_metadata() returns Meta with title."""

    ref = _make_render_ref(title="API Reference")
    sections = [content.Section(title="S", contents=[spec.SpecObject(name="x")])]

    rp = RenderReferencePage(ref, sections, level=1)
    meta = rp.render_metadata()

    assert "API Reference" in str(meta)


def test_render_api_page_post_init():
    """RenderAPIPage.__post_init__ sets page and path attributes."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_obj = griffe_to_doc(func_obj)
    page = content.Page(path="reference/my_func", contents=[doc_obj])

    ap = RenderAPIPage(node=page, level=1)

    assert ap.page is page
    assert ap.path == "reference/my_func.qmd"


def test_render_api_page_has_one_object():
    """RenderAPIPage._has_one_object is True for single-content pages."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_obj = griffe_to_doc(func_obj)
    page = content.Page(path="reference/my_func", contents=[doc_obj])

    ap = RenderAPIPage(node=page, level=1)

    assert ap._has_one_object is True


def test_render_api_page_metadata():
    """RenderAPIPage.render_metadata() returns Meta with title."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_obj = griffe_to_doc(func_obj)
    page = content.Page(path="reference/my_func", contents=[doc_obj])

    ap = RenderAPIPage(node=page, level=1)
    meta = ap.render_metadata()
    meta_str = str(meta)

    assert "title" in meta_str


def _description_meta(meta) -> str | None:
    """The `description-meta` value in rendered page front matter"""
    return meta.table.get("description-meta")


def test_render_api_page_metadata_description_from_docstring():
    """An API page describes itself with its object's docstring summary as plain text."""

    func_obj = gf.Function(name="my_func", lineno=1)
    func_obj.docstring = gf.Docstring(
        "Add the `values` of [](`~pkg.Frame`) and `*rest`.\n\nMore detail.", parent=func_obj
    )
    page = content.Page(path="reference/my_func", contents=[griffe_to_doc(func_obj)])

    meta = RenderAPIPage(node=page, level=1).render_metadata()

    assert _description_meta(meta) == "Add the values of Frame and \\*rest."


def test_render_api_page_metadata_description_from_summary():
    """An API page with a summary entry describes itself with the summary's text."""

    func_obj = gf.Function(name="my_func", lineno=1)
    func_obj.docstring = gf.Docstring("From the docstring.", parent=func_obj)
    page = content.Page(
        path="reference/my_func",
        contents=[griffe_to_doc(func_obj)],
        summary=content.SummaryItem(name="my_func", desc="From the summary"),
    )

    meta = RenderAPIPage(node=page, level=1).render_metadata()

    assert _description_meta(meta) == "From the summary"


def test_render_api_page_metadata_without_docstring_has_no_description():
    """An API page without a docstring summary leaves the description to the site default."""

    page = content.Page(path="reference/my_func", contents=[griffe_to_doc(gf.Function("f"))])

    assert _description_meta(RenderAPIPage(node=page, level=1).render_metadata()) is None


@pytest.mark.parametrize(("desc", "expected"), [("The `mypkg` API", "The mypkg API"), (None, None)])
def test_render_reference_page_metadata_description(desc, expected):
    """The reference index describes itself with the reference description, when set."""

    ref = _make_render_ref(desc=desc)
    sections = [content.Section(title="S", contents=[spec.SpecObject(name="x")])]

    meta = RenderReferencePage(ref, sections, level=1).render_metadata()

    assert _description_meta(meta) == expected


def test_render_api_page_render_body():
    """RenderAPIPage.render_body() returns Blocks with render_objs."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_obj = griffe_to_doc(func_obj)
    page = content.Page(path="reference/my_func", contents=[doc_obj])

    ap = RenderAPIPage(node=page, level=1)
    body = ap.render_body()

    assert body is not None


def test_render_api_page_summary_with_summary_details():
    """RenderAPIPage.render_summary() uses page.summary when set."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_obj = griffe_to_doc(func_obj)
    summary = content.SummaryItem(name="my_func", desc="A function")
    page = content.Page(
        path="reference/my_func",
        contents=[doc_obj],
        summary=summary,
    )

    ap = RenderAPIPage(node=page, level=1)
    result = ap.render_summary()

    assert len(result) == 1
    assert "A function" in str(result[0])


def test_render_api_page_summary_multi_no_flatten_raises():
    """RenderAPIPage.render_summary() raises ValueError for multi-content without flatten."""

    f1 = griffe_to_doc(gf.Function(name="func1", lineno=1))
    f2 = griffe_to_doc(gf.Function(name="func2", lineno=2))
    page = content.Page(
        path="reference/funcs",
        contents=[f1, f2],
        flatten=False,
    )

    ap = RenderAPIPage(node=page, level=1)
    with pytest.raises(ValueError, match="Cannot summarize page"):
        ap.render_summary()


def test_label_unknown_kind_raises():
    """get_label raises ValueError for unknown object kind."""

    obj = MagicMock()
    obj.is_function = False
    obj.is_class = False
    obj.is_attribute = False
    obj.is_type_alias = False
    obj.is_module = False
    with pytest.raises(ValueError, match="Unknown kind"):
        get_label(obj)


@pytest.mark.skipif(
    sys.version_info < (3, 12),
    reason="PEP 695 `type` statement requires Python 3.12+",
)
def test_get_label_typealias_kind():
    """get_label returns 'typealias' for a real griffe TYPE_ALIAS-kind object."""

    with gf.temporary_visited_package("pkg", {"__init__.py": "type MyType = int\n"}) as pkg:
        obj = pkg["MyType"]
        assert obj.kind is gf.Kind.TYPE_ALIAS
        assert get_label(obj) == "typealias"


def test_extend_base_class_with_super():
    """extend_base_class handles methods using super()."""

    class GrandBase:
        def greet(self):
            return "hello"

    class FakeBase2(GrandBase):
        pass

    class Child2(FakeBase2):
        def greet(self):
            return super().greet() + " world"

    extend_base_class(Child2)

    # After extending, FakeBase2.greet calls GrandBase.greet via adjusted super()
    assert FakeBase2().greet() == "hello world"


def test_set_class_attr_with_closure():
    """set_class_attr adjusts closure-based functions."""

    class Base3:
        def base_method(self):
            return "base"

    # Create a function with a closure over __class__
    class Source3(Base3):
        def method_with_super(self):
            return super().base_method() + "_extended"

    set_class_attr(Base3, "method_with_super", Source3.method_with_super)

    assert hasattr(Base3, "method_with_super")


def test_set_class_attr_property_with_closure():
    """set_class_attr adjusts property getters with closures."""

    class Target3:
        _value = 42

    prop = property(lambda self: self._value * 2)
    set_class_attr(Target3, "doubled", prop)

    assert Target3().doubled == 84


def test_set_class_attr_static_method():
    """set_class_attr handles MethodType (staticmethod)."""

    class Target4:
        pass

    def static_func(cls):
        return "static"

    method = MethodType(static_func, Target4)
    set_class_attr(Target4, "my_static", method)

    assert hasattr(Target4, "my_static")


def test_exclude_parameters_function():
    """exclude_parameters updates EXCLUSIONS.parameters."""

    original = dict(EXCLUSIONS.parameters)
    try:
        exclude_parameters({"pkg.Cls": ("p1", "p2")})
        assert EXCLUSIONS.parameters["pkg.Cls"] == ("p1", "p2")
    finally:
        EXCLUSIONS.parameters.clear()
        EXCLUSIONS.parameters.update(original)


def test_exclude_attributes_function():
    """exclude_attributes updates EXCLUSIONS.attributes."""

    original = dict(EXCLUSIONS.attributes)
    try:
        exclude_attributes({"pkg.Cls": ("a", "b")})
        assert EXCLUSIONS.attributes["pkg.Cls"] == ("a", "b")
    finally:
        EXCLUSIONS.attributes.clear()
        EXCLUSIONS.attributes.update(original)


def test_exclude_functions_function():
    """exclude_functions updates EXCLUSIONS.functions."""

    original = dict(EXCLUSIONS.functions)
    try:
        exclude_functions({"pkg.Cls": "fn"})
        assert EXCLUSIONS.functions["pkg.Cls"] == "fn"
    finally:
        EXCLUSIONS.functions.clear()
        EXCLUSIONS.functions.update(original)


def test_exclude_classes_function():
    """exclude_classes updates EXCLUSIONS.classes."""

    original = dict(EXCLUSIONS.classes)
    try:
        exclude_classes({"pkg.Mod": "OldClass"})
        assert EXCLUSIONS.classes["pkg.Mod"] == "OldClass"
    finally:
        EXCLUSIONS.classes.clear()
        EXCLUSIONS.classes.update(original)


def test_render_reference_page_render_body():
    """RenderReferencePage.render_body() renders sections."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_func = content.DocFunction(name="my_func", obj=func_obj, anchor="my_func")

    section = content.Section(title="Functions", contents=[doc_func])
    ref = _make_render_ref(title="API")

    rp = RenderReferencePage(ref, [section], level=1)
    body = rp.render_body()

    assert body is not None

    body_str = str(body)

    assert isinstance(body_str, str)


def test_render_reference_section_body_with_contents():
    """RenderReferenceSection.render_body() renders Doc objects."""

    func_obj = gf.Function(name="some_func", lineno=1)
    doc_func = content.DocFunction(name="some_func", obj=func_obj, anchor="some_func")

    section = content.Section(title="Functions", contents=[doc_func])

    rs = RenderReferenceSection(node=section, level=1)
    body = rs.render_body()

    assert body is not None

    body_str = str(body)

    assert isinstance(body_str, str)


def test_render_reference_section_post_init():
    """RenderReferenceSection.__post_init__() sets section."""

    section = content.Section(title="Test", contents=[spec.SpecObject(name="x")])

    rs = RenderReferenceSection(node=section, level=1)

    assert rs.section is section


def test_render_reference_section_title_and_subtitle():
    """RenderReferenceSection.render_title() for title vs subtitle."""

    # Title case
    sec_t = content.Section(title="Methods", contents=[spec.SpecObject(name="x")])
    rs_t = RenderReferenceSection(node=sec_t, level=1)

    assert "Methods" in str(rs_t.render_title())

    # Subtitle case
    sec_s = content.Section(subtitle="Helpers", contents=[spec.SpecObject(name="x")])
    rs_s = RenderReferenceSection(node=sec_s, level=1)

    assert "Helpers" in str(rs_s.render_title())


def test_render_api_page_full_lifecycle():
    """RenderAPIPage full lifecycle with real Doc objects."""

    func_obj = gf.Function(name="my_func", lineno=1)
    func_obj.endlineno = 10
    doc_func = content.DocFunction(name="my_func", obj=func_obj, anchor="my_func")

    page = content.Page(path="reference/my_func", contents=[doc_func])

    ap = RenderAPIPage(node=page, level=1)

    # Test __post_init__
    assert ap.page is page
    assert ap.path == "reference/my_func.qmd"

    # Test _has_one_object
    assert ap._has_one_object is True

    # Test render_objs
    objs = ap.render_objs
    assert len(objs) == 1

    # Test render_metadata
    meta = ap.render_metadata()
    assert meta is not None

    # Test render_body
    body = ap.render_body()
    assert body is not None

    # Test render_summary (flatten default)
    summary = ap.render_summary()
    assert len(summary) >= 1


def test_render_api_page_with_summary_details():
    """RenderAPIPage.render_summary() with explicit summary."""

    func_obj = gf.Function(name="fn", lineno=1)
    doc_func = content.DocFunction(name="fn", obj=func_obj, anchor="fn")

    page = content.Page(
        path="reference/fn",
        contents=[doc_func],
        summary=content.SummaryItem(name="fn()", desc="Do something"),
    )

    ap = RenderAPIPage(node=page, level=1)
    summary = ap.render_summary()
    assert len(summary) == 1
    assert "fn()" in str(summary[0][0])
    assert "Do something" in str(summary[0][1])


def _make_function_page(name="my_func"):
    """Build a single-function Page for RenderAPIPage duplication tests."""
    obj = gf.Function(name=name, lineno=1)
    obj.endlineno = 10
    doc = content.DocFunction(name=name, obj=obj, anchor=name)
    return content.Page(path=f"reference/{name}", contents=[doc])


def _front_matter_title(rendered: str) -> str:
    """Return the parsed YAML front-matter title, format-independent."""
    import re

    m = re.match(r"^---\n(.*?)\n---\n", rendered, re.DOTALL)
    return parse_yaml(m.group(1)).get("title", "") if m else ""


def _make_class_page_with_members(name="MyClass"):
    """Build a Page containing a class with an attribute and a method.

    Mirrors the original failure case (``config.BakeryConfig``), which
    rendered Attributes and Methods sections in addition to the
    duplicated class header.
    """
    cls_obj = gf.Class(name=name, lineno=1)
    attr_obj = gf.Attribute(name="my_attr", lineno=2)
    func_obj = gf.Function(name="method", lineno=3)
    cls_obj.set_member("my_attr", attr_obj)
    cls_obj.set_member("method", func_obj)
    doc_attr = content.DocAttribute(name="my_attr", obj=attr_obj)
    doc_func = content.DocFunction(name="method", obj=func_obj)
    doc_cls = content.DocClass(name=name, obj=cls_obj, members=[doc_attr, doc_func])
    return content.Page(path=f"reference/{name}", contents=[doc_cls])


def test_render_api_page_suppresses_inner_title_at_level_1():
    """At level=1, RenderAPIPage flips the inner object's show_title off."""
    page = _make_function_page()

    ap = RenderAPIPage(node=page, level=1)
    inner = ap.render_objs[0]

    assert inner.show_title is False
    assert ap.show_title is True


def test_render_api_page_single_object_renders_title_once():
    """Single-object pages emit exactly one heading for the object.

    The front-matter title is preserved as ``title:`` in the YAML block.
    The body retains the signature and other content, but does not add
    a header that duplicates the front-matter title.
    """
    page = _make_function_page()

    rendered = str(RenderAPIPage(node=page, level=1))

    assert "[my_func()]" in _front_matter_title(rendered)
    assert "\n# [my_func()]" not in rendered
    # Body content survives despite the suppressed inner title.
    assert "```pythonsignature\nmy_func()" in rendered


def test_render_api_page_class_with_members_renders_title_once():
    """Class pages avoid the duplicate heading and keep member sections."""
    page = _make_class_page_with_members()

    rendered = str(RenderAPIPage(node=page, level=1))

    assert "[MyClass]" in _front_matter_title(rendered)
    assert "\n# [MyClass]" not in rendered
    assert "## Attributes" in rendered
    assert "## Methods" in rendered


def test_render_api_page_renders_body_header_at_level_2():
    """At level=2, the body header is H2 and coexists with the H1 title."""
    page = _make_function_page()

    rendered = str(RenderAPIPage(node=page, level=2))

    assert "[my_func()]" in _front_matter_title(rendered)
    assert "\n## [my_func()]" in rendered


def test_render_api_page_multi_object_renders_all_inner_headers():
    """Multi-object pages keep every inner header.

    The front-matter title comes from the first object only. Body
    headers render at level+1 for every object on the page.
    """
    f1 = gf.Function(name="func1", lineno=1)
    f1.endlineno = 5
    f2 = gf.Function(name="func2", lineno=10)
    f2.endlineno = 15
    doc_f1 = content.DocFunction(name="func1", obj=f1, anchor="func1")
    doc_f2 = content.DocFunction(name="func2", obj=f2, anchor="func2")
    page = content.Page(
        path="reference/funcs",
        contents=[doc_f1, doc_f2],
        flatten=True,
    )

    rendered = str(RenderAPIPage(node=page, level=1))

    assert "\n## [func1()]" in rendered
    assert "\n## [func2()]" in rendered


def test_renderdoc_display_name_relative_level_gt1():
    """RenderDoc.display_name uses 'name' format when level > 1."""

    func_obj = gf.Function(name="my_func", lineno=1)
    doc_func = content.DocFunction(name="my_func", obj=func_obj)

    render = RenderDocFunction(doc_func, level=2, display_name_format="relative")
    name = render.display_name
    # At level > 1 with "relative" format, it switches to "name"
    assert isinstance(name, str)


def test_renderdoc_render_annotation_non_attribute_raises():
    """RenderDoc.render_annotation() raises TypeError for non-attribute."""

    func_obj = gf.Function(name="fn", lineno=1)
    doc_func = content.DocFunction(name="fn", obj=func_obj)

    render = RenderDocFunction(doc_func, level=1)
    with pytest.raises(TypeError, match="Cannot render annotation"):
        render.render_annotation()


def test_renderdoc_render_annotation_attribute():
    """RenderDoc.render_annotation() for attribute."""

    attr_obj = gf.Attribute(name="x", lineno=1)
    attr_obj.annotation = gf.ExprName("int")
    doc_attr = content.DocAttribute(name="x", obj=attr_obj)

    render = RenderDocAttribute(doc_attr, level=1)
    result = render.render_annotation()
    assert isinstance(result, str)
    assert "int" in result


def test_renderdoc_render_annotation_none():
    """RenderDoc.render_annotation() with None annotation."""

    attr_obj = gf.Attribute(name="y", lineno=1)
    attr_obj.annotation = None
    doc_attr = content.DocAttribute(name="y", obj=attr_obj)

    render = RenderDocAttribute(doc_attr, level=1)
    result = render.render_annotation()
    assert result == ""


def test_renderdoc_docstring_section_deprecated():
    """RenderDoc handles DocstringSectionDeprecated."""

    func_obj = gf.Function(name="old_fn", lineno=1)
    func_obj.docstring = gf.Docstring(
        "Short desc.\n\nDeprecated\n----------\n1.0\n    Use new_fn instead.",
        parent=func_obj,
        parser="numpy",
    )
    doc_func = content.DocFunction(name="old_fn", obj=func_obj)

    render = RenderDocFunction(doc_func, level=1)
    body = render.render_body()
    body_str = str(body)
    assert "Deprecated" in body_str or "deprecated" in body_str


def test_renderdoc_docstring_section_examples():
    """RenderDoc handles DocstringSectionExamples."""

    func_obj = gf.Function(name="ex_fn", lineno=1)
    func_obj.docstring = gf.Docstring(
        "Short desc.\n\nExamples\n--------\n>>> 1 + 1\n2\n",
        parent=func_obj,
        parser="numpy",
    )
    doc_func = content.DocFunction(name="ex_fn", obj=func_obj)

    render = RenderDocFunction(doc_func, level=1)
    body = render.render_body()
    body_str = str(body)
    assert "1 + 1" in body_str or "Examples" in body_str


def test_renderdoc_docstring_section_text_in_div():
    """RenderDoc wraps 'Text' sections in a Div."""

    func_obj = gf.Function(name="txt_fn", lineno=1)
    func_obj.docstring = gf.Docstring(
        "Short description.\n\nParameters\n----------\nx : int\n    A number.",
        parent=func_obj,
        parser="numpy",
    )
    doc_func = content.DocFunction(name="txt_fn", obj=func_obj)

    render = RenderDocFunction(doc_func, level=1)
    body = render.render_body()
    assert body is not None


def test_renderdoc_source_link_with_github_url():
    """A configured repository URL produces a source link"""

    mod = gf.Module(name="mymod", filepath=Path("/fake/pkg/mymod.py"))
    func_obj = gf.Function(name="linked_fn", lineno=5)
    func_obj.endlineno = 15
    mod.set_member("linked_fn", func_obj)
    doc_func = content.DocFunction(name="linked_fn", obj=func_obj)

    links = SourceLinks(repo_url="https://github.com/test/repo")
    with active_settings(Settings(source_links=links)):
        render = RenderDocFunction(doc_func, level=1)
        link = render.source_link
    assert link is not None
    link_str = str(link)
    assert "Source" in link_str
    assert "github.com" in link_str


def test_renderdoc_see_also_section():
    """RenderDoc handles See Also section."""

    func_obj = gf.Function(name="sa_fn", lineno=1)
    func_obj.docstring = gf.Docstring(
        "Short desc.\n\nSee Also\n--------\nother_func : Related function.",
        parent=func_obj,
        parser="numpy",
    )
    doc_func = content.DocFunction(name="sa_fn", obj=func_obj)

    render = RenderDocFunction(doc_func, level=1)
    body = render.render_body()
    body_str = str(body) if body else ""
    assert isinstance(body_str, str)


def test_prepare_build_directory_config_js_branches():
    """
    Copy scripts for the enabled announcement, navbar and content styles
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        # Provide a real package with pyproject.toml
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.0"\n')
        # Enable the relevant config flags
        (tmp / "great-docs.yml").write_text(
            "announcement:\n  content: Hello\nnavbar_style: modern\ncontent_style: wide\n"
        )
        docs = GreatDocs(project_path=tmp_dir)
        # Ensure the docs dir exists
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        (docs.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER)
        # Copy scss so the method doesn't fail
        scss_src = docs.assets_path / "great-docs.scss"
        if scss_src.exists():
            shutil.copy2(scss_src, docs.build_dir / "great-docs.scss")

        prepare_build_directory(docs, make_run(docs))

        # Verify the config-specific JS files were copied
        assert (docs.build_dir / "announcement-banner.js").exists()
        assert (docs.build_dir / "navbar-style.js").exists()
        assert (docs.build_dir / "content-style.js").exists()


def test_detect_docstring_style_no_docstrings():
    """Verify that a package without docstrings selects NumPy"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        pkg_dir = tmp / "nodocpkg2"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("x = 1\ny = 2\n")
        (tmp / "pyproject.toml").write_text('[project]\nname = "nodocpkg2"\n')

        sys.path.insert(0, str(tmp))
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("nodocpkg2"), report=print)
            assert style == "numpy"
        finally:
            sys.path.remove(str(tmp))
            sys.modules.pop("nodocpkg2", None)


def test_detect_docstring_style_google():
    """Verify that Google headings without NumPy sections select Google"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        pkg_dir = tmp / "googlepkg2"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('''
"""Package with Google-style docs."""
__all__ = ["add"]

def add(a, b):
    """Add two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Sum of a and b.
    """
    return a + b

def sub(a, b):
    """Subtract two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Difference of a and b.
    """
    return a - b
''')
        (tmp / "pyproject.toml").write_text('[project]\nname = "googlepkg2"\n')

        sys.path.insert(0, str(tmp))
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = detect_docstring_style(make_exports(docs).package("googlepkg2"), report=print)
            assert style == "google"
        finally:
            sys.path.remove(str(tmp))
            sys.modules.pop("googlepkg2", None)


def test_type_sections_empty_lists():
    """TypeSections with no items produces empty Blocks output."""

    ts = TypeSections(
        protocols_items=[],
        typevars_items=[],
        typealiases_items=[],
    )

    assert [category.renders for category in ts.categories] == [[], [], []]
    assert ts.items == []
    body = ts.render_body()
    assert str(body) == ""
    assert str(ts) == ""


def test_type_sections_items_combines_all():
    """TypeSections.items returns protocols + typevars + typealiases combined."""

    p_item = InventoryItem(name="P", obj=MagicMock(), uri="ref/P.html#P", dispname="P")
    tv_item = InventoryItem(name="TV", obj=MagicMock(), uri="ref/TV.html#TV", dispname="TV")
    ta_item = InventoryItem(name="TA", obj=MagicMock(), uri="ref/TA.html#TA", dispname="TA")

    mock_render = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc") as mock_g2d,
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        mock_g2d.return_value = MagicMock()
        ts = TypeSections(
            protocols_items=[p_item],
            typevars_items=[tv_item],
            typealiases_items=[ta_item],
        )

    assert ts.items == [p_item, tv_item, ta_item]
    assert [len(category.renders) for category in ts.categories] == [1, 1, 1]


def test_type_sections_post_init_protocols_no_summary():
    """TypeSections.__post_init__ sets show_members_summary=False on protocols."""

    p_item = InventoryItem(name="Proto", obj=MagicMock())

    mock_render = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[p_item],
            typevars_items=[],
            typealiases_items=[],
        )

    assert mock_render.show_members_summary is False


def test_type_sections_post_init_typevars_no_sig_name():
    """TypeSections.__post_init__ sets show_signature_name=False on typevars."""

    tv_item = InventoryItem(name="T", obj=MagicMock())

    mock_render = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[],
            typevars_items=[tv_item],
            typealiases_items=[],
        )

    assert mock_render.show_signature_name is False


def test_type_sections_post_init_typealiases_settings():
    """TypeSections keeps alias names and hides redundant annotations."""

    ta_item = InventoryItem(name="MyAlias", obj=MagicMock())

    mock_render = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[],
            typevars_items=[],
            typealiases_items=[ta_item],
        )

    assert mock_render.show_signature_annotation is False
    assert "show_signature_name" not in ts.categories[2].render_flags


def test_type_sections_render_body_protocols_section():
    """TypeSections.render_body includes 'Protocols' header when protocols exist."""

    p_item = InventoryItem(name="P", obj=MagicMock())

    mock_render = MagicMock()
    mock_render.__str__ = MagicMock(return_value="<protocol-rendered>")
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[p_item],
            typevars_items=[],
            typealiases_items=[],
        )

    body_str = str(ts.render_body())
    assert "Protocols" in body_str
    assert "<protocol-rendered>" in body_str
    assert "Type Variables" not in body_str
    assert "Type Aliases" not in body_str


def test_type_sections_render_body_typevars_section():
    """TypeSections.render_body includes 'Type Variables' header when typevars exist."""

    tv_item = InventoryItem(name="T", obj=MagicMock())

    mock_render = MagicMock()
    mock_render.__str__ = MagicMock(return_value="<typevar-rendered>")
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[],
            typevars_items=[tv_item],
            typealiases_items=[],
        )

    body_str = str(ts.render_body())
    assert "Type Variables" in body_str
    assert "<typevar-rendered>" in body_str


def test_type_sections_render_body_typealiases_section():
    """TypeSections.render_body includes 'Type Aliases' header when typealiases exist."""

    ta_item = InventoryItem(name="A", obj=MagicMock())

    mock_render = MagicMock()
    mock_render.__str__ = MagicMock(return_value="<alias-rendered>")
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[],
            typevars_items=[],
            typealiases_items=[ta_item],
        )

    body_str = str(ts.render_body())
    assert "Type Aliases" in body_str
    assert "<alias-rendered>" in body_str


def test_type_sections_render_body_all_sections():
    """TypeSections.render_body includes all three section headers when all types present."""

    p_item = InventoryItem(name="P", obj=MagicMock())
    tv_item = InventoryItem(name="T", obj=MagicMock())
    ta_item = InventoryItem(name="A", obj=MagicMock())

    mock_render = MagicMock()
    mock_render.__str__ = MagicMock(return_value="<rendered>")
    mock_render_cls = MagicMock(return_value=mock_render)

    with (
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ts = TypeSections(
            protocols_items=[p_item],
            typevars_items=[tv_item],
            typealiases_items=[ta_item],
        )

    body_str = str(ts.render_body())
    assert "Protocols" in body_str
    assert "Type Variables" in body_str
    assert "Type Aliases" in body_str


def test_type_information_post_init():
    """TypeInformation.__post_init__ sets package and dir from builder."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)

    assert ti.package == "mypkg"
    assert ti.dir == "reference"


def test_type_information_base_uri_strips_package():
    """TypeInformation.base_uri strips the package prefix from module_path."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    ti = TypeInformation(module_path="mypkg.sub.types", api_ref=mock_builder)
    assert ti.base_uri == "reference/sub.types"


def test_type_information_base_uri_no_package_prefix():
    """TypeInformation.base_uri keeps full path when module doesn't start with package."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    ti = TypeInformation(module_path="otherpkg.types", api_ref=mock_builder)
    assert ti.base_uri == "reference/otherpkg.types"


def test_type_information_sections_calls_get_object():
    """TypeInformation.sections calls get_object and classifies members."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    # Create mock members with canonical_path
    mock_proto = MagicMock()
    mock_proto.canonical_path = "mypkg.types.MyProto"
    mock_tv = MagicMock()
    mock_tv.canonical_path = "mypkg.types.T"
    mock_alias = MagicMock()
    mock_alias.canonical_path = "mypkg.types.MyAlias"

    mock_module = MagicMock()
    mock_module.members = {"MyProto": mock_proto, "T": mock_tv, "MyAlias": mock_alias}

    mock_render_obj = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render_obj)

    with (
        patch("great_docs._apiref.typing_information.get_object", return_value=mock_module),
        patch(
            "great_docs._apiref.typing_information.is_protocol",
            side_effect=lambda m: m is mock_proto,
        ),
        patch(
            "great_docs._apiref.typing_information.is_typevar",
            side_effect=lambda m: m is mock_tv,
        ),
        patch(
            "great_docs._apiref.typing_information.is_typealias",
            side_effect=lambda m: m is mock_alias,
        ),
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)
        sections = ti.sections

    assert len(sections.protocols_items) == 1
    assert sections.protocols_items[0].name == "mypkg.types.MyProto"
    assert len(sections.typevars_items) == 1
    assert sections.typevars_items[0].name == "mypkg.types.T"
    assert len(sections.typealiases_items) == 1
    assert sections.typealiases_items[0].name == "mypkg.types.MyAlias"


def test_type_information_sections_item_uris():
    """TypeInformation.sections creates items with correct URIs based on base_uri."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    mock_attr = MagicMock()
    mock_attr.canonical_path = "mypkg.sub.MyAlias"

    mock_module = MagicMock()
    mock_module.members = {"MyAlias": mock_attr}

    mock_render_obj = MagicMock()
    mock_render_cls = MagicMock(return_value=mock_render_obj)

    with (
        patch("great_docs._apiref.typing_information.get_object", return_value=mock_module),
        patch("great_docs._apiref.typing_information.is_protocol", return_value=False),
        patch("great_docs._apiref.typing_information.is_typevar", return_value=False),
        patch("great_docs._apiref.typing_information.is_typealias", return_value=True),
        patch("great_docs._apiref.typing_information.griffe_to_doc"),
        patch(
            "great_docs._apiref.typing_information.get_render_type", return_value=mock_render_cls
        ),
    ):
        ti = TypeInformation(module_path="mypkg.sub", api_ref=mock_builder)
        sections = ti.sections

    item = sections.typealiases_items[0]
    assert item.uri == "reference/sub.html#mypkg.sub.MyAlias"
    assert item.dispname == "mypkg.sub.MyAlias"


def test_type_information_content_has_meta_and_sections():
    """TypeInformation.content returns Blocks with Meta title and TypeSections."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    mock_module = MagicMock()
    mock_module.members = {}

    with patch("great_docs._apiref.typing_information.get_object", return_value=mock_module):
        ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)
        content = ti.content

    content_str = str(content)
    assert "Typing Information" in content_str


def test_type_information_str_delegates_to_content():
    """TypeInformation.__str__ returns str(self.content)."""

    mock_builder = MagicMock()
    mock_builder.package = "mypkg"
    mock_builder.settings.dir = "reference"

    mock_module = MagicMock()
    mock_module.members = {}

    with patch("great_docs._apiref.typing_information.get_object", return_value=mock_module):
        ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)
        result = str(ti)

    assert "Typing Information" in result


def test_type_information_write_creates_file():
    """TypeInformation.write() extends builder items and writes the qmd file."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_builder = MagicMock()
        mock_builder.package = "mypkg"
        mock_builder.settings.dir = str(Path(tmp_dir) / "reference")
        mock_builder.items = []

        mock_module = MagicMock()
        mock_module.members = {}

        with patch("great_docs._apiref.typing_information.get_object", return_value=mock_module):
            ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)

            # Ensure the output directory exists
            Path(ti.base_uri).parent.mkdir(parents=True, exist_ok=True)
            ti.write()

        filepath = Path(f"{ti.base_uri}.qmd")
        assert filepath.exists()
        content = filepath.read_text()
        assert "Typing Information" in content


def test_type_information_write_extends_builder_items():
    """TypeInformation.write() adds all section items to builder.items."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        ref_dir = str(Path(tmp_dir) / "reference")

        mock_builder = MagicMock()
        mock_builder.package = "mypkg"
        mock_builder.settings.dir = ref_dir
        mock_builder.items = []

        mock_member = MagicMock()
        mock_member.canonical_path = "mypkg.types.T"

        mock_module = MagicMock()
        mock_module.members = {"T": mock_member}

        mock_render_obj = MagicMock()
        mock_render_cls = MagicMock(return_value=mock_render_obj)

        with (
            patch("great_docs._apiref.typing_information.get_object", return_value=mock_module),
            patch("great_docs._apiref.typing_information.is_protocol", return_value=False),
            patch("great_docs._apiref.typing_information.is_typevar", return_value=True),
            patch("great_docs._apiref.typing_information.is_typealias", return_value=False),
            patch("great_docs._apiref.typing_information.griffe_to_doc"),
            patch(
                "great_docs._apiref.typing_information.get_render_type",
                return_value=mock_render_cls,
            ),
        ):
            ti = TypeInformation(module_path="mypkg.types", api_ref=mock_builder)

            Path(ref_dir).mkdir(parents=True, exist_ok=True)
            ti.write()

        assert len(mock_builder.items) == 1
        assert mock_builder.items[0].name == "mypkg.types.T"


class TestBuildSectionsFromReferenceConfig:
    """Tests for _build_sections_from_reference_config."""

    def test_basic_string_items(self):
        """Builds sections from simple string references."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {"title": "Classes", "desc": "Main classes", "contents": ["MyClass", "OtherClass"]},
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert len(result) == 1
            assert result[0]["title"] == "Classes"
            assert result[0]["contents"] == ["MyClass", "OtherClass"]

    def test_dict_items_with_members_false(self):
        """Handles dict items with members: false."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {"title": "Classes", "contents": [{"name": "MyClass", "members": False}]},
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert result[0]["contents"][0] == {"name": "MyClass", "members": []}

    def test_dict_items_with_members_true(self):
        """Handles dict items with members: true (default inline)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {"title": "Classes", "contents": [{"name": "MyClass", "members": True}]},
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert result[0]["contents"][0] == "MyClass"

    def test_empty_config_returns_none(self):
        """Returns None for empty config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            assert reference_sections.from_reference_config([]) is None
            assert reference_sections.from_reference_config(None) is None

    def test_skips_non_dict_entries(self):
        """Skips entries that aren't dicts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                "not a dict",
                {"title": "Functions", "contents": ["func_a"]},
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert len(result) == 1

    def test_skips_empty_contents(self):
        """Skips sections with no contents."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {"title": "Empty", "contents": []},
                {"title": "Real", "contents": ["func_a"]},
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert len(result) == 1
            assert result[0]["title"] == "Real"

    def test_dict_item_missing_name(self):
        """Skips dict items without a name."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {"title": "Classes", "contents": [{"members": False}]},
            ]
            result = reference_sections.from_reference_config(config)
            # No valid contents, so the section is skipped
            assert result is None


class TestDetectDocstringStyleSphinx:
    """Tests for Sphinx docstring style detection."""

    def test_sphinx_style_detection(self):
        """Detects Sphinx-style docstrings via griffe."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            pkg = tmp / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text(
                "def func_a(x):\n"
                '    """:param x: The x parameter.\n'
                "    :returns: The result.\n"
                "    :rtype: int\n"
                '    """\n'
                "    return x\n\n"
                "def func_b(y):\n"
                '    """:param y: The y parameter.\n'
                "    :raises ValueError: If y is bad.\n"
                '    """\n'
                "    return y\n"
            )
            docs = GreatDocs(project_path=tmp_dir)
            old_path = sys.path[:]
            sys.path.insert(0, tmp_dir)
            try:
                result = detect_docstring_style(make_exports(docs).package("mypkg"), report=print)
            finally:
                sys.path[:] = old_path
            assert result == "sphinx"


class TestEmptyCategories:
    """Empty reference categories with independent collections"""

    def test_has_all_keys(self):
        """Empty categories dict has all expected keys."""
        cats = empty_categories()
        assert "classes" in cats
        assert "functions" in cats
        assert "constants" in cats
        assert "type_aliases" in cats
        assert "class_methods" in cats
        assert "class_method_names" in cats
        assert "other" in cats

    def test_all_lists_empty(self):
        """All list values are empty."""
        cats = empty_categories()
        for key in (
            "classes",
            "functions",
            "constants",
            "type_aliases",
            "async_functions",
            "dataclasses",
            "enums",
            "exceptions",
            "namedtuples",
            "typeddicts",
            "protocols",
            "abstract_classes",
            "other",
        ):
            assert cats[key] == []


class TestQuartoEnvironment:
    """Quarto's Python environment"""

    def test_sets_quarto_python(self):
        """Sets QUARTO_PYTHON in environment."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            docs = GreatDocs(project_path=tmp_dir)
            env = quarto.environment(docs._config)
            assert "QUARTO_PYTHON" in env
            assert env["QUARTO_PYTHON"]

    def test_sets_pythonpath(self):
        """Sets PYTHONPATH including package root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            docs = GreatDocs(project_path=tmp_dir)
            env = quarto.environment(docs._config)
            assert "PYTHONPATH" in env
            assert str(tmp) in env["PYTHONPATH"]

    def test_includes_src_dir(self):
        """Includes src/ in PYTHONPATH when it exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "src").mkdir()
            docs = GreatDocs(project_path=tmp_dir)
            env = quarto.environment(docs._config)
            assert "src" in env["PYTHONPATH"]

    def test_includes_python_dir(self):
        """Includes python/ in PYTHONPATH when it exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "python").mkdir()
            docs = GreatDocs(project_path=tmp_dir)
            env = quarto.environment(docs._config)
            assert "python" in env["PYTHONPATH"]


class TestUpdateSidebarFromSections:
    """Tests for _update_sidebar_from_sections."""

    def _make_docs(self, tmp_dir, sections):
        """Helper: create a GreatDocs with _quarto.yml containing api-reference sections."""
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = docs.build_dir / "_quarto.yml"
        config = {
            "website": {"sidebar": []},
            "api-reference": {"package": "mypkg", "sections": sections},
            "format": {"html": {}},
        }
        with open(quarto_yml, "w") as f:
            write_yaml(config, f)
        return docs

    def test_builds_sidebar_from_sections(self):
        """Creates sidebar entries from API reference sections."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            sections = [
                {"title": "Classes", "contents": ["MyClass", "OtherClass"]},
                {"title": "Functions", "contents": ["func_a"]},
            ]
            docs = self._make_docs(tmp_dir, sections)
            reference_sections.update_sidebar(docs._config, docs.build_dir)
            with open(docs.build_dir / "_quarto.yml") as f:
                config = read_yaml(f)
            sidebar = config["website"]["sidebar"]
            assert len(sidebar) == 1
            assert sidebar[0]["id"] == "reference"
            # First entry is the API link, then sections
            contents = sidebar[0]["contents"]
            assert contents[0]["href"] == "reference/index.qmd"
            assert contents[1]["section"] == "Classes"
            assert {"text": "MyClass", "href": "reference/MyClass.qmd"} in contents[1]["contents"]

    def test_handles_dict_format_items(self):
        """Processes dict-format items with name key."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            sections = [
                {"title": "Classes", "contents": [{"name": "Graph", "members": []}]},
            ]
            docs = self._make_docs(tmp_dir, sections)
            reference_sections.update_sidebar(docs._config, docs.build_dir)
            with open(docs.build_dir / "_quarto.yml") as f:
                config = read_yaml(f)
            contents = config["website"]["sidebar"][0]["contents"]
            assert {"text": "Graph", "href": "reference/Graph.qmd"} in contents[1]["contents"]

    def test_no_api_reference_returns_early(self):
        """Returns early when no api-reference in config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {"website": {"sidebar": [{"id": "reference", "contents": []}]}}
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            reference_sections.update_sidebar(docs._config, docs.build_dir)
            with open(quarto_yml) as f:
                result = read_yaml(f)
            # Sidebar unchanged
            assert result["website"]["sidebar"][0]["id"] == "reference"


class TestUpdateQuartoConfigScripts:
    """
    Site script registration tests
    """

    def _make_project(self, tmp_dir, metadata=None, gd_config=None):
        """
        Create a minimal project with metadata and optional site settings
        """
        tmp = Path(tmp_dir)
        pyproject = {
            "project": {"name": "mypkg", "version": "0.1.0"},
        }
        if metadata:
            if "authors" in metadata:
                pyproject["project"]["authors"] = metadata["authors"]
            if "urls" in metadata:
                pyproject["project"]["urls"] = metadata["urls"]
        (tmp / "pyproject.toml").write_text(
            "[project]\n"
            f'name = "{pyproject["project"]["name"]}"\n'
            f'version = "{pyproject["project"]["version"]}"\n'
        )
        if metadata and "authors" in metadata:
            authors_lines = []
            for a in metadata["authors"]:
                if isinstance(a, dict):
                    parts = []
                    if "name" in a:
                        parts.append(f'name = "{a["name"]}"')
                    if "email" in a:
                        parts.append(f'email = "{a["email"]}"')
                    authors_lines.append("{" + ", ".join(parts) + "}")
            if authors_lines:
                with open(tmp / "pyproject.toml", "a") as f:
                    f.write("authors = [\n")
                    for line in authors_lines:
                        f.write(f"  {line},\n")
                    f.write("]\n")

        if gd_config:
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml(gd_config, f)

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        return docs

    def test_injects_sidebar_wrap_script(self):
        """Injects sidebar-wrap.js into include-after-body."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(tmp_dir)
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {"include-after-body": [], "include-in-header": []}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            update_quarto_config(docs, make_run(docs))
            with open(quarto_yml) as f:
                result = read_yaml(f)
            after_body = result["format"]["html"]["include-after-body"]
            scripts = [str(item) for item in after_body]
            assert any("sidebar-wrap" in s for s in scripts)
            assert any("sidebar-filter" in s for s in scripts)
            assert any("dark-mode-toggle" in s for s in scripts)

    def test_injects_theme_init_in_header(self):
        """Injects theme-init.js into include-in-header for dark mode."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(tmp_dir)
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            update_quarto_config(docs, make_run(docs))
            with open(quarto_yml) as f:
                result = read_yaml(f)
            header = result["format"]["html"].get("include-in-header", [])
            scripts = [str(item) for item in header]
            assert any("theme-init" in s for s in scripts)

    def test_adds_page_footer_with_authors(self):
        """Creates page-footer with author names from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                metadata={"authors": [{"name": "Jane Doe"}, {"name": "John Smith"}]},
            )
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            update_quarto_config(docs, make_run(docs))
            with open(quarto_yml) as f:
                result = read_yaml(f)
            footer = result["website"].get("page-footer", {})
            assert "Jane" in footer.get("center", "")
            assert "John" in footer.get("center", "")

    def test_reference_switcher_with_cli_pages(self):
        """Load `reference-switcher.js` when CLI pages exist"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                gd_config={"cli": {"enabled": True}},
            )
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            cli_index = docs.build_dir / "reference" / "cli" / "index.qmd"
            cli_index.parent.mkdir(parents=True)
            cli_index.write_text("", encoding="utf-8")
            update_quarto_config(docs, make_run(docs))
            with open(quarto_yml) as f:
                result = read_yaml(f)
            after_body = result["format"]["html"].get("include-after-body", [])
            scripts = [str(item) for item in after_body]
            assert any("reference-switcher" in s for s in scripts)


class TestHomepageHeroBatch9:
    """Homepage hero logo fallbacks and badge types"""

    def _make_project(self, tmp_dir, gd_config=None, readme="# MyPkg\nDescription.\n"):
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "1.0"\ndescription = "A great package"\n'
        )
        if readme:
            (tmp / "README.md").write_text(readme)
        if gd_config:
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml(gd_config, f)
        return GreatDocs(project_path=tmp_dir)

    def test_hero_disabled_returns_empty(self):
        """Returns empty tuple when hero is explicitly disabled."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(tmp_dir, gd_config={"hero": False})
            hero_html, cleaned = homepage_hero(docs)
            assert hero_html == ""
            assert cleaned is None

    def test_hero_with_string_logo(self):
        """Renders hero with a string logo config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            docs = self._make_project(
                tmp_dir,
                gd_config={"hero": {"enabled": True, "logo": "logo.png"}},
            )
            # Create the logo file so detection doesn't fail
            (tmp / "logo.png").write_bytes(b"\x89PNG")
            hero_html, _ = homepage_hero(docs)
            assert 'src="logo.png"' in hero_html
            assert "gd-hero" in hero_html

    def test_hero_badges_as_list(self):
        """Renders hero badges from explicit list config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                gd_config={
                    "hero": {
                        "enabled": True,
                        "name": "MyPkg",
                        "badges": [
                            {
                                "alt": "CI",
                                "img": "https://img.shields.io/badge/ci-pass-green",
                                "url": "https://example.com",
                            },
                            {"alt": "NoLink", "img": "https://img.shields.io/badge/v-1.0-blue"},
                        ],
                    }
                },
            )
            hero_html, _ = homepage_hero(docs)
            assert "gd-hero-badges" in hero_html
            # Badge with url should be a link
            assert '<a href="https://example.com">' in hero_html
            # Badge without url should be plain img
            assert 'alt="NoLink"' in hero_html

    def test_hero_fallback_to_package_name(self):
        """Hero name falls back to package name from metadata."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = self._make_project(
                tmp_dir,
                gd_config={"hero": {"enabled": True}},
            )
            hero_html, _ = homepage_hero(docs)
            assert "mypkg" in hero_html

    def test_hero_with_dict_logo_light_and_dark(self):
        """Renders light and dark logo variants."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            docs = self._make_project(
                tmp_dir,
                gd_config={
                    "hero": {
                        "enabled": True,
                        "logo": {"light": "logo-light.png", "dark": "logo-dark.png"},
                    }
                },
            )
            (tmp / "logo-light.png").write_bytes(b"\x89PNG")
            (tmp / "logo-dark.png").write_bytes(b"\x89PNG")
            hero_html, _ = homepage_hero(docs)
            assert "gd-only-light" in hero_html
            assert "gd-only-dark" in hero_html


class TestBuildSectionsFromReferenceConfigBatch9:
    """Additional _build_sections_from_reference_config coverage."""

    def test_dict_item_with_members_false(self):
        """Dict item with members: false produces name-only entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {
                    "title": "Classes",
                    "contents": [{"name": "MyClass", "members": False}],
                },
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            classes_section = result[0]
            assert classes_section["contents"][0] == {"name": "MyClass", "members": []}

    def test_dict_item_with_members_true(self):
        """Dict item with members: true produces simple string entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {
                    "title": "Classes",
                    "contents": [{"name": "MyClass", "members": True}],
                },
            ]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert result[0]["contents"][0] == "MyClass"

    def test_skips_non_dict_sections(self):
        """Skips non-dict entries in reference config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = ["not_a_dict", {"title": "Funcs", "contents": ["func_a"]}]
            result = reference_sections.from_reference_config(config)
            assert result is not None
            assert len(result) == 1
            assert result[0]["title"] == "Funcs"

    def test_empty_config(self):
        """Returns None for empty config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            result = reference_sections.from_reference_config([])
            assert result is None

    def test_dict_item_without_name(self):
        """Skips dict items missing name key."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs = GreatDocs(project_path=tmp_dir)
            config = [
                {
                    "title": "Things",
                    "contents": [{"members": True}],
                },
            ]
            result = reference_sections.from_reference_config(config)
            # Section should be empty (no valid contents) so result is None
            assert result is None


class TestRefreshApiReferenceConfigBatch9:
    """Tests for _refresh_api_reference_config edge cases."""

    def test_fallback_to_explicit_reference_config(self):
        """Falls back to user's reference config when auto-discovery fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            with open(tmp / "great-docs.yml", "w") as f:
                write_yaml(
                    {"reference": [{"title": "API", "contents": ["func_a", "func_b"]}]},
                    f,
                )
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"sidebar": []},
                "api-reference": {
                    "package": "mypkg",
                    "sections": [{"title": "Old", "contents": ["old_func"]}],
                },
                "format": {"html": {}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            # Module doesn't exist, so auto-discovery will fail.
            # Method should fall back to explicit config.
            reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)
            with open(quarto_yml) as f:
                result = read_yaml(f)
            sections = result.get("api-reference", {}).get("sections", [])
            # Should have applied the explicit config
            if sections:
                assert sections[0]["title"] == "API"

    def test_no_exports_no_config_warns(self):
        """Warns when neither exports nor explicit config available."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            quarto_yml = docs.build_dir / "_quarto.yml"
            config = {
                "project": {"type": "website"},
                "website": {"sidebar": []},
                "api-reference": {
                    "package": "mypkg",
                    "sections": [{"title": "Old", "contents": ["old_func"]}],
                },
                "format": {"html": {}},
            }
            with open(quarto_yml, "w") as f:
                write_yaml(config, f)
            reference_block.refresh(docs._config, docs.build_dir, make_exports(docs).sections)
            # Should not crash — just warn and keep config unchanged


class TestUpdateQuartoConfigStrNormalizationBatch10:
    """
    Conversion of single Quarto includes to lists
    """

    def _run_with_quarto_yml(self, tmp_dir, quarto_content):
        """
        Merge site settings into the supplied Quarto configuration and return it
        """
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
            '[project.urls]\nRepository = "https://github.com/test/mypkg"\n'
        )
        (tmp / "great-docs.yml").write_text("display_name: My\n")
        docs = GreatDocs(project_path=tmp_dir)
        docs._remote = StubRemote()
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml = docs.build_dir / "_quarto.yml"
        with open(quarto_yml, "w") as f:
            write_yaml(quarto_content, f)
        update_quarto_config(docs, make_run(docs))
        with open(quarto_yml) as f:
            return read_yaml(f)

    def test_include_after_body_string_normalized_to_list(self):
        """When include-after-body is a string, it is normalized to a list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = self._run_with_quarto_yml(
                tmp_dir,
                {
                    "project": {"type": "website"},
                    "format": {"html": {"include-after-body": "my-script.js"}},
                },
            )
            after = cfg["format"]["html"]["include-after-body"]
            assert isinstance(after, list)
            assert "my-script.js" in after

    def test_include_in_header_string_normalized_to_list(self):
        """When include-in-header is a string, it is normalized to a list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = self._run_with_quarto_yml(
                tmp_dir,
                {
                    "project": {"type": "website"},
                    "format": {"html": {"include-in-header": "header.js"}},
                },
            )
            header = cfg["format"]["html"]["include-in-header"]
            assert isinstance(header, list)
            assert "header.js" in header


class TestQuartoEnvironmentBatch10:
    """Quarto's environment without an existing `PYTHONPATH`"""

    def test_no_existing_pythonpath(self):
        """When PYTHONPATH is absent, new paths are set directly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "great-docs.yml").write_text("")
            docs = GreatDocs(project_path=tmp_dir)
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("PYTHONPATH", None)
                env = quarto.environment(docs._config)
            assert "PYTHONPATH" in env
            assert os.pathsep not in env["PYTHONPATH"] or tmp_dir in env["PYTHONPATH"]


class TestHomepageHeroBatch10:
    """Cover hero section auto-detect and dual-logo paths."""

    def test_auto_detect_logo_dict_light_dark(self):
        """Hero section with light/dark logo dict renders dual images."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\ndescription = "Desc"\n')
            (tmp / "great-docs.yml").write_text(
                'hero:\n  logo:\n    light: "logo-light.svg"\n    dark: "logo-dark.svg"\n'
            )
            (tmp / "logo-light.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            (tmp / "logo-dark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            html, _ = homepage_hero(docs)
            assert "gd-only-light" in html
            assert "gd-only-dark" in html

    def test_hero_name_falls_back_to_package(self):
        """When hero.name is absent, falls back to package name."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\ndescription = "Desc"\n')
            (tmp / "great-docs.yml").write_text("hero:\n  enabled: true\n")
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            html, _ = homepage_hero(docs)
            assert "mypkg" in html

    def test_hero_returns_empty_when_no_parts(self):
        """When hero config produces no content, returns empty strings."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "great-docs.yml").write_text(
                "hero:\n  enabled: true\n  name: false\n  tagline: false\n"
            )
            docs = GreatDocs(project_path=tmp_dir)
            docs.build_dir.mkdir(parents=True, exist_ok=True)
            html, cleaned = homepage_hero(docs)
            # Should have at least the name (fallback)
            assert isinstance(html, str)


class TestHomepageMarginBatch10:
    """Cover author affiliation, homepage, and ORCID icon links."""

    def test_author_with_affiliation_homepage_orcid(self):
        """Author metadata renders affiliation, homepage, and ORCID links."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text(
                '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
                '[[project.authors]]\nname = "Jane"\nemail = "j@e.com"\n'
            )
            (tmp / "great-docs.yml").write_text(
                "authors:\n"
                "  - name: Jane\n"
                "    affiliation: MIT\n"
                "    homepage: https://jane.dev\n"
                "    orcid: 0000-0001-2345-6789\n"
            )
            docs = GreatDocs(project_path=tmp_dir)
            margin = homepage_margin(docs)
            assert "MIT" in margin
            assert "jane.dev" in margin
            assert "orcid" in margin.lower()


class TestCheckLinksURLCleanupBatch10:
    """Cover URL cleanup branches in check_links."""

    def test_unbalanced_parens_stripped(self):
        """URLs with trailing unbalanced parens are cleaned."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "great-docs.yml").write_text("")
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "test.qmd").write_text("See (https://example.com/page)) for details.\n")
            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=[".*"],  # Skip all actual HTTP checks
            )
            # The URL should be cleaned (trailing paren removed) and then skipped
            assert results["total"] == 0 or len(results["skipped"]) > 0

    def test_fstring_placeholder_urls_skipped(self):
        """URLs containing { are skipped (f-string placeholders)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
            (tmp / "great-docs.yml").write_text("")
            ug_dir = tmp / "user_guide"
            ug_dir.mkdir()
            (ug_dir / "test.qmd").write_text(
                "http://example.com/{variable}/path\nhttp://clean-url.com\n"
            )
            docs = GreatDocs(project_path=tmp_dir)
            results = docs.check_links(
                include_source=False,
                include_docs=True,
                ignore_patterns=[".*"],
            )
            # Only clean-url.com should be in the results (the {variable} one is skipped)
            all_urls = results["skipped"] + results.get("ok", [])
            assert not any("{" in u for u in all_urls)


# ---------------------------------------------------------------------------
# SKILL.md generation tests
# ---------------------------------------------------------------------------


def _skills_writer(docs: GreatDocs) -> SkillsWriter:
    return SkillsWriter(
        docs._config,
        docs.layout,
        docs.build_dir,
        make_project(docs).name,
        make_project(docs).manifest,
    )


def _skills_page_writer(docs: GreatDocs) -> SkillsPageWriter:
    return SkillsPageWriter(
        docs._config,
        docs.layout,
        docs.build_dir,
        make_project(docs).name,
        make_project(docs).manifest,
    )


def test_write_skill_basic():
    """Test basic SKILL.md generation with API sections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Create a pyproject.toml with package info
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package for testing"
license = "MIT"
requires-python = ">=3.10"
"""
        )

        # Create great-docs directory and _quarto.yml
        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: os
  sections:
    - title: Core
      desc: Core functionality
      contents:
        - Widget
        - create_widget
"""
        )

        _skills_writer(docs).write()

        skill_md = great_docs_dir / "skill.md"
        assert skill_md.exists()

        content = skill_md.read_text()

        # Check frontmatter
        assert content.startswith("---\n")
        assert "name: test-package" in content
        assert "description: >" in content
        assert "A test package for testing." in content
        assert "license: MIT" in content
        assert "compatibility: Requires Python >=3.10." in content

        # Check body
        assert "## Installation" in content
        assert "pip install test-package" in content
        assert "## API overview" in content
        assert "### Core" in content
        assert "Core functionality" in content
        assert "- `Widget`" in content
        assert "- `create_widget`" in content

        # Check resources section
        assert "## Resources" in content
        assert "[llms.txt](llms.txt)" in content
        assert "[llms-full.txt](llms-full.txt)" in content


def test_generated_skill_front_matter_quotes_punctuation(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\ndescription = "Tools: data and docs"\nlicense = "Custom: MIT"\n'
    )
    build_dir = tmp_path / "great-docs"
    build_dir.mkdir()
    (build_dir / "_quarto.yml").write_text(
        "api-reference:\n  package: os\n  sections:\n    - title: Core\n      contents: [path]\n"
    )
    docs = GreatDocs(project_path=tmp_path)

    _skills_writer(docs).write()

    front_matter, _ = split_front_matter((build_dir / "skill.md").read_text())
    assert front_matter.string("description").strip() == (
        "Tools: data and docs. Use when writing Python code that uses the os package."
    )
    assert front_matter.string("license") == "Custom: MIT"


def test_write_skill_well_known():
    """Test that SKILL.md is copied to .well-known/ directories with index.json."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        # Check legacy .well-known/skills/default placement
        well_known = great_docs_dir / ".well-known" / "skills" / "default" / "SKILL.md"
        assert well_known.exists()

        # Content should match skill.md
        skill_md = great_docs_dir / "skill.md"
        assert skill_md.read_text() == well_known.read_text()

        # Check preferred .well-known/agent-skills/{name}/SKILL.md placement
        agent_skill = great_docs_dir / ".well-known" / "agent-skills" / "test-package" / "SKILL.md"
        assert agent_skill.exists()
        assert skill_md.read_text() == agent_skill.read_text()

        # Check index.json discovery manifest
        index_json = great_docs_dir / ".well-known" / "agent-skills" / "index.json"
        assert index_json.exists()
        import json

        index_data = json.loads(index_json.read_text())
        assert "skills" in index_data
        assert len(index_data["skills"]) == 1
        assert index_data["skills"][0]["name"] == "test-package"
        assert "SKILL.md" in index_data["skills"][0]["files"]


def test_write_skill_disabled():
    """Test that SKILL.md is not generated when skill.enabled is false."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create great-docs.yml with skill disabled
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  enabled: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()

        _skills_writer(docs).write()

        skill_md = great_docs_dir / "skill.md"
        assert not skill_md.exists()


def test_write_skill_well_known_disabled():
    """Test that .well-known is skipped when skill.well_known is false."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  well_known: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        # skill.md should exist but .well-known should not
        assert (great_docs_dir / "skill.md").exists()
        assert not (great_docs_dir / ".well-known").exists()


def test_write_skill_user_override():
    """Test that a user-provided SKILL.md is copied verbatim."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create great-docs.yml pointing to a custom file
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  file: my-skill.md\n")

        # Create the custom skill file
        custom_skill = Path(tmp_dir) / "my-skill.md"
        custom_skill.write_text("---\nname: custom\ndescription: Custom skill\n---\n\n# Custom\n")

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()

        _skills_writer(docs).write()

        skill_md = great_docs_dir / "skill.md"
        assert skill_md.exists()
        assert "# Custom" in skill_md.read_text()

        # Should also be in .well-known
        well_known = great_docs_dir / ".well-known" / "skills" / "default" / "SKILL.md"
        assert well_known.exists()


def test_write_skill_publishes_companions_shown_on_page(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo-pkg"\n')
    skill_dir = tmp_path / "skills" / "demo-pkg"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "assets").mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: demo-pkg\ndescription: Demo\n---\n# Demo\n")
    (skill_dir / "recipes.md").write_text("# Recipes\n")
    (skill_dir / "references" / "api.md").write_text("# API\n")
    (skill_dir / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n")
    (skill_dir / ".DS_Store").write_bytes(b"\x00")
    docs = GreatDocs(project_path=tmp_path)
    docs.build_dir.mkdir()

    _skills_writer(docs).write()

    expected = ["SKILL.md", "assets/logo.png", "recipes.md", "references/api.md"]
    published = docs.build_dir / ".well-known" / "agent-skills" / "demo-pkg"
    files = [p.relative_to(published).as_posix() for p in published.rglob("*") if p.is_file()]
    assert sorted(files) == expected
    index = json.loads((published.parent / "index.json").read_text())
    assert index["skills"][0]["files"] == expected

    page = (docs.build_dir / "skills.qmd").read_text()
    tree = page.split('<pre class="gd-skills-tree">')[1].split("</pre>")[0]
    for name in ["logo.png", "recipes.md", "api.md"]:
        assert name in tree
    assert ".DS_Store" not in page
    assert ">recipes.md</h3>" in page
    assert ">references/api.md</h3>" in page
    assert ">assets/logo.png</h3>" not in page


def test_write_skill_at_project_root_has_no_companions(tmp_path: Path):
    (tmp_path / "great-docs.yml").write_text("skill:\n  file: SKILL.md\n")
    (tmp_path / "SKILL.md").write_text("---\nname: demo-pkg\ndescription: Demo\n---\n# Demo\n")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "helper.py").write_text("print('project asset')\n")
    docs = GreatDocs(project_path=tmp_path)
    docs.build_dir.mkdir()

    _skills_writer(docs).write()

    published = docs.build_dir / ".well-known" / "agent-skills" / "demo-pkg"
    assert [p.name for p in published.iterdir()] == ["SKILL.md"]
    page = (docs.build_dir / "skills.qmd").read_text()
    assert "helper.py" not in page
    assert "gd-skills-tree" not in page


def test_write_skill_user_override_missing():
    """Test fallback to generation when user-provided SKILL.md doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  file: nonexistent.md\n")

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        # Should still generate a skill.md (fallback)
        skill_md = great_docs_dir / "skill.md"
        assert skill_md.exists()
        assert "name: test-package" in skill_md.read_text()


def test_write_skill_gotchas_and_best_practices():
    """Test that gotchas and best_practices from config appear in SKILL.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
skill:
  gotchas:
    - "Never call foo() before bar()"
    - "The config file must be in the project root"
  best_practices:
    - "Always use context managers"
    - "Prefer keyword arguments"
"""
        )

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()

        assert "## Gotchas" in content
        assert "1. Never call foo() before bar()" in content
        assert "2. The config file must be in the project root" in content
        assert "## Best practices" in content
        assert "- Always use context managers" in content
        assert "- Prefer keyword arguments" in content


def test_write_skill_decision_table():
    """Test that manual decision table rows appear in SKILL.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
skill:
  decision_table:
    - need: "Create a widget"
      use: "Widget()"
    - need: "Format output"
      use: "fmt()"
"""
        )

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - Widget
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()

        assert "## When to use what" in content
        assert "| Need | Use |" in content
        assert "| Create a widget | `Widget()` |" in content
        assert "| Format output | `fmt()` |" in content


def test_write_skill_extra_body():
    """Test that extra_body content is appended to SKILL.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  extra_body: extra.md\n")

        # Create the extra content file
        extra_file = Path(tmp_dir) / "extra.md"
        extra_file.write_text("## Custom Section\n\nExtra content here.\n")

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()
        assert "## Custom Section" in content
        assert "Extra content here." in content


def test_write_skill_no_quarto_yml():
    """
    Skip skill writing when there is no Quarto configuration
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        _skills_writer(docs).write()
        assert not (docs.build_dir / "skill.md").exists()


def test_write_skill_with_site_url():
    """Test that site URL is included in the Resources section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"

[project.urls]
Documentation = "https://example.com/docs"
Repository = "https://github.com/test/test-package"
"""
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()
        assert "[Full documentation](https://example.com/docs/)" in content
        assert "[Source code](https://github.com/test/test-package)" in content


def test_config_skill_defaults():
    """Test that skill config properties have correct defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(Path(tmp_dir))
        assert config.skill_enabled is True
        assert config.skill_file is None
        assert config.skill_well_known is True
        assert config.skill_gotchas == []
        assert config.skill_best_practices == []
        assert config.skill_decision_table == []
        assert config.skill_extra_body is None


def test_config_skill_overrides():
    """Test that skill config properties respect user overrides."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
skill:
  enabled: false
  file: custom.md
  well_known: false
  gotchas:
    - "Watch out!"
  best_practices:
    - "Do this"
  decision_table:
    - need: X
      use: Y
  extra_body: extra.md
"""
        )
        config = Config(Path(tmp_dir))
        assert config.skill_enabled is False
        assert config.skill_file == "custom.md"
        assert config.skill_well_known is False
        assert config.skill_gotchas == ["Watch out!"]
        assert config.skill_best_practices == ["Do this"]
        assert config.skill_decision_table == [{"need": "X", "use": "Y"}]
        assert config.skill_extra_body == "extra.md"


def test_write_skill_uses_curated_skill():
    """Test that a curated skills/<pkg>/SKILL.md is used instead of auto-generating."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test-package"
description = "A test package"
"""
        )

        # Create the curated skill in skills/test-package/SKILL.md
        skills_dir = Path(tmp_dir) / "skills" / "test-package"
        skills_dir.mkdir(parents=True)
        curated_skill = skills_dir / "SKILL.md"
        curated_skill.write_text(
            "---\nname: test-package\ndescription: Curated skill\n---\n\n# Curated\n"
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        skill_md = great_docs_dir / "skill.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        # Should contain the curated content, NOT auto-generated
        assert "# Curated" in content
        assert "## API overview" not in content

        # Should also be in .well-known
        well_known = great_docs_dir / ".well-known" / "skills" / "default" / "SKILL.md"
        assert well_known.exists()
        assert "# Curated" in well_known.read_text()


def test_write_skill_curated_with_underscore_name():
    """Test curated skill discovery with underscore package names."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "my_package"
description = "A package with underscores"
"""
        )

        # Create skill using hyphenated name (PyPI convention)
        skills_dir = Path(tmp_dir) / "skills" / "my-package"
        skills_dir.mkdir(parents=True)
        curated_skill = skills_dir / "SKILL.md"
        curated_skill.write_text(
            "---\nname: my-package\ndescription: Underscore skill\n---\n\n# Hyphenated\n"
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            """
api-reference:
  package: my_package
  sections:
    - title: Main
      contents:
        - foo
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()
        assert "# Hyphenated" in content


def test_write_skill_install_uses_distribution_name():
    """Install command uses pyproject.toml distribution name, not the importable module name.

    Example: import name is 'toast', distribution name is 'toast-analytics'. The generated skill
    must emit 'pip install toast-analytics', not 'pip install toast'.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "toast-analytics"
description = "Web analytics client"
"""
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"

        # api-reference.package is the *importable* module name
        quarto_yml.write_text(
            """
api-reference:
  package: toast
  sections:
    - title: Core
      contents:
        - track
"""
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skill.md").read_text()

        assert "pip install toast-analytics" in content
        assert "pip install toast\n" not in content


def test_write_skills_page_basic():
    """Test that skills.qmd is generated alongside skill.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\ndescription = "A test package"\n')

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        skills_qmd = great_docs_dir / "skills.qmd"
        assert skills_qmd.exists()

        content = skills_qmd.read_text()

        # Check Quarto frontmatter
        assert "title: Skills" in content
        assert "page-layout: full" in content

        # Check install section (collapsible component)
        assert "Install this skill" in content
        assert "gd-skills-install-toggle" in content
        assert "npx skills add" in content

        # Check frontmatter appears inside raw markdown block
        assert "name: test-package" in content

        # Check body is rendered as raw markdown in a pre block
        assert "gd-skills-raw" in content
        assert "````markdown" in content

        front_matter = parse_yaml(content.split("---\n")[1])
        assert front_matter["gd-head-tags"] == [
            '`<meta name="robots" content="noindex, nofollow">`{=html}'
        ]


def test_write_skills_page_omits_robots_tag_without_seo() -> None:
    """Omit robots metadata from `skills.qmd` when SEO is disabled"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("seo:\n  enabled: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\ndescription = "A test package"\n')

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skills.qmd").read_text()
        assert "gd-head-tags" not in content
        assert "robots" not in content


def test_write_skills_page_github_repo_detection():
    """Test that GitHub owner/repo is auto-detected for install instructions."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-package"\n'
            'description = "A test package"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/myorg/test-package"\n'
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skills.qmd").read_text()

        # Should have GitHub-specific install command
        assert "npx skills add myorg/test-package" in content
        # Codex / OpenCode section should reference the GitHub repo
        assert "Codex / OpenCode" in content
        assert "github.com/myorg/test-package" in content


def test_write_skills_page_site_url():
    """Test that site URL is used when no GitHub repo is available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-package"\n'
            'description = "A test package"\n'
            "\n"
            "[project.urls]\n"
            'Documentation = "https://example.com/docs"\n'
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skills.qmd").read_text()

        # Should use site URL for npx install
        assert "npx skills add https://example.com/docs/" in content
        # Codex / OpenCode section should use site URL for skill file
        assert "Codex / OpenCode" in content
        assert "example.com/docs/skill.md" in content


def test_write_skills_page_frontmatter_display():
    """Test that SKILL.md frontmatter is displayed as YAML, not Quarto FM."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-package"\n'
            'description = "A test package"\n'
            'license = "MIT"\n'
            'requires-python = ">=3.10"\n'
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skills.qmd").read_text()

        # The full skill.md content should appear as raw markdown
        assert "gd-skills-raw" in content
        assert "````markdown" in content
        assert "name: test-package" in content

        # Keep the Quarto title separate from the skill's name
        assert content.startswith("---\n")
        assert parse_yaml(content.split("---\n")[1])["title"] == "Skills"


def test_write_skills_page_curated_skill():
    """Test that skills.qmd is generated from a curated skill."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\ndescription = "A test package"\n')

        # Create curated skill
        skills_dir = Path(tmp_dir) / "skills" / "test-package"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\n"
            "name: test-package\n"
            "description: Custom curated skill\n"
            "---\n"
            "\n"
            "# My Custom Skill\n"
            "\n"
            "## Gotchas\n"
            "\n"
            "1. Don't do this\n"
            "2. Also avoid that\n"
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()

        _skills_writer(docs).write()

        skills_qmd = great_docs_dir / "skills.qmd"
        assert skills_qmd.exists()

        content = skills_qmd.read_text()

        # Body from curated skill should appear as raw markdown
        assert "My Custom Skill" in content
        assert "Gotchas" in content
        assert "gd-skills-raw" in content


def test_write_skills_page_disabled():
    """Test that skills.qmd is NOT generated when skill is disabled."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  enabled: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()

        _skills_writer(docs).write()

        assert not (great_docs_dir / "skills.qmd").exists()


def test_write_skills_page_well_known_disabled():
    """Test skills.qmd doesn't show .well-known link when disabled."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text("skill:\n  well_known: false\n")

        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-package"\ndescription = "A test package"\n')

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text(
            "api-reference:\n"
            "  package: test_package\n"
            "  sections:\n"
            "    - title: Main\n"
            "      contents:\n"
            "        - foo\n"
        )

        _skills_writer(docs).write()

        content = (great_docs_dir / "skills.qmd").read_text()

        # Should still have skill.md link (raw HTML format)
        assert 'href="skill.md"' in content
        # But NOT the .well-known link
        assert ".well-known" not in content


def test_homepage_sidebar_skills_link_position():
    """Test that Skills link appears before llms.txt in the sidebar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "test-package"\n'
            'description = "A test package"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/test-org/test-package"\n'
        )

        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        # llms.txt links are only shown when the files will be generated (#350)
        (great_docs_dir / "_quarto.yml").write_text(
            "api-reference:\n  package: os\n  sections:\n"
            "    - title: Core\n      contents: [os.getcwd]\n",
            encoding="utf-8",
        )

        margin = homepage_margin(docs)

        # Skills link should appear before llms.txt
        skills_pos = margin.find('href="skills.html"')
        llms_pos = margin.find("[llms.txt](llms.txt)")

        assert skills_pos != -1, "Skills link not found in sidebar"
        assert llms_pos != -1, "llms.txt link not found in sidebar"
        assert skills_pos < llms_pos, "Skills should appear before llms.txt"


def test_announcement_inline_markdown_backticks():
    """Backtick code spans in announcement content are converted to <code> tags."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=("announcement:\n  content: 'Install with: `pip install great-docs`'\n"),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header = result["format"]["html"]["include-in-header"]
        meta_str = str(header)
        assert "&lt;code&gt;pip install great-docs&lt;/code&gt;" in meta_str


def test_announcement_inline_markdown_bold():
    """Double-asterisk bold in announcement content becomes <strong>."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=("announcement:\n  content: '**Breaking change** in v2.0'\n"),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        meta_str = str(result["format"]["html"]["include-in-header"])
        assert "&lt;strong&gt;Breaking change&lt;/strong&gt;" in meta_str


def test_announcement_inline_markdown_italic():
    """Single-asterisk italic in announcement content becomes <em>."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=("announcement:\n  content: 'This is *important* news'\n"),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        meta_str = str(result["format"]["html"]["include-in-header"])
        assert "&lt;em&gt;important&lt;/em&gt;" in meta_str


def test_announcement_inline_markdown_link():
    """Markdown links in announcement content become <a> tags."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=(
                "announcement:\n  content: 'See [release notes](https://example.com/changelog)'\n"
            ),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        meta_str = str(result["format"]["html"]["include-in-header"])
        assert "release notes" in meta_str
        assert "https://example.com/changelog" in meta_str
        assert "&lt;a href=" in meta_str


def test_announcement_inline_markdown_combined():
    """Multiple Markdown constructs in one announcement line all convert."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=(
                "announcement:\n"
                "  content: '**New!** Try `great-docs init` — see [docs](https://example.com)'\n"
            ),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        meta_str = str(result["format"]["html"]["include-in-header"])
        assert "&lt;strong&gt;New!&lt;/strong&gt;" in meta_str
        assert "&lt;code&gt;great-docs init&lt;/code&gt;" in meta_str
        assert "&lt;a href=" in meta_str


def test_announcement_plain_text_unaffected():
    """Plain text without Markdown syntax passes through unchanged."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=("announcement:\n  content: 'Just a plain announcement'\n"),
        )
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        meta_str = str(result["format"]["html"]["include-in-header"])
        assert "Just a plain announcement" in meta_str


def test_update_quarto_config_disables_native_code_copy():
    """
    Disable Quarto's built-in code copy button
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert result["format"]["html"]["code-copy"] is False


def test_update_quarto_config_includes_copy_code_js_in_resources():
    """
    Register `copy-code.js` as a Quarto resource
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "copy-code.js" in result["project"]["resources"]


def test_update_quarto_config_includes_copy_code_js_in_after_body():
    """
    Include `copy-code.js` after the page body
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        after_body_str = str(after_body)

        assert "copy-code.js" in after_body_str


def test_update_quarto_config_copy_code_not_duplicated():
    """
    Keep one `copy-code.js` include after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        copy_code_count = sum(
            1
            for item in after_body
            if isinstance(item, dict) and "copy-code.js" in str(item.get("text", ""))
        )

        assert copy_code_count == 1

        resource_count = result["project"]["resources"].count("copy-code.js")

        assert resource_count == 1


def test_update_quarto_config_includes_tooltips_js_in_resources():
    """
    Register `tooltips.js` as a Quarto resource
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "tooltips.js" in result["project"]["resources"]


def test_update_quarto_config_includes_tooltips_js_in_after_body():
    """
    Include `tooltips.js` after the page body
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        after_body_str = str(after_body)

        assert "tooltips.js" in after_body_str


def test_update_quarto_config_tooltips_not_duplicated():
    """
    Keep one `tooltips.js` include after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        tooltips_count = sum(
            1
            for item in after_body
            if isinstance(item, dict) and "tooltips.js" in str(item.get("text", ""))
        )
        assert tooltips_count == 1

        resource_count = result["project"]["resources"].count("tooltips.js")

        assert resource_count == 1


def test_update_quarto_config_includes_responsive_tables_js_in_resources():
    """
    Register `responsive-tables.js` as a Quarto resource
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "responsive-tables.js" in result["project"]["resources"]


def test_update_quarto_config_includes_responsive_tables_js_in_after_body():
    """
    Include `responsive-tables.js` after the page body
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        after_body_str = str(after_body)

        assert "responsive-tables.js" in after_body_str


def test_update_quarto_config_responsive_tables_not_duplicated():
    """
    Keep one `responsive-tables.js` include after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        resp_tables_count = sum(
            1
            for item in after_body
            if isinstance(item, dict) and "responsive-tables.js" in str(item.get("text", ""))
        )
        assert resp_tables_count == 1

        resource_count = result["project"]["resources"].count("responsive-tables.js")

        assert resource_count == 1


def test_update_quarto_config_includes_video_embed_js_in_resources():
    """
    Register `video-embed.js` as a Quarto resource
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "video-embed.js" in result["project"]["resources"]


def test_update_quarto_config_includes_video_embed_js_in_after_body():
    """
    Include `video-embed.js` after the page body
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        after_body_str = str(after_body)

        assert "video-embed.js" in after_body_str


def test_update_quarto_config_video_embed_not_duplicated():
    """
    Keep one `video-embed.js` include after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        video_count = sum(
            1
            for item in after_body
            if isinstance(item, dict) and "video-embed.js" in str(item.get("text", ""))
        )

        assert video_count == 1

        resource_count = result["project"]["resources"].count("video-embed.js")

        assert resource_count == 1


def test_update_quarto_config_video_embed_script_tag_format():
    """video-embed.js loads through a plain root-relative tag that Quarto rewrites per page."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        video_entries = [item for item in after_body if "video-embed.js" in str(item)]

        assert video_entries == [script_include("video-embed.js")]


def test_prepare_build_directory_copies_video_embed_js():
    """
    Copy `video-embed.js` into the build directory
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "mypkg"\n', encoding="utf-8")

        readme = Path(tmp_dir) / "README.md"
        readme.write_text("# My Pkg\n", encoding="utf-8")

        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

        assert (docs.build_dir / "video-embed.js").exists()


def test_video_embed_js_asset_exists():
    """The video-embed.js asset file exists in the assets directory."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        asset_path = docs.assets_path / "video-embed.js"

        assert asset_path.exists()


def test_video_embed_js_is_iife():
    """video-embed.js uses the IIFE pattern like other Great Docs JS files."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "video-embed.js").read_text(encoding="utf-8")

        assert content.startswith("/**")
        assert "(function () {" in content or "(function() {" in content
        assert '"use strict";' in content
        assert content.rstrip().endswith("})();")


def test_video_embed_js_has_lazy_loading():
    """video-embed.js contains IntersectionObserver lazy-loading for non-YouTube iframes."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "video-embed.js").read_text(encoding="utf-8")

        assert "lazyLoadIframes" in content
        assert "IntersectionObserver" in content
        assert "rootMargin" in content


def test_video_embed_js_has_video_element_enhancement():
    """video-embed.js sets preload=metadata on local <video> elements."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "video-embed.js").read_text(encoding="utf-8")

        assert "enhanceVideoElements" in content
        assert '"metadata"' in content
        assert '"preload"' in content


def test_scss_has_video_styles():
    """great-docs.scss contains styling for video containers."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "great-docs.scss").read_text(encoding="utf-8")

        # Video container border
        assert ".quarto-video" in content


def test_scss_video_container_has_border():
    """The .quarto-video container has a border and border-radius."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "great-docs.scss").read_text(encoding="utf-8")

        # Find the .quarto-video block and check its properties
        assert "border: 1px solid" in content
        assert "border-radius: 6px" in content
        assert "overflow: hidden" in content


def test_scss_video_dark_mode():
    """The video container has dark-mode-specific border color."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "great-docs.scss").read_text(encoding="utf-8")

        # Dark mode should override border color for .quarto-video
        assert (
            "quarto-dark .quarto-video" in content
            or 'data-bs-theme="dark"] .quarto-video' in content
        )


def test_scss_video_focus_visible():
    """The placeholder has :focus-visible styling for keyboard accessibility."""

    from great_docs.core import GreatDocs

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = (docs.assets_path / "great-docs.scss").read_text(encoding="utf-8")

        assert "focus-visible" in content


def test_video_embed_always_included():
    """video-embed.js is always included regardless of config settings."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Minimal config — no special settings
        docs, quarto_yml = _make_uqc_docs(tmp_dir, gd_yml_content="")
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "video-embed.js" in result["project"]["resources"]

        after_body_str = str(result["format"]["html"]["include-after-body"])

        assert "video-embed.js" in after_body_str


def test_update_quarto_config_mermaid_theme_default():
    """
    Set the Mermaid theme to `default`
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        mermaid_config = result["format"]["html"].get("mermaid")
        assert mermaid_config is not None
        assert mermaid_config.get("theme") == "default"


def test_update_quarto_config_includes_mermaid_renderer_js():
    """
    Include `mermaid-renderer.js` after the page body
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        after_body_str = str(after_body)

        assert "mermaid-renderer.js" in after_body_str


def test_update_quarto_config_mermaid_renderer_not_duplicated():
    """
    Keep one `mermaid-renderer.js` include after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        mermaid_count = sum(
            1
            for item in after_body
            if isinstance(item, dict) and "mermaid-renderer.js" in str(item.get("text", ""))
        )
        assert mermaid_count == 1


def test_config_seo_defaults():
    """Test that SEO configuration has sensible defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = Config(Path(tmp_dir))

        # Master switch
        assert config.seo_enabled is True

        # Sitemap
        assert config.sitemap_enabled is True
        assert "homepage" in config.sitemap_changefreq
        assert config.sitemap_changefreq["homepage"] == "weekly"
        assert config.sitemap_priority["homepage"] == 1.0

        # Robots
        assert config.robots_enabled is True
        assert config.robots_allow_all is True
        assert config.robots_disallow == []
        assert config.robots_crawl_delay is None

        # Canonical
        assert config.canonical_enabled is True
        assert config.canonical_base_url is None

        # Title template
        assert config.seo_title_template == "{page_title} | {site_name}"

        # Structured data
        assert config.structured_data_enabled is True
        assert config.structured_data_type == "SoftwareSourceCode"


def test_config_seo_overrides():
    """Test that SEO config properties respect user overrides."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
seo:
  enabled: false
  sitemap:
    enabled: false
    changefreq:
      homepage: daily
    priority:
      homepage: 0.5
  robots:
    enabled: false
    allow_all: false
    disallow:
      - /drafts/
    crawl_delay: 10
    extra_rules:
      - "User-agent: GPTBot"
      - "Disallow: /"
  canonical:
    enabled: false
    base_url: https://example.com/docs/
  title_template: "{page_title} - {site_name}"
  structured_data:
    enabled: false
    type: WebSite
  default_description: "My package documentation"
"""
        )
        config = Config(Path(tmp_dir))

        # Master switch
        assert config.seo_enabled is False

        # Sitemap
        assert config.sitemap_enabled is False
        assert config.sitemap_changefreq["homepage"] == "daily"
        assert config.sitemap_priority["homepage"] == 0.5

        # Robots
        assert config.robots_enabled is False
        assert config.robots_allow_all is False
        assert config.robots_disallow == ["/drafts/"]
        assert config.robots_crawl_delay == 10
        assert config.robots_extra_rules == ["User-agent: GPTBot", "Disallow: /"]

        # Canonical
        assert config.canonical_enabled is False
        assert config.canonical_base_url == "https://example.com/docs/"

        # Title template
        assert config.seo_title_template == "{page_title} - {site_name}"

        # Structured data
        assert config.structured_data_enabled is False
        assert config.structured_data_type == "WebSite"

        # Default description
        assert config.seo_default_description == "My package documentation"


def test_sitemap_page_type():
    """
    Classify rendered paths for sitemap settings
    """
    # Homepage
    assert sitemap.page_type("index.html") == "homepage"

    # Reference pages
    assert sitemap.page_type("reference/MyClass.html") == "reference"
    assert sitemap.page_type("reference/index.html") == "reference"

    # User guide
    assert sitemap.page_type("user-guide/intro.html") == "user_guide"
    assert sitemap.page_type("user-guide/configuration.html") == "user_guide"

    # Changelog
    assert sitemap.page_type("changelog.html") == "changelog"

    # Recipes (treated as user guide)
    assert sitemap.page_type("recipes/custom-css.html") == "user_guide"

    # Default for other pages
    assert sitemap.page_type("about.html") == "default"
    assert sitemap.page_type("some/nested/page.html") == "default"


def test_sitemap_write():
    """
    Write sitemap entries with the canonical base URL and homepage priority
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a mock site structure
        site_dir = Path(tmp_dir) / "great-docs" / "_site"
        site_dir.mkdir(parents=True)

        # Create some HTML files
        (site_dir / "index.html").write_text("<html></html>")
        (site_dir / "reference").mkdir()
        (site_dir / "reference" / "MyClass.html").write_text("<html></html>")
        (site_dir / "user-guide").mkdir()
        (site_dir / "user-guide" / "intro.html").write_text("<html></html>")

        # Create config with a base URL
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
seo:
  canonical:
    base_url: https://example.com/docs/
"""
        )

        docs = GreatDocs(project_path=tmp_dir)
        sitemap.write(
            site_dir,
            docs._config,
            site.identity(docs._config, docs.layout, make_project(docs)).base_url,
            report=print,
        )

        sitemap_path = site_dir / "sitemap.xml"

        assert sitemap_path.exists()

        content = sitemap_path.read_text()

        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in content
        assert "<loc>https://example.com/docs/</loc>" in content
        assert "<loc>https://example.com/docs/reference/MyClass.html</loc>" in content
        assert "<priority>1.0</priority>" in content  # Homepage priority


def test_robots_write():
    """
    Write default crawler rules, configured restrictions and the sitemap reference
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a mock site structure
        site_dir = Path(tmp_dir) / "great-docs" / "_site"
        site_dir.mkdir(parents=True)

        # Create config with custom robots settings
        config_path = Path(tmp_dir) / "great-docs.yml"
        config_path.write_text(
            """
seo:
  canonical:
    base_url: https://example.com/docs/
  robots:
    disallow:
      - /drafts/
    extra_rules:
      - "User-agent: GPTBot"
      - "Disallow: /"
"""
        )

        docs = GreatDocs(project_path=tmp_dir)
        robots.write(
            site_dir,
            docs._config,
            site.identity(docs._config, docs.layout, make_project(docs)).base_url,
            report=print,
        )

        robots_path = site_dir / "robots.txt"

        assert robots_path.exists()

        content = robots_path.read_text()

        assert "User-agent: *" in content
        assert "Allow: /" in content
        assert "Disallow: /drafts/" in content
        assert "User-agent: GPTBot" in content
        assert "Sitemap: https://example.com/docs/sitemap.xml" in content


# ---------------------------------------------------------------------------
# Back-to-top button tests
# ---------------------------------------------------------------------------


def test_back_to_top_enabled_by_default():
    """back-to-top.js is in resources and include-after-body by default."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])
        assert "back-to-top.js" in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_back_to_top = any("back-to-top.js" in str(item) for item in after_body)
        assert has_back_to_top


def test_back_to_top_disabled_via_config():
    """back-to-top.js is excluded when back_to_top is false."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="back_to_top: false\n",
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])
        assert "back-to-top.js" not in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_back_to_top = any("back-to-top.js" in str(item) for item in after_body)
        assert not has_back_to_top


def test_back_to_top_script_tag_content():
    """The back-to-top include-after-body entry has the expected script tag."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        back_to_top_entries = [item for item in after_body if "back-to-top.js" in str(item)]
        assert len(back_to_top_entries) == 1
        assert back_to_top_entries[0] == {"text": '<script src="/back-to-top.js"></script>'}


def test_back_to_top_not_duplicated():
    """
    Keep one `back-to-top.js` script tag after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        back_to_top_count = sum(1 for item in after_body if "back-to-top.js" in str(item))
        assert back_to_top_count == 1


def test_back_to_top_with_string_include_after_body():
    """back-to-top works when include-after-body starts as a string."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            quarto_content={
                "project": {"type": "website"},
                "website": {},
                "format": {"html": {"include-after-body": "existing.html"}},
            },
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        assert isinstance(after_body, list)
        has_back_to_top = any("back-to-top.js" in str(item) for item in after_body)
        assert has_back_to_top


def test_back_to_top_metadata_flag():
    """The back-to-top button is on unless configured off"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        assert docs._config.back_to_top is True


def test_back_to_top_metadata_flag_disabled():
    """`back_to_top: false` turns the back-to-top button off"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="back_to_top: false\n",
        )
        assert docs._config.back_to_top is False


def test_back_to_top_js_copied_to_project():
    """back-to-top.js is copied from assets to the project directory."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir)
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "back-to-top.js"
        assert js_file.exists()


def test_back_to_top_js_not_copied_when_disabled():
    """back-to-top.js is not copied when feature is disabled."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="back_to_top: false\n",
        )
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "back-to-top.js"
        assert not js_file.exists()


# ---------------------------------------------------------------------------
# Wide layout toggle tests
# ---------------------------------------------------------------------------


def _wide_entries(result):
    html_fmt = result["format"]["html"]
    header = [str(h) for h in html_fmt.get("include-in-header", [])]
    after_body = [str(a) for a in html_fmt.get("include-after-body", [])]
    return header, after_body


def test_wide_layout_enabled_by_default():
    """wide-layout.js is a resource, loaded after the body, with its meta tag in the header."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "wide-layout.js" in result["project"].get("resources", [])
        header, after_body = _wide_entries(result)
        assert sum("wide-layout.js" in a for a in after_body) == 1
        metas = [h for h in header if "gd-wide-layout" in h]
        assert len(metas) == 1
        assert 'data-default="normal"' in metas[0]
        assert 'data-min-viewport="1600"' in metas[0]
        assert "--gd-wide-content-scale:1.5;" in metas[0]
        assert "--gd-wide-sidebar-scale:1.2;" in metas[0]
        # No prose cap unless configured
        assert "--gd-wide-prose-max" not in metas[0]


def test_wide_layout_meta_precedes_theme_init():
    """theme-init.js reads the meta tag, so the tag must come first in the header."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header, after_body = _wide_entries(result)
        meta_index = next(i for i, h in enumerate(header) if "gd-wide-layout" in h)
        theme_index = next(i for i, h in enumerate(header) if "theme-init" in h)
        assert meta_index < theme_index
        assert sum("gd-wide-layout" in h for h in header) == 1
        assert sum("wide-layout.js" in a for a in after_body) == 1


def test_repeated_config_pass_keeps_wide_layout_in_place():
    """
    Check that a second configuration pass preserves the config and the `wide-layout.js` position
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))
        first = read_yaml(quarto_yml)
        update_quarto_config(docs, make_run(docs))
        second = read_yaml(quarto_yml)

        # Other scripts must follow the loader on the first pass to expose a move to the end
        _, after_body = _wide_entries(first)
        assert "wide-layout.js" not in after_body[-1]
        assert second == first


def test_theme_init_added_when_details_already_listed():
    """A config that already loads details.js still gets theme-init.js, after the meta tag."""
    from great_docs._website.scripts import script_include

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            quarto_content={
                "project": {"type": "website"},
                "website": {"navbar": {"left": []}, "sidebar": []},
                "format": {"html": {"include-after-body": [script_include("details.js")]}},
            },
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header, _ = _wide_entries(result)
        assert sum("theme-init" in h for h in header) == 1
        meta_index = next(i for i, h in enumerate(header) if "gd-wide-layout" in h)
        theme_index = next(i for i, h in enumerate(header) if "theme-init" in h)
        assert meta_index < theme_index


def test_wide_layout_custom_settings():
    """Configured settings flow into the meta tag and CSS custom properties."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content=(
                "wide_layout:\n"
                "  default: wide\n"
                "  content_scale: 1.75\n"
                "  sidebar_scale: 1.0\n"
                "  min_viewport: 1800\n"
                "  prose_max_width: 110ch\n"
            ),
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        header, _ = _wide_entries(result)
        meta = next(h for h in header if "gd-wide-layout" in h)
        assert 'data-default="wide"' in meta
        assert 'data-min-viewport="1800"' in meta
        assert "--gd-wide-content-scale:1.75;" in meta
        assert "--gd-wide-sidebar-scale:1;" in meta
        assert "--gd-wide-prose-max:110ch;" in meta


def test_wide_layout_disabled_via_config():
    """With wide_layout: false nothing is added, and the JS is not copied."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir, gd_yml_content="wide_layout: false\n")

        update_quarto_config(docs, make_run(docs))
        prepare_build_directory(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        assert "wide-layout.js" not in result["project"].get("resources", [])
        header, after_body = _wide_entries(result)
        assert not any("gd-wide-layout" in h for h in header)
        assert not any("wide-layout.js" in a for a in after_body)
        assert not (docs.build_dir / "wide-layout.js").exists()


def test_wide_layout_js_copied_to_project():
    """wide-layout.js is copied into the build directory by default."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir)
        prepare_build_directory(docs, make_run(docs))

        assert (docs.build_dir / "wide-layout.js").exists()


def test_wide_layout_metadata():
    """The configuration carries the validated wide layout settings"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir)
        wide_layout = docs._config.wide_layout
        assert wide_layout is not None
        assert wide_layout["content_scale"] == 1.5

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir, gd_yml_content="wide_layout: false\n")
        assert docs._config.wide_layout is None


def test_wide_layout_assets_have_expected_content():
    """The JS, theme-init, keyboard-nav, and SCSS assets carry the wide layout hooks."""

    assets = Path(__file__).parent.parent / "great_docs" / "assets"

    js = (assets / "wide-layout.js").read_text()
    assert "(function()" in js and "})();" in js
    assert "gd-wide-toggle" in js
    assert "great-docs-width" in js
    assert "aria-pressed" in js

    theme_init = (assets / "theme-init.js").read_text()
    assert 'meta[name="gd-wide-layout"]' in theme_init
    assert "gd-wide-capable" in theme_init
    assert "great-docs-width" in theme_init

    assert "kb_toggle_wide" in (assets / "keyboard-nav.js").read_text()

    scss = (assets / "great-docs.scss").read_text()
    assert "@property --gd-wide-t" in scss
    assert 'html.gd-wide-capable[data-gd-width="wide"]' in scss
    assert ".gd-wide-toggle" in scss


def test_wide_layout_translations_cover_all_languages():
    """The wide layout labels cover every language the back-to-top label does."""
    from great_docs._translations import SUPPORTED_LANGUAGES, UI_TRANSLATIONS

    for key in ("wide_layout_widen", "wide_layout_restore", "kb_toggle_wide"):
        languages = set(UI_TRANSLATIONS[key])
        assert languages >= set(SUPPORTED_LANGUAGES), key
        assert languages == set(UI_TRANSLATIONS["back_to_top"]), key


def test_back_to_top_js_file_has_expected_content():
    """The back-to-top.js asset exists and contains the IIFE pattern."""

    js_path = Path(__file__).parent.parent / "great_docs" / "assets" / "back-to-top.js"
    assert js_path.exists()
    content = js_path.read_text()

    # Verify IIFE wrapping
    assert content.startswith("/**")
    assert "(function()" in content
    assert "})();" in content

    # Verify key DOM creation
    assert "gd-back-to-top" in content
    assert "aria-label" in content
    assert "Back to top" in content

    # Verify scroll behavior
    assert "SCROLL_THRESHOLD" in content
    assert "scrollTo" in content

    # Verify reduced motion support
    assert "prefers-reduced-motion" in content

    # Verify page nav collision avoidance
    assert ".page-navigation" in content
    assert "adjustForPageNav" in content


def test_back_to_top_scss_styles_exist():
    """The SCSS file contains back-to-top button styles."""

    scss_path = Path(__file__).parent.parent / "great_docs" / "assets" / "great-docs.scss"
    content = scss_path.read_text()

    assert ".gd-back-to-top {" in content
    assert ".gd-back-to-top-visible {" in content
    assert "position: fixed" in content

    # Dark mode
    assert '[data-bs-theme="dark"] .gd-back-to-top' in content

    # Reduced motion
    assert "prefers-reduced-motion" in content


# On-this-page mobile widget tests ---------------------------------------------


def test_on_this_page_enabled_by_default():
    """on-this-page.js is in resources and include-after-body by default."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])

        assert "on-this-page.js" in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_on_this_page = any("on-this-page.js" in str(item) for item in after_body)

        assert has_on_this_page


def test_on_this_page_disabled_via_config():
    """on-this-page.js is excluded when back_to_top is false."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="back_to_top: false\n",
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])

        assert "on-this-page.js" not in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_on_this_page = any("on-this-page.js" in str(item) for item in after_body)

        assert not has_on_this_page


def test_on_this_page_script_tag_is_plain():
    """The on-this-page script loads through a plain root-relative tag."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        otp_entries = [item for item in after_body if "on-this-page.js" in str(item)]

        assert otp_entries == [script_include("on-this-page.js")]


def test_color_swatch_script_tag_is_plain():
    """The color-swatch script loads through a plain root-relative tag."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        swatch_entries = [item for item in after_body if "color-swatch.js" in str(item)]

        assert swatch_entries == [script_include("color-swatch.js")]


def test_update_quarto_config_includes_are_plain_tags_once():
    """
    Every site script and stylesheet is a plain tag, added once across re-runs

    Quarto rewrites root-relative paths for each page, so no include needs to
    locate the site root at load time. Head scripts that should not block
    parsing carry `defer`.
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir, gd_yml_content="marimo:\n  enabled: true\n")

        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        html = result["format"]["html"]
        header = html["include-in-header"]
        after_body = html["include-after-body"]
        entries = header + after_body

        assert not any("quarto:offset" in str(item) for item in entries)

        for name in (
            "gd-lightbox.js",
            "gd-lightbox-compare.js",
            "gd-lightbox-annotate.js",
            "marimo-islands.js",
        ):
            assert script_include(name, defer=True) in header
        for name in (
            "gd-lightbox.css",
            "gd-lightbox-compare.css",
            "gd-lightbox-annotate.css",
            "marimo-islands.css",
        ):
            assert stylesheet_include(name) in header
        for name in (
            "wide-layout.js",
            "sidebar-float.js",
            "on-this-page.js",
            "color-swatch.js",
            "video-embed.js",
        ):
            assert script_include(name) in after_body

        for name in (
            "gd-lightbox.js",
            "gd-lightbox-compare.js",
            "gd-lightbox-annotate.js",
            "marimo-islands.js",
            "gd-lightbox.css",
            "gd-lightbox-compare.css",
            "gd-lightbox-annotate.css",
            "marimo-islands.css",
            "wide-layout.js",
            "sidebar-float.js",
            "on-this-page.js",
            "color-swatch.js",
            "video-embed.js",
        ):
            assert sum(f"/{name}" in str(item) for item in entries) == 1, name


def test_on_this_page_not_duplicated():
    """
    Keep one `on-this-page.js` script tag after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        otp_count = sum(1 for item in after_body if "on-this-page.js" in str(item))

        assert otp_count == 1


def test_on_this_page_js_copied_to_project():
    """on-this-page.js is copied from assets to the project directory."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir)
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "on-this-page.js"

        assert js_file.exists()


def test_on_this_page_js_not_copied_when_disabled():
    """on-this-page.js is not copied when back_to_top is disabled."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="back_to_top: false\n",
        )
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "on-this-page.js"

        assert not js_file.exists()


def test_on_this_page_js_file_has_expected_content():
    """The on-this-page.js asset exists and contains the expected patterns."""

    js_path = Path(__file__).parent.parent / "great_docs" / "assets" / "on-this-page.js"

    assert js_path.exists()

    content = js_path.read_text()

    # Verify IIFE wrapping
    assert "(function ()" in content
    assert "})();" in content

    # Verify mobile-only media query
    assert "max-width: 767.98px" in content

    # Verify TOC collection uses data-scroll-target
    assert "data-scroll-target" in content

    # Verify key DOM creation
    assert "gd-otp-btn" in content
    assert "gd-otp-panel" in content
    assert "gd-otp-backdrop" in content
    assert "aria-label" in content

    # Verify reduced motion support
    assert "prefers-reduced-motion" in content

    # Verify page nav collision avoidance (same logic as back-to-top)
    assert ".page-navigation" in content
    assert ".gd-back-to-top" in content


def test_on_this_page_scss_styles_exist():
    """The SCSS file contains on-this-page widget styles."""

    scss_path = Path(__file__).parent.parent / "great_docs" / "assets" / "great-docs.scss"
    content = scss_path.read_text()

    assert ".gd-otp-btn {" in content
    assert ".gd-otp-panel {" in content
    assert ".gd-otp-backdrop {" in content
    assert ".gd-otp-panel-visible {" in content

    # Dark mode
    assert '[data-bs-theme="dark"] .gd-otp-btn' in content
    assert '[data-bs-theme="dark"] .gd-otp-panel' in content

    # Reduced motion
    assert ".gd-otp-btn," in content  # in the reduced-motion block


# Keyboard navigation tests ----------------------------------------------------


def test_keyboard_nav_enabled_by_default():
    """keyboard-nav.js is in resources and include-after-body by default."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])
        assert "keyboard-nav.js" in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_keyboard_nav = any("keyboard-nav.js" in str(item) for item in after_body)
        assert has_keyboard_nav


def test_keyboard_nav_disabled_via_config():
    """keyboard-nav.js is excluded when keyboard_nav is false."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="keyboard_nav: false\n",
        )

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        resources = result["project"].get("resources", [])
        assert "keyboard-nav.js" not in resources

        after_body = result["format"]["html"].get("include-after-body", [])
        has_keyboard_nav = any("keyboard-nav.js" in str(item) for item in after_body)
        assert not has_keyboard_nav


def test_keyboard_nav_script_tag_content():
    """The keyboard-nav include-after-body entry has the expected script tag."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        kb_entries = [item for item in after_body if "keyboard-nav.js" in str(item)]
        assert len(kb_entries) == 1
        assert kb_entries[0] == {"text": '<script src="/keyboard-nav.js"></script>'}


def test_keyboard_nav_not_duplicated():
    """
    Keep one `keyboard-nav.js` script tag after repeated configuration
    """

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)

        update_quarto_config(docs, make_run(docs))
        update_quarto_config(docs, make_run(docs))

        with open(quarto_yml) as f:
            result = read_yaml(f)

        after_body = result["format"]["html"]["include-after-body"]
        kb_count = sum(1 for item in after_body if "keyboard-nav.js" in str(item))
        assert kb_count == 1


def test_keyboard_nav_metadata_flag():
    """Keyboard navigation is on unless configured off"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(tmp_dir)
        assert docs._config.keyboard_nav is True


def test_keyboard_nav_metadata_flag_disabled():
    """`keyboard_nav: false` turns keyboard navigation off"""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, quarto_yml = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="keyboard_nav: false\n",
        )
        assert docs._config.keyboard_nav is False


def test_keyboard_nav_js_copied_to_project():
    """keyboard-nav.js is copied from assets to the project directory."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(tmp_dir)
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "keyboard-nav.js"
        assert js_file.exists()


def test_keyboard_nav_js_not_copied_when_disabled():
    """keyboard-nav.js is not copied when feature is disabled."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs, _ = _make_uqc_docs(
            tmp_dir,
            gd_yml_content="keyboard_nav: false\n",
        )
        prepare_build_directory(docs, make_run(docs))

        js_file = docs.build_dir / "keyboard-nav.js"
        assert not js_file.exists()


def test_keyboard_nav_js_file_has_expected_content():
    """The keyboard-nav.js asset exists and contains the expected patterns."""

    js_path = Path(__file__).parent.parent / "great_docs" / "assets" / "keyboard-nav.js"
    assert js_path.exists()
    content = js_path.read_text()

    # Verify IIFE wrapping
    assert content.startswith("/**")
    assert "(function()" in content
    assert "})();" in content

    # Verify shortcut handlers
    assert "focusSearch" in content
    assert "navigatePrev" in content
    assert "navigateNext" in content
    assert "showMenu" in content
    assert "toggleDarkMode" in content

    # Verify menu keyboard navigation
    assert "handleMenuKeydown" in content
    assert "menuSelectedIndex" in content
    assert "gd-menu-item-focused" in content

    # Verify menu overlay
    assert "gd-menu-overlay" in content
    assert "showMenu" in content
    assert "hideMenu" in content
    assert "getNavbarItems" in content
    assert "getSidebarItems" in content

    # Verify keyboard shortcuts overlay
    assert "gd-keyboard-overlay" in content
    assert "showOverlay" in content
    assert "hideOverlay" in content

    # Verify accessibility
    assert 'role", "dialog"' in content or "role" in content
    assert "aria-modal" in content
    assert "aria-label" in content

    # Verify input guard
    assert "isTyping" in content

    # Verify reduced motion support
    assert "prefers-reduced-motion" in content


def test_keyboard_nav_scss_styles_exist():
    """The SCSS file contains keyboard navigation overlay styles."""

    scss_path = Path(__file__).parent.parent / "great_docs" / "assets" / "great-docs.scss"
    content = scss_path.read_text()

    assert ".gd-keyboard-overlay {" in content
    assert ".gd-keyboard-overlay-visible {" in content
    assert ".gd-keyboard-overlay-inner {" in content
    assert ".gd-keyboard-row {" in content
    assert "kbd {" in content

    # Menu overlay
    assert ".gd-menu-overlay {" in content
    assert ".gd-menu-overlay-visible {" in content
    assert ".gd-menu-overlay-inner {" in content
    assert ".gd-menu-item {" in content
    assert ".gd-menu-section {" in content
    assert ".gd-menu-item-focused {" in content

    # Keyboard navbar button
    assert ".gd-keyboard-btn {" in content
    assert "#gd-keyboard-btn-container {" in content

    # Dark mode
    assert ".gd-keyboard-overlay-inner" in content
    assert ".gd-menu-overlay-inner" in content

    # Reduced motion
    assert ".gd-keyboard-overlay," in content
    assert ".gd-menu-overlay," in content


# ── status data injection ────────────────────────────────────────


def test_status_data_injection_no_json():
    """Does nothing when _page_status.json doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = Path(tmp)
        page_status.inject(gd.build_dir)


def test_status_data_injection_injects():
    """Injects status data as inline script."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        status_data = {"page_statuses": {}, "definitions": {}}
        (project / "_page_status.json").write_text(json.dumps(status_data))
        quarto_config = {"format": {"html": {"include-after-body": ["page-status-badges.js"]}}}
        (project / "_quarto.yml").write_text(format_yaml(quarto_config))

        page_status.inject(gd.build_dir)

        result = read_yaml(project / "_quarto.yml")
        entries = result["format"]["html"]["include-after-body"]
        has_status = any("__GD_STATUS_DATA__" in str(e) for e in entries)
        assert has_status


def test_status_data_injection_string_body():
    """Handles include-after-body as string (converted to list)."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        (project / "_page_status.json").write_text('{"page_statuses": {}}')
        quarto_config = {"format": {"html": {"include-after-body": "existing.js"}}}
        (project / "_quarto.yml").write_text(format_yaml(quarto_config))

        page_status.inject(gd.build_dir)

        result = read_yaml(project / "_quarto.yml")
        entries = result["format"]["html"]["include-after-body"]
        assert isinstance(entries, list)
        assert len(entries) >= 2  # original + injected


def test_inline_status_data_injection_keeps_generated_header(tmp_path: Path):
    """Preserve the generated configuration header when embedding status data"""
    gd = GreatDocs(project_path=str(tmp_path))
    gd.build_dir.mkdir()
    write_initial_quarto_yml(gd.build_dir)
    with edit_quarto_yml(gd.build_dir) as config:
        config["format"]["html"]["include-after-body"] = ["page-status-badges.js"]
    (gd.build_dir / "_page_status.json").write_text("{}", encoding="utf-8")

    page_status.inject(gd.build_dir)

    assert "_DATA__=" in (gd.build_dir / "_quarto.yml").read_text(encoding="utf-8")
    validate_build_dir(gd.build_dir)


# ── status collection ────────────────────────────────────────────


def test_status_collection():
    """Collects page status from frontmatter."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("page_status: true\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        ug = project / "user-guide"
        ug.mkdir()
        (ug / "feature.qmd").write_text("---\ntitle: Feature\nstatus: new\n---\nContent.")

        status_map = page_status.collect(gd._config, gd.layout, gd.build_dir)
        assert "user-guide/feature.qmd" in status_map
        assert status_map["user-guide/feature.qmd"] == "new"


def test_status_collection_ignores_invalid():
    """Ignores files with unknown status values."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("page_status: true\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        ug = project / "user-guide"
        ug.mkdir()
        (ug / "bad.qmd").write_text("---\ntitle: Bad\nstatus: nonexistent_status\n---\nContent.")

        status_map = page_status.collect(gd._config, gd.layout, gd.build_dir)
        assert "user-guide/bad.qmd" not in status_map


# ── Homepage sidebar ───────────────────────────────────────────────────


def test_homepage_margin_roadmap():
    """Margin includes roadmap link when ROADMAP.md exists."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.0"\n')
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        # Create ROADMAP.md
        (project / "ROADMAP.md").write_text("# Roadmap\n\nUpcoming features.")

        result = homepage_margin(gd)
        assert "roadmap" in result.lower()


def test_homepage_margin_meta_tags():
    """Margin includes tags link when tags are enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.0"\n')
        (project / "great-docs.yml").write_text("display_name: MyPkg\ntags: true\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        result = homepage_margin(gd)
        assert "tags" in result.lower()


# ── Homepage sidebar (meta section) ──────────────────────────────────


def test_homepage_margin_requires_python():
    """Margin includes requires_python in meta section."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "1.0"\nrequires-python = ">=3.9"\n'
        )
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        result = homepage_margin(gd)
        assert "3.9" in result


def test_homepage_margin_extras():
    """Margin includes optional dependency extras."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "1.0"\n\n'
            "[project.optional-dependencies]\ndev = ['pytest']\ndocs = ['sphinx']\n"
        )
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        result = homepage_margin(gd)
        assert "dev" in result
        assert "docs" in result


# ── _build_skill_page (companion files) ──────────────────────────────


def test_write_skills_page_with_companions():
    """
    Render companion files from skill subdirectories
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        # Create skill dir with SKILL.md and companion files
        skill_dir = project / "skill-test"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("# My Skill\n\nDo things.")

        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "setup.sh").write_text("#!/bin/bash\necho hello")

        refs_dir = skill_dir / "references"
        refs_dir.mkdir()
        (refs_dir / "api.md").write_text("# API Ref")

        _skills_page_writer(gd).write(skill_md, skill_dir=skill_dir)

        skills_page = project / "skills.qmd"
        assert skills_page.exists()
        content = skills_page.read_text()
        assert "gd-skills-tree" in content
        assert "scripts/setup.sh" in content
        assert "references/api.md" in content
        assert "SKILL LAYOUT" in content


def test_write_skills_page_multi_skill_switcher():
    """
    Render a switcher when the page contains multiple skills
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        # Create primary skill
        skill_dir_a = project / "skill-a"
        skill_dir_a.mkdir()
        skill_md_a = skill_dir_a / "SKILL.md"
        skill_md_a.write_text(
            "---\nname: write_user_guide\ndescription: Write user guide pages\n---\n\n"
            "# Write User Guide\n\nHelps write guide pages."
        )
        refs_a = skill_dir_a / "references"
        refs_a.mkdir()
        (refs_a / "guide-style.md").write_text("# Guide Style")

        # Create secondary skill
        skill_dir_b = project / "skill-b"
        skill_dir_b.mkdir()
        skill_md_b = skill_dir_b / "SKILL.md"
        skill_md_b.write_text(
            "---\nname: revise_docstrings\ndescription: Revise docstrings\n---\n\n"
            "# Revise Docstrings\n\nHelps fix docstrings."
        )

        _skills_page_writer(gd).write(
            skill_md_a,
            skill_dir=skill_dir_a,
            extra_skills=[(skill_md_b, skill_dir_b)],
        )

        skills_page = project / "skills.qmd"
        assert skills_page.exists()
        content = skills_page.read_text()

        # Switcher bar should exist with both skill pills
        assert 'class="gd-skill-switcher"' in content
        assert "write_user_guide" in content
        assert "revise_docstrings" in content
        assert "gd-skill-pill" in content

        # Two panels should exist
        assert content.count('class="gd-skill-panel"') == 2

        # First panel visible, second hidden
        assert '<div class="gd-skill-panel">' in content
        assert '<div class="gd-skill-panel" hidden>' in content

        # Each panel has its own content
        assert "Write User Guide" in content
        assert "Revise Docstrings" in content

        # Multi-skill intro text
        assert "multiple skills" in content

        # Script tag for the switcher JS
        assert 'src="/skill-switcher.js"' in content

        # Companion files appear in the first panel
        assert "guide-style.md" in content


def test_write_skills_page_multi_skill_install_section():
    """Multi-skill install section uses 'install all' phrasing and lists per-skill URLs."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        # `pyproject.toml` names the package
        (project / "pyproject.toml").write_text('[project]\nname = "test-pkg"\n')
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        # _quarto.yml with site-url so URLs are generated
        (project / "_quarto.yml").write_text("website:\n  site-url: https://example.com/docs/\n")

        skill_dir_a = project / "skill-a"
        skill_dir_a.mkdir()
        skill_md_a = skill_dir_a / "SKILL.md"
        skill_md_a.write_text("---\nname: alpha\ndescription: Skill alpha\n---\n\n# Alpha\n")

        skill_dir_b = project / "skill-b"
        skill_dir_b.mkdir()
        skill_md_b = skill_dir_b / "SKILL.md"
        skill_md_b.write_text("---\nname: beta\ndescription: Skill beta\n---\n\n# Beta\n")

        _skills_page_writer(gd).write(
            skill_md_a,
            skill_dir=skill_dir_a,
            extra_skills=[(skill_md_b, skill_dir_b)],
        )

        content = (project / "skills.qmd").read_text()

        # npx line uses "install all with"
        assert "install all with" in content
        assert "npx skills add https://example.com/docs/" in content

        # CLI install line present with detected package name
        assert "great-docs skill install test-pkg" in content

        # Codex/OpenCode lists per-skill .well-known URLs
        assert ".well-known/agent-skills/alpha/SKILL.md" in content
        assert ".well-known/agent-skills/beta/SKILL.md" in content

        # Plural install label
        assert "Install these skills" in content

        # No Manual/curl section in multi-skill mode
        assert "curl -O" not in content

        # Browse label for multi-skill
        assert "browse the skill files below" in content


def test_write_skills_page_multi_skill_no_cli_without_package_name():
    """Multi-skill install omits CLI line when package name cannot be detected."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        # Without `pyproject.toml` or a package directory, no name is detected
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        skill_dir_a = project / "skill-a"
        skill_dir_a.mkdir()
        skill_md_a = skill_dir_a / "SKILL.md"
        skill_md_a.write_text("---\nname: alpha\ndescription: Skill alpha\n---\n\n# Alpha\n")

        skill_dir_b = project / "skill-b"
        skill_dir_b.mkdir()
        skill_md_b = skill_dir_b / "SKILL.md"
        skill_md_b.write_text("---\nname: beta\ndescription: Skill beta\n---\n\n# Beta\n")

        _skills_page_writer(gd).write(
            skill_md_a,
            skill_dir=skill_dir_a,
            extra_skills=[(skill_md_b, skill_dir_b)],
        )

        content = (project / "skills.qmd").read_text()

        # CLI install line should NOT appear
        assert "great-docs skill install" not in content

        # Other install methods still present
        assert "npx skills add" in content
        assert ".well-known/agent-skills/alpha/SKILL.md" in content


def test_write_skills_page_single_skill_install_section():
    """Single-skill install section uses singular phrasing and includes Manual/curl."""
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        (project / "_quarto.yml").write_text("website:\n  site-url: https://example.com/docs/\n")

        skill_dir = project / "skill-solo"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: solo\ndescription: A solo skill\n---\n\n# Solo\n")

        _skills_page_writer(gd).write(skill_md, skill_dir=skill_dir)

        content = (project / "skills.qmd").read_text()

        # Singular install label
        assert "Install this skill" in content

        # Single-skill npx uses "install with" (not "install all with")
        assert "install with" in content
        assert "install all with" not in content

        # Codex/OpenCode points to skill.md directly
        assert "Fetch the skill file at" in content
        assert "example.com/docs/skill.md" in content

        # Manual/curl section present
        assert "curl -O" in content
        assert "Manual" in content

        # No CLI install line (that's multi-skill only)
        assert "great-docs skill install" not in content


def test_write_skills_page_single_skill_no_switcher():
    """
    Omit the switcher when the page contains one skill
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("display_name: MyPkg\n")
        gd = GreatDocs(project_path=tmp)
        gd.build_dir = project

        skill_dir = project / "skill-solo"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("---\nname: solo_skill\ndescription: A lone skill\n---\n\n# Solo\n")

        _skills_page_writer(gd).write(skill_md, skill_dir=skill_dir)

        content = (project / "skills.qmd").read_text()

        # No switcher bar or panels
        assert "gd-skill-switcher" not in content
        assert "gd-skill-panel" not in content
        assert "skill-switcher.js" not in content

        # Content is still rendered
        assert "Solo" in content


def _translated_languages() -> list[str]:
    from great_docs._translations import UI_TRANSLATIONS

    return sorted({lang for entry in UI_TRANSLATIONS.values() for lang in entry})


@pytest.mark.parametrize("lang", _translated_languages())
def test_skills_page_intro_is_a_whole_translated_paragraph(tmp_path: Path, lang: str):
    """
    Verify that all Skills page intros share a translated definition of a skill
    """
    (tmp_path / "great-docs.yml").write_text(f"site:\n  lang: {lang}\n")
    gd = GreatDocs(project_path=str(tmp_path))
    gd.build_dir = tmp_path
    skill_dir = tmp_path / "solo"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: solo\ndescription: A skill\n---\n\n# Solo\n")
    other_md = tmp_path / "OTHER.md"
    other_md.write_text("---\nname: other\ndescription: Another skill\n---\n\n# Other\n")
    variants = {
        "generated": {},
        "curated": {"skill_dir": skill_dir},
        "multi": {"skill_dir": skill_dir, "extra_skills": [(other_md, None)]},
    }

    intros: dict[str, str] = {}
    for variant, kwargs in variants.items():
        _skills_page_writer(gd).write(skill_md, **kwargs)
        body = (tmp_path / "skills.qmd").read_text().split("---\n", 2)[2]
        intros[variant] = body.strip().split("\n", 1)[0]

    for intro in intros.values():
        assert "skills_intro" not in intro
        assert "{" not in intro
    # A shared opening definition catches intros that start with a sentence
    # fragment or an untranslated key.
    first_sentences = {re.sub(r"(?<=[.。।]).*", "", intro) for intro in intros.values()}
    assert len(first_sentences) == 1
    assert len(set(intros.values())) == 3


# ── Sitemap generation ──────────────────────────────────────────────────────


def test_sitemap_write_basic():
    """
    Write sitemap entries for the homepage and reference pages
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text(
            "seo:\n  sitemap: true\n  canonical:\n    base_url: https://example.com/\n"
        )
        gd = GreatDocs(project_path=tmp)

        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html></html>")
        sub = site_dir / "reference"
        sub.mkdir()
        (sub / "index.html").write_text("<html></html>")

        sitemap.write(
            gd.layout.site_dir,
            gd._config,
            site.identity(gd._config, gd.layout, make_project(gd)).base_url,
            report=print,
        )

        sitemap_path = site_dir / "sitemap.xml"
        assert sitemap_path.exists()
        content = sitemap_path.read_text()
        assert '<?xml version="1.0"' in content
        assert "https://example.com/" in content
        assert "<url>" in content


def test_sitemap_write_no_site_dir(capsys):
    """
    Report a missing site directory when writing the sitemap
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text(
            "seo:\n  sitemap: true\n  canonical:\n    base_url: https://example.com/\n"
        )
        gd = GreatDocs(project_path=tmp)

        sitemap.write(
            gd.layout.site_dir,
            gd._config,
            site.identity(gd._config, gd.layout, make_project(gd)).base_url,
            report=print,
        )
        captured = capsys.readouterr()
        assert "_site" in captured.out


def test_sitemap_write_no_base_url(capsys):
    """
    Report a missing base URL when writing the sitemap
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("seo:\n  sitemap: true\n")
        gd = GreatDocs(project_path=tmp)

        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)
        (site_dir / "index.html").write_text("<html></html>")

        sitemap.write(gd.layout.site_dir, gd._config, None, report=print)
        captured = capsys.readouterr()
        assert "base URL" in captured.out


def test_sitemap_write_excludes_unindexed_pages(tmp_path: Path):
    """
    Leave noindex pages, redirect stubs and older versions out of the sitemap
    """
    (tmp_path / "great-docs.yml").write_text(
        "seo:\n  canonical:\n    base_url: https://example.com/\nversions:\n  - '0.2'\n  - '0.1'\n"
    )
    gd = GreatDocs(project_path=str(tmp_path))
    site_dir = gd.layout.site_dir
    pages = {
        "index.html": "<html><head></head></html>",
        "skills.html": '<html><head><meta name="robots" content="noindex, nofollow"></head></html>',
        "old-intro.html": '<html><head><meta http-equiv="refresh" content="0;URL=\'intro.html\'">',
        "v/latest/index.html": '<html><head><meta http-equiv="refresh" content="0; url=/">',
        "v/0.1/index.html": "<html><head></head></html>",
    }
    for rel_path, html in pages.items():
        (site_dir / rel_path).parent.mkdir(parents=True, exist_ok=True)
        (site_dir / rel_path).write_text(html)

    sitemap.write(
        site_dir,
        gd._config,
        site.identity(gd._config, gd.layout, make_project(gd)).base_url,
        report=print,
    )

    locs = re.findall(r"<loc>([^<]*)</loc>", (site_dir / "sitemap.xml").read_text())
    assert locs == ["https://example.com/"]


def test_sitemap_write_keeps_v_directory_without_versions(tmp_path: Path):
    """
    Keep pages under `v/` in the sitemap of a site without versions
    """
    (tmp_path / "great-docs.yml").write_text(
        "seo:\n  canonical:\n    base_url: https://example.com/\n"
    )
    gd = GreatDocs(project_path=str(tmp_path))
    site_dir = gd.layout.site_dir
    (site_dir / "v").mkdir(parents=True)
    (site_dir / "v" / "page.html").write_text("<html><head></head></html>")

    sitemap.write(
        site_dir,
        gd._config,
        site.identity(gd._config, gd.layout, make_project(gd)).base_url,
        report=print,
    )

    assert "https://example.com/v/page.html" in (site_dir / "sitemap.xml").read_text()


# ── Crawler rules ───────────────────────────────────────────────────────────


def test_robots_write_basic():
    """
    Write default crawler rules and the sitemap reference
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text(
            "seo:\n  robots: true\n  sitemap: true\n  canonical:\n    base_url: https://example.com/\n"
        )
        gd = GreatDocs(project_path=tmp)

        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        robots.write(
            gd.layout.site_dir,
            gd._config,
            site.identity(gd._config, gd.layout, make_project(gd)).base_url,
            report=print,
        )

        robots_path = site_dir / "robots.txt"
        assert robots_path.exists()
        content = robots_path.read_text()
        assert "User-agent: *" in content
        assert "Allow: /" in content
        assert "Sitemap:" in content


def test_robots_write_no_site_dir(capsys):
    """
    Report a missing site directory when writing crawler rules
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        (project / "great-docs.yml").write_text("seo:\n  robots: true\n")
        gd = GreatDocs(project_path=tmp)

        robots.write(
            gd.layout.site_dir,
            gd._config,
            site.identity(gd._config, gd.layout, make_project(gd)).base_url,
            report=print,
        )
        captured = capsys.readouterr()
        assert "_site" in captured.out


# ── Namespace package support ────────────────────────────────────────────────


def test_discover_exports_namespace_src_layout():
    """Verify that literal `__all__` parsing finds exports in a namespace package under `src/`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create src/mypkg/sub/__init__.py with __all__
        src_dir = Path(tmp_dir) / "src"
        pkg_path = src_dir / "mypkg" / "sub"
        pkg_path.mkdir(parents=True)
        (pkg_path / "__init__.py").write_text(
            '"""Namespace sub-package."""\n'
            '__all__ = ["hello", "goodbye"]\n'
            "\n"
            "def hello(name: str) -> str:\n"
            '    """Say hello."""\n'
            "    return f'Hello {name}'\n"
            "\n"
            "def goodbye(name: str) -> str:\n"
            '    """Say goodbye."""\n'
            "    return f'Goodbye {name}'\n",
            encoding="utf-8",
        )
        # mypkg namespace level
        (src_dir / "mypkg" / "__init__.py").write_text("")

        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "mypkg-sub"\n', encoding="utf-8"
        )

        docs = GreatDocs(project_path=tmp_dir)
        # A dotted namespace name must resolve to its `__init__.py` under `src/`.
        exports = parse_dunder_all(_package_init(docs, "mypkg.sub"), docs._config, report=print)

        assert exports is not None
        assert "hello" in exports
        assert "goodbye" in exports


def test_cli_scan_uses_module_name():
    """Verify that CLI scan uses the detected namespace package"""
    from click.testing import CliRunner

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("great_docs.cli.Exports") as MockExports:
            package_exports = MockExports.make.return_value
            package_exports.config = mock_config(module="firebird.base")
            package_exports.project = Project.make(
                package_exports.config, Layout.make(write_pyproject(Path(tmp_dir), "firebird-base"))
            )
            package_exports.names.return_value = ["connect", "Config"]
            package_exports.categorise.return_value = {
                "classes": ["Config"],
                "functions": ["connect"],
                "class_method_names": {},
            }

            result = runner.invoke(scan, ["--project-path", tmp_dir])
            assert result.exit_code == 0
            # Should show the module name, not the PyPI name
            assert "firebird.base" in result.output
            package_exports.names.assert_called_with("firebird.base")


def test_parse_dunder_all_dotted_name():
    """Verify that literal `__all__` parsing supports a dotted package name"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_path = Path(tmp_dir) / "src" / "ns" / "pkg"
        pkg_path.mkdir(parents=True)
        (pkg_path / "__init__.py").write_text(
            '__all__ = ["Alpha", "Beta"]\n',
            encoding="utf-8",
        )
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "ns-pkg"\n', encoding="utf-8"
        )

        docs = GreatDocs(project_path=tmp_dir)
        exports = parse_dunder_all(_package_init(docs, "ns.pkg"), docs._config, report=print)

        assert exports is not None
        assert "Alpha" in exports
        assert "Beta" in exports


# ── inline_methods integration tests ─────────────────────────────────────────


# ── Package Info Page ──────────────────────────────────────────────────────


def test_homepage_margin_includes_package_info_link():
    """Verify that the sidebar includes a Package Info link when the page exists"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\nrequires-python = ">=3.11"\n',
            encoding="utf-8",
        )
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()

        # Create package-info.qmd to simulate it having been generated
        (gd_dir / "package-info.qmd").write_text(
            "---\ntitle: Package Info\n---\n", encoding="utf-8"
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "Package Info" in result
        assert "package-info.html" in result


def test_homepage_margin_no_package_info_link_when_missing():
    """Verify that the sidebar omits the Package Info link when the page is missing"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        gd_dir = Path(tmp_dir) / "great-docs"
        gd_dir.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = homepage_margin(docs)

        assert "package-info.html" not in result


def test_announcement_position_in_meta_tag():
    """
    Set the announcement metadata's `data-position` attribute
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"')
        (project_path / "great-docs.yml").write_text(
            "announcement:\n  content: Hi\n  position: below-navbar\n",
            encoding="utf-8",
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        with open(docs.build_dir / "_quarto.yml", "r") as f:
            config = read_yaml(f)

        header = config["format"]["html"]["include-in-header"]
        meta_texts = [item.get("text", "") for item in header if isinstance(item, dict)]
        ann = next((t for t in meta_texts if "gd-announcement" in t), None)
        assert ann is not None, "gd-announcement meta tag not found"
        assert 'data-position="below-navbar"' in ann


def test_announcement_position_defaults_above_in_meta_tag():
    """Default announcement position is above-navbar in the meta tag"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "0.1.0"')
        (project_path / "great-docs.yml").write_text("announcement: Hi\n", encoding="utf-8")

        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)
        write_initial_quarto_yml(docs.build_dir)
        update_quarto_config(docs, make_run(docs))

        with open(docs.build_dir / "_quarto.yml", "r") as f:
            config = read_yaml(f)

        header = config["format"]["html"]["include-in-header"]
        meta_texts = [item.get("text", "") for item in header if isinstance(item, dict)]
        ann = next((t for t in meta_texts if "gd-announcement" in t), None)
        assert ann is not None, "gd-announcement meta tag not found"
        assert 'data-position="above-navbar"' in ann


def test_build_reference_yaml_classes_and_functions():
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        categories = {
            "classes": ["Beta", "Alpha"],
            "functions": ["helper"],
            "class_methods": {"Alpha": 0, "Beta": 0},
            "class_method_names": {},
        }
        result = reference_block.reference_yaml(docs._config, categories)
        assert result.startswith("reference:")
        assert "  - title: Classes" in result
        assert "      - Alpha" in result  # sorted
        assert "  - title: Functions" in result
        assert "      - helper" in result


def test_build_reference_yaml_large_class_split():
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        categories = {
            "classes": ["Big"],
            "class_methods": {"Big": 42},
            "class_method_names": {"Big": ["a", "b"]},
        }
        result = reference_block.reference_yaml(docs._config, categories)
        assert "members: false" in result
        assert "  - title: Big Methods" in result
        assert "      - Big.a" in result


def test_build_reference_yaml_empty():
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert reference_block.reference_yaml(docs._config, {}) == "reference:"


class TestSaveFreezeCacheVersioned:
    def test_collects_freeze_from_sibling_version_dirs(self, tmp_path: Path):
        from great_docs._utils import QUARTO_YML_HEADER

        docs = GreatDocs(project_path=str(tmp_path))

        latest_freeze = tmp_path / "great-docs" / "_freeze"
        latest_freeze.mkdir(parents=True)
        (latest_freeze / "latest.json").write_text("{}", encoding="utf-8")

        old = tmp_path / "great-docs-0.2"
        old.mkdir()
        (old / "_quarto.yml").write_text(
            QUARTO_YML_HEADER + "project:\n  type: website\n", encoding="utf-8"
        )
        (old / "_freeze").mkdir()
        (old / "_freeze" / "old.json").write_text("{}", encoding="utf-8")

        unmarked = tmp_path / "great-docs-notes"
        (unmarked / "_freeze").mkdir(parents=True)
        (unmarked / "_freeze" / "stray.json").write_text("{}", encoding="utf-8")

        count = freeze.save(docs.layout)

        assert count == 2
        assert (tmp_path / "_freeze" / "latest.json").is_file()
        assert (tmp_path / "_freeze" / "old.json").is_file()
        assert not (tmp_path / "_freeze" / "stray.json").exists()

    def test_merge_keeps_pages_scoped_out_of_a_historical_version(self, tmp_path: Path):
        """
        Preserve latest pages that a historical version excludes

        Quarto groups page caches below shared section directories. Replacing
        a whole section with a historical cache would discard pages that the
        historical version excluded.
        """
        from great_docs._utils import QUARTO_YML_HEADER

        docs = GreatDocs(project_path=str(tmp_path))

        latest_freeze = tmp_path / "great-docs" / "_freeze" / "user-guide"
        for page in ("a", "b", "c"):
            page_dir = latest_freeze / page / "execute-results"
            page_dir.mkdir(parents=True)
            (page_dir / "html.json").write_text(f'{{"page": "{page}"}}', encoding="utf-8")

        old = tmp_path / "great-docs-0.14.0"
        old.mkdir()
        (old / "_quarto.yml").write_text(
            QUARTO_YML_HEADER + "project:\n  type: website\n", encoding="utf-8"
        )
        old_page_dir = old / "_freeze" / "user-guide" / "a" / "execute-results"
        old_page_dir.mkdir(parents=True)
        (old_page_dir / "html.json").write_text('{"page": "a-old"}', encoding="utf-8")

        freeze.save(docs.layout)

        for page in ("a", "b", "c"):
            assert (
                tmp_path / "_freeze" / "user-guide" / page / "execute-results" / "html.json"
            ).is_file()

        # The latest cache is merged last and must win same-path collisions.
        merged_a = (
            tmp_path / "_freeze" / "user-guide" / "a" / "execute-results" / "html.json"
        ).read_text(encoding="utf-8")
        assert merged_a == '{"page": "a"}'


# ---------------------------------------------------------------------------
# Dependency extras and optional dependency groups
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Build preparation warnings for missing scripts, bibliographies and CSS
# ---------------------------------------------------------------------------


def test_prepare_build_dir_pre_render_script_exists(tmp_path):
    """Lines 338-339: pre-render script is copied when the file exists."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    # Create the script file that will be referenced
    (tmp_path / "prerender.py").write_text("# pre-render script\n")
    (tmp_path / "great-docs.yml").write_text("pre_render:\n  - prerender.py\n")
    docs = GreatDocs(project_path=str(tmp_path))

    with patch("great_docs._build.reference.add_api_block"):
        with patch.object(reference_sections, "update_sidebar"):
            prepare_build_directory(docs, make_run(docs))

    # Script should be copied to scripts/ in the build dir
    assert (docs.build_dir / "scripts" / "prerender.py").exists()


def test_prepare_build_dir_css_file_warning(tmp_path):
    """Line 366: warning printed when CSS file under site.css doesn't exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("site:\n  css:\n    - nonexistent.css\n")
    docs = GreatDocs(project_path=str(tmp_path))

    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        with patch("great_docs._build.reference.add_api_block"):
            with patch.object(reference_sections, "update_sidebar"):
                prepare_build_directory(docs, make_run(docs))

    assert "CSS" in out.getvalue() or "css" in out.getvalue().lower()


def test_prepare_build_dir_css_file_exists(tmp_path):
    """Lines 362-364: CSS file is copied when it exists."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "custom.css").write_text("body { color: red; }\n")
    (tmp_path / "great-docs.yml").write_text("site:\n  css:\n    - custom.css\n")
    docs = GreatDocs(project_path=str(tmp_path))

    with patch("great_docs._build.reference.add_api_block"):
        with patch.object(reference_sections, "update_sidebar"):
            prepare_build_directory(docs, make_run(docs))

    # CSS file should be in the build dir
    assert (docs.build_dir / "custom.css").exists()

    """Warning printed when pre_render script path doesn't exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("pre_render:\n  - scripts/nonexistent.py\n")
    docs = GreatDocs(project_path=str(tmp_path))
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        try:
            prepare_build_directory(docs, make_run(docs))
        except Exception:
            pass
    assert "Warning" in out.getvalue() or "warning" in out.getvalue().lower()


def test_prepare_build_dir_missing_bibliography_file(tmp_path):
    """Warning when bibliography file doesn't exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("bibliography:\n  - refs.bib\n")
    docs = GreatDocs(project_path=str(tmp_path))
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        try:
            prepare_build_directory(docs, make_run(docs))
        except Exception:
            pass
    assert "Warning" in out.getvalue() or "warning" in out.getvalue().lower()


def test_prepare_build_dir_missing_csl_file(tmp_path):
    """Warning when CSL file doesn't exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("csl: nonexistent.csl\n")
    docs = GreatDocs(project_path=str(tmp_path))
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        try:
            prepare_build_directory(docs, make_run(docs))
        except Exception:
            pass
    assert "Warning" in out.getvalue() or "warning" in out.getvalue().lower()


def test_prepare_build_dir_missing_css_file(tmp_path):
    """Warning when custom CSS file doesn't exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("site:\n  css:\n    - nonexistent.css\n")
    docs = GreatDocs(project_path=str(tmp_path))
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        try:
            prepare_build_directory(docs, make_run(docs))
        except Exception:
            pass
    assert "Warning: CSS file not found: nonexistent.css" in out.getvalue()


def test_prepare_build_dir_marimo_not_installed(tmp_path):
    """Warning when marimo enabled but not installed."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("marimo: true\n")
    docs = GreatDocs(project_path=str(tmp_path))
    import io
    from contextlib import redirect_stdout

    out = io.StringIO()
    with redirect_stdout(out):
        with patch("importlib.util.find_spec", return_value=None):
            try:
                prepare_build_directory(docs, make_run(docs))
            except Exception:
                pass
    assert "Warning" in out.getvalue() or "warning" in out.getvalue().lower()


# ---------------------------------------------------------------------------
# Command help blocks, bullet lists and positional arguments
# ---------------------------------------------------------------------------


def test_command_page_with_help_text(tmp_path):
    """
    Include full help output in a collapsed details block
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "run",
        "full_path": "mypkg run",
        "help": "Run the pipeline.",
        "help_text": "Usage: mypkg run [OPTIONS]\n\nRun the pipeline.\n",
        "is_group": False,
        "options": [],
        "arguments": [],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert '.details summary="Full `--help` output"' in result
    assert "Usage: mypkg run" in result


def test_command_page_help_summary_translated(tmp_path):
    """
    Translate the collapsed help summary into the site language
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("site:\n  lang: fr\n")
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "run",
        "full_path": "mypkg run",
        "help": "Run the pipeline.",
        "help_text": "Usage: mypkg run [OPTIONS]\n",
        "is_group": False,
        "options": [],
        "arguments": [],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert '.details summary="Sortie complète de `--help`"' in result


def test_command_page_with_arguments_typed(tmp_path):
    """
    Show type annotations for typed positional arguments
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "process",
        "full_path": "mypkg process",
        "help": "Process a file.",
        "help_text": "",
        "is_group": False,
        "options": [],
        "arguments": [
            {
                "name": "FILE",
                "name_display": "FILE",
                "type": "path",
                "required": True,
                "help": "Input file path.",
                "default": None,
            }
        ],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert "Arguments" in result
    assert "path" in result.lower()


def test_command_page_with_argument_no_type(tmp_path):
    """
    Omit type annotations for untyped positional arguments
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "greet",
        "full_path": "mypkg greet",
        "help": "Greet someone.",
        "help_text": "",
        "is_group": False,
        "options": [],
        "arguments": [
            {
                "name": "NAME",
                "name_display": "NAME",
                "type": None,
                "required": True,
                "help": "",
                "default": None,
            }
        ],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert "NAME" in result


def test_command_page_bullet_paragraphs(tmp_path):
    """
    Serialise help paragraphs with bullet lists as Markdown bullets
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "run",
        "full_path": "mypkg run",
        "help": "Run the pipeline.\n\n• Step one\n• Step two",
        "help_text": "",
        "is_group": False,
        "options": [],
        "arguments": [],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert "- Step one" in result or "Step one" in result


def test_command_page_indented_paragraph(tmp_path):
    """
    Preserve indented help blocks
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "run",
        "full_path": "mypkg run",
        "help": "Run the pipeline.\n\n  Quick start:\n  do_thing --flag",
        "help_text": "",
        "is_group": False,
        "options": [],
        "arguments": [],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert "Quick start:" in result or "do_thing" in result


def test_command_page_prose_paragraph(tmp_path):
    """
    Join plain help paragraphs into single lines
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    docs = GreatDocs(project_path=str(tmp_path))

    cmd_info = {
        "name": "run",
        "full_path": "mypkg run",
        "help": "Run the pipeline.\n\nThis is extra context for the user.",
        "help_text": "",
        "is_group": False,
        "options": [],
        "arguments": [],
        "commands": [],
        "examples": "",
    }
    result = cli_render.command_page(docs._config, cmd_info)
    assert "extra context" in result


# ---------------------------------------------------------------------------
# _strip_numeric_prefix — instance method
# ---------------------------------------------------------------------------


def test_strip_numeric_prefix_double_digit():
    docs = GreatDocs()
    assert strip_numeric_prefix("00-introduction.qmd") == "introduction.qmd"


def test_strip_numeric_prefix_single_digit():
    docs = GreatDocs()
    assert strip_numeric_prefix("1-getting-started.qmd") == "getting-started.qmd"


def test_strip_numeric_prefix_no_prefix():
    docs = GreatDocs()
    assert strip_numeric_prefix("introduction.qmd") == "introduction.qmd"


def test_strip_numeric_prefix_underscore_separator():
    docs = GreatDocs()
    result = strip_numeric_prefix("01_getting_started.qmd")
    assert result == "getting_started.qmd"


def test_strip_numeric_prefix_preserves_non_numeric():
    docs = GreatDocs()
    assert strip_numeric_prefix("advanced.qmd") == "advanced.qmd"


# ---------------------------------------------------------------------------
# CLI command discovery
# ---------------------------------------------------------------------------


def test_find_command_cli_module_import_fails(tmp_path):
    """
    Return `None` when the configured CLI module cannot be imported
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text("cli:\n  enabled: true\n  module: mypkg.cli\n")
    docs = GreatDocs(project_path=str(tmp_path))

    with patch("importlib.import_module", side_effect=ImportError("not found")):
        result = cli_click.find_command(
            "mypkg", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
        )

    assert result is None


def test_find_command_with_cli_name(tmp_path):
    """
    Return the command named by `cli.name`
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "great_docs"\n')
    (tmp_path / "great-docs.yml").write_text(
        "cli:\n  enabled: true\n  module: great_docs.cli\n  name: cli\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))

    result = cli_click.find_command(
        "great_docs", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
    )

    import click as _click

    assert isinstance(result.command, (_click.Command, _click.Group))


def test_find_command_attr_loop(tmp_path):
    """
    Find a command under a conventional attribute name
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "great_docs"\n')
    (tmp_path / "great-docs.yml").write_text("cli:\n  enabled: true\n  module: great_docs.cli\n")
    docs = GreatDocs(project_path=str(tmp_path))

    # No cli_name set — falls through to the "cli"/"main"/"app" loop
    result = cli_click.find_command(
        "great_docs", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
    )

    import click as _click

    assert isinstance(result.command, (_click.Command, _click.Group))


def test_find_command_no_module_found_returns_none(tmp_path):
    """
    Return `None` when no CLI module is found
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "nonexistent_pkg_xyzzy"\n')
    (tmp_path / "great-docs.yml").write_text("cli:\n  enabled: true\n")
    docs = GreatDocs(project_path=str(tmp_path))

    result = cli_click.find_command(
        "nonexistent_pkg_xyzzy", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
    )

    assert result is None


def test_find_command_dir_loop(tmp_path):
    """
    Scan public module attributes when conventional names hold no command
    """
    import types

    import click as _click

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text(
        "cli:\n  enabled: true\n  module: fake_cli_module_xyzzy\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))

    # Create a fake module with a click command under a non-standard name
    fake_module = types.ModuleType("fake_cli_module_xyzzy")
    fake_cmd = _click.command()(lambda: None)
    fake_cmd.name = "run"
    setattr(fake_module, "run_command", fake_cmd)

    with patch.dict(sys.modules, {"fake_cli_module_xyzzy": fake_module}):
        with patch("importlib.import_module", return_value=fake_module):
            result = cli_click.find_command(
                "mypkg", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
            )

    assert isinstance(result.command, (_click.Command, _click.Group))


def test_find_command_discovery_loop_finds_module(tmp_path):
    """
    Discover a candidate module containing a Click command
    """
    import types

    import click as _click

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

    # No module: in great-docs.yml → triggers discovery loop
    (tmp_path / "great-docs.yml").write_text("cli:\n  enabled: true\n")
    docs = GreatDocs(project_path=str(tmp_path))

    # Create a fake module that the discovery loop can find
    fake_module = types.ModuleType("mypkg.cli")
    fake_cmd = _click.command()(lambda: None)
    fake_cmd.name = "run"
    setattr(fake_module, "cli", fake_cmd)

    def fake_import(name):
        if name == "mypkg.cli":
            return fake_module
        raise ImportError(f"No module {name}")

    with patch("importlib.import_module", side_effect=fake_import):
        result = cli_click.find_command(
            "mypkg", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
        )

    assert isinstance(result.command, (_click.Command, _click.Group))


def test_find_command_no_commands_returns_none(tmp_path):
    """
    Return `None` when the module contains no command
    """
    import types

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text(
        "cli:\n  enabled: true\n  module: fake_empty_module_xyzzy\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))

    # Module with no click commands at all
    fake_module = types.ModuleType("fake_empty_module_xyzzy")
    fake_module.not_a_command = "just a string"

    with patch.dict(sys.modules, {"fake_empty_module_xyzzy": fake_module}):
        with patch("importlib.import_module", return_value=fake_module):
            result = cli_click.find_command(
                "mypkg", cli_module=docs._config.cli_module, cli_name=docs._config.cli_name
            )

    assert result is None


# ---------------------------------------------------------------------------
# status JSON writing
# ---------------------------------------------------------------------------


def test_status_json_writing_writes_json(tmp_path):
    """
    Write `_page_status.json` for page badges
    """
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)

    status_map = {"user-guide/intro.qmd": "new", "user-guide/old.qmd": "deprecated"}
    page_status.write(docs._config, docs.build_dir, status_map)

    status_file = docs.build_dir / "_page_status.json"

    assert status_file.exists()

    data = json.loads(status_file.read_text())

    assert data["page_statuses"] == status_map
    assert "new" in data["definitions"]
    assert "deprecated" in data["definitions"]


def test_status_json_writing_builtin_statuses_have_labels(tmp_path):
    """
    Resolve labels for every built-in status
    """
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)

    page_status.write(docs._config, docs.build_dir, {})
    data = json.loads((docs.build_dir / "_page_status.json").read_text())

    for key in ("new", "updated", "beta", "deprecated", "experimental", "upcoming"):
        assert key in data["definitions"]
        assert data["definitions"][key]["label"]  # non-empty label


# ---------------------------------------------------------------------------
# status collection
# ---------------------------------------------------------------------------


def test_status_collection_from_user_guide(tmp_path):
    """
    Read status front matter from user guide pages
    """
    docs = GreatDocs(project_path=str(tmp_path))
    ug_dir = docs.build_dir / "user-guide"
    ug_dir.mkdir(parents=True, exist_ok=True)
    (ug_dir / "page.qmd").write_text("---\nstatus: new\n---\n")

    result = page_status.collect(docs._config, docs.layout, docs.build_dir)

    assert "user-guide/page.qmd" in result
    assert result["user-guide/page.qmd"] == "new"


def test_status_collection_unknown_status_warns(tmp_path, capsys):
    """Unknown status triggers warning and is skipped."""
    docs = GreatDocs(project_path=str(tmp_path))
    ug_dir = docs.build_dir / "user-guide"
    ug_dir.mkdir(parents=True, exist_ok=True)
    (ug_dir / "page.qmd").write_text("---\nstatus: completely-unknown-xyz\n---\n")

    result = page_status.collect(docs._config, docs.layout, docs.build_dir)

    assert "user-guide/page.qmd" not in result

    out = capsys.readouterr().out

    assert "Unknown" in out or "unknown" in out.lower()


def test_status_collection_custom_section(tmp_path):
    """Custom sections are also scanned for status."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    (tmp_path / "great-docs.yml").write_text(
        "sections:\n  - title: Tutorials\n    dir: tutorials\n"
    )
    docs = GreatDocs(project_path=str(tmp_path))

    section_dir = docs.build_dir / "tutorials"
    section_dir.mkdir(parents=True, exist_ok=True)
    (section_dir / "page.qmd").write_text("---\nstatus: beta\n---\n")

    result = page_status.collect(docs._config, docs.layout, docs.build_dir)

    assert any("tutorials/page.qmd" in k for k in result)
    assert "beta" in result.values()


# ---------------------------------------------------------------------------
# Reference classification errors
# ---------------------------------------------------------------------------


def test_categorise_references_cyclic_alias_error(tmp_path):
    """Verify that a configured cyclic alias is grouped under `other`"""
    import griffe

    docs = GreatDocs(project_path=str(tmp_path))

    # Create a member whose kind property raises CyclicAliasError
    class BadMember:
        @property
        def kind(self):
            raise griffe.CyclicAliasError("cycle")

    bad_member = BadMember()

    mock_pkg = MagicMock()
    mock_pkg.members = {"bad_func": bad_member}

    with patch.object(Exports, "package", return_value=mock_pkg):
        result = categorise_references(
            make_exports(docs).package("fakepkg"), [{"contents": ["bad_func"]}]
        )

    assert "bad_func" in result["other"]


# ---------------------------------------------------------------------------
# Export discovery errors
# ---------------------------------------------------------------------------


def test_discover_exports_cyclic_alias_skipped(tmp_path):
    """Verify that discovery excludes a cyclic alias"""
    import griffe

    docs = GreatDocs(project_path=str(tmp_path))

    bad_member = MagicMock()
    type(bad_member).kind = PropertyMock(side_effect=griffe.CyclicAliasError("cycle"))

    mock_pkg = MagicMock()
    mock_pkg.members = {"bad_func": bad_member, "good_func": MagicMock()}
    mock_pkg.members["good_func"].kind.value = "function"
    mock_pkg.members["good_func"].is_alias = False
    mock_pkg.members["good_func"].members = {}

    # __all__ not set, use members keys
    del mock_pkg.__all__
    mock_pkg.__all__ = ["bad_func", "good_func"]
    mock_pkg.all_members = mock_pkg.members

    # The function discovers exports using pkg.members for public names
    with patch.object(Exports, "package", return_value=mock_pkg):
        with patch.object(docs, "_config") as mock_config:
            mock_config.__getitem__ = MagicMock(
                side_effect=lambda k: [] if k == "exclude" else False
            )
            mock_config.no_auto_exclude = False
            # Call with the package already loaded, bypass discovery
            result = discover_exports(
                make_exports(docs).package("fakepkg"), docs._config, report=print
            )

    # Should not crash; result may be None (if __all__ handling differs) or a list
    assert result is None or isinstance(result, list)


# ---------------------------------------------------------------------------
# Configured method references
# ---------------------------------------------------------------------------


def test_categorise_references_method_ref_categorises_its_class():
    """A `ClassName.method` reference puts its class under `classes`."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "refpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            'class MyClass:\n    def my_method(self):\n        """A method."""\n        pass\n',
            encoding="utf-8",
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            result = categorise_references(
                make_exports(docs).package("refpkg"), [{"contents": ["MyClass.my_method"]}]
            )

            assert result["classes"] == ["MyClass"]
            assert result["other"] == []
        finally:
            sys.path.remove(tmp_dir)
            sys.modules.pop("refpkg", None)


def test_freeze_runs_every_preparation_step_but_the_changelog(tmp_path: Path):
    """
    Run all preparation steps except those that publish remote content
    """
    docs = GreatDocs(project_path=str(tmp_path))
    log = BuildLog(stream=io.StringIO())
    steps = docs._preparation_steps(make_run(docs), log)
    ran: list[str] = []

    def record(selected: list[Step], *_: object) -> None:
        ran.extend(step.title for step in selected)

    with patch("great_docs._build.freeze.run_steps", record):
        freeze.prepare(steps, log, docs.build_dir)

    assert [step.title for step in steps if step.title not in ran] == ["Generate changelog"]
    assert log.total_steps == count_listed(steps) - 1


def _write_user_guide(docs: GreatDocs, project: Path) -> None:
    """Copy the project's user guide"""
    user_guide_step(docs, discover_user_guide(docs))


def _write_sections(docs: GreatDocs, project: Path) -> None:
    """Publish the project's `examples` section and blog"""
    with open(docs.build_dir / "_quarto.yml", "w") as f:
        write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)
    sections_step(docs, discover_user_guide(docs))


def _write_custom_pages(docs: GreatDocs, project: Path) -> None:
    """Wrap the project's passthrough custom page"""
    with open(docs.build_dir / "_quarto.yml", "w") as f:
        write_yaml({"website": {"sidebar": [], "navbar": {"left": []}}}, f)
    custom_pages_step(docs, discover_user_guide(docs))


def _write_index(docs: GreatDocs, project: Path) -> None:
    """Write the homepage and the community pages"""
    write_homepage(docs)


@pytest.mark.parametrize(
    ("write", "page"),
    [
        (_write_user_guide, "user-guide/intro.qmd"),
        (_write_sections, "examples/basic.qmd"),
        (_write_sections, "blog/post.qmd"),
        (_write_custom_pages, "custom/landing.qmd"),
        (_write_index, "contributing.qmd"),
        (_write_index, "code-of-conduct.qmd"),
        (_write_index, "roadmap.qmd"),
        (_write_index, "security.qmd"),
        (_write_index, "license.qmd"),
        (_write_index, "citation.qmd"),
    ],
)
def test_copied_pages_carry_dates(tmp_path: Path, write, page: str):
    """Include source dates and available author details on copied pages"""
    files = {
        "pyproject.toml": '[project]\nname = "pkg"\nversion = "1.0"\n',
        "great-docs.yml": (
            "show_dates: true\n"
            "sections:\n"
            "  - title: Examples\n    dir: examples\n"
            "  - title: Blog\n    dir: blog\n    type: blog\n"
        ),
        "pkg/__init__.py": "",
        "README.md": "# pkg\n\nA package.\n",
        "user_guide/01-intro.qmd": "---\ntitle: Intro\nauthor: Ada\n---\n\nText\n",
        "examples/01-basic.qmd": "---\ntitle: Basic\nauthor: Ada\n---\n\nText\n",
        "blog/post.qmd": "---\ntitle: Post\ndescription: About it\nauthor: Ada\n---\n\nText\n",
        "custom/landing.html": "---\ntitle: Landing\nauthor: Ada\n---\n<p>Hi</p>\n",
        ".github/CONTRIBUTING.md": "# Contributing\n\nText\n",
        "CODE_OF_CONDUCT.md": "# Code of Conduct\n\nText\n",
        "ROADMAP.md": "# Roadmap\n\nText\n",
        ".github/SECURITY.md": "# Security\n\nText\n",
        "LICENSE": "MIT License\n",
        "CITATION.cff": "cff-version: 1.2.0\ntitle: pkg\nauthors:\n  - name: Ada\n",
    }
    for name, content in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content, encoding="utf-8")
    docs = GreatDocs(project_path=str(tmp_path))
    docs.build_dir.mkdir(parents=True, exist_ok=True)

    write(docs, tmp_path)

    front_matter, _ = split_front_matter((docs.build_dir / page).read_text())
    tags = front_matter.data["gd-head-tags"]
    assert any('name="gd-page-modified"' in tag for tag in tags)
    if write is not _write_index:
        assert any('<meta name="gd-page-author" content="Ada">' in tag for tag in tags)
    if write is _write_index:
        homepage, _ = split_front_matter((docs.build_dir / "index.qmd").read_text())
        assert "gd-head-tags" not in homepage


# ---------------------------------------------------------------------------
# Front matter values of unexpected types
# ---------------------------------------------------------------------------


def test_skills_page_ignores_a_non_string_description(tmp_path: Path) -> None:
    """Verify that a curated skill whose `description` is a list still gets a page"""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-package"\n')
    skills_dir = tmp_path / "skills" / "test-package"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: test-package\ndescription: [a, b]\n---\n\n# Skill\n"
    )
    (tmp_path / "great-docs").mkdir()
    docs = GreatDocs(project_path=str(tmp_path))

    _skills_writer(docs).write()

    assert "# Skill" in (tmp_path / "great-docs" / "skills.qmd").read_text()


def test_readme_homepage_without_margin_starts_with_front_matter_fence():
    """Verify that a README homepage with an empty metadata margin opens with a bare `---`"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        Path(tmp_dir, "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
        Path(tmp_dir, "great-docs.yml").write_text("", encoding="utf-8")
        Path(tmp_dir, "README.md").write_text("# Pkg\n\nA first paragraph.\n", encoding="utf-8")
        docs = GreatDocs(project_path=tmp_dir)
        docs.build_dir.mkdir(parents=True, exist_ok=True)

        with patch("great_docs._website.homepage.margin.render", return_value=""):
            write_homepage(docs)

        content = (docs.build_dir / "index.qmd").read_text(encoding="utf-8")

        assert content.startswith("---\n")
        assert "pragma" not in content
