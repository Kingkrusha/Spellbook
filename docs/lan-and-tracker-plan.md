# LAN sessions + initiative tracker: evaluation and plan

Status: planning document (written before implementation). Branch: `feature/lan-sessions`.

## 1. Verdict

Difficulty is **moderate**. The sockets are the easy part. The hard parts are keeping Tkinter
thread-safe, handling received data without overwriting the user's own content, OS
firewall/permission prompts, characters that depend on homebrew the receiver lacks, and (for the
tracker) never leaking hidden information to players.

Rough effort for one developer: LAN base 10-14 days (including encryption), initiative tracker
16-22 days, so about 5-7 weeks in total.

## 2. Decisions

| Decision | Resulting design |
|---|---|
| Host-only relay (star) | The DM's app is the only server and the only holder of game state. Players never connect to each other. DMs and direct sends are routed through the host. |
| Encryption from the start | TLS 1.3 with a per-session throwaway self-signed certificate; the joiner pins the certificate fingerprint carried in the invite code. See section 5. |
| Manual IP only (v1) | Join dialog: IP, port, invite code. Discovery (UDP beacon) comes later and is never the only path. |
| Dice + `[[links]]` in chat | In scope. The host rolls dice (`/roll 2d6+3`) so results are fair. Links reuse `object_link_widgets`. |
| Cross-platform from the start | Windows, macOS arm64 and macOS Intel are all first-class (the release workflow already builds all three). |

## 3. What the codebase gives us / what gets in the way

Helps:
- Serializers exist: `CharacterSheet`/`CharacterSpellList` `to_dict`/`from_dict`, and `content_io`
  (`bundle_of`, `import_bundle`, `ImportReport`) with a versioned `spellbook-content` format.
- Official content never needs to travel (`unofficial_objects()` returns only homebrew).
- Payloads are small (all character sheets together are ~43 KB).
- Standard library networking; a background-thread-to-UI pattern already exists (update check).
- SQLite opens a fresh connection per operation, so it is safe across threads.

Gets in the way:
1. Character import is UI-coupled (`ui/character_transfer.py`); it must become a headless module.
2. `content_io` updates an existing *custom* record with the same name. That is right for your own
   files, wrong for content from a peer: it needs a dry-run / conflict preview.
3. A character is two records joined by name (spell list in `characters.json`, sheet in
   `character_sheets.json`).
4. Managers notify UI listeners synchronously and are not thread-safe: every network-triggered
   mutation must run on the Tk thread.
5. Only spells have a per-object export today.
6. No test suite.
7. `paths.user_data_dir()` has no override, so two instances cannot run side by side from source.
   Add a `SPELLBOOK_DATA_DIR` override.

## 4. Architecture

- **Transport:** TCP, 4-byte big-endian length + UTF-8 JSON envelope
  `{v, type, id, from, ts, body}`, run on `asyncio` in a dedicated thread. Message types: `hello`,
  `welcome`, `presence`, `chat`, `dm`, `send_offer`, `send_data`, `accept`, `decline`, `ping`,
  `bye`, `error`, plus `tracker_state` / `tracker_cmd` for the tracker. `hello` carries protocol
  version, app version and data schema version; mismatches give a readable "please update".
- **Thread rule:** the network thread never touches widgets or managers. It pushes events onto a
  `queue.Queue`; the UI drains it with `after(50, ...)`.
- **SessionService:** owned by `MainWindow`, not by a page (pages are destroyed on navigation).
  The Session tab, tracker page and pop-up are all views of it.
- **UI:** a "Session" page (peers, chat, Send..., Inbox, status chip), reached from Home > Game
  Tools. Avoid deep edits to `character_sheet_view.py` (5.5k lines).
- **Shutdown:** disconnect cleanly from the close path in `main.py`.

## 5. Encryption design

- The host generates a throwaway self-signed certificate per session and runs TLS 1.3 using
  Python's `ssl`. The joining client checks the certificate's SHA-256 fingerprint (carried in the
  invite code) after the handshake and before sending anything.
- The DM approves each joiner (display name + IP); an optional session password is a second check.
- Cost: Python's `ssl` cannot create certificates, so this adds the `cryptography` dependency
  (wheels exist for all three targets; adds several MB per binary; touches all three `.spec`
  files). Not yet tested inside a PyInstaller build.

## 6. Features

- **Chat:** messages, join/leave notices, DMs, `/roll`, `[[category:Name]]` links.
- **Send a character:** flush pending edits, snapshot sheet + spell list, compute the homebrew
  closure (unofficial classes, subclasses, feats, lineage, background, spells, equipment, magic
  items referenced by fields or `[[links]]`) and bundle it with `content_io.bundle_of`. Send an
  offer (metadata + summary), receiver accepts, payload lands in an Inbox, nothing is applied
  until the user confirms.
- **Send other objects:** homebrew objects use the same envelope via one generic "Send..." picker.
- **Receiving is always explicit:** preview + per-item conflict choice (replace / keep both,
  renamed / skip), results via `ImportReport`. Official content stays protected.

## 7. Security

| Risk | Mitigation |
|---|---|
| Unauthorized joiner | Invite code + DM approval + optional password; listen only while a session runs; off by default. |
| Impersonating the host | Certificate fingerprint pinning. |
| Eavesdropping | TLS. |
| Memory / DoS | Frame caps (~16 KB chat, ~4 MB objects), per-peer rate limits, drop on protocol violation. |
| Malicious payload | JSON only (never pickle); existing `from_dict` / `content_io` validation; text shown in text widgets. |
| Data loss | Inbox + explicit accept + conflict preview. |
| Name spoofing | Host assigns and de-duplicates display names; peers get random ids. |

## 8. OS and packaging

- Windows: Defender Firewall prompt on first listen (rule keyed to the exe path; the portable
  build re-prompts if moved).
- macOS: ad-hoc signed, not notarized, so expect an incoming-connections prompt; newer macOS also
  has a Local Network permission. Add the relevant `NSLocalNetworkUsageDescription` key to the
  `info_plist` in `Spellbook-mac.spec` and test on a real Mac (not yet verified).
- Antivirus: the updater documents past AV flags. Keep networking user-initiated and off at startup.
- New settings must be added to `known_fields` in `settings.py` or they are silently dropped.

## 9. Initiative tracker

### 9.1 Principles

- One `SessionService` owns the connection and combat state. The tracker also works with no
  network (the DM is a host with zero players), so it can ship before LAN is finished.
- Three pure-code pieces with no widgets: **state**, a **reducer** `apply(state, actor, command)`
  that holds every rule including authorization, and a **projection** `project(state, viewer)`.
  The DM's local UI and remote players use the same reducer.
- The host filters secrets before sending. A player's client never receives hidden entries,
  hidden HP or hidden AC.
- Wire: clients send commands; the host replies with the full projected state and a revision
  number (about 30 rows is a few KB, so no deltas). Clients wait for the host rather than
  updating optimistically.

### 9.2 Requirements mapped

| Requirement | How |
|---|---|
| Table: name, HP, AC, conditions | Custom row widgets (not `ttk.Treeview`: it cannot span a row, draw health bars or follow the theme). |
| HP/AC/name fetched from sheet or monster | Copied at add time. Sheet: `hit_points`, `armor_class`, `get_initiative()`. Monster: `hp`, `ac`, `get_initiative()`, `hit_dice` for optional HP rolls; summons use `hp_text` / `ac_text`. |
| Changes do not touch the base object | Entries hold copies and never write back; a regression test asserts the sources are unchanged. "Re-sync from sheet" is explicit and one-way. |
| DM adds/removes players and monsters | One "Add combatant" dialog: connected players' characters, the DM's own sheets, the Monsters collection (incl. summons), custom, event. Quantity, auto-numbering, "add hidden", "group together". |
| DM sets initiative order | Initiative number per entry, Roll (d20 + bonus), Sort, drag/arrow reorder. |
| Next turn rotates the table | Stored order + pointer; the display rotates so the active unit is on top and the previous unit goes to the bottom. Round counter increments when the pointer wraps. |
| Group creatures | A group is a block of adjacent entries with a shared id; Next turn moves the whole block. |
| Players edit own HP/AC/conditions | Reducer allows a player to change only entries they own and only those fields. HP accepts relative changes (-7, +4) as well as absolute. |
| Resizable always-on-top pop-up | See 9.5. |
| DM settings: hide monster HP, hide AC, HP as bar | Applied in the projection; bar mode sends only a rounded fraction. |
| Custom monsters | Entry kind `custom`: name, HP, AC, initiative bonus. |
| Events | Entry kind `event`: name only, one label spanning all columns, has an initiative position. |
| Hide entries | `hidden` flag, settable at add time and toggled any time. A hidden player entry is still sent to its owner with a "Hidden" badge. |

### 9.3 Turn mechanics

- A "unit" is one entry, one group or one event.
- Mid-combat add: slot in by initiative and adjust the pointer so the active creature does not
  change. Removing the active entry advances to the next unit.
- A short snapshot history gives "Previous turn" and undo.
- Optional "skip defeated" flag (auto-set when a monster hits 0 HP; players at 0 are not skipped).

### 9.4 Visibility (all in the projection)

- Hidden entries are never sent, except a hidden player's own entry to that player.
- Group labels count only visible members. DM-private notes are never sent.
- If the active creature is hidden, players see the next visible entry on top with no "active"
  highlight.
- DM switches: monster HP (number / bar / hidden), AC shown/hidden, other players' HP. Optional
  per-entry reveal.

### 9.5 Pop-up window

- Separate top-level with no `transient()` (a transient window hides when its owner minimizes).
- `attributes("-topmost")` applied after CTk's delayed init (the icon patch uses 260 ms / 600 ms).
  Never steal focus on state updates.
- Resizable with minimum size, flexible Name column, compact mode; size and position saved and
  clamped to the screen on restore. Pin toggle, opacity slider, "your turn" highlight and optional
  beep.
- Role-based colors make it theme-aware (the Restyler walks top-levels).
- Caveat: macOS topmost behaviour with other apps' full-screen spaces is unverified and needs a
  real Mac test early. Neither platform overlays exclusive-fullscreen games.
- The row table uses reused CTk frames keyed by entry id; if resize performance with ~30 rows is
  poor, switch to a single canvas-drawn table.

### 9.6 Integration

- Enable the "Game Tools" card in `ui/home_view.py` and add `game_tools` and `session` page kinds
  (`_build_page`, `_open_from_home`, `_page_title`, `_restore_tab` in `ui/main_window.py`).
- New `conditions.py` (2024 conditions, Exhaustion 1-6, free-text customs).
- Autosave combat state to `initiative_state.json` via `atomic_io`; offer to resume.
- Stable per-install player id so a reconnecting player reclaims their entry.
- Authorization in the reducer: validate types and ranges, cap entry count, name length and
  conditions per entry.

### 9.7 Assumptions (change if wrong)

1. "Hide AC" applies to monsters, custom creatures and NPCs, not players.
2. Players see each other's HP by default; the DM can switch to bar or hidden.
3. A player shares only a combat snapshot (name, HP, AC, initiative bonus).
4. No write-back to sheets.
5. Active hidden creature: players see the next visible entry on top.
6. Players can add themselves; the DM can switch that off.

## 10. Phases

LAN base:

| Phase | Scope | Days |
|---|---|---|
| 0 | Prerequisites: headless `character_io`, `content_io` dry-run / conflict preview, `SPELLBOOK_DATA_DIR` override | 1-2 |
| 1 | Transport + TLS: framing, handshake, auth, presence, chat, keepalive, loopback tests | 3-5 |
| 2 | Session UI: Host/Join dialogs, Session page, chat, status chip, settings, shutdown hook | 2-3 |
| 3 | Object transfer: offer/accept, Inbox, homebrew closure, conflict UI, Send... entry points | 3-4 |
| 4 | Polish: reconnect, firewall/Mac guidance, plist, README, release-workflow check | 1-2 |
| 5 | Dice, chat links; discovery later | 1-2 each |

Tracker:

| Phase | Scope | Days |
|---|---|---|
| T0 | State, reducer, projection, persistence, tests | 3-4 |
| T1 | Sheet / monster / custom snapshots, conditions | 1-2 |
| T2 | DM table UI, add dialog, HP popover, conditions picker, group/hide/reorder, Game Tools page (local) | 5-7 |
| T3 | Player view, pop-up window, geometry, macOS/Windows checks | 3-4 |
| T4 | Tracker messages on the session, authorization, reconnect, "your turn" alert | 2-3 |
| T5 | DM settings, per-entry reveal, undo/previous turn, polish | 2-3 |

Suggested order: Phase 0, tracker core + DM UI (local), transport + chat, tracker over the network
with player view and pop-up, object sending, then dice / links / polish.

## 11. Testing

- Protocol: framing, fuzzed and oversized frames, bad versions, auth failure, 3-peer loopback
  session with TLS.
- Reducer: rotation, rounds, groups, mid-combat insert/delete.
- Leak test: for random states and every viewer, search the serialized projection for hidden names
  and values.
- Decoupling test: edit tracker HP, assert source sheet and monster are untouched.
- Closure + conflict tests against `content_io`.
- UI smoke test (headless approach), including asserting the pop-up reports topmost.
- Manual matrix: Windows + Windows, Windows + Mac, a VPN case, pop-up over another app.

## 12. Risks

1. Tk threading bugs (queue rule, applied without exception).
2. Version skew in official content (send app + schema version in `hello`, warn on mismatch).
3. Firewall / permission / antivirus friction, plus `cryptography` packaging.
4. CTk table performance and macOS topmost (test early).
5. Information leaks (projection design + leak test).
6. Scope creep into live shared editing of sheets: out of scope.
