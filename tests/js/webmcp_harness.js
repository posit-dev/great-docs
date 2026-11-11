// Run `webmcp.js` in a stub page and print what a scenario observed, as JSON.
//
//     node webmcp_harness.js <webmcp.js> <options JSON> <scenario>
//
// The scenario is the body of an async function. It sees the page's globals and:
//
// - `tools`: `window.greatDocs.tools`, or `undefined` without the JS API
// - `browser`: the stub `modelContext`, whose `tools` are the registered tool definitions
// - `settle()`: a promise that resolves once pending registrations and fetches settle
//
// Its return value is printed with the page's status, ready events, warnings, fetched URLs and
// whether the platform objects kept their properties.
//
// Options, all optional:
//
// - `settings`: the settings object, a string to use as the element's text, or `null` for none
// - `bodyClasses`: the `<body>` classes
// - `pathname`: the open page, such as `/docs/user-guide/intro.html`
// - `scriptSrc`: the script's `src`, such as `/docs/webmcp.js`
// - `modelContext`: `document`, `navigator`, `both` or `none`
// - `refuse`: tool names the browser refuses to register
// - `siteDir`: the directory that `fetch` serves, as the directory holding the script
// - `fetchFails`: whether every `fetch` fails as a network error would
// - `main`: the page's `<main>` element, as `[tag, attributes, ...children]` with string text
// - `title`: the page's `<title>`
// - `meta`: the page's `<meta>` elements, as an object mapping names to content
// - `testMode`: whether `window.__GD_WEBMCP_TEST__` is set (default `true`)

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const [runtimePath, optionsJson, scenario] = process.argv.slice(2);
const options = JSON.parse(optionsJson);
const origin = 'https://docs.example.org';
const pathname = options.pathname || '/user-guide/intro.html';
const scriptSrc = options.scriptSrc || '/webmcp.js';
const scriptDir = scriptSrc.slice(0, scriptSrc.lastIndexOf('/') + 1);

// ---- Elements ----------------------------------------------------------------------------

function element(tag, attributes, children) {
    const node = {
        nodeType: 1,
        nodeName: tag.toUpperCase(),
        attributes: Object.assign({}, attributes || {}),
        childNodes: [],
        parentNode: null,
        hidden: Boolean(attributes && attributes.hidden),
        get id() {
            return this.attributes.id || '';
        },
        get className() {
            return this.attributes.class || '';
        },
        get textContent() {
            return this.childNodes
                .map((child) => (child.nodeType === 3 ? child.nodeValue : child.textContent))
                .join('');
        },
        set textContent(value) {
            const text = { nodeType: 3, nodeName: '#text', nodeValue: String(value) };
            text.parentNode = this;
            this.childNodes = [text];
        },
        getAttribute(name) {
            return name in this.attributes ? String(this.attributes[name]) : null;
        },
        setAttribute(name, value) {
            this.attributes[name] = String(value);
        },
        classList: {
            contains: (name) => node.className.split(/\s+/).includes(name),
        },
    };
    for (const child of children || []) {
        const childNode = typeof child === 'string'
            ? { nodeType: 3, nodeName: '#text', nodeValue: child }
            : build(child);
        childNode.parentNode = node;
        node.childNodes.push(childNode);
    }
    return node;
}

function build(spec) {
    const [tag, attributes, ...children] = spec;
    return element(tag, attributes, children);
}

function descendants(node) {
    const found = [];
    for (const child of node.childNodes || []) {
        if (child.nodeType === 1) found.push(child, ...descendants(child));
    }
    return found;
}

// Supports `tag`, `tag.class`, `tag[attribute="value"]` and `ancestor descendant`.
function matches(node, simple) {
    const attribute = /^(\w+)\[(\w+)="([^"]*)"\]$/.exec(simple);
    if (attribute) {
        return node.nodeName === attribute[1].toUpperCase() &&
            node.getAttribute(attribute[2]) === attribute[3];
    }
    const [tag, cls] = simple.split('.');
    return node.nodeName === tag.toUpperCase() && (!cls || node.classList.contains(cls));
}

function querySelector(root, selector) {
    const parts = selector.trim().split(/\s+/);
    let scopes = [root];
    for (const part of parts) {
        scopes = scopes.flatMap((scope) =>
            descendants(scope).filter((node) => matches(node, part)));
    }
    return scopes[0] || null;
}

// ---- The page ----------------------------------------------------------------------------

const warnings = [];
const events = [];
const fetched = [];
const pending = new Set();

function track(promise) {
    pending.add(promise);
    const done = () => pending.delete(promise);
    promise.then(done, done);
    return promise;
}

const body = element('body', { class: (options.bodyClasses || []).join(' ') }, [
    options.main || ['main', {}, ['p', {}, 'Page text.']],
]);
const head = element('head', {}, Object.entries(options.meta || {}).map(
    ([name, content]) => ['meta', { name, content }]));
const html = element('html', {}, []);
html.childNodes.push(head, body);

let settingsElement = null;
if (options.settings !== null) {
    const settings = options.settings === undefined ? {} : options.settings;
    settingsElement = element('script', { type: 'application/json', id: 'gd-webmcp-settings' }, []);
    settingsElement.textContent =
        typeof settings === 'string' ? settings : JSON.stringify(settings);
}

class StubModelContext {
    constructor() {
        this.tools = [];
    }

    registerTool(tool, registration) {
        return track(new Promise((resolve, reject) => {
            const taken = this.tools.some((t) => t.name === tool.name);
            if ((options.refuse || []).includes(tool.name) || taken) {
                const error = new Error(`Tool "${tool.name}" can't be registered`);
                error.name = 'InvalidStateError';
                reject(error);
                return;
            }
            this.tools.push(tool);
            if (registration && registration.signal) {
                registration.signal.addEventListener('abort', () => {
                    this.tools = this.tools.filter((t) => t !== tool);
                });
            }
            resolve();
        }));
    }
}

const variant = options.modelContext || 'document';
const browser = variant === 'none' ? undefined : new StubModelContext();
const documentContext = variant === 'document' || variant === 'both' ? browser : undefined;
const navigatorContext = variant === 'navigator' || variant === 'both' ? browser : undefined;

class CustomEvent {
    constructor(type, init) {
        this.type = type;
        this.detail = init && init.detail;
    }
}

const document = {
    title: options.title === undefined ? 'Intro – Example' : options.title,
    currentScript: { src: origin + scriptSrc },
    documentElement: html,
    head,
    body,
    modelContext: documentContext,
    getElementById: (id) => (id === 'gd-webmcp-settings' ? settingsElement : null),
    querySelector: (selector) => querySelector(html, selector),
    dispatchEvent(event) {
        const tools = context.window.greatDocs && context.window.greatDocs.tools;
        events.push({ type: event.type, detailIsTools: event.detail === tools });
        return true;
    },
};

const navigator = { modelContext: navigatorContext };

function fetch(url, init) {
    fetched.push(String(url));
    return track(new Promise((resolve, reject) => {
        if (options.fetchFails) {
            reject(new TypeError('Failed to fetch'));
            return;
        }
        const target = new URL(url);
        const relative = decodeURIComponent(target.pathname).slice(scriptDir.length);
        const file = options.siteDir && target.pathname.startsWith(scriptDir)
            ? path.join(options.siteDir, relative)
            : null;
        if (init && init.signal && init.signal.aborted) {
            reject(new Error('aborted'));
        } else if (file && fs.existsSync(file) && fs.statSync(file).isFile()) {
            const text = fs.readFileSync(file, 'utf8');
            resolve({ ok: true, status: 200, text: () => Promise.resolve(text) });
        } else {
            resolve({ ok: false, status: 404, text: () => Promise.resolve('Not found') });
        }
    }));
}

const context = {
    document,
    navigator,
    location: { href: origin + pathname + '#top', pathname, origin },
    fetch,
    URL,
    AbortController,
    CustomEvent,
    setTimeout,
    clearTimeout,
    console: { warn: (...args) => warnings.push(args.map(String).join(' ')), log() {} },
    __GD_WEBMCP_TEST__: options.testMode !== false,
};
context.window = context;
vm.createContext(context);

// ---- Platform objects --------------------------------------------------------------------

function shape(object) {
    if (!object) return null;
    const own = Object.getOwnPropertyDescriptors(object);
    const proto = Object.getOwnPropertyDescriptors(Object.getPrototypeOf(object));
    const describe = (descriptors) => Object.fromEntries(Object.entries(descriptors).map(
        ([key, d]) =>
            [key, [typeof d.value, d.writable, d.enumerable, d.configurable, typeof d.get]]
    ));
    return JSON.stringify({ own: describe(own), proto: describe(proto) });
}

function platform() {
    return JSON.stringify({
        browser: shape(browser),
        document: Object.keys(document).sort(),
        navigator: Object.keys(navigator).sort(),
    });
}

const before = platform();

// ---- Run ---------------------------------------------------------------------------------

async function settle() {
    for (let i = 0; i < 50; i++) {
        await new Promise((resolve) => setImmediate(resolve));
        if (pending.size === 0) {
            await new Promise((resolve) => setImmediate(resolve));
            if (pending.size === 0) return;
        }
        await Promise.allSettled([...pending]);
    }
}

(async () => {
    vm.runInContext(fs.readFileSync(runtimePath, 'utf8'), context, { filename: 'webmcp.js' });
    context.tools = context.window.greatDocs && context.window.greatDocs.tools;
    context.browser = browser;
    context.settle = settle;
    const result = await vm.runInContext(`(async () => {\n${scenario || ''}\n})()`, context);
    await settle();
    process.stdout.write(JSON.stringify({
        result: result === undefined ? null : result,
        status: html.getAttribute('data-gd-webmcp'),
        events,
        warnings,
        fetched,
        registered: browser ? browser.tools.map((tool) => tool.name) : null,
        platformUnchanged: platform() === before,
    }));
})().catch((error) => {
    process.stderr.write(String(error && error.stack || error));
    process.exit(1);
});
