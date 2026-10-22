# -*- mode: python ; coding: utf-8 -*-

import os

# Official-content JSON that ships only when present (e.g. magic_items.json
# doesn't exist until that data is added). Missing files are simply skipped so
# the build never breaks on one that isn't ready yet.
_optional_content = [
    (f, '.') for f in ('magic_items.json', 'monsters.json', 'rules.json', 'random_tables.json', 'legacy_2014.json')
    if os.path.exists(os.path.join(SPECPATH, f))
]


# LAN sessions. Most of these are imported lazily (inside functions, so the user can run the app
# without ever hosting); naming them here guarantees they are bundled. The `cryptography` package
# makes the per-session TLS certificate (lan/security.py).
_LAN_IMPORTS = [
    'lan', 'lan.protocol', 'lan.security', 'lan.runtime', 'lan.host', 'lan.client', 'lan.service',
    'lan.discovery', 'lan.dice', 'lan.web', 'lan.qr', 'transfer', 'character_io',
    'ui.session_view', 'ui.session_widgets', 'ui.chat_overlay', 'ui.chat_input', 'ui.chat_render',
    'ui.transfer_dialogs', 'ui.game_tools_view',
    'initiative_state', 'initiative_rows', 'initiative_sources', 'conditions', 'tracker_hub',
    'tracker_net', 'ui.initiative_table', 'ui.initiative_dialogs', 'ui.initiative_view',
    'ui.initiative_window',
    'dice_analyzer', 'character_rolls', 'character_context', 'character_rules', 'roll_rules', 'item_effects', 'roll_effects', 'matchup', 'spell_grants', 'spell_access', 'spell_grant_data', 'ui.roll_effects_editor', 'ui.matchup_view', 'ui.add_spells_dialog', 'ui.granted_spells_dialog', 'ui.dice_analyzer_view', 'ui.distribution_chart', 'ui.bar_list_chart', 'homebrew_index', 'monster_cr', 'studio_store', 'studio_service', 'ui.editor_host', 'ui.studio_view', 'ui.studio_panels', 'ui.studio_insights', 'ui.studio_text', 'ui.studio_launch', 'ui.feature_sections', 'ui.collapsible', 'ui.menu_button', 'ui.monster_features', 'monster_rules', 'sheet_stats',
    'search_index', 'hotkeys', 'ui.hotkey_actions', 'ui.hotkey_editor', 'random_tables', 'ui.random_tables_view', 'calendar_state', 'ui.calendar_view', 'content_images', 'ui.content_image', 'ui.image_packs_panel', 'backup', 'ui.backup_dialogs', 'pdf_library', 'ui.pdf_library_view', 'pdf_export', 'tabletop', 'tabletop_net', 'tabletop_initiative', 'ui.tabletop_canvas', 'ui.tabletop_view',
    'cryptography', 'cryptography.x509', 'cryptography.hazmat.primitives.asymmetric.ec',
    'cryptography.hazmat.primitives.serialization', 'cryptography.hazmat.primitives.hashes',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Bundled data files for initial migration (official content JSON files).
    # User data files (characters.json, settings.json, etc.) are created at runtime.
    # spellbook.db is created at runtime from bundled JSON + tools/spell_data.py.
    datas=[
        ('lineages.json', '.'),
        ('feats.json', '.'),
        ('classes.json', '.'),
        ('backgrounds.json', '.'),
        ('equipment.json', '.'),
        ('tools', 'tools'),
        ('lan/web', 'lan/web'),          # the page browser players open (lan/web.py)
        ('Spellbook Icon.png', '.'),
        ('Spellbook Icon.ico', '.'),
    ] + _optional_content,
    hiddenimports=['tools', 'tools.update_spell_descriptions', 'tools.spell_data', 'tools.stat_block_data',
                      'rules', 'ui.rules_view', 'ui.rule_text']
                  + _LAN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Spellbook',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Spellbook Icon.ico'],
)
