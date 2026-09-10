import json
from unittest.mock import MagicMock, patch

import pytest

from great_docs._builtin.directives import DIRECTIVES
from great_docs._lint import (
    LintIssue,
    LintResult,
    _check_cross_references,
    _check_directive_consistency,
    _check_docstring_style,
    _check_missing_docstrings,
    _extract_frontmatter_upcoming,
    _lost_sections,
    _section_kinds,
    _version_distance,
    run_lint,
)
from great_docs._interlinks import Source
from great_docs._sphinx_inventory import Inventory, InventoryEntry
from great_docs._utils import QUARTO_YML_HEADER


class TestLintIssue:
    def test_to_dict(self):
        issue = LintIssue(
            check="missing-docstring",
            severity="error",
            symbol="MyClass",
            message="No docstring.",
        )
        d = issue.to_dict()

        assert d == {
            "check": "missing-docstring",
            "severity": "error",
            "symbol": "MyClass",
            "message": "No docstring.",
        }


class TestLintResult:
    def test_empty_result(self):
        r = LintResult()

        assert r.status == "pass"
        assert r.errors == []
        assert r.warnings == []
        assert r.infos == []

    def test_status_fail_on_errors(self):
        r = LintResult(issues=[LintIssue("x", "error", "sym", "msg")])

        assert r.status == "fail"

    def test_status_warn_on_warnings(self):
        r = LintResult(issues=[LintIssue("x", "warning", "sym", "msg")])

        assert r.status == "warn"

    def test_status_pass_on_info_only(self):
        r = LintResult(issues=[LintIssue("x", "info", "sym", "msg")])

        assert r.status == "pass"

    def test_to_dict(self):
        r = LintResult(
            package_name="mypackage",
            exports_count=5,
            issues=[
                LintIssue("missing-docstring", "error", "func_a", "No docstring."),
                LintIssue("style-mismatch", "warning", "func_b", "Wrong style."),
            ],
        )
        d = r.to_dict()

        assert d["status"] == "fail"
        assert d["package"] == "mypackage"
        assert d["exports_checked"] == 5
        assert d["summary"]["errors"] == 1
        assert d["summary"]["warnings"] == 1
        assert d["summary"]["info"] == 0
        assert len(d["issues"]) == 2


NUMPY_DOC = """\
Short description.

Parameters
----------
x : int
    The value.
"""

GOOGLE_DOC = """\
Short description.

Args:
    x: The value.
"""

SPHINX_DOC = """\
Short description.

:param x: The value.
:returns: Something.
"""


class TestSectionKinds:
    @pytest.mark.parametrize(
        ("doc", "style"),
        [(NUMPY_DOC, "numpy"), (GOOGLE_DOC, "google"), (SPHINX_DOC, "sphinx")],
    )
    def test_own_parser_reads_the_parameters(self, doc: str, style: str):
        assert "parameters" in _section_kinds(doc, style)

    @pytest.mark.parametrize(
        ("doc", "style"),
        [(NUMPY_DOC, "google"), (GOOGLE_DOC, "numpy"), (SPHINX_DOC, "numpy")],
    )
    def test_foreign_parser_reads_nothing(self, doc: str, style: str):
        assert _section_kinds(doc, style) == set()

    def test_prose_has_no_structure_under_any_parser(self):
        for style in ("numpy", "google", "sphinx"):
            assert _section_kinds("Just a short description.", style) == set()

    def test_empty_string(self):
        assert _section_kinds("", "numpy") == set()


class TestLostSections:
    @pytest.mark.parametrize(
        ("doc", "style"),
        [(NUMPY_DOC, "numpy"), (GOOGLE_DOC, "google"), (SPHINX_DOC, "sphinx")],
    )
    def test_docstring_in_the_configured_style_loses_nothing(self, doc: str, style: str):
        assert _lost_sections(doc, style) == {}

    def test_prose_loses_nothing(self):
        assert _lost_sections("Just a short description.", "numpy") == {}

    def test_numpy_examples_alone_is_not_reported_as_foreign(self):
        """
        An `Examples` section is plain rST, so it must not look like another style

        griffe's own style inference omits `Examples` from its numpy patterns for
        this reason: the section appears in docstrings of every style.
        """
        doc = "Short description.\n\nExamples\n--------\n>>> f(1)\n"

        assert _lost_sections(doc, "numpy") == {}

    def test_google_sections_under_the_numpy_parser_are_reported(self):
        assert _lost_sections(GOOGLE_DOC, "numpy") == {"google": {"parameters"}}

    def test_singular_example_header_is_reported(self):
        """
        `Example:` reaches the reader as an admonition only under the Google parser

        The header is not one that a section-name pattern would list, which is why
        the check asks the parsers instead of matching headers.
        """
        doc = "Short description.\n\nExample:\n    >>> f(1)\n    1\n"

        assert _lost_sections(doc, "numpy") == {"google": {"admonition"}}

    def test_a_foreign_section_beside_native_ones_is_reported(self):
        """A docstring is not excused by the configured parser reading part of it"""
        doc = NUMPY_DOC + "\nExamples:\n    >>> f(1)\n"

        assert _lost_sections(doc, "numpy") == {"google": {"examples"}}


def _make_griffe_obj(kind="function", docstring=None, members=None):
    """Create a mock griffe object."""
    obj = MagicMock()
    obj.kind.value = kind
    if docstring is not None:
        obj.docstring = MagicMock()
        obj.docstring.value = docstring
    else:
        obj.docstring = None
    if members is not None:
        obj.members = members
    else:
        obj.members = {}
    return obj


def _make_pkg(members_dict):
    """Create a mock griffe package with a dict-like members attribute."""
    pkg = MagicMock()
    # Use a real dict for members so __contains__ and __getitem__ work naturally
    pkg.members = members_dict
    return pkg


def _make_documented_item(name, aliases, docstring):
    """Create a mock manifest item, shaped like the `InventoryItem`s `AliasClaims.make` reads."""
    item = MagicMock()
    item.name = name
    item.aliases = aliases
    item.obj = _make_griffe_obj(docstring=docstring)
    item.uri = f"reference/{name}.html"
    item.dispname = name
    return item


def _index(documented, external=()):
    """Build the index used by cross-reference checks"""
    from great_docs._apiref.inventory import create_inventory
    from great_docs._interlinks import AliasClaims, build_index

    return build_index(
        create_inventory("mypkg", "", documented),
        AliasClaims.make(documented),
        list(external),
    )


def _documented(*names):
    """Mock manifest items for objects documented under `mypkg`, each claiming its own name."""
    return [_make_documented_item(f"mypkg.{name}", (name,), "Documented.") for name in names]


class TestCheckMissingDocstrings:
    def test_export_with_docstring(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Documented function.")})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 0

    def test_export_without_docstring(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=None)})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "missing-docstring"
        assert result.issues[0].severity == "error"
        assert result.issues[0].symbol == "func_a"

    def test_export_with_empty_docstring(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="   ")})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "missing-docstring"

    def test_class_method_without_docstring(self):
        method = _make_griffe_obj(kind="function", docstring=None)
        cls = _make_griffe_obj(
            kind="class",
            docstring="Documented class.",
            members={"do_stuff": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "missing-docstring"
        assert result.issues[0].severity == "warning"
        assert result.issues[0].symbol == "MyClass.do_stuff"

    def test_private_members_skipped(self):
        private_method = _make_griffe_obj(kind="function", docstring=None)
        cls = _make_griffe_obj(
            kind="class",
            docstring="Documented class.",
            members={"_private": private_method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0

    def test_init_skipped(self):
        init_method = _make_griffe_obj(kind="function", docstring=None)
        cls = _make_griffe_obj(
            kind="class",
            docstring="Documented class.",
            members={"__init__": init_method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0

    def test_unknown_export_skipped(self):
        pkg = _make_pkg({})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["nonexistent"], result)

        assert len(result.issues) == 0


class TestCheckCrossReferences:
    def test_valid_seealso(self):
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso func_b"),
                "func_b": _make_griffe_obj(docstring="Docs."),
            }
        )
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["func_a", "func_b"],
            _documented("func_a", "func_b"),
            _index(_documented("func_a", "func_b")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_broken_seealso(self):
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso nonexistent_func"),
            }
        )
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["func_a"],
            _documented("func_a"),
            _index(_documented("func_a")),
            (),
            result,
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert result.issues[0].severity == "error"
        assert "nonexistent_func" in result.issues[0].message

    def test_broken_reference_in_second_seealso(self):
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(
                    docstring="Docs.\n\n%seealso func_b\n%seealso nonexistent_func"
                ),
                "func_b": _make_griffe_obj(docstring="Docs."),
            }
        )
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["func_a", "func_b"],
            _documented("func_a", "func_b"),
            _index(_documented("func_a", "func_b")),
            (),
            result,
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert "nonexistent_func" in result.issues[0].message

    def test_bare_seealso_does_not_lint_following_content(self):
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso\nnonexistent prose"),
            }
        )
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["func_a"],
            _documented("func_a"),
            _index(_documented("func_a")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_seealso_to_class_method(self):
        method = _make_griffe_obj(kind="function", docstring="Method.")
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.\n\n%seealso MyClass.do_stuff",
            members={"do_stuff": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["MyClass"],
            _documented("MyClass", "MyClass.do_stuff"),
            _index(_documented("MyClass", "MyClass.do_stuff")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_no_docstring_skipped(self):
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring=None),
            }
        )
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["func_a"],
            _documented("func_a"),
            _index(_documented("func_a")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_seealso_to_a_submodule_qualified_class(self):
        """
        A reference the build resolves is not reported

        `store.Cache` is documented and claims that spelling, but it is not a
        top-level export, so a check deriving its own names from the package
        called it broken.
        """
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso store.Cache"),
            }
        )
        documented = [
            _make_documented_item("mypkg.func_a", ("func_a",), "Docs."),
            _make_documented_item("mypkg.store.Cache", ("store.Cache", "Cache"), "A cache."),
        ]
        result = LintResult()
        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented), (), result
        )

        assert len(result.issues) == 0

    def test_seealso_to_an_undocumented_name_is_reported(self):
        """A reference naming nothing the build indexes still fails the check."""
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso store.Ghost"),
            }
        )
        documented = [
            _make_documented_item("mypkg.func_a", ("func_a",), "Docs."),
            _make_documented_item("mypkg.store.Cache", ("store.Cache", "Cache"), "A cache."),
        ]
        result = LintResult()
        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented), (), result
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert "store.Ghost" in result.issues[0].message

    def test_no_documented_objects_reports_nothing(self):
        """An unresolvable reference means the check cannot see the API, so it stays silent."""
        pkg = _make_pkg(
            {
                "func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso anything"),
            }
        )
        result = LintResult()
        _check_cross_references(pkg, "mypkg", ["func_a"], [], _index([]), (), result)

        assert len(result.issues) == 0


class TestSeealsoScannedObjects:
    """Cross-reference checks scan rendered docstrings only"""

    def test_an_undocumented_member_docstring_is_not_scanned(self):
        """Skip a hidden member docstring"""
        method = _make_griffe_obj(kind="function", docstring="Flush it.\n\n%seealso helper")
        pkg = _make_pkg(
            {"Cache": _make_griffe_obj(kind="class", docstring="A cache.", members={"flush": method})}
        )
        documented = [_make_documented_item("mypkg.Cache", ("Cache",), "A cache.")]
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["Cache"], documented, _index(documented), (), result
        )

        assert result.issues == []

    def test_a_documented_member_docstring_is_scanned(self):
        """Check a documented member docstring"""
        method = _make_griffe_obj(kind="function", docstring="Flush it.\n\n%seealso helper")
        pkg = _make_pkg(
            {"Cache": _make_griffe_obj(kind="class", docstring="A cache.", members={"flush": method})}
        )
        documented = [
            _make_documented_item("mypkg.Cache", ("Cache",), "A cache."),
            _make_documented_item("mypkg.Cache.flush", ("flush", "Cache.flush"), "Flush it."),
        ]
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["Cache"], documented, _index(documented), (), result
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert result.issues[0].symbol == "Cache.flush"

    def test_an_undocumented_export_docstring_is_not_scanned(self):
        """Skip an export omitted from the reference"""
        pkg = _make_pkg(
            {
                "Cache": _make_griffe_obj(kind="class", docstring="A cache."),
                "Hidden": _make_griffe_obj(kind="class", docstring="Hidden.\n\n%seealso helper"),
            }
        )
        documented = [_make_documented_item("mypkg.Cache", ("Cache",), "A cache.")]
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["Cache", "Hidden"], documented, _index(documented), (), result
        )

        assert result.issues == []


class TestSeealsoAgainstArbitration:
    """Cross-reference checks apply the build's resolution rules"""

    def test_a_seealso_to_an_ambiguous_short_name_is_reported(self):
        """Two objects claiming `flush` means `%seealso flush` links nowhere."""
        documented = [
            _make_documented_item("mypkg.StoreCache", ("StoreCache",), "A store."),
            _make_documented_item(
                "mypkg.StoreCache.flush", ("flush", "StoreCache.flush"), "Flush writes."
            ),
            _make_documented_item("mypkg.NetCache", ("NetCache",), "A connection."),
            _make_documented_item(
                "mypkg.NetCache.flush", ("flush", "NetCache.flush"), "Flush the socket."
            ),
        ]
        pkg = _make_pkg(
            {"StoreCache": _make_griffe_obj(kind="class", docstring="A store.\n\n%seealso flush")}
        )
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["StoreCache"], documented, _index(documented), (), result
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "ambiguous-xref"
        assert "mypkg.NetCache.flush" in result.issues[0].message
        assert "mypkg.StoreCache.flush" in result.issues[0].message

    def test_a_seealso_to_an_unambiguous_short_name_passes(self):
        documented = _documented("Thing", "run")
        pkg = _make_pkg(
            {"Thing": _make_griffe_obj(kind="class", docstring="A thing.\n\n%seealso run")}
        )
        result = LintResult()

        _check_cross_references(pkg, "mypkg", ["Thing"], documented, _index(documented), (), result)

        assert result.issues == []

    def test_a_seealso_to_nothing_documented_is_still_broken(self):
        """An unknown name keeps its own diagnosis rather than becoming ambiguous."""
        documented = _documented("Thing")
        pkg = _make_pkg(
            {"Thing": _make_griffe_obj(kind="class", docstring="A thing.\n\n%seealso nope")}
        )
        result = LintResult()

        _check_cross_references(pkg, "mypkg", ["Thing"], documented, _index(documented), (), result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"

_NUMPY = (
    Source(name="numpy", url="https://numpy.org/doc/stable", aliases=("np",)),
    Inventory(
        "numpy",
        "2.1",
        (InventoryEntry("numpy.ndarray", "py", "class", 1, "reference/ndarray.html", "-"),),
    ),
)
"""A linked NumPy source in the form returned by `load_sources`"""


class TestSeealsoAgainstLinkedSources:
    """Validate linked-source `%seealso` references as the build does"""

    def test_a_seealso_into_a_linked_source_resolves(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso numpy.ndarray")})
        documented = _documented("func_a")
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented, [_NUMPY]), (), result
        )

        assert result.issues == []

    def test_a_seealso_through_a_source_alias_resolves(self):
        """Resolve `%seealso` through a source alias as the filter does"""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso np.ndarray")})
        documented = _documented("func_a")
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented, [_NUMPY]), (), result
        )

        assert result.issues == []

    def test_a_seealso_naming_nothing_in_a_linked_source_is_broken(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso numpy.ghost")})
        documented = _documented("func_a")
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented, [_NUMPY]), (), result
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert "%seealso" in result.issues[0].message
        assert "%%" not in result.issues[0].message

    def test_an_unread_source_reports_itself_instead_of_the_references(self):
        """Report an unread source rather than guess at an unresolved reference"""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso numpy.ndarray")})
        documented = _documented("func_a")
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented), ("numpy",), result
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "unread-source"
        assert result.issues[0].severity == "info"
        assert "numpy" in result.issues[0].message

    def test_an_unread_source_does_not_silence_local_ambiguity(self):
        """Report local ambiguity despite an unread source"""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Docs.\n\n%seealso Cache")})
        documented = [
            _make_documented_item("mypkg.func_a", ("func_a",), "Docs."),
            _make_documented_item("mypkg.a.Cache", ("Cache",), "Documented."),
            _make_documented_item("mypkg.b.Cache", ("Cache",), "Documented."),
        ]
        result = LintResult()

        _check_cross_references(
            pkg, "mypkg", ["func_a"], documented, _index(documented), ("numpy",), result
        )

        checks = {issue.check for issue in result.issues}
        assert checks == {"ambiguous-xref", "unread-source"}


class TestCheckDocstringStyle:
    def test_matching_style(self):
        doc = "Short.\n\nParameters\n----------\nx : int\n"
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["func_a"], "numpy", result)

        assert len(result.issues) == 0

    def test_mismatching_style(self):
        doc = "Short.\n\nArgs:\n    x: The value.\n"
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["func_a"], "numpy", result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "style-mismatch"
        assert result.issues[0].severity == "warning"

    def test_no_sections_no_issue(self):
        doc = "Just a short description."
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["func_a"], "numpy", result)

        assert len(result.issues) == 0

    def test_class_methods_checked(self):
        method_doc = "method.\n\nArgs:\n    x: value.\n"
        method = _make_griffe_obj(kind="function", docstring=method_doc)
        cls = _make_griffe_obj(
            kind="class",
            docstring="class.\n\nParameters\n----------\n",
            members={"do_stuff": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["MyClass"], "numpy", result)

        # Method has google style but config says numpy -> warning
        assert len(result.issues) == 1
        assert result.issues[0].symbol == "MyClass.do_stuff"

    def test_invalid_config_style_appends_error(self):
        """Unknown config_style appends a config error and returns early."""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring="Short.")})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["func_a"], "jsdoc", result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "config"
        assert result.issues[0].severity == "error"
        assert "jsdoc" in result.issues[0].message


class TestCheckDirectiveConsistency:
    @pytest.mark.parametrize("directive", sorted(DIRECTIVES))
    def test_registered_directive_is_known(self, directive: str):
        doc = f"Short.\n\n%{directive}"
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["func_a"], result)

        assert result.issues == []

    def test_unknown_directive(self):
        doc = "Short.\n\n%internal\n"
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "unknown-directive"
        assert "%internal" in result.issues[0].message

    @pytest.mark.parametrize("directive", ["WARNING", "SeeAlso", "NODOC"])
    def test_mixed_case_directive_is_unknown(self, directive: str):
        doc = f"Short.\n\n%{directive}"
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=doc)})
        result = LintResult()

        _check_directive_consistency(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 1
        assert result.issues[0].check == "unknown-directive"
        assert f"%{directive}" in result.issues[0].message

    def test_no_docstring_skipped(self):
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=None)})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 0


class TestRunLint:
    def test_unknown_check_name(self, tmp_path):
        result = run_lint(tmp_path, checks={"bogus-check"})

        assert result.status == "fail"
        assert "Unknown check" in result.issues[0].message

    @patch("great_docs.core.GreatDocs", side_effect=RuntimeError("constructor boom"))
    def test_constructor_exception_propagates_when_not_quiet(self, mock_gd_cls, tmp_path):
        """Exception from GreatDocs() when quiet=False is re-raised to caller."""
        with pytest.raises(RuntimeError, match="constructor boom"):
            run_lint(tmp_path)

    @patch("great_docs.core.GreatDocs")
    def test_no_package_detected(self, mock_gd_cls, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = None
        mock_gd_cls.return_value = mock_gd

        result = run_lint(tmp_path)

        assert result.status == "fail"
        assert "Could not detect package name" in result.issues[0].message

    @patch("great_docs.core.GreatDocs")
    def test_griffe_import_error(self, mock_gd_cls, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._detect_module_name.return_value = None
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd_cls.return_value = mock_gd

        with patch.dict("sys.modules", {"griffe": None}):
            # Simulate ImportError for griffe
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "griffe":
                    raise ImportError("No module named 'griffe'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = run_lint(tmp_path)

        assert result.status == "fail"
        assert any("griffe" in i.message for i in result.issues)

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_successful_lint_run(self, mock_gd_cls, mock_griffe_load, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._resolve_importable_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = ["func_a", "func_b"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd_cls.return_value = mock_gd

        func_a = _make_griffe_obj(docstring="Documented.\n\nParameters\n----------\nx : int\n")
        func_b = _make_griffe_obj(docstring=None)
        members = {"func_a": func_a, "func_b": func_b}

        mock_pkg = MagicMock()
        mock_pkg.members = members
        mock_griffe_load.return_value = mock_pkg

        result = run_lint(tmp_path)

        assert result.package_name == "mypkg"
        assert result.exports_count == 2

        # func_b has no docstring -> error
        assert any(i.check == "missing-docstring" and i.symbol == "func_b" for i in result.issues)

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_ambiguity_check_respects_the_renderer_member_selection(
        self, mock_gd_cls, mock_griffe_load, tmp_path
    ):
        """A `members:` config narrowing NetCache must not make `flush` look ambiguous."""
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._resolve_importable_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = ["StoreCache", "NetCache"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        # The renderer documents NetCache itself but, per its `members: false`
        # config, none of its members — only StoreCache.flush gets a page.
        mock_gd.documented_objects.return_value = [
            _make_documented_item(
                "mypkg.StoreCache", ("StoreCache",), "A store.\n\nSee [](`flush`)."
            ),
            _make_documented_item(
                "mypkg.StoreCache.flush", ("flush", "StoreCache.flush"), "Flush buffered writes."
            ),
            _make_documented_item("mypkg.NetCache", ("NetCache",), "A connection."),
        ]
        mock_gd_cls.return_value = mock_gd

        store_flush = _make_griffe_obj(kind="function", docstring="Flush buffered writes.")
        net_flush = _make_griffe_obj(kind="function", docstring="Flush the socket.")
        store_cls = _make_griffe_obj(
            kind="class", docstring="A store.\n\nSee [](`flush`).", members={"flush": store_flush}
        )
        net_cls = _make_griffe_obj(
            kind="class", docstring="A connection.", members={"flush": net_flush}
        )
        mock_pkg = MagicMock()
        mock_pkg.members = {"StoreCache": store_cls, "NetCache": net_cls}
        mock_griffe_load.return_value = mock_pkg

        result = run_lint(tmp_path)

        assert not any(i.check == "ambiguous-xref" for i in result.issues)

    @patch("great_docs._lint.load_sources")
    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_an_unresolvable_reference_reads_no_sources(
        self, mock_gd_cls, mock_griffe_load, mock_load_sources, tmp_path
    ):
        """`load_sources` is the only thing that would put a lint run on the
        network, so a run over a project whose reference resolves nothing
        must never call it."""
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._resolve_importable_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = ["func_a"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd.documented_objects.return_value = []
        mock_gd_cls.return_value = mock_gd

        func_a = _make_griffe_obj(docstring="Docs.\n\n%seealso nope")
        mock_pkg = MagicMock()
        mock_pkg.members = {"func_a": func_a}
        mock_griffe_load.return_value = mock_pkg

        run_lint(tmp_path)

        mock_load_sources.assert_not_called()

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_resolves_module_name_when_project_name_differs(
        self, mock_gd_cls, mock_griffe_load, tmp_path
    ):
        """Regression: run_lint loads griffe by the importable module name, not the
        dash-normalized PyPI project name, when the two diverge."""
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "my-dist"
        mock_gd._resolve_importable_name.return_value = "actual_module"
        mock_gd._get_package_exports.return_value = ["func_a"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd_cls.return_value = mock_gd

        func_a = _make_griffe_obj(docstring="Documented.\n\nParameters\n----------\nx : int\n")
        mock_pkg = MagicMock()
        mock_pkg.members = {"func_a": func_a}
        mock_griffe_load.return_value = mock_pkg

        result = run_lint(tmp_path)

        mock_gd._resolve_importable_name.assert_called_once_with("my-dist")
        mock_griffe_load.assert_called_once_with(
            "actual_module", search_paths=mock_gd._griffe_search_paths.return_value
        )
        assert result.package_name == "actual_module"

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_selective_checks(self, mock_gd_cls, mock_griffe_load, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._detect_module_name.return_value = None
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = ["func_a"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd_cls.return_value = mock_gd

        # func_a has Google-style docstring (triggers style-mismatch) and no xref issues
        func_a = _make_griffe_obj(docstring="Docs.\n\nArgs:\n    x: val.\n")
        members = {"func_a": func_a}

        mock_pkg = MagicMock()
        mock_pkg.members = members
        mock_griffe_load.return_value = mock_pkg

        # Only run docstrings check — should find no issue (func_a has a docstring)
        result = run_lint(tmp_path, checks={"docstrings"})

        assert all(i.check != "style-mismatch" for i in result.issues)

        # Only run style check — should find style mismatch
        result = run_lint(tmp_path, checks={"style"})

        assert any(i.check == "style-mismatch" for i in result.issues)

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_no_exports(self, mock_gd_cls, mock_griffe_load, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = None
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd_cls.return_value = mock_gd

        mock_pkg = MagicMock()
        mock_pkg.members = {}
        mock_griffe_load.return_value = mock_pkg

        result = run_lint(tmp_path)

        assert result.status == "pass"
        assert result.exports_count == 0

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_griffe_load_failure(self, mock_gd_cls, mock_griffe_load, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd_cls.return_value = mock_gd

        mock_griffe_load.side_effect = Exception("Module not found")

        result = run_lint(tmp_path)

        assert result.status == "fail"
        assert any("Could not load package" in i.message for i in result.issues)


class TestJsonOutput:
    def test_json_is_valid(self):
        r = LintResult(
            package_name="mypkg",
            exports_count=3,
            issues=[
                LintIssue("missing-docstring", "error", "func_a", "No docstring."),
                LintIssue("style-mismatch", "warning", "func_b", "Wrong style."),
                LintIssue("broken-xref", "error", "func_c", "Unknown ref."),
            ],
        )
        output = json.dumps(r.to_dict(), indent=2)
        parsed = json.loads(output)

        assert parsed["status"] == "fail"
        assert parsed["summary"]["errors"] == 2
        assert parsed["summary"]["warnings"] == 1
        assert len(parsed["issues"]) == 3


class TestRunLintQuiet:
    """Tests that exercise the quiet=True branches for stdout suppression."""

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_quiet_suppresses_output(self, mock_gd_cls, mock_griffe_load, tmp_path, capsys):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd._get_package_exports.return_value = ["func_a"]
        mock_gd._config.get.return_value = "numpy"
        mock_gd._config.__getitem__.return_value = "numpy"
        mock_gd_cls.return_value = mock_gd

        func_a = _make_griffe_obj(docstring="Documented.")
        mock_pkg = MagicMock()
        mock_pkg.members = {"func_a": func_a}
        mock_griffe_load.return_value = mock_pkg

        result = run_lint(tmp_path, quiet=True)

        assert result.status == "pass"

    @patch("great_docs.core.GreatDocs")
    def test_quiet_no_package_restores_stdout(self, mock_gd_cls, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = None
        mock_gd_cls.return_value = mock_gd

        import sys

        original_stdout = sys.stdout
        result = run_lint(tmp_path, quiet=True)

        # stdout must be restored after early return
        assert sys.stdout is original_stdout
        assert result.status == "fail"

    @patch("great_docs.core.GreatDocs")
    def test_quiet_griffe_import_error_restores_stdout(self, mock_gd_cls, tmp_path):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd_cls.return_value = mock_gd

        import builtins
        import sys

        original_import = builtins.__import__
        original_stdout = sys.stdout

        def mock_import(name, *args, **kwargs):
            if name == "griffe":
                raise ImportError("No module named 'griffe'")
            return original_import(name, *args, **kwargs)

        with patch.dict("sys.modules", {"griffe": None}):
            with patch("builtins.__import__", side_effect=mock_import):
                result = run_lint(tmp_path, quiet=True)

        assert sys.stdout is original_stdout
        assert result.status == "fail"
        assert any("griffe" in i.message for i in result.issues)

    @patch("griffe.load")
    @patch("great_docs.core.GreatDocs")
    def test_quiet_griffe_load_failure_restores_stdout(
        self, mock_gd_cls, mock_griffe_load, tmp_path
    ):
        mock_gd = MagicMock()
        mock_gd._detect_package_name.return_value = "mypkg"
        mock_gd._normalize_package_name.return_value = "mypkg"
        mock_gd_cls.return_value = mock_gd

        mock_griffe_load.side_effect = RuntimeError("Cannot load")

        import sys

        original_stdout = sys.stdout
        result = run_lint(tmp_path, quiet=True)

        assert sys.stdout is original_stdout
        assert result.status == "fail"

    @patch("great_docs.core.GreatDocs")
    def test_quiet_constructor_exception_restores_stdout(self, mock_gd_cls, tmp_path):
        """When GreatDocs() constructor raises, stdout is restored before re-raising."""
        mock_gd_cls.side_effect = RuntimeError("constructor boom")

        import sys

        original_stdout = sys.stdout
        with pytest.raises(RuntimeError, match="constructor boom"):
            run_lint(tmp_path, quiet=True)

        assert sys.stdout is original_stdout


class TestHelperEdgeCases:
    def test_get_docstring_exception(self):
        """Test _get_docstring when accessing docstring raises an exception."""
        from great_docs._lint import _get_docstring

        obj = MagicMock()
        obj.docstring = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        # Make hasattr+access raise
        type(obj).docstring = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        result = _get_docstring(obj)

        assert result is None

    def test_iter_public_members_exception(self):
        """Test _iter_public_members when members.items() raises."""
        from great_docs._lint import _iter_public_members

        obj = MagicMock()
        obj.members.items.side_effect = RuntimeError("broken")
        members = list(_iter_public_members(obj))

        assert members == []

    def test_iter_public_members_yields_dunders(self):
        """Test that public dunders (not __init__) are yielded."""
        from great_docs._lint import _iter_public_members

        method_repr = MagicMock()
        method_init = MagicMock()
        method_public = MagicMock()
        members_dict = {
            "__repr__": method_repr,
            "__init__": method_init,
            "public_method": method_public,
        }
        obj = MagicMock()
        obj.members.items.return_value = members_dict.items()

        result = list(_iter_public_members(obj))
        names = [name for name, _ in result]

        assert "__repr__" in names
        assert "__init__" not in names
        assert "public_method" in names


class TestCheckMissingDocstringsEdgeCases:
    def test_class_member_kind_exception(self):
        """When member.kind.value raises, skip that member gracefully."""
        broken_member = MagicMock()
        broken_member.kind.value = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        # Make kind.value raise
        type(broken_member.kind).value = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )

        cls = _make_griffe_obj(
            kind="class",
            docstring="Documented class.",
            members={"broken": broken_member},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert all(i.symbol != "MyClass.broken" for i in result.issues)

    def test_class_member_non_function_skipped(self):
        """Attributes (non-function members) should not generate missing-docstring warnings."""
        attr = _make_griffe_obj(kind="attribute", docstring=None)
        cls = _make_griffe_obj(
            kind="class",
            docstring="Documented class.",
            members={"my_attr": attr},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0

    def test_class_outer_exception(self):
        """When obj.kind.value raises, the outer except catches it."""
        obj = _make_griffe_obj(docstring="Has docstring.")
        # Override kind to raise on value access
        type(obj.kind).value = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        pkg = _make_pkg({"weird_obj": obj})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["weird_obj"], result)

    def test_class_method_with_docstring_loop_continues(self):
        """Class method WITH a docstring: no issue added, loop continues."""
        method = _make_griffe_obj(kind="function", docstring="Fully documented.")
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.",
            members={"do_stuff": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_missing_docstrings(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0


class TestCheckCrossReferencesEdgeCases:
    def test_export_not_in_pkg_members(self):
        """Exports not found in pkg.members should be skipped."""
        pkg = _make_pkg({})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["missing_export"],
            _documented("other"),
            _index(_documented("other")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_class_member_broken_xref(self):
        """Broken xref in a class method docstring."""
        method = _make_griffe_obj(
            kind="function",
            docstring="Method.\n\n%seealso nonexistent_thing",
        )
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.",
            members={"my_method": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["MyClass"],
            _documented("MyClass", "MyClass.my_method"),
            _index(_documented("MyClass", "MyClass.my_method")),
            (),
            result,
        )

        assert len(result.issues) == 1
        assert result.issues[0].symbol == "MyClass.my_method"
        assert result.issues[0].check == "broken-xref"

    def test_class_member_valid_xref(self):
        """Valid xref in a class method docstring (refers to another export)."""
        method = _make_griffe_obj(
            kind="function",
            docstring="Method.\n\n%seealso helper_func",
        )
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.",
            members={"my_method": method},
        )
        helper = _make_griffe_obj(docstring="Helper.")
        pkg = _make_pkg({"MyClass": cls, "helper_func": helper})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["MyClass", "helper_func"],
            _documented("MyClass", "MyClass.my_method", "helper_func"),
            _index(_documented("MyClass", "MyClass.my_method", "helper_func")),
            (),
            result,
        )

        assert len(result.issues) == 0

    def test_class_method_broken_xref_no_class_xref(self):
        """Class has no xrefs but its method has a broken one."""
        method = _make_griffe_obj(
            kind="function",
            docstring="Method.\n\n%seealso ghost_func",
        )
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class with no seealso.",
            members={"my_method": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["MyClass"],
            _documented("MyClass", "MyClass.my_method"),
            _index(_documented("MyClass", "MyClass.my_method")),
            (),
            result,
        )

        assert len(result.issues) == 1
        assert result.issues[0].check == "broken-xref"
        assert result.issues[0].symbol == "MyClass.my_method"
        assert "ghost_func" in result.issues[0].message

    def test_class_kind_exception_while_scanning(self):
        """When obj.kind.value raises while scanning a docstring, skip gracefully."""
        obj = _make_griffe_obj(docstring="Doc.")
        type(obj.kind).value = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        pkg = _make_pkg({"broken_cls": obj})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["broken_cls"],
            _documented("broken_cls"),
            _index(_documented("broken_cls")),
            (),
            result,
        )

    def test_class_outer_exception_in_method_xref(self):
        """When iterating class methods raises, the outer except catches it."""
        obj = _make_griffe_obj(docstring="Doc.\n\n%seealso something")
        # First call to kind.value works (for the top-level xref check),
        # but accessing members raises
        obj.kind.value = "class"
        obj.members = MagicMock()
        obj.members.items.side_effect = RuntimeError("boom")
        pkg = _make_pkg({"MyClass": obj, "something": _make_griffe_obj(docstring="X.")})
        result = LintResult()
        _check_cross_references(
            pkg,
            "mypkg",
            ["MyClass", "something"],
            _documented("MyClass", "something"),
            _index(_documented("MyClass", "something")),
            (),
            result,
        )


class TestMixedStyleDocstrings:
    """
    A docstring mixing two styles reports whichever structure the build loses

    The previous header-matching check reported one winning style per docstring
    and so stayed silent whenever the configured style was among those matched.
    """

    def test_a_stray_field_of_a_kind_already_present_goes_unreported(self):
        """
        Two styles contributing the same section kind cancel out

        The check compares which kinds each parser reads, not what each one puts
        in them, so a `:param:` beside a numpy `Parameters` section is invisible:
        both parsers report `parameters`. Naming the lost parameter would mean
        comparing section contents per kind, which buys little for how rarely a
        docstring mixes styles within one kind.
        """
        doc = """\
Short description.

Parameters
----------
x : int

:param y: Another param.
"""
        assert _lost_sections(doc, "numpy") == {}

    def test_sphinx_field_with_a_google_section(self):
        doc = """\
Short description.

:param x: A param.

Args:
    y: Another param.
"""
        assert _lost_sections(doc, "numpy") == {
            "google": {"parameters"},
            "sphinx": {"parameters"},
        }


class TestCheckDocstringStyleEdgeCases:
    def test_export_not_in_pkg(self):
        """Exports not in pkg.members should be skipped."""
        pkg = _make_pkg({})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["missing"], "numpy", result)

        assert len(result.issues) == 0

    def test_class_method_style_exception(self):
        """When class kind raises, outer except catches it."""
        obj = _make_griffe_obj(docstring="Short.")
        type(obj.kind).value = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        pkg = _make_pkg({"broken": obj})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["broken"], "numpy", result)

    def test_no_docstring_skipped(self):
        """Export with None docstring is skipped without error."""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=None)})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["func_a"], "numpy", result)

        assert len(result.issues) == 0

    def test_class_method_no_docstring_not_checked(self):
        """Class method without a docstring: loop continues without calling _check_one."""
        method = _make_griffe_obj(kind="function", docstring=None)
        cls = _make_griffe_obj(kind="class", docstring="Short.", members={"do_stuff": method})
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_docstring_style(pkg, "mypkg", ["MyClass"], "numpy", result)

        assert len(result.issues) == 0


class TestCheckDirectiveConsistencyEdgeCases:
    def test_export_not_in_pkg(self):
        """Exports not in pkg.members should be skipped."""
        pkg = _make_pkg({})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["missing"], result)

        assert len(result.issues) == 0

    def test_class_method_unknown_directive(self):
        """Unknown directive in a class method docstring."""
        method = _make_griffe_obj(
            kind="function",
            docstring="Method.\n\n%versionremoved 2.0\n",
        )
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.",
            members={"my_method": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 1
        assert result.issues[0].symbol == "MyClass.my_method"
        assert result.issues[0].check == "unknown-directive"

    def test_class_method_valid_directive(self):
        """Valid directives in class method docstrings pass without issues."""
        method = _make_griffe_obj(
            kind="function",
            docstring="Method.\n\n%seealso helper_func\n",
        )
        cls = _make_griffe_obj(
            kind="class",
            docstring="Class.",
            members={"my_method": method},
        )
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0

    def test_class_kind_exception(self):
        """When class kind raises, outer except catches it."""
        obj = _make_griffe_obj(docstring="Short.")
        type(obj.kind).value = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        pkg = _make_pkg({"broken": obj})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["broken"], result)

    def test_no_docstring_on_export(self):
        """Export with no docstring should be skipped."""
        pkg = _make_pkg({"func_a": _make_griffe_obj(docstring=None)})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["func_a"], result)

        assert len(result.issues) == 0

    def test_class_method_no_docstring_loop_continues(self):
        """Class method without docstring: member_doc is falsy, loop continues."""
        method = _make_griffe_obj(kind="function", docstring=None)
        cls = _make_griffe_obj(kind="class", docstring="Short.", members={"do_stuff": method})
        pkg = _make_pkg({"MyClass": cls})
        result = LintResult()
        _check_directive_consistency(pkg, "mypkg", ["MyClass"], result)

        assert len(result.issues) == 0


# ---------------------------------------------------------------------------
# Stale version annotation checks
# ---------------------------------------------------------------------------


class TestCheckStaleVersions:
    """Tests for _check_stale_versions lint check."""

    def _make_project(self, tmp_path, versions_yaml, qmd_files: dict[str, str]):
        """Create a minimal project with great-docs.yml and .qmd files."""
        config = f"versions:\n{versions_yaml}\n"
        (tmp_path / "great-docs.yml").write_text(config)
        for rel_path, content in qmd_files.items():
            p = tmp_path / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    @property
    def _versions_yaml(self):
        return (
            '  - label: "0.8 (dev)"\n'
            "    tag: dev\n"
            '    version: "0.8"\n'
            "    prerelease: true\n"
            '  - label: "0.7"\n'
            '    tag: "0.7"\n'
            "    latest: true\n"
            '  - label: "0.6"\n'
            '    tag: "0.6"\n'
            '  - label: "0.5"\n'
            '    tag: "0.5"\n'
            '  - label: "0.4"\n'
            '    tag: "0.4"\n'
            '  - label: "0.3"\n'
            '    tag: "0.3"\n'
            '  - label: "0.2"\n'
            '    tag: "0.2"\n'
            '  - label: "0.1"\n'
            '    tag: "0.1"\n'
        )

    def test_stale_badge_detected(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\nSome text [version-badge new 0.3] here.\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert "0.3" in stale[0].message
        assert "4 releases behind" in stale[0].message

    def test_fresh_badge_not_flagged(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\nSome text [version-badge new 0.6] here.\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 0

    def test_stale_callout_detected(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\n"
                    '::: {.version-note version="0.2"}\n'
                    "Added in 0.2.\n"
                    ":::\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-callout"]
        assert len(stale) == 1
        assert "0.2" in stale[0].message
        assert stale[0].severity == "info"

    def test_fresh_callout_not_flagged(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\n"
                    '::: {.version-note version="0.5"}\n'
                    "Added in 0.5.\n"
                    ":::\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-callout"]
        assert len(stale) == 0

    def test_stale_upcoming_detected(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": ('---\ntitle: Test\nupcoming: "0.5"\n---\n\nContent.\n'),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-upcoming"]
        assert len(stale) == 1
        assert "0.5" in stale[0].message
        assert "already-released" in stale[0].message

    def test_valid_upcoming_not_flagged(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": ('---\ntitle: Test\nupcoming: "0.8"\n---\n\nContent.\n'),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-upcoming"]
        assert len(stale) == 0

    def test_deprecated_callout_stale(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\n"
                    '::: {.version-deprecated version="0.1"}\n'
                    "Use new_func().\n"
                    ":::\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-callout"]
        assert len(stale) == 1
        assert "version-deprecated" in stale[0].message

    def test_custom_thresholds(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        # Use a very high threshold so nothing is flagged
        config = (
            f"versions:\n{self._versions_yaml}\n"
            "lint:\n"
            "  stale_versions:\n"
            "    badge_threshold: 99\n"
            "    callout_threshold: 99\n"
        )
        (tmp_path / "great-docs.yml").write_text(config)
        qmd = tmp_path / "user_guide" / "page.qmd"
        qmd.parent.mkdir(parents=True)
        qmd.write_text(
            "---\ntitle: Test\n---\n\n"
            "[version-badge new 0.1]\n"
            '::: {.version-note version="0.1"}\nOld.\n:::\n'
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert len(result.issues) == 0

    def test_no_versions_config_skips(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        (tmp_path / "great-docs.yml").write_text("theme: default\n")
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert len(result.issues) == 0

    def test_skips_underscore_dirs(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "_site/page.qmd": ("---\ntitle: Test\n---\n\n[version-badge new 0.1]\n"),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert len(result.issues) == 0

    def test_skips_versioned_build_dirs(self, tmp_path):
        """
        Skip generated copies when checking stale version markers

        Versioned builds copy source `.qmd` pages into `great-docs/` and
        `great-docs-<tag>/`. Scanning those copies would duplicate each finding,
        while a nested user directory must remain in scope.
        """
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "great-docs/user-guide/page.qmd": (
                    "---\ntitle: Test\n---\n\n[version-badge new 0.1]\n"
                ),
                "great-docs-0.6/user-guide/page.qmd": (
                    "---\ntitle: Test\n---\n\n[version-badge new 0.1]\n"
                ),
                # A nested project directory remains source; only top-level
                # build directories are excluded.
                "docs/great-docs-examples/page.qmd": (
                    "---\ntitle: Test\n---\n\n[version-badge new 0.1]\n"
                ),
            },
        )
        (tmp_path / "great-docs-0.6" / "_quarto.yml").write_text(
            QUARTO_YML_HEADER,
            encoding="utf-8",
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert "great-docs-examples" in stale[0].symbol

    def test_checks_unmarked_root_directory_with_build_like_name(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "great-docs-notes/page.qmd": ("---\ntitle: Test\n---\n\n[version-badge new 0.1]\n"),
            },
        )

        result = LintResult()
        _check_stale_versions(tmp_path, result)

        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert "great-docs-notes" in stale[0].symbol

    def test_line_numbers_correct(self, tmp_path):
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {
                "user_guide/page.qmd": (
                    "---\ntitle: Test\n---\n\nLine 5\nLine 6\n[version-badge new 0.1]\n"
                ),
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert stale[0].symbol == "user_guide/page.qmd:7"

    def test_yaml_parse_error_skips(self, tmp_path):
        """Invalid YAML in great-docs.yml returns silently."""
        from great_docs._lint import _check_stale_versions

        (tmp_path / "great-docs.yml").write_text("versions: [\n  unclosed bracket")
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert result.issues == []

    def test_empty_versions_after_parse_skips(self, tmp_path):
        """When parse_versions_config returns empty list, returns silently."""
        from great_docs._lint import _check_stale_versions

        (tmp_path / "great-docs.yml").write_text("versions:\n  - tag: v0.1\n    label: '0.1'\n")
        result = LintResult()
        with patch("great_docs._versioning.parse_versions_config", return_value=[]):
            _check_stale_versions(tmp_path, result)
        assert result.issues == []

    def test_no_latest_marked_falls_back_to_first_nonprerelease(self, tmp_path):
        """No version has latest=True: fallback loop sets latest_entry to first non-prerelease."""
        from great_docs._lint import _check_stale_versions
        from great_docs._versioning import VersionEntry

        # Return versions with no latest=True so the fallback loop (lines 584-587) is exercised
        versions_no_latest = [
            VersionEntry(tag="0.5", label="0.5", latest=False),
            VersionEntry(tag="0.2", label="0.2", latest=False),
            VersionEntry(tag="0.1", label="0.1", latest=False),
        ]
        (tmp_path / "great-docs.yml").write_text("versions:\n  - tag: '0.5'\n    label: '0.5'\n")
        result = LintResult()
        with patch("great_docs._versioning.parse_versions_config", return_value=versions_no_latest):
            _check_stale_versions(tmp_path, result)
        # Ran without error; latest_entry was set to 0.5 via fallback loop

    def test_only_prerelease_versions_skips(self, tmp_path):
        """When all versions are prerelease, latest_entry stays None and returns."""
        from great_docs._lint import _check_stale_versions

        versions_yaml = '  - label: "dev"\n    tag: dev\n    prerelease: true\n'
        self._make_project(
            tmp_path,
            versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\nContent.\n"},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert result.issues == []

    def test_version_field_added_to_released_set(self, tmp_path):
        """Non-prerelease version with a version field: version string added to released set."""
        from great_docs._lint import _check_stale_versions

        versions_yaml = (
            '  - label: "0.7"\n'
            '    tag: "0.7"\n'
            '    version: "0.7.0"\n'
            "    latest: true\n"
            '  - label: "0.1"\n'
            '    tag: "0.1"\n'
        )
        self._make_project(
            tmp_path,
            versions_yaml,
            # upcoming value matches v.version string (not tag) → stale-upcoming fires
            {"page.qmd": '---\ntitle: T\nupcoming: "0.7.0"\n---\n\nContent.\n'},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-upcoming"]
        assert len(stale) == 1
        assert "0.7.0" in stale[0].message

    def test_qmd_file_read_error_skipped(self, tmp_path):
        """Files that raise OSError when read are silently skipped."""
        from pathlib import Path

        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\n[version-badge new 0.1]\n"},
        )
        original_read_text = Path.read_text

        def _raise_for_qmd(self, encoding="utf-8"):
            if self.suffix == ".qmd":
                raise OSError("unreadable")
            return original_read_text(self, encoding=encoding)

        result = LintResult()
        with patch.object(Path, "read_text", _raise_for_qmd):
            _check_stale_versions(tmp_path, result)
        assert result.issues == []

    def test_badge_without_version_number_skipped(self, tmp_path):
        """Badge with no version arg ([version-badge new]) is skipped."""
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\n[version-badge new]\n"},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert not any(i.check == "stale-badge" for i in result.issues)

    def test_expired_new_badge_advice(self, tmp_path):
        """Expired 'new' badge shows 'consider removing' advice."""
        from great_docs._lint import _check_stale_versions

        config = f"versions:\n{self._versions_yaml}\nnew_is_old: '3 releases'\n"
        (tmp_path / "great-docs.yml").write_text(config)
        qmd = tmp_path / "page.qmd"
        qmd.write_text("---\ntitle: T\n---\n\n[version-badge new 0.1]\n")
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert "consider removing" in stale[0].message

    def test_stale_changed_badge(self, tmp_path):
        """Stale 'changed' badge uses 'still displays in all versions' advice."""
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\n[version-badge changed 0.1]\n"},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        stale = [i for i in result.issues if i.check == "stale-badge"]
        assert len(stale) == 1
        assert "still displays in all versions" in stale[0].message

    def test_version_note_without_version_attr_skipped(self, tmp_path):
        """::: {.version-note} without a version= attribute is skipped."""
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\n::: {.version-note}\nSome note.\n:::\n"},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert not any(i.check == "stale-callout" for i in result.issues)

    def test_deprecated_callout_without_version_attr_skipped(self, tmp_path):
        """::: {.version-deprecated} without a version= attribute is skipped."""
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            {"page.qmd": "---\ntitle: T\n---\n\n::: {.version-deprecated}\nUse new().\n:::\n"},
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert not any(i.check == "stale-callout" for i in result.issues)

    def test_fresh_deprecated_callout_not_flagged(self, tmp_path):
        """Deprecated callout that is within the threshold is not reported."""
        from great_docs._lint import _check_stale_versions

        self._make_project(
            tmp_path,
            self._versions_yaml,
            # 0.6 is only 1 release behind latest (0.7) → below threshold (4)
            {
                "page.qmd": (
                    "---\ntitle: T\n---\n\n"
                    '::: {.version-deprecated version="0.6"}\n'
                    "Use new_func().\n"
                    ":::\n"
                )
            },
        )
        result = LintResult()
        _check_stale_versions(tmp_path, result)
        assert not any(i.check == "stale-callout" for i in result.issues)


# ---------------------------------------------------------------------------
# _version_distance helper
# ---------------------------------------------------------------------------


class TestVersionDistance:
    """Tests for the _version_distance() helper."""

    def _entry(self, tag: str, prerelease: bool = False):
        from great_docs._versioning import VersionEntry

        return VersionEntry(tag=tag, label=tag, prerelease=prerelease)

    def test_returns_none_for_unknown_version(self):
        versions = [self._entry("0.3"), self._entry("0.2"), self._entry("0.1")]
        result = _version_distance("unknown", versions[0], versions)
        assert result is None

    def test_returns_none_when_badge_version_is_prerelease(self):
        """Prerelease entry not in non_pre list → badge_idx stays None."""
        dev = self._entry("dev", prerelease=True)
        v03 = self._entry("0.3")
        v01 = self._entry("0.1")
        versions = [dev, v03, v01]
        result = _version_distance("dev", v03, versions)
        assert result is None


# ---------------------------------------------------------------------------
# _extract_frontmatter_upcoming helper
# ---------------------------------------------------------------------------


class TestExtractFrontmatterUpcoming:
    """Tests for the _extract_frontmatter_upcoming() helper."""

    def test_returns_none_when_no_frontmatter(self):
        result = _extract_frontmatter_upcoming("# Just content\nNo frontmatter here.")
        assert result is None

    def test_returns_none_when_no_upcoming_key(self):
        content = "---\ntitle: My Page\n---\n\nContent here."
        result = _extract_frontmatter_upcoming(content)
        assert result is None

    def test_returns_upcoming_value(self):
        content = '---\ntitle: My Page\nupcoming: "0.9"\n---\n\nContent here.'
        result = _extract_frontmatter_upcoming(content)
        assert result == "0.9"
