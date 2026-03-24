# Great Docs — Roadmap

## In Progress

Work that's underway or nearing completion.

### Robustness Hardening

- Continued testing against real-world packages with unusual structures (PyO3/Rust bindings, namespace packages, monorepos)
- Improving error messages for common failure modes
- Graceful degradation when griffe can't resolve aliases

---

## Planned — Near Term

High-value features that build on existing infrastructure.

### Documentation Linting

A `great-docs lint` command for documentation quality checks.

- Missing docstrings for public exports
- Broken internal cross-references
- Style-guide enforcement (consistent docstring format)
- Family/directive consistency checks
- Machine-readable JSON output for CI integration

### Harper Grammar Checker

Replace pyspellchecker with [harper](https://github.com/elijah-potter/harper), a fast local grammar checker.

- Faster checking with Rust-based tooling
- Grammar checking in addition to spelling
- Custom dictionary support (project-specific terms)
- Language server integration for interactive editing
- CI-friendly CLI via `harper-cli`
- Drop-in replacement for current `great-docs spell` command

### Mermaid Diagram Rendering

Render Mermaid.js diagrams embedded in docstrings or Markdown content.

- Auto-detect ` ```mermaid ` code blocks in README, docstrings, and user guide pages
- Render diagrams during build (static SVG or inline)
- Dark mode variant support
- Quarto's native mermaid support as the backend

### MCP Server for Documentation

Expose the rendered site as an MCP endpoint so AI agents can search and retrieve docs programmatically.

- Serve a lightweight MCP server from the `_site/` output
- `SearchDocs` tool for semantic or keyword search across pages
- Return results as Markdown for direct LLM consumption
- Integrate with the existing `llms.txt` / `llms-full.txt` pipeline
- Optional: deploy alongside the static site on GitHub Pages via a serverless function

### Social Cards & Open Graph

Auto-generate `<meta>` tags for social media previews.

- Open Graph (`og:title`, `og:description`, `og:image`) — works on LinkedIn, Discord, Slack, Bluesky, Mastodon, and most other platforms
- Twitter/X Card markup (`twitter:card`, `twitter:title`, etc.) for X-specific previews
- Per-page and site-level defaults
- Optional custom image template

### SEO Optimization

Comprehensive search engine optimization features.

- Auto-generated `sitemap.xml` with proper priorities and change frequencies
- Configurable `robots.txt` generation
- Meta descriptions from docstrings or frontmatter (`description:` field)
- Canonical URLs to prevent duplicate content issues
- Structured data (JSON-LD) for software documentation
- Page title templates with site name (`{page_title} | {site_name}`)
- `noindex` / `nofollow` controls for internal or draft pages
- `great-docs seo` CLI command to audit SEO health

### Page Metadata Timestamps

Display creation and modification dates at the bottom of main content with optional author attribution.

- Horizontal layout: `[edit icon] 4 months ago  [create icon] 2 years ago  ───  [author avatars]`
- Relative timestamps by default ("4 months ago"), configurable to absolute dates
- Git history or file metadata as date sources
- "Refreshed X ago" for auto-generated pages (reference, changelog, CLI docs)
- Hover tooltips show absolute dates
- `site.show_dates: true` config option to enable globally
- `site.date_format: "relative"` (default) or strftime pattern

### Author Attribution & Avatars

Display author information with circular GitHub-style avatars on authored pages.

- Author name and image from page YAML frontmatter (`author: {name, image, url}`)
- Circular avatar images (falls back to initials when no image)
- Author lookup from `great-docs.yml` `authors:` list for full metadata
- Only shown on authored pages (user guide, blog, recipes) with explicit `author:` frontmatter
- Auto-generated pages (reference, changelog) show dates only, no author
- Optional `team_author:` config for a catch-all team attribution (e.g., "Great Tables Team")
- `site.show_author: true/false` to enable/disable author display

### Responsive Tables

Improve table display on narrow viewports (mobile devices, split-screen windows).

- Horizontal scroll containers for wide tables
- Collapsed/stacked view for data tables
- Touch-friendly interactions
- Consistent styling with dark mode

### Enhanced Search

Improve the built-in search with modern capabilities.

- Fuzzy matching and typo tolerance
- Search suggestions and completions
- Highlighting of matched terms in results
- Keyboard navigation in search results
- Recent searches history

### Navigation Icons

Add icon support for sidebar and navbar entries.

- Prepend icons to navigation titles (`icon: book` in YAML)
- [Lucide](https://lucide.dev/) icon set (lightweight, 1500+ icons)
- SVG inlining for crisp rendering at any size
- Dark mode color adaptation
- Consistent sizing and alignment across navigation levels

---

## Planned — Medium Term

Features that expand the scope of what Great Docs can produce.

### Multi-Version Documentation

A version selector dropdown backed by versioned deployments.

- Deploy docs per release tag
- Version dropdown in the navbar
- "Outdated version" warning banners
- Inter-version linking
- Storage strategy: subdirectories (`/v1.2/`, `/latest/`) on GitHub Pages

### API Version Badges

Surface "Added in version X" and "Deprecated in version Y" badges automatically.

- Parse version annotations from docstrings or decorators
- Diff consecutive versions to detect additions, removals, signature changes
- Deprecation warning callouts in rendered docs

### API Evolution Insights

Tools for understanding how the API surface changes over time.

- Interactive dependency graph showing class inheritance and function relationships
- Version-to-version diff reports: added/removed/changed symbols
- Parameter change tracking (renamed, retyped, new defaults, removed)
- Breaking change detection and migration hints
- `great-docs api-diff v1.0 v2.0` CLI command
- Visual timeline of API surface growth

### Analytics Integration

One-line config for privacy-friendly analytics.

- Plausible Analytics (recommended default)
- Google Analytics fallback
- Opt-in cookie consent banner support

### Notebook Gallery

A gallery view for example Jupyter notebooks.

- Auto-discover `.ipynb` files in a `notebooks/` or `examples/` directory
- Thumbnail previews from the first output cell
- Tag-based filtering
- "Open in Colab" / "Open in molab" / "Download" buttons
- Execution status badges

### PDF Export

Generate a downloadable PDF of the entire documentation site.

- Single PDF combining all pages with proper pagination
- Table of contents with clickable links
- Configurable page selection (full site, sections, or individual pages)
- Styled to match the site theme
- Auto-generated link on homepage or configurable placement
- Optional per-build regeneration or manual `great-docs pdf` command

### Internationalization (i18n) — UI Text

Translate Great Docs interface text into multiple languages.

- `site.language` config key (default: `en`)
- Translation files for navbar, sidebar, and widget labels
- Community-contributed language packs
- RTL (right-to-left) layout support for Arabic, Hebrew, etc.

### Monorepo / Multi-Project Support

Unified documentation across multiple packages or subprojects.

- Shared navigation and search index across projects
- Per-project sidebars with cross-project linking
- Hierarchical project trees (parent/child relationships)
- Independent build cycles with unified deployment
- Common assets and theming across subprojects

### Offline Documentation

Self-contained sites that work without an internet connection.

- PWA (Progressive Web App) support with service worker
- Air-gapped deployable builds for secure environments
- Bundled search index for offline queries
- Optional asset inlining for single-file deployment

---

## Planned — Long Term

Larger efforts for future milestones.

### Plugin / Extension System

Allow third-party extensions to hook into the build pipeline.

- `great-docs.yml` plugin registration
- Hook points: `pre-init`, `post-discovery`, `pre-render`, `post-render`
- Package discovery via entry points (`great_docs.plugins`)
- Example plugins: custom renderers, extra page generators, analytics adapters

### Clean URLs

Strip `.html` extensions from page URLs (e.g., `/user-guide/configuration` instead of `/user-guide/configuration.html`).

- Ideally handled natively by Quarto (no upstream support yet; tracking for if/when it lands)
- Fallback: post-render script that restructures `page.html` → `page/index.html` and rewrites all internal links
- Rewrite sidebar, navbar, cross-references, search index, `objects.json`, and sitemap paths
- Works out-of-the-box on GitHub Pages (serves `dir/index.html` at `/dir/`); trivial on Netlify/Vercel/CloudFlare
- `clean_urls: true` config option in `great-docs.yml`

### Interactive Examples

Live, runnable code blocks in the browser.

- Pyodide or JupyterLite backend
- `{interactive}` code cell annotation in `.qmd`
- Sandboxed execution with output display
- Fallback to static output when JS is disabled

### Accessibility Audit & Improvements

Systematic WCAG 2.1 AA compliance.

- ARIA landmarks and labels on all navigation
- Keyboard navigation for sidebar, search, dark mode toggle
- Color contrast verification across all themes
- Screen reader testing and fixes
- Skip-to-content links

### Theme Customization Gallery

Pre-built color schemes and typography presets.

- `site.theme` config with named presets (e.g., `flatly`, `cosmo`, `solar`)
- CSS variable overrides for custom branding
- Gallery page in Great Docs documentation showing all presets
- User-contributed themes via plugin system

### Template Library

Starter templates for different project types.

- Minimal (API-only)
- Full-featured (API + CLI + User Guide + Notebooks)
- Scientific package
- Data analysis toolkit
- `great-docs init --template <name>` CLI option

### Multi-Language Documentation Sites

Full site translation with a language selector widget.

- Parallel content directories per language (`docs/en/`, `docs/es/`, etc.)
- Language selector dropdown in navbar
- `hreflang` tags for SEO
- Fallback to default language for untranslated pages
- Shared assets and cross-language linking

### AI-Assisted Translation

LLM-powered translation workflows for multi-language documentation.

- Generate translation drafts from source content
- Track changed sections needing re-translation
- Review UI for accepting/editing suggestions
- Integration with i18n content directories
- Cost-effective batch processing for large sites
- `hreflang` tags for SEO
- Fallback to default language for untranslated pages
- Shared assets and cross-language linking

---

## Feedback & Contributions

Have ideas for features not listed here? Open an issue with the `enhancement` label. Contributions to any planned item are welcome — check existing issues first to avoid duplication.

---

_This roadmap is a living document. It is updated as features ship and new priorities emerge._
