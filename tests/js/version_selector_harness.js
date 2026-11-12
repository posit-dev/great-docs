// Run `version-selector.js` in a stub page and print what it exposed and built, as JSON.
//
//     node version_selector_harness.js <version-selector.js> <options JSON>
//
// Options, all optional:
//
// - `map`: the version map, or `null` (the default) for a page without one
// - `pathname`: the open page, such as `/docs/v/1.5/guide.html` (default `/index.html`)
// - `offset`: the page's `quarto:offset`, or omitted for none
// - `loading`: whether the document is still loading, so the selector waits to build
// - `tags`: the tags to pass to `urlFor`, by default every version's tag
// - `click`: the tag of the selector link to click before reporting
//
// Prints:
//
// - `api`: whether `window.greatDocsVersions` exists
// - `current`, `list` and `urls`: its answers, with `urls` mapping each tag to `urlFor(tag)`
// - `listIsCopy`: whether changing an entry from `list()` leaves the next call's unchanged
// - `links`: the selector's link targets by tag, or `null` without a selector
// - `banner`: the warning banner's link target, or `null` without a banner
// - `stored`: the version kept in `localStorage`

'use strict';

const fs = require('fs');
const vm = require('vm');

const [scriptPath, optionsJson] = process.argv.slice(2);
const options = JSON.parse(optionsJson);
const map = options.map === undefined ? null : options.map;

function element(tag) {
    const classes = new Set();
    const listeners = {};
    return {
        tagName: tag.toUpperCase(),
        attributes: {},
        children: [],
        innerHTML: '',
        href: '',
        className: '',
        classList: {
            add: (name) => classes.add(name),
            remove: (name) => classes.delete(name),
            contains: (name) => classes.has(name),
        },
        listeners,
        setAttribute(name, value) {
            this.attributes[name] = String(value);
        },
        getAttribute(name) {
            return name in this.attributes ? this.attributes[name] : null;
        },
        appendChild(child) {
            this.children.push(child);
            return child;
        },
        addEventListener(type, listener) {
            (listeners[type] = listeners[type] || []).push(listener);
        },
        focus() {},
    };
}

function meta(content) {
    return { getAttribute: (name) => (name === 'content' ? content : null) };
}

const navbar = element('div');
let banner = null;
const main = { parentNode: { insertBefore: (node) => { banner = node; } } };

const selectors = {
    'meta[name="gd-version-map"]': map === null ? null : meta(JSON.stringify(map)),
    'meta[name="quarto:offset"]': options.offset === undefined ? null : meta(options.offset),
    '.navbar .container-fluid': navbar,
    '#quarto-content': main,
};

const stored = {};
const window = { location: { pathname: options.pathname || '/index.html' } };
const context = {
    window,
    document: {
        readyState: options.loading ? 'loading' : 'complete',
        addEventListener() {},
        createElement: element,
        querySelector: (selector) => (selector in selectors ? selectors[selector] : null),
    },
    localStorage: {
        getItem: (key) => (key in stored ? stored[key] : null),
        setItem: (key, value) => { stored[key] = String(value); },
    },
};

vm.runInNewContext(fs.readFileSync(scriptPath, 'utf8'), context);

const versions = window.greatDocsVersions;
const selector = navbar.children.find((child) => child.attributes.role === 'navigation');
const dropdown = selector && selector.children.find((child) => child.attributes.role === 'menu');
const links = dropdown ? dropdown.children : [];

if (options.click !== undefined) {
    const link = links.find((child) => child.attributes['data-version'] === options.click);
    for (const listener of link.listeners.click || []) listener();
}

const result = {
    api: versions !== undefined,
    links: dropdown
        ? Object.fromEntries(links.map((child) => [child.attributes['data-version'], child.href]))
        : null,
    banner: banner ? (/href="([^"]*)"/.exec(banner.innerHTML) || [])[1] : null,
    stored: stored['great-docs-version'] === undefined ? null : stored['great-docs-version'],
};
if (versions) {
    const tags = options.tags || versions.list().map((version) => version.tag);
    result.current = versions.current();
    result.list = versions.list();
    result.urls = Object.fromEntries(tags.map((tag) => [tag, versions.urlFor(tag)]));
    const first = versions.list()[0];
    first.tag = 'changed';
    result.listIsCopy = versions.list()[0].tag !== 'changed';
}
process.stdout.write(JSON.stringify(result));
