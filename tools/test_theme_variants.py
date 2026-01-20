"""
Minimal smoke test for appearance mode handling.

This script toggles light/dark appearance and ensures ThemeManager.get_current_color
returns the expected variant for a representative color.
"""
import sys
import os
import traceback

# Ensure repo root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import customtkinter as ctk
from theme import get_theme_manager

errors = []

def check_appearance_modes():
    tm = get_theme_manager()
    for mode in ('light', 'dark'):
        try:
            ctk.set_appearance_mode(mode)
            tup = tm.get_color('bg_primary')
            expected = tup[0] if mode == 'light' else tup[1]
            actual = tm.get_current_color('bg_primary')
            ok = (actual == expected)
            print(f"mode={mode}, expected={expected}, actual={actual}, ok={ok}")
            if not ok:
                errors.append(f"Mismatch for mode {mode}: expected {expected} got {actual}")
        except Exception as e:
            errors.append(f"Error checking mode {mode}: {e}")

def import_ui_modules():
    modules = ['ui.settings_view', 'ui.main_window', 'ui.spell_lists_view']
    for m in modules:
        try:
            __import__(m)
            print(f"Imported {m} OK")
        except Exception as e:
            errors.append(f"Import failed for {m}: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    check_appearance_modes()
    import_ui_modules()

    if errors:
        print("\nTEST FAILURES:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    else:
        print("\nALL TESTS PASSED")
        sys.exit(0)
