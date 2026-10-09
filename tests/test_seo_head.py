"""
Insertion of tags into the `<head>` of raw pages
"""

from great_docs._website.seo import head


def test_inserts_before_the_closing_head():
    page = head.insert("<head><title>T</title></head>", "<meta a>", unless="<meta a")
    assert page == "<head><title>T</title><meta a>\n</head>"


def test_leaves_a_page_that_has_the_marker():
    html = "<head><meta a></head>"
    assert head.insert(html, "<meta a>", unless="<meta a") == html


def test_leaves_a_page_without_a_head():
    assert head.insert("<div></div>", "<meta a>", unless="<meta a") == "<div></div>"
