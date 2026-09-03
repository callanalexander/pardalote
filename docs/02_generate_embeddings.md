# 2. Generating your embeddings

pardalote does not read audio directly. It reads **embeddings**: numerical
fingerprints of short chunks of sound, produced by a pretrained model. This page
covers making them and getting them into the shape pardalote expects.

If you already have embeddings, skip to
[what pardalote expects](#what-pardalote-expects) and check yours match.

---

## What an embedding is, briefly

Feed BirdNET three seconds of audio and, as well as its species guesses, it can
hand back a list of numbers describing what that audio sounded like to the model.
BirdNET gives you 1,024 numbers per segment. Perch v2 gives 1,536.

The numbers themselves mean nothing on their own. What matters is that two
segments containing the same call end up with similar lists, and a segment of
rain ends up with a very different list. That similarity is what pardalote
clusters on.

The upshot: **you do not need a recogniser that already knows your species.**
Embeddings work for anything with a consistent acoustic signature, including
species neither model was trained on, and including frogs, bats and machinery.

---

## Choosing BirdNET or Perch

| | BirdNET | Perch v2 |
|---|---|---|
| Easiest to install | Yes, has a GUI | No, notebook and pip based |
| Window length | 3 seconds | 5 seconds |
| Embedding size | 1,024 | 1,536 |
| Output | One big CSV, or a database | A database |
| Extra conversion step | Notebook `01` | Notebook `03` |

If you are unsure, **use BirdNET**. It is much easier to get running, and the
clustering quality is good enough for the great majority of jobs. Perch tends to
separate similar-sounding species a bit more cleanly, which matters if your
target is easily confused with a common congener.

You can also do both and compare, since pardalote reads either.

---

## Route A: BirdNET

### Install BirdNET-Analyzer

Download it from the
[releases page](https://github.com/birdnet-team/BirdNET-Analyzer/releases). The
Windows installer is the simplest option, and gives you both a GUI and a command
line tool.

Full documentation lives at
<https://birdnet-team.github.io/BirdNET-Analyzer/>.

### Run the embeddings command

Open Anaconda Prompt (or the BirdNET command line, if you installed it that way)
and run:

```
python -m birdnet_analyzer.embeddings ^
    -i "D:\path\to\your\audio" ^
    -db "D:\path\to\output\embed_db" ^
    --file_output "D:\path\to\output\embed"
```

The `^` characters let one command span several lines in Windows. You can also
just type it all on one line and drop them.

What the flags mean:

| Flag | What it does |
|---|---|
| `-i` | The folder holding your audio. Searched recursively |
| `-db` | A folder for BirdNET's own database. Required, even though you will not use it |
| `--file_output` | Where the CSV goes. **This is the one you need** |
| `--overlap` | Segment overlap in seconds, 0 to 2.9. Default 0 |
| `--fmin` / `--fmax` | Bandpass limits in Hz. Defaults 0 and 15000 |
| `-b` | Batch size, default 8. Raise it if you have plenty of RAM and want more speed |
| `--threads` / `--n_workers` | How many CPU cores to use |

Expect roughly real time to a few times faster than real time on a normal
laptop, so a week of continuous recording takes hours, not minutes. Start it and
go and do something else.

### Convert the CSV

BirdNET writes **one enormous CSV** covering every recording. pardalote needs one
file per recording. That is what notebook
[`01_birdnet_csv_to_txt.ipynb`](../notebooks/01_birdnet_csv_to_txt.ipynb) does.

Open it in JupyterLab, set the three paths at the top of the cell, and run it.
The notebook explains each setting, and there are worked examples for the fiddly
one (`BASE_PATH`).

### If your folders do not line up

Sometimes the audio you ran BirdNET over is not organised the same way as the
audio you want to work with. The classic case: you embedded audio sorted into
confidence "bin" folders, but your validated working copy is sorted by site.

Notebook
[`02_mirror_embeddings_to_audio_tree.ipynb`](../notebooks/02_mirror_embeddings_to_audio_tree.ipynb)
fixes that. It matches on filename only, ignores the source folders entirely, and
copies each embedding into a mirror of your audio tree.

Run it once with `DRY_RUN = True` to see the counts, then again with
`DRY_RUN = False` to actually copy. It writes a full log to
`birdnet_embed_transfer_log.csv` so you can check the matches in Excel.

If your embedding folders already mirror your audio folders, skip this notebook.

---

## Route B: Perch

### Install perch-hoplite

```
conda create -n perch python=3.11
conda activate perch
pip install perch-hoplite
```

Note this is a **separate environment** from `pardalote`. Perch pulls in
TensorFlow or JAX, which are large and fussy, and keeping them apart avoids
version fights.

The project lives at <https://github.com/google-research/perch-hoplite>.
Windows support is not officially documented, so if the install fights you,
[Google Colab](https://colab.research.google.com/) is a reasonable fallback for
the embedding step.

### Embed your audio

Perch's workflow runs through its own notebooks, not a command line tool. Open
`perch_hoplite/agile/01_embed_audio.ipynb` from the perch-hoplite repository,
point it at your audio folder, choose the Perch v2 model, and run it.

It writes a **database folder**, not files. Note down where that folder is.

### Export the database to text

Open [`03_perch_db_to_txt.ipynb`](../notebooks/03_perch_db_to_txt.ipynb) in
JupyterLab, set `DB_DIR`, `AUDIO_ROOT` and `OUT_DIR`, and run it.

This notebook needs `perch_hoplite` importable. Either `pip install
perch-hoplite` into your pardalote environment, or run this one notebook from
your `perch` environment instead. It uses nothing else beyond the standard
library, so either works.

---

## What pardalote expects

However you got here, you should end up with a folder of `.txt` files.

### File format

One file per recording, named after the recording, one row per segment:

```
0.0	3.0	"0.123,-0.456,0.789,..."
3.0	6.0	"0.234,-0.567,0.890,..."
6.0	9.0	"0.345,-0.678,0.901,..."
```

Three tab-separated fields: **start time in seconds**, **end time in seconds**,
and the **embedding vector** as comma-separated numbers. The quotes around the
vector are optional. pardalote also accepts a plain comma-separated variant where
the embedding occupies columns 3 onwards.

Both conversion notebooks produce this automatically, so you do not need to
build it by hand.

### Filenames

The embedding filename must match the audio filename, ignoring the extension.
So `site_a/rec_0031.wav` pairs with `site_a/rec_0031.birdnet.embeddings.txt`.

pardalote is fairly forgiving here. It tries an exact stem match first, then a
normalised match that strips punctuation, case and the known embedding suffixes
(`.birdnet.embeddings`, `.perch.embeddings`, `.embeddings`, `_embeddings`,
`.embed`). Renaming your files to fight the matcher is rarely necessary.

### Folder structure

This is the part people get wrong, so it is worth being explicit.

**pardalote reads the site name from the first folder level under your
embeddings root.**

```
embed_cut/                          <- this is your "Embeddings" path
├── site_a/                         <- becomes site "site_a"
│   ├── rec_0031.birdnet.embeddings.txt
│   └── rec_0032.birdnet.embeddings.txt
├── site_b/                         <- becomes site "site_b"
│   └── rec_0107.birdnet.embeddings.txt
└── site_c/
    └── ...
```

Anything sitting loose in the root, with no folder above it, gets the site name
`unknown`.

Site matters more than it might seem. Colouring the plot by site instead of
cluster is the quickest way to tell a genuine shared call from one recorder's
particular brand of interference. If a tight cluster turns out to be entirely one
site, be suspicious of it.

If you do not have meaningful sites, put everything in one folder, accept that
you get one site, and colour by cluster only. That works fine.

Your audio can be arranged however you like, as long as filenames are unique.
pardalote searches it recursively.

---

## check before moving on

- [ ] You have a folder of `.txt` files with same names and folder structure as your audio
- [ ] Opening one in Notepad shows numbers
- [ ] The filenames resemble your audio filenames
- [ ] There is at least one folder level for site names
- [ ] You know the full path to that folder, and to your audio folder

Next: **[using the GUI](03_using_the_gui.md)**.
