/* Showreel Studio — browser scene editor + agent-drivable command API.
 * Reuses window.GreatShowreel (the player) for the live preview. */
(function () {
  "use strict";

  function el(tag, cls, parent, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt != null) e.textContent = txt;
    if (parent) parent.appendChild(e);
    return e;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c];
    });
  }
  function api(path, method, body) {
    return fetch(path, {
      method: method || "GET",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    }).then(function (r) { return r.json(); });
  }

  var S = {
    spec: null, manifest: null, sel: 0, dirty: false,
    copilot: true, building: false, mtime: 0, name: "", player: null,
  };
  var R = {}; // DOM refs
  var dragFrom = null;

  function round(x, n) { var f = Math.pow(10, n || 3); return Math.round(x * f) / f; }
  function scenes() { return (S.spec && S.spec.scenes) || []; }

  // Reorder the preview manifest to match the spec scene order (instant preview,
  // no rebuild). Durations are kept; start/end are recomputed cumulatively.
  function patchManifestOrder() {
    if (!S.manifest || !S.manifest.scenes) return;
    var byId = {};
    S.manifest.scenes.forEach(function (ms) { byId[ms.id] = ms; });
    var out = [], t = 0;
    scenes().forEach(function (sc) {
      var ms = byId[sc.id];
      if (!ms) return; // scene not built yet -> appears after next Rebuild
      var dur = ms.end - ms.start;
      ms = Object.assign({}, ms, { start: round(t), end: round(t + dur) });
      t = ms.end; out.push(ms);
    });
    if (out.length) {
      S.manifest = Object.assign({}, S.manifest, {
        scenes: out, duration: round(t),
        chapters: out.map(function (m) { return { time: m.start, label: m.id }; }),
      });
      remountPlayer();
    }
  }

  function sayText(sc) {
    var v = sc.say;
    if (v == null) return "";
    if (typeof v === "string") return v;
    if (typeof v === "object") return v.text || v.prompt || "";
    return String(v);
  }
  function setSay(sc, text) { sc.say = text; }

  function log(msg, kind) {
    var e = el("div", "le " + (kind || ""), R.log);
    var tag = kind === "agent" ? "agent" : kind === "ok" ? "✓" : kind === "err" ? "✗" : "·";
    e.innerHTML = "<b>" + tag + "</b> " + escapeHtml(msg);
    R.log.scrollTop = R.log.scrollHeight;
  }

  // --- rendering ---
  function updateStatus() {
    R.status.textContent = S.building
      ? "Rebuilding…"
      : S.dirty ? "Unsaved — Rebuild to preview" : "Up to date";
    R.rebuild.classList.toggle("dirty", S.dirty);
    R.rebuild.disabled = S.building;
    R.save.disabled = !S.dirty || S.building;
  }

  function remountPlayer() {
    R.playerHost.innerHTML = "";
    if (!S.manifest || !S.manifest.scenes || !S.manifest.scenes.length) {
      el("div", "hint", R.playerHost, "No preview yet — click Rebuild.");
      return;
    }
    var pd = el("div", "gd-showreel", R.playerHost);
    S.player = window.GreatShowreel.mount(pd, S.manifest, { base: "" });
    var msc = S.manifest.scenes[Math.min(S.sel, S.manifest.scenes.length - 1)];
    if (msc) S.player.seek(msc.start + 0.05);
  }

  function renderScenes() {
    R.scenes.innerHTML = "";
    el("h3", null, R.scenes, "Scenes");
    scenes().forEach(function (sc, i) {
      var card = el("div", "st-scene" + (i === S.sel ? " sel" : ""), R.scenes);
      card.onclick = function () { select(i); };
      card.draggable = true;
      card.ondragstart = function (e) { dragFrom = i; e.dataTransfer.effectAllowed = "move"; };
      card.ondragover = function (e) { e.preventDefault(); card.classList.add("dragover"); };
      card.ondragleave = function () { card.classList.remove("dragover"); };
      card.ondrop = function (e) {
        e.preventDefault(); card.classList.remove("dragover");
        if (dragFrom != null && dragFrom !== i) move(dragFrom, i);
        dragFrom = null;
      };
      var row = el("div", "row", card);
      el("span", "st-badge", row, sc.type || "?");
      el("span", "sid", row, sc.id || "scene-" + i);
      var acts = el("div", "sacts", row);
      mini(acts, "↑", function (e) { e.stopPropagation(); move(i, i - 1); });
      mini(acts, "↓", function (e) { e.stopPropagation(); move(i, i + 1); });
      mini(acts, "✕", function (e) { e.stopPropagation(); removeScene(i); }, "del");
      var say = sayText(sc);
      if (say) el("div", "ssay", card, say);
    });
    var add = el("button", "st-btn st-add", R.scenes, "+ Add scene");
    add.onclick = addScene;
  }
  function mini(parent, txt, fn, cls) {
    var b = el("button", "st-mini" + (cls ? " " + cls : ""), parent, txt);
    b.onclick = fn;
    return b;
  }

  function field(label, type, value, onchange) {
    var f = el("div", "st-field", R.props);
    el("label", null, f, label);
    var inp = el("input", null, f);
    inp.type = type; inp.value = value;
    inp.onchange = function () { onchange(inp.value); };
    return inp;
  }
  function textareaField(label, value, onchange) {
    var f = el("div", "st-field", R.props);
    el("label", null, f, label);
    var ta = el("textarea", null, f);
    ta.value = value;
    ta.onchange = function () { onchange(ta.value); };
    return ta;
  }
  function selectField(label, options, value, onchange) {
    var f = el("div", "st-field", R.props);
    el("label", null, f, label);
    var sel = el("select", null, f);
    options.forEach(function (o) {
      var opt = el("option", null, sel, o);
      opt.value = o; if (o === value) opt.selected = true;
    });
    sel.onchange = function () { onchange(sel.value); };
    return sel;
  }

  function renderProps() {
    R.props.innerHTML = "";
    el("h3", null, R.props, "Properties");
    var sc = scenes()[S.sel];
    if (!sc) { el("div", "hint", R.props, "No scene selected."); return; }
    field("ID", "text", sc.id || "", function (v) { sc.id = v; touch(); });
    selectField("Type", ["title", "card", "image", "code", "web", "notebook"],
      sc.type || "title", function (v) { sc.type = v; touch(); renderProps(); });
    textareaField("Narration (say)", sayText(sc), function (v) { setSay(sc, v); touch(); });
    if (sc.type === "title" || sc.type === "card") {
      field("Title", "text", sc.title || "", function (v) { sc.title = v; touch(); });
      field("Subtitle", "text", sc.subtitle || "", function (v) { sc.subtitle = v; touch(); });
      if (sc.type === "card") {
        field("Body", "text", sc.body || "", function (v) { sc.body = v; touch(); });
        field("CTA", "text", sc.cta || "", function (v) { sc.cta = v; touch(); });
      }
    }
    if (sc.type === "image") field("Source (src)", "text", sc.src || "", function (v) { sc.src = v; touch(); });
    if (sc.type === "web") field("URL", "text", sc.url || "", function (v) { sc.url = v; touch(); });
    if (sc.type === "notebook") field("Notebook", "text", sc.notebook || "", function (v) { sc.notebook = v; touch(); });
    field("Duration (s, blank = auto)", "text", sc.duration != null ? String(sc.duration) : "",
      function (v) { if (v.trim() === "") delete sc.duration; else sc.duration = parseFloat(v); touch(); });
    selectField("Transition", ["crossfade", "cut"], sc.transition || "crossfade",
      function (v) { sc.transition = v; touch(); });
    selectField("Motion", ["ken_burns", "zoom", "pan", "none"], (sc.motion && sc.motion.type) || "ken_burns",
      function (v) { sc.motion = Object.assign({}, sc.motion, { type: v }); touch(); });
  }

  // --- edit operations ---
  function touch() { S.dirty = true; renderScenes(); updateStatus(); }
  function select(i) {
    S.sel = Math.max(0, Math.min(i, scenes().length - 1));
    renderScenes(); renderProps();
    if (S.player && S.manifest.scenes[S.sel]) S.player.seek(S.manifest.scenes[S.sel].start + 0.05);
  }
  function move(i, j) {
    var s = scenes();
    if (j < 0 || j >= s.length) return;
    var x = s.splice(i, 1)[0];
    s.splice(j, 0, x);
    S.sel = j; touch(); renderProps();
    patchManifestOrder(); // instant preview reorder (no rebuild)
  }
  function addScene(atIndex, scene) {
    var s = scenes();
    var n = s.length;
    var sc = scene || { id: "scene-" + (n + 1), type: "title", title: "New scene", say: "" };
    var idx = (atIndex == null || atIndex > n) ? n : atIndex;
    s.splice(idx, 0, sc);
    S.sel = idx; touch(); renderProps();
  }
  function removeScene(i) {
    var s = scenes();
    if (s.length <= 1) { log("can't delete the last scene", "err"); return; }
    s.splice(i, 1);
    S.sel = Math.min(S.sel, s.length - 1);
    touch(); renderProps();
  }

  function doSave() {
    return api("/api/save", "POST", { spec: S.spec }).then(function (d) {
      if (d.ok) { S.dirty = false; S.mtime = d.mtime; updateStatus(); log("Saved " + S.name, "ok"); }
      else log("Save failed: " + d.error, "err");
      return d;
    });
  }
  function doRebuild() {
    S.building = true; updateStatus(); log("Rebuilding…");
    return api("/api/rebuild", "POST", { spec: S.spec }).then(function (d) {
      S.building = false;
      if (d.ok) {
        S.manifest = d.manifest; S.dirty = false;
        return api("/api/mtime").then(function (m) {
          S.mtime = m.mtime; remountPlayer(); updateStatus(); log("Rebuilt preview", "ok"); return d;
        });
      }
      log("Rebuild failed: " + d.error, "err"); updateStatus(); return d;
    });
  }
  function setCopilot(v) {
    S.copilot = !!v;
    R.copilot.classList.toggle("on", S.copilot);
    log("Copilot " + (S.copilot ? "enabled" : "disabled (human phase)"));
  }

  // --- external-change (file-watch) polling ---
  function startPoll() {
    setInterval(function () {
      api("/api/mtime").then(function (m) {
        if (m.mtime > S.mtime + 0.001) {
          if (S.dirty) showReloadBanner();
          else reloadSpec("external change");
        }
      }).catch(function () {});
    }, 1500);
  }
  function reloadSpec(why) {
    api("/api/spec").then(function (d) {
      S.spec = d.spec; S.manifest = d.manifest; S.mtime = d.mtime; S.dirty = false;
      S.sel = Math.min(S.sel, scenes().length - 1);
      renderScenes(); renderProps(); remountPlayer(); updateStatus();
      log("Reloaded (" + why + ")", "ok");
      if (R.banner) { R.banner.remove(); R.banner = null; }
    });
  }
  function showReloadBanner() {
    if (R.banner) return;
    R.banner = el("div", "st-reload-banner", document.body,
      "Spec changed on disk — click to reload (discards local edits)");
    R.banner.onclick = function () { reloadSpec("manual"); };
  }

  // --- agent-drivable API ---
  function snapshot() {
    return {
      name: S.name, selection: S.sel, sceneCount: scenes().length,
      dirty: S.dirty, copilot: S.copilot, building: S.building,
      scenes: scenes().map(function (sc, i) {
        return {
          index: i, id: sc.id, type: sc.type, say: sayText(sc),
          title: sc.title, duration: sc.duration != null ? sc.duration : "auto",
          transition: sc.transition || "crossfade", motion: (sc.motion || {}).type || "ken_burns",
        };
      }),
    };
  }
  function applyOp(o) {
    var s = scenes();
    switch (o.op) {
      case "select": S.sel = o.index; break;
      case "update": Object.assign(s[o.index], o.patch || {}); break;
      case "setNarration": setSay(s[o.index], o.text); break;
      case "add": addScene(o.index, o.scene); return;
      case "delete": removeScene(o.index); return;
      case "move": move(o.from, o.to); return;
      default: throw new Error("unknown op: " + o.op);
    }
  }
  function apply(ops, opts) {
    opts = opts || {};
    if (opts.agent && !S.copilot) {
      log("agent change blocked (copilot off)", "err");
      return { ok: false, reason: "copilot-disabled" };
    }
    (ops || []).forEach(applyOp);
    if (!(ops.length === 1 && ops[0].op === "select")) S.dirty = true;
    renderScenes(); renderProps(); updateStatus();
    if (opts.agent) log((opts.label || "applied " + ops.length + " op(s)"), "agent");
    return { ok: true, snapshot: snapshot() };
  }

  function defineApi() {
    window.__studio = {
      snapshot: snapshot,
      apply: apply,
      save: function () { doSave(); return { ok: true, queued: true }; },
      rebuild: function () { doRebuild(); return { ok: true, queued: true }; },
      select: function (i) { select(i); return snapshot(); },
      setCopilot: function (v) { setCopilot(v); return { copilot: S.copilot }; },
      getSpec: function () { return S.spec; },
    };
  }

  function mount(root) {
    root.innerHTML = "";
    var tb = el("div", "st-toolbar", root);
    var title = el("div", "st-title", tb);
    title.innerHTML = 'Showreel Studio <small id="st-name"></small>';
    el("div", "st-spacer", tb);
    var cp = el("div", "st-copilot", tb);
    el("span", null, cp, "Copilot");
    R.copilot = el("div", "st-switch on", cp);
    R.copilot.onclick = function () { setCopilot(!S.copilot); };
    R.save = el("button", "st-btn", tb, "Save"); R.save.onclick = function () { doSave(); };
    R.rebuild = el("button", "st-btn primary", tb, "Rebuild ▶"); R.rebuild.onclick = function () { doRebuild(); };
    R.status = el("div", "st-status", tb);

    var body = el("div", "st-body", root);
    R.scenes = el("div", "st-col st-scenes", body);
    R.preview = el("div", "st-col st-preview", body);
    R.props = el("div", "st-col st-props", body);
    R.playerHost = el("div", null, R.preview);
    R.log = el("div", "st-log", root);

    defineApi();
    api("/api/spec").then(function (d) {
      S.spec = d.spec; S.manifest = d.manifest; S.mtime = d.mtime; S.name = d.name; S.sel = 0;
      document.getElementById("st-name").textContent = d.name;
      remountPlayer(); renderScenes(); renderProps(); updateStatus();
      log("Loaded " + d.name + " (" + scenes().length + " scenes)", "ok");
      startPoll();
    });
  }

  window.GreatStudio = { mount: mount };
})();
