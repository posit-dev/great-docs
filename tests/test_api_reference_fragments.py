from __future__ import annotations

import io
import subprocess
from pathlib import Path
from textwrap import dedent
from urllib.parse import urlsplit

import griffe as gf
import pytest
from bs4 import BeautifulSoup

from great_docs import GreatDocs
from great_docs._apiref.content import Doc
from great_docs._build import pipeline, quarto
from great_docs._build.log import BuildLog
from great_docs.rendering import FunctionRenderer
from tests.gauntlet_sites import quarto_available
from tests.support import StubRemote, write_config, write_pyproject


@pytest.fixture(scope="module")
def fragment_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render a reference with inline and standalone members"""
    if not quarto_available():
        pytest.skip("Quarto is required to check rendered fragment targets")

    root = tmp_path_factory.mktemp("reference-fragments")
    name = "reference_fragments"
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text(
        dedent('''\
            class Counter:
                """Count items."""

                def total(self):
                    """Return the total."""

                def __iter__(self):
                    """Iterate over the items."""

            class Separate:
                """Document the method on its own page."""

                def total(self):
                    """Return a different total."""
        '''),
        encoding="utf-8",
    )
    write_pyproject(root, name)
    write_config(
        root,
        {
            "dynamic": False,
            "reference": [
                {
                    "title": "Classes",
                    "contents": [
                        {"name": "Counter", "members_on_same_page": True},
                        {"name": "Separate", "members_on_same_page": False},
                    ],
                }
            ],
        },
    )
    guide = root / "user_guide"
    guide.mkdir()
    (guide / "intro.qmd").write_text(
        f"---\ntitle: Introduction\n---\n\nUse `~~{name}.Counter.total` to count items.\n",
        encoding="utf-8",
    )

    docs = GreatDocs(project_path=str(root))
    config = docs._config
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(root))
        pipeline.prepare_for_freeze(
            config, docs.layout, BuildLog(stream=io.StringIO()), remote=StubRemote()
        )
        rendered = subprocess.run(
            ["quarto", "render"],
            cwd=docs.layout.build_dir,
            env=quarto.environment(config),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    assert rendered.returncode == 0, rendered.stderr
    return docs.layout.build_dir / "_site"


def _html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("reference/index.html", "Counter"),
        ("user-guide/intro.html", "total"),
        ("reference/Counter.html", "__iter__()"),
    ],
    ids=["index-object", "guide-autolink", "dunder-summary"],
)
def test_generated_api_fragment_lands_once(fragment_site: Path, source: str, text: str) -> None:
    """A generated reference link has exactly one rendered fragment target"""
    page = fragment_site / source
    links = [link for link in _html(page).select("main a[href]") if link.get_text() == text]
    assert len(links) == 1, [link.get_text() for link in links]
    target = urlsplit(str(links[0]["href"]))
    assert target.fragment
    destination = page.parent / target.path if target.path else page
    assert len(_html(destination).find_all(id=target.fragment)) == 1, links[0]


def test_reference_keeps_existing_short_and_standalone_member_links(fragment_site: Path) -> None:
    """Keep native member heading IDs and link to standalone member pages directly"""
    embedded = _html(fragment_site / "reference/Counter.html")
    assert embedded.find(id="total") is not None
    assert embedded.find(id="iter__") is not None
    standalone = fragment_site / "reference/Separate.html"
    rows = _html(standalone).select(".gd-summary-table a[href]")
    (link,) = [row for row in rows if row.get_text() == "total()"]
    target = urlsplit(str(link["href"]))
    assert not target.fragment
    assert (standalone.parent / target.path).is_file()


def test_qualified_heading_publishes_the_fragment_once() -> None:
    """Use the heading as the target when its title already gives it the published ID"""
    obj = gf.Function("function", parent=gf.Module("package"))
    doc = Doc.from_griffe("package.function", obj)
    qmd = str(FunctionRenderer(doc, 2, page_path="function.qmd"))
    (heading,) = [line for line in qmd.splitlines() if f"{{#{doc.anchor}}}" in line]
    assert heading.startswith("## ")
