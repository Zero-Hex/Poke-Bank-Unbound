# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["launcher.py"],
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
        "waitress",
        "waitress.runner",
        "webbrowser",
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
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
    [],
    name="UnboundBank",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="hoopa_icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UnboundBank",
)
