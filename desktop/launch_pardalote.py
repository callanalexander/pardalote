"""
Entry point for the pardalote desktop app (the .exe).

The GUI code itself lives in notebooks/pardalote_gui.ipynb and is copied into
pardalote_app.py at build time by extract_app.py, so the notebook stays the
single source of truth.

    python launch_pardalote.py              start the app
    python launch_pardalote.py --selftest   headless check used by the build
"""
import multiprocessing
import os
import sys
from pathlib import Path


def _user_dir():
    docs = Path.home() / "Documents"
    d = (docs if docs.is_dir() else Path.home()) / "pardalote"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prepare_environment():
    base = _user_dir()
    # numba (used by UMAP) needs a writable cache folder inside a frozen app,
    # and it must be set before numba is first imported.
    os.environ.setdefault("NUMBA_CACHE_DIR", str(base / "numba_cache"))
    # A windowed .exe has no console, so send stray print() and library output
    # to a file instead of letting writes to a missing stream crash the app.
    if getattr(sys, "frozen", False) or sys.stdout is None:
        (base / "logs").mkdir(parents=True, exist_ok=True)
        stream = open(base / "logs" / "console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = stream


def selftest():
    """Import everything and run each heavy step on tiny data. Exit code 0 = pass."""
    import tempfile
    import time
    import numpy as np
    t0 = time.time()
    import pardalote_app as app                    # tkinter, matplotlib, librosa, sounddevice
    print(f"imports ok ({time.time() - t0:.1f}s)")

    rng = np.random.default_rng(0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # audio decode
        import soundfile as sf
        wav = tmp / "audio" / "siteA" / "rec1.wav"
        wav.parent.mkdir(parents=True)
        sf.write(wav, rng.normal(size=48000).astype("float32") * 0.01, 16000)
        y, sr = app.load_clip(wav, 0.5, 1.0)
        assert sr == 16000 and len(y) == 16000
        print("audio ok")

        # BirdNET split
        csv = tmp / "emb.csv"
        with open(csv, "w") as f:
            f.write("file,start,end,emb\n")
            for i in range(20):
                f.write(f'{wav},{i},{i + 3},"{",".join("0.1" for _ in range(64))}"\n')
        s = app.split_birdnet_csv(csv, tmp / "out")
        assert s["files"] == 1 and s["rows"] == 20, s
        print("birdnet split ok")

    # UMAP in parallel, the part most likely to break when frozen
    x = np.vstack([rng.normal(loc=c, size=(400, 32)) for c in (0, 6, 12)]).astype("float32")
    emb = app.umap.UMAP(n_components=2, n_jobs=-1, low_memory=True).fit_transform(x)
    assert emb.shape == (1200, 2)
    print(f"umap ok ({time.time() - t0:.1f}s)")

    # joblib with all cores, as used inside HDBSCAN and scikit-learn
    from joblib import Parallel, delayed
    assert Parallel(n_jobs=-1)(delayed(pow)(i, 2) for i in range(8)) == [i * i for i in range(8)]
    print("joblib ok")

    # HDBSCAN with the app's own settings, on more than 16,384 points: below
    # that size HDBSCAN never uses its multi-process code path.
    pts = np.vstack([rng.normal(loc=c, size=(7000, 2)) for c in (0, 10, 20)])
    labels = app.hdbscan.HDBSCAN(min_cluster_size=100,
                                 core_dist_n_jobs=app.HDBSCAN_JOBS).fit_predict(pts)
    n = len(set(labels)) - (1 if -1 in labels else 0)
    assert n >= 2, labels
    print(f"hdbscan ok on {len(pts):,} points, {n} clusters, "
          f"core_dist_n_jobs={app.HDBSCAN_JOBS} ({time.time() - t0:.1f}s total)")
    return 0


def main():
    # A windowed .exe (and any helper process it starts) has no console streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    # joblib's "loky" worker processes cannot start inside a PyInstaller .exe
    # (they crash with "not enough values to unpack"). Nothing in pardalote
    # should start them any more, but if something does, exit quietly instead
    # of popping up a crash window. The main window then reports the error.
    if (len(sys.argv) == 3 and sys.argv[1] == "--multiprocessing-fork"
            and "=" not in sys.argv[2]):
        sys.exit(1)
    multiprocessing.freeze_support()
    if getattr(sys, "frozen", False):
        # Make any joblib parallel work in the .exe use threads, not processes.
        import joblib
        joblib.parallel_config(backend="threading")
    if "--selftest" in sys.argv:
        import tempfile
        os.environ.setdefault("NUMBA_CACHE_DIR", tempfile.mkdtemp(prefix="numba_"))
        if getattr(sys, "frozen", False) and os.name == "nt":   # windowed exe: no console
            sys.stdout = sys.stderr = open("selftest.log", "w", encoding="utf-8", buffering=1)
        try:
            code = selftest()
        except Exception:
            import traceback
            traceback.print_exc()
            code = 1
        sys.stdout.flush()
        os._exit(code)
    _prepare_environment()

    # Show something straight away: the scientific libraries take a while to
    # load, and a double-click that seems to do nothing gets clicked again.
    import tkinter as tk
    root = tk.Tk()
    root.title("pardalote")
    root.geometry("420x120")
    msg = tk.Label(root, font=("TkDefaultFont", 11), justify="center",
                   text="Starting pardalote…\n\nThe first start after installing can take a minute.")
    msg.pack(expand=True, fill="both", padx=20, pady=20)
    root.update()

    import pardalote_app
    msg.destroy()
    pardalote_app.start_gui(root)


if __name__ == "__main__":
    main()
