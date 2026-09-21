from great_docs._content_naming import fix_numeric_prefix_links, section_slug, strip_numeric_prefix


def test_strip_numeric_prefix_two_digit() -> None:
    assert strip_numeric_prefix("01-installation.qmd") == "installation.qmd"


def test_strip_numeric_prefix_no_prefix() -> None:
    assert strip_numeric_prefix("introduction.qmd") == "introduction.qmd"


def test_fix_numeric_prefix_links_basic() -> None:
    assert fix_numeric_prefix_links("[Config](05-configuration.qmd)") == "[Config](configuration.qmd)"


def test_section_slug_replaces_underscores_and_spaces() -> None:
    assert section_slug("My_Cool Dir") == "my-cool-dir"
