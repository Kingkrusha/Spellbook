# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the macOS build of Spellbook.

Produces ``dist/Spellbook.app`` - a self-contained application bundle.

Notes vs. the Windows spec:
  * ``BUNDLE`` wraps the collected files into a real ``.app`` so Finder / the
    Dock treat it as an application.
  * ``upx=False`` - UPX corrupts Mach-O binaries (especially arm64) and is not
    normally installed on macOS anyway.
  * ``icon`` points at ``Spellbook.icns`` when present (build_mac.sh generates it
    from ``Spellbook Icon.png``); PyInstaller falls back gracefully if it's
    missing.
  * User data (spellbook.db, settings.json, characters.json, ...) is created at
    runtime under ~/Library/Application Support/Spellbook - see paths.py. Only
    read-only bundled content ships inside the .app.

Build with:  pyinstaller Spellbook-mac.spec --noconfirm
or just:     ./build_mac.sh
"""

import os

icon_file = "Spellbook.icns" if os.path.exists("Spellbook.icns") else "Spellbook Icon.png"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
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
    [],
    exclude_binaries=True,
    name='Spellbook',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_file],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Spellbook',
)

app = BUNDLE(
    coll,
    name='Spellbook.app',
    icon=icon_file,
    bundle_identifier='net.wasch.spellbook',
    version='1.5.2',
    info_plist={
        'CFBundleName': 'Spellbook',
        'CFBundleDisplayName': 'Spellbook',
        'CFBundleShortVersionString': '1.5.2',
        'CFBundleVersion': '1.5.2',
        'NSHighResolutionCapable': True,
        # App has no menu bar of its own; keep it out of the "Info" LSUIElement
        # bucket so it shows in the Dock normally.
        'LSApplicationCategoryType': 'public.app-category.role-playing-games',
        'LSMinimumSystemVersion': '11.0',
    },
)
