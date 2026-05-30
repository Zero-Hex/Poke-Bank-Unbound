# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for UnboundBank
# Build with:  pyinstaller unboundbank.spec

from pathlib import Path

block_cipher = None

# Collect all static files (frontend dist, JSON data, icons)
static_datas = []
for f in Path("static").rglob("*"):
    if f.is_file():
        static_datas.append((str(f), str(f.parent)))

# data/ folder from PUSE (MIT licensed)
data_datas = []
for f in Path("data").rglob("*"):
    if f.is_file():
        data_datas.append((str(f), str(f.parent)))

# Game source files (WTFPL licensed)
game_source_files = [
    ("Evolution Table.c", "."),
    ("species.h",         "."),
    ("items.h",           "."),
    ("moves.h",           "."),
]

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=static_datas + data_datas + game_source_files,
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
