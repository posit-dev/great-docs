/**
 * WebMCP tools for Great Docs
 *
 * Registers tools with the browser's WebMCP API (`document.modelContext`) so that an AI
 * agent working in the browser can read the site. Page scripts can use the same tools in
 * every browser through `window.greatDocs.tools`:
 *
 * - `status`: `pending`, `registered`, `partial`, `failed`, `unavailable` or `off`
 * - `list()`: each tool's name, title, description, input schema and annotations
 * - `call(name, input)`: a promise of the tool's result, which never rejects
 * - `add(toolOrTools)`: registers more tools, returning `{added, rejected}`
 *
 * `<html data-gd-webmcp>` shows the status, and a `gd-webmcp:ready` event on `document`
 * carries `window.greatDocs.tools` once the browser has accepted or refused every tool.
 *
 * The build writes the settings to `<script type="application/json" id="gd-webmcp-settings">`.
 * A page with the `gd-no-webmcp` body class registers no tools.
 *
 * A result is a plain object. A tool never throws: it returns a failure as
 * `{error: {code, message}}`, because the browser passes a thrown error to the agent
 * without its message.
 */

(function () {
    'use strict';

    // Read while the script runs; it is null afterwards.
    var currentScript = document.currentScript;

    var SETTINGS_ID = 'gd-webmcp-settings';
    var OFF_CLASS = 'gd-no-webmcp';
    var STATUS_ATTRIBUTE = 'data-gd-webmcp';
    var READY_EVENT = 'gd-webmcp:ready';
    var NAME_PATTERN = /^[A-Za-z0-9_.-]{1,128}$/;
    var FETCH_TIMEOUT_MS = 10000;
    var DEFAULT_MAX_CHARS = 40000;
    var MIN_MAX_CHARS = 500;
    var MAX_MAX_CHARS = 500000;

    // Every tool Great Docs defines. A site's own tools can't take these names, even where
    // the site doesn't register the tool.
    var RESERVED_NAMES = [
        'get_site_overview',
        'get_current_page',
        'list_pages',
        'get_page',
        'search_docs',
        'list_api',
        'get_api_reference',
        'get_cli_help',
        'list_versions',
        'get_changelog',
        'get_agent_skill',
        'get_post_summary',
        'get_post_evidence',
        'get_post_next_steps',
        'open_page',
        'set_theme',
        'switch_version'
    ];

    var DEFAULT_SETTINGS = { markdown_pages: true, actions: true, js_api: true, exclude: [] };

    function readSettings() {
        var settings = Object.assign({}, DEFAULT_SETTINGS);
        var element = document.getElementById(SETTINGS_ID);
        if (!element) return settings;
        try {
            var parsed = JSON.parse(element.textContent);
            if (parsed && typeof parsed === 'object') {
                Object.keys(DEFAULT_SETTINGS).forEach(function (key) {
                    if (key in parsed) settings[key] = parsed[key];
                });
            }
        } catch (e) {
            console.warn('Great Docs WebMCP: ignoring unreadable settings.', e);
        }
        if (!Array.isArray(settings.exclude)) settings.exclude = [];
        return settings;
    }

    // The site root is the directory that holds this script.
    function readSiteRoot() {
        try {
            return new URL('.', (currentScript && currentScript.src) || location.href).href;
        } catch (e) {
            return location.origin + '/';
        }
    }

    // ------------------------------------------------------------------------------------
    // Results
    // ------------------------------------------------------------------------------------

    function errorResult(code, message, extra) {
        return { error: Object.assign({ code: code, message: message }, extra || {}) };
    }

    var warned = {};
    function warnOnce(key, message, error) {
        if (warned[key]) return;
        warned[key] = true;
        console.warn('Great Docs WebMCP: ' + message, error);
    }

    function messageOf(error) {
        return error && error.message ? String(error.message) : String(error);
    }

    // ------------------------------------------------------------------------------------
    // Input validation, for the subset of JSON Schema that tool inputs use
    // ------------------------------------------------------------------------------------

    function typeOf(value) {
        if (value === null) return 'null';
        if (Array.isArray(value)) return 'array';
        if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number';
        return typeof value;
    }

    function hasType(value, type) {
        var actual = typeOf(value);
        return actual === type || (type === 'number' && actual === 'integer');
    }

    // Return a message describing the first problem, or null when `value` matches `schema`.
    function validate(schema, value, label) {
        label = label || 'input';
        if (!schema || typeof schema !== 'object') return null;
        if (schema.type && !hasType(value, schema.type)) {
            return label + ' must be ' + (/^[aeiou]/.test(schema.type) ? 'an ' : 'a ') +
                schema.type + ', not ' + typeOf(value) + '.';
        }
        if (schema.enum && schema.enum.indexOf(value) === -1) {
            return label + ' must be one of ' + schema.enum.map(function (item) {
                return JSON.stringify(item);
            }).join(', ') + '.';
        }
        if (typeof value === 'number') {
            if (typeof schema.minimum === 'number' && value < schema.minimum) {
                return label + ' must be at least ' + schema.minimum + '.';
            }
            if (typeof schema.maximum === 'number' && value > schema.maximum) {
                return label + ' must be at most ' + schema.maximum + '.';
            }
        }
        if (typeof value === 'string') {
            if (typeof schema.minLength === 'number' && value.length < schema.minLength) {
                return label + ' must have at least ' + schema.minLength + ' characters.';
            }
            if (typeof schema.maxLength === 'number' && value.length > schema.maxLength) {
                return label + ' must have at most ' + schema.maxLength + ' characters.';
            }
        }
        if (Array.isArray(value) && schema.items) {
            for (var i = 0; i < value.length; i++) {
                var itemProblem = validate(schema.items, value[i], label + '[' + i + ']');
                if (itemProblem) return itemProblem;
            }
        }
        if (typeOf(value) === 'object') {
            var properties = schema.properties || {};
            var required = schema.required || [];
            for (var r = 0; r < required.length; r++) {
                if (!(required[r] in value)) return '"' + required[r] + '" is required.';
            }
            var keys = Object.keys(value);
            for (var k = 0; k < keys.length; k++) {
                var key = keys[k];
                if (key in properties) {
                    var problem = validate(properties[key], value[key], '"' + key + '"');
                    if (problem) return problem;
                } else if (schema.additionalProperties === false) {
                    var known = Object.keys(properties);
                    return 'Unknown property "' + key + '". ' + (known.length
                        ? 'Known properties: ' + known.join(', ') + '.'
                        : 'This tool takes no input.');
                }
            }
        }
        return null;
    }

    function withDefaults(schema, input) {
        var properties = (schema && schema.properties) || {};
        var result = Object.assign({}, input);
        Object.keys(properties).forEach(function (key) {
            var property = properties[key];
            if (!(key in result) && typeOf(property) === 'object' && 'default' in property) {
                result[key] = property.default;
            }
        });
        return result;
    }

    // ------------------------------------------------------------------------------------
    // Tools
    // ------------------------------------------------------------------------------------

    var EMPTY_SCHEMA = { type: 'object', properties: {}, additionalProperties: false };

    function defineTool(spec) {
        return {
            name: spec.name,
            title: spec.title || '',
            description: spec.description,
            inputSchema: spec.inputSchema || EMPTY_SCHEMA,
            annotations: spec.annotations || {},
            example: spec.example || {},
            action: Boolean(spec.action),
            run: spec.run
        };
    }

    function describe(tool) {
        return JSON.parse(JSON.stringify({
            name: tool.name,
            title: tool.title,
            description: tool.description,
            inputSchema: tool.inputSchema,
            annotations: tool.annotations
        }));
    }

    function cancelled() {
        return errorResult('unavailable', 'The call was cancelled.');
    }

    // Run a tool, returning its failures as data.
    function invoke(tool, input, signal) {
        if (input === undefined || input === null) input = {};
        if (typeof input === 'string') {
            try {
                input = JSON.parse(input);
            } catch (e) {
                return Promise.resolve(errorResult('invalid_input', 'The input is not JSON.', {
                    inputSchema: tool.inputSchema, example: tool.example
                }));
            }
        }
        var problem = validate(tool.inputSchema, input);
        if (problem) {
            return Promise.resolve(errorResult('invalid_input', problem, {
                inputSchema: tool.inputSchema, example: tool.example
            }));
        }
        return new Promise(function (resolve) {
            resolve(tool.run(withDefaults(tool.inputSchema, input), { signal: signal }));
        }).then(function (result) {
            return result === undefined ? {} : result;
        }, function (error) {
            if (signal && signal.aborted) return cancelled();
            warnOnce('run:' + tool.name, tool.name + ' failed.', error);
            return errorResult('internal', tool.name + ' failed: ' + messageOf(error));
        });
    }

    // ------------------------------------------------------------------------------------
    // Fetching site files, with one request per URL however many tools ask for it
    // ------------------------------------------------------------------------------------

    var fetches = {};

    function FetchError(message, status) {
        this.name = 'FetchError';
        this.message = message;
        this.status = status;
    }
    FetchError.prototype = Object.create(Error.prototype);

    function load(url) {
        var controller = typeof AbortController === 'function' ? new AbortController() : null;
        var timedOut = false;
        var timer = setTimeout(function () {
            timedOut = true;
            if (controller) controller.abort();
        }, FETCH_TIMEOUT_MS);
        return fetch(url, controller ? { signal: controller.signal } : undefined)
            .then(function (response) {
                if (!response.ok) throw new FetchError('HTTP ' + response.status, response.status);
                return response.text();
            })
            .then(function (text) {
                clearTimeout(timer);
                return text;
            }, function (error) {
                clearTimeout(timer);
                if (error instanceof FetchError) throw error;
                throw new FetchError(timedOut ? 'timed out' : messageOf(error));
            });
    }

    // Settle with the request, or reject when `signal` aborts. A caller that stops waiting
    // doesn't cancel the request, which other callers may share.
    function waitFor(promise, signal) {
        if (!signal) return promise;
        if (signal.aborted) return Promise.reject(new FetchError('cancelled'));
        return new Promise(function (resolve, reject) {
            function onAbort() {
                reject(new FetchError('cancelled'));
            }
            signal.addEventListener('abort', onAbort, { once: true });
            promise.then(function (value) {
                signal.removeEventListener('abort', onAbort);
                resolve(value);
            }, function (error) {
                signal.removeEventListener('abort', onAbort);
                reject(error);
            });
        });
    }

    // Fetch a file's text. A failed request isn't kept, so a later call tries again.
    function fetchText(url, signal) {
        var request = fetches[url];
        if (!request) {
            request = fetches[url] = load(url);
            request.catch(function () {
                if (fetches[url] === request) delete fetches[url];
            });
        }
        return waitFor(request, signal);
    }

    // ------------------------------------------------------------------------------------
    // Markdown
    // ------------------------------------------------------------------------------------

    var FENCE = /^ {0,3}(`{3,}|~{3,})/;
    var ATX_HEADING = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$/;
    var ATTRIBUTES = /[ \t]*\{([^{}]*)\}$/;

    // Call `visit(line)` for each line outside front matter and code blocks, and return the
    // fence that leaves a code block open at the end, or null.
    function eachProseLine(markdown, visit) {
        var lines = markdown.split('\n');
        var start = 0;
        if (/^---[ \t]*$/.test(lines[0])) {
            for (var f = 1; f < lines.length; f++) {
                if (/^(---|\.\.\.)[ \t]*$/.test(lines[f])) {
                    start = f + 1;
                    break;
                }
            }
        }
        var fence = null;
        for (var i = start; i < lines.length; i++) {
            var line = lines[i];
            var match = FENCE.exec(line);
            if (fence) {
                if (match && match[1].charAt(0) === fence.charAt(0) &&
                    match[1].length >= fence.length && !line.slice(match[0].length).trim()) {
                    fence = null;
                }
            } else if (match) {
                fence = match[1];
            } else {
                visit(line);
            }
        }
        return fence;
    }

    function plainText(markdown) {
        return markdown
            .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
            .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
            .replace(/[`*]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
    }

    // Pandoc's identifier for a heading without an explicit one.
    function slug(text) {
        var id = text.toLowerCase()
            .replace(/[^\p{L}\p{N}_.\-\s]/gu, '')
            .trim()
            .replace(/\s+/g, '-')
            .replace(/^[^\p{L}]+/u, '');
        return id || 'section';
    }

    // The headings outside code blocks, as `[{level, text, anchor}]`.
    function headings(markdown) {
        var result = [];
        var seen = {};
        eachProseLine(markdown, function (line) {
            var match = ATX_HEADING.exec(line);
            if (!match) return;
            var text = (match[2] || '').replace(/(^|[ \t]+)#+$/, '');
            var anchor = null;
            var attributes = ATTRIBUTES.exec(text);
            if (attributes) {
                text = text.slice(0, attributes.index);
                var id = /(?:^|\s)#([^\s}]+)/.exec(attributes[1]);
                if (id) anchor = id[1];
            }
            text = plainText(text);
            if (!text) return;
            if (!anchor) {
                var base = slug(text);
                anchor = base;
                // Pandoc numbers a repeated identifier from 1.
                for (var n = 1; seen[anchor]; n++) anchor = base + '-' + n;
            }
            seen[anchor] = true;
            result.push({ level: match[1].length, text: text, anchor: anchor });
        });
        return result;
    }

    function cut(markdown, limit) {
        var end = markdown.lastIndexOf('\n', limit);
        // Cut at a line break unless the last one is far from the limit.
        if (end < limit * 0.8) end = limit;
        var text = markdown.slice(0, end);
        var fence = eachProseLine(text, function () {});
        return fence ? text + '\n' + fence : text;
    }

    // Shorten Markdown to at most `maxChars` characters, closing a code block it cuts.
    function truncate(markdown, maxChars) {
        if (markdown.length <= maxChars) return { text: markdown, truncated: false };
        var text = cut(markdown, maxChars);
        for (var limit = maxChars; text.length > maxChars && limit > 0;) {
            limit -= text.length - maxChars;
            text = cut(markdown, limit);
        }
        return { text: text, truncated: true };
    }

    // ------------------------------------------------------------------------------------
    // Pages
    // ------------------------------------------------------------------------------------

    function decode(path) {
        try {
            return decodeURIComponent(path);
        } catch (e) {
            return path;
        }
    }

    // A page's path relative to the site root, as Quarto writes it: `user-guide/intro.html`.
    function pagePath(pathname, rootPathname) {
        var path = decode(pathname);
        var root = decode(rootPathname);
        path = path.indexOf(root) === 0 ? path.slice(root.length) : path.replace(/^\/+/, '');
        if (path === '' || path.charAt(path.length - 1) === '/') return path + 'index.html';
        return /\.html?$/.test(path) ? path : path + '.html';
    }

    // The Markdown copy of a page, which sits beside it.
    function markdownPath(htmlPath) {
        return htmlPath.replace(/\.html?$/, '.md');
    }

    var SKIPPED_ELEMENTS = /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|BUTTON|SVG|NAV|FORM|IFRAME|SELECT)$/;
    var BLOCK_ELEMENTS = new RegExp('^(P|DIV|SECTION|ARTICLE|ASIDE|HEADER|FOOTER|MAIN|UL|OL|LI|' +
        'DL|DT|DD|TABLE|TR|BLOCKQUOTE|FIGURE|FIGCAPTION|DETAILS|SUMMARY)$');

    function attribute(element, name) {
        return typeof element.getAttribute === 'function' ? element.getAttribute(name) : null;
    }

    function headingAnchor(element) {
        var parent = element.parentNode;
        return attribute(element, 'data-anchor-id') || element.id ||
            (parent && String(parent.nodeName).toUpperCase() === 'SECTION' && parent.id) || null;
    }

    // The text of a page's main content, as Markdown with its headings, lists and code.
    function domContent(root) {
        var blocks = [];
        var outline = [];
        var line = '';
        function flush() {
            var text = line.replace(/\s+/g, ' ').trim();
            if (text) blocks.push(text);
            line = '';
        }
        function visit(node) {
            if (node.nodeType === 3) {
                line += node.nodeValue;
                return;
            }
            if (node.nodeType !== 1) return;
            var tag = String(node.nodeName).toUpperCase();
            if (SKIPPED_ELEMENTS.test(tag) || node.hidden ||
                attribute(node, 'aria-hidden') === 'true') {
                return;
            }
            var heading = /^H([1-6])$/.exec(tag);
            if (heading) {
                flush();
                var text = String(node.textContent || '').replace(/\s+/g, ' ').trim();
                if (text) {
                    var level = Number(heading[1]);
                    blocks.push(new Array(level + 1).join('#') + ' ' + text);
                    outline.push({ level: level, text: text, anchor: headingAnchor(node) });
                }
                return;
            }
            if (tag === 'PRE') {
                flush();
                blocks.push('```\n' + String(node.textContent || '').replace(/\n$/, '') + '\n```');
                return;
            }
            if (tag === 'BR') {
                flush();
                return;
            }
            var block = BLOCK_ELEMENTS.test(tag);
            if (block) flush();
            if (tag === 'LI') line += '- ';
            var children = node.childNodes || [];
            for (var i = 0; i < children.length; i++) visit(children[i]);
            if (block) flush();
        }
        visit(root);
        flush();
        return { markdown: blocks.join('\n\n'), outline: outline };
    }

    function pageTitle() {
        var heading = document.querySelector('h1.title') || document.querySelector('main h1');
        var text = heading ? String(heading.textContent || '').replace(/\s+/g, ' ').trim() : '';
        return text || document.title || '';
    }

    // The open page as Markdown and an outline, from its `.md` copy where there is one.
    function currentPageContent(signal) {
        var path = pagePath(location.pathname, new URL(siteRoot).pathname);
        function fromDom(note) {
            var main = document.querySelector('main') || document.body;
            var content = domContent(main);
            return { path: path, source: 'dom', markdown: content.markdown,
                outline: content.outline, note: note };
        }
        if (!settings.markdown_pages) return Promise.resolve(fromDom(null));
        var url = new URL(markdownPath(path), siteRoot).href;
        return fetchText(url, signal).then(function (markdown) {
            return { path: path, source: 'markdown', markdown: markdown,
                outline: headings(markdown), note: null };
        }, function (error) {
            if (signal && signal.aborted) throw error;
            return fromDom('The Markdown copy could not be loaded (' + messageOf(error) +
                '), so this is the text of the page.');
        });
    }

    var GET_CURRENT_PAGE = defineTool({
        name: 'get_current_page',
        title: 'Get the current page',
        description:
            'Get the documentation page the user has open, as Markdown or as an outline of ' +
            'its headings. Markdown longer than max_chars is cut at a line break and the ' +
            'result has truncated: true and the outline of the whole page.',
        inputSchema: {
            type: 'object',
            properties: {
                format: {
                    type: 'string',
                    enum: ['markdown', 'outline'],
                    default: 'markdown',
                    description: '"markdown" for the page text, "outline" for its headings only.'
                },
                max_chars: {
                    type: 'integer',
                    minimum: MIN_MAX_CHARS,
                    maximum: MAX_MAX_CHARS,
                    default: DEFAULT_MAX_CHARS,
                    description: 'The most characters of Markdown to return.'
                }
            },
            additionalProperties: false
        },
        example: { format: 'outline' },
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            return currentPageContent(context.signal).then(function (content) {
                var result = {
                    url: location.href.split('#')[0],
                    path: content.path,
                    title: pageTitle(),
                    format: input.format,
                    source: content.source
                };
                if (content.note) result.note = content.note;
                if (input.format === 'outline') {
                    result.outline = content.outline;
                    return result;
                }
                var shortened = truncate(content.markdown, input.max_chars);
                result.markdown = shortened.text;
                result.truncated = shortened.truncated;
                if (shortened.truncated) {
                    result.total_chars = content.markdown.length;
                    result.outline = content.outline;
                }
                return result;
            }, function () {
                return cancelled();
            });
        }
    });

    var BUILT_IN_TOOLS = [GET_CURRENT_PAGE];

    // ------------------------------------------------------------------------------------
    // Registration
    // ------------------------------------------------------------------------------------

    function findModelContext() {
        var candidates = [document.modelContext, navigator.modelContext];
        for (var i = 0; i < candidates.length; i++) {
            var candidate = candidates[i];
            if (candidate && typeof candidate.registerTool === 'function') return candidate;
        }
        return null;
    }

    // Aborting this signal unregisters every tool.
    var registrations = typeof AbortController === 'function' ? new AbortController() : null;

    // Settle once the browser accepts or refuses the tool.
    function registerWithBrowser(modelContext, tool) {
        var definition = {
            name: tool.name,
            title: tool.title,
            description: tool.description,
            inputSchema: tool.inputSchema,
            annotations: tool.annotations,
            execute: function (input, options) {
                return invoke(tool, input, options && options.signal);
            }
        };
        return new Promise(function (resolve) {
            resolve(modelContext.registerTool(
                definition, registrations ? { signal: registrations.signal } : undefined
            ));
        });
    }

    function checkTool(tool, tools) {
        if (!tool || typeof tool !== 'object') return 'A tool must be an object.';
        if (typeof tool.name !== 'string' || !NAME_PATTERN.test(tool.name)) {
            return 'The name must be 1 to 128 letters, digits, "_", "-" or ".".';
        }
        if (RESERVED_NAMES.indexOf(tool.name) !== -1) {
            return 'Great Docs defines a tool with this name.';
        }
        if (tools[tool.name]) return 'A tool with this name is already registered.';
        if (typeof tool.description !== 'string' || !tool.description.trim()) {
            return 'The description must be a non-empty string.';
        }
        if (typeof tool.execute !== 'function') return 'execute must be a function.';
        if (tool.inputSchema !== undefined &&
            (typeOf(tool.inputSchema) !== 'object' || tool.inputSchema.type !== 'object')) {
            return 'inputSchema must be a JSON Schema with type "object".';
        }
        if (tool.title !== undefined && typeof tool.title !== 'string') {
            return 'The title must be a string.';
        }
        if (tool.annotations !== undefined && typeOf(tool.annotations) !== 'object') {
            return 'annotations must be an object.';
        }
        return null;
    }

    var settings = readSettings();
    var siteRoot = readSiteRoot();
    var off = Boolean(document.body && document.body.classList &&
        document.body.classList.contains(OFF_CLASS));
    var status = 'pending';
    var tools = {};
    var order = [];

    function addTool(tool) {
        tools[tool.name] = tool;
        order.push(tool.name);
    }

    if (!off) {
        BUILT_IN_TOOLS.forEach(function (tool) {
            if (settings.exclude.indexOf(tool.name) !== -1) return;
            if (tool.action && !settings.actions) return;
            addTool(tool);
        });
    }
    var modelContext = off ? null : findModelContext();

    var api = {
        get status() {
            return status;
        },
        list: function () {
            return order.map(function (name) {
                return describe(tools[name]);
            });
        },
        call: function (name, input) {
            if (off) {
                return Promise.resolve(errorResult('unavailable', 'WebMCP is off on this page.'));
            }
            var tool = tools[name];
            if (!tool) {
                var message = 'No tool is named "' + name + '".';
                return Promise.resolve(errorResult('not_found', message, {
                    candidates: order.slice()
                }));
            }
            return invoke(tool, input, undefined);
        },
        add: function (toolOrTools) {
            var added = [];
            var rejected = [];
            var candidates = Array.isArray(toolOrTools) ? toolOrTools : [toolOrTools];
            candidates.forEach(function (candidate) {
                var reason = off ? 'WebMCP is off on this page.' : checkTool(candidate, tools);
                if (reason) {
                    var named = candidate && typeof candidate.name === 'string';
                    rejected.push({ name: named ? candidate.name : null, reason: reason });
                    return;
                }
                var tool = defineTool({
                    name: candidate.name,
                    title: candidate.title,
                    description: candidate.description,
                    inputSchema: candidate.inputSchema,
                    annotations: candidate.annotations,
                    run: function (input, context) {
                        return candidate.execute(input, context);
                    }
                });
                addTool(tool);
                added.push(tool.name);
                if (modelContext) {
                    registerWithBrowser(modelContext, tool).catch(function (error) {
                        var message = 'The browser refused ' + tool.name + '.';
                        warnOnce('register:' + tool.name, message, error);
                    });
                }
            });
            return { added: added, rejected: rejected };
        }
    };

    if (window.__GD_WEBMCP_TEST__) {
        api._internals = {
            settings: settings,
            siteRoot: siteRoot,
            reservedNames: RESERVED_NAMES.slice(),
            validate: validate,
            headings: headings,
            truncate: truncate,
            slug: slug,
            pagePath: pagePath,
            markdownPath: markdownPath,
            domContent: domContent,
            fetchText: fetchText
        };
    }

    function setStatus(value) {
        status = value;
        document.documentElement.setAttribute(STATUS_ATTRIBUTE, value);
    }

    function finish(value) {
        setStatus(value);
        if (settings.js_api) {
            document.dispatchEvent(new CustomEvent(READY_EVENT, { detail: api }));
        }
    }

    setStatus('pending');
    if (settings.js_api) {
        window.greatDocs = window.greatDocs || {};
        window.greatDocs.tools = api;
    }

    if (off || order.length === 0) {
        finish('off');
    } else if (!modelContext) {
        finish('unavailable');
    } else {
        var pending = order.map(function (name) {
            return registerWithBrowser(modelContext, tools[name]).then(function () {
                return true;
            }, function (error) {
                warnOnce('register:' + name, 'The browser refused ' + name + '.', error);
                return false;
            });
        });
        Promise.all(pending).then(function (accepted) {
            var count = accepted.filter(Boolean).length;
            finish(count === accepted.length ? 'registered' : count ? 'partial' : 'failed');
        });
    }
})();
