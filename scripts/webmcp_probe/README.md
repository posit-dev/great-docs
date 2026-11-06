# WebMCP probe

Checks how a Chrome build implements WebMCP, so that Great Docs' WebMCP runtime is built on
observed behaviour rather than on the draft spec. Re-run it when a new Chrome release changes
WebMCP.

None of this ships with Great Docs.

| File | Purpose |
|---|---|
| `probe.js` | Registers test tools in many forms (return types, annotations, bad names, signals, navigation) and records what happens in `window.__probe` |
| `probe.html` | Loads the probe while the document is still parsing |
| `page2.html` | Navigation target; loads the probe with `defer` |
| `iframe.html` | Embeds the probe same-origin and cross-origin |
| `run.mjs` | Starts a local server, launches Chrome with a throwaway profile, calls the tools through the DevTools protocol's `WebMCP` domain (the path browser agents use) and prints a summary |

## Automated run

Needs Node 22+ and a local Chrome:

```bash
node scripts/webmcp_probe/run.mjs                      # summary only
node scripts/webmcp_probe/run.mjs --out report.json    # also the full JSON report
node scripts/webmcp_probe/run.mjs --chrome "/path/to/Chrome" --headed
```

The runner tries several ways of enabling WebMCP and uses the first that works for the full run.

## Manual checks

Two things need a real browser profile and a person:

1. In Chrome, enable `chrome://flags/#enable-webmcp-testing` and relaunch.
2. Install the Model Context Tool Inspector extension.
3. Serve this directory: `python3 -m http.server -d scripts/webmcp_probe 8765`, then open
   <http://localhost:8765/probe.html>.
4. In the Inspector, check:
   - whether it shows `title`, annotations (`readOnlyHint`, `consequentialHint`,
     `untrustedContentHint`) and the input schema;
   - what it shows for `probe_throw` (an exception) compared with a tool that returns an error
     object;
   - what it shows for `probe_navigate_after`: the tool's own result, or the empty `[]` that
     Chrome reports once the page has navigated.
5. With an agent that uses WebMCP (such as Chrome's example agent extension), note whether it
   asks for confirmation before `probe_action` or `probe_consequential` but not before
   read-only tools.
