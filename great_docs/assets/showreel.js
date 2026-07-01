/* showreel player — narrated demo reels for Great Docs.
 * Vanilla JS, no dependencies. Renders a manifest produced by
 * great_docs/_showreel. The same player is the canonical renderer for both the
 * web embed and (later) the headless ffmpeg export, so all motion is driven by
 * a deterministic clock — `window.__showreel.seek(t)` advances it exactly.
 */
(function () {
  "use strict";

  var ANCHORS = {
    center: [0, 0],
    left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1],
    "top-left": [-1, -1], "top-right": [1, -1],
    "bottom-left": [-1, 1], "bottom-right": [1, 1]
  };

  function anchor(name) { return ANCHORS[name] || ANCHORS.center; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function fmt(t) {
    t = Math.max(0, Math.floor(t));
    var m = Math.floor(t / 60), s = t % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function el(tag, cls, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (parent) parent.appendChild(e);
    return e;
  }

  // Resolve an asset path against the base, leaving data:/absolute URLs intact
  // (so inlined data-URIs work for offline, zero-fetch embeds).
  function srcUrl(base, p) {
    if (/^(data:|https?:|blob:|\/)/.test(p)) return p;
    return base ? base + "/" + p : p;
  }

  // Compute a transform string for a scene's motion at progress p in [0,1].
  function motionTransform(motion, p) {
    if (!motion || motion.type === "none" || !motion.type) return "";
    var zoom = motion.zoom || 1.06;
    var a = anchor(motion.from), b = anchor(motion.to);
    var ax = lerp(a[0], b[0], p), ay = lerp(a[1], b[1], p);
    var scale, maxShift;
    if (motion.type === "pan") {
      scale = zoom;
      maxShift = (scale - 1) * 50;
    } else { // ken_burns or zoom
      scale = lerp(1.0, zoom, p);
      maxShift = (scale - 1) * 50;
    }
    var tx = -ax * maxShift, ty = -ay * maxShift;
    return "translate(" + tx.toFixed(3) + "%," + ty.toFixed(3) + "%) scale(" + scale.toFixed(4) + ")";
  }

  function Player(root, manifest, opts) {
    this.root = root;
    this.m = manifest;
    this.base = (opts && opts.base) || ".";
    this.scenes = manifest.scenes || [];
    this.duration = manifest.duration || 0;
    this.time = 0;
    this.playing = false;
    this.speed = 1;
    this.captionsOn = true;
    this._raf = null;
    this._last = 0;
    this._activeIdx = -1;
    this._audioIdx = -1; // scene index whose narration is currently playing
    this._build();
    this.seek(0);
  }

  Player.prototype._build = function () {
    var self = this;
    this.root.classList.add("gd-showreel");
    if (this.m.aspect) this.root.setAttribute("data-aspect", this.m.aspect);
    if (this.m.theme && this.m.theme !== "auto") this.root.setAttribute("data-theme", this.m.theme);
    var brand = this.m.brand || {};
    if (brand.accent) this.root.style.setProperty("--sr-accent", brand.accent);
    if (brand.font) this.root.style.setProperty("--sr-font", brand.font);
    if (brand.code_font) this.root.style.setProperty("--sr-code-font", brand.code_font);

    if (this.m.code_css && !document.getElementById("gd-sr-code-css")) {
      var st = document.createElement("style");
      st.id = "gd-sr-code-css";
      st.textContent = this.m.code_css;
      document.head.appendChild(st);
    }

    var stage = el("div", "gd-sr-stage", this.root);
    this.stage = stage;
    this._sceneEls = this.scenes.map(function (sc) { return self._buildScene(sc, stage); });

    this.capEl = el("div", "gd-sr-captions", stage);

    // Controls
    var ctr = el("div", "gd-sr-controls", this.root);
    this.playBtn = el("button", "gd-sr-btn", ctr);
    this.playBtn.setAttribute("aria-label", "Play/Pause");
    this.playBtn.innerHTML = "&#9654;";
    this.playBtn.addEventListener("click", function () { self.toggle(); });

    var track = el("div", "gd-sr-track", ctr);
    el("div", "gd-sr-rail", track);
    this.fill = el("div", "gd-sr-fill", track);
    (this.scenes || []).forEach(function (sc) {
      if (!self.duration) return;
      var tick = el("div", "gd-sr-tick", track);
      tick.style.left = (100 * sc.start / self.duration) + "%";
      tick.title = sc.id;
      tick.addEventListener("click", function (ev) { ev.stopPropagation(); self.seek(sc.start); });
    });
    this.track = track;
    track.addEventListener("click", function (ev) {
      var r = track.getBoundingClientRect();
      self.seek(((ev.clientX - r.left) / r.width) * self.duration);
    });

    this.timeEl = el("div", "gd-sr-time", ctr);
    this.timeEl.textContent = "0:00 / " + fmt(this.duration);

    this.speedBtn = el("button", "gd-sr-btn gd-sr-speed", ctr);
    this.speedBtn.textContent = "1×";
    this.speedBtn.addEventListener("click", function () { self.cycleSpeed(); });

    this.ccBtn = el("button", "gd-sr-btn is-on", ctr);
    this.ccBtn.textContent = "CC";
    this.ccBtn.addEventListener("click", function () { self.toggleCaptions(); });

    // Background music bed (looped, at configured gain; ducking is ffmpeg-only).
    this._music = null;
    var music = this.m.music;
    if (music && music.file) {
      var a = new Audio(srcUrl(this.base, music.file));
      a.loop = true;
      var g = music.gain_db != null ? music.gain_db : -22;
      a.volume = clamp(Math.pow(10, g / 20), 0, 1);
      this._music = a;
    }

    // Sound effects (preloaded; fired once by the clock during playback).
    this._sfx = (this.m.sfx || []).map(function (ev) {
      var a = new Audio(srcUrl(self.base, ev.file));
      a.preload = "auto";
      a.volume = clamp(Math.pow(10, (ev.gain_db != null ? ev.gain_db : -8) / 20), 0, 1);
      return { time: ev.time, el: a };
    });
    this._sfxFired = this._sfx.map(function () { return false; });

    // Re-fit code scenes when the stage resizes (invalidate; render refits).
    if (window.ResizeObserver) {
      this._ro = new ResizeObserver(function () {
        self._sceneEls.forEach(function (s) { if (s._steps) s._fitted = false; });
        if (!self.playing) self.render();
      });
      this._ro.observe(this.stage);
    }

    this.root.tabIndex = 0;
    this.root.addEventListener("keydown", function (ev) { self._onKey(ev); });
  };

  // Mark SFX at or before the current time as already fired (so seeking never
  // retro-fires; events after `time` stay armed to fire on forward playback).
  Player.prototype._syncSfxFired = function () {
    for (var i = 0; i < this._sfx.length; i++) {
      this._sfxFired[i] = this._sfx[i].time <= this.time + 1e-6;
    }
  };
  Player.prototype._triggerSfx = function () {
    if (this.exporting) return; // export muxes SFX via ffmpeg
    for (var i = 0; i < this._sfx.length; i++) {
      if (!this._sfxFired[i] && this._sfx[i].time <= this.time) {
        this._sfxFired[i] = true;
        var a = this._sfx[i].el;
        try { a.currentTime = 0; a.play().catch(function () {}); } catch (e) {}
      }
    }
  };

  Player.prototype._buildScene = function (sc, stage) {
    var self = this;
    var scene = el("div", "gd-sr-scene", stage);
    scene.style.setProperty("--sr-fade", (sc.transition_duration || 0.5) + "s");
    var motion = el("div", "gd-sr-motion", scene);
    var layer = sc.layer || {};

    if (sc.type === "image" && sc.src) {
      var img = el("img", null, motion);
      img.src = srcUrl(this.base, sc.src);
      img.alt = layer.title || sc.id;
    } else if (sc.keyframes && sc.keyframes.length && !sc.deferred) {
      var fwrap = el("div", "gd-sr-frames", motion);
      scene._frames = sc.keyframes.map(function (kf) {
        var fEl = el("div", "gd-sr-frame", fwrap);
        var im = el("img", null, fEl);
        im.src = srcUrl(self.base, kf.file);
        im.alt = kf.label || sc.id;
        return fEl;
      });
    } else if (sc.type === "code" && sc.code_steps) {
      var wrap = el("div", "gd-sr-code-wrap", motion);
      scene._steps = sc.code_steps.map(function (cs) {
        var stepEl = el("div", "gd-sr-code-step", wrap);
        var inner = el("div", "gd-sr-code-inner", stepEl);
        inner.innerHTML = cs.html;
        var caret = el("span", "gd-sr-caret", inner);
        caret.style.display = "none";
        return { el: stepEl, inner: inner, caret: caret, typing: cs.typing };
      });
    } else {
      var box = el("div", "gd-sr-text", motion);
      var brand = this.m.brand || {};
      if (brand.logo && (sc.type === "title" || sc.type === "card")) {
        var logo = el("img", "gd-sr-logo", box);
        logo.src = srcUrl(this.base, brand.logo);
        logo.alt = "";
        scene._logo = logo;
      }
      if (layer.title) { var t = el("h2", "sr-title", box); t.textContent = layer.title; }
      if (layer.subtitle) { var s = el("p", "sr-subtitle", box); s.textContent = layer.subtitle; }
      if (layer.body) { var b = el("p", "sr-body", box); b.textContent = layer.body; }
      if (layer.cta) { var c = el("span", "sr-cta", box); c.textContent = layer.cta; }
      if (!layer.title && !layer.body && sc.deferred) {
        var d = el("p", "sr-subtitle", box);
        d.textContent = "“" + sc.type + "” scene — capture lands in a later phase";
      }
    }
    if (sc.deferred) { var badge = el("div", "gd-sr-badge", scene); badge.textContent = sc.type; }

    // Overlays + synthetic cursor live above the scene media and fade with it.
    scene._overlays = (sc.overlays || []).map(function (ov) {
      return self._buildOverlay(ov, scene);
    });
    scene._cursorKeys = sc.cursor || [];
    scene._cursor = scene._cursorKeys.length ? self._buildCursor(scene) : null;

    scene._motion = motion;
    scene._scene = sc;
    scene._audio = null;
    return scene;
  };

  Player.prototype._buildOverlay = function (ov, parent) {
    var o = el("div", "gd-sr-ov gd-sr-ov-" + ov.type, parent);
    var r = ov.rect || [0.3, 0.3, 0.4, 0.2];
    o.style.left = (r[0] * 100) + "%";
    o.style.top = (r[1] * 100) + "%";
    o.style.width = (r[2] * 100) + "%";
    o.style.height = (r[3] * 100) + "%";
    o.style.setProperty("--ov-color", ov.color || "#f1fa8c");
    o.style.opacity = "0";
    if (ov.text && (ov.type === "label" || ov.type === "callout")) {
      var pill = el("div", "gd-sr-ov-label", o);
      pill.textContent = ov.text;
    }
    return { el: o, ov: ov };
  };

  Player.prototype._buildCursor = function (parent) {
    var c = el("div", "gd-sr-cursor", parent);
    c.innerHTML =
      '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">' +
      '<path d="M5 3l14 8-6 1.5L9.5 19z" fill="#fff" stroke="#111" stroke-width="1.3" ' +
      'stroke-linejoin="round"/></svg>';
    c._ripple = el("span", "gd-sr-cursor-ripple", c);
    c.style.opacity = "0";
    return c;
  };

  Player.prototype._audioFor = function (sceneEl) {
    var sc = sceneEl._scene;
    if (!sc.audio) return null;
    if (!sceneEl._audio) {
      var a = new Audio(srcUrl(this.base, sc.audio));
      a.preload = "auto";
      sceneEl._audio = a;
    }
    return sceneEl._audio;
  };

  Player.prototype._activeSceneIndex = function (t) {
    for (var i = 0; i < this.scenes.length; i++) {
      if (t >= this.scenes[i].start && t < this.scenes[i].end) return i;
    }
    return this.scenes.length - 1;
  };

  // Opacity of a scene at the global clock — a pure function of time, so a
  // seeked frame is deterministic (no real-time CSS transitions). Adjacent
  // scenes crossfade over `transition_duration` at their shared boundary.
  Player.prototype._sceneOpacity = function (sc, t) {
    var td = sc.transition === "cut" ? 0.001 : (sc.transition_duration || 0.5);
    if (t < sc.start) return 0;
    if (t < sc.start + td) return clamp((t - sc.start) / td, 0, 1);
    if (t < sc.end) return 1;
    if (t < sc.end + td) return clamp(1 - (t - sc.end) / td, 0, 1);
    return 0;
  };

  Player.prototype.render = function () {
    var idx = this._activeSceneIndex(this.time);
    for (var i = 0; i < this._sceneEls.length; i++) {
      var sEl = this._sceneEls[i], sc = sEl._scene;
      var op = this._sceneOpacity(sc, this.time);
      sEl.style.opacity = op.toFixed(3);
      if (op > 0) {
        var span = Math.max(0.001, sc.end - sc.start);
        var p = clamp((this.time - sc.start) / span, 0, 1);
        if (sc.type === "code" && sEl._steps) {
          sEl._motion.style.transform = "";
          if (!sEl._fitted) this._fitCode(sEl);
          this._renderCode(sEl, p);
        } else {
          sEl._motion.style.transform = motionTransform(sc.motion, p);
          if (sEl._frames) this._renderFrames(sEl, p);
        }
        if (sEl._logo) this._animLogo(sEl, this.time - sc.start);
        this._renderOverlays(sEl, this.time - sc.start);
        this._renderCursor(sEl, this.time - sc.start);
      }
    }
    this._syncAudio(idx);
    this._renderCaptions(idx);
    if (this.duration) this.fill.style.width = (100 * this.time / this.duration) + "%";
    this.timeEl.textContent = fmt(this.time) + " / " + fmt(this.duration);
  };

  // Play the active scene's narration. The audio clip is seeked ONCE when its
  // scene becomes active, then left to play on its own clock — re-seeking every
  // frame fights the audio's start-up latency and stutters it word-by-word.
  Player.prototype._syncAudio = function (idx) {
    if (this.exporting || !this.playing) return;
    if (this._audioIdx === idx) return; // same scene: already playing, don't touch
    if (this._audioIdx >= 0 && this._sceneEls[this._audioIdx]) {
      var prev = this._audioFor(this._sceneEls[this._audioIdx]);
      if (prev && !prev.paused) prev.pause();
    }
    this._audioIdx = idx;
    var au = this._audioFor(this._sceneEls[idx]);
    if (!au) return;
    var sc = this.scenes[idx];
    var want = this.time - sc.start;
    want = au.duration > 0 ? clamp(want, 0, au.duration) : Math.max(0, want);
    try { au.currentTime = want; } catch (e) {}
    au.playbackRate = this.speed;
    au.play().catch(function () {});
  };

  // Export mode: freeze residual CSS transitions/animations so each seeked
  // frame is byte-stable for the headless capturer.
  Player.prototype.setExport = function (on) {
    this.exporting = !!on;
    this.root.classList.toggle("gd-sr-exporting", this.exporting);
  };

  // Clock-driven crossfade across N items (code steps / web frames). Returns
  // the per-item opacity array plus the active index and its local progress.
  function xfade(p, n, w) {
    var sf = p * n, idx = clamp(Math.floor(sf), 0, n - 1), frac = clamp(sf - idx, 0, 1);
    var ops = new Array(n);
    for (var i = 0; i < n; i++) ops[i] = 0;
    if (idx < n - 1 && frac > 1 - w) {
      ops[idx] = 1 - (frac - (1 - w)) / w;
      ops[idx + 1] = (frac - (1 - w)) / w;
    } else {
      ops[idx] = 1;
    }
    return { ops: ops, idx: idx, frac: frac };
  }

  // Auto-fit: uniformly scale a code scene's blocks so the widest line and the
  // tallest step fit the frame, keeping the block centered at any size. One
  // scale for all steps (so they don't resize between magic-move steps).
  Player.prototype._fitCode = function (sEl) {
    var wrap = sEl.querySelector(".gd-sr-code-wrap");
    if (!wrap || !sEl._steps || !sEl._steps.length) return;
    var availW = wrap.clientWidth, availH = wrap.clientHeight;
    if (!availW || !availH) return; // not laid out yet — try again next frame
    // Reserve room for the caption so tall code shrinks to sit above it, then
    // center the code in the remaining (upper) space.
    var sc = sEl._scene;
    var capReserve = (sc && sc.say && sc.captions !== false) ? availH * 0.24 : 0;
    var fitH = availH - capReserve;
    var maxW = 1, maxH = 1;
    sEl._steps.forEach(function (s) {
      s.inner.style.transform = "none"; // measure natural size
      var code = s.inner.querySelector(".gd-sr-code");
      if (code) { maxW = Math.max(maxW, code.offsetWidth); maxH = Math.max(maxH, code.offsetHeight); }
    });
    var scale = Math.min(1, (availW * 0.97) / maxW, (fitH * 0.97) / maxH);
    sEl._steps.forEach(function (s) {
      s.inner.style.transform = "scale(" + scale.toFixed(4) + ")";
      s.el.style.paddingBottom = capReserve.toFixed(0) + "px"; // center above the caption
    });
    sEl._fitted = true;
  };

  Player.prototype._renderCode = function (sEl, p) {
    var steps = sEl._steps, n = steps.length;
    var x = xfade(p, n, 0.18);
    for (var i = 0; i < n; i++) {
      var s = steps[i];
      s.el.style.opacity = clamp(x.ops[i], 0, 1).toFixed(3);
      if (i === x.idx && s.typing) {
        var reveal = clamp(x.frac / 0.6, 0, 1); // type out over the first 60% of the step
        s.inner.style.clipPath = "inset(0 " + ((1 - reveal) * 100).toFixed(2) + "% 0 0)";
        if (reveal < 1) {
          s.caret.style.display = "block";
          s.caret.style.left = (reveal * 100).toFixed(2) + "%";
        } else {
          s.caret.style.display = "none";
        }
      } else {
        s.inner.style.clipPath = "";
        s.caret.style.display = "none";
      }
    }
  };

  Player.prototype._animLogo = function (sEl, lt) {
    var e = 1 - Math.pow(1 - clamp(lt / 0.6, 0, 1), 3); // easeOutCubic entrance
    sEl._logo.style.opacity = e.toFixed(3);
    sEl._logo.style.transform = "scale(" + (0.85 + 0.15 * e).toFixed(3) + ")";
  };

  Player.prototype._renderFrames = function (sEl, p) {
    var frames = sEl._frames, x = xfade(p, frames.length, 0.22);
    for (var i = 0; i < frames.length; i++) {
      frames[i].style.opacity = clamp(x.ops[i], 0, 1).toFixed(3);
    }
  };

  Player.prototype._renderOverlays = function (sEl, lt) {
    (sEl._overlays || []).forEach(function (o) {
      var ov = o.ov, t0 = ov.at, t1 = ov.at + ov.duration, f = ov.fade || 0.3;
      var op = 0;
      if (lt >= t0 && lt <= t1) {
        op = f > 0 ? clamp(Math.min((lt - t0) / f, (t1 - lt) / f, 1), 0, 1) : 1;
      }
      o.el.style.opacity = op.toFixed(3);
    });
  };

  Player.prototype._renderCursor = function (sEl, lt) {
    var c = sEl._cursor, keys = sEl._cursorKeys;
    if (!c || !keys.length) return;
    if (lt < keys[0].at) { c.style.opacity = "0"; return; }
    c.style.opacity = "1";
    var pos = keys[keys.length - 1];
    for (var i = 0; i < keys.length - 1; i++) {
      var a = keys[i], b = keys[i + 1];
      if (lt >= a.at && lt <= b.at) {
        var span = Math.max(0.001, b.at - a.at);
        var f = (lt - a.at) / span;
        f = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2; // easeInOutQuad
        pos = { x: lerp(a.x, b.x, f), y: lerp(a.y, b.y, f) };
        break;
      }
    }
    c.style.left = (pos.x * 100) + "%";
    c.style.top = (pos.y * 100) + "%";
    // Click ripple: animate for ~0.5s after any click waypoint.
    var elapsed = null;
    for (var k = 0; k < keys.length; k++) {
      if (keys[k].click && lt >= keys[k].at && lt - keys[k].at < 0.5) elapsed = lt - keys[k].at;
    }
    if (elapsed != null) {
      var e = elapsed / 0.5;
      c._ripple.style.opacity = (1 - e).toFixed(3);
      c._ripple.style.transform = "translate(-50%,-50%) scale(" + (0.3 + e * 1.7).toFixed(3) + ")";
    } else {
      c._ripple.style.opacity = "0";
    }
  };

  Player.prototype._buildCaption = function (sc) {
    this.capEl.innerHTML = "";
    this._capWords = null;
    if (sc.words && sc.words.length) {
      var words = [];
      var frag = document.createDocumentFragment();
      sc.words.forEach(function (wt) {
        var span = el("span", "gd-sr-cap-word", null);
        span.textContent = wt[0];
        frag.appendChild(span);
        frag.appendChild(document.createTextNode(" "));
        words.push({ el: span, start: wt[1], end: wt[2] });
      });
      this.capEl.appendChild(frag);
      this._capWords = words;
    } else {
      this.capEl.textContent = sc.say;
    }
  };

  Player.prototype._renderCaptions = function (idx) {
    var sc = this.scenes[idx];
    var show = this.captionsOn && sc && sc.captions !== false && sc.say;
    if (!show) { this.capEl.classList.remove("is-visible"); return; }
    this.capEl.classList.add("is-visible");
    if (this._capIdx !== idx) { this._buildCaption(sc); this._capIdx = idx; }
    if (this._capWords) {
      var lt = this.time - sc.start;
      for (var i = 0; i < this._capWords.length; i++) {
        var w = this._capWords[i];
        w.el.classList.toggle("is-spoken", lt >= w.start);
        w.el.classList.toggle("is-active", lt >= w.start && lt < w.end);
      }
    }
  };

  Player.prototype._tick = function (ts) {
    if (!this.playing) return;
    var dt = (ts - this._last) / 1000;
    this._last = ts;
    this.time += dt * this.speed;
    this._triggerSfx();
    if (this.time >= this.duration) { this.time = this.duration; this.pause(); this.render(); return; }
    this.render();
    this._raf = requestAnimationFrame(this._tick.bind(this));
  };

  Player.prototype.play = function () {
    if (this.playing) return;
    if (this.time >= this.duration) this.time = 0;
    this.playing = true;
    this.playBtn.innerHTML = "&#10073;&#10073;";
    this._last = performance.now();
    if (this._music && !this.exporting) this._music.play().catch(function () {});
    this._raf = requestAnimationFrame(this._tick.bind(this));
  };

  Player.prototype.pause = function () {
    this.playing = false;
    this.playBtn.innerHTML = "&#9654;";
    if (this._raf) cancelAnimationFrame(this._raf);
    this._sceneEls.forEach(function (s) { if (s._audio && !s._audio.paused) s._audio.pause(); });
    if (this._music && !this._music.paused) this._music.pause();
    this._audioIdx = -1; // re-sync narration to the clock on resume
  };

  Player.prototype.toggle = function () { this.playing ? this.pause() : this.play(); };

  Player.prototype.seek = function (t) {
    this.time = clamp(t, 0, this.duration);
    this._sceneEls.forEach(function (s) { if (s._audio) s._audio.pause(); });
    this._audioIdx = -1; // narration re-syncs to the new position on next play
    this._syncSfxFired();
    this.render();
  };

  Player.prototype.cycleSpeed = function () {
    var steps = [0.5, 1, 1.5, 2];
    this.speed = steps[(steps.indexOf(this.speed) + 1) % steps.length];
    this.speedBtn.textContent = this.speed + "×";
  };

  Player.prototype.toggleCaptions = function () {
    this.captionsOn = !this.captionsOn;
    this.root.classList.toggle("captions-off", !this.captionsOn);
    this.ccBtn.classList.toggle("is-on", this.captionsOn);
    this.render();
  };

  Player.prototype._onKey = function (ev) {
    if (ev.key === " ") { ev.preventDefault(); this.toggle(); }
    else if (ev.key === "ArrowRight") { this.seek(this.time + 5); }
    else if (ev.key === "ArrowLeft") { this.seek(this.time - 5); }
    else if (ev.key === "c" || ev.key === "C") { this.toggleCaptions(); }
  };

  function mount(rootEl, manifest, opts) {
    var p = new Player(rootEl, manifest, opts);
    // Export/automation hook: a deterministic clock the headless capturer drives.
    window.__showreel = {
      player: p,
      duration: function () { return p.duration; },
      seek: function (t) { p.pause(); p.seek(t); },
      play: function () { p.play(); },
      pause: function () { p.pause(); },
      exportMode: function (on) { p.setExport(on); }
    };
    return p;
  }

  // Auto-mount any embedded players (Quarto shortcode path, P6).
  function autoMount() {
    var nodes = document.querySelectorAll(".gd-showreel[data-manifest-id]");
    nodes.forEach(function (node) {
      var src = document.getElementById(node.getAttribute("data-manifest-id"));
      if (src) mount(node, JSON.parse(src.textContent), { base: node.getAttribute("data-base") || "." });
    });
  }

  window.GreatShowreel = { mount: mount, Player: Player, autoMount: autoMount };
  if (document.readyState !== "loading") autoMount();
  else document.addEventListener("DOMContentLoaded", autoMount);
})();
