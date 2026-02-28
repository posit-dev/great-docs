# Example Quarto Configuration with Great Docs

This example shows how to configure your documentation project to use great-docs.

## Method 1: Using the CLI (Recommended)

After installing great-docs, simply run:

```bash
great-docs init
```

This will automatically:

- Copy the post-render script to `scripts/post-render.py`
- Copy the CSS file to `great-docs.css`
- Update your `_quarto.yml` configuration

## Method 2: Manual Configuration

### 1. Basic \_quarto.yml setup

```yaml
project:
  type: website
  post-render: scripts/post-render.py

format:
  html:
    theme: flatly # Works well with great-docs
    css:
      - great-docs.css
    toc: true
    grid:
      sidebar-width: 270px
      body-width: 950px
      margin-width: 225px
      gutter-width: 1rem

website:
  title: "Your Project Name"
  navbar:
    logo: assets/logo.png # Optional
```

### 2. Copy docs files

```python
from great_docs import GreatDocs

# Initialize docs for current directory
docs = GreatDocs()

# Install docs files
docs.install()
```

## Customization

You can customize by:

1. Editing the copied `great-docs.css` file
2. Modifying the `scripts/post-render.py` script
3. Adding additional CSS files to your `_quarto.yml`
