# Deploying the site

Build the site, then publish the `_site` directory.

## GitHub Pages {#github-pages}

Push to the `gh-pages` branch, or let the workflow deploy it:

```yaml
# deploy on every push
on: push
```

### Custom domains

Add a `CNAME` file.

## Netlify

Drag the `_site` folder onto Netlify.
