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
  window.SpellbookSession = session;          // the tabletop and chat code hook in here

  function connect(name, password) {
    session.name = name;
    session.wanted = true;
    const scheme = location.protocol === "https:" ? "wss://" : "ws://";
    let ws;
    try {
      ws = new WebSocket(scheme + location.host + "/ws");
    } catch (e) {
      failed("Couldn't reach the DM's computer.");
      return;
    }
    session.ws = ws;
    ws.onopen = () => {
      setStatus(document.body.dataset.approval === "0" ? "Joining…" : "Waiting for the DM to let you in…");
      ws.send(JSON.stringify({ type: "hello", body: {
        proto: PROTOCOL, name: name, client_id: clientId(), password: password || "", app_version: "browser",
      } }));
    };
    ws.onmessage = (ev) => {
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (!msg || typeof msg.type !== "string") return;
      received(msg);
    };
    ws.onclose = () => {
      if (session.ws !== ws) return;
      clearInterval(session.pingTimer);
      const wasIn = session.joined;
      session.joined = false;
      session.ws = null;
      $("conn").classList.add("off");
      if (wasIn && session.wanted) {
        // the page stays as it is; try to get back in
        toast("Lost the connection to the DM. Reconnecting…", 6000);
        const wait = Math.min(15000, 1000 * Math.pow(2, session.retry++));
        setTimeout(() => { if (session.wanted && !session.ws) connect(session.name, password); }, wait);
      } else if (session.wanted) {
        failed("The connection closed before the DM let you in.");
      }
    };
  }

  function failed(text) {
    session.wanted = false;
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
        failed(body.message || "The DM's computer refused the connection.");
        if (session.ws) session.ws.close();
      }
      return;
    }
    switch (msg.type) {
      case "presence":
        if (body.peer && body.peer.peer_id) {
          session.peers = session.peers.filter((p) => p.peer_id !== body.peer.peer_id);
          if (body.event === "join") session.peers.push(body.peer);
          renderPeople();
        }
        break;
      case "bye":
        session.wanted = false;
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

  function welcome(body) {
    session.joined = true;
    session.retry = 0;
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
    session.pingTimer = setInterval(() => {
      if (session.ws && session.ws.readyState === 1) session.ws.send('{"type":"ping","body":{}}');
    }, PING_MS);
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

  $("join-name").value = stored("name", "");
  $("join-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = $("join-name").value.replace(/\s+/g, " ").trim();
    if (!name) {
      setStatus("Enter the name you want the table to see.", true);
      return;
    }
    $("join-btn").disabled = true;
    setStatus("Connecting…");
    connect(name, $("join-pw").value);
  });
  loadInfo();
})();
