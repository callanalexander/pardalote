# 1. Installing pardalote

You do this once. Set aside an hour, most of which is waiting on downloads.

There are four parts:

1. Install Miniconda, which is the thing that manages Python for you
2. Download pardalote
3. Create the pardalote environment
4. Check it worked

If any step fails, jump to [troubleshooting](04_troubleshooting.md) rather than
guessing. Guessing at installs tends to make things worse.

---

## A note on jargon

Three words appear constantly and are worth pinning down now.

**Python** is the programming language pardalote is written in. You will never
write any. You just need it installed.

**An environment** is a private, self-contained copy of Python with a specific
set of add-on packages. Having one for pardalote means installing something else
later cannot break it. You will create one called `pardalote`.

**Anaconda Prompt** is a black window where you type commands. It is not the
normal Windows Command Prompt. It is a special one that knows about your
environments. When these docs say "open Anaconda Prompt", they mean the one that
Miniconda installs, which you find by pressing the Windows key and typing
`Anaconda Prompt`.

---

## Step 1: Install Miniconda

Miniconda is a small installer that gives you Python plus `conda`, the tool that
builds environments.

1. Go to <https://www.anaconda.com/download/success> and, under **Miniconda
   Installers**, download the Windows 64-bit `.exe`.
2. Run it.
3. When asked, choose **Just Me**, not "All Users". This avoids needing
   administrator rights later.
4. Leave the install location at whatever it suggests.
5. On the "Advanced Options" screen, tick **Register Miniconda3 as my default
   Python**. Leave "Add to PATH" unticked: the warning next to it is real, and
   you do not need it.
6. Finish, then **restart your computer**. This genuinely matters. Skipping it is
   the single most common cause of "conda is not recognised" later.

To confirm it worked: press the Windows key, type `Anaconda Prompt`, and open it.
You should get a black window with `(base)` at the start of the line. That
`(base)` is conda telling you which environment you are in.

---

## Step 2: Download pardalote

Two options. Pick whichever you find less intimidating.

### Option A: download a zip (simplest)

1. Go to the pardalote GitHub page.
2. Click the green **Code** button, then **Download ZIP**.
3. Save it somewhere sensible, like `C:\Users\YourName\Documents`.
4. Right click the zip, choose **Extract All**, and extract it there.

You now have a folder called `pardalote-main`. Rename it to `pardalote` if you
like. **Note down the full path to this folder**, because you will need it in a
moment. It will look something like
`C:\Users\YourName\Documents\pardalote`.

### Option B: use git

If you already have git installed and know what it is:

```bash
cd C:\Users\YourName\Documents
git clone https://github.com/YOUR-USERNAME/pardalote.git
cd pardalote
```

The advantage is that `git pull` gets you future updates in one command. The
disadvantage is installing git. Option A is fine.

---

## Step 3: Create the pardalote environment

Open **Anaconda Prompt**.

First, move into the pardalote folder. Type `cd `, then the path you noted down,
in quotes:

```
cd "C:\Users\YourName\Documents\pardalote"
```

> **Tip:** you can copy a folder path from File Explorer by clicking the address
> bar and pressing Ctrl+C. In Anaconda Prompt, paste with a right click, not
> Ctrl+V.

If the folder is on a different drive, for example `D:`, you need to switch
drives first by typing `D:` on its own line, then the `cd` command.

Now build the environment:

```
conda env create -f environment.yml
```

This downloads about a gigabyte and takes ten to thirty minutes. It will look
frozen at "Solving environment" for a while. It is not frozen. Leave it alone.

When it finishes, activate the environment:

```
conda activate pardalote
```

The `(base)` at the start of your prompt should change to `(pardalote)`. That is
how you know it worked.

> **You will need to do this every time.** Opening Anaconda Prompt always starts
> you in `(base)`. Running pardalote from `(base)` will not work, because the
> packages are not installed there. Get into the habit: open prompt, type
> `conda activate pardalote`, then carry on.

### If conda is very slow

Some machines take an hour on "Solving environment". If yours is one, cancel with
Ctrl+C and use the faster solver instead:

```
conda install -n base conda-libmamba-solver
conda env create -f environment.yml --solver=libmamba
```

---

## Step 4: Check it worked

Still in Anaconda Prompt, with `(pardalote)` showing, start Jupyter:

```
jupyter lab
```

Your web browser opens with a file listing. This is JupyterLab, where you will
run everything. It is running on your own computer, not on the internet, despite
appearing in a browser.

**Leave the Anaconda Prompt window open.** Closing it shuts Jupyter down.

In the file listing on the left, double click `notebooks`, then double click
`00_check_setup.ipynb`.

You will see a block of text and, below it, a block of code in a grey box. Click
once on the grey box to select it, then press **Shift + Enter** to run it.

After a few seconds you should see a list ending in:

```
All packages are present.
```

If instead some lines say `MISSING`, the output tells you the exact command to
fix it. Copy that command, paste it into Anaconda Prompt, let it finish, then
restart the notebook kernel (menu: **Kernel** > **Restart Kernel**) and run the
cell again.

---

## You are installed

To start pardalote on any future day:

1. Open **Anaconda Prompt**
2. `conda activate pardalote`
3. `cd "C:\path\to\pardalote"`
4. `jupyter lab`

Next: **[generating your embeddings](02_generate_embeddings.md)**.

---

## Appendix: installing with pip instead of conda

Only do this if you have a reason to avoid conda, and know your way around a
terminal.

`hdbscan` and `llvmlite` need a C++ compiler when installed from pip on Windows,
so install [Microsoft C++ Build
Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) first, ticking
the "Desktop development with C++" workload. Then:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If `pip install hdbscan` fails with a wall of compiler errors, that is the
missing build tools. The conda route exists precisely to avoid this.
