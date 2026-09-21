"""
Verify published layout contracts with real Git histories and Quarto renders

This module requires Quarto, Git, Node and Jupyter because it verifies that a
real build behaves identically regardless of where the documentation source
lives.

`CASES` builds the same fixture package with its source at the project root,
in `docs/`, or in `website/`. Versioned cases use either `1.5.0` or the
`v`-prefixed `v1.5.0` tag, and two cases have no version history. One case
authors the source at the project root and migrates it to `docs/`, exercising
the migration path as well as the final layout.

The `rendered` fixture builds each case twice through a real `great-docs
build` subprocess. The tests verify rendered content, freeze-cache reuse,
historical-output isolation, version-selector URL resolution in Node, and
semantic equality across layouts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from great_docs._layout import Layout
from great_docs._layout_migration import analyse, apply

pytestmark = pytest.mark.xdist_group("layout_rendered")


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture content: the package, its Git history, and the acceptance build
# ═══════════════════════════════════════════════════════════════════════════════

ROOT = Path(__file__).resolve().parents[1]
IMAGE = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="blue"/></svg>\n'

# Every build includes `shared()`, which provides a stable page for byte-for-
# byte comparisons across layouts and tag cases.
PACKAGE = '''"""A package for rendered layout acceptance"""

def shared(value: int = 1) -> int:
    """
    Return the shared value

    Parameters
    ----------
    value
        Value to return.

    Returns
    -------
    value
        The unchanged value.
    """
    return value
'''

# Commit this function after the historical tag so historical builds must not
# expose it. This checks per-version API filtering.
LATEST = '''
def latest_only() -> str:
    """Identify an API added after the historical release"""
    return "latest"
'''

# Run the real `great-docs build` in a subprocess, including module imports,
# Quarto rendering, and site generation. Stub release lookup because these
# acceptance builds run offline.
BUILD = """
import sys
from great_docs import GreatDocs
GreatDocs._fetch_github_releases = lambda self, *args, **kwargs: []
GreatDocs(project_path=sys.argv[1], config_path=sys.argv[2]).build()
"""


# ═══════════════════════════════════════════════════════════════════════════════
# HTML inspection
# ═══════════════════════════════════════════════════════════════════════════════


class Page(HTMLParser):
    """Collect semantic text and resource references from emitted HTML"""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[str] = []
        self.images: list[str] = []
        self.resources: list[str] = []
        self.ids: set[str] = set()
        self.main_text: list[str] = []
        self.main_links: list[str] = []
        self._main = False
        self.feed(path.read_text())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "main":
            self._main = True
        if values.get("id"):
            self.ids.add(str(values["id"]))
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
            if self._main:
                self.main_links.append(str(values["href"]))
        if tag == "img" and values.get("src"):
            self.images.append(str(values["src"]))
        if tag == "script" and values.get("src"):
            self.resources.append(str(values["src"]))
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.resources.append(str(values["href"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self._main = False

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._main:
            self.main_text.append(data)


# ═══════════════════════════════════════════════════════════════════════════════
# Filesystem and Git helpers
# ═══════════════════════════════════════════════════════════════════════════════


def write_file(root: Path, name: str, content: str) -> Path:
    """
    Write a fixture file and create its parent directories

    Parameters
    ----------
    root
        Directory the path is relative to.
    name
        Path of the file, relative to `root`.
    content
        Text to write.

    Returns
    -------
    :
        The path written.
    """
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_git(root: Path, *args: str) -> str:
    """
    Run a Git command in the fixture repository

    Parameters
    ----------
    root
        Repository working directory.
    *args
        Arguments passed to `git`.

    Returns
    -------
    :
        The command's stripped standard output.
    """
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# The rendered fixture: one real build per layout and tag combination
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Rendered:
    """
    A built layout, its historical tag, and its execution log
    """

    layout: Layout
    tag: str | None
    executions: Path


def make_project(root: Path, directory: str, tag: str | None, migrate: bool) -> Rendered:
    """
    Build a package with a two-commit history and a great-docs configuration

    Parameters
    ----------
    root
        Directory to build the fixture in.
    directory
        Documentation source directory relative to `root`. Use `"."` for the
        project root.
    tag
        Historical version tag to create before the latest commit. Use `None`
        for a single-version project.
    migrate
        Whether to author the source at the project root and move it with the
        layout migration before building.

    Returns
    -------
    :
        The built layout, its tag, and its execution-log path.
    """
    source = root if migrate else root / directory
    source.mkdir(parents=True, exist_ok=True)
    write_file(root, "pyproject.toml", '[project]\nname = "layout-sample"\nversion = "2.0.0"\n')
    write_file(root, "src/layout_sample/__init__.py", PACKAGE)
    write_file(root, "README.md", "# Layout sample\n\nPackage README fallback sentinel.\n")
    write_file(root, "shared/picture.svg", IMAGE)
    write_file(
        root,
        "shared/references.bib",
        "@book{layoutref, title={Layout bibliography sentinel}, author={Example, Ada}, year={2020}}\n",
    )
    shared = "shared" if source == root else "../shared"
    guide = f"""---
title: Frozen guide
jupyter: python3
---

Guide prose sentinel. See [the homepage](../index.qmd).

![Shared image](../{shared}/picture.svg)

Read the shared reference [@layoutref].

```{{python}}
import os
from pathlib import Path
with Path(os.environ["GD_LAYOUT_EXECUTION_LOG"]).open("a") as output:
    output.write("executed\\n")
print("Frozen execution sentinel")
```
"""
    write_file(source, "user_guide/01-frozen.qmd", guide)
    config_text = f"""module: layout_sample
display_name: Layout sample
dynamic: false
repo: https://github.com/layout-example/layout-sample
github_style: icon
site_url: https://layout.example.test
pypi: false
changelog:
  enabled: false
skill:
  enabled: false
mcp:
  enabled: false
freeze: auto
bibliography: {shared}/references.bib
"""
    if tag:
        config_text += f'''versions:
  - tag: "2.0.0"
    latest: true
  - tag: "{tag}"
    git_ref: "{tag}"
'''
    config = write_file(source, "great-docs.yml", config_text)
    run_git(root, "init", "-q")
    run_git(root, "config", "user.name", "Layout acceptance")
    run_git(root, "config", "user.email", "layout@example.test")
    run_git(root, "add", ".")
    run_git(root, "commit", "-qm", "Create historical fixture")
    if tag:
        run_git(root, "tag", tag)
    write_file(root, "src/layout_sample/__init__.py", PACKAGE + LATEST)
    run_git(root, "add", "src/layout_sample/__init__.py")
    run_git(root, "commit", "-qm", "Add latest API")
    run_git(root, "tag", "2.0.0")
    layout = Layout.make(root, config)
    if migrate:
        proposal = analyse(layout, root / "docs")
        assert not proposal.blockers, proposal.blockers
        apply(proposal)
        layout = Layout.make(root)
        # Only the guide and configuration reference `shared`, so migration
        # folds it into the destination with those files.
        assert (root / "docs/shared/picture.svg").read_text() == IMAGE
        assert (root / "README.md").is_file()
    return Rendered(layout, tag, root / "executions.log")


# Build each source location with both tag styles, then build `docs/` and
# `website/` once more without version history.
CASES = [(directory, tag) for directory in (".", "docs", "website") for tag in ("1.5.0", "v1.5.0")]
CASES += [("docs", None), ("website", None)]


@pytest.fixture(scope="module")
def required_tools() -> None:
    """
    Skip this module's tests when an external tool it shells out to is missing
    """
    for name in ("git", "tar", "node", "quarto"):
        if not shutil.which(name):
            pytest.skip(f"Real layout acceptance requires {name} on PATH")
    result = subprocess.run(
        [sys.executable, "-c", "import nbformat, jupyter_client, ipykernel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Real layout acceptance requires Jupyter: {result.stderr}")
    version = subprocess.run(["quarto", "--version"], check=True, capture_output=True, text=True)
    print(f"Layout acceptance Quarto: {version.stdout.strip()}")


@pytest.fixture(scope="module", params=CASES, ids=lambda case: f"{case[0]}-{case[1] or 'single'}")
def rendered(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, required_tools: None
) -> Rendered:
    """
    Build one project twice and return its resulting layout

    The second build makes freeze-cache reuse observable through the execution
    log. A single build cannot distinguish reuse from re-execution.

    Parameters
    ----------
    request
        Supplies a `(directory, tag)` case from `CASES`.
    tmp_path_factory
        Creates a temporary project directory for the case.
    required_tools
        Confirms that Git, tar, Node, Quarto, and Jupyter are available before
        the fixture starts a subprocess.

    Returns
    -------
    :
        The built layout, its tag, and its execution-log path.
    """
    directory, tag = request.param
    root = tmp_path_factory.mktemp(f"layout-{directory.replace('.', 'root')}-{tag or 'single'}")
    fixture = make_project(root, directory, tag, migrate=directory == "docs" and tag == "1.5.0")
    env = os.environ.copy()
    env["GD_LAYOUT_EXECUTION_LOG"] = str(fixture.executions)
    env["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(root / "src"), env.get("PYTHONPATH", "")))
    for attempt in (1, 2):
        result = subprocess.run(
            [sys.executable, "-c", BUILD, str(root), str(fixture.layout.config_path)],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        write_file(root, f"build-{attempt}.log", result.stdout + result.stderr)
        assert result.returncode == 0, (
            f"Build {attempt} failed in {root}:\n{result.stdout}\n{result.stderr}"
        )
        assert (fixture.layout.site_dir / "index.html").is_file(), (
            f"No published site in {root}; inspect build-{attempt}.log"
        )
        if tag:
            assert (fixture.layout.site_dir / "v/1.5.0/index.html").is_file(), (
                f"Missing historical output after build {attempt}: {root}"
            )
    print(f"Rendered twice: {fixture.layout.site_dir}")
    return fixture


@pytest.fixture(scope="module")
def semantic_baselines() -> dict[str, tuple[str, tuple[str, ...]]]:
    """
    Store the first case's page content for cross-layout comparisons
    """
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════


def assert_local_targets(page_path: Path, site: Path) -> Page:
    """
    Parse a page and verify that every local target resolves

    Parameters
    ----------
    page_path
        HTML page to parse.
    site
        Site root for resolving absolute (`/...`) targets.

    Returns
    -------
    :
        The parsed page for further assertions.
    """
    page = Page(page_path)
    for link in page.links + page.images + page.resources:
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = (
            site / unquote(parsed.path).lstrip("/")
            if parsed.path.startswith("/")
            else page_path.parent / unquote(parsed.path)
        )
        if target.is_dir():
            target /= "index.html"
        assert target.is_file(), f"Broken local target {link!r} from {page_path}"
    return page


def test_freeze_skips_execution_on_rebuild(rendered: Rendered) -> None:
    """
    Reuse the frozen guide's cached execution on rebuild
    """
    expected_runs = 2 if rendered.tag else 1
    assert rendered.executions.read_text().splitlines() == ["executed"] * expected_runs


def test_homepage_shows_readme_fallback(rendered: Rendered) -> None:
    """
    Use the package README when no index page is authored
    """
    site = rendered.layout.site_dir
    homepage = assert_local_targets(site / "index.html", site)
    assert "Package README fallback sentinel." in " ".join(homepage.text)


def test_user_guide_renders_execution_and_citation(rendered: Rendered) -> None:
    """
    Render the guide prose, executed cell, citation, and image
    """
    site = rendered.layout.site_dir
    guide = assert_local_targets(site / "user-guide/frozen.html", site)
    assert "Guide prose sentinel." in " ".join(guide.text)
    assert "Frozen execution sentinel" in " ".join(guide.text)
    assert "ref-layoutref" in guide.ids
    assert any(
        (site / "user-guide" / src).resolve().read_text() == IMAGE
        for src in guide.images
        if "picture.svg" in src
    )


def test_api_reference_links_to_tagged_source(rendered: Rendered) -> None:
    """
    Link API source to the built version's Git tag
    """
    site = rendered.layout.site_dir
    api = assert_local_targets(site / "reference/shared.html", site)
    assert any(
        "github.com/layout-example/layout-sample/blob/2.0.0/src/layout_sample/__init__.py" in link
        for link in api.links
    )
    assert (site / "reference/latest_only.html").is_file()


def test_build_directory_matches_layout_conventions(rendered: Rendered) -> None:
    """
    Place build and freeze directories according to the selected layout
    """
    layout = rendered.layout
    assert layout.freeze_dir.is_dir()
    if layout.source_dir == layout.package_root:
        return
    assert layout.build_dir == layout.source_dir / "_quarto/default"
    assert not (layout.source_dir / "_quarto/_quarto.yml").exists()
    assert not (layout.source_dir / "_quarto/2.0.0").exists()
    assert (layout.build_dir / "_site/index.html").is_file()


def test_historical_version_output_is_isolated(rendered: Rendered) -> None:
    """
    Keep historical site, cache, and manifest entries isolated
    """
    layout, tag = rendered.layout, rendered.tag
    if tag is None:
        return
    historical = layout.build_dir_for(tag, "2.0.0")
    assert historical.parent == layout.build_dir.parent
    assert historical.name == (
        f"great-docs-{tag}" if layout.source_dir == layout.package_root else tag
    )
    assert (historical / "_site/index.html").is_file()
    old = layout.site_dir / "v/1.5.0"
    assert_local_targets(old / "index.html", layout.site_dir)
    assert_local_targets(old / "user-guide/frozen.html", layout.site_dir)
    assert (old / "reference/shared.html").is_file()
    assert not (old / "reference/latest_only.html").exists()
    assert not (layout.site_dir / "v/v1.5.0").exists()
    assert (layout.cache_dir / "snapshots" / f"{tag}.json").is_file()
    manifest = json.loads((layout.site_dir / "_version_map.json").read_text())
    assert [(version["tag"], version["path_prefix"]) for version in manifest["versions"]] == [
        ("2.0.0", ""),
        (tag, "v/1.5.0"),
    ]


def test_semantics_match_across_layouts(
    rendered: Rendered, semantic_baselines: dict[str, tuple[str, tuple[str, ...]]]
) -> None:
    """
    Keep visible text and links identical across source layouts
    """
    for prefix in ["", "v/1.5.0/"] if rendered.tag else [""]:
        for name in ("index.html", "user-guide/frozen.html", "reference/shared.html"):
            page = Page(rendered.layout.site_dir / prefix / name)
            semantic = (
                re.sub(r"\s+", " ", " ".join(page.main_text)).strip(),
                tuple(sorted(page.main_links)),
            )
            key = f"{rendered.tag}:{prefix}{name}"
            assert semantic == semantic_baselines.setdefault(key, semantic), key


def test_emitted_version_navigation(rendered: Rendered) -> None:
    """
    Resolve version-selector URLs and canonical links correctly
    """
    if rendered.tag is None:
        assert not (rendered.layout.site_dir / "_version_map.json").exists()
        return
    site = rendered.layout.site_dir
    manifest = json.loads((site / "_version_map.json").read_text())
    assert manifest["pages"]["reference/latest_only.html"] == ["2.0.0"]
    script = (site / "version-selector.js").read_text()
    html = (site / "v/1.5.0/user-guide/frozen.html").read_text()
    canonical = [
        body
        for body in re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        if 'link.rel="canonical"' in body
    ]
    assert len(canonical) == 1
    # Run the real version-selector.js and the page's canonical-link script
    # against the same stubbed browser, then compare their JSON results.
    harness = r"""
const fs = require("fs"), vm = require("vm");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const links = [];
const context = {
  window: {location: {pathname: "/v/1.5.0/user-guide/frozen.html"}},
  document: {readyState: "loading", addEventListener() {}}
};
const source = input.script.replace('if (document.readyState === "loading")',
  'globalThis.selector = {getSiteBasePath, detectCurrentVersion, getCurrentRelPath, buildVersionUrl}; if (document.readyState === "loading")');
vm.runInNewContext(source, context);
const selector = context.selector, map = input.map;
const base = selector.getSiteBasePath(map);
const result = {
  base, tag: selector.detectCurrentVersion(map),
  page: selector.getCurrentRelPath(map, base),
  latest: selector.buildVersionUrl(map, "2.0.0", "user-guide/frozen.html", base),
  historical: selector.buildVersionUrl(map, input.tag, "user-guide/frozen.html", base),
  absent: selector.buildVersionUrl(map, input.tag, "reference/latest_only.html", base)
};
context.document = {
  addEventListener(event, callback) {callback()},
  createElement() {return {}}, head: {appendChild(link) {links.push(link)}}
};
vm.runInNewContext(input.canonical, context);
result.canonical = links;
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps(
            {"script": script, "map": manifest, "tag": rendered.tag, "canonical": canonical[0]}
        ),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == {
        "base": "",
        "tag": rendered.tag,
        "page": "user-guide/frozen.html",
        "latest": "/user-guide/frozen.html",
        "historical": "/v/1.5.0/user-guide/frozen.html",
        "absent": "/v/1.5.0/index.html",
        "canonical": [
            {"rel": "canonical", "href": "https://layout.example.test/user-guide/frozen.html"}
        ],
    }
    for alias in ("latest", "stable"):
        redirect = (site / "v" / alias / "index.html").read_text()
        assert '<meta http-equiv="refresh" content="0; url=/">' in redirect
        assert '<link rel="canonical" href="/">' in redirect
        assert Page(site / "v" / alias / "index.html").links == ["/"]
