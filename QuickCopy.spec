# -*- mode: python ; coding: utf-8 -*-
# QuickCopy PyInstaller spec: single-file, windowed (no console), slimmed.
#
# Slimming strategy (verified against the bundled file list):
#   - Drop Qt modules never used by this pure-Widgets app
#     (Quick / Qml / Pdf / Network / OpenGL / Svg / VirtualKeyboard ...)
#   - Drop opengl32sw.dll (software OpenGL fallback, only needed on machines
#     without any GPU driver) and d3dcompiler (QtQuick D3D backend)
#   - Drop Qt translations (we never install a QTranslator, they are dead weight)
#   - Keep only the qwindows platform plugin; drop imageformat / tls plugins
#     (the app loads no image files and does no networking)
#
# Build with:  pyinstaller --noconfirm --clean QuickCopy.spec

import os

DROP_BIN_NAMES = {
    # software rendering / D3D compiler fallbacks
    "opengl32sw.dll", "d3dcompiler_47.dll", "d3dcompiler_43.dll",
    # unused Qt modules
    "qt6quick.dll", "qt6qml.dll", "qt6qmlmodels.dll", "qt6qmlmeta.dll",
    "qt6quickwidgets.dll", "qt6virtualkeyboard.dll",
    "qt6pdf.dll", "qt6pdfwidgets.dll",
    "qt6network.dll", "qtnetwork.pyd",
    "qt6opengl.dll", "qtopengl.pyd", "qt6openglwidgets.dll",
    "qt6svg.dll", "qtsvg.pyd", "qt6svgwidgets.dll",
    "libcrypto-1_1.dll", "libssl-1_1.dll",
}
KEEP_PLATFORM_PLUGINS = {"qwindows.dll"}  # the only platform backend we need
DROP_DIRS = (
    "/plugins/tls/", "/plugins/imageformats/",
    "/plugins/qmltooling/", "/plugins/designer/",
    "/translations/",
)


def _should_drop(arc_name):
    n = arc_name.replace("\\", "/").lower()
    base = os.path.basename(n)
    if base in DROP_BIN_NAMES:
        return True
    if any(d in n for d in DROP_DIRS):
        return True
    if "/plugins/platforms/" in n and base not in KEEP_PLATFORM_PLUGINS:
        return True
    return False


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # safety net: never imported, keep them out of the module graph
        "PySide6.QtNetwork", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.QtPdf", "PySide6.QtOpenGL", "PySide6.QtSvg",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtMultimedia", "PySide6.Qt3DCore",
    ],
    noarchive=False,
    optimize=0,
)

a.binaries = [b for b in a.binaries if not _should_drop(b[0])]
a.datas = [d for d in a.datas if not _should_drop(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="QuickCopy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # no UPX installed; enable manually if you want extra squeeze
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
