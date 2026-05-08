from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from great_docs._skill_install import (
    _find_existing_installations,
    _find_package_skills,
    _parse_frontmatter,
    _resolve_skill_dir,
    check_skill,
    detect_agents,
    install_skill,
    list_skills,
)


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        content = "---\nname: my-skill\ndescription: A skill\n---\n\n# Body"
        fm, body = _parse_frontmatter(content)
        assert fm["name"] == "my-skill"
        assert fm["description"] == "A skill"
        assert body.startswith("# Body")

    def test_no_frontmatter(self):
        content = "# Just a heading\n\nSome text."
        fm, body = _parse_frontmatter(content)
        assert fm == {}
        assert body == content

    def test_empty_frontmatter(self):
        content = "---\n---\n\n# Body"
        fm, body = _parse_frontmatter(content)
        assert fm == {}

    def test_invalid_yaml(self):
        content = "---\n: invalid: yaml: [[\n---\n\nBody"
        fm, body = _parse_frontmatter(content)
        assert fm == {}

    def test_frontmatter_with_metadata(self):
        content = (
            "---\nname: pkg\ndescription: desc\n"
            "metadata:\n  version: '1.0'\n  author: test\n---\n\nBody"
        )
        fm, body = _parse_frontmatter(content)
        assert fm["name"] == "pkg"
        assert fm["metadata"]["version"] == "1.0"


# ---------------------------------------------------------------------------
# detect_agents
# ---------------------------------------------------------------------------


class TestDetectAgents:
    def test_no_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert detect_agents(Path(tmp)) == []

    def test_detect_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".claude").mkdir()
            agents = detect_agents(Path(tmp))
            assert "claude" in agents

    def test_detect_copilot(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".github").mkdir()
            agents = detect_agents(Path(tmp))
            assert "copilot" in agents

    def test_detect_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".cursor").mkdir()
            agents = detect_agents(Path(tmp))
            assert "cursor" in agents

    def test_detect_multiple(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".claude").mkdir()
            (Path(tmp) / ".cursor").mkdir()
            agents = detect_agents(Path(tmp))
            assert "claude" in agents
            assert "cursor" in agents

    def test_detect_windsurf(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".windsurf").mkdir()
            agents = detect_agents(Path(tmp))
            assert "windsurf" in agents


# ---------------------------------------------------------------------------
# _resolve_skill_dir
# ---------------------------------------------------------------------------


class TestResolveSkillDir:
    def test_claude_local(self):
        root = Path("/project")
        result = _resolve_skill_dir("claude", "my-pkg", root=root)
        assert result == Path("/project/.claude/skills/my-pkg")

    def test_copilot_local(self):
        root = Path("/project")
        result = _resolve_skill_dir("copilot", "my-pkg", root=root)
        assert result == Path("/project/.github/skills/my-pkg")

    def test_cursor_local(self):
        root = Path("/project")
        result = _resolve_skill_dir("cursor", "my-pkg", root=root)
        assert result == Path("/project/.cursor/skills/my-pkg")

    def test_global(self):
        result = _resolve_skill_dir("claude", "my-pkg", global_=True)
        expected = Path.home() / ".claude" / "skills" / "my-pkg"
        assert result == expected

    def test_explicit_path(self):
        root = Path("/project")
        result = _resolve_skill_dir("claude", "my-pkg", path="custom/dir", root=root)
        assert result == Path("/project/custom/dir")

    def test_explicit_absolute_path(self):
        result = _resolve_skill_dir("claude", "my-pkg", path="/abs/path")
        assert result == Path("/abs/path")


# ---------------------------------------------------------------------------
# install_skill
# ---------------------------------------------------------------------------


class TestInstallSkill:
    def test_install_from_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()

            content = "---\nname: test-pkg\ndescription: A test\n---\n\n# Test"
            results = install_skill(
                skill_content=content,
                root=root,
            )
            assert len(results) == 1
            installed = results[0]
            assert installed.name == "SKILL.md"
            assert installed.exists()
            assert installed.read_text() == content

    def test_install_to_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "---\nname: my-pkg\n---\n\n# Body"

            results = install_skill(
                skill_content=content,
                path="custom/skills/my-pkg",
                root=root,
            )
            assert len(results) == 1
            assert (root / "custom" / "skills" / "my-pkg" / "SKILL.md").exists()

    def test_install_with_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "---\nname: my-pkg\n---\n\n# Body"
            extras = {
                "references/config.md": "# Config Reference",
                "references/errors.md": "# Error Guide",
            }

            results = install_skill(
                skill_content=content,
                path="custom/my-pkg",
                root=root,
                extra_files=extras,
            )
            assert len(results) == 1
            base = root / "custom" / "my-pkg"
            assert (base / "SKILL.md").exists()
            assert (base / "references" / "config.md").exists()
            assert (base / "references" / "errors.md").read_text() == "# Error Guide"

    def test_install_defaults_to_claude(self):
        """When no agent detected, defaults to Claude Code."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "---\nname: my-pkg\n---\n\n# Body"

            results = install_skill(
                skill_content=content,
                root=root,
            )
            assert len(results) == 1
            assert ".claude/skills/my-pkg/SKILL.md" in str(results[0])

    def test_install_to_multiple_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".cursor").mkdir()

            content = "---\nname: my-pkg\n---\n\n# Body"
            results = install_skill(
                skill_content=content,
                root=root,
            )
            assert len(results) == 2
            paths = [str(r) for r in results]
            assert any(".claude/skills/my-pkg/SKILL.md" in p for p in paths)
            assert any(".cursor/skills/my-pkg/SKILL.md" in p for p in paths)

    def test_install_with_explicit_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "---\nname: my-pkg\n---\n\n# Body"

            results = install_skill(
                skill_content=content,
                agent="cursor",
                root=root,
            )
            assert len(results) == 1
            assert ".cursor/skills/my-pkg/SKILL.md" in str(results[0])

    def test_install_with_name_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = "---\nname: original\n---\n\n# Body"

            results = install_skill(
                skill_content=content,
                skill_name="custom-name",
                agent="claude",
                root=root,
            )
            assert len(results) == 1
            assert "custom-name" in str(results[0])

    def test_install_no_source_error(self):
        results = install_skill(quiet=True)
        assert results == []

    def test_install_from_package(self):
        """Test installing from a package with bundled skills."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create a fake package with skills
            pkg_dir = Path(tmp) / "fake_pkg"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("__file__ = __file__\n")
            skills_dir = pkg_dir / "skills" / "fake-pkg"
            skills_dir.mkdir(parents=True)
            skill_content = "---\nname: fake-pkg\ndescription: Fake\n---\n\n# Fake"
            (skills_dir / "SKILL.md").write_text(skill_content)
            (skills_dir / "extra.md").write_text("# Extra")

            # Mock the import to return our fake package
            import types

            fake_mod = types.ModuleType("fake_pkg")
            fake_mod.__file__ = str(pkg_dir / "__init__.py")  # type: ignore[attr-defined]

            with patch.dict("sys.modules", {"fake_pkg": fake_mod}):
                results = install_skill(
                    package="fake-pkg",
                    agent="claude",
                    root=root,
                )
                assert len(results) == 1
                installed = results[0]
                assert installed.exists()
                assert installed.read_text() == skill_content

    def test_install_from_package_not_found(self):
        results = install_skill(package="nonexistent-xyz-pkg-12345", quiet=True)
        assert results == []


# ---------------------------------------------------------------------------
# check_skill
# ---------------------------------------------------------------------------


class TestCheckSkill:
    def test_check_no_installations(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = check_skill(root=Path(tmp), quiet=True)
            assert results == []

    def test_check_installed_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".claude" / "skills" / "my-pkg"
            skill_dir.mkdir(parents=True)
            content = (
                "---\nname: my-pkg\nmetadata:\n"
                "  version: '1.0'\n  package_version: '0.5.0'\n---\n\n# Body"
            )
            (skill_dir / "SKILL.md").write_text(content)

            results = check_skill(root=root, quiet=True)
            assert len(results) == 1
            assert results[0]["name"] == "my-pkg"
            assert results[0]["installed_pkg_version"] == "0.5.0"
            assert results[0]["agent"] == "claude"

    def test_check_multiple_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for agent_dir in [".claude/skills/pkg", ".cursor/skills/pkg"]:
                d = root / agent_dir
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(
                    "---\nname: pkg\nmetadata:\n  version: '2.0'\n---\n\nBody"
                )

            results = check_skill(root=root, quiet=True)
            assert len(results) == 2
            agents = {r["agent"] for r in results}
            assert agents == {"claude", "cursor"}


# ---------------------------------------------------------------------------
# list_skills
# ---------------------------------------------------------------------------


class TestListSkills:
    def test_list_from_package(self):
        """Test listing skills from a fake package."""
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "fake_pkg"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")
            skills_dir = pkg_dir / "skills" / "fake-pkg"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text(
                "---\nname: fake-pkg\ndescription: A fake package\n"
                "metadata:\n  version: '3.0'\n---\n\n# Fake"
            )

            import types

            fake_mod = types.ModuleType("fake_pkg")
            fake_mod.__file__ = str(pkg_dir / "__init__.py")  # type: ignore[attr-defined]

            with patch.dict("sys.modules", {"fake_pkg": fake_mod}):
                results = list_skills(package="fake-pkg", quiet=True)
                assert len(results) == 1
                assert results[0]["name"] == "fake-pkg"
                assert results[0]["description"] == "A fake package"
                assert results[0]["version"] == "3.0"

    def test_list_no_package(self):
        results = list_skills(package="nonexistent-xyz-pkg-12345", quiet=True)
        assert results == []


# ---------------------------------------------------------------------------
# _find_package_skills
# ---------------------------------------------------------------------------


class TestFindPackageSkills:
    def test_nonexistent_package(self):
        assert _find_package_skills("nonexistent-xyz-pkg-12345") == []

    def test_package_with_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "test_pkg"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")
            skills_dir = pkg_dir / "skills" / "test-pkg"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text("---\nname: test-pkg\n---\n\n# Test")

            import types

            fake_mod = types.ModuleType("test_pkg")
            fake_mod.__file__ = str(pkg_dir / "__init__.py")  # type: ignore[attr-defined]

            with patch.dict("sys.modules", {"test_pkg": fake_mod}):
                results = _find_package_skills("test-pkg")
                assert len(results) == 1
                assert results[0].name == "SKILL.md"

    def test_package_without_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "bare_pkg"
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")

            import types

            fake_mod = types.ModuleType("bare_pkg")
            fake_mod.__file__ = str(pkg_dir / "__init__.py")  # type: ignore[attr-defined]

            with patch.dict("sys.modules", {"bare_pkg": fake_mod}):
                results = _find_package_skills("bare-pkg")
                assert results == []


# ---------------------------------------------------------------------------
# _find_existing_installations
# ---------------------------------------------------------------------------


class TestFindExistingInstallations:
    def test_no_installations(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert _find_existing_installations(Path(tmp)) == []

    def test_finds_claude_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".claude" / "skills" / "some-pkg"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# skill")

            found = _find_existing_installations(root)
            assert "claude" in found


# ---------------------------------------------------------------------------
# Multi-skill support in core.py
# ---------------------------------------------------------------------------


class TestMultiSkillWellKnown:
    """Test that multiple skills produce a combined index.json."""

    def test_multi_skill_index_json(self):
        from great_docs.core import GreatDocs

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create pyproject.toml
            pyproject = Path(tmp_dir) / "pyproject.toml"
            pyproject.write_text('[project]\nname = "multi-pkg"\ndescription = "Multi"\n')

            # Create skills directory
            skills_dir = Path(tmp_dir) / "skills"
            for name, desc in [
                ("authoring", "Authoring pages skill"),
                ("reviewing", "Reviewing sites skill"),
            ]:
                d = skills_dir / name
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}"
                )

            # Create great-docs.yml with multi-skill config
            config_path = Path(tmp_dir) / "great-docs.yml"
            config_path.write_text(
                "skill:\n"
                "  enabled: true\n"
                "  well_known: true\n"
                "  skills:\n"
                "    - name: authoring\n"
                "      file: skills/authoring/SKILL.md\n"
                "    - name: reviewing\n"
                "      file: skills/reviewing/SKILL.md\n"
            )

            # Create great-docs directory and _quarto.yml
            great_docs_dir = Path(tmp_dir) / "great-docs"
            great_docs_dir.mkdir()
            (great_docs_dir / "_quarto.yml").write_text(
                "api-reference:\n  package: multi_pkg\n  sections: []\n"
            )

            docs = GreatDocs(project_path=tmp_dir)
            docs._generate_skill_md()

            # Check primary skill.md was created
            primary = great_docs_dir / "skill.md"
            assert primary.exists()
            assert "authoring" in primary.read_text()

            # Check .well-known/agent-skills/index.json has both skills
            index_path = great_docs_dir / ".well-known" / "agent-skills" / "index.json"
            assert index_path.exists()
            index_data = json.loads(index_path.read_text())
            assert len(index_data["skills"]) == 2
            names = {s["name"] for s in index_data["skills"]}
            assert names == {"authoring", "reviewing"}

            # Check individual skill directories
            for name in ["authoring", "reviewing"]:
                skill_md = great_docs_dir / ".well-known" / "agent-skills" / name / "SKILL.md"
                assert skill_md.exists()

            # Check legacy fallback uses first skill
            legacy = great_docs_dir / ".well-known" / "skills" / "default" / "SKILL.md"
            assert legacy.exists()
            assert "authoring" in legacy.read_text()


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


class TestSkillCLI:
    def test_skill_help(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output
        assert "check" in result.output
        assert "list" in result.output

    def test_skill_install_help(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "install", "--help"])
        assert result.exit_code == 0
        assert "--global" in result.output
        assert "--path" in result.output
        assert "--agent" in result.output

    def test_skill_check_help(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "check", "--help"])
        assert result.exit_code == 0
        assert "--update" in result.output

    def test_skill_list_help(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "list", "--help"])
        assert result.exit_code == 0
        assert "--url" in result.output

    def test_skill_install_no_source(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["skill", "install"])
            assert result.exit_code != 0

    def test_skill_check_empty(self):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["skill", "check"])
            assert result.exit_code == 0
            assert "No installed skills found" in result.output

    def test_skill_install_from_url_live(self):
        """Integration test: install from the live Great Docs site."""
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                [
                    "skill",
                    "install",
                    "https://posit-dev.github.io/great-docs/",
                    "--agent",
                    "claude",
                ],
            )
            assert result.exit_code == 0
            assert Path(".claude/skills/great-docs/SKILL.md").exists()


# ---------------------------------------------------------------------------
# Config property tests
# ---------------------------------------------------------------------------


class TestConfigSkillSkills:
    def test_default_empty(self):
        from great_docs.config import Config

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(Path(tmp))
            assert cfg.skill_skills == []

    def test_multi_skill_config(self):
        from great_docs.config import Config

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "great-docs.yml"
            config_path.write_text(
                "skill:\n"
                "  skills:\n"
                "    - name: a\n"
                "      file: skills/a/SKILL.md\n"
                "    - name: b\n"
                "      file: skills/b/SKILL.md\n"
            )
            cfg = Config(Path(tmp))
            assert len(cfg.skill_skills) == 2
            assert cfg.skill_skills[0]["name"] == "a"
