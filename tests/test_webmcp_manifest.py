"""Tests for the WebMCP manifest."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from great_docs._build import finish
from great_docs._build.steps import Skipped
from great_docs._interlinks.sphinx_inventory import Inventory, InventoryEntry, encode
from great_docs._project.layout import Layout
from great_docs._website.ai_agents import webmcp_manifest, webmcp_pages
from great_docs._website.ai_agents.webmcp_manifest import MANIFEST_FILE, Root, SiteInfo
from great_docs._website.ai_agents.webmcp_pages import PageFacts, SectionFacts
from tests.support import write_config, write_pyproject

SITE = SiteInfo(
    name="example",
    title="Example",
    description="An example package",
    version="1.2.0",
    repo="https://github.com/acme/example",
    license="MIT",
    install=("pip install example", "uv add example"),
)

_QUARTO_YML = """\
project:
  type: website
website:
  sidebar:
    - id: user-guide
      contents:
        - user-guide/intro.qmd
        - section: Advanced
          contents:
            - text: Tuning
              href: user-guide/tuning.qmd
            - user-guide/hidden.qmd
    - id: reference
      contents:
        - reference/index.qmd
        - section: Widgets
          contents:
            - reference/Widget.qmd
            - reference/Widget.spin.qmd
            - reference/spin.qmd
        - section: CLI
          contents:
            - reference/cli/index.qmd
"""


def _write(path: Path, content: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _html(classes: str = "", description: str | None = None, body: str = "") -> str:
    meta = f'<meta name="description" content="{description}">' if description else ""
    return (
        f"<!DOCTYPE html><html><head><title>t</title>{meta}</head>"
        f'<body class="{classes}"><main><p>{body}</p>'
        '<meta name="description" content="not this one"></main></body></html>'
    )


def _page(path: str, **fields: Any) -> PageFacts:
    values: dict[str, Any] = {
        "source": path.replace(".html", ".qmd"),
        "title": None,
        "description": None,
        "section": "",
        "tags": (),
        "status": None,
        "date": None,
        "draft": False,
        "webmcp": True,
        "listed": True,
    }
    return PageFacts(path=path, **{**values, **fields})


def _facts(project_dir: Path, sections: list[SectionFacts], pages: list[PageFacts]) -> None:
    data = {
        "schema": 1,
        "sections": [asdict(section) for section in sections],
        "pages": [asdict(page) for page in pages],
    }
    _write(project_dir / webmcp_pages.FACTS_FILE, json.dumps(data))


def _inventory(*entries: tuple[str, str, str, str]) -> bytes:
    """Encode `(name, role, uri, dispname)` entries"""
    return encode(
        Inventory(
            "example",
            "1.2.0",
            tuple(
                InventoryEntry(name, "py", role, 1, uri, disp) for name, role, uri, disp in entries
            ),
        )
    )


def _site(tmp_path: Path) -> Root:
    """Write a small rendered site and the project directory that rendered it"""
    project_dir = tmp_path / "build"
    site_dir = project_dir / "_site"
    _write(project_dir / "_quarto.yml", _QUARTO_YML)
    _facts(
        project_dir,
        [
            SectionFacts("user-guide", "User Guide", "guide"),
            SectionFacts("news", "News", "blog"),
            SectionFacts("empty", "Empty", "guide"),
        ],
        [
            _page("index.html", title="Home"),
            _page("notes.html", title="Notes"),
            _page(
                "user-guide/intro.html",
                title="Intro",
                description="Start   here",
                section="user-guide",
                tags=("setup",),
                status="new",
            ),
            _page("user-guide/tuning.html", section="user-guide"),
            _page("user-guide/hidden.html", section="user-guide", listed=False),
            _page("user-guide/draft.html", section="user-guide", draft=True),
            _page("news/index.html", section="news"),
            _page("news/launch.html", section="news", date="2026-01-02"),
        ],
    )
    search = [
        ("index.html", "Example"),
        ("user-guide/tuning.html", "Tuning"),
        ("user-guide/intro.html", "Introduction"),
        ("user-guide/intro.html#first-steps", "First steps"),
        ("user-guide/hidden.html", "Hidden"),
        ("user-guide/draft.html", "Draft"),
        ("news/launch.html", "Launch"),
        ("news/index.html", "News"),
        ("notes.html", ""),
        ("reference/Widget.spin.html#example.Widget.spin", "Widget.spin"),
        ("reference/Widget.html", "Widget"),
        ("reference/spin.html", "spin"),
        ("reference/index.html", "Reference"),
        ("reference/cli/index.html", "example"),
        ("changelog.html", "Changelog"),
    ]
    _write(
        site_dir / "search.json",
        json.dumps([{"href": href, "title": title, "text": "…"} for href, title in search]),
    )
    pages = {
        "index.html": _html("gd-homepage", SITE.description),
        "notes.html": _html(),
        "user-guide/intro.html": _html(description="Rendered description"),
        "user-guide/tuning.html": _html(description="Make it fast"),
        "user-guide/hidden.html": _html(),
        "user-guide/draft.html": _html(),
        "news/index.html": _html(),
        "news/launch.html": _html(),
        "reference/index.html": _html("doc-reference"),
        "reference/Widget.html": _html("doc-api-page doc-py-api-page", "A widget."),
        "reference/Widget.spin.html": _html("doc-api-page doc-py-api-page", "Spin it."),
        "reference/spin.html": _html("doc-api-page doc-py-api-page", SITE.description),
        "reference/cli/index.html": _html("doc-cli-api-page", SITE.description),
        "changelog.html": _html(),
    }
    for path, content in pages.items():
        _write(site_dir / path, content)
    for md in ["index.md", "user-guide/intro.md", "reference/Widget.md", "reference/cli/index.md"]:
        _write(site_dir / md, "# Page\n")
    _write(site_dir / "changelog.md", "# Changelog\n\n## v1.2.0\n\nText.\n\n## v1.1.0 ##\n")
    _write(site_dir / "llms.txt", "# example\n")
    _write(site_dir / ".well-known" / "agent-skills" / "index.json", '{"skills": []}')
    _write(
        site_dir / "objects.inv",
        _inventory(
            ("example.Widget", "class", "reference/Widget.html#example.Widget", "example.Widget"),
            (
                "example.Widget.spin",
                "method",
                "reference/Widget.spin.html#example.Widget.spin",
                "example.Widget.spin",
            ),
            ("example.spin", "function", "reference/spin.html#example.spin", "example.spin"),
            (
                "example.core.Widget",
                "class",
                "reference/Widget.html#example.Widget",
                "example.Widget",
            ),
        ),
    )
    return Root(site_dir, project_dir, None, "https://example.org/docs/")


def _build(root: Root) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    return webmcp_manifest.build(root, SITE, warn=warnings.append), warnings


class TestBuild:
    def test_the_site_block_describes_the_package(self, tmp_path: Path):
        manifest, warnings = _build(_site(tmp_path))

        assert warnings == []
        assert manifest["schema"] == 1
        assert manifest["generator"].startswith("great-docs ")
        assert manifest["site"] == {
            "name": "example",
            "title": "Example",
            "description": "An example package",
            "version": "1.2.0",
            "url": "https://example.org/docs/",
            "repo": "https://github.com/acme/example",
            "license": "MIT",
            "install": ["pip install example", "uv add example"],
        }

    def test_resources_list_the_files_that_exist(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert manifest["resources"] == {
            "llms_txt": "llms.txt",
            "skills": ".well-known/agent-skills/index.json",
            "search": "search.json",
            "changelog": "changelog.md",
        }

    def test_pages_follow_sections_then_the_sidebar(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert [page["path"] for page in manifest["pages"]] == [
            "index.html",
            "changelog.html",
            "notes.html",
            "user-guide/intro.html",
            "user-guide/tuning.html",
            "news/index.html",
            "news/launch.html",
            "reference/index.html",
            "reference/Widget.html",
            "reference/Widget.spin.html",
            "reference/spin.html",
            "reference/cli/index.html",
        ]

    def test_drafts_and_unlisted_pages_are_left_out(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        paths = {page["path"] for page in manifest["pages"]}
        assert "user-guide/draft.html" not in paths
        assert "user-guide/hidden.html" not in paths

    def test_page_entries_carry_their_facts(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))
        pages = {page["path"]: page for page in manifest["pages"]}

        assert pages["user-guide/intro.html"] == {
            "path": "user-guide/intro.html",
            "md": "user-guide/intro.md",
            "title": "Introduction",
            "section": "user-guide",
            "description": "Start here",
            "kind": "guide",
            "tags": ["setup"],
            "status": "new",
        }
        assert pages["user-guide/tuning.html"] == {
            "path": "user-guide/tuning.html",
            "title": "Tuning",
            "section": "user-guide",
            "group": "Advanced",
            "description": "Make it fast",
            "kind": "guide",
        }
        assert pages["news/launch.html"]["date"] == "2026-01-02"
        assert pages["notes.html"]["title"] == "Notes"
        assert pages["reference/Widget.html"]["group"] == "Widgets"

    def test_the_site_description_is_not_repeated_as_a_page_description(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))
        pages = {page["path"]: page for page in manifest["pages"]}

        assert "description" not in pages["index.html"]
        assert "description" not in pages["reference/cli/index.html"]
        assert pages["reference/Widget.html"]["description"] == "A widget."

    def test_kinds_come_from_body_classes_and_sections(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert {page["path"]: page["kind"] for page in manifest["pages"]} == {
            "index.html": "page",
            "changelog.html": "page",
            "notes.html": "page",
            "user-guide/intro.html": "guide",
            "user-guide/tuning.html": "guide",
            "news/index.html": "page",
            "news/launch.html": "post",
            "reference/index.html": "reference",
            "reference/Widget.html": "api",
            "reference/Widget.spin.html": "api",
            "reference/spin.html": "api",
            "reference/cli/index.html": "cli",
        }

    def test_sections_are_those_with_listed_pages(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert manifest["sections"] == [
            {"id": "user-guide", "title": "User Guide", "kind": "guide"},
            {"id": "news", "title": "News", "kind": "blog"},
            {"id": "reference", "title": "Reference", "kind": "reference"},
        ]

    def test_the_api_lists_public_names_with_unambiguous_aliases(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert manifest["api"] == [
            {
                "name": "example.Widget",
                "kind": "class",
                "section": "Widgets",
                "summary": "A widget.",
                "path": "reference/Widget.html",
                "md": "reference/Widget.md",
                "aliases": ["Widget"],
            },
            {
                "name": "example.Widget.spin",
                "kind": "method",
                "section": "Widgets",
                "summary": "Spin it.",
                "path": "reference/Widget.spin.html",
                "aliases": ["Widget.spin"],
            },
            {
                "name": "example.spin",
                "kind": "function",
                "section": "Widgets",
                "path": "reference/spin.html",
            },
        ]

    def test_a_method_on_its_class_page_has_no_summary(self, tmp_path: Path):
        # The page's description summarizes the class.
        root = _site(tmp_path)
        _write(
            root.site_dir / "objects.inv",
            _inventory(
                (
                    "example.Widget.stop",
                    "method",
                    "reference/Widget.html#stop",
                    "example.Widget.stop",
                ),
                (
                    "example.Widget",
                    "class",
                    "reference/Widget.html#example.Widget",
                    "example.Widget",
                ),
            ),
        )

        manifest, _ = _build(root)

        summaries = {item["name"]: item.get("summary") for item in manifest["api"]}
        assert summaries == {"example.Widget.stop": None, "example.Widget": "A widget."}

    def test_cli_pages_and_the_changelog_are_indexed(self, tmp_path: Path):
        manifest, _ = _build(_site(tmp_path))

        assert manifest["cli"] == [
            {
                "command": "example",
                "path": "reference/cli/index.html",
                "md": "reference/cli/index.md",
            }
        ]
        assert manifest["changelog"] == {
            "path": "changelog.html",
            "md": "changelog.md",
            "versions": ["v1.2.0", "v1.1.0"],
        }

    def test_a_missing_search_index_warns_and_lists_no_pages(self, tmp_path: Path):
        root = _site(tmp_path)
        (root.site_dir / "search.json").unlink()

        manifest, warnings = _build(root)

        assert manifest["pages"] == []
        assert manifest["sections"] == []
        assert len(warnings) == 1
        assert "search.json" in warnings[0]

    def test_an_unreadable_inventory_warns_and_lists_no_api(self, tmp_path: Path):
        root = _site(tmp_path)
        _write(root.site_dir / "objects.inv", b"not an inventory")

        manifest, warnings = _build(root)

        assert manifest["api"] == []
        assert len(warnings) == 1
        assert "objects.inv" in warnings[0]

    def test_missing_facts_and_sidebars_still_list_the_rendered_pages(self, tmp_path: Path):
        root = _site(tmp_path)
        (root.project_dir / webmcp_pages.FACTS_FILE).unlink()
        (root.project_dir / "_quarto.yml").unlink()

        manifest, warnings = _build(root)

        assert warnings == []
        paths = [page["path"] for page in manifest["pages"]]
        assert "user-guide/hidden.html" in paths
        assert paths[0] == "index.html"
        assert manifest["sections"] == [
            {"id": "reference", "title": "Reference", "kind": "reference"}
        ]

    def test_long_descriptions_are_shortened(self, tmp_path: Path):
        root = _site(tmp_path)
        _write(root.site_dir / "notes.html", _html(description="word " * 200))

        manifest, _ = _build(root)

        notes = next(page for page in manifest["pages"] if page["path"] == "notes.html")
        assert len(notes["description"]) <= 300
        assert notes["description"].endswith("…")


class TestWrite:
    def test_the_manifest_is_compact_and_deterministic(self, tmp_path: Path):
        root = _site(tmp_path)

        [path] = webmcp_manifest.write([root], SITE, warn=lambda _: None)
        first = path.read_bytes()
        webmcp_manifest.write([root], SITE, warn=lambda _: None)

        assert path == root.site_dir / MANIFEST_FILE
        assert path.read_bytes() == first
        assert first.endswith(b"\n") and first.count(b"\n") == 1
        assert json.loads(first)["pages"]

    def test_no_entry_is_large(self, tmp_path: Path):
        root = _site(tmp_path)
        _write(root.site_dir / "notes.html", _html(description="x" * 5000))

        manifest, _ = _build(root)

        for key in ("pages", "api", "cli"):
            for entry in manifest[key]:
                assert len(json.dumps(entry, ensure_ascii=False)) < 1000


def _versioned_project(tmp_path: Path) -> Layout:
    write_pyproject(tmp_path, "example")
    write_config(
        tmp_path,
        {
            "webmcp": True,
            "versions": [
                {"tag": "0.3", "latest": True},
                {"tag": "v0.2", "version": "0.2.1"},
                "0.1",
            ],
        },
    )
    return Layout.make(tmp_path)


class TestRoots:
    def test_an_unversioned_site_has_one_root(self, tmp_path: Path):
        write_pyproject(tmp_path, "example")
        write_config(tmp_path, {"webmcp": True})
        layout = Layout.make(tmp_path)

        assert webmcp_manifest.roots(layout.load_config(), layout, "https://x.org/") == [
            Root(layout.site_dir, layout.build_dir, None, "https://x.org/")
        ]

    def test_each_rendered_version_gets_its_own_root(self, tmp_path: Path):
        layout = _versioned_project(tmp_path)
        _write(layout.site_dir / "index.html", _html())
        _write(layout.site_dir / "v" / "0.2" / "index.html", _html())
        _write(layout.site_dir / "v" / "latest" / "index.html", "<meta http-equiv='refresh'>")

        roots = webmcp_manifest.roots(layout.load_config(), layout, "https://x.org/")

        assert roots == [
            Root(layout.site_dir, layout.build_dir, "0.3", "https://x.org/"),
            Root(
                layout.site_dir / "v" / "0.2",
                layout.build_dir_for("v0.2", "0.3"),
                "0.2.1",
                "https://x.org/v/0.2/",
            ),
        ]

    def test_each_version_describes_its_own_api(self, tmp_path: Path):
        latest = _site(tmp_path / "latest")
        old = _site(tmp_path / "old")
        _write(
            old.site_dir / "objects.inv",
            _inventory(("example.Gadget", "class", "reference/Gadget.html", "example.Gadget")),
        )
        targets = [
            Root(latest.site_dir, latest.project_dir, "0.3", None),
            Root(old.site_dir, old.project_dir, "0.2.1", None),
        ]

        written = webmcp_manifest.write(targets, SITE, warn=lambda _: None)

        manifests = [json.loads(path.read_text()) for path in written]
        assert [m["site"]["version"] for m in manifests] == ["0.3", "0.2.1"]
        assert [[a["name"] for a in m["api"]] for m in manifests] == [
            ["example.Widget", "example.Widget.spin", "example.spin"],
            ["example.Gadget"],
        ]


def _run() -> SimpleNamespace:
    project = SimpleNamespace(
        name="example",
        module="example",
        repository=None,
        manifest={"license": "", "description": "An example package"},
    )
    return SimpleNamespace(project=project, identity=SimpleNamespace(name="", base_url=None))


class TestStep:
    def test_the_step_is_skipped_when_webmcp_is_off(self, tmp_path: Path):
        write_pyproject(tmp_path, "example")
        write_config(tmp_path, {})
        layout = Layout.make(tmp_path)

        outcome = finish.webmcp_manifest(_run(), layout.load_config(), layout, None)  # type: ignore[arg-type]

        assert outcome == Skipped("WebMCP not enabled")

    def test_the_step_writes_the_manifest(self, tmp_path: Path):
        write_pyproject(tmp_path, "example")
        write_config(tmp_path, {"webmcp": True})
        layout = Layout.make(tmp_path)
        _write(layout.site_dir / "index.html", _html())
        warnings: list[str] = []

        outcome = finish.webmcp_manifest(
            _run(),  # type: ignore[arg-type]
            layout.load_config(),
            layout,
            SimpleNamespace(warn=warnings.append),  # type: ignore[arg-type]
        )

        assert outcome == "gd-webmcp.json written"
        manifest = json.loads((layout.site_dir / MANIFEST_FILE).read_text())
        assert manifest["site"]["title"] == "example"
        assert manifest["site"]["install"] == ["pip install example", "uv add example"]
        assert "license" not in manifest["site"]
        assert len(warnings) == 1
