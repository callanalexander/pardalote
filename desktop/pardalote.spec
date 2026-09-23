# PyInstaller spec for the pardalote desktop app.
# Build from the desktop/ folder:  pyinstaller pardalote.spec --noconfirm
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas, binaries, hiddenimports = [], [], []

# Packages that load data files or submodules lazily at runtime.
for pkg in ("umap", "pynndescent", "hdbscan", "librosa", "soundfile", "sounddevice"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("sklearn")

icon = "pardalote.ico" if os.path.exists("pardalote.ico") else None

a = Analysis(
    ["launch_pardalote.py"],
    pathex=["."],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports + ["pardalote_app"],
    excludes=["IPython", "jupyter", "notebook", "jupyterlab", "pytest"],
    # numba caches compiled functions next to their source, so ship the .py
    # files as well as the bytecode for the packages that use it.
    module_collection_mode={"umap": "pyz+py", "pynndescent": "pyz+py",
                            "librosa": "pyz+py", "hdbscan": "pyz+py"},
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pardalote",
          console=False, icon=icon, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="pardalote", upx=False)
