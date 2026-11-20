// Spellbook Tabletop in a browser: joining the DM's session and staying connected.
//
// The page talks to the DM's app over one WebSocket, with the same JSON messages the app uses between
// computers ({"type": ..., "body": {...}}). The DM's app decides everything: what this player may see
// arrives already filtered, and every change is a command the DM's side checks.
(function () {
  "use strict";

  const PROTOCOL = 1;
  const PING_MS = 15000;
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------------ stored per browser
  function stored(key, fallback) {
    try { return localStorage.getItem("spellbook." + key) || fallback; } catch (e) { return fallback; }
  }
  function store(key, value) {
    try { localStorage.setItem("spellbook." + key, value); } catch (e) { /* private window */ }
  }
  function clientId() {
    let id = stored("client", "");
    if (!/^[0-9a-f]{16,32}$/.test(id)) {
      const bytes = new Uint8Array(12);
      (window.crypto || window.msCrypto).getRandomValues(bytes);
      id = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      store("client", id);
    }
    return id;
  }

  // ------------------------------------------------------------------ small helpers
  let toastTimer = null;
  function toast(text, ms) {
    const el = $("toast");
    el.textContent = text;
    el.hidden = !text;
    clearTimeout(toastTimer);
    if (text) toastTimer = setTimeout(() => { el.hidden = true; }, ms || 3500);
  }
  function setStatus(text, error) {
    const el = $("join-status");
    el.textContent = text || "";
    el.classList.toggle("error", !!error);
  }

  // ------------------------------------------------------------------ the session
  const session = {
    ws: null,
    joined: false,           // admitted by the DM
    wanted: false,           // the player asked to be in (so a dropped connection rejoins)
    me: "",                  // our peer id
    name: "",
    hostName: "",
    peers: [],               // {peer_id, name, is_host, web}
    handlers: {},            // message type -> [fn(body, msg)]
    pingTimer: null,
    retry: 0,
    rejoining: false,        // was in, lost the connection, trying to get back (the page stays as it is)
    rejoinTimer: null,
    password: "",
    heardAt: 0,              // when anything last arrived from the DM's computer
    pingedAt: 0,             // when we last asked "are you there?"
    on(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
    emit(type, body, msg) {
      for (const fn of this.handlers[type] || []) {
        try { fn(body, msg); } catch (e) { console.error("Spellbook:", type, e); }
      }
    },
    send(type, body) {
      if (this.ws && this.ws.readyState === 1 && this.joined) {
        this.ws.send(JSON.stringify({ type: type, body: body || {} }));
        return true;
      }
      return false;
    },
  };
  session.toast = toast;
  window.SpellbookSession = session;          // the tabletop and chat code hook in here

  function connect(name, password) {
    session.name = name;
    session.password = password || "";
    session.wanted = true;
    clearTimeout(session.rejoinTimer);
    const scheme = location.protocol === "https:" ? "wss://" : "ws://";
    let ws;
    try {
      ws = new WebSocket(scheme + location.host + "/ws");
    } catch (e) {
      if (session.rejoining) rejoinLater();
      else failed("Couldn't reach the DM's computer.");
      return;
    }
    session.ws = ws;
    ws.onopen = () => {
      if (!session.rejoining) {
        setStatus(document.body.dataset.approval === "0" ? "Joining…" : "Waiting for the DM to let you in…");
      }
      ws.send(JSON.stringify({ type: "hello", body: {
        proto: PROTOCOL, name: name, client_id: clientId(), password: session.password, app_version: "browser",
      } }));
    };
    ws.onmessage = (ev) => {
      session.heardAt = Date.now();
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (!msg || typeof msg.type !== "string") return;
      received(msg);
    };
    ws.onclose = () => lost(ws);
  }

  // The connection is gone (closed, or silent when asked). Once we've been let in, the page stays as it is
  // and keeps trying to get back; the DM's app remembers who it let in, so nobody is asked again.
  function lost(ws) {
    if (session.ws !== ws) return;
    clearInterval(session.pingTimer);
    const wasIn = session.joined;
    session.joined = false;
    session.ws = null;
    ws.onclose = ws.onmessage = ws.onopen = null;
    try { ws.close(); } catch (e) { /* already closed */ }
    $("conn").classList.add("off");
    if (!session.wanted) return;
    if (wasIn || session.rejoining) {
      if (wasIn) toast("Lost the connection to the DM. Reconnecting…", 6000);
      session.rejoining = true;
      rejoinLater();
    } else {
      failed("The connection closed before the DM let you in.");
    }
  }

  function rejoinLater(now) {
    clearTimeout(session.rejoinTimer);
    const wait = now ? 0 : Math.min(15000, 1000 * Math.pow(2, session.retry++));
    session.rejoinTimer = setTimeout(() => {
      if (session.wanted && !session.ws) connect(session.name, session.password);
    }, wait);
  }

  // Ask the DM's computer whether it's still there; no answer within a few seconds means the connection
  // died quietly (a phone that slept, a network that changed), so start again.
  function probe(within) {
    const ws = session.ws;
    if (!ws || ws.readyState !== 1 || !session.joined) return;
    if (session.pingedAt && session.heardAt < session.pingedAt && Date.now() - session.pingedAt > within) {
      lost(ws);
      return;
    }
    if (session.heardAt >= session.pingedAt) session.pingedAt = Date.now();
    ws.send('{"type":"ping","body":{}}');
  }

  function wakeUp() {
    if (!session.wanted) return;
    if (!session.ws && session.rejoining) {
      session.retry = 0;
      rejoinLater(true);
    } else if (session.ws && session.joined && session.ws.readyState === 1) {
      session.pingedAt = Date.now();
      session.ws.send('{"type":"ping","body":{}}');
      const ws = session.ws;
      setTimeout(() => {
        if (session.ws === ws && session.heardAt < session.pingedAt) lost(ws);
      }, 6000);
    }
  }
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") wakeUp(); });
  window.addEventListener("online", wakeUp);
  window.addEventListener("pageshow", wakeUp);

  function failed(text) {
    session.wanted = false;
    session.rejoining = false;
    clearTimeout(session.rejoinTimer);
    $("join-btn").disabled = false;
    setStatus(text, true);
    showJoin();
  }

  function received(msg) {
    const body = msg.body && typeof msg.body === "object" ? msg.body : {};
    if (!session.joined) {
      if (msg.type === "welcome") {
        welcome(body);
      } else if (msg.type === "error") {
        const ws = session.ws;
        if (session.rejoining) toast(body.message || "The DM's computer refused the connection.", 8000);
        failed(body.message || "The DM's computer refused the connection.");
        if (ws) lost(ws);
      }
      return;
    }
    switch (msg.type) {
      case "presence":
        if (body.peer && body.peer.peer_id) {
          const at = session.peers.findIndex((p) => p.peer_id === body.peer.peer_id);
          if (body.event === "update" && at >= 0) session.peers[at] = body.peer;
          else {
            session.peers = session.peers.filter((p) => p.peer_id !== body.peer.peer_id);
            if (body.event === "join") session.peers.push(body.peer);
          }
          renderPeople();
        }
        break;
      case "bye":
        session.wanted = false;
        session.rejoining = false;
        clearTimeout(session.rejoinTimer);
        toast(body.reason || "The session ended.", 8000);
        $("waiting-title").textContent = "The session ended.";
        $("waiting-text").textContent = body.reason || "";
        break;
      case "pong":
        break;
      default:
        session.emit(msg.type, body, msg);
    }
  }

  // the character this player says they're playing: {name, hp, hp_max, ac, init} (the DM's app checks it)
  function readCharacter(prefix) {
    const name = $(prefix + "-name").value.replace(/\s+/g, " ").trim();
    if (!name) return { name: "" };
    const num = (id, lo, hi) => {
      const v = parseInt($(id).value, 10);
      return Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : undefined;
    };
    const hp = num(prefix + "-hp", 0, 9999);
    const out = { name: name, ac: num(prefix + "-ac", 0, 50), init: num(prefix + "-init", -20, 30) };
    if (hp !== undefined) { out.hp = hp; out.hp_max = hp; }
    return out;
  }
  session.character = { name: "" };
  session.setCharacter = function (info) {
    session.character = info && info.name ? info : { name: "" };
    try { store("character", JSON.stringify(session.character)); } catch (e) { /* ignore */ }
    return session.send("character", session.character);
  };
  session.readCharacter = readCharacter;

  function welcome(body) {
    const back = session.rejoining;
    session.joined = true;
    session.retry = 0;
    session.rejoining = false;
    session.pingedAt = 0;
    session.me = String(body.peer_id || "");
    session.name = String(body.name || session.name);
    session.hostName = String((body.host && body.host.name) || "the DM");
    session.peers = Array.isArray(body.peers) ? body.peers : [];
    store("name", session.name);
    setStatus("");
    $("join").hidden = true;
    $("app").hidden = false;
    $("conn").classList.remove("off");
    $("scene-name").textContent = session.hostName + "'s table";
    document.title = session.hostName + "'s table";
    renderPeople();
    clearInterval(session.pingTimer);
    session.pingTimer = setInterval(() => probe(PING_MS), PING_MS);
    if (session.character.name) session.send("character", session.character);
    if (back) toast("Back at the table.", 2500);
    session.emit("joined", body);
  }

  function renderPeople() {
    const list = $("people");
    list.textContent = "";
    for (const p of session.peers) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = (p.is_host ? "👑 " : "") + p.name;
      li.appendChild(name);
      const tags = [];
      if (p.peer_id === session.me) tags.push("you");
      if (p.web) tags.push("browser");
      if (p.character) tags.unshift("as " + p.character);
      if (tags.length) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = "(" + tags.join(", ") + ")";
        li.appendChild(tag);
      }
      list.appendChild(li);
    }
    const others = session.peers.length;
    $("who").textContent = others === 1 ? "1 at the table" : others + " at the table";
    session.emit("peers", session.peers);
  }

  function showJoin() {
    $("join").hidden = false;
    $("app").hidden = true;
  }

  // ------------------------------------------------------------------ the join form
  async function loadInfo() {
    try {
      const res = await fetch("/info", { cache: "no-store" });
      const info = await res.json();
      $("join-host").textContent = "Join " + (info.name || "the DM") + "'s session.";
      $("join-pw-row").hidden = !info.password;
      document.body.dataset.approval = info.approval ? "1" : "0";
      if (info.proto !== PROTOCOL) {
        setStatus("This page doesn't match the DM's Spellbook. Reload the page.", true);
      } else if (info.full) {
        setStatus("The session is full right now.", true);
      }
    } catch (e) {
      $("join-host").textContent = "Couldn't reach the DM's computer. Is the session still running?";
    }
  }

  // the side panel slides in over the map on a phone
  $("side-toggle").addEventListener("click", () => {
    const open = !$("side").classList.contains("open");
    $("side").classList.toggle("open", open);
    $("side-toggle").setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("pointerdown", (ev) => {
    const side = $("side");
    if (side.classList.contains("open") && !side.contains(ev.target) && !$("side-toggle").contains(ev.target)) {
      side.classList.remove("open");
      $("side-toggle").setAttribute("aria-expanded", "false");
    }
  });

  $("join-name").value = stored("name", "");
  try {
    const saved = JSON.parse(stored("character", "{}"));
    if (saved && saved.name) {
      $("char-name").value = saved.name;
      if (saved.hp_max !== undefined) $("char-hp").value = saved.hp_max;
      if (saved.ac !== undefined) $("char-ac").value = saved.ac;
      if (saved.init !== undefined) $("char-init").value = saved.init;
      $("join-char").open = true;
    }
  } catch (e) { /* nothing saved */ }
  $("join-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = $("join-name").value.replace(/\s+/g, " ").trim();
    if (!name) {
      setStatus("Enter the name you want the table to see.", true);
      return;
    }
    session.character = readCharacter("char");
    try { store("character", JSON.stringify(session.character)); } catch (e) { /* ignore */ }
    $("join-btn").disabled = true;
    setStatus("Connecting…");
    connect(name, $("join-pw").value);
  });
  loadInfo();
})();
