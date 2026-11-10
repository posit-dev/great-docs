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

    // `features` names the site's features that tools beyond the site tools need.
    var DEFAULT_SETTINGS = {
        markdown_pages: true, features: {}, actions: true, js_api: true, exclude: []
    };

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
        if (typeOf(settings.features) !== 'object') settings.features = {};
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
            purpose: spec.purpose || spec.title || '',
            description: spec.description,
            inputSchema: spec.inputSchema || EMPTY_SCHEMA,
            annotations: spec.annotations || {},
            example: spec.example || {},
            feature: spec.feature || 'site',
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

    // Call `visit(line, index)` for each line outside front matter and code blocks, and
    // return the fence that leaves a code block open at the end, or null.
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
                visit(line, i);
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

    // The headings outside code blocks, as `[{level, text, anchor, line}]`.
    function parseHeadings(markdown) {
        var result = [];
        var seen = {};
        eachProseLine(markdown, function (line, index) {
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
            result.push({ level: match[1].length, text: text, anchor: anchor, line: index });
        });
        return result;
    }

    // The outline of a page: its headings as `[{level, text, anchor}]`.
    function headings(markdown) {
        return parseHeadings(markdown).map(function (heading) {
            return { level: heading.level, text: heading.text, anchor: heading.anchor };
        });
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

    function currentPath() {
        return pagePath(location.pathname, new URL(siteRoot).pathname);
    }

    // The open page as Markdown and an outline, from its `.md` copy where there is one.
    function currentPageContent(signal) {
        var path = currentPath();
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
        purpose: 'The open page as Markdown, or as an outline of its headings',
        description:
            'Use this when the user asks about the page they have open. Returns it as ' +
            'Markdown, or as an outline of its headings with format "outline". Markdown ' +
            'longer than max_chars is cut at a line break, with truncated: true and the ' +
            'outline of the whole page. For another page, use get_page. Example: "Summarise ' +
            'this page."',
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

    // ------------------------------------------------------------------------------------
    // The site's manifest and search index
    // ------------------------------------------------------------------------------------

    var MANIFEST_FILE = 'gd-webmcp.json';
    var SEARCH_FILE = 'search.json';
    var FALLBACK_FILES = ['llms.txt', 'llms-full.txt', SEARCH_FILE];
    var NOT_FOUND_HINT = 'Call list_pages to see every page, or search_docs to search them.';

    function absolute(path) {
        return new URL(path, siteRoot).href;
    }

    var loaded = {};

    // Fetch and parse a JSON file of the site once, keeping `prepare(data)`.
    function loadJson(file, signal, prepare) {
        var request = loaded[file];
        if (!request) {
            request = loaded[file] = fetchText(absolute(file)).then(function (text) {
                return prepare(JSON.parse(text));
            });
            request.catch(function () {
                if (loaded[file] === request) delete loaded[file];
            });
        }
        return waitFor(request, signal);
    }

    function loadManifest(signal) {
        return loadJson(MANIFEST_FILE, signal, function (manifest) {
            ['sections', 'pages', 'api', 'cli'].forEach(function (key) {
                if (!Array.isArray(manifest[key])) manifest[key] = [];
            });
            manifest.site = manifest.site || {};
            manifest.resources = manifest.resources || {};
            return manifest;
        });
    }

    var ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'" };

    // Quarto's search index, with an entry for each page and each section of a page.
    function loadSearch(signal) {
        return loadJson(SEARCH_FILE, signal, function (entries) {
            return (Array.isArray(entries) ? entries : []).map(function (entry) {
                var href = String(entry.href || '');
                var parts = href.split('#');
                var section = String(entry.section || '');
                var text = String(entry.text || '').replace(/&(amp|lt|gt|quot|#39);/g,
                    function (all, name) {
                        return ENTITIES[name];
                    });
                // A section's text starts with its heading.
                if (section && text.indexOf(section) === 0) text = text.slice(section.length);
                return {
                    path: parts[0],
                    anchor: parts[1] || '',
                    href: href,
                    title: String(entry.title || ''),
                    section: section,
                    text: text.trim()
                };
            });
        });
    }

    // A failed load as a result, with files the agent can read instead.
    function loadFailed(file, error, signal) {
        if (signal && signal.aborted) return cancelled();
        var message = file + ' could not be loaded (' + messageOf(error) + ').';
        return errorResult('fetch_failed', message, {
            fallback: FALLBACK_FILES.filter(function (name) {
                return name !== file;
            }).map(absolute)
        });
    }

    // ------------------------------------------------------------------------------------
    // Words, for matching pages and searching
    // ------------------------------------------------------------------------------------

    var WORD = /[\p{L}\p{N}]+(?:[._][\p{L}\p{N}]+)*/gu;
    var STOP_WORDS = new Set(('a an and are as at be by can do does for from how i if in is ' +
        'it my of on or that the this to what when where which why with').split(' '));

    // The lowercase words of `text`. An identifier such as `GT.fmt_number` is kept whole as
    // well as split into `gt`, `fmt_number`, `fmt` and `number`.
    function tokenize(text) {
        var tokens = new Set();
        (String(text || '').toLowerCase().match(WORD) || []).forEach(function (word) {
            tokens.add(word);
            if (/[._]/.test(word)) {
                word.split('.').concat(word.split(/[._]/)).forEach(function (part) {
                    tokens.add(part);
                });
            }
        });
        return tokens;
    }

    // The words of a query, without words like "how" and "the" unless it has only those.
    function queryWords(text) {
        var all = Array.from(tokenize(text));
        var words = all.filter(function (word) {
            return !STOP_WORDS.has(word);
        });
        return words.length ? words : all;
    }

    // A word without a common ending, so that "deploying" and "deployment" match.
    function stem(word) {
        var base = word.replace(/(?:ments?|ings?|ions?|ers?|ed|([^s])s)$/, '$1');
        return base.length >= 3 ? base : word;
    }

    // The words of `text` and their stems.
    function terms(text) {
        var words = tokenize(text);
        var stems = new Set();
        words.forEach(function (word) {
            stems.add(stem(word));
        });
        return { words: words, stems: stems };
    }

    // 1 when `found` holds `word`, 0.5 when it holds a word with the same stem or a longer
    // word starting with it.
    function wordMatch(found, word) {
        if (found.words.has(word)) return 1;
        if (found.stems.has(stem(word))) return 0.5;
        if (word.length < 4) return 0;
        for (var other of found.words) {
            if (other.length > word.length && other.indexOf(word) === 0) return 0.5;
        }
        return 0;
    }

    // ------------------------------------------------------------------------------------
    // Finding pages and sections
    // ------------------------------------------------------------------------------------

    // A page's file name without its extension, then without a numeric prefix: `47-webmcp`
    // and `webmcp`. An index page takes its folder's name.
    function pageNames(path) {
        var parts = path.toLowerCase().replace(/\.html?$/, '').split('/');
        var name = parts.pop();
        if (name === 'index' && parts.length) name = parts.pop();
        return [name, name.replace(/^\d+[-_]/, '')];
    }

    function brief(page) {
        return { title: page.title, url: absolute(page.path), kind: page.kind };
    }

    // The one page in `pages`, an `ambiguous` error for several, or null for none.
    function onePage(pages, query, match) {
        if (pages.length === 1) return { page: pages[0], match: match };
        if (!pages.length) return null;
        return { error: errorResult('ambiguous', 'Several pages match "' + query + '".', {
            candidates: pages.slice(0, 5).map(brief),
            hint: 'Pass one of their URLs.'
        }) };
    }

    // The page path a query would be as a path or URL, or null for a URL outside the site.
    function queryPath(query) {
        var root = new URL(siteRoot);
        var target = query.split('#')[0];
        if (/^[a-z][a-z0-9+.-]*:/i.test(target)) {
            var url;
            try {
                url = new URL(target);
            } catch (e) {
                return null;
            }
            var inside = decode(url.pathname).indexOf(decode(root.pathname)) === 0;
            if (url.origin !== root.origin || !inside) return null;
            target = url.pathname;
        }
        return pagePath(target.replace(/\.(md|qmd|ipynb)$/, '.html'), root.pathname);
    }

    // Find the page `query` names: by its path or URL, an API name, its title or its file
    // name, or failing those, the page sharing the most words with it by title, file name
    // and description.
    function resolvePage(manifest, query) {
        var pages = manifest.pages;
        var text = query.trim();
        var lower = text.toLowerCase();
        var path = queryPath(text);
        if (path === null) {
            return { error: errorResult('not_found', text + ' is not a page of this site.', {
                hint: 'Pass a page under ' + siteRoot + '.'
            }) };
        }
        var paths = [path, path.replace(/\.html$/, '/index.html')];
        var named = [];
        manifest.api.forEach(function (item) {
            if (item.name !== text && (item.aliases || []).indexOf(text) === -1) return;
            var page = pages.filter(function (p) {
                return p.path === item.path;
            })[0] || { path: item.path, md: item.md, title: item.name, kind: 'api' };
            if (named.indexOf(page) === -1) named.push(page);
        });
        var found = onePage(pages.filter(function (page) {
            return paths.indexOf(page.path) !== -1;
        }), text, 'path') || onePage(named, text, 'api') || onePage(pages.filter(function (page) {
            return String(page.title || '').toLowerCase() === lower;
        }), text, 'title') || onePage(pages.filter(function (page) {
            return pageNames(page.path).indexOf(lower.replace(/\s+/g, '-')) !== -1;
        }), text, 'name');
        if (found) {
            var hash = text.indexOf('#');
            if (found.match === 'path' && hash !== -1) found.anchor = text.slice(hash + 1);
            return found;
        }
        var words = queryWords(text);
        var scored = pages.map(function (page) {
            var fields = [[terms(page.title), 3], [terms(pageNames(page.path)[1]), 2],
                [terms(page.description), 1]];
            var score = 0;
            words.forEach(function (word) {
                fields.forEach(function (field) {
                    score += field[1] * wordMatch(field[0], word);
                });
            });
            return { page: page, score: score };
        }).filter(function (item) {
            return item.score > 0;
        }).sort(function (a, b) {
            return b.score - a.score;
        });
        if (!scored.length) {
            return { error: errorResult('not_found', 'No page matches "' + text + '".', {
                hint: NOT_FOUND_HINT
            }) };
        }
        // A runner-up within 10% of the best makes the match ambiguous.
        return onePage(scored.filter(function (item) {
            return item.score >= scored[0].score * 0.9;
        }).map(function (item) {
            return item.page;
        }), text, 'words');
    }

    // The headings a section query names: an anchor, with or without `#`, or a heading's
    // text. `anchors` maps the anchors of the rendered page to their headings' text; a
    // heading found through one takes that anchor.
    function findSections(list, query, anchors) {
        var wanted = query.replace(/^#/, '').trim();
        var lower = wanted.toLowerCase();
        var tests = [
            function (h) { return h.anchor === wanted; },
            function (h) { return h.anchor.toLowerCase() === lower; },
            function (h) { return anchors[wanted] === h.text; },
            function (h) { return h.text.toLowerCase() === lower; },
            function (h) { return slug(h.text) === slug(wanted); },
            function (h) { return h.text.toLowerCase().indexOf(lower) !== -1; }
        ];
        for (var i = 0; i < tests.length; i++) {
            var matches = list.filter(tests[i]);
            if (matches.length) {
                return i === 2 ? matches.map(function (h) {
                    return Object.assign({}, h, { anchor: wanted });
                }) : matches;
            }
        }
        return [];
    }

    // A section of a page: its heading and what follows, up to the next heading of the same
    // or a higher level.
    function sliceSection(markdown, heading, list) {
        var next = list.filter(function (h) {
            return h.line > heading.line && h.level <= heading.level;
        })[0];
        var lines = markdown.split('\n');
        return lines.slice(heading.line, next ? next.line : lines.length).join('\n')
            .replace(/\s+$/, '') + '\n';
    }

    function outlineOf(heading) {
        return { level: heading.level, text: heading.text, anchor: heading.anchor };
    }

    // The section of a page that `query` names, as `{heading, list}` or `{error}`.
    function pageSection(page, markdown, query, signal) {
        var list = parseHeadings(markdown);
        function pick(anchors) {
            var matches = findSections(list, query, anchors);
            if (matches.length === 1) return { heading: matches[0], list: list };
            if (!matches.length) return null;
            return errorResult('ambiguous', 'Several sections match "' + query + '".', {
                candidates: matches.map(outlineOf)
            });
        }
        var notFound = errorResult('not_found', 'No section of ' + page.path + ' matches "' +
            query + '".', { candidates: list.map(outlineOf) });
        var found = pick({});
        if (found) return Promise.resolve(found);
        // The rendered page's anchors can differ from those of its Markdown copy.
        return loadSearch(signal).then(function (entries) {
            var anchors = {};
            entries.forEach(function (entry) {
                if (entry.path === page.path && entry.anchor) {
                    anchors[entry.anchor] = entry.section;
                }
            });
            return pick(anchors) || notFound;
        }, function () {
            return notFound;
        });
    }

    // ------------------------------------------------------------------------------------
    // Searching
    // ------------------------------------------------------------------------------------

    var EXCERPT_CHARS = 240;

    // About `EXCERPT_CHARS` characters of `text` from a little before `position`, cut
    // between words.
    function excerpt(text, position) {
        text = text.replace(/\s+/g, ' ').trim();
        var start = Math.max(0, Math.min(position - 60, text.length - EXCERPT_CHARS));
        if (start > 0) start = text.indexOf(' ', start) + 1 || start;
        var end = Math.min(text.length, start + EXCERPT_CHARS);
        var space = text.lastIndexOf(' ', end);
        if (end < text.length && space > start) end = space;
        return (start > 0 ? '…' : '') + text.slice(start, end) +
            (end < text.length ? '…' : '');
    }

    // Score a search entry. The query as a phrase counts 10 in the page title, 6 in the
    // section's heading and 3 in its text; each of its words counts 3, 2 and 1.
    function scoreEntry(entry, phrase, words) {
        if (!entry.tokens) {
            entry.fields = [entry.title, entry.section, entry.text].map(function (field) {
                return field.toLowerCase();
            });
            entry.tokens = entry.fields.map(terms);
        }
        var score = 0;
        [10, 6, 3].forEach(function (weight, i) {
            if (entry.fields[i].indexOf(phrase) !== -1) score += weight;
        });
        words.forEach(function (word) {
            [3, 2, 1].forEach(function (weight, i) {
                score += weight * wordMatch(entry.tokens[i], word);
            });
        });
        return score;
    }

    // The values a search scope can take: "all", the kinds of page and the section ids.
    function scopes(manifest) {
        var values = ['all'];
        function add(value) {
            if (value && values.indexOf(value) === -1) values.push(value);
        }
        manifest.pages.forEach(function (page) {
            add(page.kind);
        });
        manifest.sections.forEach(function (section) {
            if (section.kind === 'blog') add('blog');
            add(section.id);
        });
        return values;
    }

    // A test of whether a scope keeps a page, or null for an unknown scope.
    function scopeFilter(manifest, scope) {
        var wanted = scope.toLowerCase();
        if (wanted === 'all') return function () { return true; };
        var section = manifest.sections.filter(function (s) {
            return s.id.toLowerCase() === wanted || String(s.title).toLowerCase() === wanted;
        })[0];
        if (section) return function (page) { return page.section === section.id; };
        if (scopes(manifest).indexOf(wanted) === -1) return null;
        var blogs = manifest.sections.filter(function (s) {
            return s.kind === 'blog';
        }).map(function (s) {
            return s.id;
        });
        return function (page) {
            return page.kind === wanted ||
                (wanted === 'blog' && blogs.indexOf(page.section) !== -1);
        };
    }

    function search(manifest, entries, input) {
        var keep = scopeFilter(manifest, input.scope);
        if (!keep) {
            return errorResult('not_found', 'No scope is named "' + input.scope + '".', {
                candidates: scopes(manifest)
            });
        }
        var words = queryWords(input.query);
        if (!words.length) return errorResult('invalid_input', 'The query has no words.');
        var phrase = input.query.toLowerCase().replace(/\s+/g, ' ').trim();
        var pages = {};
        manifest.pages.forEach(function (page) {
            pages[page.path] = page;
        });
        // A query that is an API name adds 4 to that object's page.
        var named = {};
        manifest.api.forEach(function (item) {
            [item.name].concat(item.aliases || []).forEach(function (name) {
                named[name.toLowerCase()] = item.path;
            });
        });
        var hits = [];
        entries.forEach(function (entry, i) {
            var page = pages[entry.path];
            if (!page || !keep(page)) return;
            var score = scoreEntry(entry, phrase, words) + (named[phrase] === entry.path ? 4 : 0);
            if (score > 0) hits.push({ entry: entry, page: page, score: score, i: i });
        });
        hits.sort(function (a, b) {
            return b.score - a.score || a.i - b.i;
        });
        var perPage = {};
        var results = [];
        hits.forEach(function (hit) {
            var entry = hit.entry;
            perPage[entry.path] = (perPage[entry.path] || 0) + 1;
            if (perPage[entry.path] > 2 || results.length >= input.limit) return;
            var at = [phrase].concat(words).map(function (word) {
                return entry.fields[2].indexOf(word);
            }).filter(function (index) {
                return index !== -1;
            })[0];
            results.push(compact({
                title: hit.page.title || entry.title,
                section: entry.section,
                url: absolute(entry.href),
                kind: hit.page.kind,
                score: Math.round(hit.score * 10) / 10,
                excerpt: excerpt(entry.text, at || 0)
            }));
        });
        var result = { url: siteRoot, query: input.query, scope: input.scope, results: results };
        if (!results.length) result.hint = 'Try other words, or call list_pages.';
        return result;
    }

    // ------------------------------------------------------------------------------------
    // Site tools
    // ------------------------------------------------------------------------------------

    // Drop the empty fields of a result.
    function compact(object) {
        Object.keys(object).forEach(function (key) {
            var value = object[key];
            if (value === undefined || value === null || value === '' ||
                (Array.isArray(value) && !value.length)) {
                delete object[key];
            }
        });
        return object;
    }

    var GET_SITE_OVERVIEW = defineTool({
        name: 'get_site_overview',
        title: 'Get the site overview',
        purpose: "The package, its version and install commands, the site's sections and " +
            'these tools',
        description:
            'Use this first to learn what this documentation site covers. Returns the ' +
            "package's name, description, version, install commands, license and repository, " +
            "the site's sections with their page counts, files for agents such as llms.txt, " +
            'the page the user has open, and the tools on this page with what each returns. ' +
            'Example: "What is this package and how do I install it?"',
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            var current = { url: location.href.split('#')[0], path: currentPath(),
                title: pageTitle() };
            var toolList = order.map(function (name) {
                var tool = tools[name];
                return { name: name, title: tool.title, purpose: tool.purpose };
            });
            return loadManifest(context.signal).then(function (manifest) {
                var site = manifest.site;
                var resources = {};
                Object.keys(manifest.resources).forEach(function (key) {
                    resources[key] = absolute(manifest.resources[key]);
                });
                return compact({
                    url: siteRoot,
                    name: site.name,
                    title: site.title,
                    description: site.description,
                    version: site.version,
                    install: site.install,
                    license: site.license,
                    repo: site.repo,
                    sections: manifest.sections.map(function (section) {
                        return {
                            id: section.id,
                            title: section.title,
                            kind: section.kind,
                            pages: manifest.pages.filter(function (page) {
                                return page.section === section.id;
                            }).length
                        };
                    }),
                    pages: manifest.pages.length,
                    resources: resources,
                    current_page: current,
                    tools: toolList
                });
            }, function (error) {
                if (context.signal && context.signal.aborted) return cancelled();
                return {
                    url: siteRoot,
                    current_page: current,
                    tools: toolList,
                    note: MANIFEST_FILE + ' could not be loaded (' + messageOf(error) +
                        '), so this overview has no site details. Try ' + absolute('llms.txt')
                };
            });
        }
    });

    function pageEntry(page) {
        return compact({
            title: page.title,
            url: absolute(page.path),
            description: page.description,
            kind: page.kind,
            group: page.group,
            tags: page.tags,
            status: page.status,
            date: page.date
        });
    }

    var LIST_PAGES = defineTool({
        name: 'list_pages',
        title: 'List the pages',
        purpose: "The site's pages grouped by section",
        description:
            'Use this to see which pages the site has. Returns them grouped by section, with ' +
            "each page's title, URL, description, tags and status; blog posts come newest " +
            'first. Pass section, an id or title from get_site_overview, for one section. To ' +
            'find the pages about a topic, use search_docs instead. Example: "What guides are ' +
            'there?"',
        inputSchema: {
            type: 'object',
            properties: {
                section: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 200,
                    description: 'A section id or title, such as "user-guide". Omit for all.'
                }
            },
            additionalProperties: false
        },
        example: { section: 'user-guide' },
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            return loadManifest(context.signal).then(function (manifest) {
                var sections = manifest.sections;
                if (input.section) {
                    var wanted = input.section.toLowerCase();
                    sections = sections.filter(function (section) {
                        return section.id.toLowerCase() === wanted ||
                            String(section.title).toLowerCase() === wanted;
                    });
                    if (!sections.length) {
                        var message = 'No section is named "' + input.section + '".';
                        return errorResult('not_found', message, {
                            candidates: manifest.sections.map(function (section) {
                                return { id: section.id, title: section.title };
                            })
                        });
                    }
                } else if (manifest.pages.some(function (page) {
                    return !page.section;
                })) {
                    // Pages outside every section, such as the home page.
                    sections = [{ id: '', title: 'Site', kind: 'page' }].concat(sections);
                }
                return {
                    url: siteRoot,
                    sections: sections.map(function (section) {
                        var pages = manifest.pages.filter(function (page) {
                            return (page.section || '') === section.id;
                        });
                        if (section.kind === 'blog') {
                            // Undated pages, such as the blog's index, come first.
                            pages.sort(function (a, b) {
                                return (a.date ? 1 : 0) - (b.date ? 1 : 0) ||
                                    String(b.date || '').localeCompare(String(a.date || ''));
                            });
                        }
                        return {
                            id: section.id,
                            title: section.title,
                            kind: section.kind,
                            pages: pages.map(pageEntry)
                        };
                    })
                };
            }, function (error) {
                return loadFailed(MANIFEST_FILE, error, context.signal);
            });
        }
    });

    // A page's Markdown, or the section of it that `query` names, as `{markdown, section,
    // whole}` or `{error}`.
    function pageContent(page, query, strict, signal) {
        return fetchText(absolute(page.md), signal).then(function (markdown) {
            if (!query) return { markdown: markdown };
            return pageSection(page, markdown, query, signal).then(function (found) {
                if (found.error) return strict ? found : { markdown: markdown };
                return {
                    markdown: sliceSection(markdown, found.heading, found.list),
                    section: outlineOf(found.heading),
                    whole: markdown
                };
            });
        }, function (error) {
            return loadFailed(page.md, error, signal);
        });
    }

    var GET_PAGE = defineTool({
        name: 'get_page',
        title: 'Get a page',
        purpose: 'One page, or one section of it, as Markdown',
        description:
            'Use this to read a page, or one section of it, as Markdown. page can be a path, ' +
            'URL, title, file name or API name; section can be a heading or its anchor. Pages ' +
            'longer than max_chars are cut and come with their outline, so you can ask for a ' +
            'section. To find which page covers a topic, use search_docs first. Example: ' +
            '"Show me the GitHub Pages part of the deployment guide."',
        inputSchema: {
            type: 'object',
            properties: {
                page: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 500,
                    description: 'A path, URL, title, file name or API name, such as ' +
                        '"user-guide/intro.html" or "Widget.spin".'
                },
                section: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 200,
                    description: 'A heading or its anchor, such as "#parameters". Omit for ' +
                        'the whole page.'
                },
                max_chars: {
                    type: 'integer',
                    minimum: MIN_MAX_CHARS,
                    maximum: MAX_MAX_CHARS,
                    default: DEFAULT_MAX_CHARS,
                    description: 'The most characters of Markdown to return.'
                }
            },
            required: ['page'],
            additionalProperties: false
        },
        example: { page: 'user-guide/intro.html', section: 'Getting started' },
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            var signal = context.signal;
            return loadManifest(signal).then(function (manifest) {
                var found = resolvePage(manifest, input.page);
                if (found.error) return found.error;
                var page = found.page;
                var url = absolute(page.path);
                if (!page.md) {
                    return errorResult('unavailable', page.path + ' has no Markdown copy.', {
                        url: url
                    });
                }
                // An anchor in a page URL that names no section is ignored.
                var query = input.section || found.anchor;
                var loading = pageContent(page, query, Boolean(input.section), signal);
                return loading.then(function (content) {
                    if (content.error) return content;
                    var result = {
                        url: content.section ? url + '#' + content.section.anchor : url,
                        path: page.path,
                        title: page.title,
                        kind: page.kind,
                        match: found.match
                    };
                    if (content.section) result.section = content.section;
                    var shortened = truncate(content.markdown, input.max_chars);
                    result.markdown = shortened.text;
                    result.truncated = shortened.truncated;
                    if (shortened.truncated) {
                        result.total_chars = content.markdown.length;
                        result.outline = headings(content.whole || content.markdown);
                    }
                    return result;
                });
            }, function (error) {
                return loadFailed(MANIFEST_FILE, error, signal);
            });
        }
    });

    var SEARCH_DOCS = defineTool({
        name: 'search_docs',
        title: 'Search the docs',
        purpose: 'Ranked matches for a query, by page section',
        description:
            'Use this to find where the docs cover a topic. Returns the best-matching page ' +
            'sections, at most two per page, each with its title, heading, URL, an excerpt ' +
            'and a score. Read a match with get_page and its URL. scope keeps one kind of ' +
            'page, such as guide, api or blog, or one section id. Example: "How do I deploy ' +
            'to GitHub Pages?"',
        inputSchema: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 200,
                    description: 'Words, a phrase or an API name to look for.'
                },
                limit: {
                    type: 'integer',
                    minimum: 1,
                    maximum: 25,
                    default: 8,
                    description: 'The most matches to return.'
                },
                scope: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 200,
                    default: 'all',
                    description: '"all", a kind of page (such as guide, api, cli or blog) or a ' +
                        'section id.'
                }
            },
            required: ['query'],
            additionalProperties: false
        },
        example: { query: 'install', limit: 5 },
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            var signal = context.signal;
            return loadManifest(signal).then(function (manifest) {
                return loadSearch(signal).then(function (entries) {
                    return search(manifest, entries, input);
                }, function (error) {
                    return loadFailed(SEARCH_FILE, error, signal);
                });
            }, function (error) {
                return loadFailed(MANIFEST_FILE, error, signal);
            });
        }
    });

    // ------------------------------------------------------------------------------------
    // API tools
    // ------------------------------------------------------------------------------------

    // The body class of a page documenting objects of the package's API.
    var API_PAGE_CLASS = 'doc-py-api-page';
    var API_PARTS = ['signature', 'description', 'parameters', 'returns', 'raises', 'examples',
        'markdown'];
    var API_HINT = 'Call list_api to see every object.';
    var FENCED_BLOCK = /^ {0,3}(`{3,}|~{3,})[^\n]*\n([\s\S]*?)\n {0,3}\1[ \t]*$/m;

    function apiEntry(item) {
        return compact({
            name: item.name,
            kind: item.kind,
            summary: item.summary,
            url: absolute(item.path)
        });
    }

    function objectNames(item) {
        return [item.name].concat(item.aliases || []);
    }

    // Find the object `query` names: by its full name, a short name, either in any case, or
    // the end of its full name. Failing those, suggest the objects sharing words with it.
    function resolveObject(api, query) {
        var text = query.trim().replace(/\(\)$/, '');
        var lower = text.toLowerCase();
        var end = '.' + lower.replace(/^\./, '');
        var tiers = [
            ['name', function (item) {
                return item.name === text;
            }],
            ['alias', function (item) {
                return (item.aliases || []).indexOf(text) !== -1;
            }],
            ['case', function (item) {
                return objectNames(item).some(function (name) {
                    return name.toLowerCase() === lower;
                });
            }],
            ['suffix', function (item) {
                return ('.' + item.name.toLowerCase()).slice(-end.length) === end;
            }]
        ];
        for (var i = 0; i < tiers.length; i++) {
            var found = api.filter(tiers[i][1]);
            if (found.length === 1) return { item: found[0], match: tiers[i][0] };
            if (found.length) {
                return { error: errorResult('ambiguous', 'Several objects match "' + text + '".', {
                    candidates: found.slice(0, 5).map(apiEntry),
                    hint: 'Pass one of their names.'
                }) };
            }
        }
        var words = queryWords(text);
        var scored = api.map(function (item) {
            var found = terms(objectNames(item).join(' '));
            var score = 0;
            words.forEach(function (word) {
                score += wordMatch(found, word);
            });
            return { item: item, score: score };
        }).filter(function (entry) {
            return entry.score > 0;
        }).sort(function (a, b) {
            return b.score - a.score;
        });
        return { error: errorResult('not_found', 'No object is named "' + text + '".', {
            candidates: scored.slice(0, 5).map(function (entry) {
                return apiEntry(entry.item);
            }),
            hint: API_HINT
        }) };
    }

    // The object documented on the open page. Of several, such as a class and the methods
    // documented with it, the one with the shortest name.
    function pageObject(api) {
        var path = currentPath();
        return api.filter(function (item) {
            return item.path === path;
        }).sort(function (a, b) {
            return a.name.split('.').length - b.name.split('.').length;
        })[0] || null;
    }

    function sectionKey(text) {
        return text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_|_$/g, '');
    }

    // An object's reference in its page's Markdown: the heading naming it and what follows,
    // up to the next heading of its level. Before its first subheading come its summary,
    // its signature as a code block and its description. Each subheading of the next level
    // starts a docstring section, keyed by its text: `parameters`, `see_also`.
    function referenceParts(markdown, item) {
        var list = parseHeadings(markdown);
        var heading = list.filter(function (h) {
            var text = h.text.replace(/\(\)$/, '');
            return ('.' + item.name).slice(-text.length - 1) === '.' + text;
        })[0] || list[0];
        var lines = markdown.split('\n');
        var start = heading ? heading.line : -1;
        var next = list.filter(function (h) {
            return h.line > start && h.level <= (heading ? heading.level : 0);
        })[0];
        var end = next ? next.line : lines.length;
        var within = list.filter(function (h) {
            return h.line > start && h.line < end;
        });
        var level = Math.min.apply(null, within.map(function (h) {
            return h.level;
        }));
        var sections = {};
        within.forEach(function (h) {
            var key = sectionKey(h.text);
            if (h.level !== level || key in sections) return;
            sections[key] = sliceSection(markdown, h, list).split('\n').slice(1).join('\n').trim();
        });
        var intro = lines.slice(start + 1, within.length ? within[0].line : end).join('\n');
        var code = FENCED_BLOCK.exec(intro);
        var paragraphs = (code ? intro.slice(0, code.index) : intro).trim().split(/\n[ \t]*\n/);
        return {
            anchor: heading && heading.level > 1 ? heading.anchor : null,
            summary: paragraphs[0].replace(/\s+/g, ' ').trim(),
            signature: code ? code[2] : null,
            description: (code ? intro.slice(code.index + code[0].length)
                : paragraphs.slice(1).join('\n\n')).trim(),
            sections: sections,
            markdown: lines.slice(Math.max(start, 0), end).join('\n').replace(/\s+$/, '') + '\n'
        };
    }

    function apiReference(item, markdown, include, match) {
        var parts = referenceParts(markdown, item);
        function wanted(part) {
            return include ? include.indexOf(part) !== -1 : part !== 'markdown';
        }
        var url = absolute(item.path);
        var result = compact({
            name: item.name,
            kind: item.kind,
            url: parts.anchor ? url + '#' + parts.anchor : url,
            match: match,
            summary: parts.summary || item.summary,
            signature: wanted('signature') ? parts.signature : null,
            description: wanted('description') ? parts.description : null
        });
        var sections = {};
        Object.keys(parts.sections).forEach(function (key) {
            if (!include || include.indexOf(key) !== -1) sections[key] = parts.sections[key];
        });
        if (Object.keys(sections).length) result.sections = sections;
        if (wanted('markdown')) result.markdown = parts.markdown;
        return result;
    }

    var LIST_API = defineTool({
        name: 'list_api',
        title: 'List the API',
        purpose: 'The documented objects grouped by reference section',
        description:
            "Use this to see what the package's API offers. Returns the documented classes, " +
            'functions and methods grouped by reference section, each with its full name, ' +
            'kind, summary and URL. Pass section, a section title, for one group. To read ' +
            'one object, use get_api_reference. Example: "Which functions does this package ' +
            'have?"',
        feature: 'api',
        inputSchema: {
            type: 'object',
            properties: {
                section: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 200,
                    description: 'A reference section title, such as "Classes". Omit for all.'
                }
            },
            additionalProperties: false
        },
        example: { section: 'Classes' },
        annotations: { readOnlyHint: true },
        run: function (input, context) {
            return loadManifest(context.signal).then(function (manifest) {
                var groups = [];
                var byTitle = Object.create(null);
                manifest.api.forEach(function (item) {
                    var title = item.section || '';
                    if (!byTitle[title]) {
                        groups.push(byTitle[title] = { title: title, objects: [] });
                    }
                    byTitle[title].objects.push(apiEntry(item));
                });
                if (input.section) {
                    var wanted = input.section.toLowerCase();
                    var kept = groups.filter(function (group) {
                        return group.title.toLowerCase() === wanted;
                    });
                    if (!kept.length) {
                        var message = 'No reference section is named "' + input.section + '".';
                        return errorResult('not_found', message, {
                            candidates: groups.map(function (group) {
                                return group.title;
                            }).filter(Boolean)
                        });
                    }
                    groups = kept;
                }
                var index = manifest.pages.filter(function (page) {
                    return page.kind === 'reference';
                })[0];
                return {
                    url: index ? absolute(index.path) : siteRoot,
                    sections: groups.map(compact)
                };
            }, function (error) {
                return loadFailed(MANIFEST_FILE, error, context.signal);
            });
        }
    });

    // On an object's reference page, `name` defaults to that object.
    function apiReferenceTool(onObjectPage) {
        var schema = {
            type: 'object',
            properties: {
                name: {
                    type: 'string',
                    minLength: 1,
                    maxLength: 300,
                    description: 'A full or short name, such as "Widget.spin".' +
                        (onObjectPage ? ' Omit for the object documented on this page.' : '')
                },
                include: {
                    type: 'array',
                    items: { type: 'string', enum: API_PARTS },
                    description: 'The parts to return. Omit for all but markdown, the whole ' +
                        'reference.'
                }
            },
            additionalProperties: false
        };
        if (!onObjectPage) schema.required = ['name'];
        return defineTool({
            name: 'get_api_reference',
            title: 'Get an API reference',
            purpose: "One object's signature, parameters, returns and examples",
            description:
                'Use this to read about one class, function or method: its signature, ' +
                'parameters, returns, raises and examples, as Markdown. name can be full or ' +
                'short, such as "pkg.Widget.spin" or "spin"; an ambiguous name returns ' +
                'candidates. ' + (onObjectPage
                    ? 'name defaults to the object documented on this page. '
                    : '') +
                'include picks the parts to return. For other pages, use get_page. ' +
                'Example: "What arguments does spin() take?"',
            feature: 'api',
            inputSchema: schema,
            example: { name: 'Widget.spin', include: ['signature', 'parameters'] },
            annotations: { readOnlyHint: true },
            run: function (input, context) {
                var signal = context.signal;
                return loadManifest(signal).then(function (manifest) {
                    var found = input.name ? resolveObject(manifest.api, input.name) : null;
                    if (!found) {
                        var current = pageObject(manifest.api);
                        found = current ? { item: current, match: 'page' } : {
                            error: errorResult('invalid_input',
                                'This page documents no object, so name is required.',
                                { hint: API_HINT })
                        };
                    }
                    if (found.error) return found.error;
                    var item = found.item;
                    if (!item.md) {
                        return errorResult('unavailable', item.name + ' has no Markdown copy.', {
                            url: absolute(item.path)
                        });
                    }
                    return fetchText(absolute(item.md), signal).then(function (markdown) {
                        return apiReference(item, markdown, input.include, found.match);
                    }, function (error) {
                        return loadFailed(item.md, error, signal);
                    });
                }, function (error) {
                    return loadFailed(MANIFEST_FILE, error, signal);
                });
            }
        });
    }

    var GET_API_REFERENCE = apiReferenceTool(Boolean(document.body &&
        document.body.classList && document.body.classList.contains(API_PAGE_CLASS)));

    var BUILT_IN_TOOLS = [GET_SITE_OVERVIEW, GET_CURRENT_PAGE, LIST_PAGES, GET_PAGE, SEARCH_DOCS,
        LIST_API, GET_API_REFERENCE];

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
            if (tool.feature !== 'site' && !settings.features[tool.feature]) return;
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
            fetchText: fetchText,
            tokenize: function (text) {
                return Array.from(tokenize(text));
            },
            queryWords: queryWords,
            excerpt: excerpt,
            referenceParts: referenceParts
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
