# PyInstaller build recipe — run with:  pyinstaller --noconfirm --clean PurpleCalc.spec
# -*- mode: python ; coding: utf-8 -*-
import os

ROOT = os.path.abspath(SPECPATH)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "purplecalc", "fonts"), os.path.join("purplecalc", "fonts"))],
    hiddenimports=[],
    excludes=["tkinter", "unittest", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PurpleCalc",
    icon=os.path.join(ROOT, "assets", "icon.ico"),
    version=os.path.join(ROOT, "assets", "version_info.txt"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
