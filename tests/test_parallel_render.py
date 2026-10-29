"""
Rendering a website with several Quarto processes

`_parallel_render.render()` splits a project's pages into groups that each
render in a copy of the project, then merges the copies' output. The merged
site must match the output of a plain `quarto render`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from great_docs import _parallel_render as pr

# ── Choosing the number of processes ─────────────────────────────────────────


def test_resolve_jobs_defaults_to_one_process(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(pr.JOBS_ENV, raising=False)

    assert pr.resolve_jobs(None) == 1


def test_resolve_jobs_reads_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(pr.JOBS_ENV, "3")

    assert pr.resolve_jobs(None) == 3
    assert pr.resolve_jobs(5) == 5


@pytest.mark.parametrize("jobs", ["auto", "AUTO", "0", 0, -1])
def test_resolve_jobs_auto_is_capped(jobs):
    n = pr.resolve_jobs(jobs)

    assert 1 <= n <= pr.MAX_AUTO_JOBS


def test_resolve_jobs_rejects_other_text():
    with pytest.raises(ValueError, match="number or 'auto'"):
        pr.resolve_jobs("lots")


# ── Planning ─────────────────────────────────────────────────────────────────


def _covers(targets: list[pr.Target], inputs: list[str]) -> None:
    """Check each target selects exactly its inputs, and every input once"""
    rendered = [item for t in targets for item in t.inputs]
    assert sorted(rendered) == sorted(inputs)
    for t in targets:
        if t.single:
            continue
        assert sorted(i for i in inputs if i.startswith(t.path)) == sorted(t.inputs)


def _site(n_ref: int = 60, n_guide: int = 10) -> list[str]:
    return (
        ["index.qmd"]
        + [f"reference/func_{i:03d}.qmd" for i in range(n_ref)]
        + ["reference/index.qmd"]
        + [f"user-guide/{i:02d}-page.qmd" for i in range(n_guide)]
    )


def test_plan_targets_covers_every_input_once():
    inputs = _site()
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4, overhead=2.0)

    assert targets is not None
    assert len(targets) >= 4
    _covers(targets, inputs)


def test_plan_targets_balances_the_work():
    inputs = _site(n_ref=200)
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4, overhead=2.0)

    assert targets is not None
    finish = pr._makespan([t.cost for t in targets], 4, 2.0)
    # Groups split ten ways at a time, so the balance can't be perfect, but
    # four workers should still take well under half the time of two
    assert finish < 0.35 * sum(costs.values())


def test_plan_targets_keeps_expensive_targets_first():
    inputs = _site()
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4)

    assert targets is not None
    assert [t.cost for t in targets] == sorted((t.cost for t in targets), reverse=True)


def test_plan_targets_doesnt_split_cheap_sites():
    inputs = _site(n_ref=5, n_guide=2)
    costs = dict.fromkeys(inputs, 0.01)

    targets = pr.plan_targets(inputs, costs, 4, overhead=2.0)

    # The inputs are split where they must be, at the top, and no further
    assert targets is not None
    _covers(targets, inputs)
    assert len(targets) == 3


def test_plan_targets_keeps_listing_directories_together():
    inputs = _site() + [f"blog/post-{i:02d}.qmd" for i in range(30)] + ["blog/index.qmd"]
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 8, atomic=["blog"])

    assert targets is not None
    _covers(targets, inputs)
    blog = [t for t in targets if any(i.startswith("blog/") for i in t.inputs)]
    assert len(blog) == 1
    assert sorted(blog[0].inputs) == sorted(i for i in inputs if i.startswith("blog/"))


def test_plan_targets_gives_up_on_a_listing_at_the_root():
    inputs = _site()

    assert pr.plan_targets(inputs, dict.fromkeys(inputs, 1.0), 4, atomic=[""]) is None


def test_plan_targets_renders_a_listing_with_its_neighbours_when_needed():
    # `blog` would also select `blog-extra.qmd`, so the listing goes with it
    inputs = _site() + ["blog/index.qmd", "blog/a.qmd", "blog-extra.qmd"]
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4, atomic=["blog"])

    assert targets is not None
    _covers(targets, inputs)
    blog = [t for t in targets if "blog/a.qmd" in t.inputs]
    assert sorted(blog[0].inputs) == ["blog-extra.qmd", "blog/a.qmd", "blog/index.qmd"]


def test_plan_targets_gives_up_when_a_listing_directory_cant_be_named():
    inputs = _site() + ["blog/index.qmd", "blog/a.qmd", "blog-extra.qmd"]
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(
        inputs, costs, 4, atomic=["blog"], can_name=lambda p: not "blog".startswith(p)
    )

    assert targets is None


def test_plan_targets_only_uses_paths_that_can_be_named():
    inputs = _site()
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4, can_name=lambda p: "func_" not in p)

    assert targets is not None
    _covers(targets, inputs)
    assert all("func_" not in t.path or t.single for t in targets)


def test_plan_targets_selects_a_prefix_the_way_quarto_does():
    # Quarto drops a trailing "/" from `quarto render reference/`, so it
    # selects `reference-extra.qmd` too; a plan must never rely on it
    inputs = [f"reference/f{i:02d}.qmd" for i in range(20)] + ["reference-extra.qmd"]
    costs = dict.fromkeys(inputs, 1.0)

    targets = pr.plan_targets(inputs, costs, 4)

    assert targets is not None
    _covers(targets, inputs)
    assert all(t.path != "reference" for t in targets)


def test_plan_targets_with_no_inputs():
    assert pr.plan_targets([], {}, 4) is None


def test_makespan_uses_the_largest_group_first():
    assert pr._makespan([3, 3, 2, 2, 2], 2, 0.0) == 7
    assert pr._makespan([2, 3, 1], 2, 0.5) == 4.0
    assert pr._makespan([1, 1], 4, 1.0) == 2


# ── Estimating costs ─────────────────────────────────────────────────────────


def test_estimate_costs_uses_last_timings():
    costs = pr.estimate_costs(["a.qmd", "b.qmd"], {"a.qmd": 2.5, "b.qmd": 0.0}, {})

    assert costs == {"a.qmd": 2.5, "b.qmd": 0.01}


def test_estimate_costs_guesses_new_pages_from_known_ones():
    timings = {"a.qmd": 1.0, "b.qmd": 3.0, "c.qmd": 2.0}

    costs = pr.estimate_costs(["a.qmd", "b.qmd", "c.qmd", "new.qmd"], timings, {})

    assert costs["new.qmd"] == 2.0


def test_estimate_costs_charges_more_for_executable_pages():
    costs = pr.estimate_costs(["a.qmd", "run.qmd"], {}, {"run.qmd": 5})

    assert costs["a.qmd"] == pr.DEFAULT_PAGE_COST
    assert costs["run.qmd"] == pytest.approx(pr.DEFAULT_PAGE_COST + pr.EXEC_PAGE_COST + 1.0)


def test_read_timings_uses_the_first_readable_file(tmp_path: Path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"pages": [{"page": "a.qmd", "seconds": 1.5}, {"page": "b"}]}))
    bad = tmp_path / "bad.json"
    bad.write_text("not json")

    assert pr.read_timings(tmp_path / "missing.json", bad, good) == {"a.qmd": 1.5}
    assert pr.read_timings(tmp_path / "missing.json") == {}


# ── Merging ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("rel", "owner"),
    [
        ("reference/f.html", 1),
        ("reference/f.html.md", 1),
        ("reference/f.ipynb", 1),
        ("reference/f.g.html", 2),
        ("reference/other.html", None),
        ("index.html", 0),
        ("styles.css", None),
    ],
)
def test_owner_of_finds_the_page_an_output_belongs_to(rel: str, owner: int | None):
    owners = {"reference/f": 1, "reference/f.g": 2, "index": 0}

    assert pr._owner_of(rel, owners) == owner


def _write(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        # Listings and sitemaps show when each source changed
        os.utime(path, (1_700_000_000, 1_700_000_000))
    return root


def test_merge_sites_takes_pages_from_their_owners(tmp_path: Path):
    a = _write(
        tmp_path / "a",
        {
            "index.html": "a index",
            "ref/f.html": "a f",
            "ref/f_files/fig.png": "a fig",
            "ref/g.html": "stale g",
            "site_libs/lib.js": "a lib",
            "search.json": "[]",
        },
    )
    b = _write(
        tmp_path / "b",
        {
            "ref/g.html": "b g",
            "ref/f_files/fig.png": "stale fig",
            "ref/g_files/fig.png": "b fig",
            "site_libs/lib.js": "b lib",
            "site_libs/extra.js": "b extra",
        },
    )
    dest = tmp_path / "site"

    pr.merge_sites([a, b], dest, {"index": 0, "ref/f": 0, "ref/g": 1})

    def read(rel: str) -> str:
        return (dest / rel).read_text(encoding="utf-8")

    assert read("index.html") == "a index"
    assert read("ref/f.html") == "a f"
    assert read("ref/f_files/fig.png") == "a fig"
    assert read("ref/g.html") == "b g"
    assert read("ref/g_files/fig.png") == "b fig"
    assert read("site_libs/lib.js") == "a lib"
    assert read("site_libs/extra.js") == "b extra"
    # The indexes are merged separately
    assert not (dest / "search.json").exists()


def test_merge_search_orders_entries_by_page_and_prefers_owners():
    a = [
        {"href": "b.html", "title": "stale b"},
        {"href": "a.html", "title": "a"},
        {"href": "a.html#sec", "title": "a sec"},
    ]
    b = [{"href": "b.html", "title": "b"}, {"href": "c.html", "title": "c"}]

    merged = pr.merge_search([a, b], {"a.html": 0, "b.html": 1, "c.html": 2}, {"b.html": 1})

    assert [e["title"] for e in merged] == ["a", "a sec", "b", "c"]


def test_merge_sitemaps_keeps_each_location_once():
    head = '<?xml version="1.0"?>\n<urlset>\n'

    def sitemap(*locs: str) -> str:
        urls = "".join(f"  <url><loc>{loc}</loc></url>\n" for loc in locs)
        return head + urls + "</urlset>\n"

    merged = pr.merge_sitemaps([sitemap("x/a", "x/b"), "", sitemap("x/b", "x/c")])

    assert merged is not None
    assert merged.startswith(head)
    assert merged.count("<url>") == 3
    assert merged.index("x/a") < merged.index("x/b") < merged.index("x/c")
    assert merged.rstrip().endswith("</urlset>")
    assert pr.merge_sitemaps(["", ""]) is None


def test_merge_listings_keeps_each_listing_once(tmp_path: Path):
    a = tmp_path / "a.json"
    a.write_text(json.dumps([{"listing": "/blog/index.html", "items": ["/blog/p.html"]}]))
    b = tmp_path / "b.json"
    b.write_text(json.dumps([{"listing": "/blog/index.html", "items": []}, {"listing": "/x"}]))

    merged = pr._merge_listings([a, tmp_path / "missing.json", b])

    assert merged == [
        {"listing": "/blog/index.html", "items": ["/blog/p.html"]},
        {"listing": "/x"},
    ]
    assert pr._merge_listings([tmp_path / "missing.json"]) is None


def test_name_checker(tmp_path: Path):
    (tmp_path / "reference").mkdir()
    (tmp_path / "Guide.qmd").write_text("")
    (tmp_path / "link").symlink_to(tmp_path / "reference")
    can_name = pr._name_checker(tmp_path)

    assert can_name("reference")
    assert can_name("reference/func_0")
    assert can_name("new")
    assert not can_name("")
    assert not can_name("ref*")
    assert not can_name("_private")
    assert not can_name(".hidden")
    assert not can_name("link")
    assert not can_name("Guide.qmd")
    # This would be `reference` where case is ignored
    assert not can_name("Reference")


def test_dir_freeze_checker_reads_metadata_files_above_a_page(tmp_path: Path):
    _write(
        tmp_path,
        {
            "guide/_metadata.yml": "execute:\n  freeze: true\n",
            "guide/deep/page.qmd": "",
            "blog/_metadata.yaml": "freeze: false\n",
            "other/_metadata.yml": "title-prefix: Other\n",
            "broken/_metadata.yml": "execute: [\n",
        },
    )
    freezes = pr._dir_freeze_checker(tmp_path)

    assert freezes(PurePosixPath("guide"))
    assert freezes(PurePosixPath("guide/deep"))
    assert freezes(PurePosixPath("blog"))
    assert freezes(PurePosixPath("broken"))
    assert not freezes(PurePosixPath("other"))
    assert not freezes(PurePosixPath("."))


def test_slim_config_moves_sidebars_out_and_drops_great_docs_keys(tmp_path: Path):
    sidebar = [{"id": "reference", "contents": ["reference/a.qmd"]}]
    config = {
        "project": {"type": "website"},
        "website": {"title": "T", "sidebar": sidebar},
        "api-reference": {"sections": [{"contents": ["a"]}]},
    }

    pr._slim_config(config, tmp_path)

    assert config == {
        "project": {"type": "website"},
        "website": {"title": "T"},
        "metadata-files": [pr._SIDEBAR_META],
    }
    moved = pr.parse_yaml((tmp_path / pr._SIDEBAR_META).read_text(encoding="utf-8"))
    assert moved == {"website": {"sidebar": sidebar}}


def test_slim_config_leaves_sidebars_beside_other_metadata_files(tmp_path: Path):
    config = {"website": {"sidebar": [{"id": "x"}]}, "metadata-files": ["_extra.yml"]}

    pr._slim_config(config, tmp_path)

    assert config == {"website": {"sidebar": [{"id": "x"}]}, "metadata-files": ["_extra.yml"]}
    assert not (tmp_path / pr._SIDEBAR_META).exists()


def test_target_overhead_grows_with_the_project():
    assert pr.target_overhead(100) == pr.TARGET_OVERHEAD
    assert pr.target_overhead(2000) > pr.target_overhead(1000) > pr.TARGET_OVERHEAD


# ── Falling back to a plain render ───────────────────────────────────────────


def test_render_falls_back_with_one_process(tmp_path: Path):
    result = pr.render(tmp_path, {}, 1)

    assert result.fallback == "one render process requested"


def test_render_falls_back_for_other_project_types(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text("project:\n  type: book\n")

    result = pr.render(tmp_path, {}, 4)

    assert result.fallback is not None
    assert "book" in result.fallback


def test_render_falls_back_for_output_outside_the_project(tmp_path: Path):
    (tmp_path / "_quarto.yml").write_text("project:\n  type: website\n  output-dir: ../out\n")

    result = pr.render(tmp_path, {}, 4)

    assert result.fallback is not None
    assert "outside" in result.fallback


def test_render_removes_leftover_worker_directories(tmp_path: Path):
    build = tmp_path / "default"
    build.mkdir()
    leftover = pr.worker_dir(build, 0)
    leftover.mkdir()

    pr.render(build, {}, 1)

    assert not leftover.exists()


# ── Rendering with Quarto ────────────────────────────────────────────────────

_needs_quarto = pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto not installed")

_QUARTO_YML = """\
project:
  type: website

website:
  title: "Parallel"
  site-url: "https://example.com/"
  sidebar:
    - id: reference
      contents:
        - reference/index.qmd
        - section: Functions
          contents: "reference/func_*.qmd"
    - id: guide
      contents: "guide/*.qmd"
  navbar:
    left:
      - href: guide/00-intro.qmd
        text: Guide
      - href: reference/index.qmd
        text: Reference
      - href: blog/index.qmd
        text: Blog
"""


def _write_project(root: Path) -> Path:
    files = {
        "_quarto.yml": _QUARTO_YML,
        "index.qmd": "---\ntitle: Home\n---\n\nSee [the guide](guide/00-intro.qmd).\n",
        "reference/index.qmd": "---\ntitle: Reference\n---\n\nAll the functions.\n",
        "blog/index.qmd": '---\ntitle: Blog\nlisting:\n  contents: "*.qmd"\n---\n',
        "styles.css": "body { color: black; }\n",
    }
    for i in range(12):
        files[f"reference/func_{i:02d}.qmd"] = (
            f"---\ntitle: func_{i:02d}\n---\n\n## Usage\n\nCall `func_{i:02d}()`; "
            f"see [func_{(i + 1) % 12:02d}](func_{(i + 1) % 12:02d}.qmd).\n"
        )
    for i in range(5):
        files[f"guide/{i:02d}-intro.qmd" if i == 0 else f"guide/{i:02d}-page.qmd"] = (
            f"---\ntitle: Guide {i}\n---\n\n## Section\n\nSome guide text.\n"
        )
    for i in range(4):
        files[f"blog/post-{i}.qmd"] = (
            f"---\ntitle: Post {i}\ndate: 2026-01-0{i + 1}\n---\n\nPost body {i}.\n"
        )
    return _write(root, files)


def _search(site: Path) -> list[str]:
    entries = json.loads((site / "search.json").read_text(encoding="utf-8"))
    return sorted(json.dumps(e, sort_keys=True) for e in entries)


def _urls(sitemap: Path) -> list[str]:
    return sorted(pr._URL_RE.findall(sitemap.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def sites(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, pr.RenderResult]:
    plain = _write_project(tmp_path_factory.mktemp("plain") / "proj")
    split = _write_project(tmp_path_factory.mktemp("split") / "proj")
    subprocess.run(["quarto", "render"], cwd=plain, check=True, capture_output=True)
    pages: list[str] = []
    result = pr.render(split, dict(os.environ), 3, on_page=pages.append, min_pages=1)
    assert result.fallback is None, result.fallback
    assert result.returncode == 0, result.stderr
    assert result.workers > 1
    return plain / "_site", split / "_site", result


@_needs_quarto
def test_rendered_files_match_plain_render(sites):
    plain, split, _ = sites

    assert sorted(str(p.relative_to(split)) for p in split.rglob("*")) == sorted(
        str(p.relative_to(plain)) for p in plain.rglob("*")
    )


@_needs_quarto
def test_rendered_pages_match_plain_render(sites):
    plain, split, _ = sites

    for page in plain.rglob("*.html"):
        rel = page.relative_to(plain)
        assert (split / rel).read_bytes() == page.read_bytes(), rel


@_needs_quarto
def test_rendered_indexes_match_plain_render(sites):
    plain, split, _ = sites

    assert _search(split) == _search(plain)
    # Each process adds its pages to the sitemap, so they come in another order
    assert _urls(split / "sitemap.xml") == _urls(plain / "sitemap.xml")
    assert json.loads((split / "listings.json").read_text()) == json.loads(
        (plain / "listings.json").read_text()
    )


@_needs_quarto
def test_render_reports_every_page_and_cleans_up(sites):
    _, split, result = sites
    project = split.parent

    assert result.pages == len(list(project.rglob("*.qmd")))
    assert sorted(t["page"] for t in result.page_timings) == sorted(
        str(p.relative_to(project)) for p in project.rglob("*.qmd")
    )
    assert pr.worker_dirs(project) == []
    assert not (project / "_freeze").exists()
