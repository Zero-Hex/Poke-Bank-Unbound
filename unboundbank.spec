# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Tree() preserves full directory structure inside _MEIPASS
        ("static",          "static"),
        ("data",            "data"),
        ("Evolution Table.c", "."),
        ("species.h",       "."),
        ("items.h",         "."),
        ("moves.h",         "."),
    ],
    hiddenimports=[
        "flask",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.routing",
        "werkzeug.middleware",
        "werkzeug.middleware.proxy_fix",
        "jinja2",
        "click",
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        "openpyxl.writer.excel",
        "openpyxl.reader.excel",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="UnboundBank",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
