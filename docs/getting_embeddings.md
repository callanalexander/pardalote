# Getting embeddings for pardalote

pardalote does not listen to your audio directly. It clusters **embeddings**: a list
of numbers that a bird sound model (BirdNET or Perch) produces for each few seconds
of audio. Similar sounds get similar numbers, which is what lets pardalote group
them. So before you can use pardalote, you run your recordings through one of
these models once.

If you are not sure which to use, start with BirdNET. It has a point-and-click
program and needs no coding.

---

## Option 1: BirdNET-Analyzer (no coding)

### 1. Install BirdNET-Analyzer

Download the Windows installer from the
[BirdNET-Analyzer releases page](https://github.com/birdnet-team/BirdNET-Analyzer/releases)
and install it like any other program.

### 2. Make the embeddings

1. Open BirdNET-Analyzer and go to the **Embeddings** tab.
2. Choose the folder that holds your recordings as the input.
3. Choose (or create) a folder for the results.
4. Switch on the option to **save the embeddings to a file** and pick **CSV**.
5. Start it, and wait. Large datasets can take a while.

When it finishes you will have one CSV file containing the embeddings for every
recording.

<!-- Screenshot: BirdNET-Analyzer Embeddings tab with the file output option ticked -->

### 3. Load them into pardalote

1. In pardalote, press **Get embeddings…** at the top of the sidebar, then
   **Convert BirdNET CSV…**.
2. Choose the CSV file BirdNET made. The converted files are saved to a new
   folder next to it (you can pick somewhere else if you like).
3. Press **Convert**. When it finishes, the Embeddings and Audio folders are
   filled in for you.
4. Press **1. Scan**, then carry on as normal.

Tip: pardalote uses the first folder level under your recordings folder as the
**site** name, and colours the plot by site. If your recordings are organised
as one folder per site, that carries straight through.

---

## Option 2: Perch (needs Jupyter)

Perch embeddings are made with notebook `03` in the `notebooks` folder of this
repository, which needs a working Python and Jupyter setup (see the main README).

Notebook `03` writes one file per recording, ending `.perch.embeddings.txt`, so
there is nothing to convert. In pardalote, press **Get embeddings…**, then
**Use Perch files**, and choose the folder the notebook wrote to. Set the Audio
folder as usual and press **1. Scan**.

---

## Common problems

**"This file does not look like a BirdNET embeddings CSV"**
You picked BirdNET's detection results rather than the embeddings. Go back to
step 2 and make sure you used the **Embeddings** tab with CSV file output on.

**"This folder has both BirdNET and Perch embeddings"**
BirdNET and Perch embeddings can't be clustered together. Choose one of them in
the **Embed pattern** box and press Scan again.

**Scan finds the embeddings but matches 0 audio files**
Check the Audio folder points at the recordings the embeddings were made from,
and that the file names have not been changed since.

**Still stuck?** Open an issue on
[GitHub](https://github.com/callanalexander/pardalote/issues) and attach the log
(the **Open log folder** button in pardalote takes you straight to it).
