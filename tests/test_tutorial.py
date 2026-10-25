"""The guided tour (ui/tutorial.py, ui/tutorial_steps.py): where its box and shading go, the settings it keeps,
and a run through every step in the real main window, forwards, backwards and skipped half way."""

import time

import pytest


# ---------------------------------------------------------------------------------------------- layout

def test_the_box_goes_below_the_highlight_when_there_is_room():
    from ui.tutorial import callout_position
    x, y = callout_position((300, 100), (100, 100, 200, 50), (0, 0, 1000, 800))
    assert y == 100 + 50 + 14
    assert x == 100 + 100 - 150


def test_the_box_goes_above_when_the_highlight_is_low():
    from ui.tutorial import callout_position
    x, y = callout_position((300, 100), (100, 650, 200, 100), (0, 0, 1000, 800))
    assert y == 650 - 14 - 100


def test_the_box_goes_beside_a_tall_highlight_and_stays_on_screen():
    from ui.tutorial import callout_position
    x, y = callout_position((300, 100), (0, 0, 200, 800), (0, 0, 1000, 800))
    assert x == 200 + 14
    assert 0 <= y <= 800 - 100
    # nothing fits: over the bottom right of the highlight, still inside the window
    x, y = callout_position((300, 100), (0, 0, 1000, 800), (0, 0, 1000, 800))
    assert 0 <= x <= 1000 - 300 and 0 <= y <= 800 - 100


def test_without_a_highlight_the_box_is_centred():
    from ui.tutorial import callout_position
    assert callout_position((200, 100), None, (100, 100, 1000, 800)) == (500, 450)


def test_the_shading_leaves_a_hole_over_the_highlight():
    from ui.tutorial import shade_rects
    top, bottom, left, right = shade_rects((100, 200, 300, 50), (0, 0, 1000, 800))
    assert top == (0, 0, 1000, 200)
    assert bottom == (0, 250, 1000, 550)
    assert left == (0, 200, 100, 50)
    assert right == (400, 200, 600, 50)
    assert shade_rects(None, (5, 6, 7, 8))[0] == (5, 6, 7, 8)


def test_a_highlight_is_clipped_to_the_window():
    from ui.tutorial import clip
    assert clip((-10, -10, 100, 100), (0, 0, 50, 50)) == (0, 0, 50, 50)
    assert clip((60, 60, 10, 10), (0, 0, 50, 50)) is None


# ---------------------------------------------------------------------------------------------- settings

def test_the_tour_settings_are_saved_and_survive_a_reset(tmp_path):
    from settings import AppSettings, SettingsManager
    assert AppSettings().tutorial_offered is False
    data = AppSettings(tutorial_offered=True, tutorial_example_character="X").to_dict()
    loaded = AppSettings.from_dict(data)
    assert loaded.tutorial_offered is True and loaded.tutorial_example_character == "X"

    manager = SettingsManager(str(tmp_path / "settings.json"))
    manager.update(tutorial_offered=True, restore_tabs=False)
    manager.reset_to_defaults()
    assert manager.settings.tutorial_offered is True      # a reset doesn't offer the tour again
    assert manager.settings.restore_tabs is True


def test_f1_starts_the_tour():
    import hotkeys
    assert hotkeys.ACTIONS_BY_ID["help.tour"].default == "F1"


# ---------------------------------------------------------------------------------------------- the real thing

@pytest.fixture
def app(tk_root):
    from settings import get_settings_manager
    from ui.main_window import MainWindow
    settings = get_settings_manager()
    settings.update(tutorial_offered=True, restore_tabs=False)    # no offer window in the tests
    tk_root.geometry("1300x850+0+0")
    tk_root.deiconify()
    window = MainWindow(tk_root)
    window.pack(fill="both", expand=True)
    tk_root.update()
    yield window
    if window._tour is not None and window._tour.running:
        window._tour.end()
    window.destroy()
    tk_root.update()
    tk_root.withdraw()


def _settle(root, tour, timeout=6.0):
    """Run the event loop until the current step has found (or given up on) its widget."""
    end = time.monotonic() + timeout
    root.update()
    while tour._find_job is not None and time.monotonic() < end:
        root.update()
        time.sleep(0.02)
    root.update()


def test_every_step_has_what_it_points_at_and_the_tour_tidies_up(app, tk_root):
    errors = []
    tk_root.report_callback_exception = lambda *exc: errors.append(exc)
    names_before = {c.name for c in app.character_manager.characters}
    tabs_before = app.tab_bar.get_tab_ids()
    shown_before = app._current_tab_id

    app.start_tutorial()
    tour = app._tour
    assert tour.running
    missing = []
    first_sheet_step = [s.title for s in tour.steps].index("A character to look at")
    for i, step in enumerate(tour.steps):
        _settle(tk_root, tour)
        assert tour.index == i
        if step.target is not None:
            # (asked directly rather than read from tour._target: a CI runner's window may never count as
            # on screen, and then the tour rightly shows the step without a highlight)
            widget = step.target()
            try:
                found = widget is not None and bool(widget.winfo_exists())
            except Exception:
                found = False
            if not found:
                missing.append(step.title)
        if i == first_sheet_step:
            # the example character exists while the tour shows the sheet
            example = app._tour_host.example
            assert app.character_manager.get_character(example) is not None
            assert app.settings_manager.settings.tutorial_example_character == example
        tour.next()
    assert not tour.running
    tk_root.update()

    assert missing == []
    assert not errors, errors
    assert {c.name for c in app.character_manager.characters} == names_before
    assert app.settings_manager.settings.tutorial_example_character == ""
    assert app.tab_bar.get_tab_ids() == tabs_before            # the tour's tab is closed again
    assert app._current_tab_id == shown_before


def test_the_builder_step_opens_the_builder_and_leaving_it_closes_it(app, tk_root):
    app.start_tutorial()
    tour = app._tour
    titles = [s.title for s in tour.steps]
    tour._go(titles.index("The Character Builder"))
    _settle(tk_root, tour)
    view = app._tab_views[app._tour_host.tab_id]['view']
    assert view.builder is not None and view.builder.winfo_exists()
    tour.back()
    _settle(tk_root, tour)
    assert view.builder is None                               # the step before shows the list again
    tour.skip()


def test_back_undoes_what_a_step_opened(app, tk_root):
    app.start_tutorial()
    tour = app._tour
    titles = [s.title for s in tour.steps]
    tour._go(titles.index("Select many at once"))
    _settle(tk_root, tour)
    spells = app._tab_views[app._tour_host.tab_id]['sub_view']
    assert spells.spell_list.multi_select
    tour.back()
    _settle(tk_root, tour)
    assert not spells.spell_list.multi_select
    assert spells._advanced_expanded                          # the step before opens the filters...
    tour.back()
    _settle(tk_root, tour)
    assert not spells._advanced_expanded                      # ...and closes them when left
    tour.skip()


def test_skipping_and_closing_the_app_remove_the_example_character(app, tk_root):
    app.start_tutorial()
    tour = app._tour
    tour._go([s.title for s in tour.steps].index("Multiclassing"))
    _settle(tk_root, tour)
    example = app._tour_host.example
    assert app.character_manager.get_character(example) is not None
    tour.skip()
    tk_root.update()
    assert app.character_manager.get_character(example) is None

    # A tour that was running when the app closed: its character is removed at the next start
    from ui.tutorial_steps import remove_leftover_example, TourHost
    host = TourHost(app)
    name = host.example_character()
    assert app.settings_manager.settings.tutorial_example_character == name
    remove_leftover_example(app)
    assert app.character_manager.get_character(name) is None
    assert app.settings_manager.settings.tutorial_example_character == ""
