// Making the DM's changes to the map I hold: the browser side of table_patch.py (the app's player side uses
// table_patch.apply_ops; tests/test_table_patch.py checks both give the same view).
//
// After a change the DM's app sends only what changed in my view: a list of operations, each a list
// ["set", path, value], ["del", path], ["append", path, items] or ["items", path, put, gone, order]
// (records with an "id": put = new or changed ones, gone = ids taken away, order = the new order or null).
(function (root) {
  "use strict";

  const MAX_OPS = 2000;
  const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);

  function applyOps(view, ops) {
    if (!isObj(view) || !Array.isArray(ops) || ops.length > MAX_OPS) return false;
    for (const op of ops) {
      if (!Array.isArray(op) || op.length < 2 || !Array.isArray(op[1]) || !op[1].length) return false;
      const kind = op[0], path = op[1];
      if (!path.every((k) => typeof k === "string")) return false;
      let parent = view;
      for (const k of path.slice(0, -1)) {
        if (!isObj(parent) || !Object.prototype.hasOwnProperty.call(parent, k) || !isObj(parent[k])) return false;
        parent = parent[k];
      }
      const key = path[path.length - 1];
      if (key === "__proto__" || key === "constructor" || key === "prototype") return false;
      const have = Object.prototype.hasOwnProperty.call(parent, key) ? parent[key] : undefined;
      if (kind === "set" && op.length === 3) {
        parent[key] = op[2];
      } else if (kind === "del") {
        delete parent[key];
      } else if (kind === "append" && op.length === 3 && Array.isArray(op[2]) && Array.isArray(have)) {
        for (const item of op[2]) have.push(item);
      } else if (kind === "items" && op.length === 5 && Array.isArray(have)) {
        const put = op[2], gone = op[3], order = op[4];
        if (!Array.isArray(put) || !Array.isArray(gone) || !(order === null || Array.isArray(order))) return false;
        if (!put.every((r) => isObj(r) && typeof r.id === "string")) return false;
        let records = have.filter(isObj);
        const index = new Map(records.map((r, i) => [r.id, i]));
        for (const r of put) {
          if (index.has(r.id)) records[index.get(r.id)] = r;
          else { index.set(r.id, records.length); records.push(r); }
        }
        const goneIds = new Set(gone);
        records = records.filter((r) => !goneIds.has(r.id));
        if (order !== null) {
          const byId = new Map(records.map((r) => [r.id, r]));
          if (order.length !== byId.size || !order.every((i) => byId.has(i)) || new Set(order).size !== order.length) {
            return false;
          }
          records = order.map((i) => byId.get(i));
        }
        parent[key] = records;
      } else {
        return false;
      }
    }
    return true;
  }

  const api = { applyOps: applyOps, MAX_OPS: MAX_OPS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SpellbookTablePatch = api;
})(typeof self !== "undefined" ? self : this);
