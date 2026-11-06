// Drive Chrome through the DevTools protocol to learn how its WebMCP implementation
// behaves: which flags enable it, how tools register, what `execute` receives, what
// agents get back, and what happens on navigation. Calls tools through the
// protocol's `WebMCP.invokeTool`, the same path browser agents use.
//
//   node scripts/webmcp_probe/run.mjs [--chrome PATH] [--out report.json] [--headed]
//
// Prints a summary; `--out` also writes the full JSON report.
// Needs Node 22+ (global WebSocket) and a local Chrome. Not shipped with Great Docs.

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
};
const CHROME = option("--chrome", process.env.CHROME || DEFAULT_CHROME);
const OUT = option("--out", null);
const HEADED = args.includes("--headed");

// Candidate ways of turning WebMCP on, tried in order.
const FLAG_SETS = [
  { label: "no flags", flags: [] },
  { label: "--enable-features=WebMCP", flags: ["--enable-features=WebMCP"] },
  { label: "--enable-features=WebMCPTesting", flags: ["--enable-features=WebMCPTesting"] },
  {
    label: "--enable-experimental-web-platform-features",
    flags: ["--enable-experimental-web-platform-features"],
  },
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function serve() {
  const types = { ".html": "text/html", ".js": "text/javascript" };
  const server = http.createServer((request, response) => {
    const path = join(HERE, new URL(request.url, "http://x").pathname);
    if (!path.startsWith(HERE) || !existsSync(path)) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "content-type": types[extname(path)] || "text/plain" });
    response.end(readFileSync(path));
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

class Cdp {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = [];
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) reject(new Error(`${message.error.message} (${message.error.code})`));
        else resolve(message.result);
      } else if (message.method) {
        for (const listener of this.listeners) listener(message);
      }
    });
  }

  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });
    return new Cdp(socket);
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }

  on(listener) {
    this.listeners.push(listener);
  }

  waitFor(method, predicate = () => true, timeout = 5000) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => resolve(null), timeout);
      const listener = (message) => {
        if (message.method === method && predicate(message.params)) {
          clearTimeout(timer);
          this.listeners.splice(this.listeners.indexOf(listener), 1);
          resolve(message.params);
        }
      };
      this.listeners.push(listener);
    });
  }

  close() {
    this.socket.close();
  }
}

async function launch(flags) {
  const profile = mkdtempSync(join(tmpdir(), "webmcp-probe-"));
  const chrome = spawn(
    CHROME,
    [
      ...(HEADED ? [] : ["--headless=new"]),
      `--user-data-dir=${profile}`,
      "--remote-debugging-port=0",
      "--no-first-run",
      "--no-default-browser-check",
      "--allow-file-access-from-files",
      ...flags,
      "about:blank",
    ],
    { stdio: "ignore" }
  );
  const portFile = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 100 && !existsSync(portFile); i++) await sleep(100);
  if (!existsSync(portFile)) throw new Error("Chrome did not start (no DevToolsActivePort)");
  const port = readFileSync(portFile, "utf8").split("\n")[0].trim();
  let page;
  for (let i = 0; i < 50 && !page; i++) {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    page = list.find((target) => target.type === "page");
    if (!page) await sleep(100);
  }
  const { Browser: browser } = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
  const cdp = await Cdp.connect(page.webSocketDebuggerUrl);
  const stop = async () => {
    cdp.close();
    chrome.kill();
    await sleep(300);
    rmSync(profile, { recursive: true, force: true });
  };
  return { cdp, stop, browser };
}

async function navigate(cdp, url) {
  const loaded = cdp.waitFor("Page.loadEventFired", () => true, 10000);
  await cdp.send("Page.navigate", { url });
  await loaded;
  await sleep(400);
}

async function evaluate(cdp, expression) {
  const { result, exceptionDetails } = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (exceptionDetails) return { exception: exceptionDetails.exception?.description || exceptionDetails.text };
  return result.value;
}

// Count protocol events by method, and the tools they carry.
function tally(events) {
  const counts = {};
  for (const event of events) {
    const key = event.method.replace("WebMCP.", "");
    counts[key] = (counts[key] || 0) + 1;
    if (event.params.tools) counts[`${key} (tools)`] = (counts[`${key} (tools)`] || 0) + event.params.tools.length;
  }
  return counts;
}

function responses(events, phase) {
  return events
    .filter((e) => e.phase === phase && e.method === "WebMCP.toolResponded")
    .map((e) => ({ invocationId: e.params.invocationId, status: e.params.status, output: e.params.output }));
}

function summarizeOutput(output) {
  if (output === undefined) return { present: false };
  const text = typeof output === "string" ? output : JSON.stringify(output);
  return {
    present: true,
    type: Array.isArray(output) ? "array" : output === null ? "null" : typeof output,
    length: text.length,
    sample: text.length > 240 ? `${text.slice(0, 240)}…` : output,
  };
}

async function detect(origin) {
  const rows = [];
  for (const set of FLAG_SETS) {
    const { cdp, stop, browser } = await launch(set.flags);
    try {
      await cdp.send("Page.enable");
      await cdp.send("Runtime.enable");
      await navigate(cdp, `${origin}/probe.html`);
      const env = await evaluate(cdp, "window.__probe && window.__probe.env");
      let domain = "ok";
      try {
        await cdp.send("WebMCP.enable");
      } catch (error) {
        domain = error.message;
      }
      rows.push({ ...set, env, domain, browser });
    } finally {
      await stop();
    }
  }
  return rows;
}

async function fullRun(origin, crossOrigin, flags) {
  const { cdp, stop } = await launch(flags);
  const events = [];
  let phase = "initial load";
  cdp.on((message) => {
    if (message.method.startsWith("WebMCP.")) events.push({ phase, method: message.method, params: message.params });
  });
  const report = { flags, phases: {} };

  async function invoke(frameId, toolName, input) {
    const started = Date.now();
    let invocationId;
    try {
      ({ invocationId } = await cdp.send("WebMCP.invokeTool", { frameId, toolName, input }));
    } catch (error) {
      return { toolName, input, invokeError: error.message };
    }
    const response = await cdp.waitFor("WebMCP.toolResponded", (p) => p.invocationId === invocationId, 6000);
    if (!response) return { toolName, input, invocationId, timedOut: true };
    return {
      toolName,
      input,
      ms: Date.now() - started,
      status: response.status,
      output: summarizeOutput(response.output),
      errorText: response.errorText,
      exception: response.exception?.description,
    };
  }

  try {
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("WebMCP.enable");
    await navigate(cdp, `${origin}/probe.html`);

    const { frameTree } = await cdp.send("Page.getFrameTree");
    const frameId = frameTree.frame.id;
    const probe = await evaluate(cdp, "JSON.parse(JSON.stringify(window.__probe))");
    const added = events.filter((e) => e.method === "WebMCP.toolsAdded").flatMap((e) => e.params.tools);
    report.environment = probe.env;
    report.registrations = probe.registrations;
    report.toolchangeAtLoad = { count: probe.events.length, eventKeys: probe.toolchangeKeys };
    report.toolsSeenByProtocol = added.map((tool) => ({
      name: tool.name,
      description: tool.description,
      annotations: tool.annotations,
      hasInputSchema: tool.inputSchema !== undefined,
      inputSchema: tool.name === "probe_echo" || tool.name === "probe_no_schema" ? tool.inputSchema : undefined,
      keys: Object.keys(tool).sort(),
    }));

    phase = "page-script calls";
    report.fromPage = await evaluate(cdp, "window.__probeFromPage()");

    phase = "protocol invocations";
    const plan = [
      ["probe_echo", { text: "hi" }],
      ["probe_echo", {}],
      ["probe_echo", { wrong: 1 }],
      ["probe_echo", { text: 5 }],
      ["probe_string", {}],
      ["probe_content", {}],
      ["probe_undefined", {}],
      ["probe_async", {}],
      ["probe_throw", {}],
      ["probe_reject", {}],
      ["probe_big", {}],
      ["probe_no_schema", { anything: true }],
      ["probe_output_schema", {}],
      ["probe_output_mismatch", {}],
      ["probe_action", {}],
      ["no_such_tool", {}],
    ];
    report.invocations = [];
    for (const [name, input] of plan) report.invocations.push(await invoke(frameId, name, input));
    const after = await evaluate(cdp, "JSON.parse(JSON.stringify(window.__probe))");
    report.executeArguments = after.calls.filter((call) => call.tool !== "probe_big");
    report.toolchangeAfterCalls = after.events.length;

    phase = "cancel";
    const slow = cdp.send("WebMCP.invokeTool", { frameId, toolName: "probe_slow", input: {} });
    const { invocationId: slowId } = await slow;
    await sleep(200);
    const slowResponded = cdp.waitFor("WebMCP.toolResponded", (p) => p.invocationId === slowId, 5000);
    let cancelError = null;
    try {
      await cdp.send("WebMCP.cancelInvocation", { invocationId: slowId });
    } catch (error) {
      cancelError = error.message;
    }
    const slowResponse = await slowResponded;
    await sleep(100);
    report.cancel = {
      cancelError,
      status: slowResponse?.status,
      output: slowResponse ? summarizeOutput(slowResponse.output) : null,
      errorText: slowResponse?.errorText,
      pageSawAbort: await evaluate(cdp, "window.__probe.slowAborted || null"),
    };

    phase = "names";
    report.names = await evaluate(cdp, "window.__probeNames()");

    phase = "extras";
    const extras = await evaluate(cdp, "window.__probeExtras().then(e => JSON.parse(JSON.stringify(e)))");
    await sleep(200);
    const extraTools = events
      .filter((e) => e.phase === phase && e.method === "WebMCP.toolsAdded")
      .flatMap((e) => e.params.tools);
    const pageTools = await evaluate(
      cdp,
      `document.modelContext.getTools().then(list => list.filter(t => t.name.startsWith("probe_")).map(t => ({
        name: t.name, title: t.title, origin: t.origin, annotations: t.annotations,
        descriptionLength: t.description.length })))`
    );
    report.extras = extras.map((entry) => {
      const seen = extraTools.find((tool) => tool.name === entry.label);
      const page = (pageTools || []).find((tool) => tool.name === entry.label);
      return {
        label: entry.label,
        settled: entry.settled,
        error: entry.error,
        protocol: seen && {
          keys: Object.keys(seen).sort(),
          annotations: seen.annotations,
          descriptionLength: seen.description.length,
          inputSchema: entry.label === "probe_odd_schema" ? seen.inputSchema : undefined,
        },
        getTools: page,
      };
    });

    phase = "abort signal";
    const toolchangeBeforeAbort = await evaluate(cdp, "window.__probe.events.length");
    report.abort = { aborted: await evaluate(cdp, "window.__probeAbort()") };
    await sleep(400);
    report.abort.toolsRemoved = events
      .filter((e) => e.phase === phase && e.method === "WebMCP.toolsRemoved")
      .flatMap((e) => e.params.tools.map((tool) => tool.name));
    report.abort.toolchangeEvents = (await evaluate(cdp, "window.__probe.events.length")) - toolchangeBeforeAbort;

    phase = "hash navigation";
    await evaluate(cdp, "location.hash = '#section'");
    await sleep(500);
    phase = "pushState";
    await evaluate(cdp, "history.pushState({}, '', 'probe.html?state=1')");
    await sleep(500);
    for (const name of ["hash navigation", "pushState"]) {
      report.phases[name] = tally(events.filter((e) => e.phase === name));
    }

    phase = "navigate after result";
    const loadAfter = cdp.waitFor("Page.loadEventFired", () => true, 8000);
    report.navigateAfter = await invoke(frameId, "probe_navigate_after", {});
    report.navigateAfter.loaded = !!(await loadAfter);
    await sleep(600);
    report.navigateAfter.events = tally(events.filter((e) => e.phase === phase));
    report.navigateAfter.responses = responses(events, phase);
    report.navigateAfter.page2Environment = await evaluate(cdp, "window.__probe && window.__probe.env");

    await navigate(cdp, `${origin}/probe.html`);
    phase = "navigate 500 ms after result";
    const frameLater = (await cdp.send("Page.getFrameTree")).frameTree.frame.id;
    const loadLater = cdp.waitFor("Page.loadEventFired", () => true, 8000);
    report.navigateLater = await invoke(frameLater, "probe_navigate_later", {});
    report.navigateLater.loaded = !!(await loadLater);
    await sleep(600);
    report.navigateLater.responses = responses(events, phase);

    await navigate(cdp, `${origin}/probe.html`);
    phase = "navigate before result";
    const frame2 = (await cdp.send("Page.getFrameTree")).frameTree.frame.id;
    report.navigateBefore = await invoke(frame2, "probe_navigate_before", {});
    await sleep(600);
    report.navigateBefore.events = tally(events.filter((e) => e.phase === "navigate before result"));
    report.navigateBefore.responses = responses(events, "navigate before result");
    report.navigateBefore.eventOrder = events
      .filter((e) => e.phase === "navigate before result" && e.method !== "WebMCP.toolsAdded")
      .map((e) => e.method);

    phase = "iframes";
    await navigate(cdp, `${origin}/iframe.html?cross=${encodeURIComponent(`${crossOrigin}/probe.html`)}`);
    await sleep(800);
    const tree = (await cdp.send("Page.getFrameTree")).frameTree;
    const frames = Object.fromEntries((tree.childFrames || []).map((child) => [child.frame.id, child.frame.url]));
    const byFrame = {};
    for (const event of events.filter((e) => e.phase === phase && e.method === "WebMCP.toolsAdded")) {
      for (const tool of event.params.tools) {
        const url = frames[tool.frameId] || (tool.frameId === tree.frame.id ? "top" : tool.frameId);
        byFrame[url] = (byFrame[url] || 0) + 1;
      }
    }
    report.iframes = {
      frames: Object.values(frames),
      toolsAddedByFrame: byFrame,
      // Each framed probe posts its own view, which covers out-of-process frames too.
      reports: await evaluate(cdp, "window.__frames || []"),
    };

    phase = "file URL";
    await navigate(cdp, pathToFileURL(join(HERE, "probe.html")).href);
    report.fileUrl = {
      environment: await evaluate(cdp, "window.__probe && window.__probe.env"),
      registrations: await evaluate(cdp, "window.__probe && window.__probe.registrations.slice(0, 2)"),
      toolsAdded: events
        .filter((e) => e.phase === phase && e.method === "WebMCP.toolsAdded")
        .reduce((n, e) => n + e.params.tools.length, 0),
    };
  } finally {
    await stop();
  }
  return report;
}

// The answers that matter for Great Docs, one line each.
function summarize(report) {
  const lines = [`Browser: ${report.browser}`];
  const on = report.detection.filter((row) => row.documentModelContext === "object").map((row) => row.label);
  lines.push(`WebMCP available with: ${on.length ? on.join(", ") : "none of the tried flags"}`);
  const run = report.run;
  if (!run) return lines.join("\n");
  const env = run.environment;
  lines.push(`Entry points: document.modelContext=${env.documentModelContext}, navigator.modelContext=${env.navigatorModelContext}`);
  lines.push(`ModelContext members: ${env.methods.join(", ")}`);
  const first = run.registrations[0];
  lines.push(`registerTool returns: ${first.isPromise ? "a promise" : first.returned} (fulfils with ${first.value}); works while readyState=${env.readyStateAtRegistration}`);
  for (const entry of run.registrations.filter((r) => r.settled === "rejected" || r.threw)) {
    lines.push(`  rejected, ${entry.label}: ${entry.error || entry.threw}`);
  }
  const rejectedNames = run.names.filter((n) => !n.ok).map((n) => JSON.stringify(n.name));
  lines.push(`Names rejected: ${rejectedNames.join(", ") || "none"}; accepted: ${run.names.filter((n) => n.ok).map((n) => n.name).join(", ")}`);
  const call = run.executeArguments[0];
  lines.push(`execute(input, second): input is ${call.inputType}; second argument has ${call.secondKeys.join(", ") || "nothing"}`);
  const echo = run.invocations.filter((i) => i.toolName === "probe_echo");
  const unchecked = echo.slice(1).every((i) => i.status === "Completed");
  lines.push(`Browser validates input against inputSchema: ${unchecked ? "no (invalid input reached execute)" : "yes"}`);
  for (const i of run.invocations) {
    const detail = i.invokeError || (i.status === "Error" ? i.exception?.split("\n")[0] : `${i.output.type}, ${i.output.length} chars`);
    lines.push(`  ${i.toolName} ${JSON.stringify(i.input)} -> ${i.status || "not invoked"}: ${detail}`);
  }
  const hints = run.toolsSeenByProtocol.find((t) => t.name === "probe_ann_hint_names");
  const plain = run.toolsSeenByProtocol.find((t) => t.name === "probe_ann_plain_names");
  lines.push(`Annotations from *Hint names: ${JSON.stringify(hints?.annotations)}; from plain names: ${JSON.stringify(plain?.annotations)}`);
  const page = run.fromPage.getTools;
  lines.push(`getTools() annotation names: ${page.firstAnnotations}; tool members: ${page.firstKeys.join(", ")}`);
  const outSchema = run.toolsSeenByProtocol.find((t) => t.name === "probe_output_schema");
  lines.push(`outputSchema reaches the protocol: ${outSchema.keys.includes("outputSchema") ? "yes" : "no"}`);
  for (const extra of run.extras) {
    lines.push(`  ${extra.label}: ${extra.settled}${extra.error ? ` (${extra.error})` : ""}; protocol annotations ${JSON.stringify(extra.protocol?.annotations)}; getTools title ${JSON.stringify(extra.getTools?.title)}`);
  }
  lines.push(`executeTool from page: object input -> ${JSON.stringify(run.fromPage.executeObject)}; string input -> ${JSON.stringify(run.fromPage.executeString)}`);
  lines.push(`Cancel: status ${run.cancel.status}; page's signal aborted: ${!!run.cancel.pageSawAbort}`);
  lines.push(`toolchange: ${run.toolchangeAtLoad.count} events for ${run.registrations.filter((r) => r.settled === "fulfilled").length} registrations; abort -> removed ${JSON.stringify(run.abort.toolsRemoved)}, ${run.abort.toolchangeEvents} toolchange`);
  lines.push(`Hash change events: ${JSON.stringify(run.phases["hash navigation"])}; pushState events: ${JSON.stringify(run.phases.pushState)}`);
  for (const [label, nav] of [["after result", run.navigateAfter], ["500 ms after result", run.navigateLater], ["before result", run.navigateBefore]]) {
    lines.push(`Navigate ${label}: responses ${JSON.stringify(nav.responses.map((r) => [r.status, r.output]))}`);
  }
  for (const frame of run.iframes.reports) {
    const reg = frame.report.firstRegistration;
    lines.push(`iframe ${frame.from}: ${reg.settled}${reg.error ? ` (${reg.error})` : ""}`);
  }
  lines.push(`file:// page: ${run.fileUrl.toolsAdded} tools registered, isSecureContext=${run.fileUrl.environment.isSecureContext}`);
  return lines.join("\n");
}

const server = await serve();
const origin = `http://127.0.0.1:${server.address().port}`;
try {
  const detection = await detect(origin);
  const working = detection.find((row) => row.env && row.env.documentModelContext === "object");
  const report = {
    chrome: CHROME,
    browser: detection[0]?.browser,
    date: new Date().toISOString(),
    detection: detection.map((row) => ({
      label: row.label,
      documentModelContext: row.env?.documentModelContext,
      navigatorModelContext: row.env?.navigatorModelContext,
      protocolDomain: row.domain,
      userAgent: row.env?.userAgent,
    })),
  };
  const crossOrigin = origin.replace("127.0.0.1", "localhost");
  if (working) report.run = await fullRun(origin, crossOrigin, working.flags);
  else report.run = null;
  const text = JSON.stringify(report, null, 2);
  if (OUT) writeFileSync(OUT, `${text}\n`);
  process.stdout.write(`${summarize(report)}\n`);
} finally {
  server.close();
}
