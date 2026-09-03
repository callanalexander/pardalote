# pardalote

pardalote is a GUI for validating large numbers of acoustic detections. It reads
BirdNET or Perch embeddings, reduces them with UMAP, clusters them with HDBSCAN,
and plots the result. Segments can be played from the plot. Clusters can be
labelled as target species or as noise, noise clusters can be removed, and the
remaining segments re-clustered. Retained segments are exported as audio clips
in folders named by label. 

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.11-blue)
![licence](https://img.shields.io/badge/licence-MIT-green)

## Requirements

- Windows PC (for now). Not tested on Mac or Linux. The notebooks assume Windows paths.
- Python 3.11.
- Audio files.
- Embeddings for those files, from
  [BirdNET-Analyzer](https://github.com/birdnet-team/BirdNET-Analyzer) or
  [Perch](https://github.com/google-research/perch-hoplite).

## Documentation

1. [Install](docs/01_install.md)
2. [Generating embeddings](docs/02_generate_embeddings.md)
3. [Using the GUI](docs/03_using_the_gui.md)
4. [Troubleshooting](docs/04_troubleshooting.md)

## How to get embeddings in the right format?

Pardalote uses embeddings for clustering, and auditions the associated audio file. It expects embeddings in a .txt file, with the same file name as your audio file. 
We have provided test examples in the audio data folder. The easiest way to get embeddings in this format for new users is to use the BirdNET GUI: 

Use the BirdNET-Analyzer GUI.

1. Open the Embeddings tab and select Extract.
2. Set the input to the folder containing your audio.
3. Set a folder and name for the embeddings database.
4. Enable CSV output and set an output folder. Without this the embeddings are
   only written to the hoplite database, which pardalote cannot read.
5. Run

The output is a single CSV containing every 3 second segment in the dataset:
source file, start time, end time, and the embedding vector.

The equivalent command is:

pardalote reads one file per recording, so the CSV must be split. We provide a notebook to split the large BirdNET csv files: Run notebook
`01_birdnet_csv_to_txt.ipynb`, setting the input CSV and an output folder.

For Perch, we have `03_perch_db_to_txt.ipynb` to export from a Perch hoplite database.

## Input format

One `.txt` per recording. Each row is one segment:

```
start_seconds <TAB> end_seconds <TAB> "v1,v2,...,vN"
```

The first folder level below the embeddings root is read as the site name.

## Usage

```bash
conda env create -f environment.yml
conda activate pardalote
jupyter lab
```

Open `pardalote_gui.ipynb`, run the cell, set the audio and embeddings paths,
then Scan, Load, Cluster, Plot.

## Repository contents

```
pardalote/
├── notebooks/
│   ├── 00_check_setup.ipynb                      checks the install
│   ├── 01_birdnet_csv_to_txt.ipynb               BirdNET: split the CSV
│   ├── 02_mirror_embeddings_to_audio_tree.ipynb  optional: correct folder mismatches
│   ├── 03_perch_db_to_txt.ipynb                  Perch: export the database
│   └── pardalote_gui.ipynb                       the GUI
├── docs/
│   ├── 01_install.md
│   ├── 02_generate_embeddings.md
│   ├── 03_using_the_gui.md
│   └── 04_troubleshooting.md
├── src/                                          the same code as .py files
├── environment.yml
├── requirements.txt
└── LICENSE
```

`src/` contains the same code as the notebooks, for reading diffs and for
running as scripts.

## Method

BirdNET and Perch convert a segment of audio into a vector of several hundred to
several thousand values. Segments containing similar sounds have similar
vectors. These vectors are the input to pardalote.

UMAP reduces the vectors to two or three dimensions for plotting, preserving
local structure from the original space.

HDBSCAN identifies dense regions in the reduced space and assigns each a cluster
number. Points not assigned to a cluster are labelled `-1`. The number of
clusters is not specified in advance.

None of these steps use species information. They group segments by acoustic
similarity only. Assigning clusters to species is done by the user.

## Citation

- Kahl, S., Wood, C. M., Eibl, M., & Klinck, H. (2021). BirdNET: A deep learning
  solution for avian diversity monitoring. *Ecological Informatics*, 61, 101236.
  van Merriënboer, B., Dumoulin, V., Hamer, J., Harrell, L., Burns, A., & Denton, T.
  (2025). Perch 2.0: The bittern lesson for bioacoustics. arXiv preprint arXiv:2508.04665.
- McInnes, L., Healy, J., & Melville, J. (2018). UMAP: Uniform Manifold
  Approximation and Projection for Dimension Reduction. *arXiv:1802.03426*.
- Campello, R. J. G. B., Moulavi, D., & Sander, J. (2013). Density-based
  clustering based on hierarchical density estimates. *PAKDD*.
  

## Licence

MIT. See [LICENSE](LICENSE).

## Issues

Report bugs and unclear documentation at [issues](../../issues). Include the
notebook, what was being run, and the full error text.
