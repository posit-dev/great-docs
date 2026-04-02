# Great Docs — Roadmap

## Planned — Near Term

High-value features that build on existing infrastructure.

### Author Attribution & Avatars

Display author information with circular GitHub-style avatars on authored pages.

- Author name and image from page YAML frontmatter (`author: {name, image, url}`)
- Multiple author avatars displayed in a row
- Circular avatar images (falls back to initials when no image)
- Hover tooltip shows full author name
- Author lookup from `great-docs.yml` `authors:` list for full metadata
- Only shown on authored pages (user guide, blog, recipes) with explicit `author:` frontmatter
- Auto-generated pages (reference, changelog) show timestamps only, no author
- Optional `team_author:` config for a catch-all team attribution (e.g., "Great Tables Team")
- `site.show_author: true/false` to enable/disable author display

### Page Status Badges

Visual indicators for page lifecycle status in navigation.

- `status: new` frontmatter shows "New" badge in sidebar
- `status: deprecated` shows deprecation indicator
- Custom status definitions in `great-docs.yml`
- Badge icons and colors configurable per status
- Filter/highlight pages by status

### Reading Time Estimate

Auto-calculate and display estimated reading time.

- Word count-based calculation shown near page title
- Configurable words-per-minute rate
- Override via frontmatter (`readtime: 15`)
- Show/hide globally or per-page
- Useful for user guide articles, tutorials, and blog posts

### Breadcrumb Navigation

Display navigation path above page content.

- Breadcrumb trail showing hierarchy (Home > User Guide > Configuration)
- Clickable links to parent sections
- Helps orientation in deep documentation structures
- Hide per-page via frontmatter if desired
- Responsive design for mobile

### Enhanced CLI Reference

API-reference-style rendering for CLI applications.

- **Click** (primary): Parse command/group decorators to extract structure
- **Typer**: Leverage Click internals via Typer's underlying Click commands
- **argparse**: Parse `ArgumentParser` definitions and subparsers
- **Fire**: Introspect Python functions/classes exposed as CLI
- **Extensible**: Plugin interface for additional CLI frameworks
- Generate `.qmd` pages with prose sections for each command and subcommand
- Render arguments, options, and flags in styled parameter tables (like API reference)
- Include type annotations, defaults, and help text
- Auto-generate usage examples from framework-specific example metadata
- Cross-reference between subcommands and parent groups
- Search integration: CLI commands indexed alongside API symbols
- Support for command aliases and deprecated commands
- Environment variable documentation
- Alternative to raw `--help` output: richer formatting, navigation, and discoverability

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

### Blog Support

First-class blogging integrated with documentation.

- Posts directory with date-based organization
- Automatic archive and category index pages
- Post excerpts with `<!-- more -->` separator
- Author profiles with avatars and bios
- Categories and tags per post
- RSS feed generation
- Reading time and publication date display
- Pinned/featured posts
- Pagination for post listings
- Blog-only mode (documentation optional)

### Instant Loading

SPA-like navigation without full page reloads.

- XHR-based page transitions preserving search state
- Progress indicator for slow connections
- Instant prefetching on link hover
- Instant previews showing tooltip of linked section
- Anchor tracking (URL updates as you scroll)
- Significantly faster perceived navigation

### Code Annotations

Rich inline annotations inside code blocks.

- Numbered markers in code comments pointing to explanations
- Click/hover to reveal annotation content
- Supports any language with comment syntax
- Nestable annotations
- Works inside admonitions and content tabs
- Strip comment markers option for cleaner display

### Comment System Integration

Enable community discussion on documentation pages.

- One-line Giscus setup (GitHub Discussions backend)
- Theme-aware dark/light mode sync
- Per-page enable/disable via frontmatter
- Alternative backends: Disqus, Utterances
- Moderation via GitHub

### Document Contributors

Show GitHub avatars of all page contributors.

- Extract contributors from git history
- Circular avatar images linking to GitHub profiles
- Displayed at page footer alongside timestamps
- Configurable: show all or top N contributors
- Works with git-committers plugin pattern

### Image Optimization

Automatic compression and conversion of images.

- Compress PNG, JPEG, GIF during build
- Convert to modern formats (WebP, AVIF) where supported
- Lazy loading attributes for below-fold images
- Responsive image srcsets
- Significant page load improvements

### Folder-Level Metadata Defaults

Set default frontmatter for entire directories.

- `.meta.yml` files apply defaults to all pages in folder
- Reduce repetition for large documentation sections
- Inheritance: child folders can override parent defaults
- Useful for setting authors, tags, templates per section

### Content Tabs

Tabbed content blocks for alternative instructions.

- Show pip vs conda vs poetry installation
- Platform-specific instructions (macOS / Linux / Windows)
- Synced tabs across pages (user preference remembered)
- Keyboard accessible
- Code blocks and prose supported inside tabs

### Page Tags

Categorize pages with tags for improved discoverability.

- Add tags via frontmatter (`tags: [Python, Testing, API]`)
- Auto-generated tags index page listing all tags and linked pages
- Tags rendered above page title with links to tag index
- Nested/hierarchical tags (e.g., `Python/Testing`)
- Shadow tags for internal organization (hidden from public view)
- Scoped tag listings per documentation section
- Optional tag icons

### Enhanced Search

Improve the built-in search with modern capabilities.

- Fuzzy matching and typo tolerance
- Search suggestions and completions
- Highlighting of matched terms in results
- Keyboard navigation in search results
- Recent searches history

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

### Privacy & GDPR Compliance

Tools for data privacy regulation compliance.

- Auto-download external assets (fonts, analytics scripts) for self-hosting
- Cookie consent banner with configurable text
- External link rewriting to proxy through local assets
- One-line config for privacy mode
- Audit report of external requests

---

## Feedback & Contributions

Have ideas for features not listed here? Open an issue with the `enhancement` label. Contributions to any planned item are welcome so check existing issues first to avoid duplication.

_This roadmap is a living document. It is updated as features ship and new priorities emerge._
