// Spellbook Tabletop in a browser: the side panel. Chat and dice, the turn order, and who is here.
//
// Rolls are made by the DM's app (a "/roll" chat line), so nobody can fudge a die. The turn order is the
// DM's initiative tracker as the DM's app filtered it for this player; a player may only change their own
// character's HP and conditions, and the DM's app checks that again.
(function () {
  "use strict";

  const S = window.SpellbookSession;
  const $ = (id) => document.getElementById(id);
  const MAX_LINES = 300;
  const DICE = [4, 6, 8, 10, 12, 20, 100];
  const CONDITIONS = [
    "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled", "Incapacitated",
    "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious",
    "Concentrating", "Dodging", "Hasted", "Blessed", "Hexed", "Marked", "Raging",
  ];

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function button(label, title, fn, cls) {
    const b = el("button", cls || "", label);
    b.type = "button";
    if (title) b.title = title;
    b.addEventListener("click", fn);
    return b;
  }
  // "[[spell:Fireball|the fireball]]" reads as "the fireball"
  function plain(text) {
    return String(text || "").replace(/\[\[([^\]]+)\]\]/g, (m, inner) => {
      const [target, shown] = inner.split("|", 2);
      if (shown && shown.trim()) return shown.trim();
      const name = target.indexOf(":") >= 0 ? target.slice(target.indexOf(":") + 1) : target;
      return name.split("#").pop().trim();
    });
  }
  function clock(ts) {
    const d = ts ? new Date(ts * 1000) : new Date();
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }
  function peerName(id) {
    if (id === "host") return S.hostName;
    const p = S.peers.find((x) => x.peer_id === id);
    return p ? p.name : "";
  }

  // ------------------------------------------------------------------ tabs and unread dots
  let tab = "chat";
  function sideOpen() {
    const side = $("side");
    return getComputedStyle(side).position !== "fixed" || side.classList.contains("open");
  }
  function showTab(name) {
    tab = name;
    for (const b of document.querySelectorAll(".tab")) {
      const on = b.dataset.tab === name;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    }
    for (const t of ["chat", "turns", "people"]) $("tab-" + t).hidden = t !== name;
    if (name === "chat") { $("chat-dot").hidden = true; scrollChat(true); }
    if (name === "turns") $("turn-dot").hidden = true;
    sideDot();
  }
  function sideDot() {
    $("side-dot").hidden = $("chat-dot").hidden && $("turn-dot").hidden;
  }
  function unread(which) {
    if (tab === which && sideOpen()) return;
    $(which + "-dot").hidden = false;
    sideDot();
  }
  for (const b of document.querySelectorAll(".tab")) b.addEventListener("click", () => showTab(b.dataset.tab));
  $("side-toggle").addEventListener("click", () => setTimeout(() => {
    if (sideOpen()) showTab(tab);
  }, 0));

  // ------------------------------------------------------------------ chat
  const log = $("chat-log");
  function scrollChat(force) {
    if (force || log.scrollHeight - log.scrollTop - log.clientHeight < 60) log.scrollTop = log.scrollHeight;
  }
  function addLine(li, mine) {
    const near = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
    log.appendChild(li);
    while (log.children.length > MAX_LINES) log.removeChild(log.firstChild);
    if (near || mine) log.scrollTop = log.scrollHeight;
    if (!mine) unread("chat");
  }
  function line(ts, cls) {
    const li = el("li", "line " + (cls || ""));
    li.appendChild(el("span", "time", clock(ts)));
    return li;
  }

  S.on("chat", (body, msg) => {
    const mine = msg.from === S.me;
    const li = line(msg.ts);
    li.appendChild(el("span", mine ? "who me" : "who", (body.name || "?") + ": "));
    li.appendChild(el("span", "text", plain(body.text)));
    addLine(li, mine);
  });

  S.on("dm", (body, msg) => {
    const mine = msg.from === S.me;
    const li = line(msg.ts, "whisper");
    const who = mine ? "You → " + (peerName(body.to) || "them") : (body.name || peerName(msg.from) || "?") + " → you";
    li.appendChild(el("span", "who", "(whisper) " + who + ": "));
    li.appendChild(el("span", "text", plain(body.text)));
    addLine(li, mine);
  });

  S.on("roll", (body, msg) => {
    const mine = msg.from === S.me;
    const li = line(msg.ts, "roll");
    const who = mine ? "You" : (body.name || "?");
    let text = "🎲 " + (body.private ? "(private) " : "") + who + " rolled " + (body.expr || "");
    if (body.label) text += " (" + body.label + ")";
    text += ": " + (body.detail || "") + " = ";
    li.appendChild(el("span", "text", text));
    const total = el("strong", "total" + (body.crit ? " " + body.crit : ""), String(body.total));
    li.appendChild(total);
    if (body.crit) li.appendChild(el("span", body.crit, body.crit === "nat20" ? "  natural 20!" : "  natural 1…"));
    addLine(li, mine);
  });

  S.on("error", (body) => {
    const li = line(0, "system");
    li.appendChild(el("span", "text", body.message || "That didn't work."));
    addLine(li, true);
  });

  S.on("joined", () => {
    const li = line(0, "system");
    li.appendChild(el("span", "text", "You joined " + S.hostName + "'s session."));
    addLine(li, true);
  });

  S.on("peers", (peers) => {
    const to = $("chat-to");
    const keep = to.value;
    to.textContent = "";
    to.appendChild(new Option("Everyone", ""));
    for (const p of peers) {
      if (p.peer_id === S.me) continue;
      to.appendChild(new Option("→ " + p.name + (p.is_host ? " (DM)" : ""), p.peer_id));
    }
    to.value = Array.from(to.options).some((o) => o.value === keep) ? keep : "";
  });

  function say(text) {
    text = text.trim();
    if (!text) return false;
    const to = $("chat-to").value;
    const ok = to && !text.startsWith("/") ? S.send("dm", { to: to, text: text }) : S.send("chat", { text: text });
    if (!ok) S.toast("You're not connected to the DM right now.");
    return ok;
  }

  $("chat-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const input = $("chat-text");
    if (say(input.value)) input.value = "";
  });

  // ------------------------------------------------------------------ dice
  for (const sides of DICE) {
    $("dice-buttons").appendChild(button("d" + sides, "Roll a d" + sides, () => roll(sides), "die"));
  }
  function roll(sides) {
    const bonus = Math.max(-99, Math.min(99, parseInt($("dice-bonus").value, 10) || 0));
    let expr = "1d" + sides + (bonus > 0 ? "+" + bonus : bonus < 0 ? String(bonus) : "");
    const mode = $("dice-mode").value;
    if (mode && sides === 20) expr += " " + mode;
    say(($("dice-private").checked ? "/gmroll " : "/roll ") + expr);
  }

  // ------------------------------------------------------------------ the turn order
  let view = null;
  let wasMyTurn = false;
  let seq = 0;
  const amounts = {};                       // entry id -> what's typed in its HP box

  function command(cmd) {
    if (!S.send("tracker_cmd", { cmd: cmd, seq: ++seq })) S.toast("You're not connected to the DM right now.");
  }
  S.on("tracker_error", (body) => S.toast(body.message || "The DM's app refused that."));

  S.on("tracker_state", (body) => {
    const v = body.view;
    if (!v || !Array.isArray(v.entries)) return;
    const before = view ? JSON.stringify([view.round, view.active, view.entries.length]) : "";
    view = v;
    renderTurns();
    if (before && before !== JSON.stringify([v.round, v.active, v.entries.length])) unread("turns");
    const active = v.entries.find((e) => e.id === v.active);
    const myTurn = !!(v.started && active && active.mine);
    if (myTurn && !wasMyTurn) {
      S.toast("It's " + active.name + "'s turn!", 5000);
      if (navigator.vibrate) { try { navigator.vibrate(200); } catch (e) { /* not allowed */ } }
    }
    wasMyTurn = myTurn;
  });

  function hpText(e) {
    if (e.hp !== undefined && e.hp !== null) {
      return e.hp + "/" + e.hp_max + (e.hp_temp ? " +" + e.hp_temp : "");
    }
    return "";
  }

  function renderTurns() {
    const v = view;
    const list = $("turn-list");
    list.textContent = "";
    if (!v) return;
    $("turn-round").textContent = v.started ? "Round " + v.round : (v.entries.length ? "Combat hasn't started." : "No combat yet.");
    const groups = v.group_names || {};
    for (const e of v.entries) {
      const li = el("li", "turn" + (e.id === v.active && v.started ? " active" : "") + (e.mine ? " mine" : "") +
                    (e.defeated ? " defeated" : ""));
      const top = el("div", "turn-top");
      top.appendChild(el("span", "init", e.initiative === null || e.initiative === undefined ? "–" : String(e.initiative)));
      const name = el("span", "turn-name", e.name + (e.hidden ? " (hidden)" : ""));
      if (e.group && groups[e.group]) name.title = groups[e.group];
      top.appendChild(name);
      if (e.ac !== undefined && e.ac !== null) top.appendChild(el("span", "ac", "AC " + e.ac));
      li.appendChild(top);

      if (e.hp_frac !== undefined) {
        const bar = el("div", "hpbar");
        const fill = el("span");
        fill.style.width = Math.round(e.hp_frac * 100) + "%";
        fill.className = e.hp_frac <= 0.5 ? "low" : "";
        bar.appendChild(fill);
        li.appendChild(bar);
      } else if (hpText(e)) {
        li.appendChild(el("div", "hp", "HP " + hpText(e)));
      }

      const conds = el("div", "conds");
      for (const c of e.conditions || []) {
        let label = c.name + (c.level ? " " + c.level : "") + (c.rounds ? " (" + c.rounds + ")" : "");
        if (e.mine) {
          conds.appendChild(button(label + " ✕", "Remove " + c.name,
            () => command({ type: "remove_condition", id: e.id, name: c.name }), "cond mine"));
        } else {
          conds.appendChild(el("span", "cond", label));
        }
      }
      if (conds.children.length) li.appendChild(conds);

      if (e.mine && e.kind !== "event") li.appendChild(ownControls(e));
      list.appendChild(li);
    }
    const mine = v.entries.some((e) => e.mine);
    $("add-me").hidden = !(v.can_add && !mine);
    if (!$("add-me").hidden && !$("add-name").value) $("add-name").value = S.name;
  }

  function ownControls(e) {
    const box = el("div", "own");
    const amount = el("input");
    amount.type = "number";
    amount.min = "0";
    amount.max = "9999";
    amount.inputMode = "numeric";
    amount.placeholder = "HP";
    amount.setAttribute("aria-label", "Amount for " + e.name);
    amount.value = amounts[e.id] || "";
    amount.addEventListener("input", () => { amounts[e.id] = amount.value; });
    const n = () => Math.max(0, Math.min(9999, parseInt(amount.value, 10) || 0));
    const done = () => { amount.value = ""; amounts[e.id] = ""; };
    box.appendChild(amount);
    box.appendChild(button("Damage", "Take this much damage (temporary HP goes first)", () => {
      if (n()) { command({ type: "hp_delta", id: e.id, delta: -n() }); done(); }
    }, "danger"));
    box.appendChild(button("Heal", "Heal this much", () => {
      if (n()) { command({ type: "hp_delta", id: e.id, delta: n() }); done(); }
    }));
    box.appendChild(button("Temp", "Set temporary HP to this", () => {
      command({ type: "set_stats", id: e.id, hp_temp: n() }); done();
    }));
    const add = el("select", "add-cond");
    add.setAttribute("aria-label", "Add a condition to " + e.name);
    add.appendChild(new Option("+ Condition", ""));
    const have = new Set((e.conditions || []).map((c) => c.name));
    for (const c of CONDITIONS) if (!have.has(c)) add.appendChild(new Option(c, c));
    add.addEventListener("change", () => {
      if (add.value) command({ type: "add_condition", id: e.id, name: add.value });
      add.value = "";
    });
    box.appendChild(add);
    return box;
  }

  $("add-me").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const num = (id, lo, hi, d) => Math.max(lo, Math.min(hi, parseInt($(id).value, 10) || d));
    const name = $("add-name").value.replace(/\s+/g, " ").trim();
    if (!name) return;
    const hp = num("add-hp", 0, 9999, 0);
    command({ type: "add_me", name: name, hp: hp, hp_max: hp, ac: num("add-ac", 0, 50, 10),
              init_bonus: num("add-init", -20, 20, 0) });
  });

  // ------------------------------------------------------------------ playing as
  function fillPlayAs() {
    const c = S.character || {};
    $("play-name").value = c.name || "";
    $("play-hp").value = c.hp_max !== undefined ? c.hp_max : "";
    $("play-ac").value = c.ac !== undefined ? c.ac : "";
  }
  S.on("joined", fillPlayAs);
  $("play-as").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const info = S.readCharacter("play");
    if (S.setCharacter(info)) S.toast(info.name ? "The DM knows you're playing " + info.name + "." : "You're not playing a character.");
    else S.toast("You're not connected to the DM right now.");
  });

  window.SpellbookSide = { showTab: showTab, say: say };
})();
