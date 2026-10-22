// The tabletop's geometry for the browser page: grids, distances, heights and spell areas.
//
// This is a line-by-line port of the functions of the same names in tabletop.py, so a browser player's
// ruler and area previews agree with the app. tests/test_lan_web_table.py runs both on the same cases and
// compares them. Python's round() rounds halves to even and its % never goes negative, so pyRound and
// mod stand in for Math.round and %.
(function (root) {
  "use strict";

  const SQRT3 = Math.sqrt(3);
  const AREA_SHAPES = ["cube", "square", "circle", "sphere", "cone", "line", "emanation"];
  const AREA_LABELS = { cube: "Cube", square: "Square", circle: "Circle", sphere: "Sphere", cone: "Cone",
    line: "Line", emanation: "Emanation" };
  const AREA_COLORS = ["#E67E22", "#E74C3C", "#3498DB", "#2ECC71", "#9B59B6", "#F1C40F"];
  const MAX_HEIGHT = 10000;
  const CONDITION_COLORS = {
    Blinded: "#5D6D7E", Charmed: "#E91E63", Deafened: "#95A5A6", Exhaustion: "#6E2C00",
    Frightened: "#8E44AD", Grappled: "#D35400", Incapacitated: "#7F8C8D", Invisible: "#AED6F1",
    Paralyzed: "#F1C40F", Petrified: "#A6ACAF", Poisoned: "#27AE60", Prone: "#A04000",
    Restrained: "#B9770E", Stunned: "#F4D03F", Unconscious: "#17202A", Concentrating: "#3498DB",
    Dodging: "#48C9B0", Hasted: "#F39C12", Blessed: "#F7DC6F", Hexed: "#4A235A", Marked: "#E74C3C",
    Raging: "#922B21", Dead: "#000000", Bloodied: "#C0392B",
  };

  function pyRound(x, digits) {
    if (digits) {
      const k = Math.pow(10, digits);
      return pyRound(x * k) / k;
    }
    const f = Math.floor(x);
    const diff = x - f;
    if (diff > 0.5) return f + 1;
    if (diff < 0.5) return f;
    return f % 2 === 0 ? f : f + 1;
  }
  function mod(a, n) { return ((a % n) + n) % n; }
  function radians(d) { return d * Math.PI / 180; }
  function degrees(r) { return r * 180 / Math.PI; }
  function num(v, fallback, lo, hi) {
    let x = typeof v === "number" ? v : parseFloat(v);
    if (!isFinite(x)) x = fallback === undefined ? 0 : fallback;
    if (lo !== undefined) x = Math.max(lo, x);
    if (hi !== undefined) x = Math.min(hi, x);
    return x;
  }

  // ------------------------------------------------------------------ grids
  class Grid {
    constructor(kind, cell, ox, oy) {
      this.kind = ["square", "hex_rows", "hex_cols", "none"].indexOf(kind) >= 0 ? kind : "square";
      this.cell = Math.max(8, Number(cell === undefined ? 70 : cell));
      this.ox = Number(ox || 0);
      this.oy = Number(oy || 0);
    }
    static of(scene) {
      const g = (scene && scene.grid) || {};
      return new Grid(g.type || "square", g.cell === undefined ? 70 : g.cell, g.ox || 0, g.oy || 0);
    }
    _swap(x, y) { return this.kind === "hex_cols" ? [y, x] : [x, y]; }
    hexCenter(q, r) {
      const s = this.cell;
      const [ox, oy] = this._swap(this.ox, this.oy);
      return this._swap(ox + s * (q + r / 2), oy + r * s * SQRT3 / 2);
    }
    hexAt(x, y) {
      [x, y] = this._swap(x, y);
      const [ox, oy] = this._swap(this.ox, this.oy);
      const s = this.cell;
      const r = (y - oy) / (s * SQRT3 / 2);
      const q = (x - ox) / s - r / 2;
      const cx = q, cz = r, cy = -cx - cz;
      let rx = pyRound(cx), ry = pyRound(cy), rz = pyRound(cz);
      const dx = Math.abs(rx - cx), dy = Math.abs(ry - cy), dz = Math.abs(rz - cz);
      if (dx > dy && dx > dz) rx = -ry - rz;
      else if (dy > dz) ry = -rx - rz;
      else rz = -rx - ry;
      return [rx, rz];
    }
    hexCorners(q, r) {
      const [cx, cy] = this._swap(...this.hexCenter(q, r));
      const radius = this.cell / SQRT3;
      const pts = [];
      for (let i = 0; i < 6; i++) {
        const a = radians(60 * i - 30);
        pts.push(this._swap(cx + radius * Math.cos(a), cy + radius * Math.sin(a)));
      }
      return pts;
    }
    snap(x, y, size) {
      size = size === undefined ? 1 : size;
      if (this.kind === "none") return [x, y];
      if (this.kind === "square") {
        const s = this.cell;
        if (size < 1) {
          const step = s / 2;
          return [this.ox + (Math.floor((x - this.ox) / step) + 0.5) * step,
            this.oy + (Math.floor((y - this.oy) / step) + 0.5) * step];
        }
        const span = Math.max(1, pyRound(size));
        const left = pyRound((x - this.ox) / s - span / 2);
        const top = pyRound((y - this.oy) / s - span / 2);
        return [this.ox + (left + span / 2) * s, this.oy + (top + span / 2) * s];
      }
      return this.hexCenter(...this.hexAt(x, y));
    }
    cellsBetween(a, b) {
      if (this.kind === "square") {
        return Math.max(pyRound(Math.abs(b[0] - a[0]) / this.cell), pyRound(Math.abs(b[1] - a[1]) / this.cell));
      }
      if (this.kind === "hex_rows" || this.kind === "hex_cols") {
        const [q1, r1] = this.hexAt(a[0], a[1]);
        const [q2, r2] = this.hexAt(b[0], b[1]);
        const dq = q2 - q1, dr = r2 - r1;
        return (Math.abs(dq) + Math.abs(dr) + Math.abs(dq + dr)) / 2;
      }
      return Math.hypot(b[0] - a[0], b[1] - a[1]) / this.cell;
    }
    linesIn(x0, y0, x1, y1, limit) {
      limit = limit || 4000;
      const out = [];
      if (this.kind === "square") {
        const s = this.cell;
        for (let i = Math.floor((x0 - this.ox) / s); ; i++) {
          const x = this.ox + i * s;
          if (x > x1 || out.length > limit) break;
          out.push([x, y0, x, y1]);
        }
        for (let j = Math.floor((y0 - this.oy) / s); ; j++) {
          const y = this.oy + j * s;
          if (y > y1 || out.length > limit) break;
          out.push([x0, y, x1, y]);
        }
        return out;
      }
      if (this.kind === "hex_rows" || this.kind === "hex_cols") {
        const pad = this.cell;
        const c = [this.hexAt(x0 - pad, y0 - pad), this.hexAt(x1 + pad, y1 + pad), this.hexAt(x0 - pad, y1 + pad),
          this.hexAt(x1 + pad, y0 - pad)];
        const rs = c.map((p) => p[1]), qs = c.map((p) => p[0]);
        const rLo = Math.min(...rs) - 1, rHi = Math.max(...rs) + 1;
        const qLo = Math.min(...qs) - (rHi - rLo) - 1, qHi = Math.max(...qs) + (rHi - rLo) + 1;
        for (let r = rLo; r <= rHi; r++) {
          for (let q = qLo; q <= qHi; q++) {
            const [cx, cy] = this.hexCenter(q, r);
            if (x0 - pad <= cx && cx <= x1 + pad && y0 - pad <= cy && cy <= y1 + pad) {
              const p = this.hexCorners(q, r);
              out.push([p[3][0], p[3][1], p[4][0], p[4][1], p[5][0], p[5][1], p[0][0], p[0][1]]);
              if (out.length > limit) return out;
            }
          }
        }
      }
      return out;
    }
  }

  function tokenBox(token, grid) {
    return [token.x, token.y, Math.max(4, (token.size === undefined ? 1 : token.size) * grid.cell / 2)];
  }

  function pointInPolygon(x, y, pts) {
    let inside = false;
    const n = Math.floor(pts.length / 2);
    let j = n - 1;
    for (let i = 0; i < n; i++) {
      const xi = pts[2 * i], yi = pts[2 * i + 1], xj = pts[2 * j], yj = pts[2 * j + 1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-12) + xi) inside = !inside;
      j = i;
    }
    return inside;
  }

  // ------------------------------------------------------------------ heights and areas
  function feetPerPx(scene) {
    const g = scene.grid || {};
    return Number(g.feet || 5) / Math.max(1e-6, Number(g.cell || 70));
  }
  function groundAt(scene, x, y) {
    const zones = scene.zones || [];
    for (let i = zones.length - 1; i >= 0; i--) {
      if (pointInPolygon(x, y, zones[i].pts)) return Number(zones[i].elev);
    }
    return 0;
  }
  function tokenElevation(scene, token) { return groundAt(scene, token.x, token.y) + Number(token.z || 0); }
  function tokenHeight(scene, token) {
    const g = scene.grid || {};
    return Math.max(0.5, Number(token.size === undefined ? 1 : token.size)) * Number(g.feet || 5);
  }
  function distanceFt(scene, a, b) {
    const grid = Grid.of(scene);
    const feet = Number((scene.grid || {}).feet || 5);
    const flat = grid.cellsBetween([a[0], a[1]], [b[0], b[1]]);
    const up = Math.abs(b[2] - a[2]) / feet;
    if (grid.kind === "none") return Math.hypot(flat, up) * feet;
    return Math.max(flat, pyRound(up)) * feet;
  }
  function areaOrigin(scene, area) {
    const base = area.token ? (area.base || 0) : groundAt(scene, area.x, area.y);
    return [area.x, area.y, base + Number(area.dz || 0)];
  }
  function areaAxis(area) {
    const d = radians(area.dir || 0), p = radians(area.pitch || 0);
    return [Math.cos(p) * Math.cos(d), Math.cos(p) * Math.sin(d), Math.sin(p)];
  }
  function tokenReachFt(scene, area) {
    if (area.shape !== "emanation" || !area.token) return 0;
    for (const t of scene.tokens || []) {
      if (t.id === area.token) {
        return Math.max(0.5, Number(t.size === undefined ? 1 : t.size)) * Number((scene.grid || {}).feet || 5) / 2;
      }
    }
    return 0;
  }
  function areaContains(scene, area, x, y, z, reach) {
    const fpp = feetPerPx(scene);
    const [ox, oy, oz] = areaOrigin(scene, area);
    const vx = (x - ox) * fpp, vy = (y - oy) * fpp, vz = z - oz;
    const shape = area.shape, size = Number(area.size);
    const eps = 1e-6;
    if (shape === "cube" || shape === "square") {
      const d = radians(area.dir === undefined ? 45 : area.dir);
      const sx = Math.cos(d) >= 0 ? 1 : -1;
      const sy = Math.sin(d) >= 0 ? 1 : -1;
      if (!(-eps <= vx * sx && vx * sx <= size + eps && -eps <= vy * sy && vy * sy <= size + eps)) return false;
      return shape === "square" || (-eps <= vz && vz <= size + eps);
    }
    if (shape === "circle") return Math.hypot(vx, vy) <= size + eps;
    if (shape === "sphere" || shape === "emanation") {
      const r = size + (reach === undefined || reach === null ? tokenReachFt(scene, area) : reach);
      return Math.sqrt(vx * vx + vy * vy + vz * vz) <= r + eps;
    }
    const [ax, ay, az] = areaAxis(area);
    const t = vx * ax + vy * ay + vz * az;
    if (t <= eps || t > size + eps) return false;
    const px = vx - t * ax, py = vy - t * ay, pz = vz - t * az;
    const off = Math.sqrt(px * px + py * py + pz * pz);
    if (shape === "cone") return off <= t / 2 + eps;
    return off <= Number(area.width === undefined ? 5 : area.width) / 2 + eps;
  }
  function areaFootprint(scene, area) {
    const ppf = 1 / feetPerPx(scene);
    const [ox, oy] = areaOrigin(scene, area);
    const shape = area.shape, size = Number(area.size) * ppf;
    if (shape === "cube" || shape === "square") {
      const d = radians(area.dir === undefined ? 45 : area.dir);
      const sx = Math.cos(d) >= 0 ? size : -size;
      const sy = Math.sin(d) >= 0 ? size : -size;
      return [ox, oy, ox + sx, oy, ox + sx, oy + sy, ox, oy + sy];
    }
    if (shape === "circle" || shape === "sphere" || shape === "emanation") {
      const r = size + tokenReachFt(scene, area) * ppf;
      const out = [];
      for (let i = 0; i < 48; i++) out.push(ox + r * Math.cos(i * Math.PI / 24), oy + r * Math.sin(i * Math.PI / 24));
      return out;
    }
    const d = radians(area.dir || 0);
    const length = size * Math.cos(radians(area.pitch || 0));
    const ux = Math.cos(d), uy = Math.sin(d);
    const nx = -uy, ny = ux;
    if (shape === "cone") {
      const half = Number(area.size) * ppf / 2;
      const pts = [ox, oy];
      for (let i = 0; i < 9; i++) {
        const k = -1 + i / 4;
        pts.push(ox + ux * length + nx * half * k, oy + uy * length + ny * half * k);
      }
      return pts;
    }
    const w = Number(area.width === undefined ? 5 : area.width) * ppf / 2;
    const ex = ox + ux * length, ey = oy + uy * length;
    return [ox + nx * w, oy + ny * w, ex + nx * w, ey + ny * w, ex - nx * w, ey - ny * w, ox - nx * w, oy - ny * w];
  }
  function cellsIn(grid, x0, y0, x1, y1, limit) {
    limit = limit || 6000;
    const out = [];
    if (grid.kind === "square") {
      const s = grid.cell;
      const i0 = Math.floor((x0 - grid.ox) / s), i1 = Math.ceil((x1 - grid.ox) / s);
      const j0 = Math.floor((y0 - grid.oy) / s), j1 = Math.ceil((y1 - grid.oy) / s);
      for (let j = j0; j <= j1; j++) {
        for (let i = i0; i <= i1; i++) {
          const cx = grid.ox + (i + 0.5) * s, cy = grid.oy + (j + 0.5) * s;
          if (x0 <= cx && cx <= x1 && y0 <= cy && cy <= y1) {
            out.push([cx, cy]);
            if (out.length >= limit) return out;
          }
        }
      }
      return out;
    }
    if (grid.kind === "hex_rows" || grid.kind === "hex_cols") {
      const c = [grid.hexAt(x0, y0), grid.hexAt(x1, y1), grid.hexAt(x0, y1), grid.hexAt(x1, y0)];
      const qs = c.map((p) => p[0]), rs = c.map((p) => p[1]);
      const rLo = Math.min(...rs) - 1, rHi = Math.max(...rs) + 1;
      const qLo = Math.min(...qs) - (rHi - rLo) - 1, qHi = Math.max(...qs) + (rHi - rLo) + 1;
      for (let r = rLo; r <= rHi; r++) {
        for (let q = qLo; q <= qHi; q++) {
          const [cx, cy] = grid.hexCenter(q, r);
          if (x0 <= cx && cx <= x1 && y0 <= cy && cy <= y1) {
            out.push([cx, cy]);
            if (out.length >= limit) return out;
          }
        }
      }
    }
    return out;
  }
  function areaCells(scene, area) {
    const grid = Grid.of(scene);
    if (grid.kind === "none") return [];
    const pts = areaFootprint(scene, area);
    const xs = pts.filter((_, i) => i % 2 === 0), ys = pts.filter((_, i) => i % 2 === 1);
    const pad = grid.cell;
    const reach = tokenReachFt(scene, area);
    return cellsIn(grid, Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad)
      .filter(([cx, cy]) => areaContains(scene, area, cx, cy, groundAt(scene, cx, cy), reach));
  }
  function areaTokens(scene, area) {
    const grid = Grid.of(scene);
    const reach = tokenReachFt(scene, area);
    const hit = [];
    for (const t of scene.tokens || []) {
      if (t.id === area.token && (area.shape === "emanation" || area.shape === "cone" || area.shape === "line") &&
          Math.abs(area.ox || 0) < 1 && Math.abs(area.oy || 0) < 1) continue;
      const [cx, cy, r] = tokenBox(t, grid);
      const base = tokenElevation(scene, t);
      const top = base + tokenHeight(scene, t);
      const k = r * 0.85;
      const samples = [[cx, cy]];
      for (let i = 0; i < 8; i++) samples.push([cx + k * Math.cos(i * Math.PI / 4), cy + k * Math.sin(i * Math.PI / 4)]);
      let inside = false;
      for (const [x, y] of samples) {
        for (const z of [base, (base + top) / 2, top]) {
          if (areaContains(scene, area, x, y, z, reach)) { inside = true; break; }
        }
        if (inside) break;
      }
      if (inside) hit.push(t.id);
    }
    return hit;
  }
  // The same clean-up the DM's side does to a new area (so a preview is what will be laid down)
  function cleanArea(a) {
    if (!a || AREA_SHAPES.indexOf(a.shape) < 0) return null;
    return {
      id: a.id || "", shape: a.shape,
      x: pyRound(num(a.x), 1), y: pyRound(num(a.y), 1),
      size: pyRound(num(a.size, 5, 0.5, 5000), 1),
      width: pyRound(num(a.width, 5, 0.5, 500), 1),
      dir: pyRound(mod(num(a.dir, 0, -720, 720), 360), 2),
      pitch: pyRound(num(a.pitch, 0, -90, 90), 1),
      dz: pyRound(num(a.dz, 0, -MAX_HEIGHT, MAX_HEIGHT), 1),
      color: /^#[0-9A-Fa-f]{6}$/.test(a.color || "") ? a.color : AREA_COLORS[0],
      token: String(a.token || "").slice(0, 16), ox: pyRound(num(a.ox, 0, -5000, 5000), 1),
      oy: pyRound(num(a.oy, 0, -5000, 5000), 1), base: pyRound(num(a.base), 1), author: "",
    };
  }

  // ------------------------------------------------------------------ drawing helpers (ui/tabletop_canvas.py)
  const AXIS_SNAP_DEG = 6;
  function axisSnap(x0, y0, x1, y1) {
    const dx = x1 - x0, dy = y1 - y0;
    if (!dx && !dy) return [x1, y1];
    const angle = mod(Math.abs(degrees(Math.atan2(dy, dx))), 180);
    if (angle < AXIS_SNAP_DEG || angle > 180 - AXIS_SNAP_DEG) return [x1, y0];
    if (Math.abs(angle - 90) < AXIS_SNAP_DEG) return [x0, y1];
    return [x1, y1];
  }
  function shapeBox(x0, y0, x1, y1, square, centred) {
    let dx = x1 - x0, dy = y1 - y0;
    if (square) {
      const side = Math.max(Math.abs(dx), Math.abs(dy));
      dx = side * Math.sign(dx || 1);
      dy = side * Math.sign(dy || 1);
    }
    if (centred) return [x0 - dx, y0 - dy, x0 + dx, y0 + dy];
    return [x0, y0, x0 + dx, y0 + dy];
  }
  function fmt(v) {
    // Python's "{:g}" for the numbers the tabletop shows (feet, degrees)
    if (Number.isInteger(v)) return String(v);
    return String(parseFloat(v.toPrecision(6)));
  }
  function heightText(feet) {
    if (Math.abs(feet) < 0.05) return "";
    return (feet > 0 ? "↑" : "↓") + " " + fmt(Math.abs(feet)) + " ft";
  }
  function areaText(area, scene) {
    const shape = area.shape || "";
    let text = (AREA_LABELS[shape] || shape) + " " + fmt(area.size || 0) + " ft";
    if (shape === "line" && (area.width === undefined ? 5 : area.width) !== 5) text += " × " + fmt(area.width) + " ft";
    const pitch = area.pitch || 0;
    if ((shape === "cone" || shape === "line") && pitch) text += ", " + (pitch > 0 ? "up" : "down") + " " + fmt(Math.abs(pitch)) + "°";
    if (scene) {
      const h = heightText(areaOrigin(scene, area)[2]);
      if (h) text += "  (" + h + ")";
    }
    return text;
  }
  function tokenLetter(name) {
    for (const ch of String(name || "")) {
      if (/[\p{L}\p{N}]/u.test(ch)) return ch.toUpperCase();
    }
    return "?";
  }

  // condition ring colours: a made-up condition gets a steady colour of its own (as in the app: from an MD5)
  function md5hex(text) {
    const bytes = new TextEncoder().encode(text);
    const words = [];
    const n = bytes.length;
    for (let i = 0; i < n; i++) words[i >> 2] |= bytes[i] << ((i % 4) * 8);
    words[n >> 2] |= 0x80 << ((n % 4) * 8);
    const total = (((n + 8) >> 6) + 1) * 16;
    for (let i = 0; i < total; i++) words[i] = words[i] | 0;
    words[total - 2] = (n * 8) >>> 0;
    words[total - 1] = Math.floor(n / 0x20000000);
    const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    const K = [];
    for (let i = 0; i < 64; i++) K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296) | 0;
    let a0 = 0x67452301, b0 = 0xefcdab89 | 0, c0 = 0x98badcfe | 0, d0 = 0x10325476;
    for (let off = 0; off < total; off += 16) {
      let a = a0, b = b0, c = c0, d = d0;
      for (let i = 0; i < 64; i++) {
        let f, g;
        if (i < 16) { f = (b & c) | (~b & d); g = i; }
        else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
        else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
        else { f = c ^ (b | ~d); g = (7 * i) % 16; }
        const s = S[(i >> 4) * 4 + (i % 4)];
        const sum = (a + f + K[i] + words[off + g]) | 0;
        a = d; d = c; c = b;
        b = (b + ((sum << s) | (sum >>> (32 - s)))) | 0;
      }
      a0 = (a0 + a) | 0; b0 = (b0 + b) | 0; c0 = (c0 + c) | 0; d0 = (d0 + d) | 0;
    }
    let out = "";
    for (const v of [a0, b0, c0, d0]) {
      for (let i = 0; i < 4; i++) out += ((v >>> (i * 8)) & 0xff).toString(16).padStart(2, "0");
    }
    return out;
  }
  function conditionColor(name) {
    if (CONDITION_COLORS[name]) return CONDITION_COLORS[name];
    const h = parseInt(md5hex(name.toLowerCase()).slice(0, 6), 16);
    const hex = (v) => v.toString(16).toUpperCase().padStart(2, "0");
    return "#" + hex(80 + (h >> 16) % 150) + hex(80 + (h >> 8) % 150) + hex(80 + h % 150);
  }

  const api = {
    SQRT3, AREA_SHAPES, AREA_LABELS, AREA_COLORS, MAX_HEIGHT, Grid, pyRound, mod, radians, degrees,
    tokenBox, pointInPolygon, feetPerPx, groundAt, tokenElevation, tokenHeight, distanceFt, areaOrigin,
    areaContains, areaFootprint, cellsIn, areaCells, areaTokens, cleanArea, axisSnap, shapeBox, heightText,
    areaText, tokenLetter, md5hex, conditionColor, fmt,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SpellbookGeometry = api;
})(typeof self !== "undefined" ? self : this);
