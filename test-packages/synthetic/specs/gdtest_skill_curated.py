"""
gdtest_skill_curated — Tests curated skill from skills/<name>/SKILL.md.

Dimensions: S2
Focus: Developer-written SKILL.md in the skills/ directory. Great Docs
       should detect and use the curated skill instead of auto-generating.
       The skills.qmd page should render the curated content with proper
       headings, tables, and code blocks.
"""

SPEC = {
    "name": "gdtest_skill_curated",
    "description": "Tests curated skill from skills/<name>/SKILL.md directory",
    "dimensions": ["S2"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-curated",
            "version": "0.1.0",
            "description": "A package with a hand-crafted Agent Skill",
            "license": "MIT",
            "requires-python": ">=3.10",
            "urls": {
                "Repository": "https://github.com/test-org/gdtest-skill-curated",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_skill_curated/__init__.py": '''\
            """A package with a curated Agent Skill."""

            __version__ = "0.1.0"
            __all__ = ["fetch", "parse", "CacheStore"]


            class CacheStore:
                """
                A simple in-memory cache.

                Parameters
                ----------
                max_size
                    Maximum number of entries.
                ttl
                    Time-to-live in seconds.
                """

                def __init__(self, max_size: int = 100, ttl: int = 3600):
                    self.max_size = max_size
                    self.ttl = ttl
                    self._store: dict = {}

                def get(self, key: str) -> object | None:
                    """
                    Retrieve a cached value.

                    Parameters
                    ----------
                    key
                        The cache key.

                    Returns
                    -------
                    object or None
                        The cached value, or None if not found.
                    """
                    return self._store.get(key)

                def set(self, key: str, value: object) -> None:
                    """
                    Store a value in the cache.

                    Parameters
                    ----------
                    key
                        The cache key.
                    value
                        The value to cache.
                    """
                    self._store[key] = value


            def fetch(url: str, timeout: int = 30) -> str:
                """
                Fetch content from a URL.

                Parameters
                ----------
                url
                    The URL to fetch.
                timeout
                    Request timeout in seconds.

                Returns
                -------
                str
                    The response body.
                """
                return f"<content from {url}>"


            def parse(html: str, selector: str = "body") -> list[str]:
                """
                Parse HTML and extract text matching a CSS selector.

                Parameters
                ----------
                html
                    Raw HTML string.
                selector
                    CSS selector to match.

                Returns
                -------
                list of str
                    Extracted text fragments.
                """
                return [html[:50]]
        ''',
        # Curated skill file in the standard Agent Skills directory layout
        "skills/gdtest-skill-curated/SKILL.md": """\
            ---
            name: gdtest-skill-curated
            description: >
              Fetch, parse, and cache web content with gdtest-skill-curated.
              Use when writing Python code that fetches URLs, parses HTML,
              or needs in-memory caching.
            license: MIT
            compatibility: Requires Python >=3.10.
            metadata:
              author: gdg-test-suite
              version: "1.0"
            ---

            # gdtest-skill-curated

            A lightweight toolkit for fetching, parsing, and caching web content.

            ## Installation

            ```bash
            pip install gdtest-skill-curated
            ```

            ## When to use what

            | Need | Use |
            |------|-----|
            | Fetch a URL | `fetch(url)` |
            | Parse HTML content | `parse(html, selector)` |
            | Cache results in memory | `CacheStore()` |
            | Set cache TTL | `CacheStore(ttl=seconds)` |
            | Limit cache size | `CacheStore(max_size=n)` |

            ## Gotchas

            1. **Always set a timeout** when calling `fetch()` — the default is
               30 seconds, which may be too long for interactive use.
            2. **`parse()` returns a list**, not a string. Even for a single
               match you get a one-element list.
            3. **`CacheStore` is not thread-safe.** Use a lock if sharing across
               threads.
            4. The module name is `gdtest_skill_curated`, not
               `gdtest-skill-curated`.

            ## Capabilities and boundaries

            **What agents can configure:**

            - Fetch URLs with custom timeouts
            - Parse HTML with CSS selectors
            - Create and query in-memory caches
            - Set TTL and max size on caches

            **Requires human setup:**

            - Network access for `fetch()`
            - Installing the package (`pip install`)

            ## Resources

            - [llms.txt](llms.txt) — Indexed API reference for LLMs
            - [llms-full.txt](llms-full.txt) — Full documentation for LLMs
        """,
        "README.md": """\
            # gdtest-skill-curated

            A package with a hand-crafted Agent Skill for testing Great Docs
            curated skill detection.

            ## Installation

            ```bash
            pip install gdtest-skill-curated
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-curated",
        "detected_module": "gdtest_skill_curated",
        "detected_parser": "numpy",
        "export_names": ["fetch", "parse", "CacheStore"],
        "num_exports": 3,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_curated": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
