"""
pardalote step 1 (Perch only)

Extract Perch v2 embeddings from a perch-hoplite database into BirdNET-style
.txt files, mirroring the subfolder structure of the original audio.

perch-hoplite stores embeddings in a SQLite + usearch database rather than as
files. pardalote reads text files, so this script streams the database out to
one .txt per source recording:

    start_seconds <TAB> end_seconds <TAB> "v1,v2,...,v1536"

It reads one embedding at a time, so it does not need to hold the whole
database in RAM.

You only need this if you used Perch. BirdNET users go to notebook 01.

--------------------------------------------------------------------------
EDIT THE CONFIG BLOCK, THEN RUN THE CELL.
--------------------------------------------------------------------------
"""

from collections import defaultdict
from pathlib import Path, PurePath

from perch_hoplite.db import sqlite_usearch_impl

# ============================ CONFIG =====================================
# The perch-hoplite database folder (the one you passed to 01_embed_audio).
DB_DIR = Path(r"D:\Drive\2026\tawny_embed_embeddings_db")

# The root of the original audio tree, used to rebuild the folder structure.
AUDIO_ROOT = Path(r"D:\Drive\2026\bulk_snippets_bins_v5\Tawny_Frogmouth\master_manually_validated")

# Where the .txt files land. This is the folder you will point pardalote's
# "Embeddings" box at.
OUT_DIR = AUDIO_ROOT / "perch_embed"

WINDOW_SECONDS = 5.0   # Perch v2 default window length
AUDIO_EXTS = {".wav", ".flac", ".mp3", ".ogg", ".w4v", ".wac"}
SUFFIX = ".perch.embeddings.txt"
# =========================================================================

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- 1. Index the audio tree: stem -> [relative paths] ------------------
stem_map = defaultdict(list)
for p in AUDIO_ROOT.rglob("*"):
    if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
        stem_map[p.stem].append(p.relative_to(AUDIO_ROOT))

print(f"Indexed {sum(len(v) for v in stem_map.values())} audio files "
      f"under {AUDIO_ROOT}")

ambiguous = {k: v for k, v in stem_map.items() if len(v) > 1}
if ambiguous:
    print(f"WARNING: {len(ambiguous)} duplicate stems in the audio tree; "
          f"first match will be used (e.g. {next(iter(ambiguous))})")


def resolve_rel(source_id: str) -> Path:
    """Return the output path (relative to OUT_DIR) for a given source_id."""
    sp = PurePath(str(source_id).replace("\\", "/"))

    # a) source_id already holds a path that exists under AUDIO_ROOT
    for n in range(len(sp.parts)):
        cand = Path(*sp.parts[n:])
        if (AUDIO_ROOT / cand).is_file():
            return cand.with_name(cand.stem + SUFFIX)

    # b) fall back to a stem lookup
    hits = stem_map.get(sp.stem)
    if hits:
        rel = sorted(hits)[0]
        return rel.with_name(rel.stem + SUFFIX)

    # c) nothing found: dump flat and flag it
    print(f"  ! no audio match for '{source_id}', writing to root of OUT_DIR")
    return Path(sp.stem + SUFFIX)


# ---- 2. Group embedding ids by source file ------------------------------
db = sqlite_usearch_impl.SQLiteUsearchDB.create(str(DB_DIR))
all_ids = db.get_embedding_ids()
print(f"Found {len(all_ids)} embeddings")

ids_by_source = defaultdict(list)
for emb_id in all_ids:
    src = db.get_embedding_source(int(emb_id))
    start = float(src.offsets[0]) if len(src.offsets) > 0 else 0.0
    ids_by_source[src.source_id].append((start, int(emb_id)))

# ---- 3. Write one txt per source, mirroring the folder structure --------
for source_path, items in ids_by_source.items():
    items.sort()  # by start time
    out_path = OUT_DIR / resolve_rel(source_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w") as f:
        for start, emb_id in items:
            vec = db.get_embedding(emb_id)      # np.ndarray, shape (1536,)
            end = start + WINDOW_SECONDS
            csv = ",".join(repr(float(x)) for x in vec)
            f.write(f'{start}\t{end}\t"{csv}"\n')

    print(f"Wrote {out_path.relative_to(OUT_DIR)} ({len(items)} rows)")

print(f"\nDone. {len(ids_by_source):,} file(s) written to {OUT_DIR}")
print("Next: open the pardalote GUI notebook and point 'Embeddings' at "
      "the folder above.")
