# -*- mode: python ; coding: utf-8 -*-

import os

# Official-content JSON that ships only when present (e.g. magic_items.json
# doesn't exist until that data is added). Missing files are simply skipped so
# the build never breaks on one that isn't ready yet.
_optional_content = [
    (f, '.') for f in ('magic_items.json',)
    if os.path.exists(os.path.join(SPECPATH, f))
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
        ('Spellbook Icon.png', '.'),
        ('Spellbook Icon.ico', '.'),
    ] + _optional_content,
    hiddenimports=['tools', 'tools.update_spell_descriptions', 'tools.spell_data', 'tools.stat_block_data'],
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
