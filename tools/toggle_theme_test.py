from theme import get_theme_manager


def print_color(key):
    tm = get_theme_manager()
    print(f"{key}: {tm.get_current_color(key)}")


if __name__ == "__main":
    tm = get_theme_manager()
    print("Current theme:", tm.current_theme_name)
    print_color('accent_primary')
    print_color('button_normal')
    print_color('pane_sash')
    print('--- cycling presets ---')

    presets = tm.get_available_presets()
    assert presets, "No theme presets available"

    accent_tuples = []
    for preset in presets:
        tm.set_theme(preset)
        tup = tm.get_color('accent_primary')
        print(f"Set theme -> {preset} -> accent_primary = {tup}")
        accent_tuples.append(tup)

    # Assert that there is some variance across presets
    unique_accents = set(accent_tuples)
    assert len(unique_accents) > 1, "All presets share identical accent_primary values"

    print('--- set custom (init dark defaults) ---')
    tm.initialize_custom_with_dark_defaults()
    tm.set_theme('custom')
    c = tm.get_color('accent_primary')
    print(f"Custom accent_primary = {c}")
    # After initializing custom with dark defaults, light and dark entries should match
    assert c[0] == c[1], "Custom theme was not initialized with identical dark defaults"

    # Ensure theme name updated
    assert tm.current_theme_name == 'custom', "Theme name did not switch to 'custom'"

    print('Theme toggle test passed')
