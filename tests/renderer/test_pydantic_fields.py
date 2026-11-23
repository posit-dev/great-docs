from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from tests.support import reference_from_options

_MODULE = "gd_pydantic_fields"
_SOURCE = r'''
from pydantic import BaseModel as Model, Field as ModelField
from pydantic.fields import Field
from typing import Annotated, ClassVar
from typing_extensions import Annotated as AnnotatedField


def computed_description() -> str:
    return "Calculated description."


class BaseColour(Model):
    pass


class Colour(BaseColour):
    """An RGB colour"""

    red: Annotated[int, Field(description="Red metadata.")] = ModelField(description="Red amount.")
    green: AnnotatedField[
        int, Field(description="Earlier metadata."), Field(description="Green")
    ]
    blue: Annotated[int, "Blue"]
    alpha: int = Field(description="Alpha metadata.")
    """Alpha amount"""
    hue: int = Field(description=computed_description())
    saturation: int = 0
    internal: int = Field(description="Internal field.\n\n%nodoc")
    label: ClassVar[str] = Field(description="Class label.")
    quoted_label: "ClassVar[str]" = Field(description="Quoted class label.")
    unit: Annotated[ClassVar[str], "Class unit."] = "percent"

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        self.cache: Annotated[int, "Instance cache."] = 0


class BaseModel:
    pass


class PlainColour(BaseModel):
    """A colour with no validation"""

    red: int = Field(description="Plain red amount.")
'''


@pytest.fixture
def models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    (tmp_path / f"{_MODULE}.py").write_text(_SOURCE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yield
    sys.modules.pop(_MODULE, None)


@pytest.mark.usefixtures("models")
@pytest.mark.parametrize("dynamic", [False, True], ids=["static", "dynamic"])
def test_model_field_descriptions_in_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dynamic: bool
) -> None:
    if dynamic:
        pytest.importorskip("pydantic", minversion="2")
    else:
        monkeypatch.setitem(sys.modules, "pydantic", None)
        monkeypatch.setitem(sys.modules, "pydantic.fields", None)

    fields = {
        "red": "Red amount.",
        "green": "Green",
        "blue": "Blue",
        "alpha": "Alpha amount",
    }
    options = {
        "package": _MODULE,
        "dynamic": dynamic,
        "sections": [{"title": "Models", "contents": ["Colour", "PlainColour"]}],
    }
    with closing(reference_from_options(options)) as reference:
        reference.build()
        assert set(reference.documented_symbols) == {"Colour", "PlainColour"} | {
            f"Colour.{name}" for name in fields
        }

    page = (tmp_path / "reference" / "Colour.qmd").read_text(encoding="utf-8")
    lines = page.splitlines()
    for name, description in fields.items():
        assert any(
            line.startswith(f"| [{name}](#{_MODULE}.Colour.{name})")
            and line.endswith(f"| {description} |")
            for line in lines
        )
        assert f"\n{description}\n" in page

    assert (_MODULE in sys.modules) == dynamic


@pytest.mark.usefixtures("models")
def test_model_field_descriptions_follow_explicit_selection(tmp_path: Path) -> None:
    options = {
        "package": _MODULE,
        "sections": [
            {
                "title": "Models",
                "contents": [
                    {"name": "Colour", "members": ["red", "saturation", "internal"]},
                    "Colour.blue",
                ],
            }
        ],
    }
    with closing(reference_from_options(options)) as reference:
        reference.build()
        assert set(reference.documented_symbols) == {
            "Colour",
            "Colour.blue",
            "Colour.red",
            "Colour.saturation",
        }

    reference_dir = tmp_path / "reference"
    field_page = (reference_dir / "Colour.blue.qmd").read_text(encoding="utf-8")
    assert "\nBlue\n" in field_page
