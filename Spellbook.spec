# -*- mode: python ; coding: utf-8 -*-


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
        ('tools', 'tools'),
        ('Spellbook Icon.png', '.'),
    ],
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
    icon=['Spellbook Icon.png'],
)
