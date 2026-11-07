Pages served to `webmcp.js` by `tests/js/webmcp_harness.js` in `tests/test_webmcp_runtime.py`.
Each `.md` file stands for the Markdown copy that the site writes beside a page's `.html`, and
`search.json` for Quarto's search index. The tests copy this directory and add the rest of a
built site: HTML pages, `objects.inv` and `gd-webmcp.json`, written by the manifest writer.
