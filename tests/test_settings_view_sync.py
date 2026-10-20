"""The settings page keeps its controls in step with the settings (refresh when shown, and after "Reset to defaults")."""

import time
from types import SimpleNamespace

import pytest


def pump(root, n=10):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


@pytest.fixture()
def view(tk_root, monkeypatch):
    import customtkinter as ctk
    import ui.settings_view as settings_view
    from settings import AppSettings, get_settings_manager

    manager = get_settings_manager()
    saved = manager.settings.to_dict()
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    page = settings_view.SettingsView(frame, manager)
    page.pack(fill="both", expand=True)
    pump(tk_root, 20)
    page.build_all_sections_now()
    pump(tk_root, 10)
    # keep the global theme and fonts out of it
    monkeypatch.setattr(page.theme_manager, "set_theme", lambda key: None)
    monkeypatch.setattr(settings_view, "get_font_manager", lambda: SimpleNamespace(reset=lambda: None))
    monkeypatch.setattr(settings_view.ctk, "set_appearance_mode", lambda mode: None)
    yield page, manager
    manager._settings = AppSettings.from_dict(saved)
    manager.save()
    frame.destroy()


def test_refreshing_copies_every_setting_into_its_control(view):
    page, manager = view
    s = manager.settings
    s.preload_classes = not s.preload_classes
    s.allow_delete_official_spells = not s.allow_delete_official_spells
    s.link_suggest_spells = False                      # the control is the opposite: "disable suggestions"
    s.studio_max_matches = 0                           # no limit
    s.studio_min_words = 7
    s.auto_check_updates = False

    page.refresh_from_settings()

    assert page._preload_classes_var.get() == s.preload_classes
    assert page._allow_delete_official_var.get() == s.allow_delete_official_spells
    assert page._link_disable_spells_var.get() is True
    assert page._studio_max_matches_var.get() == "No limit"
    assert page._studio_min_words_var.get() == "7"
    assert page._auto_check_updates_var.get() is False


def test_resetting_puts_every_control_back_including_the_ones_it_used_to_miss(view):
    page, manager = view
    defaults = type(manager.settings)()
    s = manager.settings
    s.preload_classes = not defaults.preload_classes          # the preload switches were not refreshed by a reset
    s.preload_feats = not defaults.preload_feats
    s.allow_delete_official_spells = not defaults.allow_delete_official_spells
    s.show_comparison_highlights = not defaults.show_comparison_highlights
    page.refresh_from_settings()
    assert page._preload_classes_var.get() != defaults.preload_classes

    page._on_reset_defaults()

    assert page._preload_classes_var.get() == defaults.preload_classes
    assert page._preload_feats_var.get() == defaults.preload_feats
    assert page._allow_delete_official_var.get() == defaults.allow_delete_official_spells
    assert page._comparison_var.get() == defaults.show_comparison_highlights
    assert manager.settings.preload_classes == defaults.preload_classes


def test_refreshing_while_sections_are_still_being_built_only_syncs_the_theme_menu(view, monkeypatch):
    page, _manager = view
    calls = []
    monkeypatch.setattr(page, "_sync_theme_menu", lambda: calls.append("menu"))
    monkeypatch.setattr(page, "_sync_variables_from_settings", lambda: calls.append("variables"))
    page._pending_sections = [object()]
    page.refresh_from_settings()
    assert calls == ["menu"]
    page._pending_sections = []
    page.refresh_from_settings()
    assert calls == ["menu", "variables"]
