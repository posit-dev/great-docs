// Run `reference-switcher.js` in a stub reference page and print the switcher's HTML, as JSON.
//
//     node reference_switcher_harness.js <reference-switcher.js> <options JSON>
//
// Options:
//
// - `sections`: the page's `data-gd-ref-sections`, such as `api,cli`
// - `pathname`: the open page, such as `/reference/cli/index.html` (default `/reference/index.html`)
//
// Prints:
//
// - `html`: the HTML of the switcher added to the sidebar, or `null` without a switcher

'use strict';

const fs = require('fs');
const vm = require('vm');

const [scriptPath, optionsJson] = process.argv.slice(2);
const options = JSON.parse(optionsJson);

function element(tag) {
    const listeners = {};
    return {
        tagName: tag.toUpperCase(),
        innerHTML: '',
        className: '',
        firstChild: null,
        listeners,
        addEventListener(type, listener) {
            (listeners[type] = listeners[type] || []).push(listener);
        },
        // The switcher's handlers look up the buttons it wrote as HTML, which the stub doesn't parse.
        querySelector: () => null,
        querySelectorAll: () => [],
    };
}

let switcher = null;
const menuContainer = element('div');
menuContainer.insertBefore = (node) => { switcher = node; };
const sidebar = element('nav');
sidebar.querySelector = (selector) =>
    selector === '.sidebar-menu-container' ? menuContainer : null;

const body = {
    getAttribute: (name) => (name === 'data-gd-ref-sections' ? options.sections : null),
};
const documentListeners = {};
const context = {
    window: { location: { pathname: options.pathname || '/reference/index.html' } },
    document: {
        // Pages load the script while the document is still being parsed.
        readyState: 'loading',
        body,
        addEventListener(type, listener) {
            (documentListeners[type] = documentListeners[type] || []).push(listener);
        },
        createElement: element,
        querySelector: (selector) => (selector === '.sidebar' ? sidebar : null),
    },
};

vm.runInNewContext(fs.readFileSync(scriptPath, 'utf8'), context);
for (const listener of documentListeners.DOMContentLoaded || []) listener();

process.stdout.write(JSON.stringify({ html: switcher ? switcher.innerHTML : null }));
