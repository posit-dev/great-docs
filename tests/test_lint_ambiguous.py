from great_docs._lint import LintResult, _check_ambiguous_references


def test_a_reference_to_an_ambiguous_short_name_is_an_error():
    result = LintResult()

    _check_ambiguous_references(
        claims=[("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")],
        documented_names={"demo.store.Cache", "demo.net.Cache"},
        prose={"demo.store.Cache": "See [](`Cache`) for details."},
        result=result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].check == "ambiguous-xref"
    assert result.issues[0].severity == "error"
    assert "demo.net.Cache" in result.issues[0].message
    assert "demo.store.Cache" in result.issues[0].message


def test_an_unreferenced_collision_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        claims=[("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")],
        documented_names=set(),
        prose={"demo.store.Cache": "No references here."},
        result=result,
    )

    assert result.issues == []


def test_a_reference_to_an_unambiguous_short_name_is_not_reported():
    result = LintResult()

    _check_ambiguous_references(
        claims=[("Thing", "demo.Thing")],
        documented_names={"demo.Thing"},
        prose={"demo.Thing": "See [](`Thing`)."},
        result=result,
    )

    assert result.issues == []


def test_the_shortening_marker_is_ignored_when_matching():
    result = LintResult()

    _check_ambiguous_references(
        claims=[("Cache", "demo.store.Cache"), ("Cache", "demo.net.Cache")],
        documented_names=set(),
        prose={"guide.qmd": "See [](`~Cache`)."},
        result=result,
    )

    assert len(result.issues) == 1
    assert result.issues[0].symbol == "guide.qmd"
