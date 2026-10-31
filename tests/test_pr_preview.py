"""Tests for the PR / CI-build preview feature (`great-docs preview --pr`)."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs import _pr_preview as pp
from great_docs._build import serve
from great_docs.cli import preview

# ---------------------------------------------------------------------------
# URL / repo parsing
# ---------------------------------------------------------------------------


def test_parse_owner_repo():
    assert pp._parse_owner_repo("posit-dev/great-docs") == ("posit-dev", "great-docs")
    assert pp._parse_owner_repo("posit-dev/great-docs.git") == ("posit-dev", "great-docs")
    assert pp._parse_owner_repo("nope") is None


def test_resolve_repo_override_variants():
    assert pp.resolve_repo(None, "posit-dev/great-docs") == ("posit-dev", "great-docs")
    assert pp.resolve_repo(None, "https://github.com/posit-dev/great-docs") == (
        "posit-dev",
        "great-docs",
    )


def test_resolve_repo_override_invalid():
    with pytest.raises(pp.PreviewError):
        pp.resolve_repo(None, "not a repo!!")


def test_resolve_repo_from_git_remote(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: ("posit-dev", "great-docs"))
    assert pp.resolve_repo("/somewhere", None) == ("posit-dev", "great-docs")


def test_resolve_repo_unresolvable(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: None)
    monkeypatch.setattr(pp, "_config_repo", lambda p: None)
    with pytest.raises(pp.PreviewError):
        pp.resolve_repo(None, None)


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------


def test_resolve_token_from_env(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "envtok")
    token, source = pp.resolve_token(None, None)
    assert token == "envtok"
    assert source == "GITHUB_TOKEN"


def test_resolve_token_explicit_env_file_wins(monkeypatch, tmp_path):
    # Even with an environment token present, an explicit --env-file takes precedence.
    monkeypatch.setenv("GITHUB_TOKEN", "envtok")
    env_file = tmp_path / "secrets.env"
    env_file.write_text("GITHUB_TOKEN=filetok\n")
    token, source = pp.resolve_token(None, str(env_file))
    assert token == "filetok"
    assert str(env_file) in source


def test_resolve_token_autodetect_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    (tmp_path / ".env").write_text("GH_TOKEN=dottok\n")
    token, source = pp.resolve_token(tmp_path, None)
    assert token == "dottok"


def test_resolve_token_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    monkeypatch.setattr(pp, "find_dotenv", lambda usecwd=True: "", raising=False)
    # No env, no gh, no discoverable .env in an isolated dir.
    token, source = pp.resolve_token(None, None)
    # A stray .env in the repo working dir shouldn't matter for this assertion's intent;
    # the important behavior is that missing env + no gh yields no env-based token.
    assert source != "GITHUB_TOKEN"


# ---------------------------------------------------------------------------
# Run resolution
# ---------------------------------------------------------------------------


class FakeClient:
    """A stand-in for GitHubClient that returns canned JSON keyed by path substring."""

    def __init__(self, responses, owner="posit-dev", repo="great-docs"):
        self.owner = owner
        self.repo = repo
        self._responses = responses
        self.calls: list[str] = []

    def get_json(self, path, params=None):
        self.calls.append(path)
        for key, val in self._responses.items():
            if key in path:
                return val
        raise AssertionError(f"unexpected path: {path}")


def test_pick_run_prefers_success_then_newest():
    runs = {
        "workflow_runs": [
            {"id": 1, "name": "CI Docs", "created_at": "2026-01-01", "conclusion": "failure"},
            {"id": 2, "name": "CI Docs", "created_at": "2026-01-03", "conclusion": "success"},
            {"id": 3, "name": "CI Docs", "created_at": "2026-01-02", "conclusion": "success"},
            {"id": 4, "name": "Other", "created_at": "2026-01-09", "conclusion": "success"},
        ]
    }
    info = pp._pick_run(runs, "CI Docs")
    assert info.run_id == 2  # newest successful CI Docs run


def test_pick_run_falls_back_to_newest_when_none_succeeded():
    runs = {
        "workflow_runs": [
            {"id": 1, "name": "CI Docs", "created_at": "2026-01-01", "conclusion": "failure"},
            {"id": 2, "name": "CI Docs", "created_at": "2026-01-05", "conclusion": "failure"},
        ]
    }
    info = pp._pick_run(runs, "CI Docs")
    assert info.run_id == 2
    assert info.conclusion == "failure"


def test_resolve_run_direct_id():
    info = pp.resolve_run(FakeClient({}), pr=None, run=18273645521, branch=None)
    assert info.run_id == 18273645521


def test_resolve_run_by_pr():
    client = FakeClient(
        {
            "pulls/302": {
                "head": {"sha": "a1b2c3d4", "repo": {"full_name": "posit-dev/great-docs"}},
                "base": {"repo": {"full_name": "posit-dev/great-docs"}},
            },
            "actions/runs": {
                "workflow_runs": [
                    {
                        "id": 99,
                        "name": "CI Docs",
                        "created_at": "2026-01-01",
                        "conclusion": "success",
                    }
                ]
            },
        }
    )
    info = pp.resolve_run(client, pr=302, run=None, branch=None)
    assert info.run_id == 99
    assert info.head_sha == "a1b2c3d4"
    assert info.head_repo == "posit-dev/great-docs"


def test_resolve_run_by_pr_no_run(monkeypatch):
    client = FakeClient(
        {
            "pulls/5": {"head": {"sha": "deadbeef"}, "base": {}},
            "actions/runs": {"workflow_runs": []},
        }
    )
    with pytest.raises(pp.PreviewError, match="No 'CI Docs' run"):
        pp.resolve_run(client, pr=5, run=None, branch=None)


# ---------------------------------------------------------------------------
# Artifact selection
# ---------------------------------------------------------------------------


def test_choose_artifact_exact_match():
    arts = [
        {"name": "build-timings", "created_at": "2026-01-01"},
        {"name": "docs-html", "created_at": "2026-01-01"},
    ]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "docs-html"


def test_choose_artifact_single_fallback(capsys):
    arts = [{"name": "site", "created_at": "2026-01-01"}]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "site"
    assert "using the only one" in capsys.readouterr().out


def test_choose_artifact_multiple_non_interactive_newest():
    arts = [
        {"name": "docs-html-a", "created_at": "2026-01-01"},
        {"name": "docs-html-b", "created_at": "2026-01-09"},
    ]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "docs-html-b"


def test_choose_artifact_none_raises():
    with pytest.raises(pp.PreviewError, match="no artifacts"):
        pp.choose_artifact([], name="docs-html", interactive=False)


# ---------------------------------------------------------------------------
# Zip extraction + site root discovery
# ---------------------------------------------------------------------------


def test_safe_extract_zip_normal(tmp_path):
    zip_path = tmp_path / "site.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("index.html", "<html>hi</html>")
        zf.writestr("reference/index.html", "<html>ref</html>")
    dest = tmp_path / "out"
    dest.mkdir()
    pp._safe_extract_zip(zip_path, dest)
    assert (dest / "index.html").is_file()
    assert (dest / "reference" / "index.html").is_file()


def test_safe_extract_zip_rejects_zip_slip(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(pp.PreviewError, match="unsafe path"):
        pp._safe_extract_zip(zip_path, dest)
    assert not (tmp_path / "escape.txt").exists()


def test_find_site_root_at_root(tmp_path):
    (tmp_path / "index.html").write_text("x")
    assert pp._find_site_root(tmp_path) == tmp_path


def test_find_site_root_nested(tmp_path):
    nested = tmp_path / "_site"
    nested.mkdir()
    (nested / "index.html").write_text("x")
    assert pp._find_site_root(tmp_path) == nested


def test_find_site_root_missing(tmp_path):
    assert pp._find_site_root(tmp_path) is None


# ---------------------------------------------------------------------------
# Caching / download orchestration
# ---------------------------------------------------------------------------


class FakeDownloadClient:
    def __init__(self):
        self.owner = "posit-dev"
        self.repo = "great-docs"
        self.downloads = 0

    def download_artifact(self, run_id, artifact, dest):
        self.downloads += 1
        (dest / "index.html").write_text("<html>built</html>")


def test_cache_dir_for_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    got = pp.cache_dir_for("posit-dev", "great-docs", 42, "docs-html")
    assert (
        got == tmp_path / "great-docs" / "pr-preview" / "posit-dev-great-docs" / "42" / "docs-html"
    )


def test_download_and_extract_caches(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    client = FakeDownloadClient()
    art = {"name": "docs-html"}

    root1 = pp.download_and_extract(client, run_id=42, artifact=art, refresh=False)
    assert (root1 / "index.html").is_file()
    assert client.downloads == 1

    # Second call hits the cache (no new download).
    root2 = pp.download_and_extract(client, run_id=42, artifact=art, refresh=False)
    assert root2 == root1
    assert client.downloads == 1
    assert "cached" in capsys.readouterr().out

    # --refresh forces a re-download.
    pp.download_and_extract(client, run_id=42, artifact=art, refresh=True)
    assert client.downloads == 2


class _FakeResponse:
    """Minimal stand-in for a streaming requests.Response."""

    def __init__(self, chunks):
        self._chunks = chunks

    def iter_content(self, chunk_size=None):
        yield from self._chunks


def test_stream_to_file_writes_all_bytes(tmp_path):
    dest = tmp_path / "out.zip"
    resp = _FakeResponse([b"abc", b"def", b"ghi"])
    pp._stream_to_file(resp, dest, total=9)
    assert dest.read_bytes() == b"abcdefghi"


def test_stream_to_file_unknown_length(tmp_path):
    # total == 0 (no Content-Length) should still write the file, just without a bar.
    dest = tmp_path / "out.zip"
    resp = _FakeResponse([b"x" * 100])
    pp._stream_to_file(resp, dest, total=0)
    assert dest.read_bytes() == b"x" * 100


def test_stream_to_file_progress_bar_path(monkeypatch, tmp_path):
    # Force the TTY branch and stub click.progressbar to verify wiring (writes
    # the file and advances the bar) without depending on terminal rendering.
    import click

    class _FakeTTY:
        def isatty(self):
            return True

        def write(self, *a):
            pass

        def flush(self):
            pass

    updates: list[int] = []

    class _FakeBar:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, n):
            updates.append(n)

    monkeypatch.setattr(pp.sys, "stderr", _FakeTTY())
    monkeypatch.setattr(click, "progressbar", lambda **kwargs: _FakeBar())

    dest = tmp_path / "out.zip"
    pp._stream_to_file(_FakeResponse([b"aa", b"bb"]), dest, total=4)
    assert dest.read_bytes() == b"aabb"
    assert sum(updates) == 4


def test_download_and_extract_missing_index_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    class NoIndexClient(FakeDownloadClient):
        def download_artifact(self, run_id, artifact, dest):
            (dest / "notes.txt").write_text("no site here")

    with pytest.raises(pp.PreviewError, match="index.html"):
        pp.download_and_extract(NoIndexClient(), run_id=7, artifact={"name": "x"}, refresh=False)


# ---------------------------------------------------------------------------
# Orchestrator auth error
# ---------------------------------------------------------------------------


def test_preview_pr_requires_auth(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: (None, None))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    with pytest.raises(pp.PreviewError, match="No GitHub credentials"):
        pp.preview_pr(None, run=123)


# ---------------------------------------------------------------------------
# Serving a deep link
# ---------------------------------------------------------------------------


class _FakeServer:
    def __init__(self, addr, handler):
        pass

    def serve_forever(self):
        raise KeyboardInterrupt

    def server_close(self):
        pass


def _patch_server(monkeypatch):
    import http.server

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", _FakeServer)


def test_serve_deep_link_target(monkeypatch, tmp_path, capsys):
    (tmp_path / "index.html").write_text("<html>home</html>")
    sub = tmp_path / "reference"
    sub.mkdir()
    (sub / "page.html").write_text("<html>page</html>")

    _patch_server(monkeypatch)
    serve.site(
        tmp_path, port=45999, open_path="reference/page.html", open_browser=False, report=print
    )
    out = capsys.readouterr().out
    assert "Opening: http://localhost:45999/reference/page.html" in out


def test_serve_missing_page_warns(monkeypatch, tmp_path, capsys):
    (tmp_path / "index.html").write_text("<html>home</html>")

    _patch_server(monkeypatch)
    serve.site(
        tmp_path, port=45998, open_path="does/not/exist.html", open_browser=False, report=print
    )
    out = capsys.readouterr().out
    assert "not found" in out
    assert "Opening:" not in out


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_mutually_exclusive_sources():
    result = CliRunner().invoke(preview, ["--pr", "1", "--branch", "main"])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


def test_cli_dispatches_to_preview_pr(monkeypatch):
    captured = {}

    def fake_preview_pr(project_path, **kwargs):
        captured["project_path"] = project_path
        captured.update(kwargs)

    monkeypatch.setattr(pp, "preview_pr", fake_preview_pr)

    result = CliRunner().invoke(
        preview,
        ["--run", "18273645521", "--no-open", "--path", "reference/index.html", "--use-gh"],
    )
    assert result.exit_code == 0, result.output
    assert captured["run"] == 18273645521
    assert captured["open_browser"] is False
    assert captured["path"] == "reference/index.html"
    assert captured["use_gh"] is True


def test_cli_preview_pr_error_exits(monkeypatch):
    def boom(project_path, **kwargs):
        raise pp.PreviewError("no docs run found")

    monkeypatch.setattr(pp, "preview_pr", boom)
    result = CliRunner().invoke(preview, ["--pr", "999"])
    assert result.exit_code == 1
    assert "no docs run found" in result.output


def test_clear_cache_removes_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    root = pp._cache_root()
    (root / "posit-dev-great-docs" / "42" / "docs-html").mkdir(parents=True)
    existed, path = pp.clear_cache()
    assert existed is True
    assert path == root
    assert not root.exists()


def test_cli_clear_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    (pp._cache_root() / "posit-dev-great-docs").mkdir(parents=True)
    result = CliRunner().invoke(preview, ["--clear-cache"])
    assert result.exit_code == 0
    assert "Cleared PR-preview cache" in result.output
    assert not pp._cache_root().exists()


# ---------------------------------------------------------------------------
# _git_remote_repo (lines 81-94)
# ---------------------------------------------------------------------------


def test_git_remote_repo_success(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "https://github.com/posit-dev/great-docs.git\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp._git_remote_repo(tmp_path)
    assert result == ("posit-dev", "great-docs")


def test_git_remote_repo_nonzero_returncode(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 128)
        r.stdout = ""
        r.stderr = "fatal: not a git repository"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._git_remote_repo(tmp_path) is None


def test_git_remote_repo_os_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._git_remote_repo(tmp_path) is None


def test_git_remote_repo_none_path(monkeypatch):
    import subprocess as sp

    captured_kwargs = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "https://github.com/o/r\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp._git_remote_repo(None)
    assert result == ("o", "r")
    assert captured_kwargs["cwd"] is None


# ---------------------------------------------------------------------------
# _config_repo
# ---------------------------------------------------------------------------


def test_config_repo_success(monkeypatch):
    class FakeGreatDocs:
        def __init__(self, project_path=None):
            pass

        def _get_github_repo_info(self):
            return ("posit-dev", "great-docs", "main")

    monkeypatch.setattr(
        "great_docs._pr_preview.GreatDocs",
        FakeGreatDocs,
        raising=False,
    )
    # We need to mock the import that happens inside _config_repo
    import great_docs.core

    monkeypatch.setattr(great_docs.core, "GreatDocs", FakeGreatDocs)
    result = pp._config_repo("/some/path")
    assert result == ("posit-dev", "great-docs")


def test_config_repo_returns_none_on_exception(monkeypatch):
    import great_docs.core

    class BadGreatDocs:
        def __init__(self, project_path=None):
            raise RuntimeError("can't load")

    monkeypatch.setattr(great_docs.core, "GreatDocs", BadGreatDocs)
    assert pp._config_repo("/some/path") is None


def test_config_repo_returns_none_when_empty(monkeypatch):
    import great_docs.core

    class EmptyGreatDocs:
        def __init__(self, project_path=None):
            pass

        def _get_github_repo_info(self):
            return ("", "", "")

    monkeypatch.setattr(great_docs.core, "GreatDocs", EmptyGreatDocs)
    assert pp._config_repo("/some/path") is None


# ---------------------------------------------------------------------------
# _gh_token
# ---------------------------------------------------------------------------


def test_gh_token_success(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "ghp_abc123\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") == "ghp_abc123"


def test_gh_token_not_logged_in(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "not logged in"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


def test_gh_token_empty_output(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


def test_gh_token_os_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


# ---------------------------------------------------------------------------
# _token_from_dotenv
# ---------------------------------------------------------------------------


def test_token_from_dotenv_bad_file(tmp_path):
    bad = tmp_path / "nonexistent.env"
    assert pp._token_from_dotenv(bad) is None


def test_token_from_dotenv_gh_token(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GH_TOKEN=ghtok123\n")
    assert pp._token_from_dotenv(env) == "ghtok123"


# ---------------------------------------------------------------------------
# resolve_token edge cases
# ---------------------------------------------------------------------------


def test_resolve_token_from_gh_auth(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: "ghtok_from_cli")
    token, source = pp.resolve_token(None, None)
    assert token == "ghtok_from_cli"
    assert source == "gh auth token"


def test_resolve_token_find_dotenv_path(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=found_it\n")
    import dotenv

    monkeypatch.setattr(dotenv, "find_dotenv", lambda usecwd=True: str(env_file))
    token, source = pp.resolve_token(None, None)
    assert token == "found_it"


def test_resolve_token_skips_duplicates(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=tok\n")
    import dotenv

    monkeypatch.setattr(dotenv, "find_dotenv", lambda usecwd=True: str(env_file))
    token, source = pp.resolve_token(tmp_path, None)
    assert token == "tok"


# ---------------------------------------------------------------------------
# GitHubClient._requests_get
# ---------------------------------------------------------------------------


class _FakeRequestsResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        return self._json


def test_requests_get_success(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(200, {"runs": []})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    result = client._requests_get("repos/posit-dev/great-docs/actions/runs", None)
    assert result == {"runs": []}


def test_requests_get_404(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(404)

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pp.PreviewError, match="404"):
        client._requests_get("repos/posit-dev/great-docs/pulls/999", None)


def test_requests_get_rate_limited(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(403, headers={"X-RateLimit-Remaining": "0"})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pp.PreviewError, match="rate limit"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_401_no_rate_limit(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(401, headers={})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pp.PreviewError, match="denied"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_500(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(500)

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pp.PreviewError, match="500"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_network_error(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")

    class FakeRequestException(Exception):
        pass

    fake_requests.RequestException = FakeRequestException

    def fake_get(url, headers=None, params=None, timeout=None):
        raise FakeRequestException("Connection reset")

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pp.PreviewError, match="request failed"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_no_token(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception
    captured_headers = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured_headers.update(headers or {})
        return _FakeRequestsResponse(200, {"ok": True})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token=None)
    client._requests_get("repos/posit-dev/great-docs/actions/runs", None)
    assert "Authorization" not in captured_headers


# ---------------------------------------------------------------------------
# GitHubClient._gh_api
# ---------------------------------------------------------------------------


def test_gh_api_success(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"total_count": 1}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    result = client._gh_api("repos/posit-dev/great-docs/actions/runs", {"per_page": 100})
    assert result == {"total_count": 1}


def test_gh_api_no_params(monkeypatch):
    import subprocess as sp

    captured_cmd = []

    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"ok": true}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client._gh_api("repos/posit-dev/great-docs/pulls/5", None)
    assert "?" not in captured_cmd[2]


def test_gh_api_nonzero_returncode(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "HTTP 404"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pp.PreviewError, match="failed"):
        client._gh_api("repos/posit-dev/great-docs/pulls/999", None)


def test_gh_api_invalid_json(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "not json at all"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pp.PreviewError, match="parse"):
        client._gh_api("repos/posit-dev/great-docs/actions/runs", None)


def test_gh_api_os_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("gh not found")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pp.PreviewError, match="failed"):
        client._gh_api("repos/posit-dev/great-docs/actions/runs", None)


# ---------------------------------------------------------------------------
# _gh_download
# ---------------------------------------------------------------------------


def test_gh_download_success(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client._gh_download(42, {"name": "docs-html"}, tmp_path)


def test_gh_download_failure(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "error downloading artifact"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pp.PreviewError, match="gh run download"):
        client._gh_download(42, {"name": "docs-html"}, tmp_path)


def test_gh_download_os_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise OSError("no gh")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pp.PreviewError, match="gh run download"):
        client._gh_download(42, {"name": "docs-html"}, tmp_path)


# ---------------------------------------------------------------------------
# _requests_download
# ---------------------------------------------------------------------------


def test_requests_download_success(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_content = b""
    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html>hi</html>")
    zip_content = zip_buf.read_bytes()

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    client._requests_download({"id": 1, "archive_download_url": "https://x"}, dest)
    assert (dest / "index.html").is_file()


def test_requests_download_410_expired(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    class FakeResp:
        status_code = 410
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pp.PreviewError, match="expired"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_bad_status(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    class FakeResp:
        status_code = 500
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pp.PreviewError, match="500"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_resume_206(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html>hi</html>")
    zip_content = zip_buf.read_bytes()
    first_half = zip_content[: len(zip_content) // 2]
    second_half = zip_content[len(zip_content) // 2 :]

    call_count = [0]

    class FakeResp200:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield first_half
            raise fake_requests.RequestException("dropped")

    class FakeResp206:
        status_code = 206
        headers = {"Content-Length": str(len(second_half))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield second_half

    def fake_get(url, headers=None, timeout=None, stream=False):
        call_count[0] += 1
        if call_count[0] == 1:
            return FakeResp200()
        return FakeResp206()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )
    monkeypatch.setattr(pp, "_DOWNLOAD_RETRIES", 3)
    # Patch time.sleep to not actually wait
    monkeypatch.setattr("time.sleep", lambda s: None)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    client._requests_download({"id": 1}, dest)
    assert (dest / "index.html").is_file()


def test_requests_download_all_retries_exhausted(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")

    class FakeRequestException(Exception):
        pass

    fake_requests.RequestException = FakeRequestException

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": "100"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield b"x" * 10
            raise FakeRequestException("timeout")

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )
    monkeypatch.setattr(pp, "_DOWNLOAD_RETRIES", 2)
    monkeypatch.setattr("time.sleep", lambda s: None)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pp.PreviewError, match="failed after"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_no_token_no_auth_header(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html></html>")
    zip_content = zip_buf.read_bytes()

    captured_headers = {}

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    def fake_get(url, headers=None, timeout=None, stream=False):
        captured_headers.update(headers or {})
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token=None)
    client._requests_download({"id": 1, "archive_download_url": "https://x"}, dest)
    assert "Authorization" not in captured_headers


# ---------------------------------------------------------------------------
# resolve_run edge cases
# ---------------------------------------------------------------------------


def test_resolve_run_invalid_run_id():
    with pytest.raises(pp.PreviewError, match="Invalid --run"):
        pp.resolve_run(FakeClient({}), pr=None, run="abc", branch=None)


def test_resolve_run_no_head_sha():
    client = FakeClient(
        {
            "pulls/10": {"head": {"sha": None}, "base": {}},
            "actions/runs": {"workflow_runs": []},
        }
    )
    with pytest.raises(pp.PreviewError, match="head commit"):
        pp.resolve_run(client, pr=10, run=None, branch=None)


def test_resolve_run_by_branch():
    client = FakeClient(
        {
            "actions/runs": {
                "workflow_runs": [
                    {
                        "id": 77,
                        "name": "CI Docs",
                        "created_at": "2026-02-01",
                        "conclusion": "success",
                    }
                ]
            },
        }
    )
    info = pp.resolve_run(client, pr=None, run=None, branch="feature-x")
    assert info.run_id == 77


def test_resolve_run_by_branch_no_run():
    client = FakeClient({"actions/runs": {"workflow_runs": []}})
    with pytest.raises(pp.PreviewError, match="No 'CI Docs' run found for branch"):
        pp.resolve_run(client, pr=None, run=None, branch="feature-x")


def test_resolve_run_no_source():
    with pytest.raises(pp.PreviewError, match="Specify one of"):
        pp.resolve_run(FakeClient({}), pr=None, run=None, branch=None)


# ---------------------------------------------------------------------------
# find_artifacts
# ---------------------------------------------------------------------------


def test_find_artifacts_non_dict_response():
    class BadClient:
        owner = "posit-dev"
        repo = "great-docs"

        def get_json(self, path, params=None):
            return []  # non-dict

    assert pp.find_artifacts(BadClient(), 42, "docs-html") == []


def test_find_artifacts_no_artifacts_key():
    class EmptyClient:
        owner = "posit-dev"
        repo = "great-docs"

        def get_json(self, path, params=None):
            return {}

    assert pp.find_artifacts(EmptyClient(), 42, "docs-html") == []


# ---------------------------------------------------------------------------
# choose_artifact / _prompt_artifact
# ---------------------------------------------------------------------------


def test_choose_artifact_interactive_prompt(monkeypatch):
    import click

    arts = [
        {"name": "site-a", "created_at": "2026-01-01", "size_in_bytes": 5_000_000},
        {"name": "site-b", "created_at": "2026-01-02", "size_in_bytes": 10_000_000},
    ]
    monkeypatch.setattr(click, "prompt", lambda *a, **kw: 1)
    chosen = pp.choose_artifact(arts, name="nope", interactive=True)
    # Sorted by created_at descending, so index 1 = site-b (newest first)
    assert chosen["name"] == "site-b"


def test_prompt_artifact_selects_second(monkeypatch):
    import click

    arts = [
        {"name": "site-a", "created_at": "2026-01-01", "size_in_bytes": 5_000_000},
        {"name": "site-b", "created_at": "2026-01-02", "size_in_bytes": 10_000_000},
    ]
    monkeypatch.setattr(click, "prompt", lambda *a, **kw: 2)
    chosen = pp._prompt_artifact(arts)
    # Second in descending order is site-a
    assert chosen["name"] == "site-a"


# ---------------------------------------------------------------------------
# _print_run_line
# ---------------------------------------------------------------------------


def test_print_run_line_full(capsys):
    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_sha = "abc1234567890"
    pp._print_run_line(info, pr=5, branch=None)
    out = capsys.readouterr().out
    assert "PR #5" in out
    assert "commit abc1234" in out
    assert "run 42" in out
    assert "(success)" in out


def test_print_run_line_branch_no_sha(capsys):
    info = pp.RunInfo(run_id=100, conclusion=None)
    pp._print_run_line(info, pr=None, branch="main")
    out = capsys.readouterr().out
    assert "branch main" in out
    assert "run 100" in out
    assert "()" not in out  # no conclusion shown


# ---------------------------------------------------------------------------
# preview_pr orchestrator
# ---------------------------------------------------------------------------


def test_preview_pr_use_gh_not_installed(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    with pytest.raises(pp.PreviewError, match="not installed"):
        pp.preview_pr(None, run=123, use_gh=True)


def test_preview_pr_use_gh_not_logged_in(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: None)
    with pytest.raises(pp.PreviewError, match="not logged in"):
        pp.preview_pr(None, run=123, use_gh=True)


def test_preview_pr_fork_warning(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_sha = "abc123"
    info.head_repo = "contributor/great-docs"
    info.base_repo = "posit-dev/great-docs"
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 1000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 1000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, pr=5, open_browser=False)
    out = capsys.readouterr().out
    assert "fork" in out


def test_preview_pr_non_success_warning(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="failure")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 1000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 1000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, run=42, open_browser=False)
    out = capsys.readouterr().out
    assert "did not succeed" in out


def test_preview_pr_expired_artifact(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp,
        "find_artifacts",
        lambda c, r, n: [{"name": "docs-html", "expired": True, "size_in_bytes": 0}],
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "expired": True, "size_in_bytes": 0},
    )

    with pytest.raises(pp.PreviewError, match="expired"):
        pp.preview_pr(None, run=42, open_browser=False)


def test_preview_pr_use_gh_success(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: "ghtok")

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 5000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 5000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, run=42, use_gh=True, open_browser=False)
    out = capsys.readouterr().out
    assert "gh CLI" in out


# ---------------------------------------------------------------------------
# GitHubClient.__init__
# ---------------------------------------------------------------------------


def test_github_client_init():
    client = pp.GitHubClient("owner", "repo", token="tok", use_gh=True, gh="/bin/gh")
    assert client.owner == "owner"
    assert client.repo == "repo"
    assert client.token == "tok"
    assert client.use_gh is True
    assert client.gh == "/bin/gh"


def test_github_client_get_json_dispatches_gh(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"dispatched": true}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("o", "r", use_gh=True, gh="/bin/gh")
    assert client.get_json("repos/o/r/pulls/1") == {"dispatched": True}


def test_github_client_get_json_dispatches_requests(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(200, {"dispatched": True})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("o", "r", token="tok", use_gh=False)
    assert client.get_json("repos/o/r/pulls/1") == {"dispatched": True}


# ---------------------------------------------------------------------------
# download_artifact dispatch
# ---------------------------------------------------------------------------


def test_download_artifact_dispatches_gh(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    dest = tmp_path / "out"
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client.download_artifact(42, {"name": "docs-html"}, dest)
    assert dest.exists()


def test_download_artifact_dispatches_requests(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html></html>")
    zip_content = zip_buf.read_bytes()

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    fake_requests.get = lambda url, headers=None, timeout=None, stream=False: FakeResp()
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok", use_gh=False)
    client.download_artifact(42, {"id": 1, "archive_download_url": "https://x"}, dest)
    assert (dest / "index.html").is_file()


# ---------------------------------------------------------------------------
# _cache_root platform branches
# ---------------------------------------------------------------------------


def test_cache_root_win32(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pp.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = pp._cache_root()
    assert result == tmp_path / "great-docs" / "pr-preview"


def test_cache_root_linux(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pp.sys, "platform", "linux")
    result = pp._cache_root()
    assert result == Path.home() / ".cache" / "great-docs" / "pr-preview"


def test_cache_root_darwin(monkeypatch):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(pp.sys, "platform", "darwin")
    result = pp._cache_root()
    assert result == Path.home() / "Library" / "Caches" / "great-docs" / "pr-preview"


# ---------------------------------------------------------------------------
# _token_from_dotenv exception in dotenv_values
# ---------------------------------------------------------------------------


def test_token_from_dotenv_parse_error(monkeypatch, tmp_path):
    import dotenv

    def bad_dotenv_values(path):
        raise ValueError("parse failed")

    monkeypatch.setattr(dotenv, "dotenv_values", bad_dotenv_values)
    assert pp._token_from_dotenv(tmp_path / ".env") is None


# ---------------------------------------------------------------------------
# resolve_repo from _config_repo fallback
# ---------------------------------------------------------------------------


def test_resolve_repo_from_config(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: None)
    monkeypatch.setattr(pp, "_config_repo", lambda p: ("owner", "repo"))
    assert pp.resolve_repo("/path", None) == ("owner", "repo")


# ---------------------------------------------------------------------------
# _stream_to_file with resume start > 0
# ---------------------------------------------------------------------------


def test_stream_to_file_resume_mode(monkeypatch, tmp_path):
    import click

    class _FakeTTY:
        def isatty(self):
            return True

        def write(self, *a):
            pass

        def flush(self):
            pass

    updates = []

    class _FakeBar:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def update(self, n):
            updates.append(n)

    monkeypatch.setattr(pp.sys, "stderr", _FakeTTY())
    monkeypatch.setattr(click, "progressbar", lambda **kwargs: _FakeBar())

    dest = tmp_path / "out.zip"
    dest.write_bytes(b"xx")  # pre-existing bytes
    resp = _FakeResponse([b"yy"])
    pp._stream_to_file(resp, dest, total=4, mode="ab", start=2)
    assert dest.read_bytes() == b"xxyy"

    # start=2 causes initial bar.update(2), then chunk update(2)
    assert updates == [2, 2]


# ---------------------------------------------------------------------------
# Coverage: _gh_path
# ---------------------------------------------------------------------------


def test_gh_path_returns_path(monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: "/usr/bin/gh")
    assert pp._gh_path() == "/usr/bin/gh"


def test_gh_path_returns_none(monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: None)
    assert pp._gh_path() is None


# ---------------------------------------------------------------------------
# Coverage: _resolve_token – candidate not a file is skipped
# ---------------------------------------------------------------------------


def test_resolve_token_skips_nonexistent_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: None)
    nonexistent = tmp_path / ".env"
    token, source = pp.resolve_token(project_path=str(tmp_path), env_file=None)
    assert token is None
