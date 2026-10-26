"""Tests for the published termshow JSON Schemas.

The schemas are a contract: these tests check that what the code reads and
writes stays inside them, and that their enums stay in sync with the code.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

jsonschema = pytest.importorskip("jsonschema")

from great_docs._term_player.importer import import_asciicast
from great_docs._term_player.manifest import generate_manifest
from great_docs._term_player.parser import Event, Recording, TermInfo, parse_termshow
from great_docs._term_player.script import (
    Annotation,
    Chapter,
    Highlight,
    HighlightTarget,
    Script,
    Snippet,
    _parse_script_data,
    apply_script,
    load_script,
)
from great_docs._term_player.themes import theme_names

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "great_docs" / "_term_player" / "schemas"
CSS = ROOT / "great_docs" / "assets" / "_extensions" / "termshow" / "termshow.css"
GUIDE = ROOT / "docs" / "user_guide" / "41-terminal-recordings.qmd"
SPECS_DIR = ROOT / "test-packages" / "synthetic" / "specs"
SCHEMA_BASE = (
    "https://raw.githubusercontent.com/posit-dev/great-docs/main/great_docs/_term_player/schemas/"
)
NAMES = ["recording", "script", "manifest"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"termshow-{name}.schema.json").read_text())


def _validator(name: str, pointer: str | None = None):
    """A validator for a schema, or for one of its `$defs` when `pointer` is given."""
    schema = _schema(name)
    if pointer:
        schema = {"$ref": f"#/$defs/{pointer}", "$defs": schema["$defs"]}
    return jsonschema.Draft202012Validator(schema)


def _errors(name: str, instance, pointer: str | None = None) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
        for e in _validator(name, pointer).iter_errors(instance)
    ]


def _recording_errors(text: str) -> list[str]:
    """Validate termshow text line by line: header first, then events."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    errors = [f"header: {e}" for e in _errors("recording", json.loads(lines[0]), "header")]
    for n, line in enumerate(lines[1:], start=2):
        errors += [f"line {n}: {e}" for e in _errors("recording", json.loads(line), "event")]
    return errors


def _tracked_docs(suffix: str) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "docs"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover
        out = ""
    # Outside a git checkout this is empty, and pytest skips the tests
    return [ROOT / p for p in out.splitlines() if p.endswith(suffix)]


def _spec_files() -> dict[str, str]:
    """Termshow files embedded in the synthetic test-package specs."""
    found: dict[str, str] = {}
    for spec_path in sorted(SPECS_DIR.glob("*.py")):
        if "termshow" not in spec_path.read_text(encoding="utf-8"):
            continue
        spec = importlib.util.spec_from_file_location(f"_spec_{spec_path.stem}", spec_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for value in vars(module).values():
            if isinstance(value, dict) and isinstance(value.get("files"), dict):
                for name, content in value["files"].items():
                    if name.endswith((".termshow", ".termshow.yml")):
                        found[f"{spec_path.stem}:{name}"] = content
    return found


def _manifest_dict(recording: Recording, script: Script | None = None) -> dict:
    if script is not None:
        recording = apply_script(recording, script)
    return json.loads(generate_manifest(recording, script).to_json())


def _recording(events: list[Event], cols: int = 20, rows: int = 4) -> Recording:
    return Recording(
        version=1, format="termshow", term=TermInfo(cols=cols, rows=rows), events=events
    )


# ---------------------------------------------------------------------------
# The schemas themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_schema_is_valid(name: str):
    jsonschema.Draft202012Validator.check_schema(_schema(name))


@pytest.mark.parametrize("name", NAMES)
def test_schema_id_matches_published_path(name: str):
    schema = _schema(name)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == f"{SCHEMA_BASE}termshow-{name}.schema.json"


def test_schemas_ship_with_package():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "_term_player/schemas/*.json" in pyproject
    assert "great_docs/_term_player/schemas" in (ROOT / "MANIFEST.in").read_text()


# ---------------------------------------------------------------------------
# Enums stay in sync with the code
# ---------------------------------------------------------------------------


def _css_suffixes(prefix: str) -> set[str]:
    return set(re.findall(rf"\.gd-tp-{prefix}-([a-z-]+)", CSS.read_text()))


def test_theme_enum_matches_builtin_themes():
    defs = _schema("script")["$defs"]
    assert sorted(defs["themeName"]["enum"]) == theme_names()


def test_highlight_styles_match_css():
    styles = _schema("script")["$defs"]["highlight"]["properties"]["style"]["enum"]
    # `badge` and `pulse` are helper classes, not styles
    assert set(styles) == _css_suffixes("hl") - {"badge", "pulse"}


def test_annotation_values_match_css():
    props = _schema("script")["$defs"]["annotation"]["properties"]
    css = _css_suffixes("ann")
    styles = set(props["style"]["enum"])
    widths = {w for w in css if w.startswith("w-")}
    assert styles <= css
    assert {f"w-{w}" for w in props["width"]["enum"]} - {"w-medium"} == widths
    assert set(props["position"]["enum"]) == css - styles - widths


# ---------------------------------------------------------------------------
# Real recordings and scripts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _tracked_docs(".termshow"), ids=lambda p: str(p.relative_to(ROOT)))
def test_docs_recordings_validate(path: Path):
    assert _recording_errors(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "path", _tracked_docs(".termshow.yml"), ids=lambda p: str(p.relative_to(ROOT))
)
def test_docs_scripts_validate(path: Path):
    assert _errors("script", yaml.safe_load(path.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize("path", _tracked_docs(".termshow"), ids=lambda p: str(p.relative_to(ROOT)))
def test_docs_manifests_validate(path: Path):
    script_path = path.with_name(path.name + ".yml")
    script = load_script(script_path) if script_path.exists() else None
    assert _errors("manifest", _manifest_dict(parse_termshow(path), script)) == []


def test_spec_files_found():
    assert _spec_files()


@pytest.mark.parametrize("key", sorted(_spec_files()))
def test_spec_files_validate(key: str):
    content = _spec_files()[key]
    if key.endswith(".yml"):
        assert _errors("script", yaml.safe_load(content)) == []
    else:
        assert _recording_errors(content) == []


def _guide_scripts() -> list[tuple[int, dict]]:
    """YAML examples in the Terminal Recordings guide that are termshow scripts."""
    script_keys = set(_schema("script")["properties"])
    text = GUIDE.read_text(encoding="utf-8")
    blocks = []
    for m in re.finditer(r"^```(?:\{\.)?ya?ml[^\n]*\n(.*?)^```", text, re.M | re.S):
        data = yaml.safe_load(m.group(1))
        # Skip Quarto configuration (`project:`, `format:`) and fragments
        if isinstance(data, dict) and data and set(data) <= script_keys:
            blocks.append((text.count("\n", 0, m.start()) + 1, data))
    return blocks


def test_guide_has_script_examples():
    assert len(_guide_scripts()) >= 10


@pytest.mark.parametrize("line, data", _guide_scripts(), ids=lambda v: f"line{v}")
def test_guide_examples_validate(line: int, data: dict):
    assert _errors("script", data) == []


# ---------------------------------------------------------------------------
# Generated files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("version", [2, 3])
def test_imported_asciicast_validates(tmp_path: Path, version: int):
    cast = tmp_path / "demo.cast"
    if version == 2:
        header = {"version": 2, "width": 40, "height": 10, "env": {"TERM": "xterm"}}
        events = [[0.5, "o", "$ "], [1.0, "i", "ls\r"], [1.2, "o", "a  b\r\n"], [2.0, "m", "x"]]
    else:
        header = {"version": 3, "term": {"cols": 40, "rows": 10}, "title": "Demo"}
        events = [[0.5, "o", "$ "], [0.5, "r", "50x12"], [0.2, "x", "0"]]
    cast.write_text("\n".join(json.dumps(x) for x in [header, *events]) + "\n")

    out = tmp_path / "demo.termshow"
    import_asciicast(cast, out)
    assert _recording_errors(out.read_text(encoding="utf-8")) == []


def test_rendered_manifest_with_every_feature_validates():
    rec = _recording(
        [
            Event(time=0.0, code="o", data="$ \x1b[1;31mred\x1b[0m \x1b[42m ok \x1b[0m"),
            Event(time=0.5, code="m", data="Start"),
            Event(time=1.0, code="r", data="30x6"),
            Event(time=1.5, code="o", data="\r\n</script> ✓ wide"),
            Event(time=2.0, code="o", data="\x1b[?25l"),
            Event(time=3.0, code="o", data="\r\ndone"),
        ]
    )
    script = Script(
        window_chrome="colorful",
        show_cursor=True,
        chapters=[Chapter(time=0.0, label="Intro")],
        annotations=[Annotation(time=0.5, duration=1.0, text="Hi", position="top")],
        highlights=[
            Highlight(
                time=1.0,
                duration=1.0,
                target=HighlightTarget(region={"row": 0, "col": 0, "width": 3, "height": 1}),
                style="badge-after",
                badge_text="1",
                badge_icon="★",
                fade_in=0.1,
                pulse=True,
            ),
            Highlight(time=1.5, duration=1.0, target=HighlightTarget(lines=[1])),
            Highlight(
                time=2.0,
                duration=1.0,
                target=HighlightTarget(match=r"(done)", group=1, track_scroll=True),
            ),
        ],
        snippets=[Snippet(time=0.0, duration=2.0, text="echo hi", label="Run")],
    )
    data = _manifest_dict(rec, script)

    assert _errors("manifest", data) == []
    # The fixture exercises the optional parts of a frame
    assert any("size" in fr for fr in data["frames"])
    assert any("cursor" not in fr for fr in data["frames"])
    assert any(len(span) == 4 for line in data["lines"] for span in line[1])


def test_rendered_theme_pair_manifest_validates():
    rec = _recording([Event(time=0.0, code="o", data="$ \x1b[1;31mred\x1b[0m \x1b[42m ok \x1b[0m")])
    spec = {"light": "catppuccin-latte", "dark": {"base": "catppuccin-mocha", "bg": "#000000"}}
    data = _manifest_dict(rec, _parse_script_data({"settings": {"theme": spec}}))
    assert _errors("manifest", data) == []
    assert "cursor" in data["screen"] and "cursor" in data["dark"]
    assert _errors("manifest", {**data, "dark": {"fg": "#ffffff", "lines": []}})


def test_rendered_manifest_serialization_contract():
    rec = _recording(
        [Event(time=0.0, code="o", data="$ </b>"), Event(time=1.0, code="o", data="x")]
    )
    text = generate_manifest(rec).to_json()

    # Read by the Lua filter with patterns, not a JSON parser
    assert re.match(r'^\s*{\s*"version"\s*:\s*2', text)
    keyframes = re.findall(r'"time"\s*:\s*([\d.]+)\s*,\s*"file"\s*:\s*"([^"]+)"', text)
    assert len(keyframes) == len(json.loads(text)["keyframes"])
    assert "</" not in text


# ---------------------------------------------------------------------------
# What the schemas reject
# ---------------------------------------------------------------------------


V1_MANIFEST = {
    "version": 1,
    "title": "Old",
    "duration": 2.0,
    "term": {"cols": 80, "rows": 24},
    "theme": "default",
    "chapters": [],
    "keyframes": [{"time": 0.0, "file": "frame-000.svg"}, {"time": 1.0, "file": "frame-001.svg"}],
    "annotations": [],
}


def test_v1_manifest_validates():
    assert _errors("manifest", V1_MANIFEST) == []


def test_v2_manifest_requires_frames():
    data = dict(V1_MANIFEST, version=2)
    assert _errors("manifest", data)


def test_manifest_allows_unknown_members():
    rec = _recording([Event(time=0.0, code="o", data="$ ")])
    data = _manifest_dict(rec)
    data["future_member"] = {"anything": True}
    assert _errors("manifest", data) == []


def test_recording_allows_unknown_event_codes():
    assert _errors("recording", [0.1, "z", "future"], "event") == []


@pytest.mark.parametrize(
    "event",
    [[-1, "o", "x"], [0.1, "o"], [0.1, "r", "wide"], [0.1, "x", "zero"], ["0.1", "o", "x"]],
)
def test_recording_rejects_bad_events(event: list):
    assert _errors("recording", event, "event")


@pytest.mark.parametrize(
    "script",
    [
        {"annotations": [{"at": 1, "duraton": 2, "text": "typo"}]},
        {"settings": {"theme": "not-a-theme"}},
        {"settings": {"window_chrome": "fancy"}},
        {"highlights": [{"at": 1, "target": {"lines": [0]}, "style": "badge"}]},
        {"highlights": [{"at": 1}]},
        {"highlights": [{"at": 1, "target": {"region": {"row": 0, "col": 0}}}]},
        {"snippets": [{"at": 1, "label": "nothing to copy"}]},
        {"cuts": [{"from": 1}]},
        {"settings": {"theme": {"palette": ["#000000"] * 5}}},
        {"settings": {"theme": {"cursor": "red"}}},
        {"settings": {"theme": {"light": "nord"}}},
        {"settings": {"theme": {"light": "nord", "dark": "dracula", "bg": "#000000"}}},
        {"settings": {"theme": {"light": "auto", "dark": "dracula"}}},
        {"chapter": [{"at": 0, "label": "typo in key"}]},
    ],
)
def test_script_rejects_mistakes(script: dict):
    assert _errors("script", script)


@pytest.mark.parametrize(
    "theme",
    [
        "auto",
        {"base": "nord", "cursor": "#88c0d0"},
        {"light": "github-light", "dark": "github-dark"},
        {"light": {"base": "github-light", "cursor": "#0969da"}, "dark": {"bg": "#000000"}},
    ],
)
def test_script_accepts_theme_forms(theme):
    assert _errors("script", {"settings": {"theme": theme}}) == []
    # Everything the schema accepts, the code accepts too
    _parse_script_data({"settings": {"theme": theme}})


def test_script_accepts_legacy_highlight_region():
    script = {"highlights": [{"at": 1, "region": {"row": 0, "col": 0, "width": 2, "height": 1}}]}
    assert _errors("script", script) == []
