"""Tooltips and drop-down pop-ups must close when they no longer belong on screen.

They used to linger: on Windows a CTkToplevel handles pending events while it is being built, so the
<Leave> that should close a tooltip ran before the tooltip existed; and nothing closed a pop-up when
the view changed under a still pointer, the window moved, or the app lost focus.
"""

import time

import pytest


@pytest.fixture()
def host(tk_root):
    """A visible window: the root is withdrawn, and widgets in it are never 'viewable'."""
    import customtkinter as ctk
    win = ctk.CTkToplevel(tk_root)
    win.geometry("400x300+50+50")
    # On Windows a new CTkToplevel hides itself for a moment to recolour its title bar and shows
    # itself again from a timer: let that run, or nothing in it counts as on screen yet.
    pump(win, 150)
    win.deiconify()
    pump(win, 50)
    assert win.winfo_viewable()
    yield win
    win.destroy()


def pump(widget, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        widget.update()
        time.sleep(0.01)


def test_popup_window_skips_titlebar_work_and_global_click_handler(tk_root):
    from ui.popup_window import PopupWindow
    before = tk_root.tk.call("bind", "all", "<Button-1>")
    popup = PopupWindow(tk_root)
    try:
        assert popup._deactivate_windows_window_header_manipulation is True
        assert popup.overrideredirect()
        assert popup.state() == "withdrawn"            # the owner shows it when it is ready
        assert tk_root.tk.call("bind", "all", "<Button-1>") == before
    finally:
        popup.destroy()


def test_remove_binding_keeps_the_other_bindings(host):
    from ui.popup_window import remove_binding
    hits = []
    first = host.bind("<Button-1>", lambda e: hits.append("a"), add="+")
    second = host.bind("<Button-1>", lambda e: hits.append("b"), add="+")
    remove_binding(host, "<Button-1>", second)
    script = str(host.tk.call("bind", host._w, "<Button-1>"))
    assert first in script and second not in script
    remove_binding(host, "<Button-1>", first)


def test_tooltip_is_not_shown_once_the_pointer_has_left(host, monkeypatch):
    import customtkinter as ctk
    import ui.tooltip as tooltip
    btn = ctk.CTkButton(host, text="Hover me")
    btn.pack()
    host.update()
    tip = tooltip.HoverTooltip(btn, "Some help")
    monkeypatch.setattr(tooltip, "pointer_over", lambda w: False)
    tip._show()                                         # the delayed show fires after a lost <Leave>
    assert tip._tip is None


def test_tooltip_closes_when_its_widget_is_hidden_without_a_leave(host, monkeypatch):
    import customtkinter as ctk
    import ui.tooltip as tooltip
    import ui.popup_window as popup_window
    btn = ctk.CTkButton(host, text="Hover me")
    btn.pack()
    host.update()
    monkeypatch.setattr(tooltip, "pointer_over", lambda w: True)
    monkeypatch.setattr(popup_window, "pointer_over", lambda w: True)
    tip = tooltip.HoverTooltip(btn, "Some help")
    tip._show()
    assert tip._tip is not None
    pump(host, 300)
    assert tip._tip is not None                         # still hovered: stays
    btn.pack_forget()                                   # e.g. a hotkey switched the view
    pump(host, 500)
    assert tip._tip is None


def test_tooltip_closes_when_the_pointer_moves_off_without_a_leave(host, monkeypatch):
    import customtkinter as ctk
    import ui.tooltip as tooltip
    import ui.popup_window as popup_window
    btn = ctk.CTkButton(host, text="Hover me")
    btn.pack()
    host.update()
    over = [True]
    monkeypatch.setattr(tooltip, "pointer_over", lambda w: over[0])
    monkeypatch.setattr(popup_window, "pointer_over", lambda w: over[0])
    tip = tooltip.HoverTooltip(btn, "Some help")
    tip._show()
    assert tip._tip is not None
    over[0] = False                                     # e.g. Alt+Tab to another program
    pump(host, 500)
    assert tip._tip is None


def test_tab_tooltip_keeps_one_timer_for_several_enters(host):
    from ui.tab_bar import TabWidget
    tab = TabWidget(host, tab_id="t", tab_type="spells", display_text="A very long tab title indeed")
    tab.pack()
    tab.set_width(70)
    host.update()
    assert tab.display_text != tab.full_text
    tab._on_enter()
    first = tab._tooltip_id
    tab._on_enter()                                     # nested widgets: a second <Enter>, no <Leave>
    assert tab._tooltip_id != first
    assert first not in str(host.tk.call("after", "info"))
    tab._on_leave()
    assert tab._tooltip_id is None
    tab.destroy()


def _open_combo(host, monkeypatch):
    from ui.scrollable_combobox import ScrollableComboBox
    import ui.popup_window as popup_window
    monkeypatch.setattr(popup_window, "_app_has_focus", lambda w: True)   # no window manager under test
    combo = ScrollableComboBox(host, values=["One", "Two", "Three"])
    combo.pack(pady=20)
    host.update()
    combo._open_dropdown_menu()
    host.update()
    assert combo._scrollable_popup is not None
    return combo


def test_dropdown_closes_on_a_click_elsewhere_in_the_window(host, monkeypatch):
    import customtkinter as ctk
    other = ctk.CTkButton(host, text="Elsewhere")
    other.pack()
    combo = _open_combo(host, monkeypatch)
    pump(host, 300)
    assert combo._scrollable_popup is not None          # left alone: stays open
    other._canvas.event_generate("<ButtonPress-1>", x=5, y=5)
    host.update()
    assert combo._scrollable_popup is None
    combo.destroy()


def test_dropdown_closes_when_its_box_moves_or_is_hidden(host, monkeypatch):
    combo = _open_combo(host, monkeypatch)
    combo.pack_configure(pady=60)                       # e.g. the page scrolled
    pump(host, 500)
    assert combo._scrollable_popup is None

    combo._open_dropdown_menu()
    host.update()
    assert combo._scrollable_popup is not None
    combo.pack_forget()                                 # e.g. the view changed
    pump(host, 500)
    assert combo._scrollable_popup is None
    combo.destroy()


def test_dropdown_closes_when_the_app_loses_focus(host, monkeypatch):
    import ui.popup_window as popup_window
    combo = _open_combo(host, monkeypatch)
    monkeypatch.setattr(popup_window, "_app_has_focus", lambda w: False)
    pump(host, 700)
    assert combo._scrollable_popup is None
    combo.destroy()
