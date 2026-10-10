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

# Single source of truth for the version string - keep the .app bundle metadata
# in sync with version.py. Read it rather than importing so PyInstaller's working
# directory doesn't matter (SPECPATH is injected into spec files by PyInstaller).
_version_ns = {}
with open(os.path.join(SPECPATH, "version.py"), encoding="utf-8") as _vf:
    exec(_vf.read(), _version_ns)
APP_VERSION = _version_ns["__version__"]

# LAN sessions. Most of these are imported lazily (inside functions, so the user can run the app
# without ever hosting); naming them here guarantees they are bundled. The `cryptography` package
# makes the per-session TLS certificate (lan/security.py).
_LAN_IMPORTS = [
    'lan', 'lan.protocol', 'lan.security', 'lan.runtime', 'lan.host', 'lan.client', 'lan.service',
    'lan.discovery', 'lan.dice', 'transfer', 'character_io',
    'ui.session_view', 'ui.session_widgets', 'ui.chat_overlay', 'ui.chat_input', 'ui.chat_render',
    'ui.transfer_dialogs', 'ui.game_tools_view',
    'cryptography', 'cryptography.x509', 'cryptography.hazmat.primitives.asymmetric.ec',
    'cryptography.hazmat.primitives.serialization', 'cryptography.hazmat.primitives.hashes',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('lineages.json', '.'),
        ('feats.json', '.'),
        ('classes.json', '.'),
        ('backgrounds.json', '.'),
        ('equipment.json', '.'),
        ('tools', 'tools'),
        ('Spellbook Icon.png', '.'),
    ] + [
        (f, '.') for f in ('magic_items.json', 'monsters.json', 'legacy_2014.json')
        if os.path.exists(os.path.join(SPECPATH, f))
    ],
    hiddenimports=['tools', 'tools.update_spell_descriptions', 'tools.spell_data', 'tools.stat_block_data']
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
    version=APP_VERSION,
    info_plist={
        'CFBundleName': 'Spellbook',
        'CFBundleDisplayName': 'Spellbook',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'NSHighResolutionCapable': True,
        # App has no menu bar of its own; keep it out of the "Info" LSUIElement
        # bucket so it shows in the Dock normally.
        'LSApplicationCategoryType': 'public.app-category.role-playing-games',
        'LSMinimumSystemVersion': '11.0',
        # Shown by macOS the first time Spellbook talks to other computers on the local network
        # (hosting or joining a LAN session). Without it, newer macOS versions refuse silently.
        'NSLocalNetworkUsageDescription':
            'Spellbook uses your local network to host or join a game session with other players.',
    },
)
