"""
gdtest_display_funding — Funding with all fields.

Dimensions: K13
Focus: Funding config with name, roles, homepage, and ror fields.
"""

SPEC = {
    "name": "gdtest_display_funding",
    "description": "Funding with all fields.",
    "dimensions": ["K13"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-v2-display-funding",
            "version": "0.1.0",
            "description": "Test funding config with all fields.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "funding": {
            "name": "National Science Foundation",
            "roles": ["Funder", "Copyright holder"],
            "homepage": "https://nsf.gov",
            "ror": "https://ror.org/021nxhr62",
        },
    },
    "files": {
        "gdtest_display_funding/__init__.py": '''\
            """Package testing funding config with all fields."""

            __all__ = ["fund", "report"]


            def fund(project: str, amount: float) -> dict:
                """Record funding for a project.

                Parameters
                ----------
                project : str
                    The name of the project to fund.
                amount : float
                    The funding amount in dollars.

                Returns
                -------
                dict
                    A dictionary with funding details.

                Examples
                --------
                >>> fund("research", 50000.0)
                {'project': 'research', 'amount': 50000.0}
                """
                return {"project": project, "amount": amount}


            def report(grant_id: str) -> str:
                """Generate a funding report for a grant.

                Parameters
                ----------
                grant_id : str
                    The identifier of the grant.

                Returns
                -------
                str
                    A formatted funding report.

                Examples
                --------
                >>> report("NSF-001")
                'Grant NSF-001: active'
                """
                return f"Grant {grant_id}: active"
        ''',
        "README.md": ("# gdtest-v2-display-funding\n\nTest funding config with all fields.\n"),
    },
    "expected": {
        "detected_name": "gdtest-v2-display-funding",
        "detected_module": "gdtest_display_funding",
        "detected_parser": "numpy",
        "export_names": ["fund", "report"],
        "num_exports": 2,
    },
}
