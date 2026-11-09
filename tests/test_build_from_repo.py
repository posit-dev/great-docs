from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from click.testing import CliRunner

from great_docs._build import from_repo, serve
from great_docs._project.layout import Layout
from great_docs.cli import cli
from great_docs.core import GreatDocs


def test_install_extras_dev_and_docs():
    """Find `dev` and `docs` extras and ignore other groups"""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            "[project.optional-dependencies]\n"
            'dev = ["pytest"]\n'
            'docs = ["sphinx"]\n'
            'other = ["requests"]\n'
        )
        assert from_repo.install_extras(Path(tmp)) == "dev,docs"


def test_install_extras_all():
    """Finds 'all' extra."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            '[project.optional-dependencies]\nall = ["everything"]\n'
        )
        result = from_repo.install_extras(Path(tmp))
        assert result == "all"


def test_install_extras_no_pyproject():
    """Returns empty string when no pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp:
        assert from_repo.install_extras(Path(tmp)) == ""


def test_install_extras_no_optional_deps():
    """Returns empty string when no optional-dependencies."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nname = "x"\n')
        assert from_repo.install_extras(Path(tmp)) == ""


def test_install_extras_malformed_toml():
    """Returns empty string on malformed TOML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text("bad {{toml")
        assert from_repo.install_extras(Path(tmp)) == ""


def test_install_extras_ignores_other_groups(tmp_path):
    """Return an empty string when only other dependency groups are defined"""
    (tmp_path / "pyproject.toml").write_text(
        '[project.optional-dependencies]\nintegration = ["httpx"]\ncpu = ["numpy"]\n'
    )
    assert from_repo.install_extras(tmp_path) == ""


def test_install_extras_doc_variant():
    """Finds 'doc' (singular) extra."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            '[project.optional-dependencies]\ndoc = ["sphinx"]\n'
        )
        result = from_repo.install_extras(Path(tmp))
        assert result == "doc"


def test_from_repo_rejects_watch():
    """--watch + --from-repo is rejected."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["build", "--from-repo", "https://github.com/x/y.git", "--watch"],
    )
    assert result.exit_code != 0
    assert "--watch is not supported" in result.output


def test_build_project_path_ignored_with_from_repo(tmp_path, monkeypatch):
    """--project-path emits a warning when --from-repo is used."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("dummy").mkdir()
    with patch.object(from_repo, "build") as mock_bfr:
        result = runner.invoke(
            cli,
            [
                "build",
                "--from-repo",
                "https://github.com/x/y.git",
                "--project-path",
                "dummy",
            ],
        )
        assert "--project-path is ignored" in result.output
        mock_bfr.assert_called_once()


def test_build_branch_ignored_without_from_repo(tmp_path, monkeypatch):
    """--branch without --from-repo emits a warning."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "x"\n')
    Path("great-docs.yml").write_text("name: x\n")
    with patch.object(GreatDocs, "build") as mock_build:
        result = runner.invoke(cli, ["build", "--branch", "main", "--project-path", "."])
    assert "--branch is ignored" in result.output


def test_build_output_dir_ignored_without_from_repo(tmp_path, monkeypatch):
    """--output-dir without --from-repo emits a warning."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "x"\n')
    Path("great-docs.yml").write_text("name: x\n")
    with patch.object(GreatDocs, "build") as mock_build:
        result = runner.invoke(cli, ["build", "--output-dir", "./out", "--project-path", "."])
    assert "--output-dir is ignored" in result.output


def test_clone_failure_raises():
    """Raises RuntimeError when git clone fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=128, stderr="fatal: repo not found")

        with pytest.raises(RuntimeError, match="git clone failed"):
            from_repo.build("https://github.com/nonexistent/repo.git", report=print)


def test_clone_passes_branch():
    """Passes --branch to git clone when specified."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=128, stderr="fatal: error")

        with pytest.raises(RuntimeError, match="git clone failed"):
            from_repo.build("https://github.com/x/y.git", branch="v2.0", report=print)

        clone_call = mock_run.call_args_list[0]
        cmd = clone_call[0][0]
        assert "--branch" in cmd
        assert "v2.0" in cmd


def test_clone_without_branch():
    """Does not pass --branch when not specified."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=128, stderr="fatal: error")

        with pytest.raises(RuntimeError, match="git clone failed"):
            from_repo.build("https://github.com/x/y.git", report=print)

        clone_call = mock_run.call_args_list[0]
        cmd = clone_call[0][0]
        assert "--branch" not in cmd


@pytest.fixture
def pip_commands(monkeypatch, tmp_path):
    """
    Record the `pip install` commands `_install` runs, with each one succeeding

    Returns the list of commands. Appending a requirement to its `fail_on` attribute makes the
    install of that requirement fail.
    """

    class Commands(list[list[str]]):
        fail_on: list[str]

    commands = Commands()
    failing: list[str] = []

    def run(command, cwd=None):
        commands.append(command)
        failed = bool(failing) and failing[0] in command
        return MagicMock(returncode=1 if failed else 0, stderr="no such version")

    monkeypatch.setattr(from_repo.venv, "create", lambda *args, **kwargs: None)
    monkeypatch.setattr(from_repo, "_run", run)
    monkeypatch.setattr(from_repo, "install_extras", lambda project_dir: "")
    commands.fail_on = failing
    return commands


def test_install_uses_the_running_release(tmp_path, monkeypatch, pip_commands):
    """Install the version that is running from PyPI when it is not a source tree"""
    monkeypatch.setattr(from_repo, "_source_tree", lambda: None)
    monkeypatch.setattr(from_repo.metadata, "version", lambda name: "1.2.3")

    from_repo._install(tmp_path / "repo", tmp_path / "venv", report=print)

    assert pip_commands[0][1:] == ["install", "great-docs==1.2.3"]
    assert len(pip_commands) == 2


def test_install_uses_the_running_source_tree(tmp_path, monkeypatch, pip_commands):
    """Install a development checkout from its source tree"""
    monkeypatch.setattr(from_repo, "_source_tree", lambda: tmp_path / "src")

    from_repo._install(tmp_path / "repo", tmp_path / "venv", report=print)

    assert pip_commands[0][1:] == ["install", str(tmp_path / "src")]


def test_install_failure_names_the_running_release(tmp_path, monkeypatch, pip_commands):
    """Raise instead of installing another release when the running one is unavailable"""
    monkeypatch.setattr(from_repo, "_source_tree", lambda: None)
    monkeypatch.setattr(from_repo.metadata, "version", lambda name: "1.2.3")
    pip_commands.fail_on.append("great-docs==1.2.3")

    with pytest.raises(RuntimeError, match=r"great-docs==1\.2\.3"):
        from_repo._install(tmp_path / "repo", tmp_path / "venv", report=print)

    assert len(pip_commands) == 1


def test_source_tree_found_for_a_development_checkout():
    """Find the repository root when great-docs runs from this checkout"""
    assert from_repo._source_tree() == Path(from_repo.__file__).resolve().parents[2]


def test_source_tree_absent_for_another_project(tmp_path, monkeypatch):
    """Ignore a `pyproject.toml` that names another project"""
    root = tmp_path / "site-packages"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "other"\n')
    module = root / "great_docs" / "_build" / "from_repo.py"
    monkeypatch.setattr(from_repo, "__file__", str(module))
    assert from_repo._source_tree() is None


@pytest.fixture
def stub_remote_build(monkeypatch):
    """
    Replace the clone, installation and inner build with a site holding one page

    The page's text is the value of `pages[0]` when the inner build runs, so a test can tell
    one build's site from another's.
    """
    pages = ["first"]

    def clone(repo_url, checkout, **kwargs):
        checkout.mkdir(parents=True)
        layout = Layout.make(checkout, None)
        layout.site_dir.mkdir(parents=True)
        (layout.site_dir / "index.html").write_text(pages[0])
        return layout

    monkeypatch.setattr(from_repo, "_clone", clone)
    monkeypatch.setattr(from_repo, "_install", lambda checkout, env, report: env / "bin")
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=MagicMock(returncode=0)))
    return pages


def test_build_refuses_to_replace_a_directory_it_did_not_write(tmp_path, stub_remote_build):
    """Refuse an existing directory of the user's files before building, and keep the files"""
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    with pytest.raises(ValueError, match="not Great Docs-generated output"):
        from_repo.build("https://github.com/x/y.git", output_dir=str(tmp_path), report=print)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["pyproject.toml"]
    assert not subprocess.run.called


def test_build_replaces_its_own_earlier_output(tmp_path, stub_remote_build):
    """Fill an empty directory, then replace that site on the next build"""
    output = tmp_path / "site"
    output.mkdir()
    from_repo.build("https://github.com/x/y.git", output_dir=str(output), report=print)
    stub_remote_build[0] = "second"

    from_repo.build("https://github.com/x/y.git", output_dir=str(output), report=print)

    assert (output / "index.html").read_text() == "second"


def test_from_repo_cli_passes_flags():
    """Forward CLI flags to the repository build"""
    runner = CliRunner()
    with patch.object(from_repo, "build") as mock_bfr:
        result = runner.invoke(
            cli,
            [
                "build",
                "--from-repo",
                "https://github.com/x/y.git",
                "--branch",
                "v1.0",
                "--output-dir",
                "./my-site",
                "--no-refresh",
                "--latest-only",
            ],
        )
        mock_bfr.assert_called_once_with(
            "https://github.com/x/y.git",
            branch="v1.0",
            output_dir="./my-site",
            refresh=False,
            version_tags=None,
            latest_only=True,
            shallow=False,
            config_path=None,
            report=ANY,
        )


def test_from_repo_cli_version_tags():
    """--versions flag is forwarded as version_tags list."""
    runner = CliRunner()
    with patch.object(from_repo, "build") as mock_bfr:
        result = runner.invoke(
            cli,
            [
                "build",
                "--from-repo",
                "https://github.com/x/y.git",
                "--versions",
                "0.3,0.2",
            ],
        )
        mock_bfr.assert_called_once_with(
            "https://github.com/x/y.git",
            branch=None,
            output_dir=None,
            refresh=True,
            version_tags=["0.3", "0.2"],
            latest_only=False,
            shallow=False,
            config_path=None,
            report=ANY,
        )


def test_from_repo_cli_error_shown():
    """Report a failed repository build to the user"""
    runner = CliRunner()
    with patch.object(from_repo, "build", side_effect=RuntimeError("clone exploded")):
        result = runner.invoke(
            cli,
            ["build", "--from-repo", "https://github.com/x/y.git"],
        )
        assert result.exit_code != 0
        assert "clone exploded" in result.output


def test_history_needed_no_config():
    """Returns 'none' when great-docs.yml does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        assert from_repo.history_needed(Path(tmp)) == "none"


def test_history_needed_empty_config():
    """Returns 'tags' for a minimal config (source links benefit from tags)."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("name: mypkg\n")
        assert from_repo.history_needed(Path(tmp)) == "tags"


def test_history_needed_versions():
    """Returns 'full' when versions are configured."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("name: mypkg\nversions:\n  - '0.3'\n  - '0.2'\n")
        assert from_repo.history_needed(Path(tmp)) == "full"


def test_history_needed_show_dates(tmp_path):
    """Return `"full"` when top-level `show_dates` is enabled"""
    (tmp_path / "great-docs.yml").write_text("show_dates: true\n")
    assert from_repo.history_needed(tmp_path) == "full"


def test_history_needed_legacy_show_dates():
    """Return `"full"` when legacy `site.show_dates` is enabled"""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("name: mypkg\nsite:\n  show_dates: true\n")
        assert from_repo.history_needed(Path(tmp)) == "full"


def test_history_needed_explicit_branch():
    """Returns 'none' when source.branch is explicitly set (no tag detection needed)."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("name: mypkg\nsource:\n  branch: main\n")
        assert from_repo.history_needed(Path(tmp)) == "none"


def test_history_needed_source_without_branch(tmp_path):
    """Return `"tags"` when source settings specify no branch"""
    (tmp_path / "great-docs.yml").write_text("source:\n  repository: https://github.com/org/repo\n")
    assert from_repo.history_needed(tmp_path) == "tags"


def test_history_needed_malformed_yaml():
    """Returns 'none' on unparseable YAML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("bad: {{yaml: [")
        assert from_repo.history_needed(Path(tmp)) == "none"


def test_history_needed_show_dates_false():
    """Returns 'tags' when show_dates is explicitly false."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "great-docs.yml").write_text("name: mypkg\nsite:\n  show_dates: false\n")
        assert from_repo.history_needed(Path(tmp)) == "tags"


def test_build_shallow_cli_flag():
    """Forward `--shallow` to the repository build"""
    runner = CliRunner()
    with patch.object(from_repo, "build") as mock_bfr:
        result = runner.invoke(
            cli,
            [
                "build",
                "--from-repo",
                "https://github.com/x/y.git",
                "--shallow",
            ],
        )
        mock_bfr.assert_called_once_with(
            "https://github.com/x/y.git",
            branch=None,
            output_dir=None,
            refresh=True,
            version_tags=None,
            latest_only=False,
            shallow=True,
            config_path=None,
            report=ANY,
        )


def test_build_shallow_ignored_without_from_repo(tmp_path, monkeypatch):
    """--shallow without --from-repo emits a warning."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "x"\n')
    Path("great-docs.yml").write_text("name: x\n")
    with patch.object(GreatDocs, "build") as mock_build:
        result = runner.invoke(cli, ["build", "--shallow", "--project-path", "."])
    assert "--shallow is ignored" in result.output


# ── --preview flag tests ──────────────────────────────────────────────────────


def test_build_preview_serves_site():
    """Serve the output directory with `--preview` after `--from-repo`"""
    runner = CliRunner()
    with (
        patch.object(from_repo, "build") as mock_bfr,
        patch.object(serve, "site") as mock_preview,
    ):
        mock_bfr.return_value = Path("/tmp/out")
        result = runner.invoke(
            cli,
            [
                "build",
                "--from-repo",
                "https://github.com/x/y.git",
                "--output-dir",
                "/tmp/out",
                "--preview",
            ],
        )
        assert result.exit_code == 0
        mock_bfr.assert_called_once()
        mock_preview.assert_called_once_with(Path("/tmp/out"), report=ANY)


def test_build_preview_default_output_dir():
    """--preview without --output-dir uses the default site path."""
    runner = CliRunner()
    with (
        patch.object(from_repo, "build") as mock_bfr,
        patch.object(serve, "site") as mock_preview,
    ):
        mock_bfr.return_value = Path.cwd() / "docs/_site"
        result = runner.invoke(
            cli,
            ["build", "--from-repo", "https://github.com/x/y.git", "--preview"],
        )
        assert result.exit_code == 0
        mock_preview.assert_called_once()
        site_arg = mock_preview.call_args[0][0]
        assert site_arg == mock_bfr.return_value


def test_build_preview_ignored_without_from_repo(tmp_path, monkeypatch):
    """--preview without --from-repo emits a warning."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "x"\n')
    Path("great-docs.yml").write_text("name: x\n")
    with patch.object(GreatDocs, "build") as mock_build:
        result = runner.invoke(cli, ["build", "--preview", "--project-path", "."])
    assert "--preview is ignored" in result.output


# ── preview --site-dir tests ─────────────────────────────────────────────────


def test_preview_with_site_dir(tmp_path, monkeypatch):
    """Serve the given path with `preview --site-dir`"""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("mysite").mkdir()
    (Path("mysite") / "index.html").write_text("<html></html>")
    site_path = str(Path("mysite").resolve())
    with patch.object(serve, "site") as mock_preview:
        result = runner.invoke(cli, ["preview", "--site-dir", site_path])
        mock_preview.assert_called_once_with(
            site_path, port=3000, open_path="", open_browser=True, report=ANY
        )


def test_preview_with_site_dir_warns_about_project_path(tmp_path, monkeypatch):
    """preview --site-dir with --project-path emits a warning."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("mysite").mkdir()
    (Path("mysite") / "index.html").write_text("<html></html>")
    Path("proj").mkdir()
    site_path = str(Path("mysite").resolve())
    proj_path = str(Path("proj").resolve())
    with patch.object(serve, "site"):
        result = runner.invoke(
            cli,
            ["preview", "--site-dir", site_path, "--project-path", proj_path],
        )
        assert "--project-path is ignored" in result.output


def test_serve_missing_index_raises():
    """Raise `ServeError` for a directory without `index.html`"""
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(serve.ServeError, match="No index.html found"):
            serve.site(tmp, report=print)


def test_preview_with_site_dir_without_index_exits(tmp_path):
    """Report a missing `index.html` and exit with status 1 for `preview --site-dir`"""
    result = CliRunner().invoke(cli, ["preview", "--site-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert f"❌ No index.html found in {tmp_path}" in result.output


def test_preview_with_site_dir_on_busy_port_exits(tmp_path, monkeypatch):
    """Report an unavailable port and exit with status 1 for `preview --site-dir`"""
    import http.server

    (tmp_path / "index.html").write_text("<html></html>")

    def busy(address, handler):
        raise OSError("Address already in use")

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", busy)
    result = CliRunner().invoke(cli, ["preview", "--site-dir", str(tmp_path), "--port", "4321"])
    assert result.exit_code == 1
    assert "❌ Port 4321 is already in use. Try a different port." in result.output
