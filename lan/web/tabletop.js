// The tabletop in a browser: the map the DM shows, drawn on a canvas, and the player's tools.
//
// It mirrors ui/tabletop_canvas.py (the app's map): the same layers in the same order, the same tools, and
// the same commands sent to the DM ("table_cmd"). The DM's side checks every command, so nothing here
// decides what a player may do; it only offers what a player can.
(function () {
  "use strict";

  const G = window.SpellbookGeometry;
  const session = window.SpellbookSession;
  const $ = (id) => document.getElementById(id);

  const ZOOM_MIN = 0.1, ZOOM_MAX = 6;
  const FOG_SCALE_MAX = 1024;
  const LIFT_PX = 14;
  const DRAW_TOOLS = new Set(["free", "line", "rect", "ellipse"]);
  const DRAW_COLORS = ["#E74C3C", "#F1C40F", "#2ECC71", "#3498DB", "#9B59B6", "#FFFFFF", "#111111"];
  const ZONE_COLOR = "#BCAAA4";
  const EMPTY_BG = "#1E1E1E";
  const MAX_PARTS = 16;

  const canvas = $("map");
  const ctx = canvas.getContext("2d");

  const state = {
    view: null,                // the last view the DM sent: {rev, scene, role}
    scene: null,
    sceneId: "",
    zoom: 1, vx: 0, vy: 0,     // the map point at the canvas's top-left corner
    fitted: "",
    tool: "select",
    penColor: DRAW_COLORS[0],
    penWidth: 4,
    areaShape: "sphere",
    areaColor: G.AREA_COLORS[0],
    selected: null,            // one of my tokens' ids
    selectedArea: null,        // one of my areas' ids
    drag: null,
    pointers: new Map(),       // pointer id -> {x, y} (screen), for pinch-zoom
    pinch: null,
    measure: null,
    pings: [],
    pending: [],               // drawings sent but not yet in a view
    erased: new Set(),         // ids erased but not yet gone from a view
    images: new Map(),         // asset id -> ImageBitmap / HTMLImageElement
    requested: new Set(),
    parts: new Map(),
    seq: 0,
    frame: 0,
    fog: { key: "", canvas: null, scale: 1 },
  };

  // ------------------------------------------------------------------ talking to the DM
  function send(cmd) {
    if (!state.scene) return false;
    cmd = Object.assign({}, cmd, { scene: state.scene.id });
    state.seq += 1;
    const ok = session.send("table_cmd", { cmd: cmd, seq: state.seq });
    if (!ok) toast("You're not connected to the DM right now.");
    return ok;
  }
  const toast = (text, ms) => {
    const el = $("toast");
    el.textContent = text;
    el.hidden = !text;
    clearTimeout(toast.timer);
    if (text) toast.timer = setTimeout(() => { el.hidden = true; }, ms || 3500);
  };
  function status(text) {
    const el = $("status");
    el.textContent = text || "";
    el.hidden = !text;
  }

  session.on("joined", () => { /* the DM sends the map straight after the welcome */ });
  session.on("table_state", (body) => {
    const view = body.view;
    if (!view || typeof view !== "object") return;
    const scene = view.scene && typeof view.scene === "object" && Array.isArray(view.scene.tokens) ? view.scene : null;
    state.view = view;
    state.scene = scene;
    const id = scene ? scene.id : "";
    if (id !== state.sceneId) {
      state.sceneId = id;
      state.selected = state.selectedArea = null;
      state.drag = null;
      state.measure = null;
      state.pending = [];
      state.erased.clear();
      state.fitted = "";
    }
    if (scene) {
      // drawings and erasures we sent are in this view now (or were refused): stop showing our copies
      const have = new Set(scene.drawings.map((d) => d.id));
      state.pending = state.pending.filter((d) => !have.has(d.id) && Date.now() - d.sent < 4000);
      for (const eid of Array.from(state.erased)) {
        if (!have.has(eid) && !(scene.areas || []).some((a) => a.id === eid)) state.erased.delete(eid);
      }
      if (state.selected && !token(state.selected)) state.selected = null;
      if (state.selectedArea && !area(state.selectedArea)) state.selectedArea = null;
      fetchMissing(scene);
    }
    showScene();
  });
  session.on("table_asset", (body) => receivePart(body));
  session.on("table_error", (body) => {
    toast(body.message || "That couldn't be done.");
    state.pending = [];
    state.erased.clear();
    redraw();
  });
  session.on("table_ping", (body) => {
    const p = body.ping || {};
    if (!state.scene) return;
    state.pings.push({ x: +p.x || 0, y: +p.y || 0, name: String(p.name || "").slice(0, 32),
      color: /^#[0-9A-Fa-f]{6}$/.test(p.color || "") ? p.color : "#3498DB", t0: performance.now() });
    redraw();
  });

  // ------------------------------------------------------------------ pictures
  function fetchMissing(scene) {
    const ids = [];
    if (scene.map) ids.push(scene.map);
    for (const t of scene.tokens) if (t.image && ids.indexOf(t.image) < 0) ids.push(t.image);
    const missing = ids.filter((i) => /^[0-9a-f]{20}$/.test(i) && !state.images.has(i) && !state.requested.has(i));
    if (missing.length) {
      missing.forEach((i) => state.requested.add(i));
      session.send("table_asset_req", { ids: missing.slice(0, 50) });
    }
  }

  function receivePart(body) {
    const id = body.id, part = body.part, parts = body.parts;
    if (!/^[0-9a-f]{20}$/.test(id || "") || !state.requested.has(id) || state.images.has(id)) return;
    if (!Number.isInteger(part) || !Number.isInteger(parts) || parts < 1 || parts > MAX_PARTS || part < 0 || part >= parts) return;
    let bytes;
    try {
      const bin = atob(String(body.data || ""));
      bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    } catch (e) { return; }
    const got = state.parts.get(id) || new Map();
    got.set(part, bytes);
    state.parts.set(id, got);
    if (got.size < parts) return;
    state.parts.delete(id);
    const chunks = [];
    for (let i = 0; i < parts; i++) chunks.push(got.get(i));
    const png = chunks[0][0] === 0x89 && chunks[0][1] === 0x50;
    const blob = new Blob(chunks, { type: png ? "image/png" : "image/jpeg" });
    decode(blob).then((img) => {
      state.images.set(id, img);
      state.fog.key = "";
      redraw();
    }).catch(() => { state.requested.delete(id); });
  }

  function decode(blob) {
    if (window.createImageBitmap) return createImageBitmap(blob);
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = url;
    });
  }

  // ------------------------------------------------------------------ lookups
  function token(id) {
    if (!state.scene || !id) return null;
    return state.scene.tokens.find((t) => t.id === id) || null;
  }
  function area(id) {
    if (!state.scene || !id) return null;
    return (state.scene.areas || []).find((a) => a.id === id) || null;
  }
  const grid = () => G.Grid.of(state.scene);
  const canMove = (t) => !!(t && (t.mine || (state.scene && state.scene.players_move_all)));
  const toScreen = (x, y) => [(x - state.vx) * state.zoom, (y - state.vy) * state.zoom];
  const toMap = (sx, sy) => [sx / state.zoom + state.vx, sy / state.zoom + state.vy];
  function size() {
    const r = canvas.getBoundingClientRect();
    return [r.width, r.height];
  }

  function tokenAt(sx, sy) {
    if (!state.scene) return null;
    const [mx, my] = toMap(sx, sy);
    const g = grid();
    for (let i = state.scene.tokens.length - 1; i >= 0; i--) {
      const t = state.scene.tokens[i];
      const [cx, cy, r] = G.tokenBox(t, g);
      if ((mx - cx) ** 2 + (my - cy) ** 2 <= r * r) return t;
    }
    return null;
  }
  function handleAt(sx, sy, mineOnly) {
    if (!state.scene) return null;
    const areas = state.scene.areas || [];
    for (let i = areas.length - 1; i >= 0; i--) {
      const a = areas[i];
      if (mineOnly && !a.mine) continue;
      const [x, y] = toScreen(a.x, a.y);
      if (Math.hypot(sx - x, sy - y) <= 12) return a;
    }
    return null;
  }

  // ------------------------------------------------------------------ the view
  function showScene() {
    const scene = state.scene;
    const has = !!scene;
    $("waiting").hidden = has;
    $("tools").hidden = !has;
    $("zoom").hidden = !has;
    if (!has) {
      $("waiting-title").textContent = "You're in.";
      $("waiting-text").textContent = "The DM isn't showing a map right now. It opens here when they do.";
      $("scene-name").textContent = session.hostName + "'s table";
      $("selection").hidden = true;
      status("");
      redraw();
      return;
    }
    $("scene-name").textContent = scene.name || "Map";
    document.body.classList.toggle("no-drawing", !scene.players_draw);
    if (state.fitted !== scene.id) {
      const [w, h] = size();
      if (w > 60 && h > 60) {
        state.fitted = scene.id;
        fit();
      }
    }
    updateSelection();
    redraw();
  }

  function fit() {
    const scene = state.scene;
    if (!scene) return;
    const [w, h] = size();
    // keep the map clear of the tool panel: beside it on a wide screen, above it on a phone
    let left = 0, bottom = 0;
    const tools = document.getElementById("tools");
    if (tools && !tools.hidden) {
      const box = tools.getBoundingClientRect(), stage = canvas.getBoundingClientRect();
      if (w > 720) left = Math.max(0, box.right - stage.left + 6);
      else bottom = Math.max(0, stage.bottom - box.top + 6);
    }
    const fw = Math.max(80, w - left), fh = Math.max(80, h - bottom);
    state.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.min(fw / Math.max(scene.w, 1), fh / Math.max(scene.h, 1)) * 0.96));
    state.vx = scene.w / 2 - (left + fw / 2) / state.zoom;
    state.vy = scene.h / 2 - fh / 2 / state.zoom;
    redraw();
  }

  function zoomBy(factor, sx, sy) {
    const [w, h] = size();
    if (sx === undefined) { sx = w / 2; sy = h / 2; }
    const [mx, my] = toMap(sx, sy);
    state.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, state.zoom * factor));
    state.vx = mx - sx / state.zoom;
    state.vy = my - sy / state.zoom;
    redraw();
  }

  function redraw() {
    if (!state.frame) state.frame = requestAnimationFrame(render);
  }

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const [w, h] = size();
    const pw = Math.max(1, Math.round(w * dpr)), ph = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== pw || canvas.height !== ph) {
      canvas.width = pw;
      canvas.height = ph;
    }
    if (state.scene && state.fitted !== state.scene.id && w > 60 && h > 60) {
      state.fitted = state.scene.id;
      fit();
    }
    redraw();
  }

  // ------------------------------------------------------------------ drawing the map
  function render(now) {
    state.frame = 0;
    now = now || performance.now();
    const dpr = window.devicePixelRatio || 1;
    const [W, H] = size();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = EMPTY_BG;
    ctx.fillRect(0, 0, W, H);
    const scene = state.scene;
    if (!scene) return;
    const z = state.zoom;
    const [x0, y0] = toScreen(0, 0);
    ctx.fillStyle = scene.bg || "#2B2B2B";
    ctx.fillRect(x0, y0, scene.w * z, scene.h * z);
    const img = scene.map ? state.images.get(scene.map) : null;
    if (img) {
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = z < 1 ? "high" : "medium";
      ctx.drawImage(img, x0, y0, scene.w * z, scene.h * z);
    } else if (scene.map) {
      ctx.fillStyle = "#DDDDDD";
      ctx.font = "13px system-ui, sans-serif";
      ctx.fillText("Loading the map…", x0 + 10, y0 + 22);
    }
    drawGrid(scene, W, H);
    drawFog(scene, W, H);
    drawZones(scene);
    for (const d of scene.drawings) if (!state.erased.has(d.id)) drawDrawing(d);
    for (const d of state.pending) drawDrawing(d);
    const areas = (scene.areas || []).filter((a) => !state.erased.has(a.id));
    if (state.drag && state.drag.kind === "area" && state.drag.area) areas.push(state.drag.area);
    const hits = new Map();
    const labels = [];
    for (const a of areas) {
      const moved = state.drag && state.drag.kind === "area_move" && state.drag.id === a.id && state.drag.at
        ? Object.assign({}, a, { x: state.drag.at[0], y: state.drag.at[1], token: "" }) : a;
      for (const tid of drawArea(moved, labels)) if (!hits.has(tid)) hits.set(tid, a.color || G.AREA_COLORS[0]);
    }
    for (const t of scene.tokens) {
      const dragged = state.drag && state.drag.kind === "token" && state.drag.id === t.id && state.drag.moved;
      drawToken(dragged ? Object.assign({}, t, { x: state.drag.at[0], y: state.drag.at[1] }) : t, dragged);
      if (hits.has(t.id)) tintToken(t, hits.get(t.id));
    }
    ctx.font = "bold 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const [x, y, text] of labels) outlinedText(text, x, y, "#FFFFFF");
    if (state.drag && state.drag.kind === "lift") drawLift();
    drawPings(now);
    if (state.measure) drawMeasure(...state.measure);
    if (state.drag && state.drag.kind === "draw") drawPreview(state.drag);
    if (state.pings.length) redraw();
  }

  function outlinedText(text, x, y, color) {
    ctx.fillStyle = "#000000";
    ctx.fillText(text, x + 1, y + 1);
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);
  }

  function hexToRgba(hex, alpha) {
    const v = parseInt(String(hex || "#000000").slice(1), 16) || 0;
    return "rgba(" + ((v >> 16) & 255) + "," + ((v >> 8) & 255) + "," + (v & 255) + "," + alpha + ")";
  }

  function drawGrid(scene, W, H) {
    const g = scene.grid || {};
    const gr = grid();
    if (gr.kind === "none" || !(g.opacity > 0) || gr.cell * state.zoom < 6) return;
    let [mx0, my0] = toMap(0, 0);
    let [mx1, my1] = toMap(W, H);
    mx0 = Math.max(mx0, 0); my0 = Math.max(my0, 0);
    mx1 = Math.min(mx1, scene.w); my1 = Math.min(my1, scene.h);
    if (mx1 <= mx0 || my1 <= my0) return;
    ctx.save();
    const [sx0, sy0] = toScreen(0, 0);
    ctx.beginPath();
    ctx.rect(sx0, sy0, scene.w * state.zoom, scene.h * state.zoom);
    ctx.clip();
    ctx.strokeStyle = hexToRgba(g.color || "#000000", Math.max(0, Math.min(1, g.opacity)));
    ctx.lineWidth = state.zoom >= 1.5 ? 2 : 1;
    ctx.beginPath();
    for (const line of gr.linesIn(mx0, my0, mx1, my1)) {
      for (let i = 0; i < line.length; i += 2) {
        const [x, y] = toScreen(line[i], line[i + 1]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.restore();
  }

  // The fog (and, with line of sight on, the dark outside what my tokens see), kept as one picture of the
  // whole map at a reduced size: opaque where hidden.
  function fogMask(scene) {
    const ops = scene.fog.ops || [];
    const sight = scene.sight || null;
    const fogOn = !!scene.fog.on;
    const key = JSON.stringify([scene.id, scene.w, scene.h, fogOn, ops.length, ops.length ? ops[ops.length - 1] : "",
      sight ? sight.map((s) => [s.x, s.y, s.r, s.pts.length, s.pts[0], s.pts[s.pts.length - 1]]) : null]);
    if (state.fog.key === key) return state.fog;
    const scale = Math.min(1, FOG_SCALE_MAX / Math.max(scene.w, scene.h, 1));
    const w = Math.max(1, Math.round(scene.w * scale)), h = Math.max(1, Math.round(scene.h * scale));
    const c = state.fog.canvas || document.createElement("canvas");
    c.width = w;
    c.height = h;
    const f = c.getContext("2d");
    f.setTransform(1, 0, 0, 1, 0, 0);
    f.globalCompositeOperation = "source-over";
    f.clearRect(0, 0, w, h);
    f.fillStyle = "#000";
    if (fogOn) {
      f.fillRect(0, 0, w, h);
      for (const op of ops) {
        f.globalCompositeOperation = op.mode === "reveal" ? "destination-out" : "source-over";
        shapePath(f, op.shape, op.pts.map((p) => p * scale));
        f.fill();
      }
    }
    if (sight) {
      // what no token sees is dark: start dark, cut out each eye's view (inside its sight range)
      const d = document.createElement("canvas");
      d.width = w;
      d.height = h;
      const dc = d.getContext("2d");
      dc.fillStyle = "#000";
      dc.fillRect(0, 0, w, h);
      dc.globalCompositeOperation = "destination-out";
      for (const s of sight) {
        if (!s.pts || s.pts.length < 6) continue;
        dc.save();
        if (s.r) {
          dc.beginPath();
          dc.arc(s.x * scale, s.y * scale, s.r * scale, 0, Math.PI * 2);
          dc.clip();
        }
        shapePath(dc, "poly", s.pts.map((p) => p * scale));
        dc.fill();
        dc.restore();
      }
      f.globalCompositeOperation = "source-over";
      f.drawImage(d, 0, 0);
    }
    state.fog = { key: key, canvas: c, scale: scale };
    return state.fog;
  }

  function shapePath(c, shape, pts) {
    c.beginPath();
    if (shape === "rect") {
      const x0 = Math.min(pts[0], pts[2]), y0 = Math.min(pts[1], pts[3]);
      c.rect(x0, y0, Math.abs(pts[2] - pts[0]), Math.abs(pts[3] - pts[1]));
    } else if (shape === "ellipse") {
      const cx = (pts[0] + pts[2]) / 2, cy = (pts[1] + pts[3]) / 2;
      c.ellipse(cx, cy, Math.abs(pts[2] - pts[0]) / 2, Math.abs(pts[3] - pts[1]) / 2, 0, 0, Math.PI * 2);
    } else {
      for (let i = 0; i + 1 < pts.length; i += 2) {
        if (i === 0) c.moveTo(pts[i], pts[i + 1]); else c.lineTo(pts[i], pts[i + 1]);
      }
      c.closePath();
    }
  }

  function drawFog(scene, W, H) {
    if (!scene.fog.on && !scene.sight) return;
    const mask = fogMask(scene);
    const layer = drawFog.layer || (drawFog.layer = document.createElement("canvas"));
    const dpr = window.devicePixelRatio || 1;
    layer.width = Math.max(1, Math.round(W * dpr));
    layer.height = Math.max(1, Math.round(H * dpr));
    const l = layer.getContext("2d");
    l.setTransform(dpr, 0, 0, dpr, 0, 0);
    // everything is dark (outside the map too) except what the mask leaves open
    l.fillStyle = "rgb(12,12,16)";
    l.fillRect(0, 0, W, H);
    l.globalCompositeOperation = "destination-out";
    const [x0, y0] = toScreen(0, 0);
    l.fillStyle = "#000";
    l.fillRect(x0, y0, scene.w * state.zoom, scene.h * state.zoom);
    l.globalCompositeOperation = "source-over";
    l.imageSmoothingEnabled = true;
    l.drawImage(mask.canvas, x0, y0, scene.w * state.zoom, scene.h * state.zoom);
    // the mask is black where hidden: colour it like the fog
    l.globalCompositeOperation = "source-in";
    l.fillStyle = "rgb(12,12,16)";
    l.fillRect(0, 0, W, H);
    l.globalCompositeOperation = "source-over";
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(layer, 0, 0);
    ctx.restore();
  }

  function drawZones(scene) {
    ctx.save();
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 4]);
    ctx.strokeStyle = ZONE_COLOR;
    ctx.font = "bold 13px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    for (const zn of scene.zones || []) {
      const pts = [];
      for (let i = 0; i + 1 < zn.pts.length; i += 2) pts.push(...toScreen(zn.pts[i], zn.pts[i + 1]));
      if (pts.length < 6) continue;
      shapePath(ctx, "poly", pts);
      ctx.stroke();
      let top = 0;
      for (let i = 1; i < pts.length / 2; i++) {
        if (pts[2 * i + 1] < pts[2 * top + 1] || (pts[2 * i + 1] === pts[2 * top + 1] && pts[2 * i] < pts[2 * top])) top = i;
      }
      ctx.setLineDash([]);
      outlinedText("⛰ " + (G.heightText(zn.elev) || "0 ft"), pts[2 * top] + 6, pts[2 * top + 1] + 6, ZONE_COLOR);
      ctx.setLineDash([8, 4]);
    }
    ctx.restore();
  }

  function drawDrawing(d, preview) {
    const pts = [];
    for (let i = 0; i + 1 < d.pts.length; i += 2) pts.push(...toScreen(d.pts[i], d.pts[i + 1]));
    if (pts.length < 4) return;
    ctx.save();
    ctx.strokeStyle = d.color || "#E74C3C";
    ctx.lineWidth = Math.max(1, (d.width || 4) * state.zoom);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (d.private) ctx.setLineDash([6, 4]);
    ctx.beginPath();
    if (d.kind === "rect") {
      ctx.rect(Math.min(pts[0], pts[2]), Math.min(pts[1], pts[3]), Math.abs(pts[2] - pts[0]), Math.abs(pts[3] - pts[1]));
    } else if (d.kind === "ellipse") {
      ctx.ellipse((pts[0] + pts[2]) / 2, (pts[1] + pts[3]) / 2, Math.abs(pts[2] - pts[0]) / 2,
        Math.abs(pts[3] - pts[1]) / 2, 0, 0, Math.PI * 2);
    } else if (d.kind === "free" && pts.length > 4) {
      // a smooth line through the points (like the app's smoothed lines)
      ctx.moveTo(pts[0], pts[1]);
      for (let i = 2; i < pts.length - 2; i += 2) {
        ctx.quadraticCurveTo(pts[i], pts[i + 1], (pts[i] + pts[i + 2]) / 2, (pts[i + 1] + pts[i + 3]) / 2);
      }
      ctx.lineTo(pts[pts.length - 2], pts[pts.length - 1]);
    } else {
      ctx.moveTo(pts[0], pts[1]);
      for (let i = 2; i < pts.length; i += 2) ctx.lineTo(pts[i], pts[i + 1]);
    }
    if (preview) ctx.globalAlpha = 0.85;
    ctx.stroke();
    ctx.restore();
  }

  function cellOutline(cx, cy) {
    const g = grid();
    if (g.kind === "square") {
      const h = g.cell / 2;
      return [cx - h, cy - h, cx + h, cy - h, cx + h, cy + h, cx - h, cy + h];
    }
    const out = [];
    for (const p of g.hexCorners(...g.hexAt(cx, cy))) out.push(p[0], p[1]);
    return out;
  }

  function drawArea(a, labels) {
    const scene = state.scene;
    let outline, cells, touched;
    try {
      outline = G.areaFootprint(scene, a);
      cells = G.areaCells(scene, a);
      touched = G.areaTokens(scene, a);
    } catch (e) {
      return [];
    }
    const color = a.color || "#E67E22";
    ctx.save();
    ctx.fillStyle = hexToRgba(color, 90 / 255);
    ctx.beginPath();
    for (const [cx, cy] of cells) {
      const p = cellOutline(cx, cy);
      for (let i = 0; i < p.length; i += 2) {
        const [x, y] = toScreen(p[i], p[i + 1]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
    }
    ctx.fill();
    const foot = [];
    for (let i = 0; i < outline.length; i += 2) foot.push(...toScreen(outline[i], outline[i + 1]));
    shapePath(ctx, "poly", foot);
    ctx.fillStyle = hexToRgba(color, 35 / 255);
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = state.selectedArea === a.id ? 3 : 2;
    ctx.stroke();
    const [ox, oy] = toScreen(a.x, a.y);
    ctx.beginPath();
    ctx.arc(ox, oy, 5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#FFFFFF";
    ctx.stroke();
    ctx.restore();
    let lift = 14;
    const t = token(a.token);
    if (t) lift = G.tokenBox(t, grid())[2] * state.zoom + 14;
    labels.push([ox, oy - lift, G.areaText(a, scene)]);
    return touched;
  }

  function tintToken(t, color) {
    const [cx, cy, r] = G.tokenBox(t, grid());
    const [sx, sy] = toScreen(cx, cy);
    ctx.beginPath();
    ctx.arc(sx, sy, Math.max(3, r * state.zoom * 0.92), 0, Math.PI * 2);
    ctx.fillStyle = hexToRgba(color, 120 / 255);
    ctx.fill();
  }

  function drawToken(t, ghost) {
    const g = grid();
    const [cx, cy, r] = G.tokenBox(t, g);
    const [sx, sy] = toScreen(cx, cy);
    const sr = Math.max(5, r * state.zoom * 0.92);
    ctx.save();
    if (ghost) ctx.globalAlpha = 0.8;
    if (t.turn) {
      const halo = sr + Math.max(10, sr * 0.45);
      ctx.beginPath();
      ctx.arc(sx, sy, halo, 0, Math.PI * 2);
      ctx.strokeStyle = "#FFD54F";
      ctx.lineWidth = Math.max(3, sr * 0.12);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.fillStyle = t.color || "#C0392B";
    ctx.fill();
    const img = t.image ? state.images.get(t.image) : null;
    if (img) {
      ctx.save();
      ctx.clip();
      const side = Math.min(img.width, img.height);
      ctx.drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, sx - sr, sy - sr, sr * 2, sr * 2);
      ctx.restore();
    } else if (sr >= 6) {
      ctx.font = "bold " + Math.max(8, Math.round(sr * 1.1)) + "px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      outlinedText(G.tokenLetter(t.name), sx, sy + 1, "#FFFFFF");
    }
    const selected = t.id === state.selected;
    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.strokeStyle = selected ? "#F1C40F" : (t.color || "#111111");
    ctx.lineWidth = selected ? 3 : 2;
    ctx.stroke();
    // the condition ring
    const conditions = (t.conditions || []).slice();
    const hp = t.hp, hpMax = t.hp_max;
    if (t.state === "bloodied" && conditions.indexOf("Bloodied") < 0) conditions.push("Bloodied");
    if (hp !== null && hp !== undefined && hpMax && hp * 2 <= hpMax && hp > 0 && conditions.indexOf("Bloodied") < 0) {
      conditions.push("Bloodied");
    }
    const ringW = Math.max(3, sr * 0.16);
    if (conditions.length) {
      const ring = sr + Math.max(3, sr * 0.14);
      const span = 360 / conditions.length;
      ctx.lineWidth = ringW;
      conditions.forEach((name, i) => {
        // (Tk's arcs start at 3 o'clock and go anticlockwise; a canvas's go clockwise)
        const start = 90 - (i + 1) * span + 2;
        const extent = conditions.length > 1 ? Math.max(1, span - 4) : 359.9;
        ctx.beginPath();
        ctx.arc(sx, sy, ring, G.radians(-(start + extent)), G.radians(-start));
        ctx.strokeStyle = G.conditionColor(name);
        ctx.stroke();
      });
    }
    if (t.state === "down" || (hp !== null && hp !== undefined && hpMax && hp <= 0)) {
      const k = sr * 0.6;
      ctx.strokeStyle = "#E74C3C";
      ctx.lineWidth = Math.max(2, sr * 0.15);
      ctx.beginPath();
      ctx.moveTo(sx - k, sy - k); ctx.lineTo(sx + k, sy + k);
      ctx.moveTo(sx - k, sy + k); ctx.lineTo(sx + k, sy - k);
      ctx.stroke();
    }
    const hasHp = hp !== null && hp !== undefined && hpMax;
    if (hasHp && sr >= 10) {
      const frac = Math.max(0, Math.min(1, hp / hpMax));
      const bw = sr * 1.6, bh = Math.max(3, sr * 0.14);
      const bx = sx - bw / 2, by = sy + sr + (conditions.length ? Math.max(3, sr * 0.14) * 2 : 3);
      ctx.fillStyle = "#222222";
      ctx.fillRect(bx, by, bw, bh);
      ctx.fillStyle = frac > 0.5 ? "#27AE60" : (frac > 0.25 ? "#F39C12" : "#E74C3C");
      ctx.fillRect(bx, by, bw * frac, bh);
    }
    let ny = sy + sr + (hasHp ? 14 : 8) + (conditions.length ? Math.max(3, sr * 0.14) : 0);
    ctx.font = "bold 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    if (t.show_name !== false && sr >= 8) {
      outlinedText(t.name, sx, ny, "#FFFFFF");
      ny += 14;
    }
    const height = G.heightText(G.tokenElevation(state.scene, t));
    if (height) outlinedText(height, sx, ny, "#9AD0F5");
    ctx.restore();
  }

  function drawLift() {
    const d = state.drag;
    const t = token(d.id);
    if (!t) return;
    const [sx, sy] = toScreen(t.x, t.y);
    const total = G.groundAt(state.scene, t.x, t.y) + d.z;
    ctx.font = "bold 14px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    outlinedText(G.heightText(total) || "on the ground", sx, sy - G.tokenBox(t, grid())[2] * state.zoom - 16, "#9AD0F5");
  }

  function drawPings(now) {
    state.pings = state.pings.filter((p) => now - p.t0 < 2200);
    for (const p of state.pings) {
      const age = (now - p.t0) / 1000;
      const [sx, sy] = toScreen(p.x, p.y);
      for (let k = 0; k < 2; k++) {
        const phase = (age * 1.4 + k * 0.5) % 1;
        const r = 8 + phase * 46;
        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.strokeStyle = p.color;
        ctx.lineWidth = Math.max(1, Math.floor(4 * (1 - phase))) + 1;
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(sx, sy, 5, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1;
      ctx.stroke();
      if (p.name) {
        ctx.font = "bold 13px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        outlinedText(p.name, sx, sy - 22, "#FFFFFF");
      }
    }
  }

  function heightAt(x, y) {
    const [sx, sy] = toScreen(x, y);
    const t = tokenAt(sx, sy);
    return t ? G.tokenElevation(state.scene, t) : G.groundAt(state.scene, x, y);
  }

  function measureText(x0, y0, x1, y1) {
    const scene = state.scene;
    const g = grid();
    const feet = G.distanceFt(scene, [x0, y0, heightAt(x0, y0)], [x1, y1, heightAt(x1, y1)]);
    const cells = feet / Number((scene.grid || {}).feet || 5);
    let text = (g.kind !== "none" ? G.fmt(feet) : String(Math.round(feet))) + " ft";
    if (g.kind === "square") text += "  (" + G.fmt(cells) + " squares)";
    else if (g.kind !== "none") text += "  (" + G.fmt(cells) + " hexes)";
    return text;
  }

  function drawMeasure(x0, y0, x1, y1) {
    const [ax, ay] = toScreen(x0, y0), [bx, by] = toScreen(x1, y1);
    ctx.save();
    ctx.strokeStyle = "#F1C40F";
    ctx.fillStyle = "#F1C40F";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
    const ang = Math.atan2(by - ay, bx - ax);
    ctx.beginPath();
    ctx.moveTo(bx, by);
    ctx.lineTo(bx - 12 * Math.cos(ang - 0.4), by - 12 * Math.sin(ang - 0.4));
    ctx.lineTo(bx - 12 * Math.cos(ang + 0.4), by - 12 * Math.sin(ang + 0.4));
    ctx.closePath();
    ctx.fill();
    const text = measureText(x0, y0, x1, y1);
    ctx.font = "bold 13px system-ui, sans-serif";
    const w = ctx.measureText(text).width + 20;
    const mx = (ax + bx) / 2, my = (ay + by) / 2 - 18;
    ctx.fillStyle = "#1C1C1C";
    ctx.fillRect(mx - w / 2, my - 12, w, 24);
    ctx.strokeStyle = "#F1C40F";
    ctx.lineWidth = 1;
    ctx.strokeRect(mx - w / 2, my - 12, w, 24);
    ctx.fillStyle = "#FFFFFF";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, mx, my);
    ctx.restore();
  }

  function drawPreview(d) {
    if (d.pts.length < 4) return;
    drawDrawing({ kind: state.tool, pts: d.pts, color: state.penColor, width: state.penWidth }, true);
  }

  // ------------------------------------------------------------------ erasing: what is under a point
  function distToSeg(px, py, x0, y0, x1, y1) {
    const dx = x1 - x0, dy = y1 - y0;
    const len = dx * dx + dy * dy;
    const u = len === 0 ? 0 : Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / len));
    return Math.hypot(x0 + u * dx - px, y0 + u * dy - py);
  }
  function drawingHit(d, mx, my, reach) {
    const p = d.pts;
    let segs = [];
    if (d.kind === "rect") {
      const x0 = Math.min(p[0], p[2]), y0 = Math.min(p[1], p[3]), x1 = Math.max(p[0], p[2]), y1 = Math.max(p[1], p[3]);
      segs = [x0, y0, x1, y0, x1, y1, x0, y1, x0, y0];
    } else if (d.kind === "ellipse") {
      const cx = (p[0] + p[2]) / 2, cy = (p[1] + p[3]) / 2, rx = Math.abs(p[2] - p[0]) / 2, ry = Math.abs(p[3] - p[1]) / 2;
      for (let i = 0; i <= 32; i++) segs.push(cx + rx * Math.cos(i * Math.PI / 16), cy + ry * Math.sin(i * Math.PI / 16));
    } else {
      segs = p;
    }
    const tol = reach + (d.width || 4) / 2;
    for (let i = 0; i + 3 < segs.length; i += 2) {
      if (distToSeg(mx, my, segs[i], segs[i + 1], segs[i + 2], segs[i + 3]) <= tol) return true;
    }
    return false;
  }
  function eraseAt(sx, sy) {
    const scene = state.scene;
    const [mx, my] = toMap(sx, sy);
    const reach = 8 / state.zoom;
    for (let i = scene.drawings.length - 1; i >= 0; i--) {
      const d = scene.drawings[i];
      if (state.erased.has(d.id) || !d.mine) continue;
      if (drawingHit(d, mx, my, reach)) {
        state.erased.add(d.id);
        send({ op: "draw_delete", id: d.id });
        redraw();
        return;
      }
    }
    const areas = scene.areas || [];
    for (let i = areas.length - 1; i >= 0; i--) {
      const a = areas[i];
      if (!a.mine || state.erased.has(a.id)) continue;
      const foot = G.areaFootprint(scene, a);
      const [hx, hy] = toScreen(a.x, a.y);
      if (G.pointInPolygon(mx, my, foot) || Math.hypot(sx - hx, sy - hy) <= 10) {
        state.erased.add(a.id);
        if (state.selectedArea === a.id) state.selectedArea = null;
        send({ op: "area_delete", id: a.id });
        updateSelection();
        redraw();
        return;
      }
    }
  }

  // ------------------------------------------------------------------ the mouse, a pen, or fingers
  function point(ev) {
    const r = canvas.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top];
  }

  canvas.addEventListener("contextmenu", (ev) => ev.preventDefault());
  canvas.addEventListener("pointerdown", (ev) => {
    if (!state.scene) return;
    canvas.focus({ preventScroll: true });
    const [sx, sy] = point(ev);
    state.pointers.set(ev.pointerId, { x: sx, y: sy });
    try { canvas.setPointerCapture(ev.pointerId); } catch (e) { /* not all pointers */ }
    if (state.pointers.size === 2) {
      // a second finger: pinch to zoom and pan (whatever was being drawn is dropped)
      startPinch();
      return;
    }
    if (state.pointers.size > 2) return;
    if (ev.button === 1 || ev.button === 2) {
      if (ev.button === 2) {
        const a = handleAt(sx, sy, true) || areaUnder(sx, sy);
        if (a) { selectArea(a.id); return; }
      }
      state.drag = { kind: "pan", sx: sx, sy: sy };
      return;
    }
    press(ev, sx, sy);
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (!state.scene) return;
    const [sx, sy] = point(ev);
    if (state.pointers.has(ev.pointerId)) state.pointers.set(ev.pointerId, { x: sx, y: sy });
    if (state.pinch) { movePinch(); return; }
    if (!state.drag) { hover(sx, sy); return; }
    motion(ev, sx, sy);
  });
  const up = (ev) => {
    state.pointers.delete(ev.pointerId);
    if (state.pinch) {
      if (state.pointers.size < 2) state.pinch = null;
      return;
    }
    if (!state.scene) return;
    const [sx, sy] = point(ev);
    release(ev, sx, sy);
  };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", (ev) => {
    state.pointers.delete(ev.pointerId);
    state.pinch = null;
    state.drag = null;
    state.measure = null;
    status("");
    redraw();
  });
  canvas.addEventListener("wheel", (ev) => {
    if (!state.scene) return;
    ev.preventDefault();
    const [sx, sy] = point(ev);
    const factor = Math.pow(1.15, -Math.sign(ev.deltaY) * Math.min(3, Math.abs(ev.deltaY) / 60 || 1));
    zoomBy(ev.ctrlKey ? Math.pow(factor, 0.6) : factor, sx, sy);
  }, { passive: false });

  function startPinch() {
    const [a, b] = Array.from(state.pointers.values());
    state.drag = null;
    state.measure = null;
    status("");
    const mid = [(a.x + b.x) / 2, (a.y + b.y) / 2];
    state.pinch = { dist: Math.max(10, Math.hypot(a.x - b.x, a.y - b.y)), zoom: state.zoom, anchor: toMap(...mid) };
    redraw();
  }
  function movePinch() {
    const pts = Array.from(state.pointers.values());
    if (pts.length < 2) return;
    const [a, b] = pts;
    const p = state.pinch;
    const mid = [(a.x + b.x) / 2, (a.y + b.y) / 2];
    state.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, p.zoom * Math.hypot(a.x - b.x, a.y - b.y) / p.dist));
    state.vx = p.anchor[0] - mid[0] / state.zoom;
    state.vy = p.anchor[1] - mid[1] / state.zoom;
    redraw();
  }

  function altHeld(ev) { return ev.altKey; }

  function press(ev, sx, sy) {
    const [mx, my] = toMap(sx, sy);
    if (altHeld(ev)) {
      send({ op: "ping", x: mx, y: my });
      return;
    }
    const tool = state.tool;
    if (tool === "ping") {
      send({ op: "ping", x: mx, y: my });
      return;
    }
    if (tool === "select") {
      const t = tokenAt(sx, sy);
      if (t) {
        select(t.id);
        if (canMove(t)) {
          if (ev.shiftKey) {
            state.drag = { kind: "lift", id: t.id, sy0: sy, z0: Number(t.z || 0), z: Number(t.z || 0) };
            return;
          }
          state.drag = { kind: "token", id: t.id, sx: sx, sy: sy, moved: false, at: [t.x, t.y],
            off: [t.x - mx, t.y - my], oz: G.tokenElevation(state.scene, t) };
        }
        return;
      }
      const a = handleAt(sx, sy, true);
      if (a) {
        selectArea(a.id);
        state.drag = { kind: "area_move", id: a.id, sx: sx, sy: sy, moved: false, at: null };
        return;
      }
      if (state.selected || state.selectedArea) { select(null); }
      state.drag = { kind: "pan", sx: sx, sy: sy };
      return;
    }
    if (tool === "area") {
      const [x, y, tid] = areaOrigin(sx, sy);
      state.drag = { kind: "area", x: x, y: y, token: tid, area: null, sx: sx, sy: sy };
      return;
    }
    if (tool === "measure") {
      state.drag = { kind: "measure", x0: mx, y0: my };
      state.measure = [mx, my, mx, my];
      redraw();
      return;
    }
    if (tool === "erase") {
      eraseAt(sx, sy);
      state.drag = { kind: "erase" };
      return;
    }
    if (DRAW_TOOLS.has(tool)) {
      if (!state.scene.players_draw) {
        toast("The DM has turned drawing off on this map.");
        return;
      }
      state.drag = { kind: "draw", pts: [mx, my], last: [sx, sy], start: [mx, my] };
    }
  }

  function motion(ev, sx, sy) {
    const d = state.drag;
    const [mx, my] = toMap(sx, sy);
    if (d.kind === "pan") {
      state.vx -= (sx - d.sx) / state.zoom;
      state.vy -= (sy - d.sy) / state.zoom;
      d.sx = sx; d.sy = sy;
      redraw();
    } else if (d.kind === "token") {
      if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) > 3) d.moved = true;
      if (!d.moved) return;
      d.at = [mx + d.off[0], my + d.off[1]];
      const t = token(d.id);
      if (t) {
        const zNow = G.groundAt(state.scene, d.at[0], d.at[1]) + Number(t.z || 0);
        const feet = G.distanceFt(state.scene, [t.x, t.y, d.oz], [d.at[0], d.at[1], zNow]);
        status("Moving " + t.name + ": " + G.fmt(feet) + " ft");
      }
      redraw();
    } else if (d.kind === "lift") {
      const t = token(d.id);
      if (t) {
        const step = Number((state.scene.grid || {}).feet || 5);
        d.z = d.z0 + G.pyRound((d.sy0 - sy) / LIFT_PX) * step;
        const text = G.heightText(G.groundAt(state.scene, t.x, t.y) + d.z) || "on the ground";
        status(t.name + ": " + text + "  (let go to set it)");
      }
      redraw();
    } else if (d.kind === "area") {
      if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) < 4) return;
      d.area = areaFromDrag(d, mx, my);
      const n = G.areaTokens(state.scene, d.area).length;
      status(G.areaText(d.area, state.scene) + ": " + n + " creature" + (n === 1 ? "" : "s") + " inside");
      redraw();
    } else if (d.kind === "area_move") {
      if (Math.abs(sx - d.sx) + Math.abs(sy - d.sy) > 3) d.moved = true;
      if (d.moved) { d.at = [mx, my]; redraw(); }
    } else if (d.kind === "measure") {
      state.measure = [d.x0, d.y0, mx, my];
      redraw();
    } else if (d.kind === "erase") {
      eraseAt(sx, sy);
    } else if (d.kind === "draw") {
      const tool = state.tool;
      if (tool === "free") {
        if ((sx - d.last[0]) ** 2 + (sy - d.last[1]) ** 2 < 9 || d.pts.length >= 1200) return;
        d.pts.push(mx, my);
        d.last = [sx, sy];
      } else if (tool === "line") {
        d.pts = [d.start[0], d.start[1], ...G.axisSnap(d.start[0], d.start[1], mx, my)];
      } else {
        d.pts = G.shapeBox(d.start[0], d.start[1], mx, my, ev.shiftKey, ev.ctrlKey || ev.metaKey);
      }
      redraw();
    }
  }

  function release(ev, sx, sy) {
    const d = state.drag;
    state.drag = null;
    if (!d) return;
    if (d.kind === "token") {
      const t = token(d.id);
      status("");
      if (t && d.moved) {
        const [nx, ny] = grid().snap(d.at[0], d.at[1], t.size === undefined ? 1 : t.size);
        // move it at once; the DM's answer confirms it (or puts it back)
        t.x = nx; t.y = ny;
        send({ op: "token_move", id: t.id, x: nx, y: ny });
      }
      redraw();
    } else if (d.kind === "lift") {
      status("");
      const t = token(d.id);
      if (t && d.z !== d.z0) {
        t.z = d.z;
        send({ op: "token_move", id: t.id, x: t.x, y: t.y, z: d.z });
      }
      redraw();
    } else if (d.kind === "area") {
      status("");
      if (d.area) {
        const a = Object.assign({}, d.area);
        for (const k of ["id", "base", "author", "ox", "oy"]) delete a[k];
        send({ op: "area_add", area: a });
      }
      redraw();
    } else if (d.kind === "area_move") {
      const a = area(d.id);
      if (a && d.moved && d.at) {
        a.x = G.pyRound(d.at[0], 1); a.y = G.pyRound(d.at[1], 1);
        send({ op: "area_update", id: a.id, fields: { x: a.x, y: a.y } });
      }
      redraw();
    } else if (d.kind === "measure") {
      state.measure = null;
      redraw();
    } else if (d.kind === "draw") {
      const pts = d.pts;
      if (pts.length >= 4 && (Math.abs(pts[pts.length - 2] - pts[0]) + Math.abs(pts[pts.length - 1] - pts[1]) > 1 || pts.length > 4)) {
        const drawing = { id: newId(), kind: state.tool, pts: pts.map((p) => G.pyRound(p, 1)),
          color: state.penColor, width: state.penWidth };
        if (send({ op: "draw_add", drawing: drawing })) state.pending.push(Object.assign({ sent: Date.now() }, drawing));
      }
      redraw();
    } else if (d.kind === "pan") {
      redraw();
    }
  }

  function hover(sx, sy) {
    if (state.tool !== "select") {
      canvas.style.cursor = state.tool === "ping" ? "pointer" : "crosshair";
      return;
    }
    const t = tokenAt(sx, sy);
    canvas.style.cursor = (t && canMove(t)) || handleAt(sx, sy, true) ? "grab" : "default";
  }

  function newId() {
    const b = new Uint8Array(5);
    crypto.getRandomValues(b);
    return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  }

  function areaUnder(sx, sy) {
    const [mx, my] = toMap(sx, sy);
    const areas = (state.scene.areas || []).filter((a) => a.mine);
    for (let i = areas.length - 1; i >= 0; i--) {
      if (G.pointInPolygon(mx, my, G.areaFootprint(state.scene, areas[i]))) return areas[i];
    }
    return null;
  }

  function areaOrigin(sx, sy) {
    const t = tokenAt(sx, sy);
    if (t) return [t.x, t.y, t.id];
    const [mx, my] = toMap(sx, sy);
    const g = grid();
    if (g.kind === "square") {
      const step = state.areaShape === "cube" || state.areaShape === "square" ? g.cell : g.cell / 2;
      return [g.ox + G.pyRound((mx - g.ox) / step) * step, g.oy + G.pyRound((my - g.oy) / step) * step, ""];
    }
    return [mx, my, ""];
  }

  function areaFromDrag(d, mx, my) {
    const scene = state.scene;
    const feet = Number((scene.grid || {}).feet || 5);
    const fpp = G.feetPerPx(scene);
    const dx = mx - d.x, dy = my - d.y;
    const shape = state.areaShape;
    let reach = (shape === "cube" || shape === "square") ? Math.max(Math.abs(dx), Math.abs(dy)) * fpp : Math.hypot(dx, dy) * fpp;
    if (shape === "emanation" && d.token) {
      const t = token(d.token);
      if (t) reach -= Math.max(0.5, t.size === undefined ? 1 : t.size) * feet / 2;
    }
    let a = { shape: shape, x: d.x, y: d.y, dir: (dx || dy) ? G.degrees(Math.atan2(dy, dx)) : 0,
      color: state.areaColor, token: d.token || "", pitch: 0 };
    a.size = Math.max(feet, G.pyRound(reach / feet) * feet);
    a = G.cleanArea(a) || a;
    a.id = "preview";
    const t = token(a.token);
    if (t) a.base = G.tokenElevation(scene, t);
    return a;
  }

  // ------------------------------------------------------------------ selection and its buttons
  function select(id) {
    state.selected = id;
    state.selectedArea = null;
    updateSelection();
    redraw();
  }
  function selectArea(id) {
    state.selectedArea = id;
    updateSelection();
    redraw();
  }

  function button(label, title, fn) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (title) b.title = title;
    b.addEventListener("click", fn);
    return b;
  }

  function updateSelection() {
    const box = $("selection"), actions = $("sel-actions");
    actions.textContent = "";
    const t = token(state.selected);
    const a = area(state.selectedArea);
    if (a && a.mine) {
      $("sel-title").textContent = G.areaText(a, state.scene);
      const upd = (fields) => send({ op: "area_update", id: a.id, fields: fields });
      if (a.shape === "cone" || a.shape === "line") {
        actions.appendChild(button("Tilt ↑", "Tilt up 15°", () => upd({ pitch: Math.min(90, (a.pitch || 0) + 15) })));
        actions.appendChild(button("Tilt ↓", "Tilt down 15°", () => upd({ pitch: Math.max(-90, (a.pitch || 0) - 15) })));
        if (a.pitch) actions.appendChild(button("Level", "", () => upd({ pitch: 0 })));
      }
      if (a.shape === "line") {
        actions.appendChild(button("Wider", "+5 ft", () => upd({ width: (a.width || 5) + 5 })));
        if ((a.width || 5) > 5) actions.appendChild(button("Narrower", "−5 ft", () => upd({ width: a.width - 5 })));
      }
      actions.appendChild(button("Raise", "Raise 5 ft", () => upd({ dz: (a.dz || 0) + 5 })));
      actions.appendChild(button("Lower", "Lower 5 ft", () => upd({ dz: (a.dz || 0) - 5 })));
      actions.appendChild(button("Bigger", "+5 ft", () => upd({ size: a.size + 5 })));
      if (a.size > 5) actions.appendChild(button("Smaller", "−5 ft", () => upd({ size: a.size - 5 })));
      const following = token(a.token);
      if (following) actions.appendChild(button("Stop following", "Stop moving with " + following.name, () => upd({ token: "" })));
      const mine = state.scene.tokens.filter((x) => x.mine);
      if (!following && mine.length) {
        actions.appendChild(button("Follow " + mine[0].name, "Move with " + mine[0].name, () => upd({ token: mine[0].id })));
      }
      const del = button("Delete", "", () => {
        state.erased.add(a.id);
        state.selectedArea = null;
        send({ op: "area_delete", id: a.id });
        updateSelection();
        redraw();
      });
      del.className = "danger";
      actions.appendChild(del);
      actions.appendChild(button("✕", "Close", () => selectArea(null)));
      box.hidden = false;
      return;
    }
    if (t && canMove(t)) {
      const elev = G.tokenElevation(state.scene, t);
      $("sel-title").textContent = t.name + (G.heightText(elev) ? "  " + G.heightText(elev) : "");
      const step = Number((state.scene.grid || {}).feet || 5);
      const lift = (dz) => {
        const zNew = Math.max(-G.MAX_HEIGHT, Math.min(G.MAX_HEIGHT, Number(t.z || 0) + dz));
        t.z = zNew;
        send({ op: "token_move", id: t.id, x: t.x, y: t.y, z: zNew });
        updateSelection();
        redraw();
      };
      actions.appendChild(button("▲ Up " + G.fmt(step) + " ft", "Fly up (or Shift-drag the token)", () => lift(step)));
      actions.appendChild(button("▼ Down " + G.fmt(step) + " ft", "Go down", () => lift(-step)));
      if (Number(t.z || 0)) actions.appendChild(button("Land", "Back on the ground", () => lift(-Number(t.z || 0))));
      actions.appendChild(button("✕", "Close", () => select(null)));
      box.hidden = false;
      return;
    }
    box.hidden = true;
  }

  // ------------------------------------------------------------------ the tool bar
  function setTool(tool) {
    state.tool = tool;
    state.drag = null;
    state.measure = null;
    status("");
    for (const b of document.querySelectorAll(".tool")) {
      const on = b.dataset.tool === tool;
      b.classList.toggle("on", on);
      b.setAttribute("aria-checked", on ? "true" : "false");
    }
    $("pen").hidden = !DRAW_TOOLS.has(tool);
    $("area-options").hidden = tool !== "area";
    canvas.style.cursor = tool === "select" ? "default" : "crosshair";
    redraw();
  }

  for (const b of document.querySelectorAll(".tool")) {
    b.type = "button";
    b.setAttribute("role", "radio");
    b.addEventListener("click", () => setTool(b.dataset.tool));
  }
  function swatches(holder, colors, current, onPick) {
    holder.textContent = "";
    for (const c of colors) {
      const s = document.createElement("button");
      s.type = "button";
      s.className = "swatch" + (c === current ? " on" : "");
      s.style.background = c;
      s.title = c;
      s.setAttribute("aria-label", "Colour " + c);
      s.addEventListener("click", () => {
        onPick(c);
        for (const x of holder.children) x.classList.toggle("on", x === s);
      });
      holder.appendChild(s);
    }
  }
  swatches($("pen-colors"), DRAW_COLORS, state.penColor, (c) => { state.penColor = c; });
  swatches($("area-colors"), G.AREA_COLORS, state.areaColor, (c) => { state.areaColor = c; });
  $("pen-width").addEventListener("input", (ev) => { state.penWidth = Number(ev.target.value) || 4; });
  const shapeSelect = $("area-shape");
  for (const s of G.AREA_SHAPES) {
    const o = document.createElement("option");
    o.value = s;
    o.textContent = G.AREA_LABELS[s];
    shapeSelect.appendChild(o);
  }
  shapeSelect.value = state.areaShape;
  shapeSelect.addEventListener("change", () => { state.areaShape = shapeSelect.value; });
  for (const b of document.querySelectorAll("[data-zoom]")) {
    b.addEventListener("click", () => {
      if (b.dataset.zoom === "in") zoomBy(1.25);
      else if (b.dataset.zoom === "out") zoomBy(0.8);
      else fit();
    });
  }
  canvas.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      state.drag = null;
      state.measure = null;
      status("");
      select(null);
    } else if ((ev.key === "Delete" || ev.key === "Backspace") && state.selectedArea) {
      const a = area(state.selectedArea);
      if (a && a.mine) {
        state.erased.add(a.id);
        send({ op: "area_delete", id: a.id });
        selectArea(null);
      }
    } else if (ev.key === "+" || ev.key === "=") {
      zoomBy(1.25);
    } else if (ev.key === "-") {
      zoomBy(0.8);
    }
  });

  if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);
  window.addEventListener("resize", resize);
  setTool("select");

  // for tests and the browser console
  window.SpellbookTable = { state: state, toMap: toMap, toScreen: toScreen, setTool: setTool, fit: fit, redraw: redraw };
})();
