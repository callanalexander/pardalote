# pardalote

A point-and-click tool for sorting through large piles of acoustic detections.

You feed it BirdNET or Perch embeddings, it draws every segment of audio as a
dot on a map, and dots that sound alike land near each other. Click a dot to
hear it. Label the clumps that are your target species, mark the clumps that are
rain or traffic or a chainsaw, throw those away, and cluster again on what is
left. When you are happy, export the clips you kept, sorted into folders.

The point is to skip listening to fifty thousand false positives one at a time.

![status](https://img.shields.io/badge/platform-Windows-blue)
![status](https://img.shields.io/badge/python-3.11-blue)
![status](https://img.shields.io/badge/licence-MIT-green)

---

## Who this is for

Ecologists and bioacousticians who have run a recogniser over a season of audio,
have far more detections than they can validate by hand, and want a faster way
through. **No coding experience is assumed.** The instructions spell out every
step, including installing Python.

Everything runs on your own machine. Nothing is uploaded anywhere.

## What you need before you start

- **A Windows PC.** pardalote is only tested on Windows. It may well run on Mac
  or Linux, but nobody has checked, and the helper notebooks assume Windows-style
  paths.
- **Your audio files**, in a folder you can find.
- **Embeddings for that audio**, from either
  [BirdNET-Analyzer](https://github.com/birdnet-team/BirdNET-Analyzer) or
  [Perch](https://github.com/google-research/perch-hoplite).
  [`docs/02_generate_embeddings.md`](docs/02_generate_embeddings.md) walks you
  through making them if you have not yet.
- **8 GB of RAM minimum.** 16 GB or more if you are working with hundreds of
  thousands of segments.
- **An hour**, the first time, mostly waiting on installers.

## Getting started

Work through these in order. Each one is short.

1. **[Install everything](docs/01_install.md)** - Python, the pardalote
   environment, and the code. Do this once.
2. **[Generate your embeddings](docs/02_generate_embeddings.md)** - running
   BirdNET or Perch over your audio, then converting the output into the format
   pardalote reads.
3. **[Use the GUI](docs/03_using_the_gui.md)** - the actual sorting workflow,
   button by button.
4. **[Troubleshooting](docs/04_troubleshooting.md)** - when something does not
   work. Read this before giving up.

## What is in this repository

```
pardalote/
├── notebooks/
│   ├── 00_check_setup.ipynb                    run first, checks your install
│   ├── 01_birdnet_csv_to_txt.ipynb             BirdNET users: split the big CSV
│   ├── 02_mirror_embeddings_to_audio_tree.ipynb  optional: fix folder mismatches
│   ├── 03_perch_db_to_txt.ipynb                Perch users: export the database
│   └── pardalote_gui.ipynb                     the main tool
├── docs/
│   ├── 01_install.md
│   ├── 02_generate_embeddings.md
│   ├── 03_using_the_gui.md
│   └── 04_troubleshooting.md
├── src/                                        the same code as plain .py files
├── environment.yml                             conda install recipe
├── requirements.txt                            pip install recipe
└── LICENSE
```

You will only ever open the notebooks. The `src/` folder holds the identical
code as plain text, which is useful for reading diffs on GitHub and for anyone
who prefers running scripts.

## The very short version

For anyone who has done this sort of thing before:

```bash
conda env create -f environment.yml
conda activate pardalote
jupyter lab
```

Convert your embeddings to one `.txt` per recording using notebook `01`
(BirdNET) or `03` (Perch), where each row is:

```
start_seconds <TAB> end_seconds <TAB> "v1,v2,...,vN"
```

Arrange them so the first folder level under your embeddings root is the site
name. Then open `pardalote_gui.ipynb`, run the cell, set the two paths, and
press Scan, Load, Cluster, Plot.

## How it works

Under the hood there are three steps.

**Embeddings.** BirdNET and Perch both turn a few seconds of audio into a list
of several hundred to a couple of thousand numbers, a fingerprint of what the
sound is like. Two recordings of the same call have similar fingerprints. Those
fingerprints are the input to pardalote, not the audio itself.

**UMAP.** Those fingerprints have far too many dimensions to plot. UMAP squashes
them down to two or three, trying to keep things that were close together in the
original space close together in the squashed one. That is the map you see.

**HDBSCAN.** This finds the dense clumps in that map and gives each one a number.
Anything not in a clump is labelled noise, cluster `-1`. HDBSCAN does not ask you
how many clusters to expect, which is the right behaviour here, because you do
not know.

None of these steps know anything about birds. They just group sounds that
resemble each other. Deciding which group is your species is your job, and that
is why the tool plays audio at you.

## Citing this

If pardalote contributes to published work, please cite this repository, and
cite BirdNET or Perch for the embeddings, plus UMAP and HDBSCAN:

- **BirdNET**: Kahl, S., Wood, C. M., Eibl, M., & Klinck, H. (2021). BirdNET: A
  deep learning solution for avian diversity monitoring. *Ecological
  Informatics*, 61, 101236.
- **UMAP**: McInnes, L., Healy, J., & Melville, J. (2018). UMAP: Uniform Manifold
  Approximation and Projection for Dimension Reduction. *arXiv:1802.03426*.
- **HDBSCAN**: Campello, R. J. G. B., Moulavi, D., & Sander, J. (2013).
  Density-based clustering based on hierarchical density estimates. *PAKDD*.

## Licence

MIT. See [LICENSE](LICENSE). Use it, change it, publish with it. No warranty:
check your own results.

## Contributing and getting help

Found a bug, or got stuck on a step the docs do not cover? Open an
[issue](../../issues). Include what you were doing, the exact error text, and
which notebook you were in. If the docs were unclear, that is a bug too, and
worth reporting.
