# pyright: reportPrivateUsage=false
"""Tests for Go CLI project detection and introspection.

Local fixtures in `tests/fixtures/` are used exclusively (no external repository clones are
required). Tests that actually compile Go code are skipped automatically when the `go` compiler is
not on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from great_docs._go_cli import (
    GoCliProject,
    _find_go_main_package,
    _parse_cobra_flag,
    _parse_cobra_help,
    _parse_go_module_path,
    _uses_cobra,
    build_go_binary,
    detect_go_cli_project,
    introspect_cobra_cli,
)
from great_docs.core import GreatDocs

# ---------------------------------------------------------------------------
# Paths to committed fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# go_cli_hello: stdlib-only buildable CLI (cmd/hello/main.go, no external deps)
HELLO_FIXTURE = FIXTURES_DIR / "go_cli_hello"

# go_cli_cobra: go.mod only — declares cobra, used for static _uses_cobra tests
COBRA_FIXTURE = FIXTURES_DIR / "go_cli_cobra"

GO_AVAILABLE = shutil.which("go") is not None

requires_go = pytest.mark.skipif(not GO_AVAILABLE, reason="go compiler not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_go_project(
    tmp_path: Path, go_mod: str = "", extra_files: dict[str, str] | None = None
) -> Path:
    """Write a minimal Go project layout to *tmp_path*."""
    if not go_mod:
        go_mod = "module example.com/myapp\n\ngo 1.21\n"
    (tmp_path / "go.mod").write_text(go_mod, encoding="utf-8")
    for rel, content in (extra_files or {}).items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# _parse_go_module_path
# ---------------------------------------------------------------------------


class TestParseGoModulePath:
    def test_standard_module_line(self, tmp_path: Path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module github.com/user/repo\n\ngo 1.21\n", encoding="utf-8")
        assert _parse_go_module_path(go_mod) == "github.com/user/repo"

    def test_module_with_leading_whitespace(self, tmp_path: Path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module  github.com/user/repo\n", encoding="utf-8")
        assert _parse_go_module_path(go_mod) == "github.com/user/repo"

    def test_no_module_line_returns_none(self, tmp_path: Path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("go 1.21\n", encoding="utf-8")
        assert _parse_go_module_path(go_mod) is None

    def test_missing_file_returns_none(self, tmp_path: Path):
        assert _parse_go_module_path(tmp_path / "nonexistent.mod") is None

    def test_hello_fixture_module_path(self):
        """Committed fixture has the expected module declaration."""
        go_mod = HELLO_FIXTURE / "go.mod"
        assert (
            _parse_go_module_path(go_mod) == "github.com/posit-dev/great-docs/testdata/go_cli_hello"
        )

    def test_cobra_fixture_module_path(self):
        go_mod = COBRA_FIXTURE / "go.mod"
        assert (
            _parse_go_module_path(go_mod) == "github.com/posit-dev/great-docs/testdata/go_cli_cobra"
        )


# ---------------------------------------------------------------------------
# _find_go_main_package
# ---------------------------------------------------------------------------


class TestFindGoMainPackage:
    def test_cmd_subdir_layout(self, tmp_path: Path):
        """cmd/<name>/main.go is the most common CLI layout."""
        (tmp_path / "cmd" / "myapp").mkdir(parents=True)
        (tmp_path / "cmd" / "myapp" / "main.go").write_text("package main\n")
        pkg, name = _find_go_main_package(tmp_path, "example.com/myapp")
        assert pkg == "./cmd/myapp"
        assert name == "myapp"

    def test_cmd_main_layout(self, tmp_path: Path):
        (tmp_path / "cmd").mkdir()
        (tmp_path / "cmd" / "main.go").write_text("package main\n")
        pkg, name = _find_go_main_package(tmp_path, "example.com/myapp")
        assert pkg == "./cmd"
        assert name == "myapp"

    def test_flat_main_layout(self, tmp_path: Path):
        (tmp_path / "main.go").write_text("package main\n")
        pkg, name = _find_go_main_package(tmp_path, "example.com/myapp")
        assert pkg == "."
        assert name == "myapp"

    def test_no_main_returns_empty(self, tmp_path: Path):
        pkg, name = _find_go_main_package(tmp_path, "example.com/myapp")
        assert pkg == ""
        assert name == ""

    def test_prefers_cmd_subdir_over_flat(self, tmp_path: Path):
        """When both cmd/<name>/main.go and main.go exist, prefer the former."""
        (tmp_path / "cmd" / "myapp").mkdir(parents=True)
        (tmp_path / "cmd" / "myapp" / "main.go").write_text("package main\n")
        (tmp_path / "main.go").write_text("package main\n")
        pkg, name = _find_go_main_package(tmp_path, "example.com/myapp")
        assert pkg == "./cmd/myapp"

    def test_hello_fixture_main_package(self):
        """Committed fixture uses cmd/hello/ layout."""
        module = "github.com/posit-dev/great-docs/testdata/go_cli_hello"
        pkg, name = _find_go_main_package(HELLO_FIXTURE, module)
        assert pkg == "./cmd/hello"
        assert name == "hello"


# ---------------------------------------------------------------------------
# _uses_cobra
# ---------------------------------------------------------------------------


class TestUsesCobra:
    def test_detects_cobra(self, tmp_path: Path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text(
            "module example.com/x\n\nrequire github.com/spf13/cobra v1.8.0\n", encoding="utf-8"
        )
        assert _uses_cobra(go_mod) is True

    def test_no_cobra(self, tmp_path: Path):
        go_mod = tmp_path / "go.mod"
        go_mod.write_text("module example.com/x\n\ngo 1.21\n", encoding="utf-8")
        assert _uses_cobra(go_mod) is False

    def test_missing_file_returns_false(self, tmp_path: Path):
        assert _uses_cobra(tmp_path / "gone.mod") is False

    def test_cobra_fixture_detected(self):
        """go_cli_cobra fixture go.mod explicitly lists spf13/cobra."""
        assert _uses_cobra(COBRA_FIXTURE / "go.mod") is True

    def test_hello_fixture_has_no_cobra(self):
        """go_cli_hello is stdlib-only; cobra must not appear in its go.mod."""
        assert _uses_cobra(HELLO_FIXTURE / "go.mod") is False


# ---------------------------------------------------------------------------
# detect_go_cli_project
# ---------------------------------------------------------------------------


class TestDetectGoCliProject:
    def test_returns_none_for_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypkg'\n")
        assert detect_go_cli_project(tmp_path) is None

    def test_returns_none_for_empty_dir(self, tmp_path: Path):
        assert detect_go_cli_project(tmp_path) is None

    def test_returns_none_when_no_main_package(self, tmp_path: Path):
        """go.mod present but no main.go anywhere → not a CLI."""
        (tmp_path / "go.mod").write_text("module example.com/lib\n\ngo 1.21\n")
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "lib.go").write_text("package pkg\n")
        assert detect_go_cli_project(tmp_path) is None

    def test_detects_flat_layout(self, tmp_path: Path):
        _make_go_project(tmp_path, extra_files={"main.go": "package main\n"})
        result = detect_go_cli_project(tmp_path)
        assert result is not None
        assert result.main_package == "."
        assert result.binary_name == "myapp"

    def test_detects_cmd_subdir_layout(self, tmp_path: Path):
        _make_go_project(
            tmp_path,
            extra_files={"cmd/mycli/main.go": "package main\n"},
        )
        result = detect_go_cli_project(tmp_path)
        assert result is not None
        assert result.main_package == "./cmd/mycli"
        assert result.binary_name == "mycli"
        assert result.module_path == "example.com/myapp"

    def test_uses_cobra_flag_propagated(self, tmp_path: Path):
        go_mod = "module example.com/app\n\ngo 1.21\n\nrequire github.com/spf13/cobra v1.8.0\n"
        _make_go_project(tmp_path, go_mod=go_mod, extra_files={"main.go": "package main\n"})
        result = detect_go_cli_project(tmp_path)
        assert result is not None
        assert result.uses_cobra is True

    def test_hello_fixture_detection(self):
        """Full detection against the committed go_cli_hello fixture."""
        result = detect_go_cli_project(HELLO_FIXTURE)
        assert result is not None
        assert result.binary_name == "hello"
        assert result.module_path == "github.com/posit-dev/great-docs/testdata/go_cli_hello"
        assert result.main_package == "./cmd/hello"
        assert result.uses_cobra is False  # stdlib-only fixture
        assert result.project_root == HELLO_FIXTURE

    def test_cobra_fixture_not_a_cli(self):
        """go_cli_cobra has no main.go, so it should not be detected as a CLI."""
        result = detect_go_cli_project(COBRA_FIXTURE)
        assert result is None


# ---------------------------------------------------------------------------
# GreatDocs._detect_go_cli_project and _find_package_root
# ---------------------------------------------------------------------------


class TestGreatDocsGoIntegration:
    def test_detect_go_cli_project_on_hello_fixture(self):
        gd = GreatDocs(project_path=str(HELLO_FIXTURE))
        result = gd._detect_go_cli_project()
        assert result is not None
        assert isinstance(result, GoCliProject)
        assert result.binary_name == "hello"

    def test_detect_go_cli_project_on_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'mypkg'\n")
        gd = GreatDocs(project_path=str(tmp_path))
        assert gd._detect_go_cli_project() is None

    def test_find_package_root_recognizes_go_mod(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.21\n")
        (tmp_path / "cmd" / "app").mkdir(parents=True)
        (tmp_path / "cmd" / "app" / "main.go").write_text("package main\n")
        gd = GreatDocs(project_path=str(tmp_path))
        assert gd._find_package_root() == tmp_path

    def test_find_package_root_on_hello_fixture(self):
        gd = GreatDocs(project_path=str(HELLO_FIXTURE))
        assert gd._find_package_root() == HELLO_FIXTURE


# ---------------------------------------------------------------------------
# _parse_cobra_flag
# ---------------------------------------------------------------------------


class TestParseCobraFlag:
    def test_long_only_boolean(self):
        opt = _parse_cobra_flag("--verbose     enable verbose output")
        assert opt is not None
        assert opt["names"] == ["--verbose"]
        assert opt["is_flag"] is True
        assert opt["type"] is None
        assert "verbose" in opt["help"]

    def test_short_and_long_boolean(self):
        opt = _parse_cobra_flag("-v, --verbose     enable verbose output")
        assert opt is not None
        assert opt["names"] == ["-v", "--verbose"]
        assert opt["is_flag"] is True

    def test_string_type_with_default(self):
        opt = _parse_cobra_flag("--config string   config file (default: hello.toml)")
        assert opt is not None
        assert opt["type"] == "string"
        assert opt["default"] == "hello.toml"
        assert opt["is_flag"] is False
        assert "config file" in opt["help"]

    def test_short_and_long_with_type_and_default(self):
        opt = _parse_cobra_flag('-n, --name string   name to greet (default "World")')
        assert opt is not None
        assert opt["names"] == ["-n", "--name"]
        assert opt["type"] == "string"
        assert opt["default"] == "World"

    def test_help_flag(self):
        opt = _parse_cobra_flag("-h, --help        help for hello")
        assert opt is not None
        assert "--help" in opt["names"]
        assert opt["is_flag"] is True

    def test_unparseable_returns_none(self):
        assert _parse_cobra_flag("not a flag line") is None
        assert _parse_cobra_flag("") is None


# ---------------------------------------------------------------------------
# _parse_cobra_help
# ---------------------------------------------------------------------------

# Sample help text modelled on the fixture's own output format.
SAMPLE_COBRA_HELP = textwrap.dedent("""\
    A minimal CLI fixture for great-docs testing.

    Usage:
      hello [command]

    Available Commands:
      completion  Generate the autocompletion script for the specified shell
      greet       Print a personalised greeting
      help        Help about any command
      version     Print the version

    Flags:
      --config string   config file (default: hello.toml)
      -h, --help        help for hello
      -v, --verbose     enable verbose output

    Use "hello [command] --help" for more information about a command.
""")


class TestParseCobraHelp:
    def test_description_extracted(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        assert "minimal CLI" in result["help"]

    def test_builtin_commands_excluded(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        names = [c["name"] for c in result["commands"]]
        assert "completion" not in names
        assert "help" not in names

    def test_user_commands_included(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        names = [c["name"] for c in result["commands"]]
        assert "greet" in names
        assert "version" in names

    def test_flags_parsed(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        # options are now dicts — check that --verbose is present as a dict
        long_names = [n for opt in result["options"] for n in opt["names"]]
        assert "--verbose" in long_names
        assert "--config" in long_names

    def test_option_type_extracted(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        config_opt = next(o for o in result["options"] if "--config" in o["names"])
        assert config_opt["type"] == "string"
        assert config_opt["default"] == "hello.toml"

    def test_boolean_flag_detected(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        verbose_opt = next(o for o in result["options"] if "--verbose" in o["names"])
        assert verbose_opt["is_flag"] is True
        assert verbose_opt["type"] is None

    def test_name_preserved(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        assert result["name"] == "hello"

    def test_help_text_preserved(self):
        result = _parse_cobra_help(SAMPLE_COBRA_HELP, "hello", Path("/tmp/bin"), [])
        assert result["help_text"] == SAMPLE_COBRA_HELP

    def test_empty_input(self):
        result = _parse_cobra_help("", "myapp", Path("/tmp/bin"), [])
        assert result["name"] == "myapp"
        assert result["commands"] == []
        assert result["options"] == []


# ---------------------------------------------------------------------------
# build_go_binary / introspect_cobra_cli (mocked)
# ---------------------------------------------------------------------------


class TestBuildGoBinary:
    def test_returns_none_when_go_not_found(self, tmp_path: Path):
        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )
        with patch("great_docs._go_cli.subprocess.run", side_effect=FileNotFoundError):
            result = build_go_binary(go_project, output_dir=tmp_path)
        assert result is None

    def test_returns_none_on_build_failure(self, tmp_path: Path):
        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "build error"
        with patch("great_docs._go_cli.subprocess.run", return_value=mock_result):
            result = build_go_binary(go_project, output_dir=tmp_path)
        assert result is None

    def test_returns_binary_path_on_success(self, tmp_path: Path):
        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("great_docs._go_cli.subprocess.run", return_value=mock_result):
            result = build_go_binary(go_project, output_dir=tmp_path)
        assert result == tmp_path / "app"

    def test_returns_none_on_timeout(self, tmp_path: Path):
        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )
        with patch(
            "great_docs._go_cli.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="go", timeout=120),
        ):
            result = build_go_binary(go_project, output_dir=tmp_path)
        assert result is None


class TestIntrospectCobraCli:
    def test_returns_none_when_build_fails(self, tmp_path: Path):
        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )
        with patch("great_docs._go_cli.build_go_binary", return_value=None):
            result = introspect_cobra_cli(go_project)
        assert result is None

    def test_entry_point_name_set_on_success(self, tmp_path: Path):
        binary = tmp_path / "app"
        binary.write_text("")

        go_project = GoCliProject(
            project_root=tmp_path,
            module_path="example.com/app",
            binary_name="app",
            main_package=".",
            uses_cobra=False,
        )

        mock_proc = MagicMock()
        mock_proc.stdout = "My CLI tool\n\nUsage:\n  app [command]\n"
        mock_proc.stderr = ""
        mock_proc.returncode = 0

        with (
            patch("great_docs._go_cli.build_go_binary", return_value=binary),
            patch("great_docs._go_cli.subprocess.run", return_value=mock_proc),
        ):
            result = introspect_cobra_cli(go_project)

        assert result is not None
        assert result["entry_point_name"] == "app"
        assert "My CLI tool" in result["help"]


# ---------------------------------------------------------------------------
# Integration: build + introspect the committed go_cli_hello fixture
# Requires 'go' on PATH; auto-skipped otherwise.
# ---------------------------------------------------------------------------


@requires_go
class TestGoHelloFixtureIntegration:
    """End-to-end tests using the committed stdlib-only go_cli_hello fixture."""

    def test_detect_hello_fixture(self):
        result = detect_go_cli_project(HELLO_FIXTURE)
        assert result is not None
        assert result.binary_name == "hello"

    def test_build_hello_binary(self, tmp_path: Path):
        go_project = detect_go_cli_project(HELLO_FIXTURE)
        assert go_project is not None
        binary = build_go_binary(go_project, output_dir=tmp_path)
        assert binary is not None
        assert binary.exists()

    def test_introspect_hello_returns_commands(self, tmp_path: Path):
        go_project = detect_go_cli_project(HELLO_FIXTURE)
        assert go_project is not None
        cli_info = introspect_cobra_cli(go_project)
        assert cli_info is not None
        assert cli_info["entry_point_name"] == "hello"
        names = [c["name"] for c in cli_info["commands"]]
        assert "greet" in names
        assert "version" in names

    def test_introspect_excludes_builtin_commands(self, tmp_path: Path):
        go_project = detect_go_cli_project(HELLO_FIXTURE)
        assert go_project is not None
        cli_info = introspect_cobra_cli(go_project)
        assert cli_info is not None
        names = [c["name"] for c in cli_info["commands"]]
        assert "completion" not in names
        assert "help" not in names

    def test_binary_produces_help_text(self, tmp_path: Path):
        """The compiled binary should emit meaningful --help output."""
        go_project = detect_go_cli_project(HELLO_FIXTURE)
        assert go_project is not None
        binary = build_go_binary(go_project, output_dir=tmp_path)
        assert binary is not None
        result = subprocess.run([str(binary), "--help"], capture_output=True, text=True, timeout=5)
        output = result.stdout + result.stderr
        assert "greet" in output
        assert "version" in output
