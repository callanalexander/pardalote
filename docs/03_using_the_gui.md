# 3. Using the pardalote GUI

This is the actual work. Read it once through before you start, then keep it
open beside you.

---

## Starting up

1. Open **Anaconda Prompt**
2. `conda activate pardalote`
3. `cd "C:\path\to\pardalote"`
4. `jupyter lab`
5. In the file browser: `notebooks` > `pardalote_gui.ipynb`
6. Click the grey code cell, press **Shift + Enter**

A window opens, maximised. It may hide behind your browser: check the taskbar.

**Leave the Anaconda Prompt and the notebook tab open the whole time.** Closing
either one kills the window and takes your unsaved work with it.

---

## The layout

The window has three parts.

**Left sidebar.** Paths, the four main buttons, settings, save and load, export,
and a log at the bottom. Sections with a `▼` next to them collapse if you click
the heading, which is worth doing to make room.

**Middle.** Cluster selection, labelling, and a summary of the currently selected
cluster.

**Right.** Two tabs. **UMAP Plot** is the map. **Audio Samples** shows
spectrogram thumbnails with play buttons for a handful of segments from the
selected cluster.

You can drag the divider between panels to resize them.

---

## Setting your paths

Three boxes at the top of the sidebar. Click the `…` next to each to browse.

**Embeddings.** The folder of `.txt` files. Remember that the first folder level
underneath this becomes your site names, so point it at the parent of your site
folders, not at one site.

**Audio.** The top of your audio tree. Searched recursively, so it can be the
root of everything.

**Autosave.** Optional but recommended. pardalote drops a running
`master_tracking_<timestamp>.csv` here after every meaningful action, recording
every segment, which cluster it landed in, what you labelled it, and whether you
removed it. If something crashes three hours in, this file is what saves you. If
you leave it blank, the file goes into your embeddings folder instead.

Below those are two pattern boxes you will usually leave alone:

- **Embed pattern**: `*.embeddings.txt`. Widen to `*.txt` if your files are named
  differently.
- **Audio ext**: `.wav,.WAV,.mp3,.MP3,.flac,.FLAC`. Add extensions here if you
  work with `.w4v` or `.wac` files.

---

## The four buttons

### 1. Scan

Finds every embedding file, finds every audio file, and pairs them up. Takes
seconds.

Watch the log line it produces:

```
Mapped 4,812/4,850 embedding files to audio
```

The two numbers should be close. If you get `Mapped 0/4,850`, stop. Nothing later
will work. Go to [troubleshooting](04_troubleshooting.md#scan-matched-zero-files).

A modest shortfall is usually fine and just means a few recordings were deleted
or renamed after embedding.

### 2. Load

Reads the actual numbers into memory. Seconds to several minutes depending on
size. The progress bar at the bottom moves.

When it finishes you get a line like:

```
Loaded 284,193 embeddings x 1024 dims from 4,812 files (1.08 GB, 0 failed)
```

Check that `failed` count. A handful is fine. Hundreds means something is wrong
with your file format.

**If the GB figure worries you**, or Load is very slow, drop **Sample Rate** in
the Data settings tab from `1.0` to `0.5` and load again. That keeps a random
half of the segments from each file, which is usually plenty to find your
clusters. `0.1` is not unreasonable on a first exploratory pass.

### 3. Cluster

The slow one. UMAP runs first, then HDBSCAN. Minutes for tens of thousands of
segments, up to an hour or more for hundreds of thousands.

**The window will look frozen. It is not.** Watch the status bar at the bottom,
which keeps updating. Do not click anything, and do not close it.

If you have asked for more than your RAM can take, a warning appears first with
an estimate, offering to let you back out. Take the offer, then either turn on
PCA or lower the sample rate.

When it finishes:

```
Found 23 clusters (18,402 noise, 6.5%)
```

Noise is cluster `-1`: segments that did not fall into any dense clump. Some
noise is normal and healthy. If it is over about 40 percent, see
[tuning](#tuning-the-clustering) below.

### 4. Plot

Draws the map. Seconds. It also happens automatically after clustering, so you
mostly press this after changing a display setting.

---

## Reading the plot

Every dot is one segment of audio, positioned so that segments that sounded alike
to the model sit near each other.

**Click a dot to hear it.** This is the whole point of the tool. Click around a
clump and you will know within half a dozen clicks whether it is your species,
somebody else's, or rain.

Click detection works within about 25 pixels of a dot. If a click plays nothing,
you missed. Press **space** to stop playback at any time.

### The Color dropdown

| Option | Use it for |
|---|---|
| `cluster` | The default. See the clumps HDBSCAN found |
| `site` | Check whether a cluster is really one recorder's quirk |
| `filename` | Check whether a cluster is really one recording |
| `custom_label` | Review the labels you have applied so far |

**Colouring by site is the single most useful diagnostic here.** A tight, clean
cluster that is entirely one site is far more likely to be that unit's electrical
hum than a real biological signal. Get in the habit of flicking to `site` before
you commit to calling a cluster something.

### 2D and 3D

The **Dims** dropdown switches between them. 3D only works if you set UMAP
`n_components` to 3 or more **before** clustering. If you switch to 3D without
that, pardalote offers to bump the setting for you, and you then need to cluster
again.

In 3D, drag to rotate. The tool distinguishes a drag from a click, so rotating
does not set off audio. Your viewing angle survives replots.

3D sometimes separates clusters that overlap in 2D, but it is slower and fiddlier
to click. Start in 2D.

### Pop Out and Save PNG

**Pop Out** opens the plot in its own resizable window, which is worth doing on a
second monitor. Clicking still plays audio there. **Save PNG** writes the current
view to an image file, useful for reports.

### Max Plot Points

Default 10,000. This only limits what is *drawn*, not what is clustered. Above
about 20,000 dots the plot gets sluggish and, more importantly, becomes an
unreadable smear. Leave it.

---

## The sorting workflow

Here is the actual loop.

### Step 1: survey

Click through each cluster in the **Cluster** dropdown. For each one:

- Read the summary panel: how many points, how many sites, how many files
- Press **Show** in the Samples box to get spectrogram thumbnails with play
  buttons
- Click some dots in that region of the plot and listen

You are answering one question per cluster: is this my species, something else
biological, or junk?

### Step 2: label what you want

Select a cluster, type a name in the **Label** box, press **Apply**.

Labels flow through to everything downstream: the export folder names, the
manifest CSV, and the autosaved tracking file. Use names you will still
understand in six months. `powerful_owl_duet` beats `good one`.

### Step 3: mark what you do not want

Select a cluster and tick **Mark for Removal**. It stays visible on the plot,
usually greyed, but is flagged.

**Keep Only** is the inverse and a big time saver: select the one cluster you
care about and it marks every other cluster for removal in a single click.

Nothing is deleted at this point. Marking is reversible: untick the box.

### Step 4: re-cluster

Press **Re-cluster**. Everything marked for removal is dropped, and UMAP and
HDBSCAN run again on what is left.

This is where the real gains are. Once the rain and the traffic are gone, the
remaining variation gets spread across the whole map instead of being squashed
into one corner, and structure that was invisible in round one becomes obvious.
Two or three rounds is typical.

**Undo** steps back one round, up to five rounds deep. It restores the data, the
embeddings and your labels.

### Step 5: mop up the noise, maybe

**Assign Noise** takes every noise point (cluster `-1`) and gives it the label of
its nearest non-noise neighbour in UMAP space.

Use this at the end, when you are otherwise happy, and only if you would rather
over-include than miss things. It will pull in some genuine rubbish. If your
priority is a clean set, leave the noise where it is.

### Step 6: export

**Export Audio + CSV** asks for an output folder, asks whether to include noise,
then writes:

```
export_folder/
├── cluster_00_powerful_owl_duet/
│   ├── site_a__rec_0031__12.0s_15.0s.wav
│   └── ...
├── cluster_03_rain/
├── noise/
└── manifest.csv
```

One `.wav` per segment, cut from the original recording, in a folder per cluster
named with your label. Cutting thousands of clips takes a while: the progress bar
moves, and **Cancel Export** stops it cleanly, keeping what has already been
written.

`manifest.csv` is the important output. One row per segment with its cluster,
label, site, source file, start and end times, UMAP coordinates and iteration
number. That is your audit trail.

**Export Manifest Only** writes the CSV without cutting any audio. Fast, and
often all you need if you are going to work from the original recordings anyway.

---

## Saving and coming back later

**Save** writes three files next to each other:

- `yourname.csv`, the clustered data
- `yourname_state.json`, your labels and removal marks
- `yourname_umap.npz`, the UMAP coordinates

**Load** reads all three back and redraws everything.

One important limitation: **loading does not restore the raw embeddings.** You
get your plot, your clusters and your labels, and you can keep listening,
labelling, exporting and marking. You cannot press **Re-cluster**, because there
is nothing to re-cluster from. To do that, press **Load** (the data button) again
first to bring the embeddings back into memory.

Separately, the autosaved `master_tracking_*.csv` accumulates in the background
with no action from you. It is a complete record across every round, including
what got dropped and why, which the save files do not fully capture.

---

## Tuning the clustering

Defaults are sensible. Change one thing at a time, and only in response to a
specific problem.

### Data tab

| Setting | Default | What it does |
|---|---|---|
| Max Files/Site | 10000 | Caps files loaded per site. Lower it for a quick look |
| Sample Rate | 1.0 | Fraction of segments kept per file. **The main memory lever** |
| Use PCA | off | Squashes dimensions before UMAP. Faster, slightly blurrier |
| PCA Components | 30 | If PCA is on. 30 to 50 is the usual range |
| Max Plot Points | 10000 | Display only |
| Click to play | on | Turn off if you keep triggering audio by accident |
| Play pad (s) | 0.0 | Adds context either side of a clip. Try 0.5 if clips feel clipped |
| Load seed | 42 | Keeps subsampling reproducible. Leave it |

### UMAP tab

| Setting | Default | What it does |
|---|---|---|
| `n_neighbors` | 15 | Low values chase local detail and give many small clusters. High values give broad structure and fewer, larger ones. Try 5 or 50 |
| `min_dist` | 0.1 | How tightly points pack. Lower means tighter clumps, easier to see and click |
| `metric` | euclidean | `cosine` is worth a try for audio embeddings |
| `spread` | 1.0 | Overall scale. Usually leave it |
| `n_components` | 2 | Dimensions used for **clustering**. Set 3 to enable the 3D plot. Higher can cluster better while plotting the first two dimensions |
| Deterministic | on | Same input gives the same map every time, at the cost of running on one core. Keep it on for anything you will publish |

### HDBSCAN tab

| Setting | Default | What it does |
|---|---|---|
| `min_cluster_size` | 50 | Smallest group that counts as a cluster. **The most useful dial.** Raise it if you are drowning in tiny clusters, lower it if a rare call is being swallowed as noise |
| `min_samples` | 10 | How conservative it is. Higher means more points called noise |
| `epsilon` | 0.0 | Raise slightly to merge clusters that sit right next to each other |
| `metric` | euclidean | Leave it |
| `selection` | eom | `eom` gives fewer, larger clusters. `leaf` gives many small, fine grained ones |

### Common situations

**Too much noise (over 40 percent).** Lower `min_samples` to 5, or lower
`min_cluster_size`. If it persists, your embeddings may genuinely lack structure,
which happens with very heterogeneous soundscapes.

**One giant cluster holding everything.** Raise `n_neighbors`, or lower
`min_dist` to 0.0 to tighten the packing, or switch `selection` to `leaf`.

**Hundreds of tiny clusters.** Raise `min_cluster_size` to 100 or 200, and switch
`selection` to `eom` if it is not already.

**Your target species is split across several clusters.** That is often correct
behaviour: different call types, different distances, different background. Label
them all with the same name. Labels are not required to be unique.

**It runs out of memory.** Lower Sample Rate first. Turn on PCA second. Both
together will get almost any dataset through on a normal laptop.

---

## Habits worth having

- **Set an autosave folder before you start.** Three hours of labelling is a lot
  to lose.
- **Do a fast pass first.** Sample Rate 0.1, cluster, look. You learn the shape of
  your data in five minutes instead of an hour, and you find out early if your
  settings are wrong.
- **Colour by site before trusting any cluster.**
- **Listen before you label.** The spectrogram thumbnails are quick to skim but
  they are not enough on their own.
- **Export the manifest even when you do not need the clips.** It costs seconds
  and it is your record of what you did.
- **Re-cluster more than once.** The second round is usually where it gets good.

Stuck? **[Troubleshooting](04_troubleshooting.md)**.
