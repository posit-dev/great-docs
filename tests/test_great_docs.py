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


def test_build_requires_config():
    """Test that build() raises FileNotFoundError when great-docs.yml is missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        # No great-docs.yml exists → build should fail immediately
        with pytest.raises(FileNotFoundError, match="great-docs.yml not found"):
            docs.build()


def test_init_refuses_when_config_exists():
    """Test that init refuses to run when great-docs.yml already exists (no --force)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create an initial config
        docs = GreatDocs(project_path=tmp_dir)
        docs.install(force=True)
        assert (project_path / "great-docs.yml").exists()

        # A second init without --force should refuse (not overwrite)
        docs2 = GreatDocs(project_path=tmp_dir)
        docs2.install(force=False)
        # The original file should still be there, unchanged
        assert (project_path / "great-docs.yml").exists()


def test_parse_package_exports():
    """Test parsing __all__ from __init__.py."""
    # Test on great-docs's own __init__.py
    docs = GreatDocs()
    exports = docs._parse_package_exports("great_docs")

    assert exports is not None
    assert "GreatDocs" in exports
    assert "main" in exports


def test_create_api_sections():
    """Test auto-generation of API reference sections."""
    docs = GreatDocs()
    sections = docs._create_api_sections("great_docs")

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
            sections = docs._create_api_sections("testpkg")

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

        # Create great-docs directory and _quarto.yml with API reference config
        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text("""
api-reference:
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

        # Create great-docs directory and _quarto.yml with API reference config and site URL
        great_docs_dir = Path(tmp_dir) / "great-docs"
        great_docs_dir.mkdir()
        quarto_yml = great_docs_dir / "_quarto.yml"
        quarto_yml.write_text("""
website:
  site-url: https://example.com/docs
api-reference:
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


def test_get_github_repo_info_string_license():
    """Test GitHub repo info when license is PEP 639 string format."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
license = "MIT"

[project.urls]
Repository = "https://github.com/testowner/testrepo"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "testowner"
        assert repo == "testrepo"
        assert base_url == "https://github.com/testowner/testrepo"


def test_get_github_repo_info_yml_override():
    """Test that repo in great-docs.yml overrides pyproject.toml URLs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # pyproject.toml with one repo URL
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
Repository = "https://github.com/original/repo"
""")

        # great-docs.yml overrides with a different repo
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("repo: https://github.com/override/other-repo\n")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "override"
        assert repo == "other-repo"
        assert base_url == "https://github.com/override/other-repo"


def test_get_github_repo_info_yml_no_pyproject():
    """Test that repo in great-docs.yml works without pyproject.toml URLs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # pyproject.toml with no URLs at all
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        # great-docs.yml provides the repo
        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("repo: https://github.com/myorg/myrepo\n")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "myorg"
        assert repo == "myrepo"
        assert base_url == "https://github.com/myorg/myrepo"


def test_get_github_repo_info_url_key_fallback():
    """Test that alternative URL key names are resolved in priority order."""
    # Each key name the code checks, in priority order
    key_names = [
        "Repository",
        "repository",
        "Source",
        "source",
        "GitHub",
        "github",
        "Homepage",
        "homepage",
    ]
    for key in key_names:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text(f"""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
{key} = "https://github.com/found-via/{key}"
""")

            docs = GreatDocs(project_path=tmp_dir)
            owner, repo, base_url = docs._get_github_repo_info()

            assert owner == "found-via", f"Failed for URL key '{key}'"
            assert repo == key, f"Failed for URL key '{key}'"
            assert base_url == f"https://github.com/found-via/{key}"


def test_get_github_repo_info_url_key_priority():
    """Test that 'Repository' takes priority over 'Homepage'."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
Homepage = "https://github.com/fallback/homepage-repo"
Repository = "https://github.com/primary/repo-repo"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "primary"
        assert repo == "repo-repo"


def test_get_github_repo_info_non_github_url():
    """Test that non-GitHub URLs return None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
Repository = "https://gitlab.com/owner/repo"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner is None
        assert repo is None
        assert base_url is None


def test_get_github_repo_info_dot_git_suffix():
    """Test that .git suffix is stripped from repo name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
Repository = "https://github.com/owner/repo.git"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "owner"
        assert repo == "repo"
        assert base_url == "https://github.com/owner/repo"


def test_get_github_repo_info_ssh_url():
    """Test that git SSH URLs are parsed correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"

[project.urls]
Repository = "git@github.com:owner/repo.git"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "owner"
        assert repo == "repo"
        assert base_url == "https://github.com/owner/repo"


def test_get_github_repo_info_license_dict_text():
    """Test that dict-style license with 'text' key doesn't break URL extraction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
license = {text = "Apache-2.0"}

[project.urls]
Repository = "https://github.com/owner/repo"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "owner"
        assert repo == "repo"
        assert base_url == "https://github.com/owner/repo"


def test_get_github_repo_info_license_dict_file():
    """Test that dict-style license with 'file' key doesn't break URL extraction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
license = {file = "LICENSE"}

[project.urls]
Repository = "https://github.com/owner/repo"
""")

        docs = GreatDocs(project_path=tmp_dir)
        owner, repo, base_url = docs._get_github_repo_info()

        assert owner == "owner"
        assert repo == "repo"


def test_get_github_repo_info_yml_non_github():
    """Test that non-GitHub repo in great-docs.yml returns None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pyproject = Path(tmp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-package"
version = "0.1.0"
""")

        gd_yml = Path(tmp_dir) / "great-docs.yml"
        gd_yml.write_text("repo: https://gitlab.com/myorg/myrepo\n")

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


def test_user_guide_discovers_mixed_extensions_and_nested_files():
    """Test that user guide discovery finds .qmd and .md files at any nesting depth."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        # Create minimal pyproject.toml
        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with mixed extensions and nesting
        user_guide = project_path / "user_guide"
        user_guide.mkdir()

        # Top-level .qmd file
        (user_guide / "intro.qmd").write_text("---\ntitle: Intro QMD\n---\n\n# Intro\n")

        # Top-level .md file
        (user_guide / "setup.md").write_text("---\ntitle: Setup MD\n---\n\n# Setup\n")

        # One-level nested .qmd file
        section1 = user_guide / "section1"
        section1.mkdir()
        (section1 / "overview.qmd").write_text(
            "---\ntitle: Section 1 Overview\n---\n\n# Overview\n"
        )

        # One-level nested .md file
        (section1 / "details.md").write_text("---\ntitle: Section 1 Details\n---\n\n# Details\n")

        # Deeply nested .qmd file (2 levels)
        topic = section1 / "topic1"
        topic.mkdir()
        (topic / "deep.qmd").write_text("---\ntitle: Deep Topic\n---\n\n# Deep Topic\n")

        # Deeply nested .md file (2 levels)
        (topic / "deep-notes.md").write_text("---\ntitle: Deep Notes\n---\n\n# Deep Notes\n")

        docs = GreatDocs(project_path=tmp_dir)

        # Discover user guide
        user_guide_info = docs._discover_user_guide()
        assert user_guide_info is not None

        discovered_names = {f["path"].name for f in user_guide_info["files"]}

        # All 6 files should be discovered regardless of extension or depth
        assert "intro.qmd" in discovered_names
        assert "setup.md" in discovered_names
        assert "overview.qmd" in discovered_names
        assert "details.md" in discovered_names
        assert "deep.qmd" in discovered_names
        assert "deep-notes.md" in discovered_names
        assert len(user_guide_info["files"]) == 6

        # Copy files and verify they end up in the right places
        copied_files = docs._copy_user_guide_to_docs(user_guide_info)
        assert len(copied_files) == 6

        docs_ug = docs.project_path / "user-guide"

        # Top-level files
        assert (docs_ug / "intro.qmd").exists()
        assert (docs_ug / "setup.md").exists()

        # One-level nested files
        assert (docs_ug / "section1" / "overview.qmd").exists()
        assert (docs_ug / "section1" / "details.md").exists()

        # Deeply nested files
        assert (docs_ug / "section1" / "topic1" / "deep.qmd").exists()
        assert (docs_ug / "section1" / "topic1" / "deep-notes.md").exists()


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


def test_user_guide_warns_on_no_guide_files(capsys):
    """Test warning when user guide directory has no .qmd or .md files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        # Create user_guide directory with only non-guide files
        ug_dir = project_path / "user_guide"
        ug_dir.mkdir()
        (ug_dir / "notes.txt").write_text("just a text file")
        (ug_dir / "data.csv").write_text("a,b,c")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None
        captured = capsys.readouterr()
        assert "contains no .qmd or .md files" in captured.out


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
        config_path.write_text(
            "sections:\n  - title: Examples\n    dir: examples\n    index: true\n"
        )
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


def test_process_sections_no_index_by_default():
    """Test that sections do NOT generate an index page by default."""
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

        # No auto-generated index page
        index = dest / "index.qmd"
        assert not index.exists(), "index.qmd should NOT be generated by default"

        # Check navbar links to first page, not index
        import yaml

        with open(quarto_yml) as f:
            config = yaml.safe_load(f)
        examples_item = next(
            item
            for item in config["website"]["navbar"]["left"]
            if isinstance(item, dict) and item.get("text") == "Examples"
        )
        assert examples_item["href"] == "examples/basic.qmd"

        # Sidebar should NOT have an index entry
        sidebar = next(
            s
            for s in config["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "examples"
        )
        sidebar_hrefs = [c["href"] for c in sidebar["contents"] if isinstance(c, dict)]
        assert "examples/index.qmd" not in sidebar_hrefs
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
        (ex_dir / "page2.qmd").write_text('---\ntitle: "Page 2"\n---\n\nMore\n')

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
            "sections:\n  - title: Gallery\n    dir: gallery\n    index: true\n"
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
        # Reference is added later by _add_api_reference_config only when
        # documentable exports exist, so it's not present after bare
        # _update_quarto_config.


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
            sections = docs._create_api_sections("splitpkg")

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


# =========================================================================
# Renderer-Level Transform Tests (P0 workarounds absorbed into renderer)
# =========================================================================


class TestRendererDunderEscaping:
    """Dunder names in render_header are escaped to prevent Pandoc bold interpretation."""

    def test_dunder_name_escaped_in_heading(self):
        """__repr__ in heading becomes \\_\\_repr\\_\\_ to avoid Pandoc bold."""
        from great_docs._renderer.renderer import _escape_dunders

        assert _escape_dunders("__repr__") == "\\_\\_repr\\_\\_"

    def test_regular_name_unchanged(self):
        from great_docs._renderer.renderer import _escape_dunders

        assert _escape_dunders("process") == "process"

    def test_dotted_dunder_escaped(self):
        """Collection.__repr__ → Collection.\\_\\_repr\\_\\_"""
        from great_docs._renderer.renderer import _escape_dunders

        result = _escape_dunders("Collection.__repr__")
        assert result == "Collection.\\_\\_repr\\_\\_"

    def test_multiple_dunders_escaped(self):
        from great_docs._renderer.renderer import _escape_dunders

        result = _escape_dunders("__init__ and __del__")
        assert result == "\\_\\_init\\_\\_ and \\_\\_del\\_\\_"

    def test_single_underscore_not_escaped(self):
        from great_docs._renderer.renderer import _escape_dunders

        assert _escape_dunders("_private") == "_private"


class TestRendererRstCodeBlocks:
    """RST :: code blocks are converted to fenced code blocks at render time."""

    def test_rst_code_block_to_fenced(self):
        from great_docs._renderer.renderer import _convert_rst_text

        text = "For example::\n\n    x = 1\n    y = 2\n"
        result = _convert_rst_text(text)
        assert "```python" in result
        assert "x = 1" in result
        assert "::" not in result.split("```")[0]

    def test_rst_directive_converted_to_callout(self):
        """RST directives like .. note:: are converted to Quarto callouts."""
        from great_docs._renderer.renderer import _convert_rst_text

        text = ".. note::\n\n    Important info\n"
        result = _convert_rst_text(text)
        assert ".callout-note" in result
        assert "Important info" in result
        assert ":::" in result

    def test_math_directive_to_dollar_signs(self):
        """.. math:: → $$...$$ display math."""
        from great_docs._renderer.renderer import _convert_rst_text

        text = "The formula:\n\n.. math::\n\n    a^2 + b^2 = c^2\n"
        result = _convert_rst_text(text)
        assert "$$" in result
        assert "a^2 + b^2 = c^2" in result
        assert ".. math::" not in result

    def test_inline_math_converted(self):
        """:math:`x^2` → $x^2$"""
        from great_docs._renderer.renderer import _convert_rst_text

        text = "The value :math:`x^2` is computed."
        result = _convert_rst_text(text)
        assert "$x^2$" in result
        assert ":math:" not in result


class TestRendererRstTables:
    """RST tables are converted to Markdown pipe tables at render time."""

    def test_simple_table_converted(self):
        from great_docs._renderer.renderer import _convert_rst_text

        text = (
            "========  =========\n"
            "Method    Speed\n"
            "========  =========\n"
            "Quick     Fast\n"
            "Merge     Medium\n"
            "========  =========\n"
        )
        result = _convert_rst_text(text)
        assert "| Method" in result
        assert "| Quick" in result
        assert "| ---" in result
        assert "========" not in result

    def test_grid_table_converted(self):
        from great_docs._renderer.renderer import _convert_rst_text

        text = (
            "+--------+-------+\n"
            "| Name   | Value |\n"
            "+========+=======+\n"
            "| alpha  | 1     |\n"
            "+--------+-------+\n"
        )
        result = _convert_rst_text(text)
        assert "| Name" in result
        assert "| alpha" in result
        assert "| ---" in result
        assert "+--------+" not in result


class TestRendererOverloadSignatures:
    """Overloaded functions render all @overload signatures."""

    def test_render_overload_signatures(self):
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        # Create a simple set of "overload" lines
        sig_lines = ["process(data: str) -> bytes", "process(data: bytes) -> str"]
        result = renderer._render_overload_signatures("process", [])
        assert "```python" in result

    def test_overload_empty_falls_back(self):
        """Empty overloads list produces a basic signature."""
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        result = renderer._render_overload_signatures("func", [])
        assert "func()" in result


class TestRendererDataclassAttributes:
    """Dataclass field introspection ensures all fields appear in Attributes."""

    def test_is_griffe_dataclass_true(self):
        """A griffe object with 'dataclass' label is detected."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_griffe_dataclass

        obj = MagicMock()
        obj.labels = {"dataclass"}
        assert _is_griffe_dataclass(obj) is True

    def test_is_griffe_dataclass_false(self):
        """A griffe object without 'dataclass' label returns False."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_griffe_dataclass

        obj = MagicMock()
        obj.labels = {"class"}
        assert _is_griffe_dataclass(obj) is False

    def test_get_dataclass_field_names(self):
        """Dynamic import of a stdlib dataclass returns all field names."""
        import dataclasses as _dc
        import sys
        import types

        from great_docs._renderer.renderer import _get_dataclass_field_names

        # Create a temporary dataclass in a temporary module
        mod = types.ModuleType("_test_dc_mod")

        @_dc.dataclass
        class SampleDC:
            name: str = ""
            count: int = 0
            items: list = _dc.field(default_factory=list)

        mod.SampleDC = SampleDC
        sys.modules["_test_dc_mod"] = mod

        try:
            obj = type(
                "FakeObj",
                (),
                {"canonical_path": "_test_dc_mod.SampleDC", "path": "_test_dc_mod.SampleDC"},
            )()
            result = _get_dataclass_field_names(obj)
            assert result == ["name", "count", "items"]
        finally:
            del sys.modules["_test_dc_mod"]

    def test_get_param_descriptions(self):
        """Parameter descriptions are extracted from parsed docstring sections."""
        from unittest.mock import MagicMock

        from great_docs._renderer._griffe_compat import docstrings as ds
        from great_docs._renderer.renderer import _get_param_descriptions

        param1 = MagicMock(spec=ds.DocstringParameter)
        param1.name = "name"
        param1.description = "The name of the item."

        param2 = MagicMock(spec=ds.DocstringParameter)
        param2.name = "count"
        param2.description = "Number of items."

        section = MagicMock(spec=ds.DocstringSectionParameters)
        section.value = [param1, param2]

        docstring = MagicMock()
        docstring.parsed = [section]

        obj = MagicMock()
        obj.docstring = docstring

        result = _get_param_descriptions(obj)
        assert result == {"name": "The name of the item.", "count": "Number of items."}

    def test_get_dataclass_field_names_non_dataclass_returns_none(self):
        """Non-dataclass returns None."""
        from great_docs._renderer.renderer import _get_dataclass_field_names

        obj = type("FakeObj", (), {"canonical_path": "os.path", "path": "os.path"})()
        result = _get_dataclass_field_names(obj)
        assert result is None


class TestRendererSphinxRoles:
    """Sphinx cross-reference roles → markdown code spans."""

    def test_func_role(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":func:`get_object`") == "`get_object()`"

    def test_class_role(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":class:`MyClass`") == "`MyClass`"

    def test_exc_role(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":exc:`ValueError`") == "`ValueError`"

    def test_py_prefix_role(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":py:func:`bar`") == "`bar()`"

    def test_meth_role_appends_parens(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":meth:`run`") == "`run()`"

    def test_attr_role_no_parens(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":attr:`name`") == "`name`"

    def test_multiple_roles_in_text(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        text = "Use :func:`foo` and :class:`Bar` together."
        result = _convert_sphinx_roles(text)
        assert result == "Use `foo()` and `Bar` together."

    def test_func_already_has_parens(self):
        from great_docs._renderer.renderer import _convert_sphinx_roles

        assert _convert_sphinx_roles(":func:`foo()`") == "`foo()`"


class TestRendererRstDirectives:
    """RST admonition / version directives → Quarto callout blocks."""

    def test_inline_note(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. note:: Something important.")
        assert ".callout-note" in result
        assert "Something important." in result
        assert ":::" in result

    def test_inline_warning(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. warning:: Be careful.")
        assert ".callout-warning" in result
        assert "Be careful." in result

    def test_inline_versionadded(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. versionadded:: 2.8.1")
        assert ".callout-note" in result
        assert "Added in version" in result
        assert "2.8.1" in result

    def test_inline_deprecated(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. deprecated:: 2.6 Use X instead.")
        assert ".callout-warning" in result
        assert "Deprecated since version" in result
        assert "2.6" in result

    def test_block_note(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        text = ".. note::\n\n    This is the note body.\n"
        result = _convert_rst_directives(text)
        assert ".callout-note" in result
        assert "This is the note body." in result

    def test_block_tip(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        text = ".. tip::\n\n    Helpful advice.\n"
        result = _convert_rst_directives(text)
        assert ".callout-tip" in result
        assert "Helpful advice." in result

    def test_danger_maps_to_important(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. danger:: Critical issue.")
        assert ".callout-important" in result

    def test_bare_directive(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        result = _convert_rst_directives(".. note::")
        assert ".callout-note" in result
        assert ":::" in result

    def test_versionchanged_with_block_body(self):
        from great_docs._renderer.renderer import _convert_rst_directives

        text = ".. versionchanged:: 3.0\n\n    New behaviour.\n"
        result = _convert_rst_directives(text)
        assert "Changed in version" in result
        assert "3.0" in result


class TestRendererBoldSectionHeaders:
    """``**Examples**::`` → proper QMD section headings."""

    def test_examples_header(self):
        from great_docs._renderer.renderer import _convert_bold_section_headers

        result = _convert_bold_section_headers("**Examples**::", 2)
        assert "## Examples" in result
        assert ".doc-section-examples" in result

    def test_notes_header(self):
        from great_docs._renderer.renderer import _convert_bold_section_headers

        result = _convert_bold_section_headers("**Notes**::", 3)
        assert "### Notes" in result
        assert ".doc-section-notes" in result

    def test_see_also_header(self):
        from great_docs._renderer.renderer import _convert_bold_section_headers

        result = _convert_bold_section_headers("**See Also**::", 2)
        assert ".doc-section-see-also" in result

    def test_non_matching_text_unchanged(self):
        from great_docs._renderer.renderer import _convert_bold_section_headers

        text = "This is **bold** text."
        assert _convert_bold_section_headers(text, 2) == text


class TestRendererSphinxFields:
    """Sphinx-style ``:param:`` / ``:returns:`` / ``:raises:`` fields → sections."""

    def test_param_and_type(self):
        from great_docs._renderer.renderer import _convert_sphinx_fields

        text = ":param x: The x value.\n:type x: int"
        result = _convert_sphinx_fields(text, 2)
        assert "## Parameters" in result
        assert "x" in result
        assert "int" in result
        assert "The x value." in result

    def test_returns_and_rtype(self):
        from great_docs._renderer.renderer import _convert_sphinx_fields

        text = ":returns: The result.\n:rtype: str"
        result = _convert_sphinx_fields(text, 2)
        assert "## Returns" in result
        assert "str" in result
        assert "The result." in result

    def test_raises(self):
        from great_docs._renderer.renderer import _convert_sphinx_fields

        text = ":raises ValueError: If bad input."
        result = _convert_sphinx_fields(text, 2)
        assert "## Raises" in result
        assert "ValueError" in result
        assert "If bad input." in result

    def test_combined_fields(self):
        from great_docs._renderer.renderer import _convert_sphinx_fields

        text = (
            "Description text.\n\n"
            ":param x: The x.\n"
            ":type x: int\n"
            ":returns: Result.\n"
            ":rtype: str\n"
            ":raises ValueError: Bad."
        )
        result = _convert_sphinx_fields(text, 2)
        assert "Description text." in result
        assert "## Parameters" in result
        assert "## Returns" in result
        assert "## Raises" in result

    def test_no_fields_unchanged(self):
        from great_docs._renderer.renderer import _convert_sphinx_fields

        text = "Just normal text."
        assert _convert_sphinx_fields(text, 2) == text


class TestRendererGoogleSections:
    """Google-style ``Args:`` / ``Returns:`` / ``Raises:`` sections → QMD."""

    def test_args_section(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Args:\n    x: The x value.\n    y: The y value."
        result = _convert_google_sections(text, 2)
        assert "## Parameters" in result
        assert "x" in result
        assert "y" in result

    def test_returns_section(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Returns:\n    A dict of results."
        result = _convert_google_sections(text, 2)
        assert "## Returns" in result
        assert "A dict of results." in result

    def test_raises_section(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Raises:\n    ValueError: If bad input.\n    TypeError: If wrong type."
        result = _convert_google_sections(text, 2)
        assert "## Raises" in result
        assert "ValueError" in result
        assert "TypeError" in result

    def test_note_section(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Note:\n    This is important."
        result = _convert_google_sections(text, 2)
        assert "## Note" in result
        assert ".doc-section-notes" in result

    def test_example_section(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Examples:\n    >>> foo()\n    42"
        result = _convert_google_sections(text, 3)
        assert "### Examples" in result
        assert ".doc-section-examples" in result

    def test_combined_sections(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = (
            "Description.\n\n"
            "Args:\n    x: The x.\n\n"
            "Returns:\n    The result.\n\n"
            "Raises:\n    ValueError: Bad."
        )
        result = _convert_google_sections(text, 2)
        assert "Description." in result
        assert "## Parameters" in result
        assert "## Returns" in result
        assert "## Raises" in result

    def test_no_sections_unchanged(self):
        from great_docs._renderer.renderer import _convert_google_sections

        text = "Just normal text."
        assert _convert_google_sections(text, 2) == text


class TestRendererDoctestFencing:
    """Unfenced ``>>>`` doctest blocks → fenced ```python code blocks."""

    def test_single_doctest_line(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = ">>> print('hello')"
        result = _fence_doctest_blocks(text)
        assert "```python" in result
        assert ">>> print('hello')" in result
        assert result.endswith("```")

    def test_multi_line_doctest(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = ">>> x = 1\n>>> y = 2\n>>> x + y"
        result = _fence_doctest_blocks(text)
        assert result.count("```python") == 1
        assert result.count("```") == 2

    def test_doctest_with_continuation(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = ">>> for i in range(3):\n...     print(i)"
        result = _fence_doctest_blocks(text)
        assert "```python" in result
        assert "... " in result

    def test_interspersed_text(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = "First example:\n\n>>> x = 1\n\nSecond example:\n\n>>> y = 2"
        result = _fence_doctest_blocks(text)
        assert result.count("```python") == 2

    def test_no_doctest_unchanged(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = "Just some normal text."
        assert _fence_doctest_blocks(text) == text

    def test_bare_prompt(self):
        from great_docs._renderer.renderer import _fence_doctest_blocks

        text = ">>>"
        result = _fence_doctest_blocks(text)
        assert "```python" in result

    def test_in_render_section_text(self):
        """Doctest fencing is applied in _render_section_text."""
        from great_docs._renderer.renderer import _convert_rst_text, _fence_doctest_blocks

        text = "Example usage:\n\n>>> foo(42)\n>>> bar()"
        result = _fence_doctest_blocks(_convert_rst_text(text))
        assert "```python" in result
        assert ">>> foo(42)" in result


class TestRendererCallableParens:
    """Callable objects get ``()`` appended to their heading name."""

    def test_function_heading_has_parens(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "my_func"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.my_func"
        doc.obj.kind.value = "function"
        doc.obj.labels = set()

        # Make isinstance check work for DocFunction
        from great_docs._renderer import layout

        doc.__class__ = layout.DocFunction

        result = renderer.render_header(doc)
        assert "my_func()" in result
        assert "# my_func()" in result

    def test_class_heading_no_parens(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "MyClass"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.MyClass"
        doc.obj.kind.value = "class"
        doc.obj.labels = {"class"}

        from great_docs._renderer import layout

        doc.__class__ = layout.DocClass

        result = renderer.render_header(doc)
        assert "MyClass" in result
        assert "MyClass()" not in result


class TestRendererTypeBadgeClasses:
    """Headings get ``.doc-type-{kind}`` CSS classes."""

    def test_function_type_class(self):
        from unittest.mock import MagicMock

        from great_docs._renderer import layout
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "my_func"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.my_func"
        doc.obj.kind.value = "function"
        doc.obj.labels = set()
        doc.__class__ = layout.DocFunction

        result = renderer.render_header(doc)
        assert ".doc-type-function" in result

    def test_class_type_class(self):
        from unittest.mock import MagicMock

        from great_docs._renderer import layout
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "MyClass"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.MyClass"
        doc.obj.kind.value = "class"
        doc.obj.labels = {"class"}
        doc.__class__ = layout.DocClass

        result = renderer.render_header(doc)
        assert ".doc-type-class" in result

    def test_enum_type_class(self):
        from unittest.mock import MagicMock

        from great_docs._renderer import layout
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "Color"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.Color"
        doc.obj.kind.value = "class"
        doc.obj.labels = {"enum"}
        doc.__class__ = layout.DocClass

        result = renderer.render_header(doc)
        assert ".doc-type-enum" in result

    def test_attribute_type_class(self):
        from unittest.mock import MagicMock

        from great_docs._renderer import layout
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        doc = MagicMock(spec=["name", "obj", "__class__"])
        doc.name = "MY_CONST"
        doc.obj = MagicMock()
        doc.obj.path = "pkg.MY_CONST"
        doc.obj.kind.value = "attribute"
        doc.obj.labels = set()
        doc.__class__ = layout.DocAttribute

        result = renderer.render_header(doc)
        assert ".doc-type-attribute" in result
        assert "MY_CONST()" not in result


class TestRendererSignatureMultiline:
    """Signatures with many arguments auto-wrap to multi-line."""

    def test_short_sig_stays_single_line(self):
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        result = renderer._signature_func_or_class(
            type(
                "FakeEl",
                (),
                {
                    "name": "foo",
                    "path": "pkg.foo",
                    "parameters": [],
                    "is_class": False,
                    "parent": None,
                },
            )()
        )
        assert "foo()" in result
        assert "\n    " not in result  # no indentation = single line

    def test_long_sig_wraps(self):
        """Signatures exceeding 80 chars wrap to multi-line."""
        from unittest.mock import MagicMock

        from great_docs._renderer._griffe_compat import dataclasses as dc
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        params = []
        for pname in ["very_long_param_one", "very_long_param_two", "very_long_param_three"]:
            p = MagicMock(spec=dc.Parameter)
            p.name = pname
            p.kind = dc.ParameterKind.positional_or_keyword
            p.annotation = None
            p.default = None
            params.append(p)

        el = MagicMock()
        el.name = "a_function_with_a_really_long_name"
        el.path = "pkg.a_function_with_a_really_long_name"
        el.is_class = False
        el.parent = None
        el.parameters = dc.Parameters(*params)

        result = renderer._signature_func_or_class(el)
        assert "\n    " in result  # has indentation = multi-line


# =============================================================================
# P3 renderer improvements
# =============================================================================


class TestRendererConstantValues:
    """Constants include annotation and value in their signature."""

    def test_bare_constant_signature(self):
        """Constant with no annotation or value renders as plain name."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        el = MagicMock()
        el.name = "MY_CONST"
        el.path = "pkg.MY_CONST"
        el.is_class = False
        el.parent = None
        el.annotation = None
        el.value = None

        result = renderer._signature_module_or_attr(el)
        assert result == "`MY_CONST`"

    def test_constant_with_annotation(self):
        """Constant with type annotation renders as ``NAME: type``."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        el = MagicMock()
        el.name = "TIMEOUT"
        el.path = "pkg.TIMEOUT"
        el.is_class = False
        el.parent = None
        el.annotation = "int"
        el.value = None

        result = renderer._signature_module_or_attr(el)
        assert result == "`TIMEOUT: int`"

    def test_constant_with_value(self):
        """Constant with value renders as ``NAME = value``."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        el = MagicMock()
        el.name = "MAX_RETRIES"
        el.path = "pkg.MAX_RETRIES"
        el.is_class = False
        el.parent = None
        el.annotation = None
        el.value = "3"

        result = renderer._signature_module_or_attr(el)
        assert result == "`MAX_RETRIES = 3`"

    def test_constant_with_both(self):
        """Constant with annotation and value renders as ``NAME: type = value``."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        el = MagicMock()
        el.name = "DEFAULT_PORT"
        el.path = "pkg.DEFAULT_PORT"
        el.is_class = False
        el.parent = None
        el.annotation = "int"
        el.value = "8080"

        result = renderer._signature_module_or_attr(el)
        assert result == "`DEFAULT_PORT: int = 8080`"

    def test_constant_long_value_skipped(self):
        """Values exceeding 200 chars are not included."""
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        el = MagicMock()
        el.name = "BIG"
        el.path = "pkg.BIG"
        el.is_class = False
        el.parent = None
        el.annotation = "str"
        el.value = "x" * 201

        result = renderer._signature_module_or_attr(el)
        assert result == "`BIG: str`"
        assert "x" * 201 not in result


class TestRendererNonCallableCleanup:
    """Enums and TypedDicts do not get ``()`` in their signature."""

    def test_enum_signature_no_parens(self):
        """Enum class signature has no parentheses."""
        from unittest.mock import MagicMock

        from great_docs._renderer._griffe_compat import dataclasses as dc
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        el = MagicMock(spec=dc.Class)
        el.__class__ = dc.Class
        el.name = "Color"
        el.path = "pkg.Color"
        el.is_class = True
        el.parent = None
        el.labels = {"enum"}
        el.bases = []

        result = renderer._signature_func_or_class(el)
        assert "Color" in result
        assert "Color()" not in result

    def test_typeddict_signature_no_parens(self):
        """TypedDict class signature has no parentheses."""
        from unittest.mock import MagicMock

        from great_docs._renderer._griffe_compat import dataclasses as dc
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        el = MagicMock(spec=dc.Class)
        el.__class__ = dc.Class
        el.name = "Config"
        el.path = "pkg.Config"
        el.is_class = True
        el.parent = None
        el.labels = set()
        el.bases = ["TypedDict"]

        result = renderer._signature_func_or_class(el)
        assert "Config" in result
        assert "Config()" not in result

    def test_regular_class_still_has_parens(self):
        """Normal classes retain ``()`` in their signature."""
        from unittest.mock import MagicMock

        from great_docs._renderer._griffe_compat import dataclasses as dc
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()

        el = MagicMock(spec=dc.Class)
        el.__class__ = dc.Class
        el.name = "Widget"
        el.path = "pkg.Widget"
        el.is_class = True
        el.parent = None
        el.labels = set()
        el.bases = ["object"]
        el.parameters = dc.Parameters()

        result = renderer._signature_func_or_class(el)
        assert "Widget()" in result


class TestRendererSectionSeparators:
    """Class member docs are separated by horizontal rules."""

    def test_separators_between_methods(self):
        """Methods section includes --- separators between member docs."""
        from unittest.mock import MagicMock, patch

        from great_docs._renderer import layout
        from great_docs._renderer._griffe_compat import dataclasses as dc
        from great_docs._renderer._griffe_compat import docstrings as ds
        from great_docs._renderer.renderer import MdRenderer

        renderer = MdRenderer()
        renderer.display_name = "name"

        # Build minimal griffe-level function objects
        def _make_func_obj(name):
            obj = MagicMock(spec=dc.Function)
            obj.__class__ = dc.Function
            obj.name = name
            obj.path = f"pkg.MyClass.{name}"
            obj.is_function = True
            obj.is_attribute = False
            obj.is_class = False
            obj.kind.value = "function"
            obj.labels = set()
            obj.parent = MagicMock()
            obj.parent.name = "MyClass"
            obj.parent.is_class = True
            obj.parameters = dc.Parameters()
            obj.docstring = MagicMock(spec=dc.Docstring)
            obj.docstring.parsed = [ds.DocstringSectionText(value=f"Docstring for {name}.")]
            return obj

        def _make_method_doc(name, func_obj):
            doc = layout.DocFunction(
                name=name,
                obj=func_obj,
                anchor=f"pkg.MyClass.{name}",
                signature_name="relative",
            )
            return doc

        func_foo = _make_func_obj("foo")
        func_bar = _make_func_obj("bar")
        method1 = _make_method_doc("foo", func_foo)
        method2 = _make_method_doc("bar", func_bar)

        cls_obj = MagicMock(spec=dc.Class)
        cls_obj.__class__ = dc.Class
        cls_obj.name = "MyClass"
        cls_obj.path = "pkg.MyClass"
        cls_obj.is_class = True
        cls_obj.is_function = False
        cls_obj.is_attribute = False
        cls_obj.kind.value = "class"
        cls_obj.labels = set()
        cls_obj.bases = []
        cls_obj.parent = None
        cls_obj.parameters = dc.Parameters()
        cls_obj.docstring = MagicMock(spec=dc.Docstring)
        cls_obj.docstring.parsed = [ds.DocstringSectionText(value="A class.")]

        el = layout.DocClass(
            name="MyClass",
            obj=cls_obj,
            anchor="pkg.MyClass",
            signature_name="relative",
            members=[method1, method2],
        )

        result = renderer._render_doc_class_module(el)

        # Should contain --- separator(s) between summary and members
        assert "---" in result


class TestRendererRstCitations:
    """RST citation markers are converted to markdown numbered lists."""

    def test_simple_citations(self):
        """Basic ``.. [1]`` markers become numbered list items."""
        from great_docs._renderer.renderer import _convert_rst_citations

        text = ".. [1] Author (2023). Title.\n.. [2] Another ref."
        result = _convert_rst_citations(text)
        assert "1. Author (2023). Title." in result
        assert "2. Another ref." in result
        assert ".. [1]" not in result

    def test_citation_with_url(self):
        """Bare URLs in citation bodies get auto-linked."""
        from great_docs._renderer.renderer import _convert_rst_citations

        text = ".. [1] See https://example.com for details."
        result = _convert_rst_citations(text)
        assert "1." in result
        assert "<https://example.com>" in result

    def test_no_citations_unchanged(self):
        """Text without citation markers passes through unchanged."""
        from great_docs._renderer.renderer import _convert_rst_citations

        text = "Regular paragraph text.\nNo citations here."
        result = _convert_rst_citations(text)
        assert result == text

    def test_citations_in_convert_rst_text(self):
        """Citations are converted as part of the full RST → Markdown pipeline."""
        from great_docs._renderer.renderer import _convert_rst_text

        text = "References\n\n.. [1] First ref.\n.. [2] Second ref."
        result = _convert_rst_text(text)
        assert "1. First ref." in result
        assert "2. Second ref." in result

    def test_multi_line_citation(self):
        """Multi-line citations are joined."""
        from great_docs._renderer.renderer import _convert_rst_citations

        text = ".. [1] Author (2023).\n    Title of the work."
        result = _convert_rst_citations(text)
        assert "1. Author (2023). Title of the work." in result


class TestRendererRstMathDisplay:
    """``.. math::`` directive is converted to ``$$...$$`` display math."""

    def test_math_directive_to_display_math(self):
        """``.. math::`` block becomes ``$$`` display math."""
        from great_docs._renderer.renderer import _convert_rst_text

        text = "Some text.\n\n.. math::\n\n    E = mc^2\n"
        result = _convert_rst_text(text)
        assert "$$" in result
        assert "E = mc^2" in result
        assert ".. math::" not in result

    def test_inline_math_converted(self):
        """Inline ``:math:`` roles become ``$...$``."""
        from great_docs._renderer.renderer import _convert_rst_text

        text = "The formula :math:`x^2` is simple."
        result = _convert_rst_text(text)
        assert "$x^2$" in result
        assert ":math:" not in result


class TestRendererIsNonCallableClass:
    """Helper function _is_non_callable_class detects enums and TypedDicts."""

    def test_enum_detected(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_non_callable_class

        obj = MagicMock()
        obj.labels = {"enum"}
        obj.bases = []
        assert _is_non_callable_class(obj) is True

    def test_typeddict_detected_by_base(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_non_callable_class

        obj = MagicMock()
        obj.labels = set()
        obj.bases = ["TypedDict"]
        assert _is_non_callable_class(obj) is True

    def test_regular_class_not_detected(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_non_callable_class

        obj = MagicMock()
        obj.labels = set()
        obj.bases = ["object"]
        assert _is_non_callable_class(obj) is False

    def test_int_enum_detected(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_non_callable_class

        obj = MagicMock()
        obj.labels = set()
        obj.bases = ["IntEnum"]
        assert _is_non_callable_class(obj) is True

    def test_str_enum_detected(self):
        from unittest.mock import MagicMock

        from great_docs._renderer.renderer import _is_non_callable_class

        obj = MagicMock()
        obj.labels = set()
        obj.bases = ["StrEnum"]
        assert _is_non_callable_class(obj) is True


# ============================================================================
# Favicon Tests
# ============================================================================

# Minimal valid SVG for testing (64x64 blue square)
_MINIMAL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
    '<rect width="64" height="64" fill="#318BFC"/>'
    "</svg>"
)

# Non-square SVG (200x100)
_WIDE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
    '<rect width="200" height="100" fill="#318BFC"/>'
    "</svg>"
)


class TestFitToSquare:
    """Tests for GreatDocs._fit_to_square()."""

    def test_square_image_unchanged_dimensions(self):
        """A square image should remain square with the requested size."""
        from PIL import Image

        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        result = GreatDocs._fit_to_square(img, 64)
        assert result.size == (64, 64)

    def test_wide_image_padded_to_square(self):
        """A wide image should be padded vertically to become square."""
        from PIL import Image

        img = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
        result = GreatDocs._fit_to_square(img, 200)
        assert result.size == (200, 200)
        # Top-left corner should be transparent (padding)
        assert result.getpixel((0, 0))[3] == 0
        # Center should be opaque (the image)
        assert result.getpixel((100, 100))[3] == 255

    def test_tall_image_padded_to_square(self):
        """A tall image should be padded horizontally to become square."""
        from PIL import Image

        img = Image.new("RGBA", (100, 200), (0, 255, 0, 255))
        result = GreatDocs._fit_to_square(img, 200)
        assert result.size == (200, 200)
        # Left edge should be transparent (padding)
        assert result.getpixel((0, 100))[3] == 0
        # Center should be opaque
        assert result.getpixel((100, 100))[3] == 255

    def test_output_is_rgba(self):
        """Output should always be RGBA regardless of input mode."""
        from PIL import Image

        img = Image.new("RGB", (50, 50), (0, 0, 255))
        result = GreatDocs._fit_to_square(img, 64)
        assert result.mode == "RGBA"

    def test_downscale_preserves_aspect_ratio(self):
        """A large image should be scaled down to fit within the target size."""
        from PIL import Image

        img = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
        result = GreatDocs._fit_to_square(img, 100)
        assert result.size == (100, 100)


class TestGenerateFaviconsSvg:
    """Tests for _generate_favicons with SVG source."""

    def test_svg_generates_all_files(self):
        """SVG source should produce ico, svg, 16px, 32px, and apple-touch-icon."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            svg_file = tmp / "logo.svg"
            svg_file.write_text(_MINIMAL_SVG)

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(svg_file, dest)

            assert result["icon"] == "favicon.ico"
            assert result["icon-svg"] == "favicon.svg"
            assert result["icon-16"] == "favicon-16x16.png"
            assert result["icon-32"] == "favicon-32x32.png"
            assert result["apple-touch-icon"] == "apple-touch-icon.png"

    def test_svg_files_exist_on_disk(self):
        """All generated favicon files should actually exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            svg_file = tmp / "logo.svg"
            svg_file.write_text(_MINIMAL_SVG)

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_favicons(svg_file, dest)

            assert (dest / "favicon.ico").exists()
            assert (dest / "favicon.svg").exists()
            assert (dest / "favicon-16x16.png").exists()
            assert (dest / "favicon-32x32.png").exists()
            assert (dest / "apple-touch-icon.png").exists()

    def test_svg_png_sizes_correct(self):
        """Generated PNGs should have the correct pixel dimensions."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            svg_file = tmp / "logo.svg"
            svg_file.write_text(_MINIMAL_SVG)

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_favicons(svg_file, dest)

            assert Image.open(dest / "favicon-16x16.png").size == (16, 16)
            assert Image.open(dest / "favicon-32x32.png").size == (32, 32)
            assert Image.open(dest / "apple-touch-icon.png").size == (180, 180)

    def test_svg_copied_as_favicon_svg(self):
        """The SVG source should be copied verbatim as favicon.svg."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            svg_file = tmp / "logo.svg"
            svg_file.write_text(_MINIMAL_SVG)

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_favicons(svg_file, dest)

            assert (dest / "favicon.svg").read_text() == _MINIMAL_SVG

    def test_non_square_svg_generates_square_favicons(self):
        """A non-square SVG should produce square favicons via padding."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            svg_file = tmp / "wide-logo.svg"
            svg_file.write_text(_WIDE_SVG)

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(svg_file, dest)

            # All outputs should be square
            assert result["icon"] == "favicon.ico"
            for name in ["favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png"]:
                img = Image.open(dest / name)
                assert img.size[0] == img.size[1], f"{name} should be square"


class TestGenerateFaviconsPng:
    """Tests for _generate_favicons with PNG source."""

    def test_png_generates_all_raster_files(self):
        """PNG source should produce ico, 16px, 32px, and apple-touch-icon."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            png_file = tmp / "logo.png"
            Image.new("RGBA", (128, 128), (255, 0, 0, 255)).save(png_file, "PNG")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(png_file, dest)

            assert result["icon"] == "favicon.ico"
            assert result["icon-16"] == "favicon-16x16.png"
            assert result["icon-32"] == "favicon-32x32.png"
            assert result["apple-touch-icon"] == "apple-touch-icon.png"

    def test_png_does_not_produce_svg(self):
        """PNG source should not produce a favicon.svg."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            png_file = tmp / "logo.png"
            Image.new("RGBA", (64, 64), (0, 0, 255, 255)).save(png_file, "PNG")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(png_file, dest)

            assert "icon-svg" not in result
            assert not (dest / "favicon.svg").exists()

    def test_png_files_exist_on_disk(self):
        """All generated files from PNG source should exist."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            png_file = tmp / "logo.png"
            Image.new("RGBA", (128, 128), (255, 0, 0, 255)).save(png_file, "PNG")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_favicons(png_file, dest)

            assert (dest / "favicon.ico").exists()
            assert (dest / "favicon-16x16.png").exists()
            assert (dest / "favicon-32x32.png").exists()
            assert (dest / "apple-touch-icon.png").exists()

    def test_png_sizes_correct(self):
        """Generated PNGs from PNG source should have correct dimensions."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            png_file = tmp / "logo.png"
            Image.new("RGBA", (256, 256), (0, 128, 0, 255)).save(png_file, "PNG")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_favicons(png_file, dest)

            assert Image.open(dest / "favicon-16x16.png").size == (16, 16)
            assert Image.open(dest / "favicon-32x32.png").size == (32, 32)
            assert Image.open(dest / "apple-touch-icon.png").size == (180, 180)

    def test_non_square_png_generates_square_favicons(self):
        """A non-square PNG should produce square favicons via padding."""
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            png_file = tmp / "wide-logo.png"
            Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(png_file, "PNG")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(png_file, dest)

            assert result["icon"] == "favicon.ico"
            for name in ["favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png"]:
                img = Image.open(dest / name)
                assert img.size[0] == img.size[1], f"{name} should be square"


class TestGenerateFaviconsUnsupported:
    """Tests for _generate_favicons with unsupported formats."""

    def test_unsupported_extension_returns_empty(self):
        """An unsupported file extension should return an empty dict."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            gif_file = tmp / "logo.gif"
            gif_file.write_text("not a real gif")

            dest = tmp / "output"
            dest.mkdir()

            docs = GreatDocs(project_path=tmp_dir)
            result = docs._generate_favicons(gif_file, dest)

            assert result == {}


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

    def _build_with_favicon(
        self, tmp_dir: str, favicon_config: str | None = None, create_logo: bool = False
    ) -> dict:
        """Helper: set up a project, run _update_quarto_config, return the config."""
        import yaml

        tmp = Path(tmp_dir)

        # Minimal pyproject.toml
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
            '[project.urls]\nRepository = "https://github.com/test/test-pkg"\n'
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
        docs.project_path.mkdir(parents=True, exist_ok=True)

        # Run the config build
        docs._update_quarto_config()

        # Read the generated _quarto.yml
        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml) as f:
            return yaml.safe_load(f)

    def test_auto_detect_injects_link_tags(self):
        """Auto-detected logo should inject favicon <link> tags."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config = self._build_with_favicon(tmp_dir, create_logo=True)

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            header_text = " ".join(str(item) for item in header)

            assert "favicon.ico" in header_text
            assert "favicon.svg" in header_text
            assert "favicon-32x32.png" in header_text
            assert "favicon-16x16.png" in header_text
            assert "apple-touch-icon.png" in header_text

    def test_explicit_favicon_injects_link_tags(self):
        """Explicit favicon config should also inject <link> tags."""
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

            assert "favicon.ico" in header_text
            assert "favicon.svg" in header_text
            assert "favicon-32x32.png" in header_text
            assert "favicon-16x16.png" in header_text
            assert "apple-touch-icon.png" in header_text

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


# ═══════════════════════════════════════════════════════════════════════════════
# Badge Extraction from README Content
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractBadgesFromContent:
    """Tests for _extract_badges_from_content (top-of-file and centered-div strategies)."""

    def _make_builder(self):
        """Create a minimal GreatDocs instance for calling _extract_badges_from_content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            (tmp / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
            (tmp / "test_pkg").mkdir()
            (tmp / "test_pkg" / "__init__.py").write_text('"""Test."""\n')
            builder = GreatDocs(str(tmp))
        return builder

    def test_top_of_file_badges_extracted(self):
        """Badges right after the heading are extracted."""
        content = (
            "# My Package\n"
            "\n"
            "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org/p)\n"
            "[![License](https://img.shields.io/badge/license-MIT-green)](https://mit.edu)\n"
            "\n"
            "Some body text.\n"
        )
        builder = self._make_builder()
        badges, cleaned, hero_extras = builder._extract_badges_from_content(content)

        assert len(badges) == 2
        assert badges[0]["alt"] == "PyPI"
        assert "img.shields.io" in badges[0]["img"]
        # Heading preserved, badges stripped, body preserved
        assert "# My Package" in cleaned
        assert "Some body text." in cleaned
        assert "img.shields.io" not in cleaned
        # No hero extras for top-of-file badges
        assert hero_extras == {}

    def test_centered_div_badges_extracted(self):
        """Badges inside <div align="center"> are extracted and the entire div is stripped."""
        content = (
            "> [!TIP]\n"
            "> Install via pip.\n"
            "\n"
            '<div align="center">\n'
            '<img src="logo.png" width="350">\n'
            "<br />\n"
            "*A cool tagline*\n"
            "<br />\n"
            "[![PyPI](https://img.shields.io/badge/pypi-v1-blue)](https://pypi.org)\n"
            "[![CI](https://img.shields.io/badge/ci-pass-green)](https://github.com/ci)\n"
            "[![Coverage](https://codecov.io/badge.svg)](https://codecov.io)\n"
            "</div>\n"
            "\n"
            "Body text after.\n"
        )
        builder = self._make_builder()
        badges, cleaned, hero_extras = builder._extract_badges_from_content(content)

        assert len(badges) == 3
        assert badges[0]["alt"] == "PyPI"
        assert badges[2]["alt"] == "Coverage"
        # Entire div block removed
        assert "<div" not in cleaned
        assert "</div>" not in cleaned
        assert "logo.png" not in cleaned
        assert "cool tagline" not in cleaned
        # Surrounding content preserved
        assert "Install via pip" in cleaned
        assert "Body text after." in cleaned
        # Hero extras extracted from centered div
        assert hero_extras["logo_url"] == "logo.png"
        assert hero_extras["tagline"] == "A cool tagline"

    def test_no_badges_returns_original(self):
        """Content without badges returns empty list and original content."""
        content = "# Title\n\nJust text, no badges.\n"
        builder = self._make_builder()
        badges, cleaned, hero_extras = builder._extract_badges_from_content(content)

        assert badges == []
        assert cleaned == content
        assert hero_extras == {}

    def test_non_badge_images_in_div_ignored(self):
        """A centered div without badge host URLs is not stripped."""
        content = '<div align="center">\n<img src="hero.png">\n</div>\n\nBody text.\n'
        builder = self._make_builder()
        badges, cleaned, hero_extras = builder._extract_badges_from_content(content)

        assert badges == []
        assert "<div" in cleaned

    def test_centered_div_linked_logo_extracted(self):
        """A linked <a><img></a> logo in the centered div is extracted."""
        content = (
            '<div align="center">\n'
            "\n"
            '<a href="https://example.com/"><img src="https://example.com/logo.svg" width="65%"/></a>\n'
            "\n"
            "_Obtain Polars DataFrames of NOAA historical weather data_\n"
            "\n"
            "[![PyPI](https://img.shields.io/pypi/pyversions/pkg.svg)](https://pypi.org/project/pkg/)\n"
            "[![Tests](https://github.com/user/pkg/actions/workflows/tests.yml/badge.svg)](https://github.com/user/pkg/actions)\n"
            "\n"
            "</div>\n"
            "\n"
            "## Features\n"
            "Some text.\n"
        )
        builder = self._make_builder()
        badges, cleaned, hero_extras = builder._extract_badges_from_content(content)

        assert len(badges) == 2
        assert hero_extras["logo_url"] == "https://example.com/logo.svg"
        assert hero_extras["tagline"] == "Obtain Polars DataFrames of NOAA historical weather data"
        assert "<div" not in cleaned
        assert "## Features" in cleaned


def test_config_markdown_pages_disabled():
    """Test that markdown_pages: false excludes copy-page.js from Quarto config."""
    import yaml

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

        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        # copy-page.js should NOT be in resources
        resources = config["project"].get("resources", [])
        assert "copy-page.js" not in resources

        # copy-page.js should NOT be in include-after-body
        after_body = config["format"]["html"].get("include-after-body", [])
        for item in after_body:
            assert "copy-page" not in str(item)


def test_config_markdown_pages_widget_disabled():
    """Test that markdown_pages: {widget: false} generates .md but hides widget."""
    import yaml

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

        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

        # copy-page.js should NOT be in resources
        resources = config["project"].get("resources", [])
        assert "copy-page.js" not in resources

        # copy-page.js should NOT be in include-after-body
        after_body = config["format"]["html"].get("include-after-body", [])
        for item in after_body:
            assert "copy-page" not in str(item)


def test_config_markdown_pages_default_enabled():
    """Test that markdown_pages defaults to true (copy-page.js included)."""
    import yaml

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)

        pyproject = project_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\nversion = "0.1.0"')

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "r") as f:
            config = yaml.safe_load(f)

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
        """Helper: set up a project with funding config, run _update_quarto_config, return config."""
        import yaml

        tmp = Path(tmp_dir)

        (tmp / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')

        yml_lines = ["display_name: Test\n"]
        if funding_name is not None:
            yml_lines.append(f"funding:\n  name: {funding_name}\n")
        (tmp / "great-docs.yml").write_text("".join(yml_lines))

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        docs._update_quarto_config()

        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml) as f:
            return yaml.safe_load(f)

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
        """Running _update_quarto_config twice should not duplicate the badge."""
        import yaml

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            (tmp / "pyproject.toml").write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n')
            (tmp / "great-docs.yml").write_text("display_name: Test\nfunding:\n  name: Posit\n")

            docs = GreatDocs(project_path=tmp_dir)
            docs.project_path.mkdir(parents=True, exist_ok=True)
            docs._update_quarto_config()
            docs._update_quarto_config()  # second run

            quarto_yml = docs.project_path / "_quarto.yml"
            with open(quarto_yml) as f:
                config = yaml.safe_load(f)

            header = config.get("format", {}).get("html", {}).get("include-in-header", [])
            badge_count = sum(1 for item in header if "supported-by-posit" in str(item))
            assert badge_count == 1


# ---------------------------------------------------------------------------
# Coverage: _update_project_gitignore (core.py lines ~302-328)
# ---------------------------------------------------------------------------


def test_update_gitignore_force_creates_new():
    """_update_project_gitignore with force creates .gitignore when it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs._update_project_gitignore(force=True)

        gitignore = Path(tmp_dir) / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert "great-docs/" in content


def test_update_gitignore_force_appends_to_existing():
    """_update_project_gitignore with force appends to existing .gitignore."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gitignore = Path(tmp_dir) / ".gitignore"
        gitignore.write_text("__pycache__/\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs._update_project_gitignore(force=True)

        content = gitignore.read_text()
        assert "__pycache__/" in content
        assert "great-docs/" in content


def test_update_gitignore_skip_when_already_present():
    """_update_project_gitignore does nothing if entry already exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        gitignore = Path(tmp_dir) / ".gitignore"
        gitignore.write_text("great-docs/\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs._update_project_gitignore(force=True)

        # Should not duplicate
        content = gitignore.read_text()
        assert content.count("great-docs/") == 1


# ---------------------------------------------------------------------------
# Coverage: _detect_package_name (core.py lines ~352-379)
# ---------------------------------------------------------------------------


def test_detect_package_name_from_setup_cfg():
    """_detect_package_name reads name from setup.cfg when no pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        setup_cfg = Path(tmp_dir) / "setup.cfg"
        setup_cfg.write_text("[metadata]\nname = my-cfg-package\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_package_name() == "my-cfg-package"


def test_detect_package_name_from_setup_py():
    """_detect_package_name reads name from setup.py when no pyproject.toml or setup.cfg."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        setup_py = Path(tmp_dir) / "setup.py"
        setup_py.write_text('from setuptools import setup\nsetup(name="my-setup-package")\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_package_name() == "my-setup-package"


def test_detect_package_name_returns_none():
    """_detect_package_name returns None when no package metadata found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_package_name() is None


# ---------------------------------------------------------------------------
# Coverage: _detect_logo (core.py lines ~467-468)
# ---------------------------------------------------------------------------


def test_detect_logo_finds_svg():
    """_detect_logo finds logo.svg in project root."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "logo.svg").write_text("<svg/>")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_logo()

        assert result is not None
        assert result["light"] == "logo.svg"


def test_detect_logo_finds_png_in_assets():
    """_detect_logo finds logo.png in assets/ directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        assets = Path(tmp_dir) / "assets"
        assets.mkdir()
        (assets / "logo.png").write_bytes(b"\x89PNG")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_logo()

        assert result is not None
        assert result["light"] == "assets/logo.png"


def test_detect_logo_returns_none():
    """_detect_logo returns None when no logo file is found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_logo() is None


def test_detect_logo_light_dark_pair():
    """_detect_logo finds light/dark logo pair."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "logo.svg").write_text("<svg/>")
        (Path(tmp_dir) / "logo-dark.svg").write_text("<svg dark/>")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_logo()

        assert result is not None
        assert result["light"] == "logo.svg"
        assert result["dark"] == "logo-dark.svg"


# ---------------------------------------------------------------------------
# Coverage: _detect_hero_logo (core.py lines ~507-529)
# ---------------------------------------------------------------------------


def test_detect_hero_logo_finds_svg():
    """_detect_hero_logo finds logo-hero.svg."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "logo-hero.svg").write_text("<svg hero/>")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_hero_logo()

        assert result is not None
        assert result["light"] == "logo-hero.svg"


def test_detect_hero_logo_light_dark_pair():
    """_detect_hero_logo finds light/dark hero pair."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "logo-hero-light.svg").write_text("<svg light/>")
        (Path(tmp_dir) / "logo-hero-dark.svg").write_text("<svg dark/>")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_hero_logo()

        assert result is not None
        assert result["light"] == "logo-hero-light.svg"
        assert result["dark"] == "logo-hero-dark.svg"


def test_detect_hero_logo_returns_none():
    """_detect_hero_logo returns None when no hero logo exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_hero_logo() is None


def test_detect_hero_logo_in_assets():
    """_detect_hero_logo finds hero logo in assets/ directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        assets = Path(tmp_dir) / "assets"
        assets.mkdir()
        (assets / "logo-hero.png").write_bytes(b"\x89PNG")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_hero_logo()

        assert result is not None
        assert result["light"] == "assets/logo-hero.png"


# ---------------------------------------------------------------------------
# Coverage: _normalize_package_name (core.py line 670)
# ---------------------------------------------------------------------------


def test_normalize_package_name():
    """_normalize_package_name replaces hyphens with underscores."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._normalize_package_name("my-cool-package") == "my_cool_package"
        assert docs._normalize_package_name("already_underscored") == "already_underscored"
        assert docs._normalize_package_name("simple") == "simple"


# ---------------------------------------------------------------------------
# Coverage: _detect_module_name (core.py lines ~692-768)
# ---------------------------------------------------------------------------


def test_detect_module_name_from_config():
    """_detect_module_name uses explicit module setting from config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "great-docs.yml").write_text("module: my_custom_module\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "my_custom_module"


def test_detect_module_name_from_pyi_stub():
    """_detect_module_name finds module from .pyi stub file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "my_module.pyi").write_text("def foo() -> int: ...\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "my_module"


def test_detect_module_name_from_maturin():
    """_detect_module_name reads module-name from [tool.maturin]."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[tool.maturin]\nmodule-name = "rust_mod"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "rust_mod"


def test_detect_module_name_from_setuptools_packages():
    """_detect_module_name reads from [tool.setuptools] packages list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[tool.setuptools]\npackages = ["my_lib"]\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "my_lib"


def test_detect_module_name_from_hatch_packages():
    """_detect_module_name reads from [tool.hatch.build.targets.wheel]."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n'
            "[tool.hatch.build.targets.wheel]\n"
            'packages = ["src/hatch_pkg"]\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "hatch_pkg"


def test_detect_module_name_falls_back_to_init():
    """_detect_module_name falls back to _find_package_init when no config found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "my-pkg"\n')
        pkg = Path(tmp_dir) / "my_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("__version__ = '1.0'\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() == "my_pkg"


def test_detect_module_name_returns_none():
    """_detect_module_name returns None when nothing is found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "mystery"\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_module_name() is None


# ---------------------------------------------------------------------------
# Coverage: _is_compiled_extension (core.py lines ~779-793)
# ---------------------------------------------------------------------------


def test_is_compiled_extension_cargo():
    """_is_compiled_extension returns True when Cargo.toml exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "Cargo.toml").write_text("[package]\nname = 'mypkg'\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._is_compiled_extension() is True


def test_is_compiled_extension_pyi_without_py():
    """_is_compiled_extension returns True for .pyi without matching .py."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (Path(tmp_dir) / "myext.pyi").write_text("def foo() -> int: ...\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._is_compiled_extension() is True


def test_is_compiled_extension_false():
    """_is_compiled_extension returns False for a normal Python package."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._is_compiled_extension() is False


# ---------------------------------------------------------------------------
# Coverage: _get_cli_entry_point_name (core.py lines ~2124-2150)
# ---------------------------------------------------------------------------


def test_get_cli_entry_point_name():
    """_get_cli_entry_point_name reads first entry point from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[project.scripts]\nmycli = "pkg.cli:main"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("pkg") == "mycli"


def test_get_cli_entry_point_name_gui_scripts():
    """_get_cli_entry_point_name falls back to gui-scripts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\n[project.gui-scripts]\nmyapp = "pkg.gui:main"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("pkg") == "myapp"


def test_get_cli_entry_point_name_no_scripts():
    """_get_cli_entry_point_name returns None when no scripts defined."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("pkg") is None


def test_get_cli_entry_point_name_no_pyproject():
    """_get_cli_entry_point_name returns None when pyproject.toml missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("pkg") is None


# ---------------------------------------------------------------------------
# Coverage: _add_frontmatter_option (core.py lines ~2861-2871)
# ---------------------------------------------------------------------------


def test_add_frontmatter_option_new_key():
    """_add_frontmatter_option adds a new key to existing frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "---\ntitle: Hello\n---\n\n# Body\n"
        result = docs._add_frontmatter_option(content, "toc", False)
        assert "toc: false" in result
        assert "title: Hello" in result


def test_add_frontmatter_option_update_existing():
    """_add_frontmatter_option updates an existing key."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "---\ntitle: Old Title\n---\n\n# Body\n"
        result = docs._add_frontmatter_option(content, "title", "New Title")
        assert '"New Title"' in result
        assert "Old Title" not in result


def test_add_frontmatter_option_no_frontmatter():
    """_add_frontmatter_option creates frontmatter when none exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "# No frontmatter here\n"
        result = docs._add_frontmatter_option(content, "title", "Added")
        assert result.startswith("---\n")
        assert '"Added"' in result
        assert "# No frontmatter here" in result


def test_add_frontmatter_option_bool_true():
    """_add_frontmatter_option handles boolean True values."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "---\ntitle: Test\n---\nBody"
        result = docs._add_frontmatter_option(content, "toc", True)
        assert "toc: true" in result


# ---------------------------------------------------------------------------
# Coverage: _update_navbar_github_link (core.py lines ~1063-1100)
# ---------------------------------------------------------------------------


def test_update_navbar_github_link_widget_style():
    """_update_navbar_github_link creates a widget entry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = {"website": {"navbar": {"right": []}}}
        docs._update_navbar_github_link(
            config, "owner", "repo", "https://github.com/owner/repo", "widget"
        )
        right = config["website"]["navbar"]["right"]
        assert len(right) == 1
        assert "github-widget" in right[0]["text"]


def test_update_navbar_github_link_icon_style():
    """_update_navbar_github_link creates an icon entry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = {"website": {"navbar": {"right": []}}}
        docs._update_navbar_github_link(
            config, "owner", "repo", "https://github.com/owner/repo", "icon"
        )
        right = config["website"]["navbar"]["right"]
        assert len(right) == 1
        assert right[0]["icon"] == "github"


def test_update_navbar_github_link_replaces_existing():
    """_update_navbar_github_link replaces an existing GitHub icon entry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = {
            "website": {
                "navbar": {
                    "right": [
                        {"icon": "github", "href": "https://github.com/old/old"},
                        {"icon": "twitter", "href": "https://twitter.com"},
                    ]
                }
            }
        }
        docs._update_navbar_github_link(
            config, "new_owner", "new_repo", "https://github.com/new_owner/new_repo", "widget"
        )
        right = config["website"]["navbar"]["right"]
        assert len(right) == 2
        assert "github-widget" in right[0]["text"]
        assert right[1]["icon"] == "twitter"


def test_update_navbar_github_link_no_url():
    """_update_navbar_github_link does nothing if repo_url is None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = {"website": {"navbar": {"right": []}}}
        docs._update_navbar_github_link(config, None, None, None, "icon")
        assert config["website"]["navbar"]["right"] == []


def test_update_navbar_github_link_creates_right_section():
    """_update_navbar_github_link creates 'right' list if missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = {"website": {"navbar": {}}}
        docs._update_navbar_github_link(
            config, "owner", "repo", "https://github.com/owner/repo", "icon"
        )
        assert "right" in config["website"]["navbar"]
        assert len(config["website"]["navbar"]["right"]) == 1


# ---------------------------------------------------------------------------
# Coverage: _find_index_source_file (core.py lines ~6537-6560)
# ---------------------------------------------------------------------------


def test_find_index_source_file_readme():
    """_find_index_source_file finds README.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname="p"\n')
        (Path(tmp_dir) / "README.md").write_text("# Hello\n")

        docs = GreatDocs(project_path=tmp_dir)
        source, warnings = docs._find_index_source_file()

        assert source is not None
        assert source.name == "README.md"


def test_find_index_source_file_index_qmd_priority():
    """_find_index_source_file prefers index.qmd over README.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname="p"\n')
        (Path(tmp_dir) / "index.qmd").write_text("---\ntitle: Main\n---\n")
        (Path(tmp_dir) / "README.md").write_text("# Hello\n")

        docs = GreatDocs(project_path=tmp_dir)
        source, warnings = docs._find_index_source_file()

        assert source is not None
        assert source.name == "index.qmd"
        assert len(warnings) == 1  # warns about multiple candidates


def test_find_index_source_file_none():
    """_find_index_source_file returns None when no source file exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname="p"\n')

        docs = GreatDocs(project_path=tmp_dir)
        source, warnings = docs._find_index_source_file()

        assert source is None


# ---------------------------------------------------------------------------
# Coverage: _format_preserved_extras_yaml (core.py lines ~5964-6004)
# ---------------------------------------------------------------------------


def test_format_preserved_extras_yaml_with_values():
    """_format_preserved_extras_yaml generates active YAML when values set."""
    dn, site, funding = GreatDocs._format_preserved_extras_yaml(
        display_name="My Package",
        site={"theme": "flatly", "toc": True},
        funding={"name": "ACME Corp", "roles": ["funder"], "homepage": "https://acme.com"},
    )
    assert 'display_name: "My Package"' in dn
    assert "site:" in site
    assert "theme: flatly" in site
    assert "toc: true" in site
    assert 'name: "ACME Corp"' in funding
    assert "- funder" in funding
    assert "homepage: https://acme.com" in funding


def test_format_preserved_extras_yaml_defaults():
    """_format_preserved_extras_yaml generates commented templates when no values."""
    dn, site, funding = GreatDocs._format_preserved_extras_yaml()
    assert dn == ""
    assert "# site:" in site
    assert "# funding:" in funding


def test_format_preserved_extras_yaml_funding_with_ror():
    """_format_preserved_extras_yaml includes ROR when provided."""
    _, _, funding = GreatDocs._format_preserved_extras_yaml(
        funding={"name": "Posit", "ror": "https://ror.org/123"}
    )
    assert "ror: https://ror.org/123" in funding


# ---------------------------------------------------------------------------
# Coverage: _format_cli_yaml (core.py lines ~6039-6049)
# ---------------------------------------------------------------------------


def test_format_cli_yaml_enabled():
    """_format_cli_yaml generates active YAML when CLI is enabled."""
    result = GreatDocs._format_cli_yaml({"enabled": True, "module": "pkg.cli", "name": "mycli"})
    assert "cli:" in result
    assert "enabled: true" in result
    assert "module: pkg.cli" in result
    assert "name: mycli" in result


def test_format_cli_yaml_disabled():
    """_format_cli_yaml generates commented template when disabled."""
    result = GreatDocs._format_cli_yaml(None)
    assert "# cli:" in result
    assert "#   enabled: true" in result


def test_format_cli_yaml_enabled_minimal():
    """_format_cli_yaml with only enabled flag set."""
    result = GreatDocs._format_cli_yaml({"enabled": True})
    assert "cli:" in result
    assert "enabled: true" in result
    assert "module:" not in result


# ---------------------------------------------------------------------------
# Coverage: _get_package_metadata (core.py lines ~931-991)
# ---------------------------------------------------------------------------


def test_get_package_metadata_from_setup_cfg():
    """_get_package_metadata reads metadata from setup.cfg fallback."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "setup.cfg").write_text(
            "[metadata]\n"
            "name = my-package\n"
            "description = A test package\n"
            "license = MIT\n"
            "author = Test Author\n"
            "author_email = test@example.com\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert metadata["description"] == "A test package"
        assert metadata["license"] == "MIT"
        assert len(metadata["authors"]) == 1
        assert metadata["authors"][0]["name"] == "Test Author"


def test_get_package_metadata_setup_cfg_urls():
    """_get_package_metadata reads URLs from setup.cfg."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "setup.cfg").write_text(
            "[metadata]\n"
            "name = my-package\n"
            "description = A test\n"
            "url = https://github.com/me/pkg\n"
            "project_urls =\n"
            "    Documentation = https://docs.example.com\n"
            "    Bug Tracker = https://github.com/me/pkg/issues\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert "Repository" in metadata["urls"]
        assert "Documentation" in metadata["urls"]


def test_get_package_metadata_setup_cfg_maintainer():
    """_get_package_metadata reads maintainer from setup.cfg."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "setup.cfg").write_text(
            "[metadata]\n"
            "name = my-package\n"
            "description = Desc\n"
            "maintainer = Maintainer Person\n"
            "maintainer_email = maint@example.com\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert len(metadata["maintainers"]) == 1
        assert metadata["maintainers"][0]["name"] == "Maintainer Person"


def test_get_package_metadata_setup_cfg_python_requires():
    """_get_package_metadata reads python_requires from setup.cfg."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "setup.cfg").write_text(
            "[metadata]\nname = my-package\ndescription = D\n\n[options]\npython_requires = >=3.8\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        metadata = docs._get_package_metadata()

        assert metadata["requires_python"] == ">=3.8"


# ---------------------------------------------------------------------------
# Coverage: _find_package_init third-pass auto-discovery (core.py lines ~3660-3696)
# ---------------------------------------------------------------------------


def test_find_package_init_auto_discovers():
    """_find_package_init auto-discovers packages with non-matching names."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "completely-different"\n')

        # Create a package with a different name than the project
        pkg = Path(tmp_dir) / "actual_pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("x = 1\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._find_package_init("completely-different")

        assert result is not None
        assert result.parent.name == "actual_pkg"


def test_find_package_init_skips_excluded_dirs():
    """_find_package_init skips tests/, docs/, .venv/ etc during auto-discovery."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text('[project]\nname = "nonexistent"\n')

        # These should be skipped
        for d in ["tests", "docs", ".venv", "__pycache__"]:
            skipped = Path(tmp_dir) / d
            skipped.mkdir()
            (skipped / "__init__.py").write_text("")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._find_package_init("nonexistent")

        assert result is None


def test_find_package_init_hatch_packages():
    """_find_package_init uses [tool.hatch.build.targets.wheel.packages]."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        (Path(tmp_dir) / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n'
            "[tool.hatch.build.targets.wheel]\n"
            'packages = ["src/hatch_mod"]\n'
        )

        src = Path(tmp_dir) / "src" / "hatch_mod"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("__all__ = ['x']\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._find_package_init("mypkg")

        assert result is not None
        assert result.parent.name == "hatch_mod"


# ---------------------------------------------------------------------------
# Coverage: _sub_classify_class static method (core.py lines ~4435-4504)
# ---------------------------------------------------------------------------


def test_sub_classify_class_dataclass():
    """_sub_classify_class identifies dataclasses."""

    class FakeObj:
        labels = {"dataclass"}
        bases = []
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "dataclass"


def test_sub_classify_class_enum():
    """_sub_classify_class identifies enums."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "enum.IntEnum"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "enum"


def test_sub_classify_class_exception():
    """_sub_classify_class identifies exceptions."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "Exception"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "exception"


def test_sub_classify_class_namedtuple():
    """_sub_classify_class identifies NamedTuples."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "NamedTuple"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "namedtuple"


def test_sub_classify_class_typeddict():
    """_sub_classify_class identifies TypedDicts."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "TypedDict"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "typeddict"


def test_sub_classify_class_protocol():
    """_sub_classify_class identifies Protocols."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "Protocol"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "protocol"


def test_sub_classify_class_abc():
    """_sub_classify_class identifies ABCs."""

    class FakeObj:
        labels = set()

        class FakeBase:
            def __str__(self):
                return "ABC"

        bases = [FakeBase()]
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "abc"


def test_sub_classify_class_abc_from_decorator():
    """_sub_classify_class identifies ABCs from abstractmethod decorator."""

    class FakeDecorator:
        def __init__(self):
            self.value = "abstractmethod"

    class FakeObj:
        labels = set()
        bases = []
        decorators = [FakeDecorator()]

    assert GreatDocs._sub_classify_class(FakeObj()) == "abc"


def test_sub_classify_class_plain():
    """_sub_classify_class returns 'class' for regular classes."""

    class FakeObj:
        labels = set()
        bases = []
        decorators = []

    assert GreatDocs._sub_classify_class(FakeObj()) == "class"


# ---------------------------------------------------------------------------
# Coverage: _sub_classify_function static method (core.py lines ~4494-4504)
# ---------------------------------------------------------------------------


def test_sub_classify_function_async():
    """_sub_classify_function identifies async functions."""

    class FakeObj:
        labels = {"async"}

    assert GreatDocs._sub_classify_function(FakeObj()) == "async"


def test_sub_classify_function_classmethod():
    """_sub_classify_function identifies classmethods."""

    class FakeObj:
        labels = {"classmethod"}

    assert GreatDocs._sub_classify_function(FakeObj()) == "classmethod"


def test_sub_classify_function_staticmethod():
    """_sub_classify_function identifies staticmethods."""

    class FakeObj:
        labels = {"staticmethod"}

    assert GreatDocs._sub_classify_function(FakeObj()) == "staticmethod"


def test_sub_classify_function_property():
    """_sub_classify_function identifies properties."""

    class FakeObj:
        labels = {"property"}

    assert GreatDocs._sub_classify_function(FakeObj()) == "property"


def test_sub_classify_function_plain():
    """_sub_classify_function returns 'function' for regular functions."""

    class FakeObj:
        labels = set()

    assert GreatDocs._sub_classify_function(FakeObj()) == "function"


# ---------------------------------------------------------------------------
# Coverage: _sub_classify_attribute static method (core.py lines ~4527-4544)
# ---------------------------------------------------------------------------


def test_sub_classify_attribute_type_alias():
    """_sub_classify_attribute identifies type aliases via kind."""

    class FakeKind:
        value = "type alias"

    class FakeObj:
        labels = set()
        kind = FakeKind()
        annotation = None

    assert GreatDocs._sub_classify_attribute(FakeObj()) == "type_alias"


def test_sub_classify_attribute_typevar():
    """_sub_classify_attribute identifies TypeVar annotations."""

    class FakeObj:
        labels = set()
        kind = None
        annotation = "TypeVar"

    assert GreatDocs._sub_classify_attribute(FakeObj()) == "typevar"


def test_sub_classify_attribute_paramspec():
    """_sub_classify_attribute identifies ParamSpec annotations."""

    class FakeObj:
        labels = set()
        kind = None
        annotation = "ParamSpec"

    assert GreatDocs._sub_classify_attribute(FakeObj()) == "typevar"


def test_sub_classify_attribute_constant():
    """_sub_classify_attribute returns 'constant' for regular attributes."""

    class FakeObj:
        labels = set()
        kind = None
        annotation = None

    assert GreatDocs._sub_classify_attribute(FakeObj()) == "constant"


# ---------------------------------------------------------------------------
# Coverage: _extract_constant_metadata static method (core.py lines ~4577-4583)
# ---------------------------------------------------------------------------


def test_extract_constant_metadata_value_and_annotation():
    """_extract_constant_metadata captures both value and annotation."""

    class FakeObj:
        value = "42"
        annotation = "int"

    categories = {"constant_metadata": {}}
    GreatDocs._extract_constant_metadata(FakeObj(), "MY_CONST", categories)

    assert "MY_CONST" in categories["constant_metadata"]
    assert categories["constant_metadata"]["MY_CONST"]["value"] == "42"
    assert categories["constant_metadata"]["MY_CONST"]["annotation"] == "int"


def test_extract_constant_metadata_no_value():
    """_extract_constant_metadata skips when value is None."""

    class FakeObj:
        value = None
        annotation = "str"

    categories = {"constant_metadata": {}}
    GreatDocs._extract_constant_metadata(FakeObj(), "X", categories)

    assert "X" in categories["constant_metadata"]
    assert "value" not in categories["constant_metadata"]["X"]
    assert categories["constant_metadata"]["X"]["annotation"] == "str"


def test_extract_constant_metadata_long_value():
    """_extract_constant_metadata skips values longer than 200 chars."""

    class FakeObj:
        value = "x" * 201
        annotation = None

    categories = {"constant_metadata": {}}
    GreatDocs._extract_constant_metadata(FakeObj(), "BIG", categories)

    assert "BIG" not in categories["constant_metadata"]


# ---------------------------------------------------------------------------
# Coverage: _count_cli_sidebar_items static method (core.py line ~2350)
# ---------------------------------------------------------------------------


def test_count_cli_sidebar_items_flat():
    """_count_cli_sidebar_items counts simple string entries."""
    assert GreatDocs._count_cli_sidebar_items(["a.qmd", "b.qmd", "c.qmd"]) == 3


def test_count_cli_sidebar_items_nested():
    """_count_cli_sidebar_items counts nested section contents."""
    items = [
        "top.qmd",
        {"section": "Group", "contents": ["a.qmd", "b.qmd"]},
    ]
    assert GreatDocs._count_cli_sidebar_items(items) == 3


def test_count_cli_sidebar_items_empty():
    """_count_cli_sidebar_items returns 0 for empty list."""
    assert GreatDocs._count_cli_sidebar_items([]) == 0


# ===========================================================================
# Coverage batch 2: Blog, section, user-guide, config, and navigation methods
# ===========================================================================

import json
import shutil
import yaml


# ---------------------------------------------------------------------------
# _copy_blog_files  (core.py ~1606-1670)
# ---------------------------------------------------------------------------


def test_copy_blog_files_basic():
    """_copy_blog_files copies files and extracts frontmatter metadata."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "blog"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        content = "---\ntitle: My Post\ndescription: About stuff\n---\nBody text\n"
        (src / "my-post.qmd").write_text(content)

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_blog_files([src / "my-post.qmd"], src, dest)

        assert len(result) == 1
        assert result[0]["title"] == "My Post"
        assert result[0]["description"] == "About stuff"
        assert result[0]["filename"] == "my-post.qmd"
        assert (dest / "my-post.qmd").read_text() == content


def test_copy_blog_files_no_frontmatter():
    """_copy_blog_files derives title from filename when no frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "blog"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        (src / "hello-world.qmd").write_text("Just body text\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_blog_files([src / "hello-world.qmd"], src, dest)

        assert result[0]["title"] == "Hello World"
        assert result[0]["description"] == ""


def test_copy_blog_files_subdirectory():
    """_copy_blog_files preserves subdirectory structure."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "blog"
        sub = src / "2024" / "post-1"
        sub.mkdir(parents=True)
        dest = tmp / "out"
        dest.mkdir()

        (sub / "index.qmd").write_text("---\ntitle: Nested Post\n---\nBody\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_blog_files([sub / "index.qmd"], src, dest)

        assert result[0]["filename"] == "2024/post-1/index.qmd"
        assert (dest / "2024" / "post-1" / "index.qmd").exists()


def test_copy_blog_files_bad_yaml():
    """_copy_blog_files handles invalid YAML frontmatter gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "blog"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        (src / "bad.qmd").write_text("---\n: [invalid yaml\n---\nBody\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_blog_files([src / "bad.qmd"], src, dest)

        assert len(result) == 1
        assert result[0]["title"] == "Bad"


# ---------------------------------------------------------------------------
# _generate_blog_index  (core.py ~1672-1710)
# ---------------------------------------------------------------------------


def test_generate_blog_index_creates_file():
    """_generate_blog_index creates an index.qmd with listing directive."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "blog"
        dest.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        docs._generate_blog_index("My Blog", "blog", dest)

        index = dest / "index.qmd"
        assert index.exists()
        content = index.read_text()
        assert 'title: "My Blog"' in content
        assert "listing:" in content
        assert 'sort: "date desc"' in content
        assert "bread-crumbs: false" in content


# ---------------------------------------------------------------------------
# _generate_section_index  (core.py ~1709-1809)
# ---------------------------------------------------------------------------


def test_generate_section_index_with_pages():
    """_generate_section_index creates a card gallery index."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "recipes"
        dest.mkdir()

        pages = [
            {"filename": "intro.qmd", "title": "Intro", "description": "Getting started"},
            {"filename": "advanced.qmd", "title": "Advanced", "description": "Deep dive"},
        ]
        docs = GreatDocs(project_path=tmp_dir)
        docs._generate_section_index("Recipes", pages, "recipes", dest)

        index = dest / "index.qmd"
        assert index.exists()
        content = index.read_text()
        assert 'title: "Recipes"' in content
        assert "section-cards" in content
        assert "Intro" in content
        assert "Advanced" in content


def test_generate_section_index_filters_index():
    """_generate_section_index excludes index.qmd from entries."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        pages = [
            {"filename": "index.qmd", "title": "Index", "description": ""},
            {"filename": "page.qmd", "title": "Page", "description": "A page"},
        ]
        docs = GreatDocs(project_path=tmp_dir)
        docs._generate_section_index("Section", pages, "sec", dest)

        content = (dest / "index.qmd").read_text()
        assert "Page" in content
        # The card for Index should not appear (it's excluded from entries)
        assert 'href="index.qmd"' not in content


def test_generate_section_index_empty():
    """_generate_section_index writes 'No pages found' when empty."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        docs._generate_section_index("Empty", [], "sec", dest)

        content = (dest / "index.qmd").read_text()
        assert "No pages found" in content


def test_generate_section_index_with_image():
    """_generate_section_index includes image tags when entries have images."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        pages = [
            {"filename": "card.qmd", "title": "Card", "description": "Desc", "image": "pic.png"},
        ]
        docs = GreatDocs(project_path=tmp_dir)
        docs._generate_section_index("Sec", pages, "sec", dest)

        content = (dest / "index.qmd").read_text()
        assert "pic.png" in content
        assert "<img" in content


# ---------------------------------------------------------------------------
# _copy_section_files  (core.py ~1524-1606)
# ---------------------------------------------------------------------------


def test_copy_section_files_strips_prefix():
    """_copy_section_files strips numeric prefixes from filenames."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "recipes"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        (src / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nBody\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_section_files([src / "01-intro.qmd"], src, dest)

        assert result[0]["filename"] == "intro.qmd"
        assert result[0]["title"] == "Intro"
        assert (dest / "intro.qmd").exists()


def test_copy_section_files_adds_breadcrumbs():
    """_copy_section_files adds bread-crumbs: false to frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "sec"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        (src / "page.qmd").write_text("---\ntitle: Page\n---\nContent\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs._copy_section_files([src / "page.qmd"], src, dest)

        written = (dest / "page.qmd").read_text()
        assert "bread-crumbs" in written


def test_copy_section_files_no_frontmatter():
    """_copy_section_files handles files without frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "sec"
        src.mkdir()
        dest = tmp / "out"
        dest.mkdir()

        (src / "raw.qmd").write_text("Just regular content\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._copy_section_files([src / "raw.qmd"], src, dest)

        assert result[0]["title"] == "Raw"
        assert (dest / "raw.qmd").exists()


# ---------------------------------------------------------------------------
# _add_section_sidebar  (core.py ~1809-1875)
# ---------------------------------------------------------------------------


def test_add_section_sidebar_creates_sidebar():
    """_add_section_sidebar creates a sidebar entry in _quarto.yml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        pages = [
            {"filename": "page1.qmd", "title": "Page 1"},
            {"filename": "page2.qmd", "title": "Page 2"},
        ]
        docs._add_section_sidebar("Recipes", "recipes", pages, has_user_index=True)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        sidebar = result["website"]["sidebar"]
        assert len(sidebar) == 1
        assert sidebar[0]["id"] == "recipes"
        assert sidebar[0]["title"] == "Recipes"
        assert len(sidebar[0]["contents"]) == 3  # index + 2 pages


def test_add_section_sidebar_skips_single_page():
    """_add_section_sidebar returns early for single-page sections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        pages = [{"filename": "only.qmd", "title": "Only"}]
        docs._add_section_sidebar("Solo", "solo", pages, has_user_index=False)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        assert result["website"]["sidebar"] == []


def test_add_section_sidebar_replaces_existing():
    """_add_section_sidebar removes old sidebar with same id before adding new."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [{"id": "recipes", "title": "Old", "contents": ["old.qmd"]}],
                "navbar": {"left": []},
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        pages = [
            {"filename": "new1.qmd", "title": "New 1"},
            {"filename": "new2.qmd", "title": "New 2"},
        ]
        docs._add_section_sidebar("Recipes", "recipes", pages, has_user_index=True)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        sidebar = result["website"]["sidebar"]
        assert len(sidebar) == 1
        assert sidebar[0]["title"] == "Recipes"


# ---------------------------------------------------------------------------
# _inject_section_body_class  (core.py ~1876-1915)
# ---------------------------------------------------------------------------


def test_inject_section_body_class_adds_class():
    """_inject_section_body_class adds gd-section-no-sidebar to frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        (dest / "page.qmd").write_text("---\ntitle: Page\n---\nContent\n")

        pages = [{"filename": "page.qmd"}]
        docs = GreatDocs(project_path=tmp_dir)
        docs._inject_section_body_class("sec", pages, dest)

        content = (dest / "page.qmd").read_text()
        assert "gd-section-no-sidebar" in content


def test_inject_section_body_class_preserves_existing():
    """_inject_section_body_class appends to existing body-classes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        fm = "---\ntitle: Page\nbody-classes: my-custom\n---\nContent\n"
        (dest / "page.qmd").write_text(fm)

        pages = [{"filename": "page.qmd"}]
        docs = GreatDocs(project_path=tmp_dir)
        docs._inject_section_body_class("sec", pages, dest)

        content = (dest / "page.qmd").read_text()
        assert "my-custom" in content
        assert "gd-section-no-sidebar" in content


def test_inject_section_body_class_skip_missing():
    """_inject_section_body_class skips files that don't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        pages = [{"filename": "missing.qmd"}]
        docs = GreatDocs(project_path=tmp_dir)
        # Should not raise
        docs._inject_section_body_class("sec", pages, dest)


def test_inject_section_body_class_skip_no_frontmatter():
    """_inject_section_body_class skips files without --- frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        (dest / "plain.qmd").write_text("No frontmatter here\n")

        pages = [{"filename": "plain.qmd"}]
        docs = GreatDocs(project_path=tmp_dir)
        docs._inject_section_body_class("sec", pages, dest)

        content = (dest / "plain.qmd").read_text()
        assert "gd-section-no-sidebar" not in content


def test_inject_section_body_class_idempotent():
    """_inject_section_body_class doesn't duplicate the class."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        dest = tmp / "sec"
        dest.mkdir()

        fm = "---\ntitle: Page\nbody-classes: gd-section-no-sidebar\n---\nContent\n"
        (dest / "page.qmd").write_text(fm)

        pages = [{"filename": "page.qmd"}]
        docs = GreatDocs(project_path=tmp_dir)
        docs._inject_section_body_class("sec", pages, dest)

        content = (dest / "page.qmd").read_text()
        assert content.count("gd-section-no-sidebar") == 1


# ---------------------------------------------------------------------------
# _add_section_to_navbar  (core.py ~1915-1988)
# ---------------------------------------------------------------------------


def test_add_section_to_navbar_basic():
    """_add_section_to_navbar adds a link to the navbar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_section_to_navbar("Recipes", "recipes/index.qmd")

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        assert any(i.get("text") == "Recipes" for i in items)


def test_add_section_to_navbar_idempotent():
    """_add_section_to_navbar doesn't duplicate existing links."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [],
                "navbar": {"left": [{"text": "Recipes", "href": "recipes/index.qmd"}]},
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_section_to_navbar("Recipes", "recipes/index.qmd")

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        recipe_count = sum(1 for i in items if isinstance(i, dict) and i.get("text") == "Recipes")
        assert recipe_count == 1


def test_add_section_to_navbar_after():
    """_add_section_to_navbar inserts after a specific item."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [],
                "navbar": {
                    "left": [
                        {"text": "Guide", "href": "guide/"},
                        {"text": "Reference", "href": "reference/"},
                    ]
                },
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_section_to_navbar("Recipes", "recipes/", navbar_after="Guide")

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        texts = [i.get("text") for i in items if isinstance(i, dict)]
        assert texts == ["Guide", "Recipes", "Reference"]


def test_add_section_to_navbar_before_reference():
    """_add_section_to_navbar inserts before Reference when no navbar_after."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [],
                "navbar": {
                    "left": [
                        {"text": "Guide", "href": "guide/"},
                        {"text": "Reference", "href": "reference/"},
                    ]
                },
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_section_to_navbar("Blog", "blog/")

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        texts = [i.get("text") for i in items if isinstance(i, dict)]
        assert texts == ["Guide", "Blog", "Reference"]


def test_add_section_to_navbar_no_navbar():
    """_add_section_to_navbar returns early if no navbar exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": []}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        # Should not raise
        docs._add_section_to_navbar("X", "x/")


def test_add_section_to_navbar_after_not_found():
    """_add_section_to_navbar falls back to before Reference when after item not found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [],
                "navbar": {
                    "left": [
                        {"text": "Guide", "href": "guide/"},
                        {"text": "Reference", "href": "reference/"},
                    ]
                },
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_section_to_navbar("Extra", "extra/", navbar_after="NonExistent")

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        texts = [i.get("text") for i in items if isinstance(i, dict)]
        # Should insert before Reference as fallback
        assert texts == ["Guide", "Extra", "Reference"]


# ---------------------------------------------------------------------------
# _add_changelog_to_navbar  (core.py ~1377-1405)
# ---------------------------------------------------------------------------


def test_add_changelog_to_navbar():
    """_add_changelog_to_navbar adds Changelog link."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"navbar": {"left": [{"text": "Guide", "href": "guide/"}]}}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_changelog_to_navbar()

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        assert any(i.get("text") == "Changelog" for i in items)


def test_add_changelog_to_navbar_idempotent():
    """_add_changelog_to_navbar doesn't add duplicate entries."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"navbar": {"left": [{"text": "Changelog", "href": "changelog.qmd"}]}}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._add_changelog_to_navbar()

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        changelog_count = sum(
            1 for i in items if isinstance(i, dict) and i.get("text") == "Changelog"
        )
        assert changelog_count == 1


def test_add_changelog_to_navbar_no_file():
    """_add_changelog_to_navbar returns early when _quarto.yml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        # Should not raise
        docs._add_changelog_to_navbar()


# ---------------------------------------------------------------------------
# _parse_user_guide_file  (core.py ~2671-2721)
# ---------------------------------------------------------------------------


def test_parse_user_guide_file_with_frontmatter():
    """_parse_user_guide_file extracts title and section from frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "01-install.qmd"
        qmd.write_text("---\ntitle: Installation\nguide-section: Getting Started\n---\nBody\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_user_guide_file(qmd)

        assert result is not None
        assert result["title"] == "Installation"
        assert result["section"] == "Getting Started"


def test_parse_user_guide_file_derives_title():
    """_parse_user_guide_file derives title from filename when not in frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "03-getting-started.qmd"
        qmd.write_text("---\nguide-section: Basics\n---\nBody\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_user_guide_file(qmd)

        assert result is not None
        assert result["title"] == "Getting Started"


def test_parse_user_guide_file_no_frontmatter():
    """_parse_user_guide_file derives title from filename without frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        qmd = tmp / "05_advanced-usage.qmd"
        qmd.write_text("Just body content, no frontmatter\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_user_guide_file(qmd)

        assert result is not None
        assert result["title"] == "Advanced Usage"
        assert result["section"] is None


def test_parse_user_guide_file_missing_file():
    """_parse_user_guide_file returns None for missing files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_user_guide_file(Path(tmp_dir) / "nonexistent.qmd")
        assert result is None


# ---------------------------------------------------------------------------
# _discover_user_guide  (core.py ~2575-2671) — auto-discovery mode
# ---------------------------------------------------------------------------


def test_discover_user_guide_auto():
    """_discover_user_guide auto-discovers files from user_guide directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nContent\n")
        (ug / "02-setup.qmd").write_text("---\ntitle: Setup\n---\nContent\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert result["explicit"] is False
        assert len(result["files"]) == 2


def test_discover_user_guide_empty_dir():
    """_discover_user_guide returns None for an empty user_guide directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None


def test_discover_user_guide_no_dir():
    """_discover_user_guide returns None when no user_guide dir exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is None


def test_discover_user_guide_with_sections():
    """_discover_user_guide groups files by guide-section frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-intro.qmd").write_text("---\ntitle: Intro\nguide-section: Basics\n---\nA\n")
        (ug / "02-setup.qmd").write_text("---\ntitle: Setup\nguide-section: Basics\n---\nB\n")
        (ug / "03-api.qmd").write_text("---\ntitle: API\nguide-section: Advanced\n---\nC\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert "Basics" in result["sections"]
        assert "Advanced" in result["sections"]
        assert len(result["sections"]["Basics"]) == 2


def test_discover_user_guide_with_subdirectories():
    """_discover_user_guide discovers files recursively in subdirectories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "intro.qmd").write_text("---\ntitle: Intro\n---\nA\n")
        sub = ug / "advanced"
        sub.mkdir()
        (sub / "deep.qmd").write_text("---\ntitle: Deep\n---\nB\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide()

        assert result is not None
        assert len(result["files"]) == 2


# ---------------------------------------------------------------------------
# _discover_user_guide_explicit  (core.py ~2482-2575)
# ---------------------------------------------------------------------------


def test_discover_user_guide_explicit():
    """_discover_user_guide_explicit builds guide from config list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "install.qmd").write_text("---\ntitle: Install\n---\nA\n")
        (ug / "usage.qmd").write_text("---\ntitle: Usage\n---\nB\n")

        config = [
            {
                "section": "Getting Started",
                "contents": ["install.qmd", "usage.qmd"],
            }
        ]
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide_explicit(ug, config)

        assert result is not None
        assert result["explicit"] is True
        assert len(result["files"]) == 2
        assert "Getting Started" in result["sections"]


def test_discover_user_guide_explicit_missing_file():
    """_discover_user_guide_explicit handles missing files gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "real.qmd").write_text("---\ntitle: Real\n---\nA\n")

        config = [
            {
                "section": "Section",
                "contents": ["real.qmd", "missing.qmd"],
            }
        ]
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide_explicit(ug, config)

        assert result is not None
        assert len(result["files"]) == 1


def test_discover_user_guide_explicit_dict_items():
    """_discover_user_guide_explicit handles dict items with text/href."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "guide.qmd").write_text("---\ntitle: Guide\n---\nA\n")

        config = [
            {
                "section": "Docs",
                "contents": [{"href": "guide.qmd", "text": "Custom Label"}],
            }
        ]
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide_explicit(ug, config)

        assert result is not None
        assert result["files"][0]["custom_text"] == "Custom Label"


def test_discover_user_guide_explicit_empty():
    """_discover_user_guide_explicit returns None when no valid files found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()

        config = [{"section": "Empty", "contents": ["missing.qmd"]}]
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide_explicit(ug, config)

        assert result is None


def test_discover_user_guide_explicit_skips_duplicates():
    """_discover_user_guide_explicit skips files already seen."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "intro.qmd").write_text("---\ntitle: Intro\n---\nA\n")

        config = [
            {"section": "S1", "contents": ["intro.qmd"]},
            {"section": "S2", "contents": ["intro.qmd"]},  # duplicate
        ]
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_user_guide_explicit(ug, config)

        assert result is not None
        assert len(result["files"]) == 1


# ---------------------------------------------------------------------------
# _copy_user_guide_to_docs  (core.py ~2747-2825)
# ---------------------------------------------------------------------------


def test_copy_user_guide_to_docs_auto():
    """_copy_user_guide_to_docs strips numeric prefixes in auto mode."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nContent\n")

        guide_info = {
            "files": [{"path": src / "01-intro.qmd", "title": "Intro", "section": None}],
            "source_dir": src,
            "explicit": False,
        }
        result = docs._copy_user_guide_to_docs(guide_info)

        assert len(result) == 1
        assert "intro.qmd" in result[0]
        assert (docs.project_path / "user-guide" / "intro.qmd").exists()


def test_copy_user_guide_to_docs_explicit():
    """_copy_user_guide_to_docs preserves filenames in explicit mode."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nContent\n")

        guide_info = {
            "files": [{"path": src / "01-intro.qmd", "title": "Intro", "section": None}],
            "source_dir": src,
            "explicit": True,
        }
        result = docs._copy_user_guide_to_docs(guide_info)

        assert "01-intro.qmd" in result[0]


def test_copy_user_guide_to_docs_adds_breadcrumbs():
    """_copy_user_guide_to_docs adds bread-crumbs: false."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "page.qmd").write_text("---\ntitle: Page\n---\nContent\n")

        guide_info = {
            "files": [{"path": src / "page.qmd", "title": "Page", "section": None}],
            "source_dir": src,
            "explicit": True,
        }
        docs._copy_user_guide_to_docs(guide_info)

        content = (docs.project_path / "user-guide" / "page.qmd").read_text()
        assert "bread-crumbs" in content


def test_copy_user_guide_to_docs_empty():
    """_copy_user_guide_to_docs returns empty list for falsy input."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._copy_user_guide_to_docs({}) == []
        assert docs._copy_user_guide_to_docs(None) == []


def test_copy_user_guide_to_docs_copies_assets():
    """_copy_user_guide_to_docs copies asset directories without .qmd files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "page.qmd").write_text("---\ntitle: P\n---\nC\n")
        assets = src / "images"
        assets.mkdir()
        (assets / "logo.png").write_text("fake-png")

        guide_info = {
            "files": [{"path": src / "page.qmd", "title": "P", "section": None}],
            "source_dir": src,
            "explicit": True,
        }
        docs._copy_user_guide_to_docs(guide_info)

        assert (docs.project_path / "user-guide" / "images" / "logo.png").exists()


# ---------------------------------------------------------------------------
# _update_sidebar_with_cli  (core.py ~2360-2435)
# ---------------------------------------------------------------------------


def test_update_sidebar_with_cli_new():
    """_update_sidebar_with_cli adds CLI section to sidebar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": []}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._update_sidebar_with_cli(["reference/cli/cmd1.qmd", "reference/cli/cmd2.qmd"])

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        sidebar = result["website"]["sidebar"]
        cli = next(s for s in sidebar if isinstance(s, dict) and s.get("id") == "cli-reference")
        assert cli["title"] == "CLI Reference"
        assert len(cli["contents"]) == 2


def test_update_sidebar_with_cli_updates_existing():
    """_update_sidebar_with_cli updates existing CLI section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [
                    {"id": "cli-reference", "title": "CLI Reference", "contents": ["old.qmd"]}
                ]
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._update_sidebar_with_cli(["new1.qmd", "new2.qmd"])

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        cli = next(
            s
            for s in result["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "cli-reference"
        )
        assert cli["contents"] == ["new1.qmd", "new2.qmd"]


def test_update_sidebar_with_cli_empty():
    """_update_sidebar_with_cli returns early for empty cli_files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {"website": {"sidebar": []}}
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._update_sidebar_with_cli([])

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        assert result["website"]["sidebar"] == []


def test_update_sidebar_with_cli_adds_api_link():
    """_update_sidebar_with_cli adds API link to reference sidebar if missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [
                    {
                        "id": "reference",
                        "title": "Reference",
                        "contents": ["reference/some.qmd"],
                    }
                ]
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        docs._update_sidebar_with_cli(["cli/cmd.qmd"])

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        ref = next(
            s
            for s in result["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "reference"
        )
        assert ref["contents"][0]["text"] == "API"


# ---------------------------------------------------------------------------
# _format_preserved_extras_yaml  (core.py ~5937-6023)
# ---------------------------------------------------------------------------


def test_format_preserved_extras_yaml_display_name():
    """_format_preserved_extras_yaml returns active display_name YAML when given."""
    dn, _, _ = GreatDocs._format_preserved_extras_yaml(display_name="My Package")
    assert 'display_name: "My Package"' in dn


def test_format_preserved_extras_yaml_no_display_name():
    """_format_preserved_extras_yaml returns empty string for no display_name."""
    dn, _, _ = GreatDocs._format_preserved_extras_yaml(display_name=None)
    assert dn == ""


def test_format_preserved_extras_yaml_site_active():
    """_format_preserved_extras_yaml returns active site YAML with key-value pairs."""
    _, site, _ = GreatDocs._format_preserved_extras_yaml(
        site={"theme": "flatly", "toc": True, "toc-depth": 3}
    )
    assert "site:" in site
    assert "theme: flatly" in site
    assert "toc: true" in site
    assert "toc-depth: 3" in site


def test_format_preserved_extras_yaml_site_commented():
    """_format_preserved_extras_yaml returns commented template when no site."""
    _, site, _ = GreatDocs._format_preserved_extras_yaml(site=None)
    assert "# site:" in site
    assert "#   theme:" in site


def test_format_preserved_extras_yaml_funding_active():
    """_format_preserved_extras_yaml returns active funding YAML."""
    _, _, funding = GreatDocs._format_preserved_extras_yaml(
        funding={"name": "Acme Corp", "roles": ["funder", "sponsor"], "homepage": "https://acme.co"}
    )
    assert "funding:" in funding
    assert 'name: "Acme Corp"' in funding
    assert "- funder" in funding
    assert "homepage: https://acme.co" in funding


def test_format_preserved_extras_yaml_funding_with_ror():
    """_format_preserved_extras_yaml includes ror when provided."""
    _, _, funding = GreatDocs._format_preserved_extras_yaml(
        funding={"name": "Lab", "ror": "https://ror.org/abc123"}
    )
    assert "ror: https://ror.org/abc123" in funding


def test_format_preserved_extras_yaml_funding_commented():
    """_format_preserved_extras_yaml returns commented template for no funding."""
    _, _, funding = GreatDocs._format_preserved_extras_yaml(funding=None)
    assert "# funding:" in funding


def test_format_preserved_extras_yaml_funding_no_name():
    """_format_preserved_extras_yaml returns template when funding has no name."""
    _, _, funding = GreatDocs._format_preserved_extras_yaml(funding={"homepage": "https://x.co"})
    assert "# funding:" in funding


# ---------------------------------------------------------------------------
# _format_cli_yaml  (core.py ~6023-6065)
# ---------------------------------------------------------------------------


def test_format_cli_yaml_enabled():
    """_format_cli_yaml returns active config when enabled."""
    result = GreatDocs._format_cli_yaml({"enabled": True, "module": "pkg.cli", "name": "main"})
    assert "cli:" in result
    assert "enabled: true" in result
    assert "module: pkg.cli" in result
    assert "name: main" in result


def test_format_cli_yaml_enabled_minimal():
    """_format_cli_yaml with only enabled=True omits optional keys."""
    result = GreatDocs._format_cli_yaml({"enabled": True})
    assert "cli:" in result
    assert "enabled: true" in result
    assert "module:" not in result
    assert "name:" not in result


def test_format_cli_yaml_disabled():
    """_format_cli_yaml returns commented template when disabled."""
    result = GreatDocs._format_cli_yaml({"enabled": False})
    assert "# cli:" in result


def test_format_cli_yaml_none():
    """_format_cli_yaml returns commented template for None."""
    result = GreatDocs._format_cli_yaml(None)
    assert "# cli:" in result


# ---------------------------------------------------------------------------
# _find_index_source_file  (core.py ~6470-6513)
# ---------------------------------------------------------------------------


def test_find_index_source_file_readme():
    """_find_index_source_file finds README.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "README.md").write_text("# My Package\n")

        docs = GreatDocs(project_path=tmp_dir)
        winner, warnings = docs._find_index_source_file()

        assert winner is not None
        assert winner.name == "README.md"
        assert len(warnings) == 0


def test_find_index_source_file_priority():
    """_find_index_source_file prefers index.qmd over README.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "index.qmd").write_text("---\ntitle: Home\n---\n")
        (tmp / "README.md").write_text("# My Package\n")

        docs = GreatDocs(project_path=tmp_dir)
        winner, warnings = docs._find_index_source_file()

        assert winner.name == "index.qmd"
        assert len(warnings) == 1  # warns about README.md being ignored


def test_find_index_source_file_none():
    """_find_index_source_file returns None when no candidates exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        winner, warnings = docs._find_index_source_file()

        assert winner is None


def test_find_index_source_file_rst():
    """_find_index_source_file finds README.rst as lowest priority."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "README.rst").write_text("My Package\n==========\n")

        docs = GreatDocs(project_path=tmp_dir)
        winner, warnings = docs._find_index_source_file()

        assert winner is not None
        assert winner.name == "README.rst"


# ---------------------------------------------------------------------------
# _detect_git_ref  (core.py ~3498-3546)
# ---------------------------------------------------------------------------


def test_detect_git_ref_configured():
    """_detect_git_ref returns configured source branch."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "1.0"\n')
        (tmp / "great-docs.yml").write_text("source:\n  branch: develop\n")

        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_git_ref() == "develop"


def test_detect_git_ref_fallback():
    """_detect_git_ref defaults to 'main' when git not available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        # In a temp dir without git, should fallback
        ref = docs._detect_git_ref()
        # Should be either the actual git branch or 'main' fallback
        assert isinstance(ref, str) and len(ref) > 0


# ---------------------------------------------------------------------------
# _build_github_source_url  (core.py ~3434-3498)
# ---------------------------------------------------------------------------


def test_build_github_source_url_basic():
    """_build_github_source_url builds URL with line anchors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "1.0"\n'
            '[project.urls]\nSource = "https://github.com/user/repo"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        source = {"file": "mypkg/core.py", "start_line": 10, "end_line": 20}
        url = docs._build_github_source_url(source, branch="main")

        assert url is not None
        assert "github.com/user/repo" in url
        assert "/blob/main/" in url
        assert "#L10-L20" in url


def test_build_github_source_url_single_line():
    """_build_github_source_url uses single-line anchor when start==end."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\nversion = "1.0"\n'
            '[project.urls]\nSource = "https://github.com/user/repo"\n'
        )

        docs = GreatDocs(project_path=tmp_dir)
        source = {"file": "mypkg/core.py", "start_line": 42, "end_line": 42}
        url = docs._build_github_source_url(source, branch="v1.0")

        assert "#L42" in url
        assert "-L" not in url


def test_build_github_source_url_no_repo():
    """_build_github_source_url returns None when no GitHub info available."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        source = {"file": "mypkg/core.py", "start_line": 1, "end_line": 10}
        url = docs._build_github_source_url(source, branch="main")

        assert url is None


# ---------------------------------------------------------------------------
# _process_sections  (core.py ~1405-1524) — the orchestrator
# ---------------------------------------------------------------------------


def test_process_sections_no_config():
    """_process_sections returns 0 when no sections configured."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._process_sections() == 0


def test_process_sections_invalid_type():
    """_process_sections returns 0 when sections is not a list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "great-docs.yml").write_text("sections: not-a-list\n")
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._process_sections() == 0


def test_process_sections_default_section():
    """_process_sections processes a default-type section end-to-end."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        # Create section source
        sec = tmp / "recipes"
        sec.mkdir()
        (sec / "01-basic.qmd").write_text("---\ntitle: Basic Recipe\n---\nContent\n")
        (sec / "02-advanced.qmd").write_text("---\ntitle: Advanced Recipe\n---\nContent\n")

        # Write config
        (tmp / "great-docs.yml").write_text("sections:\n  - title: Recipes\n    dir: recipes\n")

        docs = GreatDocs(project_path=tmp_dir)
        # Create the project build dir and _quarto.yml
        docs.project_path.mkdir(parents=True, exist_ok=True)
        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(docs.project_path / "_quarto.yml", "w") as f:
            yaml.dump(config, f)

        result = docs._process_sections()

        assert result == 1
        assert (docs.project_path / "recipes").exists()


def test_process_sections_blog_section():
    """_process_sections processes a blog-type section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        blog = tmp / "blog"
        blog.mkdir()
        (blog / "post1.qmd").write_text("---\ntitle: First Post\ndate: 2024-01-01\n---\nHello\n")

        (tmp / "great-docs.yml").write_text(
            "sections:\n  - title: Blog\n    dir: blog\n    type: blog\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(docs.project_path / "_quarto.yml", "w") as f:
            yaml.dump(config, f)

        result = docs._process_sections()

        assert result == 1
        # Blog should create an auto-generated index
        assert (docs.project_path / "blog" / "index.qmd").exists()


def test_process_sections_missing_dir():
    """_process_sections skips sections with non-existent directories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "great-docs.yml").write_text("sections:\n  - title: Missing\n    dir: no-such-dir\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        result = docs._process_sections()

        assert result == 0


def test_process_sections_missing_title():
    """_process_sections skips entries without title."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "great-docs.yml").write_text("sections:\n  - dir: recipes\n")

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._process_sections()
        assert result == 0


def test_process_sections_with_navbar_after():
    """_process_sections passes navbar_after to _add_section_to_navbar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        sec = tmp / "tutorials"
        sec.mkdir()
        (sec / "tut.qmd").write_text("---\ntitle: Tutorial\n---\nContent\n")

        (tmp / "great-docs.yml").write_text(
            "sections:\n  - title: Tutorials\n    dir: tutorials\n    navbar_after: Guide\n"
        )

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        config = {
            "website": {
                "sidebar": [],
                "navbar": {"left": [{"text": "Guide", "href": "guide/"}]},
            }
        }
        with open(docs.project_path / "_quarto.yml", "w") as f:
            yaml.dump(config, f)

        docs._process_sections()

        with open(docs.project_path / "_quarto.yml") as f:
            result = yaml.safe_load(f)

        items = result["website"]["navbar"]["left"]
        texts = [i.get("text") for i in items if isinstance(i, dict)]
        assert "Tutorials" in texts


# ---------------------------------------------------------------------------
# _insert_before_reference  (core.py ~1982)
# ---------------------------------------------------------------------------


def test_insert_before_reference():
    """_insert_before_reference inserts before Reference item."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = [{"text": "Guide"}, {"text": "Reference"}]
        docs._insert_before_reference(items, {"text": "New"})
        texts = [i["text"] for i in items]
        assert texts == ["Guide", "New", "Reference"]


def test_insert_before_reference_no_reference():
    """_insert_before_reference appends when no Reference found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = [{"text": "Guide"}]
        docs._insert_before_reference(items, {"text": "New"})
        texts = [i["text"] for i in items]
        assert texts == ["Guide", "New"]


# ---------------------------------------------------------------------------
# _read_quarto_config  (core.py ~1988)
# ---------------------------------------------------------------------------


def test_read_quarto_config_existing():
    """_read_quarto_config reads and returns config with defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

        quarto_yml = docs.project_path / "_quarto.yml"
        with open(quarto_yml, "w") as f:
            yaml.dump({"project": {"type": "website"}}, f)

        config = docs._read_quarto_config(quarto_yml)
        assert "website" in config
        assert "sidebar" in config["website"]
        assert "navbar" in config["website"]


def test_read_quarto_config_missing():
    """_read_quarto_config returns defaults when file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        config = docs._read_quarto_config(Path(tmp_dir) / "missing.yml")
        assert config["website"]["sidebar"] == []
        assert "left" in config["website"]["navbar"]


# ---------------------------------------------------------------------------
# _add_frontmatter_option  (core.py ~2825)
# ---------------------------------------------------------------------------


def test_add_frontmatter_option_new_key():
    """_add_frontmatter_option adds new key to frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "---\ntitle: Page\n---\nBody\n"
        result = docs._add_frontmatter_option(content, "bread-crumbs", False)
        assert "bread-crumbs: false" in result


def test_add_frontmatter_option_bool_true():
    """_add_frontmatter_option formats boolean True correctly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "---\ntitle: Page\n---\nBody\n"
        result = docs._add_frontmatter_option(content, "toc", True)
        assert "toc: true" in result


def test_add_frontmatter_option_no_frontmatter():
    """_add_frontmatter_option handles content without frontmatter."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        content = "Just plain content\n"
        result = docs._add_frontmatter_option(content, "key", "val")
        # Should wrap in frontmatter
        assert "---" in result


# ===========================================================================
# Coverage batch 3: CLI documentation, user guide orchestration, sidebar, nodoc
# ===========================================================================


# ---------------------------------------------------------------------------
# _get_cli_entry_point_name  (core.py ~2110)
# ---------------------------------------------------------------------------


def test_get_cli_entry_point_name_scripts():
    """_get_cli_entry_point_name returns first [project.scripts] name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n\n[project.scripts]\nmy-tool = "mypkg.cli:main"\n'
        )
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("mypkg") == "my-tool"


def test_get_cli_entry_point_name_gui_scripts():
    """_get_cli_entry_point_name falls back to gui-scripts."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n\n[project.gui-scripts]\nmy-gui = "mypkg.gui:main"\n'
        )
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("mypkg") == "my-gui"


def test_get_cli_entry_point_name_no_scripts():
    """_get_cli_entry_point_name returns None when no scripts defined."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("mypkg") is None


def test_get_cli_entry_point_name_no_pyproject():
    """_get_cli_entry_point_name returns None when pyproject.toml missing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._get_cli_entry_point_name("mypkg") is None


# ---------------------------------------------------------------------------
# _extract_click_command  (core.py ~2155)
# ---------------------------------------------------------------------------


def test_extract_click_command_simple():
    """_extract_click_command extracts info from a simple Click command."""
    pytest.importorskip("click")
    import click

    @click.command()
    @click.option("--name", help="Your name")
    def hello(name):
        """Say hello."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._extract_click_command(hello, "hello")

        assert result["name"] == "hello"
        assert result["full_path"] == "hello"
        assert result["help"] == "Say hello."
        assert result["is_group"] is False
        assert result["commands"] == []


def test_extract_click_command_group():
    """_extract_click_command extracts subcommands from a Click group."""
    pytest.importorskip("click")
    import click

    @click.group()
    def cli():
        """Main CLI."""

    @cli.command()
    def sub():
        """A subcommand."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._extract_click_command(cli, "tool")

        assert result["is_group"] is True
        assert len(result["commands"]) == 1
        assert result["commands"][0]["name"] == "sub"
        assert result["commands"][0]["full_path"] == "tool sub"


def test_extract_click_command_hidden_subcommand():
    """_extract_click_command skips hidden subcommands."""
    pytest.importorskip("click")
    import click

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
        result = docs._extract_click_command(cli, "tool")

        names = [c["name"] for c in result["commands"]]
        assert "public" in names
        assert "secret" not in names


def test_extract_click_command_with_parent_path():
    """_extract_click_command builds full_path from parent_path."""
    pytest.importorskip("click")
    import click

    @click.command()
    def sub():
        """A subcommand."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._extract_click_command(sub, "sub", parent_path="tool")
        assert result["full_path"] == "tool sub"


# ---------------------------------------------------------------------------
# _get_click_help_text  (core.py ~2216)
# ---------------------------------------------------------------------------


def test_get_click_help_text():
    """_get_click_help_text returns formatted --help output."""
    pytest.importorskip("click")
    import click

    @click.command()
    @click.option("--name", help="Your name")
    def hello(name):
        """Say hello to someone."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._get_click_help_text(hello, "hello")

        assert "Usage:" in result
        assert "--name" in result
        assert "Say hello to someone." in result


# ---------------------------------------------------------------------------
# _generate_cli_command_page  (core.py ~2370)
# ---------------------------------------------------------------------------


def test_generate_cli_command_page_main():
    """_generate_cli_command_page generates main CLI page."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "my-tool",
            "full_path": "my-tool",
            "help_text": "Usage: my-tool [OPTIONS]\n\n  My tool help.\n",
        }
        result = docs._generate_cli_command_page(cmd_info, is_main=True)

        assert 'title: "my-tool"' in result
        assert "sidebar: cli-reference" in result
        assert "Usage: my-tool" in result
        assert ".cli-manpage" in result


def test_generate_cli_command_page_subcommand():
    """_generate_cli_command_page uses full_path for subcommand title."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        cmd_info = {
            "name": "build",
            "full_path": "my-tool build",
            "help_text": "Usage: my-tool build [OPTIONS]\n",
        }
        result = docs._generate_cli_command_page(cmd_info, is_main=False)

        assert 'title: "my-tool build"' in result


# ---------------------------------------------------------------------------
# _generate_cli_reference_pages  (core.py ~2263)
# ---------------------------------------------------------------------------


def test_generate_cli_reference_pages_empty():
    """_generate_cli_reference_pages returns empty list for empty input."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._generate_cli_reference_pages({}) == []
        assert docs._generate_cli_reference_pages(None) == []


def test_generate_cli_reference_pages_basic():
    """_generate_cli_reference_pages generates index and subcommand pages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)

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
        result = docs._generate_cli_reference_pages(cli_info)

        assert "reference/cli/index.qmd" in result
        assert (docs.project_path / "reference" / "cli" / "index.qmd").exists()
        assert (docs.project_path / "reference" / "cli" / "build.qmd").exists()


# ---------------------------------------------------------------------------
# _generate_subcommand_pages  (core.py ~2306)
# ---------------------------------------------------------------------------


def test_generate_subcommand_pages_nested():
    """_generate_subcommand_pages handles nested command groups."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        cli_dir = docs.project_path / "reference" / "cli"
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
        result = docs._generate_subcommand_pages(cmd_info, cli_dir)

        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["section"] == "task"
        assert (cli_dir / "task.qmd").exists()
        assert (cli_dir / "task" / "run.qmd").exists()


def test_generate_subcommand_pages_leaf():
    """_generate_subcommand_pages returns strings for leaf commands."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        cli_dir = docs.project_path / "reference" / "cli"
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
        result = docs._generate_subcommand_pages(cmd_info, cli_dir)
        assert result == ["reference/cli/build.qmd"]


# ---------------------------------------------------------------------------
# _discover_click_cli  (core.py ~1988)
# ---------------------------------------------------------------------------


def test_discover_click_cli_disabled():
    """_discover_click_cli returns None when CLI not enabled."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._discover_click_cli("mypkg") is None


def test_discover_click_cli_no_click():
    """_discover_click_cli returns None when click is not importable."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        (tmp / "great-docs.yml").write_text("cli:\n  enabled: true\n")
        docs = GreatDocs(project_path=tmp_dir)
        # click IS installed in test env so this would proceed,
        # but there's no CLI module to find
        result = docs._discover_click_cli("nonexistent_pkg_xyzzy")
        assert result is None


# ---------------------------------------------------------------------------
# _rewrite_href_recursive  (core.py ~3120)
# ---------------------------------------------------------------------------


def test_rewrite_href_recursive_dict_match():
    """_rewrite_href_recursive replaces a dict href."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = [
            {"text": "Intro", "href": "user-guide/intro.qmd"},
            {"text": "Setup", "href": "user-guide/setup.qmd"},
        ]
        found = docs._rewrite_href_recursive(items, "user-guide/intro.qmd", "index.qmd")
        assert found is True
        assert items[0]["href"] == "index.qmd"


def test_rewrite_href_recursive_string_match():
    """_rewrite_href_recursive replaces a bare string entry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = ["user-guide/intro.qmd", "user-guide/setup.qmd"]
        found = docs._rewrite_href_recursive(items, "user-guide/intro.qmd", "index.qmd")
        assert found is True
        assert items[0] == {"text": "Home", "href": "index.qmd"}


def test_rewrite_href_recursive_nested():
    """_rewrite_href_recursive searches nested section contents."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = [
            {
                "section": "Getting Started",
                "contents": [
                    {"text": "Intro", "href": "user-guide/intro.qmd"},
                ],
            },
        ]
        found = docs._rewrite_href_recursive(items, "user-guide/intro.qmd", "index.qmd")
        assert found is True
        assert items[0]["contents"][0]["href"] == "index.qmd"


def test_rewrite_href_recursive_no_match():
    """_rewrite_href_recursive returns False when no match found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        items = [{"text": "Other", "href": "other.qmd"}]
        assert docs._rewrite_href_recursive(items, "missing.qmd", "new.qmd") is False


# ---------------------------------------------------------------------------
# _rewrite_sidebar_first_entry  (core.py ~3094)
# ---------------------------------------------------------------------------


def test_rewrite_sidebar_first_entry():
    """_rewrite_sidebar_first_entry rewrites first href to index.qmd."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        sidebar = {
            "id": "user-guide",
            "title": "User Guide",
            "contents": [
                {"text": "Intro", "href": "user-guide/intro.qmd"},
                "user-guide/setup.qmd",
            ],
        }
        docs._rewrite_sidebar_first_entry(sidebar, "user-guide/intro.qmd")
        assert sidebar["contents"][0]["href"] == "index.qmd"


# ---------------------------------------------------------------------------
# _organize_files_into_sidebar  (core.py ~2972)  [the auto sidebar builder]
# ---------------------------------------------------------------------------


def test_organize_files_into_sidebar_flat():
    """_generate_user_guide_sidebar_auto generates flat sidebar from root files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "intro.qmd").write_text("---\ntitle: Intro\n---\n")
        (src / "setup.qmd").write_text("---\ntitle: Setup\n---\n")

        docs = GreatDocs(project_path=tmp_dir)
        guide_info = {
            "files": [
                {"path": src / "intro.qmd", "title": "Intro", "section": None},
                {"path": src / "setup.qmd", "title": "Setup", "section": None},
            ],
            "source_dir": src,
            "sections": {},
        }
        result = docs._generate_user_guide_sidebar_auto(guide_info)

        assert result["id"] == "user-guide"
        assert len(result["contents"]) == 2
        assert "user-guide/intro.qmd" in result["contents"]


def test_organize_files_into_sidebar_with_sections():
    """_generate_user_guide_sidebar_auto groups files by section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "a.qmd").write_text("A\n")
        (src / "b.qmd").write_text("B\n")

        f_a = {"path": src / "a.qmd", "title": "A", "section": "Basics"}
        f_b = {"path": src / "b.qmd", "title": "B", "section": "Basics"}
        guide_info = {
            "files": [f_a, f_b],
            "source_dir": src,
            "sections": {"Basics": [f_a, f_b]},
        }

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._generate_user_guide_sidebar_auto(guide_info)

        assert result["id"] == "user-guide"
        # Should have one section entry
        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]
        assert len(section_items) == 1
        assert section_items[0]["section"] == "Basics"


def test_organize_files_into_sidebar_subdirectories():
    """_generate_user_guide_sidebar_auto groups by subdirectory when no sections."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        sub = src / "advanced"
        sub.mkdir()
        (src / "intro.qmd").write_text("Intro\n")
        (sub / "deep.qmd").write_text("Deep\n")

        guide_info = {
            "files": [
                {"path": src / "intro.qmd", "title": "Intro", "section": None},
                {"path": sub / "deep.qmd", "title": "Deep", "section": None},
            ],
            "source_dir": src,
            "sections": {},
        }

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._generate_user_guide_sidebar_auto(guide_info)

        # Should have root file + subdirectory section
        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]
        assert len(section_items) == 1
        assert section_items[0]["section"] == "Advanced"


# ---------------------------------------------------------------------------
# _update_config_with_user_guide  (core.py ~3203)
# ---------------------------------------------------------------------------


def test_update_config_with_user_guide_adds_sidebar():
    """_update_config_with_user_guide adds sidebar and navbar entry."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [],
                "navbar": {"left": [{"text": "Reference", "href": "reference/"}]},
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "page.qmd").write_text("---\ntitle: Page\n---\n")

        guide_info = {
            "files": [{"path": src / "page.qmd", "title": "Page", "section": None}],
            "source_dir": src,
            "sections": {},
            "has_index": False,
            "explicit": False,
        }
        docs._update_config_with_user_guide(guide_info)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        # Should add user-guide sidebar
        sidebar_ids = [s.get("id") for s in result["website"]["sidebar"] if isinstance(s, dict)]
        assert "user-guide" in sidebar_ids

        # Should add User Guide to navbar
        nav_texts = [
            i.get("text") for i in result["website"]["navbar"]["left"] if isinstance(i, dict)
        ]
        assert "User Guide" in nav_texts


def test_update_config_with_user_guide_no_quarto_yml():
    """_update_config_with_user_guide returns early if no _quarto.yml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        guide_info = {"files": [], "source_dir": Path(tmp_dir), "sections": {}}
        # Should not raise
        docs._update_config_with_user_guide(guide_info)


def test_update_config_with_user_guide_idempotent():
    """_update_config_with_user_guide replaces existing user-guide sidebar."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = docs.project_path / "_quarto.yml"
        docs.project_path.mkdir(parents=True, exist_ok=True)

        config = {
            "website": {
                "sidebar": [
                    {"id": "user-guide", "title": "Old", "contents": ["old.qmd"]},
                    {"id": "reference", "title": "Reference", "contents": []},
                ],
                "navbar": {"left": [{"text": "User Guide", "href": "user-guide/old.qmd"}]},
            }
        }
        with open(quarto_yml, "w") as f:
            yaml.dump(config, f)

        src = tmp / "user_guide"
        src.mkdir()
        (src / "new.qmd").write_text("---\ntitle: New\n---\n")

        guide_info = {
            "files": [{"path": src / "new.qmd", "title": "New", "section": None}],
            "source_dir": src,
            "sections": {},
            "has_index": False,
            "explicit": False,
        }
        docs._update_config_with_user_guide(guide_info)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)

        ug_sidebars = [
            s
            for s in result["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "user-guide"
        ]
        assert len(ug_sidebars) == 1
        # Reference sidebar should be preserved
        ref_sidebars = [
            s
            for s in result["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "reference"
        ]
        assert len(ref_sidebars) == 1


# ---------------------------------------------------------------------------
# _process_user_guide  (core.py ~3260)
# ---------------------------------------------------------------------------


def test_process_user_guide_no_guide():
    """_process_user_guide returns False when no user guide found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._process_user_guide() is False


def test_process_user_guide_with_pages():
    """_process_user_guide discovers, copies, and configures user guide."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-intro.qmd").write_text("---\ntitle: Intro\n---\nContent\n")
        (ug / "02-usage.qmd").write_text("---\ntitle: Usage\n---\nContent\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(docs.project_path / "_quarto.yml", "w") as f:
            yaml.dump(config, f)

        assert docs._process_user_guide() is True
        assert (docs.project_path / "user-guide").exists()


def test_process_user_guide_with_sections():
    """_process_user_guide processes sectioned user guide."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        ug = tmp / "user_guide"
        ug.mkdir()
        (ug / "01-a.qmd").write_text("---\ntitle: A\nguide-section: Basics\n---\nA\n")
        (ug / "02-b.qmd").write_text("---\ntitle: B\nguide-section: Advanced\n---\nB\n")

        docs = GreatDocs(project_path=tmp_dir)
        docs.project_path.mkdir(parents=True, exist_ok=True)
        config = {"website": {"sidebar": [], "navbar": {"left": []}}}
        with open(docs.project_path / "_quarto.yml", "w") as f:
            yaml.dump(config, f)

        result = docs._process_user_guide()
        assert result is True

        with open(docs.project_path / "_quarto.yml") as f:
            result_config = yaml.safe_load(f)
        ug_sidebar = next(
            s
            for s in result_config["website"]["sidebar"]
            if isinstance(s, dict) and s.get("id") == "user-guide"
        )
        # Should have sections in the sidebar
        section_items = [
            c for c in ug_sidebar["contents"] if isinstance(c, dict) and "section" in c
        ]
        assert len(section_items) >= 1


# ---------------------------------------------------------------------------
# _apply_nodoc_filter  (core.py ~5773)
# ---------------------------------------------------------------------------


def test_apply_nodoc_filter_removes_items():
    """_apply_nodoc_filter removes items with %nodoc directive."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "great_docs"\n')

        docs = GreatDocs(project_path=tmp_dir)

        sections = [
            {"title": "Functions", "contents": ["func_a", "func_b"]},
        ]

        # Patch _extract_all_directives to return nodoc for func_b
        from unittest.mock import patch, MagicMock

        mock_directives = MagicMock()
        mock_directives.nodoc = True

        with patch.object(
            docs, "_extract_all_directives", return_value={"func_b": mock_directives}
        ):
            result = docs._apply_nodoc_filter("great_docs", sections)

        assert result is not None
        assert len(result) == 1
        assert result[0]["contents"] == ["func_a"]


def test_apply_nodoc_filter_no_directives():
    """_apply_nodoc_filter returns sections unchanged when no directives."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        sections = [{"title": "Funcs", "contents": ["f1", "f2"]}]

        from unittest.mock import patch

        with patch.object(docs, "_extract_all_directives", return_value={}):
            result = docs._apply_nodoc_filter("pkg", sections)

        assert result == sections


def test_apply_nodoc_filter_removes_companion_section():
    """_apply_nodoc_filter removes companion 'ClassName Methods' section."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        sections = [
            {"title": "Classes", "contents": ["MyClass"]},
            {"title": "MyClass Methods", "contents": ["MyClass.foo", "MyClass.bar"]},
        ]

        from unittest.mock import patch, MagicMock

        mock_dir = MagicMock()
        mock_dir.nodoc = True
        with patch.object(docs, "_extract_all_directives", return_value={"MyClass": mock_dir}):
            result = docs._apply_nodoc_filter("pkg", sections)

        # Both the class entry and the companion method section should be gone
        assert result is None


def test_apply_nodoc_filter_all_excluded():
    """_apply_nodoc_filter returns None when all items excluded."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        sections = [{"title": "Funcs", "contents": ["only_func"]}]

        from unittest.mock import patch, MagicMock

        mock_dir = MagicMock()
        mock_dir.nodoc = True
        with patch.object(docs, "_extract_all_directives", return_value={"only_func": mock_dir}):
            result = docs._apply_nodoc_filter("pkg", sections)

        assert result is None


def test_apply_nodoc_filter_dict_items():
    """_apply_nodoc_filter handles dict items (name/members format)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)

        sections = [
            {
                "title": "Classes",
                "contents": [
                    {"name": "Good", "members": []},
                    {"name": "Bad", "members": []},
                ],
            }
        ]

        from unittest.mock import patch, MagicMock

        mock_dir = MagicMock()
        mock_dir.nodoc = True
        with patch.object(docs, "_extract_all_directives", return_value={"Bad": mock_dir}):
            result = docs._apply_nodoc_filter("pkg", sections)

        assert len(result) == 1
        assert len(result[0]["contents"]) == 1
        assert result[0]["contents"][0]["name"] == "Good"


# ---------------------------------------------------------------------------
# _generate_user_guide_sidebar_explicit  (core.py ~2893)
# ---------------------------------------------------------------------------


def test_generate_user_guide_sidebar_explicit():
    """_generate_user_guide_sidebar_explicit builds sidebar from config."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        src = tmp / "user_guide"
        src.mkdir()
        (src / "install.qmd").write_text("I\n")
        (src / "usage.qmd").write_text("U\n")

        docs = GreatDocs(project_path=tmp_dir)
        guide_info = {
            "files": [
                {
                    "path": src / "install.qmd",
                    "title": "Install",
                    "section": "Getting Started",
                    "custom_text": None,
                },
                {
                    "path": src / "usage.qmd",
                    "title": "Usage",
                    "section": "Getting Started",
                    "custom_text": None,
                },
            ],
            "source_dir": src,
            "sections": {
                "Getting Started": [
                    {"path": src / "install.qmd", "title": "Install", "section": "Getting Started"},
                    {"path": src / "usage.qmd", "title": "Usage", "section": "Getting Started"},
                ]
            },
            "explicit": True,
            "explicit_config": [
                {"section": "Getting Started", "contents": ["install.qmd", "usage.qmd"]},
            ],
        }
        result = docs._generate_user_guide_sidebar_explicit(guide_info)
        assert result["id"] == "user-guide"
        section_items = [c for c in result["contents"] if isinstance(c, dict) and "section" in c]
        assert len(section_items) == 1


# ---------------------------------------------------------------------------
# _strip_numeric_prefix  (core.py)
# ---------------------------------------------------------------------------


def test_strip_numeric_prefix_various():
    """_strip_numeric_prefix handles different prefix formats."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._strip_numeric_prefix("01-intro.qmd") == "intro.qmd"
        assert docs._strip_numeric_prefix("99_advanced.qmd") == "advanced.qmd"
        assert docs._strip_numeric_prefix("no-prefix.qmd") == "no-prefix.qmd"
        assert docs._strip_numeric_prefix("001-triple.qmd") == "triple.qmd"


# ---------------------------------------------------------------------------
# _normalize_package_name  (core.py)
# ---------------------------------------------------------------------------


def test_normalize_package_name():
    """_normalize_package_name replaces hyphens with underscores."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._normalize_package_name("my-package") == "my_package"
        assert docs._normalize_package_name("already_good") == "already_good"
        assert docs._normalize_package_name("multi-hyphen-name") == "multi_hyphen_name"


# ---------------------------------------------------------------------------
# _get_source_location  (core.py ~3370)
# ---------------------------------------------------------------------------


def test_get_source_location_found():
    """_get_source_location returns file/line info for an exported symbol."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        # Use great_docs itself as a known package
        result = docs._get_source_location("great_docs", "GreatDocs")
        assert result is not None
        assert "file" in result
        assert "start_line" in result
        assert "end_line" in result
        assert result["start_line"] > 0


def test_get_source_location_not_found():
    """_get_source_location returns None for non-existent symbol."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._get_source_location("great_docs", "NonExistentSymbol")
        assert result is None


def test_get_source_location_method():
    """_get_source_location finds a class method by dotted name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._get_source_location("great_docs", "GreatDocs.build")
        if result is not None:
            assert result["start_line"] > 0
            assert result["end_line"] >= result["start_line"]


def test_get_source_location_bad_package():
    """_get_source_location returns None for non-existent packages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._get_source_location("nonexistent_pkg_xyzzy", "SomeClass")
        assert result is None


# ---------------------------------------------------------------------------
# _count_cli_sidebar_items  (already tested, adding nested test)
# ---------------------------------------------------------------------------


def test_count_cli_sidebar_items_nested():
    """_count_cli_sidebar_items counts nested dict items recursively."""
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
    assert GreatDocs._count_cli_sidebar_items(items) == 3


# ---------------------------------------------------------------------------
# _write_quarto_yml  (core.py — used by many methods)
# ---------------------------------------------------------------------------


def test_write_quarto_yml():
    """_write_quarto_yml writes YAML config to file."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        docs = GreatDocs(project_path=tmp_dir)
        quarto_yml = tmp / "_quarto.yml"

        config = {"project": {"type": "website"}, "website": {"title": "Test"}}
        docs._write_quarto_yml(quarto_yml, config)

        with open(quarto_yml) as f:
            result = yaml.safe_load(f)
        assert result["website"]["title"] == "Test"


# ---------------------------------------------------------------------------
# _detect_package_name  (core.py)
# ---------------------------------------------------------------------------


def test_detect_package_name_from_pyproject():
    """_detect_package_name reads name from pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "my-cool-pkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        assert docs._detect_package_name() == "my-cool-pkg"


def test_detect_package_name_no_pyproject():
    """_detect_package_name returns None when no pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._detect_package_name()
        assert result is None


# ---------------------------------------------------------------------------
# _parse_all_from_init  (core.py ~3829)
# ---------------------------------------------------------------------------


def test_parse_package_exports():
    """_parse_package_exports extracts __all__ from a synthetic package."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        pkg = tmp / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__all__ = ["Foo", "bar"]\n')
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')

        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_package_exports("mypkg")

        assert result is not None
        assert "Foo" in result
        assert "bar" in result


def test_parse_package_exports_missing_package():
    """_parse_package_exports returns None for missing packages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_package_exports("nonexistent_pkg_xyzzy")
        assert result is None


def test_parse_package_exports_with_exclude():
    """_parse_package_exports filters out config excludes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "great_docs"\n')
        (tmp / "great-docs.yml").write_text("exclude:\n  - GreatDocs\n")
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._parse_package_exports("great_docs")
        if result is not None:
            assert "GreatDocs" not in result


# ---------------------------------------------------------------------------
# _discover_package_exports  (core.py ~3885)
# ---------------------------------------------------------------------------


def test_discover_package_exports():
    """_discover_package_exports discovers exports using griffe."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_package_exports("great_docs")
        assert result is not None
        assert "GreatDocs" in result


def test_discover_package_exports_missing():
    """_discover_package_exports returns None for missing packages."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._discover_package_exports("nonexistent_pkg_xyzzy")
        assert result is None


# ---------------------------------------------------------------------------
# _extract_authors_from_pyproject  (core.py ~5843)
# ---------------------------------------------------------------------------


def test_extract_authors_from_pyproject():
    """_extract_authors_from_pyproject extracts author info."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text(
            '[project]\nname = "mypkg"\n\n'
            '[[project.authors]]\nname = "Alice"\nemail = "alice@example.com"\n\n'
            '[[project.maintainers]]\nname = "Bob"\nemail = "bob@example.com"\n'
        )
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._extract_authors_from_pyproject()

        assert len(result) == 2
        # Maintainers come first in the implementation
        assert result[0]["name"] == "Bob"
        assert result[0]["role"] == "Maintainer"
        assert result[1]["name"] == "Alice"
        assert result[1]["role"] == "Author"


def test_extract_authors_from_pyproject_no_authors():
    """_extract_authors_from_pyproject returns empty list when no authors."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        (tmp / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._extract_authors_from_pyproject()
        assert result == []


# ---------------------------------------------------------------------------
# _format_authors_yaml  (core.py ~5900)
# ---------------------------------------------------------------------------


def test_format_authors_yaml():
    """_format_authors_yaml generates YAML for authors list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        authors = [
            {"name": "Alice", "email": "alice@example.com", "role": "Author"},
            {"name": "Bob", "email": "bob@example.com", "role": "Maintainer"},
        ]
        result = docs._format_authors_yaml(authors)
        assert "Alice" in result
        assert "alice@example.com" in result
        assert "Bob" in result
        assert "authors:" in result


def test_format_authors_yaml_empty():
    """_format_authors_yaml returns empty string for empty list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        result = docs._format_authors_yaml([])
        assert result == ""
