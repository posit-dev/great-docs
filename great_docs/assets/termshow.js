/**
 * Great Docs Termshow Player
 *
 * A lightweight player for pre-rendered SVG terminal recordings.
 * Loads a manifest.json and displays keyframe SVGs with timeline navigation,
 * chapter markers, annotations, and keyboard controls.
 */
(function () {
  'use strict';

  const PLAYER_CLASS = 'gd-termshow';
  const ACTIVE_CLASS = 'gd-tp-active';

  /**
   * Fetch a resource as text or JSON, with file:// fallback via XHR.
   */
  function fetchResource(url, asJson) {
    if (window.location.protocol === 'file:') {
      return new Promise(function (resolve, reject) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.onload = function () {
          if (xhr.status === 0 || xhr.status === 200) {
            resolve(asJson ? JSON.parse(xhr.responseText) : xhr.responseText);
          } else {
            reject(new Error('XHR ' + xhr.status));
          }
        };
        xhr.onerror = function () { reject(new Error('XHR network error')); };
        xhr.send();
      });
    }
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return asJson ? r.json() : r.text();
    });
  }

  /**
   * Initialize all termshow player instances on the page.
   */
  function initAll() {
    const players = document.querySelectorAll(`.${PLAYER_CLASS}`);
    players.forEach((el) => initPlayer(el));
  }

  /**
   * Initialize a single termshow player instance.
   */
  function initPlayer(container) {
    const manifestUrl = container.dataset.manifest;
    if (!manifestUrl) return;

    // Prevent double-init
    if (container.classList.contains(ACTIVE_CLASS)) return;
    container.classList.add(ACTIVE_CLASS);

    const options = {
      autoplay: container.dataset.autoplay === 'true',
      speed: parseFloat(container.dataset.speed) || 1.0,
      pauseOnChapters: container.dataset.pauseOnChapters === 'true',
      loop: container.dataset.loop === 'true',
    };

    // Create player state
    const state = {
      manifest: null,
      frames: null,
      currentTime: 0,
      playing: false,
      ended: false,
      chapterPaused: false,
      currentKeyframeIdx: -1,
      animFrameId: null,
      lastTick: null,
      speed: options.speed,
      baseUrl: manifestUrl.substring(0, manifestUrl.lastIndexOf('/') + 1),
    };

    // Try to read inline manifest + frames (embedded by Lua filter)
    var inlineManifest = null;
    var inlineFrames = null;
    var manifestEl = container.querySelector('script.gd-tp-manifest');
    var framesEl = container.querySelector('script.gd-tp-frames');
    if (manifestEl) {
      try { inlineManifest = JSON.parse(manifestEl.textContent); } catch (e) {}
    }
    if (framesEl) {
      try { inlineFrames = JSON.parse(framesEl.textContent); } catch (e) {}
    }

    // Title bar (separate from viewport, above it)
    const chapterBar = document.createElement('div');
    chapterBar.className = 'gd-tp-chapter-bar';

    // Build player DOM
    const viewport = document.createElement('div');
    viewport.className = 'gd-tp-viewport';
    // Defer tabindex until user interaction to prevent Safari from treating
    // auto-playing players as scroll-restoration targets.
    if (!options.autoplay) {
      viewport.setAttribute('tabindex', '0');
    }
    viewport.setAttribute('role', 'application');
    viewport.setAttribute('aria-label', 'Terminal recording player');

    const svgContainer = document.createElement('div');
    svgContainer.className = 'gd-tp-svg';
    viewport.appendChild(svgContainer);

    const annotationLayer = document.createElement('div');
    annotationLayer.className = 'gd-tp-annotations';
    viewport.appendChild(annotationLayer);

    // Center overlay (play / replay)
    const centerOverlay = document.createElement('div');
    centerOverlay.className = 'gd-tp-center-overlay';
    centerOverlay.setAttribute('aria-hidden', 'true');
    const centerBtn = document.createElement('div');
    centerBtn.className = 'gd-tp-center-overlay-btn';
    centerBtn.innerHTML = '<span class="gd-tp-icon-play">\u25b6</span>';
    centerOverlay.appendChild(centerBtn);
    viewport.appendChild(centerOverlay);

    const controls = buildControls();

    // Replace container content with player structure
    container.innerHTML = '';
    container.appendChild(chapterBar);
    container.appendChild(viewport);
    container.appendChild(controls.root);

    // Initialize with manifest (inline or fetched)
    function activate(manifest, frames) {
      state.manifest = manifest;
      state.frames = frames;
      controls.duration.textContent = formatTime(manifest.duration);
      renderChapterMarkers(controls.timeline, manifest);

      // Add traffic light decorations if window_chrome is set
      var chrome = manifest.window_chrome || 'none';
      var hasChapters = manifest.chapters && manifest.chapters.length > 0;
      if (chrome === 'none' && !hasChapters) {
        chapterBar.style.display = 'none';
      } else if (chrome !== 'none') {
        chapterBar.classList.add('gd-tp-has-chrome');
        var lights = document.createElement('div');
        lights.className = 'gd-tp-traffic-lights' + (chrome === 'minimal' ? ' gd-tp-chrome-minimal' : '');
        lights.innerHTML = '<span class="gd-tp-traffic-dot gd-tp-dot-close"></span>' +
          '<span class="gd-tp-traffic-dot gd-tp-dot-minimize"></span>' +
          '<span class="gd-tp-traffic-dot gd-tp-dot-maximize"></span>';
        chapterBar.appendChild(lights);
      }

      // Add a span for chapter text (so traffic lights aren't overwritten)
      var chapterText = document.createElement('span');
      chapterText.className = 'gd-tp-chapter-text';
      chapterBar.appendChild(chapterText);
      state.chapterText = chapterText;

      updateChapterBar(chapterBar, manifest, 0);
      // Show initial frame
      showFrame(state, svgContainer, 0);
      if (options.autoplay) {
        play(state, svgContainer, annotationLayer, controls, options, container, centerOverlay, chapterBar);
      }
    }

    if (inlineManifest) {
      // Always try fetching the external manifest first (it reflects the latest
      // termshow render without requiring an HTML rebuild). Fall back to inline
      // data if the fetch fails (file:// protocol, offline, etc.).
      fetchResource(manifestUrl, true)
        .then(function (manifest) { activate(manifest, null); })
        .catch(function () { activate(inlineManifest, inlineFrames); });
    } else {
      // No inline data: fetch is the only option
      fetchResource(manifestUrl, true)
        .then(function (manifest) { activate(manifest, null); })
        .catch(function (err) {
          console.warn('[termshow] Failed to load manifest:', manifestUrl, err);
        });
    }

    // Restore tabindex on first user interaction (for keyboard nav)
    function ensureTabindex() {
      if (!viewport.hasAttribute('tabindex')) {
        viewport.setAttribute('tabindex', '0');
      }
    }

    // Event listeners
    controls.playBtn.addEventListener('click', () => {
      ensureTabindex();
      if (state.playing) {
        pause(state, controls, container, centerOverlay);
      } else if (state.ended) {
        // Return to initial state (don't autoplay)
        state.ended = false;
        state.currentTime = 0;
        state.currentKeyframeIdx = -1;
        controls.playBtn.textContent = '\u25b6';
        controls.playBtn.setAttribute('aria-label', 'Play');
        centerBtn.innerHTML = '<span class="gd-tp-icon-play">\u25b6</span>';
        container.classList.remove('gd-tp-ended');
        updateDisplay(state, svgContainer, annotationLayer, controls);
        updateChapterBar(chapterBar, state.manifest, state.currentTime);
      } else {
        play(state, svgContainer, annotationLayer, controls, options, container, centerOverlay, chapterBar);
      }
    });

    centerOverlay.addEventListener('click', () => {
      ensureTabindex();
      if (state.ended) {
        // Return to initial state (don't autoplay)
        state.ended = false;
        state.currentTime = 0;
        state.currentKeyframeIdx = -1;
        controls.playBtn.textContent = '\u25b6';
        controls.playBtn.setAttribute('aria-label', 'Play');
        centerBtn.innerHTML = '<span class="gd-tp-icon-play">\u25b6</span>';
        container.classList.remove('gd-tp-ended');
        updateDisplay(state, svgContainer, annotationLayer, controls);
        updateChapterBar(chapterBar, state.manifest, state.currentTime);
        return;
      }
      play(state, svgContainer, annotationLayer, controls, options, container, centerOverlay, chapterBar);
    });

    controls.timeline.addEventListener('click', (e) => {
      if (!state.manifest) return;
      const rect = controls.timeline.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      // Reset ended/chapter-paused state if seeking
      if (state.ended) {
        state.ended = false;
        controls.playBtn.textContent = '\u25b6';
        controls.playBtn.setAttribute('aria-label', 'Play');
        centerBtn.innerHTML = '<span class="gd-tp-icon-play">\u25b6</span>';
        container.classList.remove('gd-tp-ended');
      }
      state.chapterPaused = false;
      container.classList.remove('gd-tp-chapter-paused');
      seek(state, ratio * state.manifest.duration, svgContainer, annotationLayer, controls);
      updateChapterBar(chapterBar, state.manifest, state.currentTime);
    });

    // Speed control
    controls.speedBtn.addEventListener('click', () => {
      const speeds = [0.5, 1, 1.5, 2, 3];
      const idx = speeds.indexOf(state.speed);
      state.speed = speeds[(idx + 1) % speeds.length];
      controls.speedBtn.textContent = state.speed + '\u00d7';
    });

    // Keyboard navigation
    viewport.addEventListener('keydown', (e) => {
      if (!state.manifest) return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          if (state.playing) pause(state, controls, container, centerOverlay);
          else if (state.ended) {
            state.ended = false;
            state.currentTime = 0;
            state.currentKeyframeIdx = -1;
            controls.playBtn.textContent = '\u25b6';
            controls.playBtn.setAttribute('aria-label', 'Play');
            centerBtn.innerHTML = '<span class="gd-tp-icon-play">\u25b6</span>';
            container.classList.remove('gd-tp-ended');
            updateDisplay(state, svgContainer, annotationLayer, controls);
            updateChapterBar(chapterBar, state.manifest, state.currentTime);
          } else {
            play(state, svgContainer, annotationLayer, controls, options, container, centerOverlay, chapterBar);
          }
          break;
        case 'ArrowRight':
          e.preventDefault();
          seek(state, state.currentTime + 5, svgContainer, annotationLayer, controls);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          seek(state, state.currentTime - 5, svgContainer, annotationLayer, controls);
          break;
        case '.':
          e.preventDefault();
          nextChapter(state, svgContainer, annotationLayer, controls);
          break;
        case ',':
          e.preventDefault();
          prevChapter(state, svgContainer, annotationLayer, controls);
          break;
      }
    });
  }

  // --- Playback ---

  function play(state, svgContainer, annotationLayer, controls, options, container, centerOverlay, chapterBar) {
    state.playing = true;
    state.ended = false;
    state.chapterPaused = false;
    state.lastTick = performance.now();
    controls.playBtn.textContent = '\u275a\u275a'; // ❚❚
    controls.playBtn.setAttribute('aria-label', 'Pause');
    container.classList.add('gd-tp-playing');
    container.classList.remove('gd-tp-ended');
    container.classList.remove('gd-tp-chapter-paused');

    function tick(now) {
      if (!state.playing) return;

      const dt = ((now - state.lastTick) / 1000) * state.speed;
      state.lastTick = now;
      state.currentTime += dt;

      const manifest = state.manifest;
      if (state.currentTime >= manifest.duration) {
        if (options.loop) {
          state.currentTime = 0;
        } else {
          state.currentTime = manifest.duration;
          state.ended = true;
          pause(state, controls, container, centerOverlay);
          // Show replay icon in controls and overlay
          controls.playBtn.textContent = '\u21ba'; // ↺
          controls.playBtn.setAttribute('aria-label', 'Replay');
          centerOverlay.querySelector('.gd-tp-center-overlay-btn').innerHTML =
            '<span>\u21ba</span>';
          container.classList.remove('gd-tp-playing');
          container.classList.add('gd-tp-ended');
          return;
        }
      }

      // Check chapter pause
      if (options.pauseOnChapters && manifest.chapters.length > 0) {
        const prevTime = state.currentTime - dt;
        for (const ch of manifest.chapters) {
          if (ch.time > 0 && prevTime < ch.time && state.currentTime >= ch.time) {
            state.currentTime = ch.time;
            state.chapterPaused = true;
            pause(state, controls, container, centerOverlay);
            updateDisplay(state, svgContainer, annotationLayer, controls);
            updateChapterBar(chapterBar, manifest, state.currentTime);
            return;
          }
        }
      }

      updateDisplay(state, svgContainer, annotationLayer, controls);
      updateChapterBar(chapterBar, manifest, state.currentTime);
      state.animFrameId = requestAnimationFrame(tick);
    }

    state.animFrameId = requestAnimationFrame(tick);
  }

  function pause(state, controls, container, centerOverlay) {
    state.playing = false;
    if (state.animFrameId) {
      cancelAnimationFrame(state.animFrameId);
      state.animFrameId = null;
    }
    if (!state.ended) {
      controls.playBtn.textContent = '\u25b6'; // ▶
      controls.playBtn.setAttribute('aria-label', 'Play');
    }
    if (container) {
      container.classList.remove('gd-tp-playing');
      // Hide center overlay on chapter pauses (only show at start/end)
      if (state.chapterPaused) {
        container.classList.add('gd-tp-chapter-paused');
      } else {
        container.classList.remove('gd-tp-chapter-paused');
      }
    }
  }

  function seek(state, time, svgContainer, annotationLayer, controls) {
    state.currentTime = Math.max(0, Math.min(time, state.manifest.duration));
    updateDisplay(state, svgContainer, annotationLayer, controls);
  }

  function nextChapter(state, svgContainer, annotationLayer, controls) {
    if (!state.manifest || !state.manifest.chapters.length) return;
    for (const ch of state.manifest.chapters) {
      if (ch.time > state.currentTime + 0.1) {
        seek(state, ch.time, svgContainer, annotationLayer, controls);
        return;
      }
    }
  }

  function prevChapter(state, svgContainer, annotationLayer, controls) {
    if (!state.manifest || !state.manifest.chapters.length) return;
    const chapters = state.manifest.chapters;
    for (let i = chapters.length - 1; i >= 0; i--) {
      if (chapters[i].time < state.currentTime - 0.5) {
        seek(state, chapters[i].time, svgContainer, annotationLayer, controls);
        return;
      }
    }
    seek(state, 0, svgContainer, annotationLayer, controls);
  }

  // --- Display ---

  function updateDisplay(state, svgContainer, annotationLayer, controls) {
    const manifest = state.manifest;
    if (!manifest) return;

    // Update timeline progress
    const progress = manifest.duration > 0 ? state.currentTime / manifest.duration : 0;
    controls.progress.style.width = (progress * 100) + '%';
    controls.time.textContent = formatTime(state.currentTime);
    controls.duration.textContent = formatTime(manifest.duration - state.currentTime);

    // Find the correct keyframe for current time
    const kfIdx = findKeyframeIndex(manifest.keyframes, state.currentTime);
    if (kfIdx !== state.currentKeyframeIdx) {
      state.currentKeyframeIdx = kfIdx;
      showFrame(state, svgContainer, kfIdx);
    }

    // Update annotations
    updateAnnotations(annotationLayer, manifest.annotations, state.currentTime);
  }

  function updateChapterBar(chapterBar, manifest, time) {
    var textEl = chapterBar.querySelector('.gd-tp-chapter-text');
    if (!textEl) return;
    if (!manifest || !manifest.chapters || manifest.chapters.length === 0) {
      textEl.textContent = '';
      return;
    }
    // Find the current chapter (last one at or before current time)
    var label = '';
    for (let i = manifest.chapters.length - 1; i >= 0; i--) {
      if (manifest.chapters[i].time <= time + 0.05) {
        label = manifest.chapters[i].label || '';
        break;
      }
    }
    textEl.textContent = label;
  }

  function showFrame(state, svgContainer, idx) {
    const manifest = state.manifest;
    if (!manifest || idx < 0 || idx >= manifest.keyframes.length) return;

    // Pin height before replacing innerHTML to prevent layout collapse.
    // All frames in a recording share the same dimensions, so we pin once
    // and keep it for the lifetime of playback. This prevents Safari's
    // scroll-preservation heuristic from firing on the last player where
    // even a sub-frame height flicker affects scrollHeight.
    if (!svgContainer.style.minHeight) {
      var pinHeight = svgContainer.offsetHeight;
      if (pinHeight > 0) {
        svgContainer.style.minHeight = pinHeight + 'px';
      }
    }

    // Use inline frames if available (no fetch needed)
    if (state.frames && state.frames[idx]) {
      svgContainer.innerHTML = state.frames[idx];
      return;
    }

    // Fallback: fetch the SVG file
    const kf = manifest.keyframes[idx];
    const svgUrl = state.baseUrl + kf.file;

    fetchResource(svgUrl, false)
      .then((svg) => {
        svgContainer.innerHTML = svg;
      })
      .catch(() => {});
  }

  function findKeyframeIndex(keyframes, time) {
    // Find the last keyframe at or before the current time
    let idx = 0;
    for (let i = keyframes.length - 1; i >= 0; i--) {
      if (keyframes[i].time <= time) {
        idx = i;
        break;
      }
    }
    return idx;
  }

  function updateAnnotations(layer, annotations, time) {
    if (!annotations || annotations.length === 0) {
      for (var i = 0; i < layer.children.length; i++) {
        layer.children[i].style.opacity = '0';
      }
      return;
    }

    // Pre-create elements with full styling at init time. Once created, ONLY
    // opacity is mutated per-frame. This prevents Safari from re-evaluating
    // position styles (top/bottom/margin-block) during playback, which triggers
    // its scroll-position recalculation bug.
    if (!layer._annEls) {
      layer._annEls = [];
      for (var j = 0; j < annotations.length; j++) {
        var ann0 = annotations[j];
        var el = document.createElement('div');
        var wCls = ann0.width && ann0.width !== 'medium' ? ' gd-tp-ann-w-' + ann0.width : '';
        el.className = 'gd-tp-annotation gd-tp-ann-' + ann0.position + ' gd-tp-ann-' + ann0.style + wCls;
        el.textContent = ann0.text;
        el.style.opacity = '0';
        el.setAttribute('aria-hidden', 'true');
        layer.appendChild(el);
        layer._annEls.push(el);
      }
    }

    for (var k = 0; k < annotations.length; k++) {
      var ann = annotations[k];
      var node = layer._annEls[k];
      if (time >= ann.time && time <= ann.time + ann.duration) {
        // Fade progress (for smooth entry/exit)
        var elapsed = time - ann.time;
        var fadeIn = Math.min(1, elapsed / 0.3);
        var fadeOut = Math.min(1, (ann.duration - elapsed) / 0.3);
        node.style.opacity = Math.min(fadeIn, fadeOut);
      } else {
        if (node.style.opacity !== '0') node.style.opacity = '0';
      }
    }
  }

  // --- Controls UI ---

  function buildControls() {
    const root = document.createElement('div');
    root.className = 'gd-tp-controls';

    const playBtn = document.createElement('button');
    playBtn.className = 'gd-tp-play-btn';
    playBtn.textContent = '\u25b6'; // ▶
    playBtn.setAttribute('aria-label', 'Play');

    const time = document.createElement('span');
    time.className = 'gd-tp-time';
    time.textContent = '0:00';

    const timeline = document.createElement('div');
    timeline.className = 'gd-tp-timeline';
    timeline.setAttribute('role', 'slider');
    timeline.setAttribute('aria-label', 'Playback position');

    const progress = document.createElement('div');
    progress.className = 'gd-tp-progress';
    timeline.appendChild(progress);

    const duration = document.createElement('span');
    duration.className = 'gd-tp-duration';
    duration.textContent = '0:00';

    const speedBtn = document.createElement('button');
    speedBtn.className = 'gd-tp-speed-btn';
    speedBtn.textContent = '1\u00d7';
    speedBtn.setAttribute('aria-label', 'Playback speed');

    root.appendChild(playBtn);
    root.appendChild(time);
    root.appendChild(timeline);
    root.appendChild(duration);
    root.appendChild(speedBtn);

    return { root, playBtn, time, timeline, progress, duration, speedBtn };
  }

  function renderChapterMarkers(timeline, manifest) {
    if (!manifest.chapters || manifest.chapters.length === 0) return;

    for (const ch of manifest.chapters) {
      if (ch.time > manifest.duration) continue;
      const pct = manifest.duration > 0 ? (ch.time / manifest.duration) * 100 : 0;
      const marker = document.createElement('div');
      marker.className = 'gd-tp-chapter-marker';
      marker.style.left = pct + '%';
      marker.setAttribute('title', ch.label || 'Chapter');
      timeline.appendChild(marker);
    }
  }

  // --- Utilities ---

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  // --- Initialization ---

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Also handle Quarto's dynamic content loading
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === 1) {
          if (node.classList && node.classList.contains(PLAYER_CLASS)) {
            initPlayer(node);
          }
          const nested = node.querySelectorAll && node.querySelectorAll(`.${PLAYER_CLASS}`);
          if (nested) nested.forEach((el) => initPlayer(el));
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
