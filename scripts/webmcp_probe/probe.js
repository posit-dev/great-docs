// WebMCP platform probe. Registers test tools in as many forms as we need to learn
// how the browser treats them, and records everything in `window.__probe` for
// `run.mjs` to read. Not shipped with Great Docs.
(function () {
  "use strict";

  var probe = (window.__probe = {
    env: {},
    registrations: [],
    calls: [],
    events: [],
    errors: [],
  });

  function protoMethods(obj) {
    var names = [];
    for (var p = Object.getPrototypeOf(obj); p && p !== Object.prototype; p = Object.getPrototypeOf(p)) {
      Object.getOwnPropertyNames(p).forEach(function (name) {
        if (name !== "constructor" && names.indexOf(name) < 0) names.push(name);
      });
    }
    return names.sort();
  }

  function describe(value) {
    if (value === null) return "null";
    if (Array.isArray(value)) return "array";
    return typeof value;
  }

  function keysOf(value) {
    if (!value || typeof value !== "object") return [];
    var keys = [];
    for (var key in value) keys.push(key);
    return keys.sort();
  }

  var docMc = document.modelContext;
  var navMc = navigator.modelContext;
  var mc = docMc || navMc;

  probe.env = {
    documentModelContext: describe(docMc),
    navigatorModelContext: describe(navMc),
    sameObject: !!docMc && docMc === navMc,
    constructorName: mc && mc.constructor ? mc.constructor.name : null,
    methods: mc ? protoMethods(mc) : [],
    readyStateAtRegistration: document.readyState,
    isSecureContext: window.isSecureContext,
    origin: location.origin,
    href: location.href,
    userAgent: navigator.userAgent,
  };

  if (!mc) return;

  if (typeof mc.addEventListener === "function") {
    mc.addEventListener("toolchange", function (event) {
      if (!probe.toolchangeKeys) probe.toolchangeKeys = keysOf(event);
      probe.events.push({ type: event.type, at: Date.now() });
    });
  }
  probe.env.hasOnToolchange = "ontoolchange" in mc;

  // Every execute callback records what it received.
  function recorder(name, body) {
    return function () {
      var input = arguments[0];
      var second = arguments[1];
      probe.calls.push({
        tool: name,
        argc: arguments.length,
        inputType: describe(input),
        input: typeof input === "string" ? input : JSON.stringify(input),
        secondType: describe(second),
        secondKeys: second ? keysOf(second).concat(protoMethods(second)) : [],
      });
      return body(input, second);
    };
  }

  var echoSchema = {
    type: "object",
    properties: { text: { type: "string", description: "Text to echo" } },
    required: ["text"],
    additionalProperties: false,
  };

  var big = new Array(1024 * 1024 + 1).join("x");

  var tools = [
    {
      name: "probe_echo",
      description: "Echo the input back as a plain object.",
      inputSchema: echoSchema,
      annotations: { readOnlyHint: true },
      execute: recorder("probe_echo", function (input) {
        return { echo: input };
      }),
    },
    {
      name: "probe_string",
      description: "Return a plain string.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_string", function () {
        return "plain string result";
      }),
    },
    {
      name: "probe_content",
      description: "Return an MCP-style content array.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_content", function () {
        return { content: [{ type: "text", text: "content array result" }] };
      }),
    },
    {
      name: "probe_undefined",
      description: "Return undefined.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_undefined", function () {
        return undefined;
      }),
    },
    {
      name: "probe_async",
      description: "Resolve after 50 ms.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_async", function () {
        return new Promise(function (resolve) {
          setTimeout(function () {
            resolve({ async: true });
          }, 50);
        });
      }),
    },
    {
      name: "probe_throw",
      description: "Throw an error.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_throw", function () {
        throw new Error("probe_throw failed on purpose");
      }),
    },
    {
      name: "probe_reject",
      description: "Return a rejected promise.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_reject", function () {
        return Promise.reject(new Error("probe_reject failed on purpose"));
      }),
    },
    {
      name: "probe_big",
      description: "Return a 1 MB string inside an object.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_big", function () {
        return { text: big };
      }),
    },
    {
      name: "probe_no_schema",
      description: "A tool registered without an inputSchema.",
      execute: recorder("probe_no_schema", function (input) {
        return { input: input };
      }),
    },
    {
      name: "probe_ann_hint_names",
      description: "Annotations spelled with the MCP *Hint suffix.",
      inputSchema: { type: "object", properties: {} },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
        untrustedContentHint: true,
      },
      execute: recorder("probe_ann_hint_names", function () {
        return { ok: true };
      }),
    },
    {
      name: "probe_ann_plain_names",
      description: "Annotations spelled as in the DevTools protocol.",
      inputSchema: { type: "object", properties: {} },
      annotations: { readOnly: true, untrustedContent: true, consequential: false },
      execute: recorder("probe_ann_plain_names", function () {
        return { ok: true };
      }),
    },
    {
      name: "probe_action",
      description: "An action tool marked consequential.",
      inputSchema: { type: "object", properties: {} },
      annotations: { readOnlyHint: false, consequential: true },
      execute: recorder("probe_action", function () {
        return { acted: true };
      }),
    },
    {
      name: "probe_output_schema",
      description: "A tool with an outputSchema.",
      inputSchema: { type: "object", properties: {} },
      outputSchema: {
        type: "object",
        properties: { value: { type: "number" } },
        required: ["value"],
      },
      execute: recorder("probe_output_schema", function () {
        return { value: 42 };
      }),
    },
    {
      name: "probe_output_mismatch",
      description: "Returns a value that violates its outputSchema.",
      inputSchema: { type: "object", properties: {} },
      outputSchema: {
        type: "object",
        properties: { value: { type: "number" } },
        required: ["value"],
      },
      execute: recorder("probe_output_mismatch", function () {
        return { value: "not a number" };
      }),
    },
    {
      name: "probe_slow",
      description: "Resolve after 3 s unless the call is cancelled.",
      inputSchema: { type: "object", properties: {} },
      execute: recorder("probe_slow", function (input, options) {
        return new Promise(function (resolve) {
          var signal = options && options.signal;
          var timer = setTimeout(function () {
            resolve({ finished: true });
          }, 3000);
          if (signal && typeof signal.addEventListener === "function") {
            signal.addEventListener("abort", function () {
              clearTimeout(timer);
              probe.slowAborted = { reason: String(signal.reason), at: Date.now() };
              resolve({ aborted: true });
            });
          }
        });
      }),
    },
    {
      name: "probe_navigate_after",
      description: "Return a result, then navigate on the next tick.",
      inputSchema: { type: "object", properties: {} },
      annotations: { readOnlyHint: false },
      execute: recorder("probe_navigate_after", function () {
        setTimeout(function () {
          location.href = "page2.html";
        }, 0);
        return { navigating: "page2.html" };
      }),
    },
    {
      name: "probe_navigate_later",
      description: "Return a result, then navigate 500 ms later.",
      inputSchema: { type: "object", properties: {} },
      annotations: { readOnlyHint: false },
      execute: recorder("probe_navigate_later", function () {
        setTimeout(function () {
          location.href = "page2.html";
        }, 500);
        return { navigating: "page2.html" };
      }),
    },
    {
      name: "probe_navigate_before",
      description: "Navigate without ever resolving.",
      inputSchema: { type: "object", properties: {} },
      annotations: { readOnlyHint: false },
      execute: recorder("probe_navigate_before", function () {
        location.href = "page2.html";
        return new Promise(function () {});
      }),
    },
  ];

  function register(tool, options, label) {
    var entry = { label: label || tool.name };
    try {
      var result = options === undefined ? mc.registerTool(tool) : mc.registerTool(tool, options);
      entry.returned = describe(result);
      entry.isPromise = !!result && typeof result.then === "function";
      if (entry.isPromise) {
        entry.settled = "pending";
        result.then(
          function (value) {
            entry.settled = "fulfilled";
            entry.value = describe(value);
          },
          function (error) {
            entry.settled = "rejected";
            entry.error = String(error && error.name) + ": " + String(error && error.message);
          }
        );
      }
    } catch (error) {
      entry.threw = String(error && error.name) + ": " + String(error && error.message);
    }
    probe.registrations.push(entry);
    return entry;
  }

  tools.forEach(function (tool) {
    register(tool);
  });

  // Duplicate name.
  register(
    {
      name: "probe_echo",
      description: "A second tool with an existing name.",
      inputSchema: { type: "object", properties: {} },
      execute: function () {
        return { duplicate: true };
      },
    },
    undefined,
    "duplicate probe_echo"
  );

  // Malformed registrations.
  register(
    { name: "bad name!", description: "Spaces and punctuation.", execute: function () {} },
    undefined,
    "invalid name"
  );
  register({ name: "probe_no_description", execute: function () {} }, undefined, "no description");
  register(
    { name: "probe_bad_schema", description: "Schema is a string.", inputSchema: "nope", execute: function () {} },
    undefined,
    "string inputSchema"
  );
  register(
    { name: "probe_no_execute", description: "No execute callback.", inputSchema: { type: "object" } },
    undefined,
    "no execute"
  );
  register(
    {
      name: "a_" + new Array(200).join("n"),
      description: "A 200-character name.",
      inputSchema: { type: "object", properties: {} },
      execute: function () {},
    },
    undefined,
    "200-char name"
  );

  // Unregistration through an AbortSignal.
  var controller = typeof AbortController === "function" ? new AbortController() : null;
  if (controller) {
    register(
      {
        name: "probe_signal",
        description: "Unregistered later through an AbortSignal.",
        inputSchema: { type: "object", properties: {} },
        execute: function () {
          return { ok: true };
        },
      },
      { signal: controller.signal },
      "with signal"
    );
  }
  window.__probeAbort = function () {
    if (controller) controller.abort();
    return !!controller;
  };

  function settle(entry) {
    return new Promise(function (resolve) {
      (function check() {
        if (entry.settled === "pending") setTimeout(check, 10);
        else resolve(entry);
      })();
    });
  }

  // Which names the browser accepts. Each tool is unregistered once settled.
  window.__probeNames = function () {
    var names = [
      "a",
      "ab",
      "get_page",
      "get-page",
      "get.page",
      "getPage",
      "GET_PAGE",
      "1get_page",
      "_get_page",
      "get page",
      "get/page",
      "get:page",
      "gét_page",
      "n" + new Array(64).join("x"),
      "n" + new Array(65).join("x"),
      "n" + new Array(128).join("x"),
      "n" + new Array(129).join("x"),
    ];
    var results = [];
    return names
      .reduce(function (chain, name) {
        return chain.then(function () {
          var controller = new AbortController();
          var entry = register(
            {
              name: name,
              description: "Name test.",
              inputSchema: { type: "object", properties: {} },
              execute: function () {
                return {};
              },
            },
            { signal: controller.signal },
            "name " + name.length + ": " + (name.length > 20 ? name.slice(0, 8) + "…" : name)
          );
          return settle(entry).then(function () {
            results.push({ name: name.length > 20 ? name.length + " chars" : name, ok: entry.settled === "fulfilled", error: entry.error });
            controller.abort();
          });
        });
      }, Promise.resolve())
      .then(function () {
        return results;
      });
  };

  // Optional members: which reach the agent.
  window.__probeExtras = function () {
    var extras = [
      {
        name: "probe_title",
        title: "Probe Title",
        description: "Registered with a title.",
        inputSchema: { type: "object", properties: {} },
        execute: function () {
          return {};
        },
      },
      {
        name: "probe_consequential",
        description: "consequentialHint: true.",
        inputSchema: { type: "object", properties: {} },
        annotations: { readOnlyHint: false, consequentialHint: true },
        execute: function () {
          return {};
        },
      },
      {
        name: "probe_untrusted",
        description: "untrustedContentHint: true with readOnlyHint: true.",
        inputSchema: { type: "object", properties: {} },
        annotations: { readOnlyHint: true, untrustedContentHint: true },
        execute: function () {
          return {};
        },
      },
      {
        name: "probe_long_description",
        description: new Array(10001).join("d"),
        inputSchema: { type: "object", properties: {} },
        execute: function () {
          return {};
        },
      },
      {
        name: "probe_odd_schema",
        description: "inputSchema that isn't valid JSON Schema.",
        inputSchema: { type: "nonsense", properties: 5 },
        execute: function () {
          return {};
        },
      },
    ];
    var entries = extras.map(function (tool) {
      return register(tool);
    });
    return Promise.all(entries.map(settle)).then(function () {
      return entries;
    });
  };

  // A framed probe reports to its parent, which can't read a cross-origin frame.
  if (window.parent !== window) {
    setTimeout(function () {
      window.parent.postMessage(
        {
          probe: {
            href: location.href,
            documentModelContext: probe.env.documentModelContext,
            firstRegistration: probe.registrations[0],
          },
        },
        "*"
      );
    }, 500);
  }

  // Calls from page script, for comparison with agent calls.
  window.__probeFromPage = function () {
    var out = {};
    var chain = Promise.resolve();
    if (typeof mc.getTools !== "function") {
      out.getTools = "missing";
      return Promise.resolve(out);
    }
    return chain
      .then(function () {
        return mc.getTools();
      })
      .then(function (list) {
        out.getTools = {
          count: list.length,
          names: list.map(function (tool) {
            return tool.name;
          }),
          firstKeys: list[0] ? keysOf(list[0]).concat(protoMethods(list[0])) : [],
          firstAnnotations: list[0] && list[0].annotations ? JSON.stringify(list[0].annotations) : null,
        };
        var echo = list.filter(function (tool) {
          return tool.name === "probe_echo";
        })[0];
        if (!echo || typeof mc.executeTool !== "function") {
          out.executeTool = "missing";
          return out;
        }
        function attempt(label, input) {
          return Promise.resolve()
            .then(function () {
              return mc.executeTool(echo, input);
            })
            .then(
              function (value) {
                out[label] = { type: describe(value), value: value };
              },
              function (error) {
                out[label] = { error: String(error && error.name) + ": " + String(error && error.message) };
              }
            );
        }
        return attempt("executeObject", { text: "hi" })
          .then(function () {
            return attempt("executeString", JSON.stringify({ text: "hi" }));
          })
          .then(function () {
            return attempt("executeInvalid", { wrong: 1 });
          })
          .then(function () {
            return out;
          });
      })
      .catch(function (error) {
        out.error = String(error && error.name) + ": " + String(error && error.message);
        return out;
      });
  };
})();
