"""
pardalote - setup check

Run this cell first. It does not touch your data. It just tells you whether
every package pardalote needs is installed, and whether your speakers work.

If something is missing, the message tells you exactly what to type.
"""

import importlib
import platform
import sys

REQUIRED = [
    ("numpy",        "numpy"),
    ("pandas",       "pandas"),
    ("scipy",        "scipy"),
    ("sklearn",      "scikit-learn"),
    ("matplotlib",   "matplotlib"),
    ("umap",         "umap-learn"),
    ("hdbscan",      "hdbscan"),
    ("librosa",      "librosa"),
    ("soundfile",    "soundfile"),
    ("sounddevice",  "sounddevice"),
    ("psutil",       "psutil"),
    ("tkinter",      "tk"),
]

print("pardalote setup check")
print("=" * 60)
print(f"Python   : {sys.version.split()[0]}  ({platform.python_implementation()})")
print(f"System   : {platform.system()} {platform.release()}")
print(f"Env path : {sys.prefix}")
print("=" * 60)

missing = []
for module_name, install_name in REQUIRED:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "")
        print(f"  OK      {module_name:<12} {version}")
    except Exception as exc:
        missing.append(install_name)
        print(f"  MISSING {module_name:<12} ({type(exc).__name__}: {str(exc)[:60]})")

print("=" * 60)

if missing:
    print("\nSome packages are missing. Close Jupyter, open Anaconda Prompt, then run:\n")
    print("    conda activate pardalote")
    print("    conda install -c conda-forge " + " ".join(missing))
    print("\nThen restart Jupyter and run this cell again.")
else:
    print("\nAll packages are present.")

# ---- Audio output check -------------------------------------------------
# pardalote plays clips through your default sound device. If the list below
# is empty, or playback is silent, see docs/04_troubleshooting.md.
try:
    import sounddevice as sd

    default_out = sd.default.device[1]
    devices = sd.query_devices()
    print("\nSound output devices:")
    for i, d in enumerate(devices):
        if d["max_output_channels"] > 0:
            marker = "  <- default" if i == default_out else ""
            print(f"  [{i}] {d['name']}{marker}")
    if not any(d["max_output_channels"] > 0 for d in devices):
        print("  none found - clip playback will not work on this machine")
except Exception as exc:
    print(f"\nCould not query sound devices: {exc}")

# ---- Free memory --------------------------------------------------------
# UMAP holds roughly 3 copies of your embedding matrix in RAM. As a rule of
# thumb, 100,000 segments x 1024 dimensions needs about 1.2 GB per copy.
try:
    import psutil

    total_gb = psutil.virtual_memory().total / (1024 ** 3)
    avail_gb = psutil.virtual_memory().available / (1024 ** 3)
    print(f"\nRAM: {avail_gb:.1f} GB free of {total_gb:.1f} GB total")
    if avail_gb < 4:
        print("  Less than 4 GB free. Close other programs, or lower")
        print("  'Sample Rate' in the pardalote Data settings tab.")
except Exception:
    pass
