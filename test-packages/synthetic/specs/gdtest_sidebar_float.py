"""
gdtest_sidebar_float — Floating sidebar stress test.

Dimensions: N10
Focus: 30+ user guide pages in multiple sections to stress-test the floating
       sidebar with scroll containment, affordances, and active-page highlighting.
"""

# ── User guide page definitions ──────────────────────────────────────────────
# Organized into sections with many pages per section to make the sidebar tall.

_SECTIONS = {
    "Getting Started": [
        ("welcome", "Welcome"),
        ("installation", "Installation"),
        ("quickstart", "Quickstart"),
        ("first-project", "First Project"),
        ("editor-setup", "Editor Setup"),
    ],
    "Core Concepts": [
        ("architecture", "Architecture"),
        ("configuration", "Configuration"),
        ("themes", "Themes"),
        ("layouts", "Layouts"),
        ("templates", "Templates"),
        ("data-sources", "Data Sources"),
        ("routing", "Routing"),
    ],
    "Advanced Usage": [
        ("plugins", "Plugins"),
        ("custom-directives", "Custom Directives"),
        ("internationalization", "Internationalization"),
        ("performance", "Performance Tuning"),
        ("caching", "Caching Strategies"),
        ("security", "Security Best Practices"),
        ("accessibility", "Accessibility"),
    ],
    "Deployment": [
        ("local-preview", "Local Preview"),
        ("static-hosting", "Static Hosting"),
        ("ci-cd", "CI/CD Pipelines"),
        ("docker", "Docker Containers"),
        ("cdn-setup", "CDN Setup"),
        ("monitoring", "Monitoring"),
    ],
    "Reference": [
        ("cli-reference", "CLI Reference"),
        ("config-reference", "Config Reference"),
        ("api-reference", "API Reference"),
        ("changelog", "Changelog"),
        ("migration-guide", "Migration Guide"),
        ("troubleshooting", "Troubleshooting"),
        ("faq", "FAQ"),
    ],
}

# Build numbered user_guide files and expected outputs
_ug_files: dict[str, str] = {}
_expected_files: list[str] = []
_counter = 1

for section_name, pages in _SECTIONS.items():
    for slug, title in pages:
        filename = f"{_counter:02d}-{slug}.qmd"
        _ug_files[f"user_guide/{filename}"] = (
            f"---\n"
            f'title: "{title}"\n'
            f"---\n"
            f"\n"
            f"## {title}\n"
            f"\n"
            f"This is the **{title}** page in the _{section_name}_ section.\n"
            f"\n"
            f"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do\n"
            f"eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim\n"
            f"ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut\n"
            f"aliquip ex ea commodo consequat.\n"
        )
        html_name = filename.replace(".qmd", ".html")
        _expected_files.append(f"great-docs/user-guide/{html_name}")
        _counter += 1


SPEC = {
    "name": "gdtest_sidebar_float",
    "description": "30+ user guide pages in 5 sections to stress-test floating sidebar.",
    "dimensions": ["N10"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-sidebar-float",
            "version": "0.1.0",
            "description": "Floating sidebar stress test with 32 user guide pages.",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "user_guide": "user_guide",
        "user_guide_sections": {
            "Getting Started": [
                "01-welcome",
                "02-installation",
                "03-quickstart",
                "04-first-project",
                "05-editor-setup",
            ],
            "Core Concepts": [
                "06-architecture",
                "07-configuration",
                "08-themes",
                "09-layouts",
                "10-templates",
                "11-data-sources",
                "12-routing",
            ],
            "Advanced Usage": [
                "13-plugins",
                "14-custom-directives",
                "15-internationalization",
                "16-performance",
                "17-caching",
                "18-security",
                "19-accessibility",
            ],
            "Deployment": [
                "20-local-preview",
                "21-static-hosting",
                "22-ci-cd",
                "23-docker",
                "24-cdn-setup",
                "25-monitoring",
            ],
            "Reference": [
                "26-cli-reference",
                "27-config-reference",
                "28-api-reference",
                "29-changelog",
                "30-migration-guide",
                "31-troubleshooting",
                "32-faq",
            ],
        },
    },
    "files": {
        "gdtest_sidebar_float/__init__.py": (
            '"""Floating sidebar test package."""\n'
            "\n"
            '__version__ = "0.1.0"\n'
            '__all__ = ["configure", "build", "deploy"]\n'
            "\n"
            "\n"
            "def configure(path: str) -> dict:\n"
            '    """Configure the project.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    path : str\n"
            "        Path to the config file.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    dict\n"
            "        Parsed configuration.\n"
            '    """\n'
            "    return {}\n"
            "\n"
            "\n"
            "def build(config: dict) -> None:\n"
            '    """Build the site from configuration.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    config : dict\n"
            "        Project configuration.\n"
            '    """\n'
            "    pass\n"
            "\n"
            "\n"
            "def deploy(target: str = 'production') -> bool:\n"
            '    """Deploy the built site.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    target : str\n"
            "        Deployment target name.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    bool\n"
            "        True if deployment succeeded.\n"
            '    """\n'
            "    return True\n"
        ),
        **_ug_files,
        "README.md": (
            "# gdtest-sidebar-float\n"
            "\n"
            "Stress test for the floating sidebar with 32 user guide pages\n"
            "organized into 5 sections.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-sidebar-float",
        "detected_module": "gdtest_sidebar_float",
        "detected_parser": "numpy",
        "export_names": ["configure", "build", "deploy"],
        "num_exports": 3,
        "files_exist": _expected_files,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "sechdg", "sbsec", "hdg"],
    },
}
