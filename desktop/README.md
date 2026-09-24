# pardalote desktop app (Windows installer)

This folder turns the pardalote GUI into a normal Windows program: a
`pardalote-setup-x.y.z.exe` that installs without admin rights and puts
pardalote in the Start menu and on the desktop. No Python, Anaconda or
Jupyter needed on the user's computer.

The GUI code is **not** duplicated here. `notebooks/pardalote_gui.ipynb` stays
the single source of truth, and `extract_app.py` copies its GUI cell into
`pardalote_app.py` at build time. Edit the notebook, never `pardalote_app.py`.

## Making a release

Everything runs on GitHub's Windows machines via
`.github/workflows/build-windows.yml`.

1. Commit your changes to the notebook.
2. Tag and push, using a plain number for the version:
   ```
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. About 10 to 15 minutes later the installer is attached to a new release on
   the repo's Releases page.

To test a build without making a release, open the **Actions** tab, choose
**Build Windows installer**, press **Run workflow**, and download the
installer from the run's **Artifacts** section.

Each build runs `pardalote.exe --selftest` before packaging (imports, audio
decoding, the BirdNET CSV split, UMAP and HDBSCAN in parallel). If that fails
the build stops, so a broken installer never reaches a release.

## Building on your own Windows PC

```
python -m venv .venv
.venv\Scripts\activate
pip install -r desktop\requirements-build.txt
python desktop\extract_app.py
cd desktop
pyinstaller pardalote.spec --noconfirm
dist\pardalote\pardalote.exe
```

For the installer, install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and run
`"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=1.0.0 pardalote.iss`.

## Files

| File | What it does |
|---|---|
| `launch_pardalote.py` | Entry point: loading window, log redirection, numba cache folder, `--selftest` |
| `extract_app.py` | Copies the GUI cell out of the notebook |
| `pardalote.spec` | PyInstaller build recipe |
| `pardalote.iss` | Inno Setup installer recipe |
| `requirements-build.txt` | Pinned library versions the build was tested with |
| `pardalote.png` | Optional icon. A square PNG, 256x256 or bigger. The build turns it into `pardalote.ico` and uses it for the program, the window, the shortcuts and the installer |

## Things users should know

- **"Windows protected your PC"**: the installer is not code-signed, so
  SmartScreen warns on first run. Click **More info**, then **Run anyway**.
  Signing it (for example with Microsoft's Trusted Signing service) removes this.
- **First start is slow**: the scientific libraries take a minute to load and
  compile the first time. A "Starting pardalote…" window shows while this happens.
- **Settings and logs** live in `Documents\pardalote`. The **Open log folder**
  button in the app goes straight there, which is the thing to attach to a bug report.
