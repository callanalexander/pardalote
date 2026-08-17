# 4. Troubleshooting

Find your error message below. If it is not here,
[open an issue](../../../issues) with the exact text, which notebook you were in,
and what you had just done.

---

## Installing

### `'conda' is not recognized as an internal or external command`

You are in the ordinary Windows Command Prompt, not Anaconda Prompt. Press the
Windows key, type `Anaconda Prompt`, and use that window instead.

If Anaconda Prompt does not appear in the start menu at all, Miniconda did not
install. Run the installer again, and restart your computer afterwards.

### `conda env create` sits on "Solving environment" forever

It is slow, not stuck, but you can make it much faster:

```
conda install -n base conda-libmamba-solver
conda env create -f environment.yml --solver=libmamba
```

### `EnvironmentFileNotFound: environment.yml file not found`

You are not in the pardalote folder. Check with `dir`, which lists the current
folder. If you do not see `environment.yml` in the output, `cd` to the right
place. Remember that switching drives needs the drive letter on its own first:

```
D:
cd "D:\path\to\pardalote"
```

### `CondaHTTPError` or `SSLError`

A network problem, often a workplace proxy or VPN. Try off the VPN. If your
institution intercepts SSL, ask IT for the certificate bundle and set:

```
conda config --set ssl_verify path\to\cert.pem
```

### The environment built but `conda activate pardalote` fails

Run `conda init` once, close Anaconda Prompt entirely, open a fresh one, and try
again.

### pip install of `hdbscan` fails with pages of compiler errors

You are missing a C++ compiler. Use conda instead, which is why
`environment.yml` exists. If you must use pip, install
[Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
with the "Desktop development with C++" workload ticked, then try again.

---

## Jupyter

### `jupyter: command not found` or `'jupyter' is not recognized`

Your prompt is showing `(base)` rather than `(pardalote)`. Run
`conda activate pardalote` first. This catches everyone at least once.

### Jupyter opens but there is no `pardalote` kernel

Start Jupyter from inside the activated environment and the default `Python 3`
kernel *is* the pardalote one. If you want it registered by name:

```
conda activate pardalote
python -m ipykernel install --user --name pardalote --display-name pardalote
```

### The notebook says `Kernel starting, please wait` and never finishes

Menu: **Kernel** > **Restart Kernel**. If that does not fix it, close Jupyter
(Ctrl+C twice in Anaconda Prompt), and start it again.

### `ModuleNotFoundError: No module named 'umap'`

Either the environment is not active, or that package did not install. Run
notebook `00_check_setup.ipynb`, which tells you exactly which packages are
missing and the command to fix them.

Note the naming trap: the package to install is `umap-learn`, but you import it
as `umap`. Likewise `scikit-learn` imports as `sklearn`.

---

## The GUI window

### The cell ran and printed `starting pardalote` but no window appeared

It is usually behind your browser. Check the taskbar, or press Alt+Tab.

If it truly is not there, `tkinter` may be missing. Run `00_check_setup.ipynb`
and look for the `tkinter` line. Fix with:

```
conda activate pardalote
conda install -c conda-forge tk
```

### The window is enormous, or bits are cut off

pardalote opens maximised and assumes a reasonably sized screen. On a small
laptop display, collapse sidebar sections by clicking their `▼` headings, and
drag the divider between the sidebar and the plot. **Pop Out** puts the plot in
its own window, which helps a lot.

If everything is tiny on a high-DPI screen, right click the Anaconda Prompt
shortcut, choose Properties, then Compatibility, then "Change high DPI settings",
and set scaling override to "System".

### The window went white or "Not Responding" during clustering

Expected. UMAP blocks the interface while it runs. Watch the status bar at the
bottom for progress. Wait it out. Hundreds of thousands of segments can take an
hour.

If it is still frozen long after the status bar last changed, close it, restart
the kernel, and try again with a lower Sample Rate.

### Closing the notebook killed the window

Yes. The window is run by the notebook. Keep the notebook tab and the Anaconda
Prompt open the whole session. This is why the autosave folder matters.

---

## Scanning and loading

### Scan matched zero files

The most common problem in the whole tool. Work through these in order.

**1. Is the embed pattern right?** Default is `*.embeddings.txt`. If your files
are named `rec_0031_embeddings.txt`, or just `rec_0031.txt`, the default will not
match them. Widen it to `*.txt` and scan again.

**2. Are the audio extensions right?** Default covers `.wav`, `.mp3` and `.flac`
in both cases. If you work with `.w4v` or `.wac`, add them, comma separated, no
spaces:

```
.wav,.WAV,.mp3,.MP3,.flac,.FLAC,.wac,.w4v
```

**3. Do the filenames actually correspond?** Open your embeddings folder and your
audio folder side by side. `rec_0031.wav` should have a partner beginning
`rec_0031`. If your embedding files are named after bins, or numbered
sequentially, or all called `embeddings.txt` in different folders, the matcher
has nothing to work with. Rerun the conversion notebook with a `BASE_PATH` that
preserves more of the original structure.

**4. Are the paths pointing where you think?** Pointing "Embeddings" at the
parent of the folder that actually holds the files still works, because the
search is recursive, but pointing it at the wrong drive does not. Check for
typos, and check that a network drive is actually connected.

### Scan matched some files but far fewer than expected

Usually genuine: some recordings were deleted, renamed or moved after embedding.
Check the numbers are plausible before worrying.

If the shortfall is large and your embeddings sit in a different folder layout
from your audio, run notebook
[`02_mirror_embeddings_to_audio_tree.ipynb`](../notebooks/02_mirror_embeddings_to_audio_tree.ipynb).
It matches on filename only and ignores folders, and writes a full log you can
inspect in Excel.

### Load reports lots of failures

Open one of the failing `.txt` files in Notepad. You should see three
tab-separated fields per row: a start time, an end time, then a long list of
comma-separated numbers.

Common causes:

- **The header row was not stripped.** If the first line contains words rather
  than numbers, rerun the conversion notebook, which skips headers.
- **Wrong delimiter.** Commas where tabs should be in the first three fields.
  pardalote handles a pure-comma variant, but not a mixture.
- **Empty files.** Zero bytes means the conversion notebook wrote nothing for that
  recording, usually because it appeared in the CSV with no rows.

### `Loaded 0 embeddings` or `No valid embeddings loaded`

Every file failed to parse. See above. Check one file in Notepad before doing
anything else.

### Load is very slow, or Windows starts swapping

Too much data. In the Data tab, lower **Sample Rate** to `0.5` or `0.2` and load
again. A random subsample finds the same clusters and costs you very little.

---

## Clustering

### `MemoryError`, or the whole computer grinds to a halt

UMAP holds several copies of your matrix at once. Options, in the order worth
trying:

1. Lower **Sample Rate** in the Data tab
2. Turn on **Use PCA** with 30 components
3. Close your browser tabs, which are probably using more RAM than you think
4. Set **Max Files/Site** to cap how much comes in

The memory warning that appears before clustering is a genuine estimate. Believe
it.

### Clustering finished but everything is one cluster

Try, one at a time:

- Raise UMAP `n_neighbors` to 50
- Lower `min_dist` to 0.0
- Set HDBSCAN `selection` to `leaf`
- Raise `min_cluster_size`, which sounds backwards but often splits a blob

If nothing works, your embeddings may genuinely be uniform: a single recorder in
one habitat with one dominant sound can look like this.

### Almost everything is noise

Lower `min_samples` to 5, and lower `min_cluster_size` to 20 or 30. If it is
still mostly noise, you may not have enough data. HDBSCAN needs a reasonable
number of similar segments to call something a cluster.

### The results change every time I run it

Turn on **Deterministic** in the UMAP tab. Off, UMAP runs multi-core and gives a
slightly different map each time. On, it is reproducible but single-core and
slower. For anything you will publish, keep it on.

### 3D is greyed out or falls back to 2D

3D needs UMAP `n_components` set to 3 or more **before** you cluster. Change the
setting, then press **3. Cluster** again. pardalote offers to change it for you,
but the setting alone does nothing until you re-cluster.

---

## Audio

### Clicking a dot plays nothing

**Is "Click to play" ticked?** Data settings tab.

**Did you actually hit a dot?** The click radius is about 25 pixels. Zoom in with
the matplotlib toolbar, or use **Pop Out** for a bigger target.

**Is the audio file still there?** If you moved or renamed recordings after
scanning, the stored paths are stale. Re-scan and re-load.

**Do your speakers work?** Run `00_check_setup.ipynb`, which lists your sound
output devices and flags the default.

### Audio plays but is cut off, or you cannot hear the start of the call

Raise **Play pad (s)** in the Data tab to `0.5` or `1.0`. That adds context either
side of each segment without changing the segment boundaries themselves.

### `PortAudioError` in the log

`sounddevice` cannot reach your audio hardware. Common with Bluetooth headphones
that went to sleep, or with remote desktop sessions, which usually have no audio
device at all. Reconnect the device, then restart the notebook kernel: the audio
library grabs the device once at import.

### Spectrogram thumbnails do not appear

They are skipped silently if the audio cannot be read. The Play button is a good
test: if that fails too, the file is missing or unreadable. Some `.wac` and
`.w4v` files need conversion to `.wav` before librosa will open them.

---

## Exporting

### Export produced folders but the `.wav` files are missing

Check `clip_written` in `manifest.csv`. `False` means the source recording could
not be read at cut time. Usually the audio moved between scanning and exporting.
Re-scan, re-load, re-export.

### Export is very slow

It is cutting and writing one file per segment, so tens of thousands of segments
takes a while. **Cancel Export** stops it cleanly and keeps what is already
written. If you do not actually need the clips, **Export Manifest Only** takes
seconds.

### Cluster folders have odd names

Folders are named `cluster_<number>_<your label>`, with characters Windows
forbids (`\ / : * ? " < > |`) replaced by underscores. Rename your labels if you
want tidier folders, then export again.

---

## Saving and loading

### Load restored my plot but Re-cluster is greyed out or complains

Expected. Saved files contain your plot, clusters and labels, but not the raw
embeddings, which are far too large to save. Press **2. Load** to bring the
embeddings back into memory, and then Re-cluster works.

### Autosave is not writing anything

The autosave folder must exist and be writable. Network drives that have dropped
out are a common culprit. If the box is blank, pardalote writes to your
embeddings folder instead, so check there before assuming it failed. The log
panel reports every autosave, so scroll back and look.

---

## Still stuck

Open an issue with:

1. The exact error text, copied rather than described
2. Which notebook or which button
3. Your operating system and how much RAM
4. Roughly how many embedding files and segments
5. What the first two lines of one of your `.txt` files look like, truncated

The last one solves a surprising proportion of cases on its own.
