"""
Global member placement after direct members are selected and resolved
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.content import Doc, MemberPage


def _document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    *,
    name: str = "policy_example:Widget",
    entry: dict[str, object] | None = None,
    global_placement: bool | None = None,
    limit: int = 5,
) -> Doc:
    """
    Resolve an authored entry against a temporary source package
    """
    package = tmp_path / "policy_example"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text(dedent(source), encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    ref = APIReference(
        {
            "package": None,
            "dynamic": False,
            "members_on_same_page": global_placement,
            "max_members_on_same_page": limit,
            "sections": [{"title": "API", "contents": [{"name": name, **(entry or {})}]}],
        }
    )
    return ref.resolved[0].contents[0].contents[0]


_SOURCE = '''
"""The package"""

class Widget:
    """A widget"""

    size = 1
    """The size"""

    def run(self):
        """Run the widget"""

    def stop(self):
        """Stop the widget"""

    def _hidden(self):
        """An internal operation"""

    def undocumented(self):
        pass

    def omitted(self):
        """%nodoc"""
'''


@pytest.mark.parametrize("name", ["policy_example:Widget", "policy_example"])
@pytest.mark.parametrize("limit,expected_same_page", [(0, False), (1, False), (2, True), (3, True)])
def test_limit_counts_selected_members_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    limit: int,
    expected_same_page: bool,
) -> None:
    """
    Keep selected members together up to and including the limit

    Exclude the documented parent from its own member count.
    """
    source = (
        _SOURCE
        if ":" in name
        else '''
        """The package"""
        def run():
            """Run"""
        def stop():
            """Stop"""
        def extra():
            """An unselected function"""
    '''
    )
    doc = _document(
        tmp_path, monkeypatch, source, name=name, entry={"members": ["run", "stop"]}, limit=limit
    )
    assert len(doc.members) == 2
    assert all(
        isinstance(member, Doc if expected_same_page else MemberPage) for member in doc.members
    )


@pytest.mark.parametrize(
    "entry,global_placement,limit,expected_same_page",
    [
        ({}, True, 0, True),
        ({}, False, 100, False),
        ({"members_on_same_page": True}, False, 0, True),
        ({"members_on_same_page": False}, True, 100, False),
    ],
)
def test_explicit_placement_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry: dict[str, object],
    global_placement: bool,
    limit: int,
    expected_same_page: bool,
) -> None:
    """
    Prefer entry placement to the global choice and the global choice to the limit
    """
    doc = _document(
        tmp_path, monkeypatch, _SOURCE, entry=entry, global_placement=global_placement, limit=limit
    )
    assert len(doc.members) == 3
    assert all(
        isinstance(member, Doc if expected_same_page else MemberPage) for member in doc.members
    )


@pytest.mark.parametrize(
    "entry,count",
    [
        ({}, 3),
        ({"include_private": True}, 4),
        ({"include_empty": True}, 4),
        ({"include_attributes": False}, 2),
        ({"include_functions": False}, 1),
        ({"exclude": ["stop"]}, 2),
        ({"members": ["_hidden", "undocumented", "size"], "include_functions": False}, 3),
        ({"members": []}, 0),
    ],
)
def test_filters_and_explicit_selection_determine_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: dict[str, object], count: int
) -> None:
    """
    Count members after filtering and `%nodoc` exclusions
    """
    doc = _document(tmp_path, monkeypatch, _SOURCE, entry=entry, limit=count)
    assert len(doc.members) == count
    assert all(isinstance(member, Doc) for member in doc.members)
    if count:
        doc = _document(tmp_path, monkeypatch, _SOURCE, entry=entry, limit=count - 1)
        assert len(doc.members) == count
        assert all(isinstance(member, MemberPage) for member in doc.members)


_NESTED_SOURCE = '''
"""The package"""
class Widget:
    """The parent"""
    class Nested:
        """The nested class"""
        def one(self):
            """First member"""
        def two(self):
            """Second member"""
        def three(self):
            """Third member"""
'''


@pytest.mark.parametrize("global_placement", [None, False])
def test_nested_members_use_their_immediate_parent_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, global_placement: bool | None
) -> None:
    """
    Count a nested class once and apply the global choice only to top-level entries
    """
    doc = _document(
        tmp_path, monkeypatch, _NESTED_SOURCE, global_placement=global_placement, limit=1
    )
    assert len(doc.members) == 1
    nested = doc.members[0]
    if global_placement is False:
        assert isinstance(nested, MemberPage)
        nested = nested.contents[0]
    else:
        assert isinstance(nested, Doc)
    assert len(nested.members) == 3
    assert all(isinstance(member, Doc) for member in nested.members)


def test_explicit_member_options_override_nested_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Honour explicit separate pages for a nested class's members
    """
    from great_docs._apiref.spec import SpecOptions

    doc = _document(
        tmp_path,
        monkeypatch,
        _NESTED_SOURCE,
        entry={"member_options": SpecOptions(members_on_same_page=False)},
        global_placement=True,
        limit=100,
    )
    [nested] = doc.members
    assert isinstance(nested, Doc)
    assert all(isinstance(member, MemberPage) for member in nested.members)


@pytest.mark.parametrize("include_inherited,expected_count", [(False, 1), (True, 2)])
def test_inherited_selection_controls_the_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_inherited: bool,
    expected_count: int,
) -> None:
    """
    Count inherited members only when the entry includes them
    """
    source = '''
        class Base:
            """The base"""
            def inherited(self):
                """An inherited operation"""
        class Widget(Base):
            """The widget"""
            def direct(self):
                """A direct operation"""
    '''
    doc = _document(
        tmp_path, monkeypatch, source, entry={"include_inherited": include_inherited}, limit=1
    )
    assert len(doc.members) == expected_count
    assert all(
        isinstance(member, Doc if expected_count == 1 else MemberPage) for member in doc.members
    )


@pytest.mark.parametrize("include_imports,expected_count", [(False, 1), (True, 2)])
def test_imported_selection_controls_the_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_imports: bool, expected_count: int
) -> None:
    """
    Count imported module members only when the entry includes them
    """
    package = tmp_path / "policy_example"
    package.mkdir()
    (package / "extra.py").write_text('def imported():\n    """An imported operation"""\n')
    source = '''
        """The package"""
        from .extra import imported
        __all__ = ["direct", "imported"]
        def direct():
            """A direct operation"""
    '''
    doc = _document(
        tmp_path,
        monkeypatch,
        source,
        name="policy_example",
        entry={"include_imports": include_imports},
        limit=1,
    )
    assert len(doc.members) == expected_count
    assert all(
        isinstance(member, Doc if expected_count == 1 else MemberPage) for member in doc.members
    )


@pytest.mark.parametrize("limit,expected_type", [(2, MemberPage), (3, Doc)])
def test_module_counts_attributes_functions_and_classes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: int, expected_type: type
) -> None:
    """
    Count documented module attributes, functions and classes equally
    """
    source = '''
        """The package"""
        value = 1
        """A setting"""
        def operation():
            """An operation"""
        class Child:
            """A child class"""
            def first(self):
                """A child operation"""
            def second(self):
                """Another child operation"""
    '''
    doc = _document(tmp_path, monkeypatch, source, name="policy_example", limit=limit)
    assert len(doc.members) == 3
    assert all(isinstance(member, expected_type) for member in doc.members)


def test_resolution_hooks_skip_members_before_counting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Exclude members omitted by hooks before applying the page limit
    """
    from great_docs._apiref import resolve

    original = resolve.emit_object_resolved
    monkeypatch.setattr(
        resolve, "emit_object_resolved", lambda obj: None if obj.name == "stop" else original(obj)
    )
    doc = _document(tmp_path, monkeypatch, _SOURCE, limit=2)
    assert [member.name for member in doc.members] == ["run", "size"]
    assert all(isinstance(member, Doc) for member in doc.members)


@pytest.mark.parametrize("placement", [None, True, False])
def test_recreated_entries_preserve_automatic_and_explicit_placement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, placement: bool | None
) -> None:
    """
    Preserve automatic placement and member selection when reusing printed configuration
    """
    from great_docs._apiref.resolve import _to_simple_dict
    from great_docs._apiref.spec import SpecObject

    authored: dict[str, object] = {
        "name": "policy_example:Widget",
        "members": ["run", "stop"],
    }
    if placement is not None:
        authored["members_on_same_page"] = placement
    encoded = _to_simple_dict(SpecObject(**authored))
    assert encoded == authored
    doc = _document(tmp_path, monkeypatch, _SOURCE, entry=encoded, limit=1)
    assert len(doc.members) == 2
    assert all(
        isinstance(member, Doc if placement is True else MemberPage) for member in doc.members
    )


@pytest.mark.parametrize("global_placement", [None, False])
def test_module_member_pages_render_without_splitting_descendants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, global_placement: bool | None
) -> None:
    """
    Write direct module members as pages while keeping nested members on their own parent page
    """
    package = tmp_path / "policy_example"
    package.mkdir()
    (package / "__init__.py").write_text(
        dedent('''
            """The package"""
            setting = 1
            """A setting"""
            def operate():
                """Perform an operation"""
            class Child:
                """The child class"""
                def nested(self):
                    """A nested operation"""
        '''),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    ref = APIReference(
        {
            "package": None,
            "dynamic": False,
            "members_on_same_page": global_placement,
            "max_members_on_same_page": 0,
            "sections": [{"title": "API", "contents": ["policy_example"]}],
        }
    )
    ref.build()
    output = tmp_path / "reference"
    assert {path.name for path in output.glob("*.qmd")} == {
        "index.qmd",
        "policy_example.qmd",
        "policy_example.setting.qmd",
        "policy_example.operate.qmd",
        "policy_example.Child.qmd",
    }
    parent = (output / "policy_example.qmd").read_text(encoding="utf-8")
    assert "policy_example.Child.qmd)" in parent
    assert "policy_example.setting.qmd)" in parent
    assert "policy_example.operate.qmd)" in parent
    assert "A nested operation" in (output / "policy_example.Child.qmd").read_text(encoding="utf-8")


@pytest.mark.parametrize("replace", [False, True])
def test_yaml_member_options_control_nested_placement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replace: bool
) -> None:
    """
    Honour nested member placement in an `api-reference` YAML entry
    """
    from yaml12 import read_yaml

    from great_docs._apiref.resolve import _to_simple_dict
    from great_docs._apiref.spec import SpecObject

    config_path = tmp_path / "reference.yml"
    config_path.write_text(
        dedent("""
            name: policy_example:Widget
            member_options:
              members_on_same_page: false
              member_options:
                members_on_same_page: true
        """),
        encoding="utf-8",
    )
    entry = read_yaml(config_path)
    if replace:
        original = SpecObject(name=entry.pop("name"))
        entry = _to_simple_dict(original.replace(**entry))
    doc = _document(
        tmp_path, monkeypatch, _NESTED_SOURCE, entry=entry, global_placement=True, limit=100
    )
    [nested] = doc.members
    assert isinstance(nested, Doc)
    assert len(nested.members) == 3
    assert all(isinstance(member, MemberPage) for member in nested.members)


@pytest.mark.parametrize("replace", [False, True])
def test_yaml_member_options_validate_nested_placement(replace: bool) -> None:
    """
    Reject non-boolean placement values inside recursively nested options
    """
    from great_docs._apiref.spec import SpecObject

    options = {"member_options": {"member_options": {"members_on_same_page": "false"}}}
    with pytest.raises(ValueError, match="members_on_same_page.*true or false"):
        if replace:
            SpecObject(name="Widget").replace(**options)
        else:
            SpecObject(name="Widget", **options)
