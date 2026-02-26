# pyright: reportPrivateUsage=false
import tempfile
from pathlib import Path

import pytest

from great_docs import GreatDocs, Config, load_config, create_default_config


def test_great_docs_init():
    """Test GreatDocs initialization."""
    docs = GreatDocs()
    assert docs.project_root == Path.cwd()


def test_great_docs_init_with_path():
    """Test GreatDocs initialization with custom path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs.project_root == Path(tmp_dir)


def test_install_creates_files():
    """Test that install creates the expected files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)

        # Check that config file was created
        project_path = Path(tmp_dir)
        assert (project_path / "great-docs.yml").exists()

        # Check that .gitignore was updated (or created)
        gitignore_path = project_path / ".gitignore"
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            assert "great-docs/" in content


def test_uninstall_removes_files():
    """Test that uninstall removes the docs files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Install first
        docs.install(force=True)

        project_path = Path(tmp_dir)
        assert (project_path / "great-docs.yml").exists()

        # Then uninstall
        docs.uninstall()

        # Check that config was removed
        assert not (project_path / "great-docs.yml").exists()

        # Check that great-docs directory was removed if it existed
        assert not (project_path / "great-docs").exists()


def test_parse_package_exports():
    """Test parsing __all__ from __init__.py."""
    # Test on great-docs's own __init__.py
    docs = GreatDocs()
    exports = docs._parse_package_exports("great_docs")

    assert exports is not None
    assert "GreatDocs" in exports
    assert "main" in exports


def test_create_quartodoc_sections():
    """Test auto-generation of quartodoc sections."""
    docs = GreatDocs()
    sections = docs._create_quartodoc_sections("great_docs")

    assert sections is not None
    assert len(sections) > 0

    # Check that we have at least one section with contents
    has_contents = any(section.get("contents") for section in sections)
    assert has_contents


def test_detect_package_name_from_pyproject():
    """Test package name detection from pyproject.toml."""
    # Test on great-docs's own pyproject.toml
    docs = GreatDocs()
    package_name = docs._detect_package_name()

    assert package_name == "great-docs"


def test_find_package_init():
    """Test finding __init__.py in standard location."""
    docs = GreatDocs()
    init_file = docs._find_package_init("great_docs")

    assert init_file is not None
    assert init_file.exists()
    assert init_file.name == "__init__.py"


def test_find_package_init_with_nested_structure():
    """Test finding __init__.py in nested directories like python/."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a package structure in python/ subdirectory
        python_dir = Path(tmp_dir) / "python"
        python_dir.mkdir()
        package_dir = python_dir / "mypackage"
        package_dir.mkdir()

        # Create __init__.py with __version__ and __all__
        init_file = package_dir / "__init__.py"
        init_file.write_text('__version__ = "1.0.0"\n__all__ = ["MyClass"]')

        docs = GreatDocs(project_path=tmp_dir)
        found_init = docs._find_package_init("mypackage")

        assert found_init is not None
        assert found_init == init_file


def test_cli_import():
    """Test that CLI module can be imported."""
    from great_docs.cli import main

    assert callable(main)


def test_method_section_generation():
    """Test that classes with >5 methods get separate method sections."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a test package with a class that has many methods
        package_dir = Path(tmp_dir) / "testpkg"
        package_dir.mkdir()

        # Create __init__.py with __all__ and a class with many methods
        init_content = '''
"""Test package."""
__version__ = "1.0.0"
__all__ = ["BigClass", "SmallClass", "some_function"]

class BigClass:
    """A class with many methods."""
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass

class SmallClass:
    """A class with few methods."""
    def method1(self): pass
    def method2(self): pass

def some_function():
    """A function."""
    pass
'''
        (package_dir / "__init__.py").write_text(init_content)

        # Add temp dir to sys.path so griffe can find the package
        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            sections = docs._create_quartodoc_sections("testpkg")

            assert sections is not None

            # Check that we have a Classes section
            class_section = next((s for s in sections if s["title"] == "Classes"), None)
            assert class_section is not None

            # BigClass should have members: [] since it has >5 methods
            big_class_entry = next(
                (
                    c
                    for c in class_section["contents"]
                    if isinstance(c, dict) and c.get("name") == "BigClass"
                ),
                None,
            )
            assert big_class_entry is not None
            assert big_class_entry == {"name": "BigClass", "members": []}

            # SmallClass should be a plain string (inline documentation)
            assert "SmallClass" in class_section["contents"]

            # Check that we have a separate method section for BigClass
            method_section = next((s for s in sections if s["title"] == "BigClass Methods"), None)
            assert method_section is not None
            assert len(method_section["contents"]) == 7
            assert "BigClass.method1" in method_section["contents"]
            assert "BigClass.method7" in method_section["contents"]

            # SmallClass should NOT have a separate method section
            small_method_section = next(
                (s for s in sections if s["title"] == "SmallClass Methods"), None
            )
            assert small_method_section is None

            # Check that functions section exists
            func_section = next((s for s in sections if s["title"] == "Functions"), None)
            assert func_section is not None
            assert "some_function" in func_section["contents"]
        finally:
            # Clean up sys.path
            sys.path.remove(tmp_dir)


def test_config_exclude_in_parse():
    """Test that great-docs.yml exclude filters items from __all__."""
    import sys

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
        exports = docs._parse_package_exports("testpkg_cfgexcl")

        # Should have filtered out Node and Edge via config exclude
        assert exports is not None
        assert "Graph" in exports
        assert "some_function" in exports
        assert "Node" not in exports
        assert "Edge" not in exports
        assert len(exports) == 2


def test_setup_github_pages_command():
    """Test the setup-github-pages CLI command."""
    from click.testing import CliRunner
    from great_docs.cli import setup_github_pages

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
        import yaml

        with open(workflow_file) as f:
            workflow = yaml.safe_load(f)

        assert "name" in workflow
        assert workflow["name"] == "CI Docs"
        assert "jobs" in workflow
        assert "build-docs" in workflow["jobs"]
        assert "publish-docs" in workflow["jobs"]
        assert "preview-docs" in workflow["jobs"]


def test_setup_github_pages_custom_options():
    """Test setup-github-pages with custom options."""
    from click.testing import CliRunner
    from great_docs.cli import setup_github_pages

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
    from click.testing import CliRunner
    from great_docs.cli import setup_github_pages

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create the workflow first
        runner.invoke(setup_github_pages, ["--project-path", tmp_dir, "--force"])

        # Try again without force
        result = runner.invoke(setup_github_pages, ["--project-path", tmp_dir], input="n\n")

        assert result.exit_code == 1
        assert "Aborted" in result.output


def test_generate_llms_txt():
    """Test generation of llms.txt file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Create a pyproject.toml with package info
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
description = "A test package"
""")

        # Create great-docs directory and _quarto.yml with quartodoc config
        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text("""
quartodoc:
  package: test_package
  sections:
    - title: Main
      desc: Main functions
      contents:
        - foo
        - bar
    - title: Classes
      contents:
        - MyClass
""")

        # Generate llms.txt
        docs._generate_llms_txt()

        # Check the file was created in great-docs directory
        llms_txt = great_docs_dir / "llms.txt"
        assert llms_txt.exists()

        # Check content structure
        content = llms_txt.read_text()
        assert "# test_package" in content
        assert "> A test package" in content
        assert "## Docs" in content
        assert "### API Reference" in content
        assert "#### Main" in content
        assert "> Main functions" in content
        assert "- [foo](reference/foo.html)" in content
        assert "- [bar](reference/bar.html)" in content
        assert "#### Classes" in content
        assert "- [MyClass](reference/MyClass.html)" in content


def test_generate_llms_txt_with_site_url():
    """Test llms.txt generation with site URL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # Create great-docs directory and _quarto.yml with quartodoc config and site URL
        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text("""
website:
  site-url: https://example.com/docs
quartodoc:
  package: test_package
  sections:
    - title: Main
      contents:
        - foo
""")

        # Generate llms.txt
        docs._generate_llms_txt()

        # Check the file was created with absolute URLs in great-docs directory
        llms_txt = great_docs_dir / "llms.txt"
        content = llms_txt.read_text()
        assert "https://example.com/docs/reference/foo.html" in content


def test_get_github_repo_info():
    """Test GitHub repository info extraction from pyproject.toml."""
    # Test on great-docs's own pyproject.toml
    docs = GreatDocs()
    owner, repo, base_url = docs._get_github_repo_info()

    assert owner == "rich-iannone"
    assert repo == "great-docs"
    assert base_url == "https://github.com/rich-iannone/great-docs"


def test_get_github_repo_info_no_repo():
    """Test GitHub repo info when no repository URL exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a minimal pyproject.toml without repository URL
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner is None
        assert repo is None
        assert base_url is None


def test_get_source_location():
    """Test source location detection for classes and methods."""
    docs = GreatDocs()
    source_loc = docs._get_source_location("great_docs", "GreatDocs")

    assert source_loc is not None
    assert "file" in source_loc
    assert "start_line" in source_loc
    assert "end_line" in source_loc
    assert source_loc["start_line"] > 0
    assert source_loc["end_line"] >= source_loc["start_line"]
    assert "core.py" in source_loc["file"]


def test_get_source_location_method():
    """Test source location detection for methods."""
    docs = GreatDocs()
    source_loc = docs._get_source_location("great_docs", "GreatDocs.install")

    assert source_loc is not None
    assert "file" in source_loc
    assert "start_line" in source_loc
    assert source_loc["start_line"] > 0


def test_get_source_location_not_found():
    """Test source location returns None for non-existent items."""
    docs = GreatDocs()
    source_loc = docs._get_source_location("great_docs", "NonExistentClass")

    assert source_loc is None


def test_build_github_source_url():
    """Test GitHub source URL construction."""
    docs = GreatDocs()

    source_loc = {
        "file": "/path/to/great_docs/core.py",
        "start_line": 42,
        "end_line": 58,
    }

    url = docs._build_github_source_url(source_loc, branch="main")

    assert url is not None
    assert "https://github.com/rich-iannone/great-docs" in url
    assert "blob/main" in url
    assert "#L42-L58" in url


def test_build_github_source_url_single_line():
    """Test GitHub source URL with single line."""
    docs = GreatDocs()

    source_loc = {
        "file": "/path/to/great_docs/core.py",
        "start_line": 42,
        "end_line": 42,
    }

    url = docs._build_github_source_url(source_loc, branch="main")

    assert url is not None
    assert "#L42" in url
    # Should not have the range format
    assert "#L42-L42" not in url


def test_source_link_config_defaults():
    """Test that source link configuration has proper defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pyproject.toml without source config
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        # Defaults should be: enabled=True, branch=None, path=None, placement="usage"
        assert metadata.get("source_link_enabled", True) is True
        assert metadata.get("source_link_branch") is None
        assert metadata.get("source_link_path") is None
        assert metadata.get("source_link_placement", "usage") == "usage"


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
  placement: title
""")

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert metadata.get("source_link_enabled") is False
        assert metadata.get("source_link_branch") == "develop"
        assert metadata.get("source_link_path") == "src/mypackage"
        assert metadata.get("source_link_placement") == "title"


# ============================================================================
# Link Checker Tests
# ============================================================================


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
        results = docs.check_links(
            include_source=False,
            include_docs=True,
            timeout=5.0,
            verbose=False,
        )

        assert results["total"] >= 2
        assert "by_file" in results
        assert len(results["by_file"]) > 0


def test_check_links_ignore_patterns():
    """Test that ignore patterns work correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "user_guide"
        docs_dir.mkdir()

        test_md = docs_dir / "test.md"
        test_md.write_text("""
# Test

https://localhost:8000/api
https://127.0.0.1:3000/test
https://example.com/page
        """)

        quarto_yml = docs_dir / "_quarto.yml"
        quarto_yml.write_text("project:\n  type: website\n")

        docs = GreatDocs(project_path=tmp_dir)
        results = docs.check_links(
            include_source=False,
            include_docs=True,
            ignore_patterns=["localhost", "127.0.0.1", "example.com"],
            verbose=False,
        )

        # All URLs should be skipped
        assert len(results["skipped"]) == 3
        assert len(results["ok"]) == 0
        assert len(results["broken"]) == 0


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


# ============================================================================
# Config Module Tests
# ============================================================================


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
        assert config.source_placement == "usage"
        assert config.sidebar_filter_enabled is True
        assert config.sidebar_filter_min_items == 20
        assert config.cli_enabled is False
        assert config.cli_module is None
        assert config.cli_name is None
        assert config.dark_mode_toggle is True
        assert config.reference == []
        assert config.authors == []


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

        assert config.get("source.enabled") is False
        assert config.get("source.branch") == "develop"
        assert config.get("source.nonexistent", "default") == "default"


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
    assert "sidebar_filter" in content
    assert "cli:" in content
    assert "authors:" in content
    assert "parser:" in content


# --- Docstring Style Detection Tests ---


def test_detect_docstring_style_numpy():
    """Test detection of NumPy-style docstrings."""
    import sys

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
            style = docs._detect_docstring_style("numpypkg")
            assert style == "numpy"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_google():
    """Test detection of Google-style docstrings."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        package_dir = Path(tmp_dir) / "googlepkg"
        package_dir.mkdir()

        # Create a package with Google-style docstrings
        init_content = '''
"""Test package with Google-style docstrings."""
__version__ = "1.0.0"
__all__ = ["my_function", "MyClass"]

def my_function(x, y):
    """Add two numbers together.

    Args:
        x: The first number.
        y: The second number.

    Returns:
        The sum of x and y.

    Examples:
        >>> my_function(1, 2)
        3
    """
    return x + y

class MyClass:
    """A sample class.

    Attributes:
        value: The stored value.
    """

    def __init__(self, value):
        """Initialize the class.

        Args:
            value: The initial value.
        """
        self.value = value
'''
        (package_dir / "__init__.py").write_text(init_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = docs._detect_docstring_style("googlepkg")
            assert style == "google"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_sphinx():
    """Test detection of Sphinx-style docstrings."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        package_dir = Path(tmp_dir) / "sphinxpkg"
        package_dir.mkdir()

        # Create a package with Sphinx-style docstrings
        init_content = '''
"""Test package with Sphinx-style docstrings."""
__version__ = "1.0.0"
__all__ = ["my_function"]

def my_function(x, y):
    """Add two numbers together.

    :param x: The first number.
    :type x: int
    :param y: The second number.
    :type y: int
    :returns: The sum of x and y.
    :rtype: int
    """
    return x + y
'''
        (package_dir / "__init__.py").write_text(init_content)

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            style = docs._detect_docstring_style("sphinxpkg")
            assert style == "sphinx"
        finally:
            sys.path.remove(tmp_dir)


def test_detect_docstring_style_defaults_to_numpy():
    """Test that detection defaults to numpy when no docstrings are found."""
    import sys

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
            style = docs._detect_docstring_style("nodocspkg")
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

        sections = docs._build_sections_from_reference_config(reference_config)

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

        sections = docs._build_sections_from_reference_config(reference_config)

        assert sections is not None
        assert len(sections) == 1
        assert {"name": "MyClass", "members": []} in sections[0]["contents"]
        assert "SimpleClass" in sections[0]["contents"]


def test_build_sections_from_reference_config_empty():
    """Test that empty reference config returns None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        assert docs._build_sections_from_reference_config([]) is None
        assert docs._build_sections_from_reference_config(None) is None


def test_explicit_reference_config_applied_when_discovery_fails():
    """Test that explicit reference config is used when auto-discovery fails."""
    import sys

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
            sections = docs._build_sections_from_reference_config(docs._config.reference)
            assert sections is not None
            assert len(sections) == 1
            assert "my_func" in sections[0]["contents"]
        finally:
            sys.path.remove(tmp_dir)


# --- Quarto Environment Tests ---


def test_get_quarto_env_returns_current_python():
    """Test that _get_quarto_env returns QUARTO_PYTHON with current interpreter."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = docs._get_quarto_env()

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


def test_get_quarto_env_detects_venv():
    """Test that _get_quarto_env detects a virtual environment."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a fake .venv directory structure
        venv_dir = Path(tmp_dir) / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        fake_python = venv_dir / "python"
        fake_python.write_text("#!/bin/bash\n# fake python")

        docs = GreatDocs(project_path=tmp_dir)
        env = docs._get_quarto_env()

        assert "QUARTO_PYTHON" in env
        assert env["QUARTO_PYTHON"] == str(fake_python)


def test_get_quarto_env_preserves_existing_env():
    """Test that _get_quarto_env preserves existing environment variables."""
    import os

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        env = docs._get_quarto_env()

        # Should contain existing env vars like PATH
        assert "PATH" in env
        assert env["PATH"] == os.environ.get("PATH")


# --- Dynamic Mode Tests ---


def test_detect_dynamic_mode_returns_true_for_simple_package():
    """Test that _detect_dynamic_mode returns True for packages without cyclic aliases."""
    import sys

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
            result = docs._detect_dynamic_mode("simple_pkg")
            # Should return True for a simple package
            assert result is True
        finally:
            sys.path.remove(tmp_dir)


def test_detect_dynamic_mode_returns_true_with_no_package():
    """Test that _detect_dynamic_mode returns True when package name is empty."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_dynamic_mode("")
        assert result is True


def test_config_dynamic_property():
    """Test Config.dynamic property returns correct value."""
    from great_docs.config import Config

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
    from great_docs.config import Config

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
    import yaml
    from datetime import datetime

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
        citation_cff.write_text(yaml.dump(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        docs._create_index_from_readme()

        # Check that citation.qmd was created
        citation_qmd = docs_dir / "citation.qmd"
        assert citation_qmd.exists()

        content = citation_qmd.read_text()
        # Check that 2023 appears in the citation (from date-released)
        assert "2023" in content
        assert "year = {2023}" in content


def test_citation_year_defaults_to_current():
    """Test that citation year defaults to current year when date-released is missing."""
    import yaml
    from datetime import datetime

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
        citation_cff.write_text(yaml.dump(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        docs._create_index_from_readme()

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
    import yaml
    from datetime import datetime

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
        citation_cff.write_text(yaml.dump(citation_data))

        # Create README.md
        readme = project_path / "README.md"
        readme.write_text("# Test Package\n\nA test package.")

        # Create great-docs directory
        docs_dir = project_path / "great-docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        docs = GreatDocs(project_path=tmp_dir)
        docs._create_index_from_readme()

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


# --- Author Extraction Tests ---


def test_extract_authors_from_pyproject_with_authors():
    """Test extracting authors from pyproject.toml with authors field."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create pyproject.toml with authors
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-package"
version = "0.1.0"
authors = [
    {name = "Alice Smith", email = "alice@example.com"},
    {name = "Bob Jones", email = "bob@example.com"}
]
""")

        docs = GreatDocs(project_path=tmp_dir)
        authors = docs._extract_authors_from_pyproject()

        assert len(authors) == 2
        assert authors[0]["name"] == "Alice Smith"
        assert authors[0]["role"] == "Author"
        assert authors[0]["email"] == "alice@example.com"
        assert authors[1]["name"] == "Bob Jones"


def test_extract_authors_from_pyproject_with_maintainers():
    """Test extracting authors from pyproject.toml with maintainers field."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create pyproject.toml with maintainers
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-package"
version = "0.1.0"
maintainers = [
    {name = "Carol White", email = "carol@example.com"}
]
""")

        docs = GreatDocs(project_path=tmp_dir)
        authors = docs._extract_authors_from_pyproject()

        assert len(authors) == 1
        assert authors[0]["name"] == "Carol White"
        assert authors[0]["role"] == "Maintainer"
        assert authors[0]["email"] == "carol@example.com"


def test_extract_authors_from_pyproject_deduplicates():
    """Test that authors appearing in both authors and maintainers are deduplicated."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create pyproject.toml with same person as author and maintainer
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-package"
version = "0.1.0"
authors = [
    {name = "Rich Iannone", email = "rich@example.com"}
]
maintainers = [
    {name = "Rich Iannone", email = "rich@example.com"}
]
""")

        docs = GreatDocs(project_path=tmp_dir)
        authors = docs._extract_authors_from_pyproject()

        # Should only have one entry, with Maintainer role (maintainers processed first)
        assert len(authors) == 1
        assert authors[0]["name"] == "Rich Iannone"
        assert authors[0]["role"] == "Maintainer"


def test_extract_authors_from_pyproject_no_authors():
    """Test extracting authors when pyproject.toml has no authors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create pyproject.toml without authors
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "test-package"
version = "0.1.0"
""")

        docs = GreatDocs(project_path=tmp_dir)
        authors = docs._extract_authors_from_pyproject()

        assert authors == []


def test_extract_authors_from_pyproject_no_file():
    """Test extracting authors when pyproject.toml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        authors = docs._extract_authors_from_pyproject()

        assert authors == []


def test_format_authors_yaml_basic():
    """Test formatting authors as YAML."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        authors = [{"name": "Test Author", "role": "Maintainer", "email": "test@example.com"}]
        yaml_output = docs._format_authors_yaml(authors)

        assert "# Author Information" in yaml_output
        assert "authors:" in yaml_output
        assert "- name: Test Author" in yaml_output
        assert "role: Maintainer" in yaml_output
        assert "email: test@example.com" in yaml_output
        assert "# github:" in yaml_output
        assert "# orcid:" in yaml_output


def test_format_authors_yaml_empty():
    """Test formatting empty authors list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)
        yaml_output = docs._format_authors_yaml([])

        assert yaml_output == ""


def test_format_authors_yaml_no_email():
    """Test formatting authors without email."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        authors = [{"name": "No Email Author", "role": "Author"}]
        yaml_output = docs._format_authors_yaml(authors)

        assert "- name: No Email Author" in yaml_output
        assert "role: Author" in yaml_output
        assert "# email:" in yaml_output  # Should be commented out placeholder


# ============================================================================
# User Guide URL Stripping Tests
# ============================================================================


def test_strip_numeric_prefix_single_digit():
    """Test stripping single-digit numeric prefix like 1-, 2-, etc."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("1-getting-started.qmd") == "getting-started.qmd"
        assert docs._strip_numeric_prefix("2-configuration.qmd") == "configuration.qmd"
        assert docs._strip_numeric_prefix("9-advanced.qmd") == "advanced.qmd"


def test_strip_numeric_prefix_two_digit():
    """Test stripping two-digit numeric prefix like 00-, 01-, etc."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("00-introduction.qmd") == "introduction.qmd"
        assert docs._strip_numeric_prefix("01-installation.qmd") == "installation.qmd"
        assert docs._strip_numeric_prefix("09-conclusion.qmd") == "conclusion.qmd"
        assert docs._strip_numeric_prefix("10-appendix.qmd") == "appendix.qmd"
        assert docs._strip_numeric_prefix("99-final.qmd") == "final.qmd"


def test_strip_numeric_prefix_three_digit():
    """Test stripping three-digit numeric prefix like 001-, 010-, etc."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("001-overview.qmd") == "overview.qmd"
        assert docs._strip_numeric_prefix("010-details.qmd") == "details.qmd"
        assert docs._strip_numeric_prefix("0100-reference.qmd") == "reference.qmd"


def test_strip_numeric_prefix_underscore():
    """Test stripping numeric prefix with underscore separator."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("01_introduction.qmd") == "introduction.qmd"
        assert docs._strip_numeric_prefix("1_getting_started.qmd") == "getting_started.qmd"


def test_strip_numeric_prefix_no_prefix():
    """Test that filenames without numeric prefix are unchanged."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("introduction.qmd") == "introduction.qmd"
        assert docs._strip_numeric_prefix("index.qmd") == "index.qmd"
        assert docs._strip_numeric_prefix("getting-started.qmd") == "getting-started.qmd"


def test_strip_numeric_prefix_preserves_internal_numbers():
    """Test that numbers within filename are preserved."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        assert docs._strip_numeric_prefix("01-python3-setup.qmd") == "python3-setup.qmd"
        assert docs._strip_numeric_prefix("02-chapter-10.qmd") == "chapter-10.qmd"


def test_user_guide_files_renamed_on_copy():
    """Test that user guide files are renamed when copied to docs directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with numbered files
        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "00-introduction.qmd").write_text("""---
title: Introduction
guide-section: Getting Started
---
# Introduction
""")
        (user_guide / "01-installation.qmd").write_text("""---
title: Installation
guide-section: Getting Started
---
# Installation
""")

        docs = GreatDocs(project_path=tmp_dir)

        # Process the user guide
        user_guide_info = docs._discover_user_guide()
        assert user_guide_info is not None

        copied_files = docs._copy_user_guide_to_docs(user_guide_info)

        # Check that files were copied with clean names
        assert "user-guide/introduction.qmd" in copied_files
        assert "user-guide/installation.qmd" in copied_files

        # Check files exist with clean names
        docs_user_guide = docs.project_path / "user-guide"
        assert (docs_user_guide / "introduction.qmd").exists()
        assert (docs_user_guide / "installation.qmd").exists()

        # Check numbered versions do NOT exist
        assert not (docs_user_guide / "00-introduction.qmd").exists()
        assert not (docs_user_guide / "01-installation.qmd").exists()


def test_user_guide_sidebar_uses_clean_urls():
    """Test that the generated sidebar uses clean URLs without numeric prefixes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with numbered files
        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "00-introduction.qmd").write_text("""---
title: Introduction
guide-section: Getting Started
---
# Introduction
""")
        (user_guide / "01-installation.qmd").write_text("""---
title: Installation
guide-section: Getting Started
---
# Installation
""")

        docs = GreatDocs(project_path=tmp_dir)

        # Discover and generate sidebar
        user_guide_info = docs._discover_user_guide()
        assert user_guide_info is not None

        sidebar_config = docs._generate_user_guide_sidebar(user_guide_info)

        # Check sidebar structure
        assert sidebar_config["id"] == "user-guide"
        assert sidebar_config["title"] == "User Guide"

        # Find the contents and verify clean URLs
        contents = sidebar_config["contents"]
        assert len(contents) > 0

        # Flatten all hrefs from sections
        all_hrefs = []
        for item in contents:
            if isinstance(item, dict) and "contents" in item:
                for sub_item in item["contents"]:
                    if isinstance(sub_item, str):
                        all_hrefs.append(sub_item)
                    elif isinstance(sub_item, dict):
                        all_hrefs.append(sub_item.get("href", ""))
            elif isinstance(item, str):
                all_hrefs.append(item)

        # Verify clean URLs (no numeric prefixes)
        assert "user-guide/introduction.qmd" in all_hrefs
        assert "user-guide/installation.qmd" in all_hrefs
        assert "user-guide/00-introduction.qmd" not in all_hrefs
        assert "user-guide/01-installation.qmd" not in all_hrefs


def test_copy_assets_basic():
    """Test that assets directory is copied to docs directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create assets directory with files
        assets = project_path / "assets"
        assets.mkdir()

        (assets / "image.png").write_text("fake png content")
        (assets / "style.css").write_text("body { color: red; }")
        (assets / "data.json").write_text('{"key": "value"}')

        docs = GreatDocs(project_path=tmp_dir)

        # Copy assets
        result = docs._copy_assets()

        # Check that method returns True
        assert result is True

        # Check that files were copied
        docs_assets = docs.project_path / "assets"
        assert docs_assets.exists()
        assert (docs_assets / "image.png").exists()
        assert (docs_assets / "style.css").exists()
        assert (docs_assets / "data.json").exists()

        # Verify content
        assert (docs_assets / "image.png").read_text() == "fake png content"
        assert (docs_assets / "style.css").read_text() == "body { color: red; }"
        assert (docs_assets / "data.json").read_text() == '{"key": "value"}'


def test_copy_assets_nested_directories():
    """Test that nested asset directories are copied correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create assets directory with nested structure
        assets = project_path / "assets"
        (assets / "images" / "icons").mkdir(parents=True)
        (assets / "css").mkdir()
        (assets / "js").mkdir()

        (assets / "images" / "logo.png").write_text("logo")
        (assets / "images" / "icons" / "star.svg").write_text("<svg>star</svg>")
        (assets / "css" / "theme.css").write_text("/* theme */")
        (assets / "js" / "app.js").write_text("console.log('app');")

        docs = GreatDocs(project_path=tmp_dir)

        # Copy assets
        result = docs._copy_assets()

        assert result is True

        # Check nested structure was preserved
        docs_assets = docs.project_path / "assets"
        assert (docs_assets / "images" / "logo.png").exists()
        assert (docs_assets / "images" / "icons" / "star.svg").exists()
        assert (docs_assets / "css" / "theme.css").exists()
        assert (docs_assets / "js" / "app.js").exists()

        # Verify content
        assert (docs_assets / "images" / "icons" / "star.svg").read_text() == "<svg>star</svg>"


def test_copy_assets_no_directory():
    """Test that _copy_assets returns False when no assets directory exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        # Try to copy assets when none exist
        result = docs._copy_assets()

        # Should return False
        assert result is False

        # Assets directory should not exist in docs
        docs_assets = docs.project_path / "assets"
        assert not docs_assets.exists()


def test_copy_assets_replaces_existing():
    """Test that copying assets replaces existing assets directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create assets directory
        assets = project_path / "assets"
        assets.mkdir()
        (assets / "new_file.txt").write_text("new content")

        docs = GreatDocs(project_path=tmp_dir)

        # Create existing assets in docs directory
        docs_assets = docs.project_path / "assets"
        docs_assets.mkdir(parents=True)
        (docs_assets / "old_file.txt").write_text("old content")

        # Copy assets
        result = docs._copy_assets()

        assert result is True

        # Check that old file was removed and new file exists
        assert not (docs_assets / "old_file.txt").exists()
        assert (docs_assets / "new_file.txt").exists()
        assert (docs_assets / "new_file.txt").read_text() == "new content"


def test_assets_added_to_quarto_config():
    """Test that assets directory is added to Quarto config resources."""
    import yaml

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create assets directory
        assets = project_path / "assets"
        assets.mkdir()
        (assets / "test.txt").write_text("test")

        docs = GreatDocs(project_path=tmp_dir)

        # Copy assets first
        docs._copy_assets()

        # Update Quarto config
        docs._update_quarto_config()

        # Read the generated _quarto.yml
        quarto_yml = docs.project_path / "_quarto.yml"
        assert quarto_yml.exists()

        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        # Check that assets/** is in resources
        assert "project" in config
        assert "resources" in config["project"]
        assert "assets/**" in config["project"]["resources"]


def test_assets_not_added_to_quarto_config_when_missing():
    """Test that assets/** is not added to Quarto config when assets don't exist."""
    import yaml

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        # Create great-docs directory (required for _quarto.yml)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        # Update Quarto config without assets
        docs._update_quarto_config()

        # Read the generated _quarto.yml
        quarto_yml = docs.project_path / "_quarto.yml"
        assert quarto_yml.exists()

        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        # Check that assets/** is NOT in resources
        assert "project" in config
        assert "resources" in config["project"]
        assert "assets/**" not in config["project"]["resources"]


def test_assets_added_to_config_after_copy():
    """Test that _update_quarto_config() adds assets/** after copying assets."""
    import yaml

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create assets directory
        assets = project_path / "assets"
        assets.mkdir()
        (assets / "image.png").write_text("fake image")

        docs = GreatDocs(project_path=tmp_dir)

        # Create great-docs directory and initial config (simulating _prepare_build_directory)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        # Read initial config - should NOT have assets/**
        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            initial_config = yaml.safe_load(f)

        assert "assets/**" not in initial_config["project"]["resources"]

        # Now copy assets and update config again (simulating build flow)
        assets_copied = docs._copy_assets()
        assert assets_copied is True

        docs._update_quarto_config()

        # Read updated config - should NOW have assets/**
        with open(quarto_yml, "r") as f:
            updated_config = yaml.safe_load(f)

        assert "project" in updated_config
        assert "resources" in updated_config["project"]
        assert "assets/**" in updated_config["project"]["resources"]


def test_assets_config_update_only_when_copied():
    """Test that config is updated conditionally based on whether assets were copied."""
    import yaml

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)

        # Create great-docs directory and initial config
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        # Try to copy assets when none exist - should return False
        assets_copied = docs._copy_assets()
        assert assets_copied is False

        # Config should still not have assets/** since copy returned False
        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        assert "assets/**" not in config["project"]["resources"]


# =============================================================================
# User Guide Config Path Tests
# =============================================================================


def test_user_guide_config_option_overrides_default_dir():
    """Test that user_guide config option takes precedence over user_guide/ directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create conventional user_guide/ directory with a file
        conventional_dir = project_path / "user_guide"
        conventional_dir.mkdir()
        (conventional_dir / "00-from-default.qmd").write_text(
            "---\ntitle: From Default\n---\n# Default\n"
        )

        # Create custom directory with a different file
        custom_dir = project_path / "docs" / "guides"
        custom_dir.mkdir(parents=True)
        (custom_dir / "00-from-custom.qmd").write_text("---\ntitle: From Custom\n---\n# Custom\n")

        # Configure great-docs.yml to use the custom path
        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: docs/guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()

        assert user_guide_info is not None
        assert len(user_guide_info["files"]) == 1
        assert user_guide_info["files"][0]["title"] == "From Custom"
        assert user_guide_info["source_dir"] == custom_dir


def test_user_guide_config_option_custom_directory():
    """Test that user_guide config option works with a subdirectory path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create a nested custom directory
        custom_dir = project_path / "content" / "user-docs"
        custom_dir.mkdir(parents=True)
        (custom_dir / "intro.qmd").write_text("---\ntitle: Intro\n---\n# Intro\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: content/user-docs\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()

        assert user_guide_info is not None
        assert len(user_guide_info["files"]) == 1
        assert user_guide_info["source_dir"] == custom_dir


def test_user_guide_config_option_nonexistent_dir(capsys):
    """Test warning when user_guide config points to a nonexistent directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: nonexistent/dir\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None
        captured = capsys.readouterr()
        assert "does not exist" in captured.out


def test_user_guide_warns_on_empty_directory(capsys):
    """Test warning when user guide directory is empty."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create empty user_guide directory
        empty_dir = project_path / "user_guide"
        empty_dir.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None
        captured = capsys.readouterr()
        assert "is empty" in captured.out


def test_user_guide_warns_on_no_qmd_files(capsys):
    """Test warning when user guide directory has no .qmd files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with only non-.qmd files
        ug_dir = project_path / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "notes.txt").write_text("just a text file")
        (ug_dir / "readme.md").write_text("# readme")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None
        captured = capsys.readouterr()
        assert "contains no .qmd files" in captured.out


def test_user_guide_config_warns_when_both_exist(capsys):
    """Test warning when both config option and conventional directory exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create conventional user_guide/ directory
        conventional_dir = project_path / "user_guide"
        conventional_dir.mkdir()
        (conventional_dir / "default.qmd").write_text("---\ntitle: Default\n---\n# Default\n")

        # Create custom directory
        custom_dir = project_path / "my_guides"
        custom_dir.mkdir()
        (custom_dir / "custom.qmd").write_text("---\ntitle: Custom\n---\n# Custom\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: my_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()

        assert user_guide_info is not None
        # Config option should win
        assert user_guide_info["source_dir"] == custom_dir

        captured = capsys.readouterr()
        assert "using configured path" in captured.out


def test_user_guide_fallback_without_config():
    """Test that default user_guide/ directory is used when no config option is set."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create conventional user_guide/ directory
        ug_dir = project_path / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "intro.qmd").write_text("---\ntitle: Intro\n---\n# Intro\n")

        # No great-docs.yml or one without user_guide key
        config_path = project_path / "great-docs.yml"
        config_path.write_text("display_name: Test\n")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()

        assert user_guide_info is not None
        assert user_guide_info["source_dir"] == ug_dir


def test_user_guide_config_empty_dir_warns(capsys):
    """Test warning when user_guide config points to an empty directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        empty_dir = project_path / "empty_guides"
        empty_dir.mkdir()

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: empty_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None
        captured = capsys.readouterr()
        assert "is empty" in captured.out


def test_copy_user_guide_files_uses_config():
    """Test that _copy_user_guide_files respects the user_guide config option."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create custom directory with files
        custom_dir = project_path / "my_docs"
        custom_dir.mkdir()
        (custom_dir / "guide.qmd").write_text("---\ntitle: Guide\n---\n# Guide\n")
        (custom_dir / "guide.md").write_text("# Guide MD\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: my_docs\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        docs._copy_user_guide_files()

        dest = docs.project_path / "user-guide"
        assert dest.exists()
        assert (dest / "guide.qmd").exists()
        assert (dest / "guide.md").exists()


# =========================================================================
# Explicit User Guide Ordering Tests
# =========================================================================


def test_user_guide_explicit_config_discovery():
    """Test that explicit user_guide config (list) discovers files correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with files (no numeric prefixes)
        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "index.qmd").write_text("---\ntitle: Welcome\n---\n# Welcome\n")
        (user_guide / "quickstart.qmd").write_text("---\ntitle: Quick Start\n---\n# Quick Start\n")
        (user_guide / "installation.qmd").write_text(
            "---\ntitle: Installation\n---\n# Installation\n"
        )
        (user_guide / "advanced.qmd").write_text("---\ntitle: Advanced Topics\n---\n# Advanced\n")

        # Write config with explicit ordering
        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Get Started"
    contents:
      - text: "Welcome"
        href: index.qmd
      - quickstart.qmd
      - installation.qmd
  - section: "Advanced"
    contents:
      - advanced.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert result["explicit"] is True
        assert len(result["files"]) == 4
        assert result["has_index"] is True
        assert "Get Started" in result["sections"]
        assert "Advanced" in result["sections"]
        assert len(result["sections"]["Get Started"]) == 3
        assert len(result["sections"]["Advanced"]) == 1


def test_user_guide_explicit_config_preserves_order():
    """Test that explicit config preserves file ordering as specified."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        # Create files that would sort differently alphabetically
        (user_guide / "zebra.qmd").write_text("---\ntitle: Zebra\n---\n# Zebra\n")
        (user_guide / "apple.qmd").write_text("---\ntitle: Apple\n---\n# Apple\n")
        (user_guide / "mango.qmd").write_text("---\ntitle: Mango\n---\n# Mango\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Fruits"
    contents:
      - zebra.qmd
      - apple.qmd
      - mango.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        # Files should be in config order, not alphabetical
        assert result["files"][0]["path"].name == "zebra.qmd"
        assert result["files"][1]["path"].name == "apple.qmd"
        assert result["files"][2]["path"].name == "mango.qmd"


def test_user_guide_explicit_config_sidebar_generation():
    """Test sidebar generation from explicit config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "index.qmd").write_text("---\ntitle: Welcome\n---\n# Welcome\n")
        (user_guide / "quickstart.qmd").write_text("---\ntitle: Quick Start\n---\n# Quick Start\n")
        (user_guide / "installation.qmd").write_text(
            "---\ntitle: Installation\n---\n# Installation\n"
        )
        (user_guide / "advanced.qmd").write_text("---\ntitle: Advanced\n---\n# Advanced\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Get Started"
    contents:
      - text: "Welcome to Package"
        href: index.qmd
      - quickstart.qmd
      - installation.qmd
  - section: "Advanced"
    contents:
      - advanced.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()
        sidebar = docs._generate_user_guide_sidebar(user_guide_info)

        assert sidebar["id"] == "user-guide"
        assert sidebar["title"] == "User Guide"
        assert len(sidebar["contents"]) == 2

        # Check first section
        section1 = sidebar["contents"][0]
        assert section1["section"] == "Get Started"
        assert len(section1["contents"]) == 3
        # First item has custom text
        assert section1["contents"][0] == {
            "text": "Welcome to Package",
            "href": "user-guide/index.qmd",
        }
        # Other items are plain hrefs
        assert section1["contents"][1] == "user-guide/quickstart.qmd"
        assert section1["contents"][2] == "user-guide/installation.qmd"

        # Check second section
        section2 = sidebar["contents"][1]
        assert section2["section"] == "Advanced"
        assert section2["contents"] == ["user-guide/advanced.qmd"]


def test_user_guide_explicit_config_no_prefix_stripping():
    """Test that explicit config does NOT strip numeric prefixes from filenames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        # Files WITH numeric prefixes (user chose to keep them)
        (user_guide / "01-intro.qmd").write_text("---\ntitle: Intro\n---\n# Intro\n")
        (user_guide / "02-setup.qmd").write_text("---\ntitle: Setup\n---\n# Setup\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Basics"
    contents:
      - 01-intro.qmd
      - 02-setup.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        user_guide_info = docs._discover_user_guide()

        # Copy files - should preserve names
        docs.project_path.mkdir(parents=True, exist_ok=True)
        copied_files = docs._copy_user_guide_to_docs(user_guide_info)

        assert "user-guide/01-intro.qmd" in copied_files
        assert "user-guide/02-setup.qmd" in copied_files

        # Verify files exist with original names
        docs_ug = docs.project_path / "user-guide"
        assert (docs_ug / "01-intro.qmd").exists()
        assert (docs_ug / "02-setup.qmd").exists()

        # Sidebar should also use original names
        sidebar = docs._generate_user_guide_sidebar(user_guide_info)
        section_contents = sidebar["contents"][0]["contents"]
        assert section_contents[0] == "user-guide/01-intro.qmd"
        assert section_contents[1] == "user-guide/02-setup.qmd"


def test_user_guide_explicit_config_missing_file(capsys):
    """Test warning when explicit config references a non-existent file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "exists.qmd").write_text("---\ntitle: Exists\n---\n# Exists\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Docs"
    contents:
      - exists.qmd
      - missing.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        # Only the existing file should be included
        assert len(result["files"]) == 1
        assert result["files"][0]["path"].name == "exists.qmd"

        captured = capsys.readouterr()
        assert "missing.qmd" in captured.out
        assert "does not exist" in captured.out


def test_user_guide_explicit_config_custom_text():
    """Test that custom text entries are preserved in file info."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "index.qmd").write_text("---\ntitle: Home\n---\n# Home\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Start"
    contents:
      - text: "Welcome to the Package"
        href: index.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert result["files"][0].get("custom_text") == "Welcome to the Package"


def test_user_guide_explicit_overrides_frontmatter_sections():
    """Test that explicit config sections override frontmatter guide-section keys."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        # File has guide-section in frontmatter, but config will override
        (user_guide / "intro.qmd").write_text(
            "---\ntitle: Intro\nguide-section: Old Section\n---\n# Intro\n"
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "New Section"
    contents:
      - intro.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        # Section should come from config, not frontmatter
        assert result["files"][0]["section"] == "New Section"
        assert "New Section" in result["sections"]
        assert "Old Section" not in result["sections"]


def test_user_guide_explicit_with_conventional_dir():
    """Test that explicit config works with auto-discovered user_guide/ directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Use conventional user_guide/ directory
        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        (user_guide / "page.qmd").write_text("---\ntitle: Page\n---\n# Page\n")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("""user_guide:
  - section: "Main"
    contents:
      - page.qmd
""")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert result["explicit"] is True
        assert result["source_dir"] == user_guide


def test_user_guide_string_config_still_works():
    """Test that string user_guide config (directory path) still works as before."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        custom_dir = project_path / "my_guides"
        custom_dir.mkdir()
        (custom_dir / "intro.qmd").write_text(
            "---\ntitle: Intro\nguide-section: Start\n---\n# Intro\n"
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("user_guide: my_guides\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert result.get("explicit", False) is False
        assert result["source_dir"] == custom_dir
        assert len(result["files"]) == 1


# =========================================================================
# Landing Page Generation Tests
# =========================================================================


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
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._create_index_from_readme()

        index_qmd = docs.project_path / "index.qmd"
        assert index_qmd.exists()

        content = index_qmd.read_text()
        assert "my-package" in content
        assert "A great package" in content
        assert "pip install my-package" in content
        assert "API Reference" in content


def test_landing_page_includes_description_from_pyproject():
    """Test that the landing page uses the description from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "fancy-lib"\nversion = "2.0"\n'
            'description = "Fancy library for doing fancy things"\n'
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        pkg_dir = project_path / "fancy_lib"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        content = docs._generate_landing_page_content(metadata)
        assert "## fancy-lib" in content
        assert "Fancy library for doing fancy things" in content
        assert "pip install fancy-lib" in content


def test_landing_page_metadata_fallback_to_setup_cfg():
    """Test that metadata falls back to setup.cfg when pyproject.toml lacks [project]."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # pyproject.toml without [project] section
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text("[build-system]\nrequires = ['setuptools']\n")

        setup_cfg = project_path / "setup.cfg"
        setup_cfg.write_text(
            "[metadata]\n"
            "name = my-tool\n"
            "description = A CLI tool for developers\n"
            "author = Jane Doe\n"
            "author_email = jane@example.com\n"
            "license = MIT\n"
            "url = https://github.com/jane/my-tool\n"
            "project_urls =\n"
            "    Documentation = https://my-tool.readthedocs.io\n"
            "    Source = https://github.com/jane/my-tool\n"
            "\n[options]\n"
            "python_requires = >=3.8\n"
        )

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        pkg_dir = project_path / "my_tool"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert metadata["description"] == "A CLI tool for developers"
        assert metadata["license"] == "MIT"
        assert metadata["requires_python"] == ">=3.8"
        assert metadata["authors"] == [{"name": "Jane Doe", "email": "jane@example.com"}]
        assert "Repository" in metadata["urls"]
        assert "Source" in metadata["urls"]


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
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._create_index_from_readme()

        index_qmd = docs.project_path / "index.qmd"
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
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._create_index_from_readme()

        index_qmd = docs.project_path / "index.qmd"
        content = index_qmd.read_text()

        # Should have sidebar with metadata
        assert ".column-margin" in content
        assert "View on PyPI" in content
        assert "Full license" in content
        assert ">=3.9" in content


def test_landing_page_with_no_metadata():
    """Test landing page generation when minimal metadata is available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Only a package directory, no pyproject.toml or setup.cfg
        pkg_dir = project_path / "minimal_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        content = docs._generate_landing_page_content(metadata)
        assert "## minimal_pkg" in content
        assert "pip install minimal_pkg" in content


# =========================================================================
# README.rst and Index Source Discovery Tests
# =========================================================================


def test_find_index_source_priority_order():
    """Test that _find_index_source_file returns files in correct priority order."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "1.0"\n')
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        # Only README.rst → should find it
        (project_path / "README.rst").write_text("Title\n=====\n")
        docs = GreatDocs(project_path=tmp_dir)
        source, warnings = docs._find_index_source_file()
        assert source is not None
        assert source.name == "README.rst"
        assert len(warnings) == 0

        # Add README.md → should prefer it over README.rst
        (project_path / "README.md").write_text("# Title\n")
        source, warnings = docs._find_index_source_file()
        assert source.name == "README.md"
        assert len(warnings) == 1
        assert "README.rst" in warnings[0]

        # Add index.md → should prefer it
        (project_path / "index.md").write_text("# Index\n")
        source, warnings = docs._find_index_source_file()
        assert source.name == "index.md"

        # Add index.qmd → should prefer it
        (project_path / "index.qmd").write_text("---\ntitle: Index\n---\n")
        source, warnings = docs._find_index_source_file()
        assert source.name == "index.qmd"


def test_find_index_source_no_files():
    """Test that _find_index_source_file returns None when no source files exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        source, warnings = docs._find_index_source_file()
        assert source is None
        assert len(warnings) == 0


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
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._create_index_from_readme()

        index_qmd = docs.project_path / "index.qmd"
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
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._create_index_from_readme()

        index_qmd = docs.project_path / "index.qmd"
        content = index_qmd.read_text()
        assert "Markdown README" in content
        assert "RST readme" not in content


def test_convert_rst_to_markdown():
    """Test RST to Markdown conversion via pandoc."""
    import shutil

    # Skip if neither quarto nor pandoc is available
    if not shutil.which("quarto") and not shutil.which("pandoc"):
        import pytest

        pytest.skip("quarto/pandoc not available")

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        rst_file = project_path / "test.rst"
        rst_file.write_text(
            "Title\n=====\n\nParagraph text.\n\nSubtitle\n--------\n\n- Item 1\n- Item 2\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._convert_rst_to_markdown(rst_file)

        # Should have Markdown headings
        assert "# Title" in result
        assert "## Subtitle" in result or "Subtitle" in result
        assert "Paragraph text" in result
        assert "Item 1" in result


# =========================================================================
# Changelog (GitHub Releases) Tests
# =========================================================================


def test_fetch_github_releases_success():
    """Test fetching releases from the GitHub API (mocked)."""
    from unittest.mock import patch, MagicMock

    docs = GreatDocs()

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [
        {
            "tag_name": "v1.0.0",
            "name": "Version 1.0",
            "body": "First stable release.\n\n- Feature A\n- Feature B",
            "published_at": "2026-01-15T00:00:00Z",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
            "prerelease": False,
            "draft": False,
        },
        {
            "tag_name": "v0.9.0",
            "name": "Beta",
            "body": "Beta release.",
            "published_at": "2025-12-01T00:00:00Z",
            "html_url": "https://github.com/owner/repo/releases/tag/v0.9.0",
            "prerelease": True,
            "draft": False,
        },
        {
            "tag_name": "v0.8.0-draft",
            "name": "Draft",
            "body": "Draft release.",
            "published_at": "2025-11-01T00:00:00Z",
            "html_url": "https://github.com/owner/repo/releases/tag/v0.8.0-draft",
            "prerelease": False,
            "draft": True,
        },
    ]

    with patch("requests.get", return_value=fake_response) as mock_get:
        releases = docs._fetch_github_releases("owner", "repo", max_releases=10)

    mock_get.assert_called_once()
    assert len(releases) == 2  # Draft skipped
    assert releases[0]["tag_name"] == "v1.0.0"
    assert releases[0]["name"] == "Version 1.0"
    assert releases[0]["body"] == "First stable release.\n\n- Feature A\n- Feature B"
    assert releases[1]["prerelease"] is True


def test_fetch_github_releases_404():
    """Test that a 404 returns an empty list."""
    from unittest.mock import patch, MagicMock

    docs = GreatDocs()
    fake_response = MagicMock()
    fake_response.status_code = 404

    with patch("requests.get", return_value=fake_response):
        releases = docs._fetch_github_releases("no", "repo")

    assert releases == []


def test_fetch_github_releases_rate_limited():
    """Test that a 403 returns what was already fetched (empty)."""
    from unittest.mock import patch, MagicMock

    docs = GreatDocs()
    fake_response = MagicMock()
    fake_response.status_code = 403

    with patch("requests.get", return_value=fake_response):
        releases = docs._fetch_github_releases("owner", "repo")

    assert releases == []


def test_fetch_github_releases_network_error():
    """Test graceful handling of network errors."""
    from unittest.mock import patch
    import requests as req_lib

    docs = GreatDocs()

    with patch("requests.get", side_effect=req_lib.ConnectionError("offline")):
        releases = docs._fetch_github_releases("owner", "repo")

    assert releases == []


def test_generate_changelog_page():
    """Test changelog.qmd page generation."""
    from unittest.mock import patch, MagicMock

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal project structure
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n\n'
            '[project.urls]\nRepository = "https://github.com/owner/repo"\n'
        )
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        docs = GreatDocs(project_path=tmp_dir)

        fake_releases = [
            {
                "tag_name": "v2.0.0",
                "name": "Version 2.0",
                "body": "Major update.\n\n### Breaking changes\n\n- Removed X\n",
                "published_at": "2026-02-10T00:00:00Z",
                "html_url": "https://github.com/owner/repo/releases/tag/v2.0.0",
                "prerelease": False,
            },
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0",
                "body": "Initial release.",
                "published_at": "2025-12-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
                "prerelease": False,
            },
        ]

        with patch.object(docs, "_fetch_github_releases", return_value=fake_releases):
            result = docs._generate_changelog_page()

        assert result == "changelog.qmd"

        changelog_qmd = build_dir / "changelog.qmd"
        assert changelog_qmd.exists()

        content = changelog_qmd.read_text()
        assert 'title: "Changelog"' in content
        assert "## Version 2.0" in content
        assert "## Version 1.0" in content
        assert "*2026-02-10*" in content
        assert "### Breaking changes" in content
        assert "Initial release." in content
        assert "https://github.com/owner/repo/releases" in content


def test_generate_changelog_page_no_github():
    """Test that changelog is skipped when no GitHub repo is configured."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._generate_changelog_page()

        assert result is None


def test_generate_changelog_page_no_releases():
    """Test that changelog is skipped when there are no releases."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n\n'
            '[project.urls]\nRepository = "https://github.com/owner/repo"\n'
        )
        config_path = project_path / "great-docs.yml"
        config_path.write_text("")
        (project_path / "great-docs").mkdir()

        docs = GreatDocs(project_path=tmp_dir)

        with patch.object(docs, "_fetch_github_releases", return_value=[]):
            result = docs._generate_changelog_page()

        assert result is None


def test_add_changelog_to_navbar():
    """Test that a Changelog link is added to the navbar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        # Write a basic _quarto.yml
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs._add_changelog_to_navbar()

        import yaml

        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        navbar_items = config["website"]["navbar"]["left"]
        changelog_items = [
            i for i in navbar_items if isinstance(i, dict) and i.get("text") == "Changelog"
        ]
        assert len(changelog_items) == 1
        assert changelog_items[0]["href"] == "changelog.qmd"


def test_add_changelog_to_navbar_idempotent():
    """Test that adding changelog twice doesn't duplicate it."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n  navbar:\n    left:\n      - text: Reference\n        href: reference/index.qmd\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs._add_changelog_to_navbar()
        docs._add_changelog_to_navbar()

        import yaml

        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        changelog_items = [
            i
            for i in config["website"]["navbar"]["left"]
            if isinstance(i, dict) and i.get("text") == "Changelog"
        ]
        assert len(changelog_items) == 1


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


def test_fetch_github_releases_pagination():
    """Test that pagination works for many releases."""
    from unittest.mock import patch, MagicMock, call

    docs = GreatDocs()

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = [
        {
            "tag_name": f"v{i}.0.0",
            "name": f"Release {i}",
            "body": f"Release {i} notes.",
            "published_at": f"2026-01-{i:02d}T00:00:00Z",
            "html_url": f"https://github.com/o/r/releases/tag/v{i}.0.0",
            "prerelease": False,
            "draft": False,
        }
        for i in range(1, 4)
    ]

    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = []  # empty = last page

    with patch("requests.get", side_effect=[page1, page2]):
        releases = docs._fetch_github_releases("o", "r", max_releases=10)

    assert len(releases) == 3


def test_fetch_github_releases_max_cap():
    """Test that max_releases caps the returned list."""
    from unittest.mock import patch, MagicMock

    docs = GreatDocs()

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [
        {
            "tag_name": f"v{i}",
            "name": f"R{i}",
            "body": "",
            "published_at": "2026-01-01T00:00:00Z",
            "html_url": f"https://github.com/o/r/releases/tag/v{i}",
            "prerelease": False,
            "draft": False,
        }
        for i in range(1, 20)
    ]

    with patch("requests.get", return_value=fake_response):
        releases = docs._fetch_github_releases("o", "r", max_releases=5)

    assert len(releases) == 5


# =========================================================================
# Linkify GitHub References Tests
# =========================================================================


def test_linkify_bare_issue_number():
    """Test that bare #NNN references become links."""
    docs = GreatDocs()
    text = "Fixed a bug (#42) and another issue #100."
    result = docs._linkify_github_references(text, "owner", "repo")
    assert "[#42](https://github.com/owner/repo/issues/42)" in result
    assert "[#100](https://github.com/owner/repo/issues/100)" in result


def test_linkify_gh_issue_and_pr():
    """Test 'gh issue #NNN' and 'gh pr #NNN' patterns."""
    docs = GreatDocs()
    text = "Reported by @amureki (gh issue #662, gh pr #679)"
    result = docs._linkify_github_references(text, "owner", "repo")
    assert "[#662](https://github.com/owner/repo/issues/662)" in result
    assert "[#679](https://github.com/owner/repo/issues/679)" in result
    # The "gh issue" / "gh pr" prefix should be consumed
    assert "gh issue" not in result
    assert "gh pr" not in result


def test_linkify_at_mention():
    """Test @username becomes a link to GitHub profile."""
    docs = GreatDocs()
    text = "Reported and fixed by @amureki and @some-user."
    result = docs._linkify_github_references(text, "o", "r")
    assert "[@amureki](https://github.com/amureki)" in result
    assert "[@some-user](https://github.com/some-user)" in result


def test_linkify_no_double_linking():
    """Test that already-linked references are not double-wrapped."""
    docs = GreatDocs()
    # After one pass, #42 becomes [#42](…/42); a second pass must not re-wrap
    text = "[#42](https://github.com/owner/repo/issues/42)"
    result = docs._linkify_github_references(text, "owner", "repo")
    # Should still have exactly one link, not nested
    assert result.count("[#42]") == 1


def test_linkify_email_not_matched():
    """Test that email addresses are not treated as @mentions."""
    docs = GreatDocs()
    text = "Contact user@example.com for help."
    result = docs._linkify_github_references(text, "o", "r")
    assert "[@example" not in result
    assert "user@example.com" in result


def test_linkify_case_insensitive_gh_prefix():
    """Test that GH Issue / GH PR are matched case-insensitively."""
    docs = GreatDocs()
    text = "See GH Issue #10 and GH PR #20."
    result = docs._linkify_github_references(text, "o", "r")
    assert "[#10](https://github.com/o/r/issues/10)" in result
    assert "[#20](https://github.com/o/r/issues/20)" in result


def test_linkify_backslash_escaped_refs():
    """Test that GitHub API backslash escapes (\\@, \\#) are handled."""
    docs = GreatDocs()
    # Raw body from GitHub API often contains \@ and \# escapes
    text = r"Reported by \@hawkEye-01 (gh issue \#1167). Fixed by \@Mifrill (gh pr \#1168)"
    result = docs._linkify_github_references(text, "dateutil", "dateutil")
    assert "[@hawkEye-01](https://github.com/hawkEye-01)" in result
    assert "[#1167](https://github.com/dateutil/dateutil/issues/1167)" in result
    assert "[#1168](https://github.com/dateutil/dateutil/issues/1168)" in result
    # No leftover backslashes before @ or #
    assert "\\@" not in result
    assert "\\#" not in result


def test_linkify_backslash_escaped_quotes():
    """Test that escaped quotes and apostrophes are cleaned up."""
    docs = GreatDocs()
    text = r"Fixed a bug where it doesn\'t work with \"special\" input."
    result = docs._linkify_github_references(text, "o", "r")
    assert "doesn't" in result
    assert '"special"' in result
    assert "\\" not in result


def test_linkify_integrated_in_changelog():
    """Test that linkification happens when generating changelog.qmd."""
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "pkg"\nversion = "1.0"\n\n'
            '[project.urls]\nRepository = "https://github.com/owner/repo"\n'
        )
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        docs = GreatDocs(project_path=tmp_dir)

        fake_releases = [
            {
                "tag_name": "v1.0.0",
                "name": "Version 1.0",
                "body": "Fixed #55 by @contributor (gh pr #60).",
                "published_at": "2025-06-01T00:00:00Z",
                "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
                "prerelease": False,
            },
        ]

        with patch.object(docs, "_fetch_github_releases", return_value=fake_releases):
            docs._generate_changelog_page()

        content = (build_dir / "changelog.qmd").read_text()
        assert "[#55](https://github.com/owner/repo/issues/55)" in content
        assert "[#60](https://github.com/owner/repo/issues/60)" in content
        assert "[@contributor](https://github.com/contributor)" in content


# =========================================================================
# Custom Sections Tests
# =========================================================================


def test_process_sections_empty_config():
    """Test that no sections are processed when config is empty."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        (project_path / "great-docs").mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()
        assert result == 0


def test_process_sections_discovers_and_copies():
    """Test that sections are discovered, copied, and indexed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        config_path = project_path / "great-docs.yml"
        config_path.write_text("sections:\n  - title: Examples\n    dir: examples\n")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()

        # Write a minimal _quarto.yml
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        # Create example files
        examples_dir = project_path / "examples"
        examples_dir.mkdir()
        (examples_dir / "01-basic.qmd").write_text(
            '---\ntitle: "Basic Example"\ndescription: "A basic demo"\n---\n\nHello\n'
        )
        (examples_dir / "02-advanced.qmd").write_text(
            '---\ntitle: "Advanced Example"\n---\n\nAdvanced content\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()

        assert result == 1

        # Check files were copied (with numeric prefix stripped)
        dest = build_dir / "examples"
        assert dest.exists()
        assert (dest / "basic.qmd").exists()
        assert (dest / "advanced.qmd").exists()

        # Check auto-generated index
        index = dest / "index.qmd"
        assert index.exists()
        content = index.read_text()
        assert "Examples" in content
        assert "Basic Example" in content
        assert "Advanced Example" in content

        # Check navbar was updated
        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)
        navbar_texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]
        assert "Examples" in navbar_texts

        # Check sidebar was added
        sidebar_ids = [s.get("id") for s in config["website"]["sidebar"] if isinstance(s, dict)]
        assert "examples" in sidebar_ids


def test_process_sections_user_provided_index():
    """Test that user-provided index.qmd is used instead of auto-generating."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Demos\n    dir: demos\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n  navbar:\n    left:\n"
            "      - text: Home\n        href: index.qmd\n"
            "  sidebar: []\n"
        )

        demos_dir = project_path / "demos"
        demos_dir.mkdir()
        (demos_dir / "index.qmd").write_text(
            '---\ntitle: "My Custom Index"\n---\n\nCustom gallery content\n'
        )
        (demos_dir / "demo1.qmd").write_text('---\ntitle: "Demo One"\n---\n\nDemo\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()

        assert result == 1

        # The user's index should be preserved, not overwritten
        index = build_dir / "demos" / "index.qmd"
        content = index.read_text()
        assert "Custom gallery content" in content


def test_process_sections_missing_dir():
    """Test that a section with a missing directory is skipped."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Nope\n    dir: nonexistent\n"
        )
        (project_path / "great-docs").mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()

        assert result == 0


def test_process_sections_navbar_after():
    """Test that navbar_after controls link placement."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Tutorials\n    dir: tutorials\n    navbar_after: User Guide\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: User Guide\n"
            "        href: user-guide/index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        tut_dir = project_path / "tutorials"
        tut_dir.mkdir()
        (tut_dir / "intro.qmd").write_text('---\ntitle: "Intro"\n---\n\nIntro\n')

        docs = GreatDocs(project_path=tmp_dir)
        docs._process_sections()

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]
        # Tutorials should be right after User Guide
        assert texts.index("Tutorials") == texts.index("User Guide") + 1
        assert texts.index("Tutorials") < texts.index("Reference")


def test_process_sections_default_navbar_before_reference():
    """Test that without navbar_after, link goes before Reference."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: User Guide\n"
            "        href: user-guide/index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "demo.qmd").write_text('---\ntitle: "Demo"\n---\n\nDemo\n')

        docs = GreatDocs(project_path=tmp_dir)
        docs._process_sections()

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]
        assert texts.index("Examples") < texts.index("Reference")


def test_process_sections_multiple():
    """Test processing multiple sections at once."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n"
            "  - title: Examples\n"
            "    dir: examples\n"
            "  - title: Tutorials\n"
            "    dir: tutorials\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "      - text: Reference\n"
            "        href: reference/index.qmd\n"
            "  sidebar: []\n"
        )

        for d in ("examples", "tutorials"):
            (project_path / d).mkdir()
            (project_path / d / "page.qmd").write_text(f'---\ntitle: "{d} page"\n---\n\n{d}\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()

        assert result == 2

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)
        texts = [
            item.get("text")
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict)
        ]
        assert "Examples" in texts
        assert "Tutorials" in texts


def test_process_sections_idempotent():
    """Test that processing sections twice doesn't duplicate navbar/sidebar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Examples\n    dir: examples\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
            "website:\n"
            "  navbar:\n"
            "    left:\n"
            "      - text: Home\n"
            "        href: index.qmd\n"
            "  sidebar: []\n"
        )

        ex_dir = project_path / "examples"
        ex_dir.mkdir()
        (ex_dir / "page.qmd").write_text('---\ntitle: "Page"\n---\n\nContent\n')

        docs = GreatDocs(project_path=tmp_dir)
        docs._process_sections()
        docs._process_sections()

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)

        # Only one navbar link
        example_links = [
            item
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict) and item.get("text") == "Examples"
        ]
        assert len(example_links) == 1

        # Only one sidebar
        example_sidebars = [
            s
            for s in config["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "examples"
        ]
        assert len(example_sidebars) == 1


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


def test_generate_section_index_with_descriptions():
    """Test auto-generated index includes descriptions and images."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text(
            "sections:\n  - title: Gallery\n    dir: gallery\n"
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text("website:\n  navbar:\n    left: []\n  sidebar: []\n")

        gallery_dir = project_path / "gallery"
        gallery_dir.mkdir()
        (gallery_dir / "card1.qmd").write_text(
            '---\ntitle: "Card One"\ndescription: "First card description"\n'
            'image: "img/card1.png"\n---\n\nBody\n'
        )
        (gallery_dir / "card2.qmd").write_text(
            '---\ntitle: "Card Two"\ndescription: "Second card"\n---\n\nBody\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs._process_sections()

        index = build_dir / "gallery" / "index.qmd"
        content = index.read_text()
        assert "Card One" in content
        assert "First card description" in content
        assert "img/card1.png" in content
        assert "Card Two" in content
        assert "Second card" in content


# =============================================================================
# Navbar Home Removal + Version Badge Tests
# =============================================================================


def test_navbar_no_home_new_build():
    """Test that new builds don't include a Home navbar item."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text("website:\n  title: TestPkg\nformat:\n  html:\n    theme: flatly\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs._update_quarto_config()

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)

        navbar_items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in navbar_items if isinstance(item, dict)]
        assert "Home" not in texts
        assert "Reference" in texts


def test_navbar_home_removed_from_existing():
    """Test that existing navbars with Home get it removed."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text(
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
        docs._update_quarto_config()

        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)

        navbar_items = config["website"]["navbar"]["left"]
        texts = [item.get("text") for item in navbar_items if isinstance(item, dict)]
        assert "Home" not in texts
        assert "Reference" in texts


def test_version_metadata_from_github_release():
    """Test that _package_meta.json is written from the latest GitHub release."""
    from unittest.mock import patch

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
        quarto_yml.write_text("website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n")

        docs = GreatDocs(project_path=tmp_dir)

        with patch.object(docs, "_fetch_github_releases", return_value=fake_releases):
            docs._update_quarto_config()

        import json

        meta_path = build_dir / "_package_meta.json"
        assert meta_path.exists()
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta["version"] == "2.3.4"
        assert meta["published_at"] == "2025-06-15T18:30:00Z"


def test_version_metadata_not_written_no_releases():
    """Test graceful degradation when no GitHub releases exist."""
    from unittest.mock import patch

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
        quarto_yml.write_text("website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n")

        docs = GreatDocs(project_path=tmp_dir)

        with patch.object(docs, "_fetch_github_releases", return_value=[]):
            docs._update_quarto_config()

        meta_path = build_dir / "_package_meta.json"
        assert not meta_path.exists()


def test_version_metadata_not_written_no_github():
    """Test that _package_meta.json is not written when no GitHub repo info."""
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
        quarto_yml.write_text("website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs._update_quarto_config()

        meta_path = build_dir / "_package_meta.json"
        assert not meta_path.exists()


def test_version_metadata_strips_v_prefix():
    """Test that 'v' prefix is stripped from tag_name for the version value."""
    from unittest.mock import patch

    fake_releases = [
        {
            "tag_name": "v1.0.0",
            "name": "v1.0.0",
            "body": "",
            "published_at": "2025-01-01T00:00:00Z",
            "html_url": "",
            "prerelease": False,
        }
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        (project_path / "great-docs.yml").write_text("")
        (project_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "test-pkg"\n'
            'version = "1.0.0"\n'
            "\n"
            "[project.urls]\n"
            'Repository = "https://github.com/test/pkg"\n'
        )
        build_dir = project_path / "great-docs"
        build_dir.mkdir()
        quarto_yml = build_dir / "_quarto.yml"
        quarto_yml.write_text("website:\n  title: test-pkg\nformat:\n  html:\n    theme: flatly\n")

        docs = GreatDocs(project_path=tmp_dir)

        with patch.object(docs, "_fetch_github_releases", return_value=fake_releases):
            docs._update_quarto_config()

        import json

        meta_path = build_dir / "_package_meta.json"
        assert meta_path.exists()
        with open(meta_path) as f:
            meta = json.load(f)
        # Should be "1.0.0" not "v1.0.0"
        assert meta["version"] == "1.0.0"


# ── Module Introspection Tests ───────────────────────────────────────────


def test_module_exports_categorized():
    """Test that packages exporting submodules properly categorize their contents."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a package that exports submodules (like python-dateutil)
        pkg_dir = Path(tmp_dir) / "modpkg"
        pkg_dir.mkdir()

        # Main __init__.py exports submodules
        (pkg_dir / "__init__.py").write_text(
            '"""A package with submodule exports."""\n__all__ = ["shapes", "colors"]\n'
        )

        # Create shapes submodule with classes and functions
        shapes_dir = pkg_dir / "shapes"
        shapes_dir.mkdir()
        (shapes_dir / "__init__.py").write_text(
            '"""Shapes module."""\n'
            "class Circle:\n"
            '    """A circle."""\n'
            "    def area(self): pass\n"
            "\n"
            "class Square:\n"
            '    """A square."""\n'
            "    def area(self): pass\n"
            "\n"
            "def draw(shape):\n"
            '    """Draw a shape."""\n'
            "    pass\n"
            "\n"
            "MAX_SIDES = 100\n"
        )

        # Create colors submodule with functions
        colors_dir = pkg_dir / "colors"
        colors_dir.mkdir()
        (colors_dir / "__init__.py").write_text(
            '"""Colors module."""\n'
            "def mix(a, b):\n"
            '    """Mix two colors."""\n'
            "    pass\n"
            "\n"
            "def blend(a, b, ratio=0.5):\n"
            '    """Blend two colors."""\n'
            "    pass\n"
            "\n"
            "RED = (255, 0, 0)\n"
            "BLUE = (0, 0, 255)\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects("modpkg", ["shapes", "colors"])

            # Classes inside modules should be categorized with qualified names
            assert "shapes.Circle" in categories["classes"]
            assert "shapes.Square" in categories["classes"]

            # Functions inside modules should be categorized with qualified names
            assert "shapes.draw" in categories["functions"]
            assert "colors.mix" in categories["functions"]
            assert "colors.blend" in categories["functions"]

            # Constants inside modules should be categorized
            assert "shapes.MAX_SIDES" in categories["constants"]
            assert "colors.RED" in categories["constants"]
            assert "colors.BLUE" in categories["constants"]

            # Nothing should be in "other"
            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_module_class_methods_tracked():
    """Test that classes inside modules have methods properly counted."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "methpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with module exports."""\n__all__ = ["models"]\n'
        )

        models_dir = pkg_dir / "models"
        models_dir.mkdir()
        (models_dir / "__init__.py").write_text(
            '"""Models module."""\n'
            "class BigModel:\n"
            '    """A model with many methods."""\n'
            "    def fit(self): pass\n"
            "    def predict(self): pass\n"
            "    def score(self): pass\n"
            "    def transform(self): pass\n"
            "    def validate(self): pass\n"
            "    def serialize(self): pass\n"
            "    def load(self): pass\n"
            "\n"
            "class SmallModel:\n"
            '    """A model with few methods."""\n'
            "    def fit(self): pass\n"
            "    def predict(self): pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects("methpkg", ["models"])

            # BigModel should have 7 methods tracked
            assert categories["class_methods"]["models.BigModel"] == 7
            assert len(categories["class_method_names"]["models.BigModel"]) == 7
            assert "fit" in categories["class_method_names"]["models.BigModel"]
            assert "serialize" in categories["class_method_names"]["models.BigModel"]

            # SmallModel should have 2 methods tracked
            assert categories["class_methods"]["models.SmallModel"] == 2
        finally:
            sys.path.remove(tmp_dir)


def test_module_big_class_splitting():
    """Test that classes inside modules with >5 methods get separate sections."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "splitpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with big class in submodule."""\n__all__ = ["engine"]\n'
        )

        engine_dir = pkg_dir / "engine"
        engine_dir.mkdir()
        (engine_dir / "__init__.py").write_text(
            '"""Engine module."""\n'
            "class Engine:\n"
            '    """A big engine class."""\n'
            "    def start(self): pass\n"
            "    def stop(self): pass\n"
            "    def accelerate(self): pass\n"
            "    def brake(self): pass\n"
            "    def reverse(self): pass\n"
            "    def park(self): pass\n"
            "    def idle(self): pass\n"
            "\n"
            "def create_engine():\n"
            '    """Create an engine."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            sections = docs._create_quartodoc_sections("splitpkg")

            assert sections is not None

            # Classes section should exist with engine.Engine having members: []
            class_section = next((s for s in sections if s["title"] == "Classes"), None)
            assert class_section is not None

            big_class_entry = next(
                (
                    c
                    for c in class_section["contents"]
                    if isinstance(c, dict) and c.get("name") == "engine.Engine"
                ),
                None,
            )
            assert big_class_entry is not None
            assert big_class_entry == {"name": "engine.Engine", "members": []}

            # Separate method section for engine.Engine
            method_section = next(
                (s for s in sections if s["title"] == "engine.Engine Methods"),
                None,
            )
            assert method_section is not None
            assert len(method_section["contents"]) == 7
            assert "engine.Engine.start" in method_section["contents"]
            assert "engine.Engine.park" in method_section["contents"]

            # Functions section should have create_engine
            func_section = next((s for s in sections if s["title"] == "Functions"), None)
            assert func_section is not None
            assert "engine.create_engine" in func_section["contents"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_exception_subclassification():
    """Test that exceptions inside modules are categorized correctly."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "errpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with exceptions in submodule."""\n__all__ = ["errors"]\n'
        )

        errors_dir = pkg_dir / "errors"
        errors_dir.mkdir()
        (errors_dir / "__init__.py").write_text(
            '"""Errors module."""\n'
            "class ValidationError(ValueError):\n"
            '    """Validation failed."""\n'
            "    pass\n"
            "\n"
            "class NotFoundError(KeyError):\n"
            '    """Item not found."""\n'
            "    pass\n"
            "\n"
            "class Widget:\n"
            '    """A regular class."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects("errpkg", ["errors"])

            # Exceptions should be in the exceptions category
            assert "errors.ValidationError" in categories["exceptions"]
            assert "errors.NotFoundError" in categories["exceptions"]

            # Regular class should be in classes
            assert "errors.Widget" in categories["classes"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_empty_submodule_goes_to_other():
    """Test that modules with no documentable members go to 'other'."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "emptypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with empty submodule."""\n__all__ = ["empty_mod"]\n'
        )

        empty_dir = pkg_dir / "empty_mod"
        empty_dir.mkdir()
        (empty_dir / "__init__.py").write_text(
            '"""Empty module with only private members."""\n_internal = 42\n_helper = lambda x: x\n'
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects("emptypkg", ["empty_mod"])

            # Module with no public members should go to "other"
            assert "empty_mod" in categories["other"]
        finally:
            sys.path.remove(tmp_dir)


def test_module_mixed_with_top_level():
    """Test packages with both module exports and top-level classes/functions."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mixedpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Mixed package."""\n'
            '__all__ = ["TopClass", "top_func", "sub"]\n'
            "\n"
            "class TopClass:\n"
            '    """A top-level class."""\n'
            "    pass\n"
            "\n"
            "def top_func():\n"
            '    """A top-level function."""\n'
            "    pass\n"
        )

        sub_dir = pkg_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text(
            '"""Sub module."""\n'
            "class SubClass:\n"
            '    """A class inside a submodule."""\n'
            "    pass\n"
            "\n"
            "def sub_func():\n"
            '    """A function inside a submodule."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects("mixedpkg", ["TopClass", "top_func", "sub"])

            # Top-level items
            assert "TopClass" in categories["classes"]
            assert "top_func" in categories["functions"]

            # Submodule items (qualified names)
            assert "sub.SubClass" in categories["classes"]
            assert "sub.sub_func" in categories["functions"]

            # No "other"
            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_module_submodule_allowed_in_exports():
    """Test that submodules are not excluded from _get_package_exports."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "subexpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with submodule in __all__."""\n__all__ = ["mymod"]\n'
        )

        mod_dir = pkg_dir / "mymod"
        mod_dir.mkdir()
        (mod_dir / "__init__.py").write_text('"""My module."""\ndef hello(): pass\n')

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            exports = docs._get_package_exports("subexpkg")

            # Submodules should NOT be excluded
            assert exports is not None
            assert "mymod" in exports
        finally:
            sys.path.remove(tmp_dir)


def test_write_object_types_json():
    """Test that _write_object_types_json writes correct type mapping."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        categories = docs._empty_categories()
        categories["classes"] = ["MyClass", "parser.ParserInfo"]
        categories["exceptions"] = ["parser.ParserError"]
        categories["functions"] = ["parse", "easter.easter"]
        categories["constants"] = ["DEFAULTPARSER"]
        categories["enums"] = ["Color"]
        categories["type_aliases"] = ["DateType"]
        categories["other"] = ["sys"]
        categories["class_method_names"] = {
            "MyClass": ["fit", "predict"],
            "parser.ParserInfo": ["info"],
        }

        docs._write_object_types_json(categories)

        types_path = docs.project_path / "_object_types.json"
        assert types_path.exists()

        with open(types_path) as f:
            obj_types = json.load(f)

        # Classes (including module-qualified ones)
        assert obj_types["MyClass"] == "class"
        assert obj_types["parser.ParserInfo"] == "class"

        # Exceptions
        assert obj_types["parser.ParserError"] == "exception"

        # Functions
        assert obj_types["parse"] == "function"
        assert obj_types["easter.easter"] == "function"

        # Constants
        assert obj_types["DEFAULTPARSER"] == "constant"

        # Enums
        assert obj_types["Color"] == "enum"

        # Type aliases
        assert obj_types["DateType"] == "type_alias"

        # Other
        assert obj_types["sys"] == "other"

        # Methods
        assert obj_types["MyClass.fit"] == "method"
        assert obj_types["MyClass.predict"] == "method"
        assert obj_types["parser.ParserInfo.info"] == "method"


def test_write_object_types_json_empty_categories():
    """Test that _write_object_types_json handles empty categories."""
    import json

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        categories = docs._empty_categories()

        docs._write_object_types_json(categories)

        types_path = docs.project_path / "_object_types.json"
        assert types_path.exists()

        with open(types_path) as f:
            obj_types = json.load(f)

        assert obj_types == {}


def test_object_types_integrated_with_categorization():
    """Test that _categorize_api_objects + _write_object_types_json produce
    correct types for a package with mixed exports."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "typepkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with diverse types."""\n'
            '__all__ = ["MyClass", "my_func", "MyError", "MAX_SIZE"]\n'
            "\n"
            "class MyClass:\n"
            '    """A normal class."""\n'
            "    def action(self): pass\n"
            "\n"
            "def my_func():\n"
            '    """A function."""\n'
            "    pass\n"
            "\n"
            "class MyError(Exception):\n"
            '    """An exception."""\n'
            "    pass\n"
            "\n"
            "MAX_SIZE = 1024\n"
        )

        sys.path.insert(0, tmp_dir)

        # Create a build directory for the docs output
        build_dir = Path(tmp_dir) / "docs"
        build_dir.mkdir()

        try:
            docs = GreatDocs(project_path=str(build_dir))
            docs.project_path.mkdir(parents=True, exist_ok=True)
            categories = docs._categorize_api_objects(
                "typepkg", ["MyClass", "my_func", "MyError", "MAX_SIZE"]
            )

            docs._write_object_types_json(categories)

            import json

            types_path = docs.project_path / "_object_types.json"
            assert types_path.exists()

            with open(types_path) as f:
                obj_types = json.load(f)

            assert obj_types["MyClass"] == "class"
            assert obj_types["my_func"] == "function"
            assert obj_types["MyError"] == "exception"
            assert obj_types["MAX_SIZE"] == "constant"
            assert obj_types["MyClass.action"] == "method"
        finally:
            sys.path.remove(tmp_dir)


# ── Fallback categorization (griffe unavailable) ─────────────────────


def test_categorize_fallback_functions_not_other():
    """Functions must be categorized as 'functions', not 'other', when griffe
    cannot load the package and the inspect-based fallback is used."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "fbpkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Fallback test package."""\n'
            '__all__ = ["greet", "farewell"]\n'
            "\n"
            "def greet(name: str) -> str:\n"
            '    """Say hello."""\n'
            "    return f'Hello, {name}'\n"
            "\n"
            "def farewell(name: str) -> str:\n"
            '    """Say goodbye."""\n'
            "    return f'Goodbye, {name}'\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects_fallback("fbpkg", ["greet", "farewell"])

            assert "greet" in categories["functions"]
            assert "farewell" in categories["functions"]
            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_categorize_fallback_mixed_types():
    """Fallback categorization must correctly distinguish classes, functions,
    exceptions, dataclasses, and constants."""
    import sys
    from dataclasses import dataclass

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mixfb"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Mixed fallback test package."""\n'
            "from dataclasses import dataclass\n"
            "\n"
            '__all__ = ["Widget", "Config", "WidgetError", "build", "MAX"]\n'
            "\n"
            "class Widget:\n"
            '    """A widget."""\n'
            "    pass\n"
            "\n"
            "@dataclass\n"
            "class Config:\n"
            '    """A config."""\n'
            "    name: str = 'default'\n"
            "\n"
            "class WidgetError(Exception):\n"
            '    """A widget error."""\n'
            "    pass\n"
            "\n"
            "def build() -> Widget:\n"
            '    """Build a widget."""\n'
            "    return Widget()\n"
            "\n"
            "MAX = 100\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects_fallback(
                "mixfb", ["Widget", "Config", "WidgetError", "build", "MAX"]
            )

            assert "Widget" in categories["classes"]
            assert "Config" in categories["dataclasses"]
            assert "WidgetError" in categories["exceptions"]
            assert "build" in categories["functions"]
            assert "MAX" in categories["constants"]
            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_categorize_fallback_discovers_module_by_dir():
    """When the normalized project name doesn't match the actual module,
    the fallback must discover and import the correct module directory."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Project name normalizes to 'my_v2_pkg' but the actual module is 'mypkg'
        pkg_dir = Path(tmp_dir) / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Package with mismatched name."""\n'
            '__all__ = ["do_stuff"]\n'
            "\n"
            "def do_stuff():\n"
            '    """Do stuff."""\n'
            "    pass\n"
        )

        # Also create pyproject.toml so _find_package_root works
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "my-v2-pkg"\nversion = "0.1.0"\n'
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects_fallback(
                "my_v2_pkg",  # wrong name — should discover 'mypkg'
                ["do_stuff"],
            )

            assert "do_stuff" in categories["functions"]
            assert categories["other"] == []
        finally:
            sys.path.remove(tmp_dir)


def test_categorize_fallback_skips_metadata():
    """Metadata variables like __version__ must be skipped by the fallback."""
    import sys

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "metapkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text(
            '"""Metadata test."""\n'
            '__version__ = "1.0.0"\n'
            '__all__ = ["run"]\n'
            "\n"
            "def run():\n"
            '    """Run."""\n'
            "    pass\n"
        )

        sys.path.insert(0, tmp_dir)
        try:
            docs = GreatDocs(project_path=tmp_dir)
            categories = docs._categorize_api_objects_fallback("metapkg", ["__version__", "run"])

            assert "run" in categories["functions"]
            assert "__version__" not in categories["functions"]
            assert "__version__" not in categories["other"]
            assert "__version__" not in categories["constants"]
        finally:
            sys.path.remove(tmp_dir)


# =========================================================================
# RST Math Conversion Tests
# =========================================================================


class TestFixRstMathInQmd:
    """Tests for .. math:: and :math: conversion in _fix_rst_code_blocks_in_qmd."""

    def _run_fix(self, qmd_content: str) -> str:
        """Create a temp project with a .qmd file, run the fixer, return result."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "great-docs"
            ref_dir = project_path / "reference"
            ref_dir.mkdir(parents=True)
            qmd_file = ref_dir / "func.qmd"
            qmd_file.write_text(qmd_content)

            config_path = project_path.parent / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=str(project_path.parent))
            docs.project_path = project_path
            docs._fix_rst_code_blocks_in_qmd()

            return qmd_file.read_text()

    def test_display_math_converted_to_dollar_signs(self):
        """.. math:: with indented LaTeX becomes $$...$$ block."""
        qmd = (
            "Some text:\n\n.. math::\n\n    \\|x\\| = \\sqrt{\\sum_{i=1}^{n} x_i^2}\n\nMore text.\n"
        )
        result = self._run_fix(qmd)
        assert "$$" in result
        assert "\\|x\\| = \\sqrt{\\sum_{i=1}^{n} x_i^2}" in result
        assert ".. math::" not in result

    def test_display_math_multiline(self):
        """.. math:: with multi-line LaTeX is properly converted."""
        qmd = (
            "The softmax:\n"
            "\n"
            ".. math::\n"
            "\n"
            "    \\sigma(z)_i = \\frac{e^{z_i}}\n"
            "    {\\sum_{j=1}^{K} e^{z_j}}\n"
            "\n"
            "End.\n"
        )
        result = self._run_fix(qmd)
        assert "$$" in result
        assert "\\sigma(z)_i" in result
        assert ".. math::" not in result

    def test_multiple_display_math_blocks(self):
        """Multiple .. math:: blocks in same file are all converted."""
        qmd = (
            "First:\n"
            "\n"
            ".. math::\n"
            "\n"
            "    a^2 + b^2 = c^2\n"
            "\n"
            "Second:\n"
            "\n"
            ".. math::\n"
            "\n"
            "    E = mc^2\n"
            "\n"
            "Done.\n"
        )
        result = self._run_fix(qmd)
        assert result.count("$$") == 4  # Two blocks, each with opening + closing $$
        assert "a^2 + b^2 = c^2" in result
        assert "E = mc^2" in result

    def test_inline_math_converted(self):
        r"""RST :math:`...` becomes $...$."""
        qmd = "The distance :math:`d(x, y)` is computed.\n"
        result = self._run_fix(qmd)
        assert "$d(x, y)$" in result
        assert ":math:" not in result

    def test_multiple_inline_math(self):
        """Multiple :math: on the same line are all converted."""
        qmd = "For :math:`x` and :math:`y`, compute :math:`x + y`.\n"
        result = self._run_fix(qmd)
        assert "$x$" in result
        assert "$y$" in result
        assert "$x + y$" in result
        assert ":math:" not in result

    def test_inline_math_with_complex_expression(self):
        r"""Inline math with complex LaTeX is correctly converted."""
        qmd = "The sigmoid is :math:`\\sigma(x) = \\frac{1}{1 + e^{-x}}`.\n"
        result = self._run_fix(qmd)
        assert "$\\sigma(x) = \\frac{1}{1 + e^{-x}}$" in result
        assert ":math:" not in result

    def test_non_math_directives_preserved(self):
        """Other RST directives like .. note:: are not converted to math."""
        qmd = ".. note::\n\n    This is a note.\n\n"
        result = self._run_fix(qmd)
        assert ".. note::" in result
        assert "$$" not in result

    def test_regular_code_block_still_converted(self):
        """Normal :: code blocks are still converted to fenced blocks."""
        qmd = "Example::\n\n    x = 1\n    y = 2\n\n"
        result = self._run_fix(qmd)
        assert "```python" in result
        assert "x = 1" in result
        assert "::" not in result.split("```")[0]  # :: removed from intro text

    def test_mixed_math_and_code(self):
        """File with both math and code blocks handles each correctly."""
        qmd = "The formula:\n\n.. math::\n\n    E = mc^2\n\nExample::\n\n    result = compute()\n\n"
        result = self._run_fix(qmd)
        assert "$$" in result
        assert "E = mc^2" in result
        assert "```python" in result
        assert "result = compute()" in result

    def test_index_qmd_skipped(self):
        """index.qmd files are not processed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "great-docs"
            ref_dir = project_path / "reference"
            ref_dir.mkdir(parents=True)

            index = ref_dir / "index.qmd"
            index.write_text(".. math::\n\n    x = 1\n")

            config_path = project_path.parent / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=str(project_path.parent))
            docs.project_path = project_path
            docs._fix_rst_code_blocks_in_qmd()

            # index.qmd should be unchanged
            assert ".. math::" in index.read_text()

    def test_no_reference_dir(self):
        """No crash when reference/ directory does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=tmp_dir)
            docs.project_path = Path(tmp_dir) / "great-docs"
            # Should not raise
            docs._fix_rst_code_blocks_in_qmd()


# =========================================================================
# RST Table Conversion Tests
# =========================================================================


class TestFixRstTablesInQmd:
    """Tests for RST simple-table and grid-table conversion in _fix_rst_tables_in_qmd."""

    def _run_fix(self, qmd_content: str) -> str:
        """Create a temp project with a .qmd file, run the fixer, return result."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "great-docs"
            ref_dir = project_path / "reference"
            ref_dir.mkdir(parents=True)
            qmd_file = ref_dir / "func.qmd"
            qmd_file.write_text(qmd_content)

            config_path = project_path.parent / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=str(project_path.parent))
            docs.project_path = project_path
            docs._fix_rst_tables_in_qmd()

            return qmd_file.read_text()

    def test_simple_table_three_separators(self):
        """RST simple table with 3 separators (header/body) converts to Markdown pipe table."""
        qmd = (
            "The following table:\n"
            "\n"
            "========  =========  ===========\n"
            "Method    Speed      Memory\n"
            "========  =========  ===========\n"
            "Quick     O(n log n) O(log n)\n"
            "Merge     O(n log n) O(n)\n"
            "Bubble    O(n^2)     O(1)\n"
            "========  =========  ===========\n"
            "\n"
            "More text after.\n"
        )
        result = self._run_fix(qmd)
        # Should contain Markdown pipe table
        assert "| Method | Speed | Memory |" in result
        assert "| --- | --- | --- |" in result
        assert "| Quick | O(n log n) | O(log n) |" in result
        assert "| Merge | O(n log n) | O(n) |" in result
        assert "| Bubble | O(n^2) | O(1) |" in result
        # RST separators should be gone
        assert "========" not in result
        # Surrounding text preserved
        assert "The following table:" in result
        assert "More text after." in result

    def test_simple_table_two_separators(self):
        """RST simple table with 2 separators converts correctly."""
        qmd = (
            "==========  =====\n"
            "Metric      Value\n"
            "count       100\n"
            "mean        42.5\n"
            "std         12.3\n"
            "==========  =====\n"
        )
        result = self._run_fix(qmd)
        assert "| Metric | Value |" in result
        assert "| --- | --- |" in result
        assert "| count | 100 |" in result
        assert "| mean | 42.5 |" in result
        assert "| std | 12.3 |" in result
        assert "========" not in result

    def test_grid_table_with_header(self):
        """RST grid table with = header separator converts correctly."""
        qmd = (
            "+--------+-------+\n"
            "| Name   | Value |\n"
            "+========+=======+\n"
            "| alpha  | 1     |\n"
            "| beta   | 2     |\n"
            "+--------+-------+\n"
        )
        result = self._run_fix(qmd)
        assert "| Name | Value |" in result
        assert "| --- | --- |" in result
        assert "| alpha | 1 |" in result
        assert "| beta | 2 |" in result
        assert "+--------+" not in result

    def test_grid_table_without_header(self):
        """RST grid table with only - borders treats first row as header."""
        qmd = (
            "+--------+-------+\n"
            "| Name   | Value |\n"
            "+--------+-------+\n"
            "| alpha  | 1     |\n"
            "+--------+-------+\n"
        )
        result = self._run_fix(qmd)
        assert "| Name | Value |" in result
        assert "| --- | --- |" in result
        assert "| alpha | 1 |" in result

    def test_multiple_tables_in_one_file(self):
        """Multiple RST tables in a single file are all converted."""
        qmd = (
            "First table:\n"
            "\n"
            "====  =====\n"
            "A     B\n"
            "====  =====\n"
            "1     2\n"
            "====  =====\n"
            "\n"
            "Second table:\n"
            "\n"
            "=====  ======\n"
            "X      Y\n"
            "=====  ======\n"
            "10     20\n"
            "=====  ======\n"
        )
        result = self._run_fix(qmd)
        assert "| A | B |" in result
        assert "| 1 | 2 |" in result
        assert "| X | Y |" in result
        assert "| 10 | 20 |" in result
        assert "========" not in result
        assert "=====" not in result

    def test_cell_values_wider_than_header(self):
        """Cell values wider than the column header are fully captured."""
        qmd = (
            "========  =========  ===========\n"
            "Method    Speed      Memory\n"
            "========  =========  ===========\n"
            "Quick     O(n log n) O(log n)\n"
            "========  =========  ===========\n"
        )
        result = self._run_fix(qmd)
        # O(n log n) is wider than "=========" — ensure it's not truncated
        assert "O(n log n)" in result
        assert "O(n log n |" not in result.replace("O(n log n) |", "")

    def test_no_tables_unchanged(self):
        """Files without RST tables are not modified."""
        qmd = "No tables here.\n\nJust some text.\n"
        result = self._run_fix(qmd)
        assert result == qmd

    def test_index_qmd_skipped(self):
        """index.qmd files are not processed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_path = Path(tmp_dir) / "great-docs"
            ref_dir = project_path / "reference"
            ref_dir.mkdir(parents=True)

            index = ref_dir / "index.qmd"
            index.write_text(
                "========  =====\nA         B\n========  =====\n1         2\n========  =====\n"
            )

            config_path = project_path.parent / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=str(project_path.parent))
            docs.project_path = project_path
            docs._fix_rst_tables_in_qmd()

            # index.qmd should be unchanged
            assert "========" in index.read_text()

    def test_no_reference_dir(self):
        """No crash when reference/ directory does not exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "great-docs.yml"
            config_path.write_text("")

            docs = GreatDocs(project_path=tmp_dir)
            docs.project_path = Path(tmp_dir) / "great-docs"
            # Should not raise
            docs._fix_rst_tables_in_qmd()


# =========================================================================
# RST Table Conversion Unit Tests (module-level helpers)
# =========================================================================


class TestRstSimpleTableToMd:
    """Unit tests for _rst_simple_table_to_md."""

    def test_basic_three_column(self):
        from great_docs.core import _rst_simple_table_to_md

        lines = [
            "========  =========  ===========",
            "Method    Speed      Memory",
            "========  =========  ===========",
            "Quick     O(n log n) O(log n)",
            "Merge     O(n log n) O(n)",
            "Bubble    O(n^2)     O(1)",
            "========  =========  ===========",
        ]
        result = _rst_simple_table_to_md(lines)
        assert result is not None
        assert "| Method | Speed | Memory |" in result
        assert "| Quick | O(n log n) | O(log n) |" in result

    def test_two_column(self):
        from great_docs.core import _rst_simple_table_to_md

        lines = [
            "==========  =====",
            "Metric      Value",
            "==========  =====",
            "count       100",
            "mean        42.5",
            "std         12.3",
            "==========  =====",
        ]
        result = _rst_simple_table_to_md(lines)
        assert result is not None
        assert "| Metric | Value |" in result
        assert "| count | 100 |" in result
        assert "| std | 12.3 |" in result

    def test_insufficient_separators_returns_none(self):
        from great_docs.core import _rst_simple_table_to_md

        lines = [
            "========  =========",
            "Method    Speed",
        ]
        result = _rst_simple_table_to_md(lines)
        assert result is None


class TestRstGridTableToMd:
    """Unit tests for _rst_grid_table_to_md."""

    def test_basic_grid_table(self):
        from great_docs.core import _rst_grid_table_to_md

        lines = [
            "+--------+-------+",
            "| Name   | Value |",
            "+========+=======+",
            "| alpha  | 1     |",
            "| beta   | 2     |",
            "+--------+-------+",
        ]
        result = _rst_grid_table_to_md(lines)
        assert result is not None
        assert "| Name | Value |" in result
        assert "| alpha | 1 |" in result
        assert "| beta | 2 |" in result

    def test_no_header_separator(self):
        from great_docs.core import _rst_grid_table_to_md

        lines = [
            "+--------+-------+",
            "| Name   | Value |",
            "+--------+-------+",
            "| alpha  | 1     |",
            "+--------+-------+",
        ]
        result = _rst_grid_table_to_md(lines)
        assert result is not None
        assert "| Name | Value |" in result
        assert "| alpha | 1 |" in result

    def test_single_column_returns_none(self):
        from great_docs.core import _rst_grid_table_to_md

        lines = ["+--------+"]
        result = _rst_grid_table_to_md(lines)
        assert result is None


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
        assert "<table" in html, "Expected <table> element in compare_methods.html"
        assert "<thead>" in html, "Expected <thead> in table"
        assert "<th>Method</th>" in html
        assert "<th>Speed</th>" in html
        assert "<th>Memory</th>" in html
        # Body data
        assert "O(n log n)" in html
        assert "O(n^2)" in html
        assert "O(log n)" in html
        # Raw RST separators should NOT appear
        assert "========" not in html

    def test_format_report_has_table(self):
        """format_report reference page contains an HTML table with expected data."""
        html = self._read_html("reference", "format_report.html")
        assert "<table" in html, "Expected <table> element in format_report.html"
        assert "<thead>" in html, "Expected <thead> in table"
        assert "<th>Metric</th>" in html
        assert "<th>Value</th>" in html
        # Body data
        assert ">count<" in html
        assert ">100<" in html
        assert ">42.5<" in html
        # Raw RST separators should NOT appear
        assert "========" not in html
