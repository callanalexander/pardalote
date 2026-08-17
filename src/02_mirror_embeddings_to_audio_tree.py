"""
pardalote step 2 (optional)

Mirror BirdNET embedding .txt files into the audio folder structure.

Use this when your embeddings ended up in a different folder layout from your
audio. A common case: you ran BirdNET over audio that had been sorted into
"bin" folders by confidence score, but your working copy of the audio is
sorted by site or by validation status instead.

Source embeddings sit anywhere under EMBED_ROOT. Output goes to
    <AUDIO_ROOT>/birdnet_embed/<same subfolders as the audio>/
Matching is on filename stem, so the source bin folders are ignored.

Run it once with DRY_RUN = True to see what it would do, read the counts, then
set DRY_RUN = False and run it again.

--------------------------------------------------------------------------
EDIT THE CONFIG BLOCK, THEN RUN THE CELL.
--------------------------------------------------------------------------
"""

import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd

# ============================ CONFIG =====================================
# Where the .txt embedding files currently are (searched recursively).
EMBED_ROOT = Path(r"D:\Drive\2026\bulk_snippets_bins_v5\Powerful_Owl\binned_audio\embed_cut")

# The root of the audio tree whose structure you want to copy.
AUDIO_ROOT = Path(r"D:\Drive\2026\bulk_snippets_bins_v5\Powerful_Owl\master_manually_validated")

# Where the mirrored embeddings land. This is the folder you will point
# pardalote's "Embeddings" box at.
OUT_DIR = AUDIO_ROOT / "birdnet_embed"

SUFFIX = ".birdnet.embeddings.txt"
AUDIO_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".w4v", ".wac"}
SKIP_DIRS = {"birdnet_embed", "perch_embed"}   # not part of the audio tree

DRY_RUN = True     # True = report only, nothing written. Set False to apply.
MOVE = False       # False = copy (safer). True = delete sources after copying.
OVERWRITE = False  # False = skip files already present in OUT_DIR
# =========================================================================

# ---- 1. Index the embedding files: key = name minus SUFFIX --------------
embed_map = defaultdict(list)
for p in EMBED_ROOT.rglob("*.txt"):
    n = p.name.lower()
    if n.endswith(SUFFIX.lower()):
        embed_map[n[: -len(SUFFIX)]].append(p)

print(f"indexed {sum(len(v) for v in embed_map.values())} embedding files "
      f"({len(embed_map)} unique stems) under {EMBED_ROOT}")

amb = {k: v for k, v in embed_map.items() if len(v) > 1}
if amb:
    print(f"WARNING: {len(amb)} stems appear in more than one bin folder, "
          f"first by path will be used (e.g. {next(iter(amb))})")

# ---- 2. Walk the audio tree and pair each file with its embedding --------
plan = []
for a in AUDIO_ROOT.rglob("*"):
    if not a.is_file() or a.suffix.lower() not in AUDIO_EXTS:
        continue
    rel = a.relative_to(AUDIO_ROOT)
    if SKIP_DIRS & set(rel.parts[:-1]):
        continue

    hits = sorted(embed_map.get(a.stem.lower(), []))
    tgt = OUT_DIR / rel.parent / (a.stem + SUFFIX)

    if not hits:
        plan.append((a, None, tgt, "no_embedding"))
    elif tgt.exists() and not OVERWRITE:
        plan.append((a, hits[0], tgt, "already_present"))
    else:
        plan.append((a, hits[0], tgt, "ambiguous_ok" if len(hits) > 1 else "ok"))

counts = pd.Series([s for *_, s in plan]).value_counts()
print(f"\n{len(plan)} audio files found under {AUDIO_ROOT}")
print(counts.to_string())

missing = [a.name for a, _, _, s in plan if s == "no_embedding"]
for n in missing[:10]:
    print("   no embedding:", n)
if len(missing) > 10:
    print(f"   ... and {len(missing) - 10} more")

# ---- 3. Copy, then delete sources only if MOVE --------------------------
todo = [(src, tgt) for _, src, tgt, s in plan if s in {"ok", "ambiguous_ok"}]

if DRY_RUN:
    print(f"\nDRY RUN, nothing written. {len(todo)} files would be "
          f"{'moved' if MOVE else 'copied'}. Set DRY_RUN = False to apply.")
    for src, tgt in todo[:5]:
        print(f"   {src}  ->  {tgt}")
else:
    done = []
    for src, tgt in todo:
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, tgt)
        done.append(src)
    print(f"\ncopied {len(done)} files into {OUT_DIR}")

    if MOVE:
        for src in set(done):
            src.unlink()
        print(f"removed {len(set(done))} source files from {EMBED_ROOT}")

# ---- 4. Write a log so you can check what happened ----------------------
log = pd.DataFrame(
    [{"audio": str(a.relative_to(AUDIO_ROOT)),
      "embedding_src": str(src) if src else "",
      "embedding_out": str(tgt.relative_to(AUDIO_ROOT)) if src else "",
      "status": s if not DRY_RUN else f"{s}_dryrun"}
     for a, src, tgt, s in plan])
log.to_csv(AUDIO_ROOT / "birdnet_embed_transfer_log.csv", index=False)
print("log written to", AUDIO_ROOT / "birdnet_embed_transfer_log.csv")
