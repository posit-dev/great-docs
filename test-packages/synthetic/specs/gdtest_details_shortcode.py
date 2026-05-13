"""
gdtest_details_shortcode — Exercise the details fenced-div extension in many contexts.

Dimensions: A1, B1, C4, D2, E6, F1, G1, H7
Focus: The collapsible details extension using ::: {.details} fenced divs with
       every supported option: basic expand/collapse, open-by-default, Lucide
       icon prefixes, callout-type variants (note, warning, tip, danger),
       accordion groups, nesting, and use in mixed content (lists, callouts,
       tables, prose).  Tests that all variants render correctly in light and
       dark mode with smooth animations and proper ARIA attributes.
"""

SPEC = {
    "name": "gdtest_details_shortcode",
    "description": "Collapsible details extension with types, icons, accordion, nesting",
    "dimensions": ["A1", "B1", "C4", "D2", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-details-shortcode",
            "version": "1.0.0",
            "description": "A package demonstrating the details fenced-div extension",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal) ──────────────────────────────────────
        "gdtest_details_shortcode/__init__.py": (
            '"""Collapsible details extension demo package."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["render", "transform"]\n'
            "\n"
            "\n"
            "def render(template: str) -> str:\n"
            '    """Render a template string.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    template\n"
            "        The template to render.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        Rendered output.\n"
            '    """\n'
            "    return template\n"
            "\n"
            "\n"
            "def transform(data: list) -> list:\n"
            '    """Transform a data list.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    data\n"
            "        Input data.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    list\n"
            "        Transformed data.\n"
            '    """\n'
            "    return data\n"
        ),
        # ── User guide page 1: Basic usage ───────────────────────────────
        "user_guide/01-basic-usage.qmd": (
            "---\n"
            "title: Basic Usage\n"
            "---\n"
            "\n"
            "The `::: {.details}` fenced div creates enhanced collapsible\n"
            "sections with smooth animation and accessible markup.\n"
            "\n"
            "## Simple Collapsible\n"
            "\n"
            "A basic collapsible section with a title:\n"
            "\n"
            '::: {.details summary="Click to expand"}\n'
            "This content is hidden by default. Click the summary bar above\n"
            "to reveal it.\n"
            "\n"
            "You can include **bold**, *italic*, and `code` formatting.\n"
            ":::\n"
            "\n"
            "## Default Title\n"
            "\n"
            "Omitting the summary gives a default label:\n"
            "\n"
            "::: {.details}\n"
            "Content with the default summary text.\n"
            ":::\n"
            "\n"
            "## Open by Default\n"
            "\n"
            "Add the `.open` class to start expanded:\n"
            "\n"
            '::: {.details .open summary="Already expanded"}\n'
            "This section is visible when the page loads. The reader can\n"
            "still click the summary bar to collapse it.\n"
            ":::\n"
            "\n"
            "## Multiple Sections\n"
            "\n"
            "Several collapsible sections in sequence:\n"
            "\n"
            '::: {.details summary="Section One"}\n'
            "Content for the first section.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Section Two"}\n'
            "Content for the second section.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Section Three"}\n'
            "Content for the third section.\n"
            ":::\n"
        ),
        # ── User guide page 2: Callout types ─────────────────────────────
        "user_guide/02-callout-types.qmd": (
            "---\n"
            "title: Callout Types\n"
            "---\n"
            "\n"
            "The `type` attribute styles the details section like a\n"
            "Quarto callout — with matching colors and a default icon.\n"
            "\n"
            "## Note\n"
            "\n"
            'A note-styled collapsible section (`type="note"`):\n'
            "\n"
            '::: {.details summary="Additional Information" type="note"}\n'
            "This uses the note color scheme (blue) and automatically\n"
            "includes the info icon.\n"
            "\n"
            "Notes are good for supplementary information that most\n"
            "readers can skip.\n"
            ":::\n"
            "\n"
            "## Warning\n"
            "\n"
            'A warning-styled section (`type="warning"`):\n'
            "\n"
            '::: {.details summary="Potential Issues" type="warning"}\n'
            "This uses the warning color scheme (amber) with the\n"
            "triangle-alert icon.\n"
            "\n"
            "Use warnings for gotchas, common mistakes, or things\n"
            "that could go wrong.\n"
            ":::\n"
            "\n"
            "## Tip\n"
            "\n"
            'A tip-styled section (`type="tip"`):\n'
            "\n"
            '::: {.details summary="Pro Tip" type="tip"}\n'
            "This uses the tip color scheme (green) with the\n"
            "lightbulb icon.\n"
            "\n"
            "Tips are great for best practices and helpful advice.\n"
            ":::\n"
            "\n"
            "## Danger\n"
            "\n"
            'A danger-styled section (`type="danger"`):\n'
            "\n"
            '::: {.details summary="Breaking Changes" type="danger"}\n'
            "This uses the danger color scheme (red) with the\n"
            "circle-alert icon.\n"
            "\n"
            "Use danger for destructive operations, breaking changes,\n"
            "or irreversible actions.\n"
            ":::\n"
            "\n"
            "## All Types Together\n"
            "\n"
            "Comparing all four types side by side:\n"
            "\n"
            '::: {.details summary="Note type" type="note"}\n'
            "Blue theme with info icon.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Warning type" type="warning"}\n'
            "Amber theme with alert icon.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Tip type" type="tip"}\n'
            "Green theme with lightbulb icon.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Danger type" type="danger"}\n'
            "Red theme with circle-alert icon.\n"
            ":::\n"
        ),
        # ── User guide page 3: Icons ─────────────────────────────────────
        "user_guide/03-icons.qmd": (
            "---\n"
            "title: Icons\n"
            "---\n"
            "\n"
            "Add a Lucide icon before the summary text with the `icon`\n"
            "attribute.\n"
            "\n"
            "## Custom Icons\n"
            "\n"
            "Any Lucide icon name works:\n"
            "\n"
            '::: {.details summary="Configuration" icon="settings"}\n'
            "Settings and configuration options for the project.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Source Code" icon="code"}\n'
            "View the implementation details.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Download Options" icon="download"}\n'
            "Available download formats and mirrors.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Performance Notes" icon="zap"}\n'
            "Benchmarks and optimization tips.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Security Advisory" icon="shield"}\n'
            "Important security information.\n"
            ":::\n"
            "\n"
            "## Icon with Type\n"
            "\n"
            "When a `type` is set, the default icon for that type is used\n"
            "automatically. You can override it with a custom icon:\n"
            "\n"
            '::: {.details summary="Default note icon" type="note"}\n'
            "Uses the default info icon for notes.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Custom note icon" type="note" icon="book-open"}\n'
            "Overrides the note icon with book-open.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Custom warning icon" type="warning" icon="flame"}\n'
            "Overrides the warning icon with flame.\n"
            ":::\n"
        ),
        # ── User guide page 4: Accordion groups ──────────────────────────
        "user_guide/04-accordion-groups.qmd": (
            "---\n"
            "title: Accordion Groups\n"
            "---\n"
            "\n"
            'Use `group="name"` to create accordion behavior — only one\n'
            "section in the group can be open at a time.\n"
            "\n"
            "## FAQ Accordion\n"
            "\n"
            "Click one section and the others close automatically:\n"
            "\n"
            '::: {.details summary="What is Great Docs?" group="faq"}\n'
            "Great Docs is a documentation site generator for Python\n"
            "packages. It builds beautiful, searchable API reference\n"
            "sites from your docstrings.\n"
            ":::\n"
            "\n"
            '::: {.details summary="How do I install it?" group="faq"}\n'
            "Install with pip:\n"
            "\n"
            "```bash\n"
            "pip install great-docs\n"
            "```\n"
            "\n"
            "Or with uv:\n"
            "\n"
            "```bash\n"
            "uv add great-docs\n"
            "```\n"
            ":::\n"
            "\n"
            '::: {.details summary="What Python versions are supported?" group="faq"}\n'
            "Great Docs supports Python 3.9 and later.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Is it free?" group="faq"}\n'
            "Yes! Great Docs is open source under the MIT license.\n"
            ":::\n"
            "\n"
            "## Multiple Groups\n"
            "\n"
            "Different groups operate independently. Sections in the\n"
            '"install" group don\'t affect the "config" group.\n'
            "\n"
            "**Installation options:**\n"
            "\n"
            '::: {.details summary="pip" group="install"}\n'
            "```bash\n"
            "pip install great-docs\n"
            "```\n"
            ":::\n"
            "\n"
            '::: {.details summary="conda" group="install"}\n'
            "```bash\n"
            "conda install great-docs\n"
            "```\n"
            ":::\n"
            "\n"
            '::: {.details summary="uv" group="install"}\n'
            "```bash\n"
            "uv add great-docs\n"
            "```\n"
            ":::\n"
            "\n"
            "**Configuration files:**\n"
            "\n"
            '::: {.details summary="great-docs.yml" group="config"}\n'
            "The main configuration file for your documentation site.\n"
            ":::\n"
            "\n"
            '::: {.details summary="pyproject.toml" group="config"}\n'
            "Package metadata is read from pyproject.toml automatically.\n"
            ":::\n"
            "\n"
            '::: {.details summary="_quarto.yml" group="config"}\n'
            "Quarto configuration is generated automatically by Great Docs.\n"
            ":::\n"
        ),
        # ── User guide page 5: Nesting ───────────────────────────────────
        "user_guide/05-nesting.qmd": (
            "---\n"
            "title: Nesting\n"
            "---\n"
            "\n"
            "Details sections can be nested inside each other for\n"
            "hierarchical content. Use more colons for nested fences.\n"
            "\n"
            "## Two Levels Deep\n"
            "\n"
            ':::: {.details summary="Outer Section"}\n'
            "This is the outer content.\n"
            "\n"
            '::: {.details summary="Inner Section"}\n'
            "This is nested inside the outer section.\n"
            ":::\n"
            "\n"
            "More outer content after the nested section.\n"
            "::::\n"
            "\n"
            "## Nested with Types\n"
            "\n"
            ':::: {.details summary="Main Topic" type="note"}\n'
            "An overview of the main topic.\n"
            "\n"
            '::: {.details summary="Important caveat" type="warning"}\n'
            "Watch out for this edge case when using the feature.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Helpful hint" type="tip"}\n'
            "Here is a useful tip related to this topic.\n"
            ":::\n"
            "::::\n"
            "\n"
            "## Three Levels Deep\n"
            "\n"
            '::::: {.details summary="Level 1"}\n'
            "First level of nesting.\n"
            "\n"
            ':::: {.details summary="Level 2"}\n'
            "Second level of nesting.\n"
            "\n"
            '::: {.details summary="Level 3"}\n'
            "Third level — the deepest.\n"
            ":::\n"
            "::::\n"
            ":::::\n"
        ),
        # ── User guide page 6: Rich content ──────────────────────────────
        "user_guide/06-rich-content.qmd": (
            "---\n"
            "title: Rich Content\n"
            "---\n"
            "\n"
            "The body of a details section supports full Markdown.\n"
            "\n"
            "## Code Blocks\n"
            "\n"
            '::: {.details summary="Python Example" icon="code"}\n'
            "```python\n"
            "import great_docs\n"
            "\n"
            "site = great_docs.build(\n"
            '    package="my-package",\n'
            '    theme="sky",\n'
            ")\n"
            "site.serve()\n"
            "```\n"
            ":::\n"
            "\n"
            '::: {.details summary="Shell Commands" icon="terminal"}\n'
            "```bash\n"
            "great-docs init my-project\n"
            "cd my-project\n"
            "great-docs build\n"
            "great-docs serve\n"
            "```\n"
            ":::\n"
            "\n"
            "## Lists\n"
            "\n"
            '::: {.details summary="Feature List"}\n'
            "Key features of the project:\n"
            "\n"
            "- Automatic API reference generation\n"
            "- Dark mode support\n"
            "- Gradient theme presets\n"
            "- Version badge system\n"
            "- Keyboard navigation\n"
            ":::\n"
            "\n"
            '::: {.details summary="Numbered Steps"}\n'
            "1. Install the package\n"
            "2. Run `great-docs init`\n"
            "3. Edit `great-docs.yml`\n"
            "4. Run `great-docs build`\n"
            "5. Deploy to GitHub Pages\n"
            ":::\n"
            "\n"
            "## Tables\n"
            "\n"
            '::: {.details summary="Comparison Table" icon="table"}\n'
            "| Feature | Free | Pro |\n"
            "|---------|------|-----|\n"
            "| API Reference | Yes | Yes |\n"
            "| Dark Mode | Yes | Yes |\n"
            "| Custom Themes | No | Yes |\n"
            "| Priority Support | No | Yes |\n"
            ":::\n"
            "\n"
            "## Blockquotes\n"
            "\n"
            '::: {.details summary="Notable Quotes"}\n'
            "> Documentation is a love letter that you write to your\n"
            "> future self.\n"
            ">\n"
            "> — Damian Conway\n"
            ":::\n"
            "\n"
            "## Mixed Content\n"
            "\n"
            '::: {.details summary="Full Example" type="tip" icon="book-open"}\n'
            "Here is a complete example combining multiple elements:\n"
            "\n"
            "**Step 1:** Install the package:\n"
            "\n"
            "```bash\n"
            "pip install great-docs\n"
            "```\n"
            "\n"
            "**Step 2:** Create the configuration:\n"
            "\n"
            "| Setting | Value |\n"
            "|---------|-------|\n"
            '| theme | "sky" |\n'
            '| parser | "numpy" |\n'
            "\n"
            "**Step 3:** Build and verify:\n"
            "\n"
            "```bash\n"
            "great-docs build\n"
            "great-docs serve\n"
            "```\n"
            "\n"
            "> The site should be available at `http://localhost:8080`.\n"
            ":::\n"
        ),
        # ── User guide page 7: Combinations ──────────────────────────────
        "user_guide/07-combinations.qmd": (
            "---\n"
            "title: Combinations\n"
            "---\n"
            "\n"
            "Combining multiple options together for real-world use cases.\n"
            "\n"
            "## Typed Accordion\n"
            "\n"
            "An accordion group where each section has a different type:\n"
            "\n"
            '::: {.details .open summary="Overview" type="note" group="typed-acc"}\n'
            "Start with a high-level overview of the feature.\n"
            "This section is open by default.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Known Issues" type="warning" group="typed-acc"}\n'
            "Current limitations and known bugs.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Best Practices" type="tip" group="typed-acc"}\n'
            "Recommended approaches for common use cases.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Migration Guide" type="danger" group="typed-acc"}\n'
            "Breaking changes when upgrading from v1 to v2.\n"
            ":::\n"
            "\n"
            "## Icon + Type + Open\n"
            "\n"
            '::: {.details .open summary="Release Notes" type="note" icon="rocket"}\n'
            "Version 2.0 brings major improvements:\n"
            "\n"
            "- Faster build times\n"
            "- New gradient presets\n"
            "- Improved dark mode\n"
            ":::\n"
            "\n"
            "## Accordion with Icons\n"
            "\n"
            '::: {.details summary="Getting Started" icon="rocket" group="guide"}\n'
            "Quick start instructions for new users.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Configuration" icon="settings" group="guide"}\n'
            "Detailed configuration reference.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Deployment" icon="cloud" group="guide"}\n'
            "Deploy your site to GitHub Pages, Netlify, or Vercel.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Troubleshooting" icon="wrench" group="guide"}\n'
            "Common issues and their solutions.\n"
            ":::\n"
            "\n"
            "## Gradient Theme\n"
            "\n"
            "The `gradient` type uses your site's animated theme gradient on\n"
            "the summary bar and a subdued tint in the body:\n"
            "\n"
            '::: {.details summary="Animated Gradient" type="gradient"}\n'
            "This details section uses the site's accent gradient colors\n"
            "with a smooth shifting animation.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Gradient (open)" type="gradient" icon="sparkles"}\n'
            "A gradient section that starts expanded, with a custom icon.\n"
            "\n"
            "- The summary bar has a vivid animated gradient\n"
            "- The body has a subtle, subdued version\n"
            "- Respects dark mode automatically\n"
            ":::\n"
            "\n"
            '::: {.details summary="Gradient Accordion A" type="gradient" group="grad-acc"}\n'
            "First gradient accordion panel.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Gradient Accordion B" type="gradient" group="grad-acc"}\n'
            "Second gradient accordion panel.\n"
            ":::\n"
            "\n"
            "## Nested Accordion\n"
            "\n"
            "An outer accordion with nested content:\n"
            "\n"
            ':::: {.details summary="Frontend" group="stack"}\n'
            "Frontend technologies used:\n"
            "\n"
            '::: {.details summary="HTML/CSS"}\n'
            "Quarto generates semantic HTML with SCSS theming.\n"
            ":::\n"
            "\n"
            '::: {.details summary="JavaScript"}\n'
            "Custom JS for interactive features like accordion groups,\n"
            "dark mode toggle, and keyboard navigation.\n"
            ":::\n"
            "::::\n"
            "\n"
            ':::: {.details summary="Backend" group="stack"}\n'
            "Backend technologies used:\n"
            "\n"
            '::: {.details summary="Python"}\n'
            "Core logic for parsing, rendering, and configuration.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Lua"}\n'
            "Quarto shortcode extensions for custom components.\n"
            ":::\n"
            "::::\n"
        ),
        # ── User guide page 8: Gradient themes ───────────────────────────
        "user_guide/08-gradient-themes.qmd": (
            "---\n"
            "title: Gradient Themes\n"
            "---\n"
            "\n"
            "Each gradient preset from the Great Docs theme system is\n"
            'available as a details variant using `gradient="name"`.\n'
            "\n"
            "## Sky\n"
            "\n"
            '::: {.details summary="Sky gradient" gradient="sky"}\n'
            "Soft sky blues — inspired by clear horizons.\n"
            "\n"
            "The animated gradient shifts smoothly through four\n"
            "related hues, creating a gentle sense of motion.\n"
            ":::\n"
            "\n"
            "## Peach\n"
            "\n"
            '::: {.details summary="Peach gradient" gradient="peach"}\n'
            "Warm peach and blush tones — friendly and inviting.\n"
            "\n"
            "Works well for introductory or welcoming content.\n"
            ":::\n"
            "\n"
            "## Prism\n"
            "\n"
            '::: {.details summary="Prism gradient" gradient="prism"}\n'
            "Mint, sky, and lavender — a multi-spectral blend.\n"
            "\n"
            "Great for highlighting creative or multi-faceted topics.\n"
            ":::\n"
            "\n"
            "## Lilac\n"
            "\n"
            '::: {.details summary="Lilac gradient" gradient="lilac"}\n'
            "Lilac and pink — soft and elegant.\n"
            "\n"
            "A refined choice for design-related documentation.\n"
            ":::\n"
            "\n"
            "## Slate\n"
            "\n"
            '::: {.details summary="Slate gradient" gradient="slate"}\n'
            "Cool grays — understated and professional.\n"
            "\n"
            "Ideal for technical or enterprise documentation.\n"
            ":::\n"
            "\n"
            "## Honey\n"
            "\n"
            '::: {.details summary="Honey gradient" gradient="honey"}\n'
            "Warm cream and apricot — rich and earthy.\n"
            "\n"
            "A natural choice for warm, approachable content.\n"
            ":::\n"
            "\n"
            "## Dusk\n"
            "\n"
            '::: {.details summary="Dusk gradient" gradient="dusk"}\n'
            "Soft lavender-blue — twilight serenity.\n"
            "\n"
            "Evokes calm and focus, perfect for deep-dive content.\n"
            ":::\n"
            "\n"
            "## Mint\n"
            "\n"
            '::: {.details summary="Mint gradient" gradient="mint"}\n'
            "Pale aqua — fresh and clean.\n"
            "\n"
            "A crisp option for health, environment, or refreshing topics.\n"
            ":::\n"
            "\n"
            "## All Presets in Sequence\n"
            "\n"
            "Every preset shown together for comparison:\n"
            "\n"
            '::: {.details .open summary="Sky" gradient="sky"}\n'
            "Light: soft sky blues. Dark: deep ocean.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Peach" gradient="peach"}\n'
            "Light: peach and blush. Dark: warm embers.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Prism" gradient="prism"}\n'
            "Light: mint, sky, lavender. Dark: deep jewel tones.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Lilac" gradient="lilac"}\n'
            "Light: lilac and pink. Dark: deep violet.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Slate" gradient="slate"}\n'
            "Light: cool grays. Dark: charcoal depths.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Honey" gradient="honey"}\n'
            "Light: warm cream. Dark: molten amber.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Dusk" gradient="dusk"}\n'
            "Light: soft lavender. Dark: midnight indigo.\n"
            ":::\n"
            "\n"
            '::: {.details .open summary="Mint" gradient="mint"}\n'
            "Light: pale aqua. Dark: deep teal.\n"
            ":::\n"
            "\n"
            "## Gradient Preset Accordion\n"
            "\n"
            "Same presets in accordion mode:\n"
            "\n"
            '::: {.details summary="Sky" gradient="sky" group="presets"}\n'
            "Soft sky blues with animated shimmer.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Peach" gradient="peach" group="presets"}\n'
            "Warm peach and blush tones.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Prism" gradient="prism" group="presets"}\n'
            "Multi-spectral mint, sky, and lavender.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Lilac" gradient="lilac" group="presets"}\n'
            "Elegant lilac and pink.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Slate" gradient="slate" group="presets"}\n'
            "Understated cool grays.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Honey" gradient="honey" group="presets"}\n'
            "Rich cream and apricot.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Dusk" gradient="dusk" group="presets"}\n'
            "Twilight lavender-blue.\n"
            ":::\n"
            "\n"
            '::: {.details summary="Mint" gradient="mint" group="presets"}\n'
            "Fresh pale aqua.\n"
            ":::\n"
            "\n"
            "## Gleam Border Effect\n"
            "\n"
            "Add `.gleam` to give the details frame a traveling light\n"
            "that sweeps around the border:\n"
            "\n"
            '::: {.details .gleam summary="Default gleam"}\n'
            "A subtle light traces the border continuously.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Gleam + Note" type="note"}\n'
            "The gleam color matches the note type (blue).\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Gleam + Tip" type="tip"}\n'
            "The gleam color matches the tip type (green).\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Gleam + Warning" type="warning"}\n'
            "The gleam color matches the warning type (amber).\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Gleam + Danger" type="danger"}\n'
            "The gleam color matches the danger type (red).\n"
            ":::\n"
            "\n"
            "## Gleam + Gradient Presets\n"
            "\n"
            "Combining the gleam border with gradient backgrounds:\n"
            "\n"
            '::: {.details .gleam summary="Sky gleam" gradient="sky"}\n'
            "Animated sky gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Peach gleam" gradient="peach"}\n'
            "Warm peach gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Prism gleam" gradient="prism"}\n'
            "Multi-spectral gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Lilac gleam" gradient="lilac"}\n'
            "Elegant lilac gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Dusk gleam" gradient="dusk"}\n'
            "Twilight gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            '::: {.details .gleam summary="Mint gleam" gradient="mint"}\n'
            "Fresh aqua gradient with a matching gleam border.\n"
            ":::\n"
            "\n"
            "## Gleam + Theme Gradient\n"
            "\n"
            '::: {.details .gleam .open summary="Theme accent gleam" type="gradient"}\n'
            "Uses the site accent colors for both the animated gradient\n"
            "background and the gleam border effect.\n"
            ":::\n"
        ),
        # ── README ───────────────────────────────────────────────────────
        "README.md": (
            "# gdtest-details-shortcode\n"
            "\n"
            "A synthetic test package that exercises the `::: {.details}`\n"
            "fenced-div extension with every supported option: basic usage,\n"
            "callout types, Lucide icons, accordion groups, nesting,\n"
            "rich markdown content, and combined parameters.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-details-shortcode",
        "detected_module": "gdtest_details_shortcode",
        "detected_parser": "numpy",
        "export_names": ["render", "transform"],
        "num_exports": 2,
        "has_user_guide": True,
        "user_guide_files": [
            "01-basic-usage.qmd",
            "02-callout-types.qmd",
            "03-icons.qmd",
            "04-accordion-groups.qmd",
            "05-nesting.qmd",
            "06-rich-content.qmd",
            "07-combinations.qmd",
            "08-gradient-themes.qmd",
        ],
        "files_contain": {
            "great-docs/_site/user-guide/basic-usage.html": [
                "gd-details",
                "gd-details-summary",
                "gd-details-body",
                "gd-details-chevron",
            ],
            "great-docs/_site/user-guide/callout-types.html": [
                "gd-details--note",
                "gd-details--warning",
                "gd-details--tip",
                "gd-details--danger",
            ],
            "great-docs/_site/user-guide/icons.html": [
                "gd-details-icon-wrap",
                "gd-details",
            ],
            "great-docs/_site/user-guide/accordion-groups.html": [
                'data-gd-group="faq"',
                'data-gd-group="install"',
                'data-gd-group="config"',
            ],
            "great-docs/_site/user-guide/nesting.html": [
                "gd-details",
                "gd-details--note",
                "gd-details--warning",
                "gd-details--tip",
            ],
            "great-docs/_site/user-guide/rich-content.html": [
                "gd-details",
                "gd-details-body",
            ],
            "great-docs/_site/user-guide/combinations.html": [
                "gd-details",
                'data-gd-group="typed-acc"',
                'data-gd-group="guide"',
                'data-gd-group="stack"',
                "gd-details--gradient",
            ],
            "great-docs/_site/user-guide/gradient-themes.html": [
                "gd-details--gradient-sky",
                "gd-details--gradient-peach",
                "gd-details--gradient-prism",
                "gd-details--gradient-lilac",
                "gd-details--gradient-slate",
                "gd-details--gradient-honey",
                "gd-details--gradient-dusk",
                "gd-details--gradient-mint",
                'data-gd-group="presets"',
                "gd-details--gleam",
            ],
        },
        "coverage_exclude": ["nodoc", "bigcl", "supp", "sechdg", "sbsec", "hdg"],
    },
}
