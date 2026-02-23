"""
gdtest_display_authors — Authors with full metadata.

Dimensions: K14
Focus: Authors config with name, email, role, and github fields for multiple authors.
"""

SPEC = {
    "name": "gdtest_display_authors",
    "description": "Authors with full metadata.",
    "dimensions": ["K14"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-display-authors",
            "version": "0.1.0",
            "description": "Test authors config with full metadata.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "authors": [
            {
                "name": "Dr. Jane Doe",
                "email": "jane@university.edu",
                "role": "Principal Investigator",
                "github": "janedoe",
            },
            {
                "name": "John Smith",
                "email": "john@lab.org",
                "role": "Lead Developer",
                "github": "jsmith",
            },
        ],
    },
    "files": {
        "gdtest_display_authors/__init__.py": '''\
            """Package testing authors config with full metadata."""

            __all__ = ["research", "publish"]


            def research(topic: str) -> dict:
                """Conduct research on a given topic.

                Parameters
                ----------
                topic : str
                    The research topic.

                Returns
                -------
                dict
                    A dictionary with research findings.

                Examples
                --------
                >>> research("machine learning")
                {'topic': 'machine learning', 'status': 'complete'}
                """
                return {"topic": topic, "status": "complete"}


            def publish(paper: dict) -> str:
                """Publish a research paper.

                Parameters
                ----------
                paper : dict
                    A dictionary describing the paper to publish.

                Returns
                -------
                str
                    The DOI of the published paper.

                Examples
                --------
                >>> publish({"title": "AI Research"})
                'doi:10.1234/ai-research'
                """
                return f"doi:10.1234/{paper.get('title', 'unknown').lower().replace(' ', '-')}"
        ''',
        "README.md": ("# gdtest-v2-display-authors\n\nTest authors config with full metadata.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-display-authors",
        "detected_module": "gdtest_display_authors",
        "detected_parser": "numpy",
        "export_names": ["publish", "research"],
        "num_exports": 2,
    },
}
