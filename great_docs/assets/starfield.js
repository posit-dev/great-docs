/**
 * Starfield / Neon-Ring Animation
 *
 * Dark mode:  Parallax starfield with twinkling and quasar glow effects.
 * Light mode: Retrofuturist drifting neon ellipses in a vaporwave palette.
 *
 * Both modes are interactive — moving the pointer steers the focal point.
 * Respects prefers-reduced-motion and pauses when offscreen.
 */
(function () {
  "use strict";

  /* ── Shared constants ──────────────────────────────────── */
  const MOUSE_INFLUENCE = 0.12;

  /* ── Dark-mode starfield constants ─────────────────────── */
  const STAR_COUNT     = 800;
  const SPEED          = 0.40;
  const DEPTH          = 950;
  const TWINKLE_SPEED  = 0.035;   // sine-wave twinkle rate
  const QUASAR_CHANCE  = 0.07;    // fraction of stars that glow

  /* Nebula cloud count */
  const NEBULA_COUNT   = 12;

  /* Star colour palette (dark mode) — cool whites, blues, warm hints */
  const STAR_COLORS = [
    [200, 220, 255],   // blue-white
    [255, 255, 255],   // pure white
    [180, 200, 255],   // periwinkle
    [255, 210, 180],   // warm amber (rare giant star look)
    [210, 180, 255],   // soft lavender
  ];

  /* Nebula colour palette — blues and purples */
  const NEBULA_COLORS = [
    [ 80,  80, 255],   // royal blue
    [100, 120, 255],   // cornflower
    [140,  40, 200],   // deep purple
    [100,  60, 220],   // violet-blue
    [ 60, 100, 240],   // medium blue
    [160,  60, 240],   // blue-violet
    [120,  30, 180],   // dark purple
    [ 90, 140, 255],   // soft blue
  ];

  /* ── Light-mode neon constants ───────────────────────────── */
  const RING_COUNT      = 22;
  const ORB_COUNT       = 45;
  const WIREFRAME_COUNT = 6;
  const RING_SPEED      = 0.12;
  const ORB_SPEED       = 0.08;

  /* Vaporwave / retrofuturism palette */
  const NEON_PALETTE = [
    [255,  85, 200],   // hot pink
    [  0, 230, 255],   // electric cyan
    [180, 130, 255],   // lavender
    [255, 160, 220],   // rose
    [100, 220, 255],   // sky
    [200, 100, 255],   // purple
    [255, 120, 180],   // coral-pink
    [140, 255, 240],   // mint
  ];

  /* ── Canvas setup ──────────────────────────────────────── */
  const canvas = document.getElementById("gd-starfield");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let width, height, cx, cy;
  let mouseX = 0, mouseY = 0;
  let rafId  = null;
  let visible = true;
  let frame  = 0;                // global frame counter for animation

  function isDark() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark";
  }

  function resize() {
    width  = window.innerWidth;
    height = window.innerHeight;
    canvas.width  = width  * devicePixelRatio;
    canvas.height = height * devicePixelRatio;
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    cx = width  / 2;
    cy = height / 2;
  }

  /* ── Dark-mode: star pool ──────────────────────────────── */
  var stars = [];

  function createStar(zOverride) {
    var color = STAR_COLORS[(Math.random() * STAR_COLORS.length) | 0];
    return {
      x: (Math.random() - 0.5) * width  * 2,
      y: (Math.random() - 0.5) * height * 2,
      z: zOverride !== undefined ? zOverride : Math.random() * DEPTH,
      phase: Math.random() * Math.PI * 2,           // twinkle phase offset
      quasar: Math.random() < QUASAR_CHANCE,         // whether this star glows
      r: color[0], g: color[1], b: color[2],
    };
  }

  function initStars() {
    stars = [];
    for (var i = 0; i < STAR_COUNT; i++) stars.push(createStar());
  }

  /* ── Dark-mode: nebula clouds ──────────────────────────── */
  var nebulae = [];

  function createNebula() {
    var c = NEBULA_COLORS[(Math.random() * NEBULA_COLORS.length) | 0];
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      rx: 120 + Math.random() * 250,        // horizontal radius
      ry: 80  + Math.random() * 160,         // vertical radius
      angle: Math.random() * Math.PI,        // rotation
      phase: Math.random() * Math.PI * 2,    // pulse phase offset
      drift: (Math.random() - 0.5) * 0.06,  // slow angular drift
      r: c[0], g: c[1], b: c[2],
    };
  }

  function initNebulae() {
    nebulae = [];
    for (var i = 0; i < NEBULA_COUNT; i++) nebulae.push(createNebula());
  }

  function drawNebulae() {
    var ox = (mouseX - cx) * MOUSE_INFLUENCE * 0.5;
    var oy = (mouseY - cy) * MOUSE_INFLUENCE * 0.5;

    for (var i = 0; i < nebulae.length; i++) {
      var n = nebulae[i];
      n.angle += n.drift * 0.003;
      // Gentle breathing motion
      n.x += Math.sin(frame * 0.003 + n.phase) * 0.15;
      n.y += Math.cos(frame * 0.002 + n.phase) * 0.1;

      // Wrap
      if (n.x < -300) n.x = width  + 300;
      if (n.x > width  + 300) n.x = -300;
      if (n.y < -300) n.y = height + 300;
      if (n.y > height + 300) n.y = -300;

      // Pulsate opacity
      var pulse = 0.5 + 0.5 * Math.sin(frame * 0.012 + n.phase);
      var alpha = 0.04 + pulse * 0.06;

      ctx.save();
      ctx.translate(n.x + ox, n.y + oy);
      ctx.rotate(n.angle);

      // Draw as an elliptical radial gradient
      // We scale the context to make a circle → ellipse
      ctx.scale(1, n.ry / n.rx);
      var grad = ctx.createRadialGradient(0, 0, 0, 0, 0, n.rx);
      grad.addColorStop(0,   "rgba(" + n.r + "," + n.g + "," + n.b + "," + (alpha * 1.5) + ")");
      grad.addColorStop(0.4, "rgba(" + n.r + "," + n.g + "," + n.b + "," + alpha + ")");
      grad.addColorStop(1,   "rgba(" + n.r + "," + n.g + "," + n.b + ",0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(0, 0, n.rx, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }
  }

  function drawStars() {
    var ox = cx + (mouseX - cx) * MOUSE_INFLUENCE;
    var oy = cy + (mouseY - cy) * MOUSE_INFLUENCE;

    // Draw nebulae first (behind stars)
    drawNebulae();

    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      s.z -= SPEED;
      if (s.z <= 0.5) { stars[i] = createStar(DEPTH); continue; }

      var k  = 300 / s.z;
      var sx = ox + s.x * k;
      var sy = oy + s.y * k;
      if (sx < -40 || sx > width + 40 || sy < -40 || sy > height + 40) {
        stars[i] = createStar(DEPTH); continue;
      }

      var t      = 1 - s.z / DEPTH;                       // 0=far, 1=near
      var twinkle = 0.5 + 0.5 * Math.sin(frame * TWINKLE_SPEED + s.phase);
      var alpha   = (0.30 + t * 0.65) * (0.65 + 0.35 * twinkle);

      // Dramatic size curve: stars get BIG when very close
      // Cubic easing makes close stars grow fast
      var t3     = t * t * t;
      var radius = 0.3 + t * 1.6 + t3 * 8.0;

      // Core dot
      ctx.fillStyle = "rgba(" + s.r + "," + s.g + "," + s.b + "," + alpha + ")";
      ctx.beginPath();
      ctx.arc(sx, sy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Quasar / flyby glow on nearby stars (quasars glow earlier, all big stars glow)
      var glowThreshold = s.quasar ? 0.3 : 0.7;
      if (t > glowThreshold) {
        var glowR = radius * (2.5 + t * 5);
        var glowA = alpha * 0.22 * t;
        var grad  = ctx.createRadialGradient(sx, sy, radius * 0.4, sx, sy, glowR);
        grad.addColorStop(0, "rgba(" + s.r + "," + s.g + "," + s.b + "," + glowA + ")");
        grad.addColorStop(0.5, "rgba(" + s.r + "," + s.g + "," + s.b + "," + (glowA * 0.3) + ")");
        grad.addColorStop(1, "rgba(" + s.r + "," + s.g + "," + s.b + ",0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(sx, sy, glowR, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  /* ── Light-mode: neon rings + orbs + wireframes ──────────── */
  var rings = [];
  var orbs  = [];
  var wireframes = [];

  function pickNeon() { return NEON_PALETTE[(Math.random() * NEON_PALETTE.length) | 0]; }

  function createRing() {
    var c = pickNeon();
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      rx: 30 + Math.random() * 200,
      ry: 15 + Math.random() * 100,
      angle: Math.random() * Math.PI,
      drift: (Math.random() - 0.5) * RING_SPEED,
      phase: Math.random() * Math.PI * 2,
      r: c[0], g: c[1], b: c[2],
    };
  }

  function createOrb() {
    var c = pickNeon();
    // Varied sizes: mostly small, some medium, a few large
    var sizeRoll = Math.random();
    var radius = sizeRoll < 0.5 ? 1.5 + Math.random() * 4
               : sizeRoll < 0.85 ? 5 + Math.random() * 10
               : 12 + Math.random() * 20;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      radius: radius,
      vx: (Math.random() - 0.5) * ORB_SPEED * (1 + 6 / (radius + 1)),
      vy: (Math.random() - 0.5) * ORB_SPEED * (1 + 6 / (radius + 1)),
      phase: Math.random() * Math.PI * 2,
      r: c[0], g: c[1], b: c[2],
    };
  }

  /* 3D wireframe shapes — cube and octahedron vertex definitions */
  var CUBE_VERTS = [
    [-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
    [-1,-1, 1],[1,-1, 1],[1,1, 1],[-1,1, 1]
  ];
  var CUBE_EDGES = [
    [0,1],[1,2],[2,3],[3,0],
    [4,5],[5,6],[6,7],[7,4],
    [0,4],[1,5],[2,6],[3,7]
  ];
  var OCTA_VERTS = [
    [0,-1,0],[1,0,0],[0,0,1],[-1,0,0],[0,0,-1],[0,1,0]
  ];
  var OCTA_EDGES = [
    [0,1],[0,2],[0,3],[0,4],
    [5,1],[5,2],[5,3],[5,4],
    [1,2],[2,3],[3,4],[4,1]
  ];

  function createWireframe() {
    var c = pickNeon();
    var isOcta = Math.random() > 0.5;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      size: 30 + Math.random() * 60,
      rotX: Math.random() * Math.PI * 2,
      rotY: Math.random() * Math.PI * 2,
      rotZ: Math.random() * Math.PI * 2,
      spinX: (Math.random() - 0.5) * 0.008,
      spinY: (Math.random() - 0.5) * 0.012,
      spinZ: (Math.random() - 0.5) * 0.006,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.1,
      phase: Math.random() * Math.PI * 2,
      verts: isOcta ? OCTA_VERTS : CUBE_VERTS,
      edges: isOcta ? OCTA_EDGES : CUBE_EDGES,
      r: c[0], g: c[1], b: c[2],
    };
  }

  function initNeon() {
    rings = [];
    orbs  = [];
    wireframes = [];
    for (var i = 0; i < RING_COUNT; i++) rings.push(createRing());
    for (var i = 0; i < ORB_COUNT;  i++) orbs.push(createOrb());
    for (var i = 0; i < WIREFRAME_COUNT; i++) wireframes.push(createWireframe());
  }

  /* Project a 3D point with rotation */
  function project3D(vx, vy, vz, rx, ry, rz) {
    // Rotate around X
    var cosX = Math.cos(rx), sinX = Math.sin(rx);
    var y1 = vy * cosX - vz * sinX;
    var z1 = vy * sinX + vz * cosX;
    // Rotate around Y
    var cosY = Math.cos(ry), sinY = Math.sin(ry);
    var x2 = vx * cosY + z1 * sinY;
    var z2 = -vx * sinY + z1 * cosY;
    // Rotate around Z
    var cosZ = Math.cos(rz), sinZ = Math.sin(rz);
    var x3 = x2 * cosZ - y1 * sinZ;
    var y3 = x2 * sinZ + y1 * cosZ;
    return [x3, y3];
  }

  function drawNeon() {
    // Top-darkening gradient wash
    var gradWash = ctx.createLinearGradient(0, 0, 0, height * 0.5);
    gradWash.addColorStop(0, "rgba(40, 20, 60, 0.12)");
    gradWash.addColorStop(0.5, "rgba(30, 15, 50, 0.06)");
    gradWash.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradWash;
    ctx.fillRect(0, 0, width, height);

    // No mouse offset in light mode

    // Elliptical rings
    for (var i = 0; i < rings.length; i++) {
      var rn = rings[i];
      rn.angle += rn.drift * 0.008;
      rn.x += Math.sin(frame * 0.005 + rn.phase) * 0.3;
      rn.y += Math.cos(frame * 0.004 + rn.phase) * 0.2;

      if (rn.x < -250) rn.x = width  + 250;
      if (rn.x > width  + 250) rn.x = -250;
      if (rn.y < -250) rn.y = height + 250;
      if (rn.y > height + 250) rn.y = -250;

      var pulse = 0.5 + 0.5 * Math.sin(frame * 0.02 + rn.phase);
      var alpha = 0.10 + pulse * 0.18;

      ctx.save();
      ctx.translate(rn.x, rn.y);
      ctx.rotate(rn.angle);

      // Outer glow (wide, soft)
      ctx.strokeStyle = "rgba(" + rn.r + "," + rn.g + "," + rn.b + "," + (alpha * 0.3) + ")";
      ctx.lineWidth = 5;
      ctx.beginPath();
      ctx.ellipse(0, 0, rn.rx, rn.ry, 0, 0, Math.PI * 2);
      ctx.stroke();

      // Mid glow
      ctx.strokeStyle = "rgba(" + rn.r + "," + rn.g + "," + rn.b + "," + (alpha * 0.6) + ")";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.ellipse(0, 0, rn.rx, rn.ry, 0, 0, Math.PI * 2);
      ctx.stroke();

      // Core ring
      ctx.strokeStyle = "rgba(" + rn.r + "," + rn.g + "," + rn.b + "," + alpha + ")";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(0, 0, rn.rx, rn.ry, 0, 0, Math.PI * 2);
      ctx.stroke();

      ctx.restore();
    }

    // 3D wireframe shapes
    for (var i = 0; i < wireframes.length; i++) {
      var w = wireframes[i];
      w.rotX += w.spinX;
      w.rotY += w.spinY;
      w.rotZ += w.spinZ;
      w.x += w.vx + Math.sin(frame * 0.003 + w.phase) * 0.1;
      w.y += w.vy + Math.cos(frame * 0.003 + w.phase) * 0.08;

      if (w.x < -150) w.x = width  + 150;
      if (w.x > width  + 150) w.x = -150;
      if (w.y < -150) w.y = height + 150;
      if (w.y > height + 150) w.y = -150;

      var pulse = 0.5 + 0.5 * Math.sin(frame * 0.018 + w.phase);
      var alpha = 0.12 + pulse * 0.20;

      // Project all vertices
      var projected = [];
      for (var v = 0; v < w.verts.length; v++) {
        var pt = w.verts[v];
        var p = project3D(pt[0], pt[1], pt[2], w.rotX, w.rotY, w.rotZ);
        projected.push([w.x + p[0] * w.size, w.y + p[1] * w.size]);
      }

      // Draw edges with glow
      for (var e = 0; e < w.edges.length; e++) {
        var a = projected[w.edges[e][0]];
        var b = projected[w.edges[e][1]];

        // Outer glow
        ctx.strokeStyle = "rgba(" + w.r + "," + w.g + "," + w.b + "," + (alpha * 0.25) + ")";
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();

        // Core edge
        ctx.strokeStyle = "rgba(" + w.r + "," + w.g + "," + w.b + "," + alpha + ")";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
      }

      // Vertex dots with glow
      for (var v = 0; v < projected.length; v++) {
        var px = projected[v][0], py = projected[v][1];
        var dotR = 2 + pulse * 1.5;
        var gRad = dotR * 4;
        var grd = ctx.createRadialGradient(px, py, dotR * 0.3, px, py, gRad);
        grd.addColorStop(0, "rgba(" + w.r + "," + w.g + "," + w.b + "," + (alpha * 0.7) + ")");
        grd.addColorStop(1, "rgba(" + w.r + "," + w.g + "," + w.b + ",0)");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(px, py, gRad, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "rgba(" + w.r + "," + w.g + "," + w.b + "," + alpha + ")";
        ctx.beginPath();
        ctx.arc(px, py, dotR, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Floating orbs (varied sizes, stronger glow)
    for (var i = 0; i < orbs.length; i++) {
      var o = orbs[i];
      o.x += o.vx + Math.sin(frame * 0.01 + o.phase) * 0.15;
      o.y += o.vy + Math.cos(frame * 0.01 + o.phase) * 0.1;

      var margin = o.radius * 4;
      if (o.x < -margin) o.x = width  + margin;
      if (o.x > width  + margin) o.x = -margin;
      if (o.y < -margin) o.y = height + margin;
      if (o.y > height + margin) o.y = -margin;

      var pulse = 0.5 + 0.5 * Math.sin(frame * 0.025 + o.phase);
      var alpha = 0.12 + pulse * 0.28;
      var glowR = o.radius * (3 + pulse * 4);

      // Outer glow
      var grad = ctx.createRadialGradient(
        o.x, o.y, o.radius * 0.2,
        o.x, o.y, glowR
      );
      grad.addColorStop(0, "rgba(" + o.r + "," + o.g + "," + o.b + "," + (alpha * 0.7) + ")");
      grad.addColorStop(0.4, "rgba(" + o.r + "," + o.g + "," + o.b + "," + (alpha * 0.3) + ")");
      grad.addColorStop(1, "rgba(" + o.r + "," + o.g + "," + o.b + ",0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(o.x, o.y, glowR, 0, Math.PI * 2);
      ctx.fill();

      // Core
      ctx.fillStyle = "rgba(" + o.r + "," + o.g + "," + o.b + "," + (alpha * 1.2) + ")";
      ctx.beginPath();
      ctx.arc(o.x, o.y, o.radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /* ── Main loop ─────────────────────────────────────────── */
  function draw() {
    ctx.clearRect(0, 0, width, height);
    frame++;
    if (isDark()) {
      drawStars();
    } else {
      drawNeon();
    }
  }

  function loop() {
    if (!visible) return;
    draw();
    rafId = requestAnimationFrame(loop);
  }

  function onPointerMove(e) {
    // Only track pointer in dark mode (starfield steering)
    if (!isDark()) return;
    mouseX = e.clientX;
    mouseY = e.clientY;
  }

  /* ── Scroll-based fade ──────────────────────────────────── */
  // Instead of hard-stopping the animation when the hero scrolls away,
  // smoothly fade the canvas opacity to 0 as the hero leaves the viewport.
  var heroEl = canvas.parentElement;

  function updateScrollFade() {
    if (!heroEl) return;
    var heroRect = heroEl.getBoundingClientRect();
    var heroBottom = heroRect.bottom;
    var fadeZone = heroRect.height * 0.6;

    if (heroBottom > heroRect.height) {
      // Hero fully in view
      canvas.style.opacity = "1";
      if (!visible) { visible = true; if (!rafId) loop(); }
    } else if (heroBottom > -fadeZone) {
      // Fading zone: hero partially scrolled out
      var t = Math.max(0, heroBottom + fadeZone) / (heroRect.height + fadeZone);
      canvas.style.opacity = String(Math.max(0, t));
      if (!visible) { visible = true; if (!rafId) loop(); }
    } else {
      // Fully scrolled past — stop to save resources
      canvas.style.opacity = "0";
      visible = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    }
  }

  window.addEventListener("scroll", updateScrollFade, { passive: true });

  /* ── Initialization ────────────────────────────────────── */
  resize();
  initStars();
  initNebulae();
  initNeon();

  updateScrollFade();

  if (!reducedMotion) {
    document.addEventListener("pointermove", onPointerMove);
    mouseX = cx;
    mouseY = cy;
    loop();
  } else {
    draw();
  }

  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      resize();
      // Re-scatter elements to fill new dimensions
      initNebulae();
      initNeon();
    }, 100);
  });

  // Re-init when theme toggles so the right mode is ready
  var themeObserver = new MutationObserver(function () {
    if (reducedMotion) draw();
  });
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-bs-theme"],
  });
})();
