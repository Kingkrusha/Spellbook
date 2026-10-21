"""The Tabletop page: building a map, and the mouse tools on the canvas (move, draw, erase, fog, ping, ruler)."""

import io

import pytest

import tabletop as T


def pump(root, n=6):
    for _ in range(n):
        root.update()


@pytest.fixture
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


@pytest.fixture
def window(tk_root, fresh_fonts):
    import customtkinter as ctk
    win = ctk.CTkToplevel(tk_root)
    win.geometry("1300x820+0+0")
    yield win
    win.destroy()


@pytest.fixture
def page(window, tmp_path, tk_root):
    from ui.tabletop_view import TabletopView
    table = T.Tabletop(str(tmp_path / "tabletop.json"))
    assets = T.AssetStore(str(tmp_path / "assets"), str(tmp_path / "cache"))
    view = TabletopView(window, {}, table=table, assets=assets)
    view.pack(fill="both", expand=True)
    view.wait_window = lambda w: None
    pump(tk_root, 10)
    view.table_ = table
    return view


def with_map(page, tk_root, **kw):
    data = {"name": "Field", "w": 700, "h": 490, "cell": 70}
    data.update(kw)
    page._dispatch({"op": "scene_new", "scene_data": data})
    pump(tk_root, 10)
    page.canvas.fit()
    pump(tk_root)
    return page.backend.view()["scene"]["id"]


def drag(canvas, points, button=1):
    (x, y), rest = points[0], points[1:]
    canvas.event_generate(f"<ButtonPress-{button}>", x=int(x), y=int(y))
    for x, y in rest:
        canvas.event_generate(f"<B{button}-Motion>", x=int(x), y=int(y))
    canvas.event_generate(f"<ButtonRelease-{button}>", x=int(x), y=int(y))


def test_an_empty_page_asks_for_a_map_then_shows_it(page, tk_root):
    texts = [page.canvas.itemcget(i, "text") for i in page.canvas.find_all() if page.canvas.type(i) == "text"]
    assert any("New Map" in t for t in texts)
    with_map(page, tk_root)
    assert page.canvas.find_withtag("base")
    assert page.scene_menu.get() == "Field"


def test_dragging_a_token_moves_it_onto_the_grid(page, tk_root):
    sid = with_map(page, tk_root)
    tid = page._dispatch({"op": "token_add", "token": {"name": "Orc", "x": 105, "y": 105}})["token"]
    pump(tk_root)
    c = page.canvas
    sx, sy = c.to_screen(105, 105)
    tx, ty = c.to_screen(330, 260)
    drag(c, [(sx, sy), ((sx + tx) / 2, (sy + ty) / 2), (tx, ty)])
    pump(tk_root)
    token = T.Tabletop._token_or_fail(page.table_.scene(sid), tid)
    assert (token["x"], token["y"]) == (315, 245)            # the centre of the square it was dropped in
    assert c.selected == tid
    page._undo()
    assert T.Tabletop._token_or_fail(page.table_.scene(sid), tid)["x"] == 105


def test_dragging_empty_space_pans(page, tk_root):
    with_map(page, tk_root)
    c = page.canvas
    vx = c.vx
    drag(c, [(400, 300), (300, 300)])
    assert c.vx == pytest.approx(vx + 100 / c.zoom)


def test_draw_then_erase(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page.set_tool("free")
    a, b, d = c.to_screen(100, 100), c.to_screen(200, 150), c.to_screen(300, 120)
    drag(c, [a, b, d])
    pump(tk_root)
    drawings = page.table_.scene(sid)["drawings"]
    assert len(drawings) == 1 and drawings[0]["kind"] == "free" and drawings[0]["color"] == c.draw_color
    page.set_tool("rect")
    drag(c, [c.to_screen(400, 300), c.to_screen(500, 400)])
    pump(tk_root)
    assert len(page.table_.scene(sid)["drawings"]) == 2
    page.set_tool("erase")
    on_line = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)          # a smoothed line passes through its segments' middles
    drag(c, [on_line, on_line])
    pump(tk_root)
    assert [x["kind"] for x in page.table_.scene(sid)["drawings"]] == ["rect"]


def test_fog_reveal_and_the_ruler(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page.set_tool("fog_reveal")
    drag(c, [c.to_screen(0, 0), c.to_screen(140, 140)])
    pump(tk_root)
    fog = page.table_.scene(sid)["fog"]
    assert fog["on"] and fog["ops"][0]["mode"] == "reveal" and fog["ops"][0]["shape"] == "rect"
    page.set_tool("measure")
    c.event_generate("<ButtonPress-1>", x=int(c.to_screen(35, 35)[0]), y=int(c.to_screen(35, 35)[1]))
    x, y = c.to_screen(35 + 70 * 4, 35 + 70 * 2)
    c.event_generate("<B1-Motion>", x=int(x), y=int(y))
    labels = [c.itemcget(i, "text") for i in c.find_withtag("measure") if c.type(i) == "text"]
    assert labels and labels[0].startswith("20 ft")              # 4 squares across, 2 down: 4 squares
    c.event_generate("<ButtonRelease-1>", x=int(x), y=int(y))
    assert not c.find_withtag("measure")


def test_ping_shows_on_the_map(page, tk_root):
    with_map(page, tk_root)
    c = page.canvas
    page.set_tool("ping")
    x, y = c.to_screen(200, 200)
    c.event_generate("<ButtonPress-1>", x=int(x), y=int(y))
    c.event_generate("<ButtonRelease-1>", x=int(x), y=int(y))
    pump(tk_root)
    assert c.find_withtag("ping")


def test_placing_from_the_library_and_editing_a_token(page, tk_root, tmp_path):
    from PIL import Image
    sid = with_map(page, tk_root)
    pic = tmp_path / "hero.png"
    Image.new("RGBA", (300, 300), (200, 30, 30, 255)).save(pic)
    page._place_file(str(pic), "hero")
    c = page.canvas
    x, y = c.to_screen(250, 250)
    c.event_generate("<ButtonPress-1>", x=int(x), y=int(y))
    pump(tk_root)
    token = page.table_.scene(sid)["tokens"][0]
    assert token["name"] == "Hero" and token["image"] and (token["x"], token["y"]) == (245, 245)
    assert page.assets.path(token["image"])

    from ui.tabletop_view import TokenDialog
    dialog = TokenDialog(page.winfo_toplevel(), token, [("Alice", "cid-a")])
    dialog.hp.insert(0, "9")
    dialog.hp_max.insert(0, "12")
    dialog.cond_vars["Prone"].set(True)
    dialog.other.insert(0, "Hunter's Mark")
    dialog.owner.set("Alice")
    dialog._accept()
    page._dispatch({"op": "token_update", "id": token["id"], "fields": dialog.result})
    token = page.table_.scene(sid)["tokens"][0]
    assert token["hp"] == 9 and token["conditions"] == ["Prone", "Hunter's Mark"]
    assert token["owner"] == "cid-a" and token["kind"] == "pc" and token["image"]
    pump(tk_root)
    assert c.find_withtag(f"t:{token['id']}")


def test_a_player_sees_no_dm_tools_and_no_hidden_tokens(window, tk_root, tmp_path):
    import tabletop_net as N
    from lan.service import CLIENT
    from ui.tabletop_view import TabletopView
    table = T.Tabletop(str(tmp_path / "t.json"))
    sid = table.apply({"op": "scene_new", "scene_data": {"name": "Cave"}})["scene"]
    table.apply({"op": "token_add", "scene": sid, "token": {"name": "Lurker", "hidden": True}})
    table.apply({"op": "token_add", "scene": sid, "token": {"name": "Me", "owner": "me"}})

    class Service:
        role = CLIENT
        active = True

        def add_listener(self, fn):
            pass

        def remove_listener(self, fn):
            pass

    class Remote(N.LocalTable):
        role = "player"

        def view(self):
            return T.project(self.table.scene(self.scene_id), "me", rev=1)

        def on_error(self, fn):
            pass

    remote = Remote(table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    view = TabletopView(window, {}, table=table, service=Service(), remote_backend=lambda: remote)
    view.pack(fill="both", expand=True)
    pump(tk_root, 10)
    assert "fog_reveal" not in view._tool_buttons and not hasattr(view, "side")
    names = {view.canvas.itemcget(i, "text") for i in view.canvas.find_withtag("label")}
    assert "Me" in names and not any("Lurker" in n for n in names)
    view.destroy()


def test_tokens_join_initiative_and_the_active_one_glows(window, tk_root, tmp_path):
    import initiative_state as I
    from tabletop_initiative import InitiativeLink
    from ui.tabletop_view import TabletopView
    table = T.Tabletop(str(tmp_path / "tabletop.json"))
    assets = T.AssetStore(str(tmp_path / "assets"), str(tmp_path / "cache"))
    tracker = I.Tracker()
    link = InitiativeLink(table, tracker)
    page = TabletopView(window, {}, table=table, assets=assets, initiative=lambda: link)
    page.pack(fill="both", expand=True)
    pump(tk_root, 10)
    sid = with_map(page, tk_root)
    orc = page._dispatch({"op": "token_add", "token": {"name": "Orc", "x": 105, "y": 105, "hp": 15,
                                                       "hp_max": 15}})["token"]
    page._dispatch({"op": "token_add", "token": {"name": "Crate", "x": 175, "y": 105, "kind": "prop"}})
    page._add_map_to_initiative()
    assert [e.name for e in tracker.state.entries] == ["Orc"]
    assert not page.canvas.find_withtag("turn")
    page._next_turn()
    pump(tk_root)
    assert page.canvas.find_withtag(f"t:{orc}") and set(page.canvas.find_withtag("turn")) & set(
        page.canvas.find_withtag(f"t:{orc}"))
    tracker.dispatch(I.DM, {"type": "hp_delta", "id": tracker.state.entries[0].id, "delta": -4})
    pump(tk_root)
    assert page.canvas.token(orc)["hp"] == 11
    page._remove_from_initiative(orc)
    pump(tk_root)
    assert tracker.state.entries == [] and not page.canvas.find_withtag("turn")
    link.close()
