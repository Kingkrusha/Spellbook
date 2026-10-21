"""Game calendars (calendar_state.py) and the Calendar page."""

import datetime

import pytest

import calendar_state as cs


def test_gregorian_preset_matches_the_real_calendar():
    c = cs.preset("Gregorian")
    start = datetime.date(1950, 1, 1)
    base = c.to_ordinal(1950, 0, 1)
    for n in range(0, 50 * 365, 13):
        real = start + datetime.timedelta(days=n)
        assert c.from_ordinal(base + n) == (real.year, real.month - 1, real.day)
        assert c.weekday(real.year, real.month - 1, real.day) == real.weekday()


def test_ordinals_round_trip_with_leap_and_outside_days():
    c = cs.preset("Twelve thirties with festivals")
    assert c.year_length(3) == 364 and c.year_length(4) == 365
    for o in range(-3000, 3000, 7):
        assert c.to_ordinal(*c.from_ordinal(o)) == o


def test_days_outside_the_months_have_no_weekday_and_dont_move_it():
    c = cs.CalendarConfig([cs.Month("A", 3), cs.Month("Fest", 1, outside=True), cs.Month("B", 3)],
                          ["X", "Y"])
    assert c.weekday(1, 1, 1) is None
    # A has 3 days: X Y X; B carries on with Y, skipping the festival
    assert [c.weekday(1, 0, d) for d in (1, 2, 3)] == [0, 1, 0]
    assert c.weekday(1, 2, 1) == 1
    assert c.date_text(1, 1, 1) == "Fest, 1"


def test_parse_months():
    months, problems = cs.parse_months("Deepwinter 30\nMidwinter 1 outside\nLeapday 0 outside leap 4\n\nbad line")
    assert [(m.name, m.days, m.outside, m.leap_every) for m in months] == [
        ("Deepwinter", 30, False, 0), ("Midwinter", 1, True, 0), ("Leapday", 0, True, 4)]
    assert len(problems) == 1 and "Line 5" in problems[0]
    cfg = cs.CalendarConfig(months, [])
    assert cs.parse_months(cfg.months_text())[0] == months


def test_advance_moves_the_clock_and_the_automatic_trackers():
    camp = cs.new_campaign("Test", "Simple", year=10)
    camp.minute = 22 * 60
    craft = cs.Tracker("Craft a sword", 2, "days")
    rest = cs.Tracker("Rest", 8, "hours", auto=False)
    camp.trackers += [craft, rest]
    report = camp.advance(3 * 60)                   # 22:00 + 3 hours = 01:00 the next day
    assert (camp.day, camp.time_text()) == (2, "01:00")
    assert craft.progress == pytest.approx(3 / 24) and rest.progress == 0
    report = camp.advance_days(2)
    assert craft.done and report.finished == [craft]
    assert "Finished: Craft a sword" in report.messages(camp.config)
    camp.advance_days(-20)                          # back past the start of the year
    assert (camp.year, camp.month) == (9, 11)
    assert craft.progress == 0


def test_advance_reports_the_events_it_reaches():
    camp = cs.new_campaign("Test", "Simple", year=1)
    camp.events.append(cs.Event("Harvest Feast", 0, 3))           # every year
    camp.events.append(cs.Event("Coronation", 0, 5, year=2))      # once
    report = camp.advance_days(5)
    assert [e.name for _d, e in report.events] == ["Harvest Feast"]
    camp.set_datetime(2, 0, 1)
    report = camp.advance_days(10)
    assert [e.name for _d, e in report.events] == ["Harvest Feast", "Coronation"]


def test_set_datetime_can_count_as_time_passing():
    camp = cs.new_campaign("Test", "Simple")
    t = cs.Tracker("Journey", 10, "days")
    camp.trackers.append(t)
    camp.set_datetime(1, 0, 6)
    assert t.progress == 0
    camp.set_datetime(1, 0, 11, move_trackers=True)
    assert t.progress == pytest.approx(5)


def test_clamp_after_the_calendar_shrinks():
    camp = cs.new_campaign("Test", "Simple")
    camp.set_datetime(1, 11, 30)
    camp.config = cs.CalendarConfig([cs.Month("Only", 10)], [])
    camp.clamp()
    assert (camp.month, camp.day) == (0, 10)


def test_store_saves_and_loads(tmp_path):
    path = str(tmp_path / "calendars.json")
    store = cs.CalendarStore(path)
    camp = store.add(cs.new_campaign("Saved", "Gregorian", year=1492))
    camp.config.year_suffix = "AR"
    camp.events.append(cs.Event("Midsummer", 5, 21, description="Feast"))
    camp.trackers.append(cs.Tracker("Train", 10, auto=False, progress=3))
    camp.advance(90)
    store.save()
    again = cs.CalendarStore(path)
    loaded = again.active
    assert loaded.to_dict() == camp.to_dict()
    assert loaded.date_text().endswith("1492 AR")
    again.remove(loaded.id)
    assert cs.CalendarStore(path).campaigns == []


def test_store_survives_a_damaged_file(tmp_path):
    path = tmp_path / "calendars.json"
    path.write_text("{not json")
    assert cs.CalendarStore(str(path)).campaigns == []


# --------------------------------------------------------------------------- the page


@pytest.fixture()
def fresh_fonts(tk_root):
    """The shared fonts belong to the Tk that first made them (an earlier test module's): make them again."""
    from typography import get_font_manager
    get_font_manager().scope.refresh()

def test_calendar_page(tk_root, fresh_fonts, tmp_path):
    from ui.calendar_view import CalendarView
    store = cs.CalendarStore(str(tmp_path / "calendars.json"))
    view = CalendarView(tk_root, {}, store=store)
    view.pack(fill="both", expand=True)
    tk_root.update()
    assert view.empty.winfo_manager()                      # nothing yet: the "New Calendar" prompt

    camp = store.add(cs.new_campaign("Page", "Simple"))
    camp.trackers.append(cs.Tracker("Brew potion", 1, "days"))
    camp.events.append(cs.Event("Market", 0, 2))
    view.refresh()
    tk_root.update()
    assert view.main.winfo_manager() and not view.empty.winfo_manager()
    assert "Page" in view.campaign_var.get()
    assert view.canvas._cells                              # the month was drawn

    view.advance(1, "days")
    assert camp.day == 2 and camp.trackers[0].done
    assert "Finished: Brew potion" in view.notice_label.cget("text")
    assert "Market" in view.notice_label.cget("text")
    _row, bar, text = view._tracker_rows[0]
    assert bar.get() == pytest.approx(1.0) and "done" in text.cget("text")

    view._step_month(1)
    assert view._view == (1, 1)
    view._go_today()
    assert view._view == (1, 0)
    view._on_select_day((1, 0, 9))
    assert view._selected == (1, 0, 9)
    view._flush_save()
    view.destroy()
    store.save()
    assert cs.CalendarStore(store.path).active.day == 2
