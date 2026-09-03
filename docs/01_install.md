# 1. Installing pardalote

There are four stages:

1. Install Anaconda or Miniconda, which manages Python and its environments
2. Obtain the pardalote source
3. Create the pardalote environment
4. Verify the installation

If a stage fails, consult [troubleshooting](04_troubleshooting.md) 
---

## Step 1: Install Miniconda (or Anaconda)

Miniconda provides Python and `conda`, the environment manager.

1. Download the Windows 64-bit `.exe` installer from
   <https://www.anaconda.com/download/success>, under **Miniconda Installers**.
2. Run the installer.
3. Select **Just Me** rather than "All Users". This avoids the need for
   administrator rights at later stages.
4. Accept the default install location.
5. Under **Advanced Options**, tick **Register Miniconda3 as my default
   Python**. Leave **Add to PATH** unticked, as advised by the installer.
6. Complete the installation, then **restart the computer**. Omitting this is
   the most common cause of `conda is not recognised` errors.

To confirm installation, open Anaconda Prompt. The prompt should begin with
`(base)`, which indicates the currently active environment.

---

## Step 2: Obtain pardalote

### Option A: download the archive

1. Open the pardalote GitHub page.
2. Select **Code**, then **Download ZIP**.
3. Save the archive to a working directory, for example
   `C:\Users\YourName\Documents`.
4. Right click the archive, select **Extract All**, and extract in place.

This produces a folder named `pardalote-main`, which may be renamed to
`pardalote`. Record the full path to this folder, as it is required in the next
stage. The path will resemble `C:\Users\YourName\Documents\pardalote`.

### Option B: clone with git

If git is already installed:

```bash
cd C:\Users\YourName\Documents
git clone https://github.com/callanalexander/pardalote.git
cd pardalote
```

---

## Step 3: Create the pardalote environment

Open Anaconda Prompt and change to the pardalote directory, quoting the path
recorded above:

```
cd "C:\Users\YourName\Documents\pardalote"
```

> A folder path can be copied from File Explorer by selecting the address bar
> and pressing Ctrl+C. In Anaconda Prompt, paste with a right click rather than
> Ctrl+V.

If the folder is on a different drive, for example `D:`, enter the drive letter
on its own line before the `cd` command.

Create the environment:

```
conda env create -f environment.yml
```

Activate the environment once it completes:

```
conda activate pardalote
```

The prompt prefix should change from `(base)` to `(pardalote)`, confirming
activation.

> Activation is required in every new session. Anaconda Prompt always opens in
> `(base)`, and pardalote will not run there because its packages are installed
> only in the `pardalote` environment.


## Step 4: Verify the installation

With `(pardalote)` active, start Jupyter:

```
jupyter lab
```

JupyterLab opens in the default web browser and displays a file listing. It runs
locally, not over the internet, despite the browser interface.

Leave the Anaconda Prompt window open. Closing it terminates the Jupyter server.

In the file listing, open `notebooks`, then `00_check_setup.ipynb`. Select the
code cell and press **Shift + Enter** to execute it. The expected output ends
with:

```
All packages are present.
```

If any package is reported as `MISSING`, the output includes the command
required to install it. Run that command in Anaconda Prompt, restart the
notebook kernel (**Kernel** > **Restart Kernel**), and execute the cell again.

---

## Starting pardalote in subsequent sessions

1. Open Anaconda Prompt
2. `conda activate pardalote`
3. `cd "C:\path\to\pardalote"`
4. `jupyter lab`

Next: **[generating your embeddings](02_generate_embeddings.md)**.

---
