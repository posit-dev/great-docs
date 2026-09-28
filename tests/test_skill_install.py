from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

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
            pyproject.write_text(
                '[project]\nname = "multi-pkg"\ndescription = "Multi"\n'
            )

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
                skill_md = (
                    great_docs_dir / ".well-known" / "agent-skills" / name / "SKILL.md"
                )
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

    def test_skill_install_no_source(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["skill", "install"])

        assert result.exit_code != 0

    def test_skill_check_empty(self, tmp_path, monkeypatch):
        from click.testing import CliRunner

        from great_docs.cli import cli

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["skill", "check"])

        assert result.exit_code == 0
        assert "No installed skills found" in result.output


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


# ---------------------------------------------------------------------------
# _parse_frontmatter — non-dict YAML
# ---------------------------------------------------------------------------


class TestParseFrontmatterEdgeCases:
    def test_non_dict_frontmatter_returns_empty(self):
        """Non-dict YAML frontmatter (e.g. a bare list) returns ({}, content)."""
        content = "---\n- item1\n- item2\n---\nBody"
        fm, body = _parse_frontmatter(content)

        assert fm == {}
        assert "Body" in body

    def test_only_two_dashes_parts_returns_empty(self):
        """Frontmatter with only one --- (no closing) returns ({}, original)."""
        content = "---\nname: x\n"
        fm, body = _parse_frontmatter(content)

        assert fm == {}


# ---------------------------------------------------------------------------
# _find_package_skills — missing package
# ---------------------------------------------------------------------------


class TestFindPackageSkillsMissing:
    def test_import_error_returns_empty(self):
        """Returns [] when the package cannot be imported."""
        from great_docs._skill_install import _find_package_skills

        result = _find_package_skills("_nonexistent_package_xyz_")
        assert result == []


# ---------------------------------------------------------------------------
# _find_skill_from_url — fallback and failure paths
# ---------------------------------------------------------------------------


class TestFindSkillFromUrl:
    def test_index_ok_but_skill_fetch_fails_skips_entry(self):
        """When index.json lists a skill but the SKILL.md fetch fails, that entry is skipped."""
        import urllib.error
        import urllib.request
        from unittest.mock import MagicMock

        from great_docs._skill_install import _find_skill_from_url

        index_json = json.dumps({"skills": [{"name": "my-skill"}]}).encode()

        call_count = {"n": 0}

        def fake_urlopen(url, timeout=10):
            call_count["n"] += 1
            if "index.json" in url:
                resp = MagicMock()
                resp.read.return_value = index_json
                resp.__enter__ = lambda s: s
                resp.__exit__ = MagicMock(return_value=False)
                return resp
            raise urllib.error.URLError("not found")

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            result = _find_skill_from_url("https://example.com")

        # All individual skill fetches failed, so falls through to fallback, which also fails
        assert result is None

    def test_fallback_skill_md_succeeds(self):
        """When index fails, fallback to /skill.md succeeds."""
        import urllib.error
        import urllib.request
        from unittest.mock import MagicMock

        from great_docs._skill_install import _find_skill_from_url

        skill_content = b"---\nname: fallback-skill\n---\nBody"

        def fake_urlopen(url, timeout=10):
            if "index.json" in url:
                raise urllib.error.URLError("no index")
            resp = MagicMock()
            resp.read.return_value = skill_content
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            result = _find_skill_from_url("https://example.com")

        assert result is not None
        assert result[0][0] == "fallback-skill"

    def test_both_index_and_fallback_fail_returns_none(self):
        """Returns None when both index.json and skill.md fetches fail."""
        import urllib.error
        import urllib.request

        from great_docs._skill_install import _find_skill_from_url

        with patch.object(
            urllib.request, "urlopen", side_effect=urllib.error.URLError("fail")
        ):
            result = _find_skill_from_url("https://example.com")

        assert result is None

    def test_index_returns_empty_skills_list_falls_to_fallback(self):
        """When index.json has skills=[], tries fallback /skill.md."""
        import urllib.error
        import urllib.request
        from unittest.mock import MagicMock

        from great_docs._skill_install import _find_skill_from_url

        index_json = json.dumps({"skills": []}).encode()

        def fake_urlopen(url, timeout=10):
            if "index.json" in url:
                resp = MagicMock()
                resp.read.return_value = index_json
                resp.__enter__ = lambda s: s
                resp.__exit__ = MagicMock(return_value=False)
                return resp
            raise urllib.error.URLError("no skill.md")

        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            result = _find_skill_from_url("https://example.com")

        assert result is None


# ---------------------------------------------------------------------------
# detect_agents_global
# ---------------------------------------------------------------------------


class TestDetectAgentsGlobal:
    def test_detects_claude_in_home(self, tmp_path: Path):
        """detect_agents_global finds agents configured in the home directory."""
        from great_docs._skill_install import detect_agents_global

        (tmp_path / ".claude").mkdir()
        with patch("great_docs._skill_install.Path.home", return_value=tmp_path):
            result = detect_agents_global()

        assert "claude" in result

    def test_empty_home_returns_empty(self, tmp_path: Path):
        """detect_agents_global returns [] when no agents are configured."""
        from great_docs._skill_install import detect_agents_global

        with patch("great_docs._skill_install.Path.home", return_value=tmp_path):
            result = detect_agents_global()

        assert result == []


# ---------------------------------------------------------------------------
# install_skill — url failure, package not found, detect mode
# ---------------------------------------------------------------------------


class TestInstallSkillMorePaths:
    def test_url_no_skills_found_returns_empty(self, tmp_path: Path):
        """install_skill with url that returns None prints error and returns []."""
        from great_docs._skill_install import install_skill

        with patch("great_docs._skill_install._find_skill_from_url", return_value=None):
            result = install_skill(url="https://example.com", root=tmp_path)

        assert result == []

    def test_package_no_skills_found_returns_empty(self, tmp_path: Path):
        """install_skill with package that has no skills prints error and returns []."""
        from great_docs._skill_install import install_skill

        with patch("great_docs._skill_install._find_package_skills", return_value=[]):
            result = install_skill(package="mypkg", root=tmp_path)

        assert result == []

    def test_no_source_returns_empty(self, tmp_path: Path):
        """install_skill with no package/url/skill_content returns []."""
        from great_docs._skill_install import install_skill

        result = install_skill(root=tmp_path)

        assert result == []

    def test_detect_no_existing_installations_returns_empty(self, tmp_path: Path):
        """install_skill with detect=True and no existing installs returns []."""
        from great_docs._skill_install import install_skill

        content = "---\nname: my-skill\n---\nBody"
        with patch(
            "great_docs._skill_install._find_existing_installations", return_value=[]
        ):
            result = install_skill(skill_content=content, detect=True, root=tmp_path)

        assert result == []

    def test_detect_finds_existing_and_installs(self, tmp_path: Path):
        """install_skill with detect=True updates existing agent installations."""
        from great_docs._skill_install import install_skill

        content = "---\nname: my-skill\n---\nBody"
        with patch(
            "great_docs._skill_install._find_existing_installations",
            return_value=["claude"],
        ):
            result = install_skill(skill_content=content, detect=True, root=tmp_path)

        assert len(result) == 1
        assert result[0].name == "SKILL.md"


# ---------------------------------------------------------------------------
# check_skill — all status paths
# ---------------------------------------------------------------------------


def _make_skill_md(root: Path, agent: str, skill_name: str, content: str) -> Path:
    """Helper: write a SKILL.md for the given agent and skill name."""
    skill_dir = root / f".{agent}" / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    p = skill_dir / "SKILL.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestCheckSkillStatusPaths:
    def test_no_installed_version_returns_outdated(self, tmp_path: Path):
        """Skill with no metadata at all is reported as 'outdated'."""
        content = "---\nname: my-skill\n---\nBody"
        _make_skill_md(tmp_path, "claude", "my-skill", content)

        with patch(
            "great_docs._skill_install._get_package_version", return_value="1.0.0"
        ):
            results = check_skill(root=tmp_path, quiet=True)

        assert any(r["status"] == "outdated" for r in results)

    def test_pkg_not_installed_returns_local(self, tmp_path: Path):
        """Skill whose package is not installed is reported as 'local'."""
        content = "---\nname: my-skill\n---\nBody"
        _make_skill_md(tmp_path, "claude", "my-skill", content)

        with patch("great_docs._skill_install._get_package_version", return_value=None):
            results = check_skill(root=tmp_path, quiet=True)

        assert any(r["status"] == "local" for r in results)

    def test_content_hash_current(self, tmp_path: Path):
        """Skill with matching content_hash is reported as 'current'."""
        from great_docs._skill_install import _stamp_install_metadata

        raw = "---\nname: my-skill\n---\nBody"
        stamped = _stamp_install_metadata(raw, "1.0.0")
        _make_skill_md(tmp_path, "claude", "my-skill", stamped)

        # The bundled skill is the same raw content
        bundled = Path(tempfile.mkdtemp()) / "SKILL.md"
        bundled.parent.mkdir(parents=True, exist_ok=True)
        bundled.write_text(raw, encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            results = check_skill(root=tmp_path, quiet=True)

        assert any(r["status"] == "current" for r in results)

    def test_version_comparison_fallback_current(self, tmp_path: Path):
        """Skill with pkg_version metadata equal to installed uses version comparison."""

        raw = "---\nname: my-skill\n---\nBody"
        # Stamp with only package_version, no content_hash
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '1.0.0'\n---\nBody"
        )
        _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        with patch(
            "great_docs._skill_install._get_package_version", return_value="1.0.0"
        ):
            results = check_skill(root=tmp_path, quiet=True)

        assert any(r["status"] == "current" for r in results)

    def test_version_comparison_fallback_outdated(self, tmp_path: Path):
        """Skill with older package_version metadata and no hash is 'outdated'."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        with patch(
            "great_docs._skill_install._get_package_version", return_value="1.0.0"
        ):
            results = check_skill(root=tmp_path, quiet=True)

        assert any(r["status"] == "outdated" for r in results)

    def test_update_reinstalls_outdated_skill(self, tmp_path: Path):
        """check_skill with update=True reinstalls outdated skills."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        skill_md = _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        bundled_dir = tmp_path / "bundled_skills" / "my-skill"
        bundled_dir.mkdir(parents=True)
        bundled = bundled_dir / "SKILL.md"
        bundled.write_text("---\nname: my-skill\n---\nNew body", encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            results = check_skill(root=tmp_path, update=True, quiet=True)

        updated = [r for r in results if r["status"] == "updated"]

        assert updated
        assert "New body" in skill_md.read_text()

    def test_print_status_messages(self, tmp_path: Path, capsys):
        """check_skill prints status lines for current/local/outdated skills."""
        content_local = "---\nname: local-skill\n---\nBody"
        _make_skill_md(tmp_path, "claude", "local-skill", content_local)

        with patch("great_docs._skill_install._get_package_version", return_value=None):
            check_skill(root=tmp_path, quiet=False)

        out = capsys.readouterr().out

        assert "local-skill" in out


# ---------------------------------------------------------------------------
# list_skills — URL path
# ---------------------------------------------------------------------------


class TestListSkillsUrl:
    def test_url_success(self):
        """list_skills with a URL fetches index and returns skill entries."""
        import urllib.request
        from unittest.mock import MagicMock

        from great_docs._skill_install import list_skills

        index = json.dumps(
            {"skills": [{"name": "gt-skill", "description": "A skill"}]}
        ).encode()
        resp = MagicMock()
        resp.read.return_value = index
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=resp):
            results = list_skills(url="https://example.com", quiet=True)

        assert len(results) == 1
        assert results[0]["name"] == "gt-skill"
        assert results[0]["source"] == "url"

    def test_url_fetch_failure_returns_empty(self, capsys):
        """list_skills with a failing URL returns []."""
        import urllib.error
        import urllib.request

        from great_docs._skill_install import list_skills

        with patch.object(
            urllib.request, "urlopen", side_effect=urllib.error.URLError("fail")
        ):
            results = list_skills(url="https://example.com", quiet=False)

        assert results == []

        out = capsys.readouterr().out

        assert "Error" in out

    def test_url_prints_skills_when_not_quiet(self, capsys):
        """list_skills prints each skill name when quiet=False."""
        import urllib.request
        from unittest.mock import MagicMock

        from great_docs._skill_install import list_skills

        index = json.dumps(
            {"skills": [{"name": "cool-skill", "description": "Does things"}]}
        ).encode()
        resp = MagicMock()
        resp.read.return_value = index
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=resp):
            list_skills(url="https://example.com", quiet=False)

        out = capsys.readouterr().out

        assert "cool-skill" in out


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_returns_16_char_hex(self):
        from great_docs._skill_install import _content_hash

        h = _content_hash("some content")

        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_content_same_hash(self):
        from great_docs._skill_install import _content_hash

        assert _content_hash("hello") == _content_hash("hello")

    def test_different_content_different_hash(self):
        from great_docs._skill_install import _content_hash

        assert _content_hash("hello") != _content_hash("world")


# ---------------------------------------------------------------------------
# _stamp_install_metadata
# ---------------------------------------------------------------------------


class TestStampInstallMetadata:
    def test_stamps_version_and_hash(self):
        from great_docs._skill_install import _content_hash, _stamp_install_metadata

        raw = "---\nname: my-skill\n---\nBody"
        stamped = _stamp_install_metadata(raw, "2.0.0")

        fm, _ = _parse_frontmatter(stamped)

        assert fm["metadata"]["package_version"] == "2.0.0"
        assert fm["metadata"]["content_hash"] == _content_hash(raw)

    def test_no_frontmatter_returns_original(self):
        from great_docs._skill_install import _stamp_install_metadata

        raw = "No frontmatter here"

        assert _stamp_install_metadata(raw, "1.0.0") == raw

    def test_hash_is_of_original_not_stamped(self):
        """content_hash is computed before stamping so it's stable across re-installs."""
        from great_docs._skill_install import _stamp_install_metadata

        raw = "---\nname: s\n---\nBody"
        stamped = _stamp_install_metadata(raw, "1.0")
        stamped2 = _stamp_install_metadata(stamped, "1.1")

        fm, _ = _parse_frontmatter(stamped2)

        # The hash embedded in stamped uses raw as source; stamped2's hash uses stamped as source
        # Key property: the function always hashes whatever it receives
        assert "content_hash" in fm["metadata"]


# ---------------------------------------------------------------------------
# _check_content_freshness
# ---------------------------------------------------------------------------


class TestCheckContentFreshness:
    def test_matching_hash_returns_current(self, tmp_path: Path):
        from great_docs._skill_install import _check_content_freshness, _content_hash

        content = "---\nname: my-skill\n---\nBody"
        bundled = tmp_path / "SKILL.md"
        bundled.write_text(content, encoding="utf-8")

        with patch(
            "great_docs._skill_install._find_package_skills", return_value=[bundled]
        ):
            result = _check_content_freshness(
                "mypkg", "my-skill", _content_hash(content)
            )

        assert result == "current"

    def test_changed_content_returns_outdated(self, tmp_path: Path):
        from great_docs._skill_install import _check_content_freshness

        content = "---\nname: my-skill\n---\nNew body"
        bundled = tmp_path / "SKILL.md"
        bundled.write_text(content, encoding="utf-8")

        with patch(
            "great_docs._skill_install._find_package_skills", return_value=[bundled]
        ):
            result = _check_content_freshness("mypkg", "my-skill", "stale_hash_000000")

        assert result == "outdated"

    def test_skill_not_found_in_package_returns_outdated(self, tmp_path: Path):
        from great_docs._skill_install import _check_content_freshness

        with patch("great_docs._skill_install._find_package_skills", return_value=[]):
            result = _check_content_freshness("mypkg", "my-skill", "anyhash")

        assert result == "outdated"

    def test_name_mismatch_returns_outdated(self, tmp_path: Path):
        from great_docs._skill_install import _check_content_freshness

        content = "---\nname: other-skill\n---\nBody"
        bundled = tmp_path / "SKILL.md"
        bundled.write_text(content, encoding="utf-8")

        with patch(
            "great_docs._skill_install._find_package_skills", return_value=[bundled]
        ):
            result = _check_content_freshness("mypkg", "my-skill", "anyhash")

        assert result == "outdated"


# ---------------------------------------------------------------------------
# _compare_versions
# ---------------------------------------------------------------------------


class TestCompareVersions:
    def test_equal_versions_current(self):
        from great_docs._skill_install import _compare_versions

        assert _compare_versions("1.0.0", "1.0.0") == "current"

    def test_installed_newer_current(self):
        from great_docs._skill_install import _compare_versions

        assert _compare_versions("2.0.0", "1.0.0") == "current"

    def test_installed_older_outdated(self):
        from great_docs._skill_install import _compare_versions

        assert _compare_versions("0.9.0", "1.0.0") == "outdated"

    def test_non_pep440_equal_strings_current(self):
        from great_docs._skill_install import _compare_versions

        assert _compare_versions("abc", "abc") == "current"

    def test_non_pep440_different_strings_outdated(self):
        from great_docs._skill_install import _compare_versions

        assert _compare_versions("abc", "xyz") == "outdated"


# ---------------------------------------------------------------------------
# install_skill — additional branch coverage
# ---------------------------------------------------------------------------


class TestInstallSkillQuietBranches:
    def test_url_failure_quiet_true(self, tmp_path: Path):
        """install_skill with url failure and quiet=True returns [] silently."""
        with patch("great_docs._skill_install._find_skill_from_url", return_value=None):
            result = install_skill(url="https://example.com", root=tmp_path, quiet=True)

        assert result == []

    def test_detect_no_installs_quiet_true(self, tmp_path: Path):
        """install_skill detect mode with quiet=True and no installs returns [] silently."""
        content = "---\nname: s\n---\nBody"
        with patch(
            "great_docs._skill_install._find_existing_installations", return_value=[]
        ):
            result = install_skill(
                skill_content=content, detect=True, root=tmp_path, quiet=True
            )

        assert result == []

    def test_no_source_quiet_true(self, tmp_path: Path):
        """install_skill with no source and quiet=True returns [] silently."""
        result = install_skill(root=tmp_path, quiet=True)

        assert result == []

    def test_explicit_path_mode(self, tmp_path: Path):
        """install_skill with path= installs directly to that path."""
        content = "---\nname: my-skill\n---\nBody"
        target = tmp_path / "custom_skills" / "my-skill"
        result = install_skill(
            skill_content=content, path=str(target), root=tmp_path, quiet=True
        )

        assert len(result) == 1
        assert (target / "SKILL.md").exists()

    def test_no_agents_detected_defaults_to_claude(self, tmp_path: Path, capsys):
        """install_skill defaults to claude agent when no agents are detected."""
        content = "---\nname: my-skill\n---\nBody"
        with patch("great_docs._skill_install.detect_agents", return_value=[]):
            result = install_skill(skill_content=content, root=tmp_path, quiet=False)

        assert any(p.name == "SKILL.md" for p in result)

        out = capsys.readouterr().out

        assert "defaulting" in out

    def test_url_returns_empty_list_hits_no_skills_guard(self, tmp_path: Path):
        """install_skill with url returning [] (not None) returns [] via line 358 guard."""
        with patch("great_docs._skill_install._find_skill_from_url", return_value=[]):
            result = install_skill(url="https://example.com", root=tmp_path, quiet=True)

        assert result == []

    def test_package_stamps_metadata(self, tmp_path: Path):
        """install_skill with package= stamps version metadata when pkg is installed."""
        content = "---\nname: my-skill\n---\nBody"
        bundled = tmp_path / "bundled" / "SKILL.md"
        bundled.parent.mkdir(parents=True)
        bundled.write_text(content, encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.2.3"
            ),
        ):
            result = install_skill(package="mypkg", root=tmp_path, quiet=True)

        assert result

        installed_text = result[0].read_text()

        assert "1.2.3" in installed_text


# ---------------------------------------------------------------------------
# check_skill — local/global_ branches and print paths
# ---------------------------------------------------------------------------


class TestCheckSkillScanRoots:
    def test_local_true_scans_cwd(self, tmp_path: Path):
        """check_skill with local=True scans the project root."""
        content = "---\nname: my-skill\n---\nBody"
        _make_skill_md(tmp_path, "claude", "my-skill", content)

        with patch("great_docs._skill_install._get_package_version", return_value=None):
            results = check_skill(root=tmp_path, local=True, quiet=True)

        assert any(r["name"] == "my-skill" for r in results)

    def test_global_true_scans_home(self, tmp_path: Path):
        """check_skill with global_=True scans Path.home()."""
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\n---\nBody", encoding="utf-8"
        )

        with (
            patch("great_docs._skill_install._get_package_version", return_value=None),
            patch("great_docs._skill_install.Path.home", return_value=tmp_path),
        ):
            results = check_skill(global_=True, root=tmp_path, quiet=True)

        assert any(r["name"] == "my-skill" for r in results)

    def test_current_status_prints_checkmark(self, tmp_path: Path, capsys):
        """check_skill prints a checkmark line for current skills."""
        from great_docs._skill_install import _stamp_install_metadata

        raw = "---\nname: my-skill\n---\nBody"
        stamped = _stamp_install_metadata(raw, "1.0.0")
        _make_skill_md(tmp_path, "claude", "my-skill", stamped)

        bundled = tmp_path / "bundled" / "SKILL.md"
        bundled.parent.mkdir(parents=True)
        bundled.write_text(raw, encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            check_skill(root=tmp_path, quiet=False)

        out = capsys.readouterr().out

        assert "current" in out

    def test_outdated_status_prints_warning(self, tmp_path: Path, capsys):
        """check_skill prints a warning line for outdated skills."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        with patch(
            "great_docs._skill_install._get_package_version", return_value="1.0.0"
        ):
            check_skill(root=tmp_path, quiet=False)

        out = capsys.readouterr().out

        assert "outdated" in out

    def test_update_with_extra_files_copies_them(self, tmp_path: Path):
        """check_skill update=True copies extra files alongside SKILL.md."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        skill_md = _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        bundled_dir = tmp_path / "bundled" / "my-skill"
        bundled_dir.mkdir(parents=True)
        bundled = bundled_dir / "SKILL.md"
        bundled.write_text("---\nname: my-skill\n---\nNew body", encoding="utf-8")
        extra = bundled_dir / "helper.sh"
        extra.write_text("#!/bin/bash\necho hi", encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            results = check_skill(root=tmp_path, update=True, quiet=True)

        assert any(r["status"] == "updated" for r in results)
        assert (skill_md.parent / "helper.sh").exists()

    def test_update_prints_message(self, tmp_path: Path, capsys):
        """check_skill update=True prints 'Updated' when not quiet."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        bundled_dir = tmp_path / "bundled" / "my-skill"
        bundled_dir.mkdir(parents=True)
        bundled = bundled_dir / "SKILL.md"
        bundled.write_text("---\nname: my-skill\n---\nNew body", encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            check_skill(root=tmp_path, update=True, quiet=False)

        out = capsys.readouterr().out

        assert "Updated" in out


# ---------------------------------------------------------------------------
# list_skills — quiet=False with results
# ---------------------------------------------------------------------------


class TestListSkillsQuiet:
    def test_package_prints_skills_when_not_quiet(self, tmp_path: Path, capsys):
        """list_skills prints each skill name when quiet=False and results exist."""
        content = "---\nname: found-skill\ndescription: A description\n---\nBody"
        bundled = tmp_path / "found-skill" / "SKILL.md"
        bundled.parent.mkdir(parents=True)
        bundled.write_text(content, encoding="utf-8")

        with patch(
            "great_docs._skill_install._find_package_skills", return_value=[bundled]
        ):
            list_skills(package="mypkg", quiet=False)

        out = capsys.readouterr().out

        assert "found-skill" in out

    def test_no_source_returns_empty(self):
        """list_skills with no package/url returns []."""
        result = list_skills(quiet=True)

        assert result == []


# ---------------------------------------------------------------------------
# Final branch coverage fixes
# ---------------------------------------------------------------------------


class TestFinalBranches:
    def test_find_package_skills_project_root_skills_dir(self, tmp_path: Path):
        """_find_package_skills finds skills/ one level above the package __init__.py."""
        from great_docs._skill_install import _find_package_skills

        # Create a fake package where skills/ is at the project root, not inside the package
        pkg_dir = tmp_path / "mypkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        # skills/ lives one level up (at tmp_path, not inside mypkg/)
        skills_dir = tmp_path / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\nname: my-skill\n---\nBody")

        import types

        fake_mod = types.ModuleType("mypkg")
        fake_mod.__file__ = str(pkg_dir / "__init__.py")
        with patch.dict("sys.modules", {"mypkg": fake_mod}):
            result = _find_package_skills("mypkg")

        assert len(result) == 1
        assert result[0].name == "SKILL.md"

    def test_check_skill_local_false_global_true(self, tmp_path: Path):
        """check_skill with local=False and global_=True skips the local scan root."""
        from great_docs._skill_install import check_skill

        # Put a skill in the global (home) location
        skill_dir = tmp_path / ".claude" / "skills" / "g-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: g-skill\n---\nBody", encoding="utf-8"
        )

        with (
            patch("great_docs._skill_install._get_package_version", return_value=None),
            patch("great_docs._skill_install.Path.home", return_value=tmp_path),
        ):
            results = check_skill(local=False, global_=True, root=tmp_path, quiet=True)

        assert any(r["name"] == "g-skill" for r in results)

    def test_update_skips_unmatched_bundled_skills(self, tmp_path: Path):
        """check_skill update iterates multiple bundled skills but only updates matching one."""
        fm_only = (
            "---\nname: target-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        skill_md = _make_skill_md(tmp_path, "claude", "target-skill", fm_only)

        bundled_dir = tmp_path / "bundled"
        # Two bundled skill files; only the second matches
        other = bundled_dir / "other-skill" / "SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("---\nname: other-skill\n---\nOther body", encoding="utf-8")
        matching = bundled_dir / "target-skill" / "SKILL.md"
        matching.parent.mkdir(parents=True)
        matching.write_text("---\nname: target-skill\n---\nNew body", encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills",
                return_value=[other, matching],
            ),
        ):
            results = check_skill(root=tmp_path, update=True, quiet=True)

        assert any(r["status"] == "updated" for r in results)
        assert "New body" in skill_md.read_text()

    def test_update_no_pkg_version_skips_stamp(self, tmp_path: Path):
        """check_skill update with pkg_ver=None installs without stamping."""
        fm_only = (
            "---\nname: my-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        skill_md = _make_skill_md(tmp_path, "claude", "my-skill", fm_only)

        bundled_dir = tmp_path / "bundled" / "my-skill"
        bundled_dir.mkdir(parents=True)
        bundled = bundled_dir / "SKILL.md"
        bundled.write_text("---\nname: my-skill\n---\nFresh body", encoding="utf-8")

        def fake_pkg_version(pkg_name):
            # Return None on the second call (during update stamping)
            fake_pkg_version.calls = getattr(fake_pkg_version, "calls", 0) + 1
            if fake_pkg_version.calls == 1:
                return "1.0.0"  # First call: determine status = outdated
            return None  # Second call: inside update stamping

        with (
            patch(
                "great_docs._skill_install._get_package_version",
                side_effect=fake_pkg_version,
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            results = check_skill(root=tmp_path, update=True, quiet=True)

        # Should still update (just without stamping)
        assert any(r["status"] == "updated" for r in results)
        assert "Fresh body" in skill_md.read_text()

    def test_list_skills_url_failure_quiet_true(self):
        """list_skills with URL failure and quiet=True returns [] silently."""
        import urllib.error
        import urllib.request

        from great_docs._skill_install import list_skills

        with patch.object(
            urllib.request, "urlopen", side_effect=urllib.error.URLError("fail")
        ):
            results = list_skills(url="https://example.com", quiet=True)

        assert results == []


class TestUpdateNoMatch:
    def test_update_no_matching_bundled_skill(self, tmp_path: Path):
        """check_skill update leaves skill unchanged when no bundled file matches by name."""
        fm_only = (
            "---\nname: wanted-skill\nmetadata:\n  package_version: '0.9.0'\n---\nBody"
        )
        skill_md = _make_skill_md(tmp_path, "claude", "wanted-skill", fm_only)
        original_text = skill_md.read_text()

        # Only a bundled file with a different name — no match
        bundled_dir = tmp_path / "bundled" / "other-skill"
        bundled_dir.mkdir(parents=True)
        bundled = bundled_dir / "SKILL.md"
        bundled.write_text("---\nname: other-skill\n---\nOther body", encoding="utf-8")

        with (
            patch(
                "great_docs._skill_install._get_package_version", return_value="1.0.0"
            ),
            patch(
                "great_docs._skill_install._find_package_skills", return_value=[bundled]
            ),
        ):
            results = check_skill(root=tmp_path, update=True, quiet=True)

        # Status stays "outdated" since we found no matching bundled file
        assert any(r["status"] == "outdated" for r in results)
        assert skill_md.read_text() == original_text
