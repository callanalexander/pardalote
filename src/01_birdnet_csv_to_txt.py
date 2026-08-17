"""
pardalote step 1 (BirdNET only)

Split one big BirdNET embeddings.csv into one .txt file per source recording.

BirdNET-Analyzer's `--file_output` flag writes a single CSV containing every
segment from every recording. pardalote wants one file per recording, named
after the recording, so it can match embeddings back to audio. This script
does that split, and rebuilds the original folder structure while it goes.

Output format, one row per segment:

    start_seconds <TAB> end_seconds <TAB> "v1,v2,...,vN"

You only need this if you used BirdNET. Perch users go to notebook 03.

--------------------------------------------------------------------------
EDIT THE THREE PATHS IN THE CONFIG BLOCK, THEN RUN THE CELL.
--------------------------------------------------------------------------
"""

from pathlib import Path, PureWindowsPath

# ============================ CONFIG =====================================
# Use r"..." around every path so Windows backslashes are read literally.

# The big CSV that BirdNET wrote.
INPUT_CSV = r"Z:\validation\bulk_snippets_bins_v6\Common_Bronzewing\embed\embeddings.csv"

# Where the per-recording .txt files should go. Created if it does not exist.
OUTPUT_DIR = r"Z:\validation\bulk_snippets_bins_v6\Common_Bronzewing\embed_cut"

# Everything in the original audio path AFTER this prefix is preserved as
# subfolder structure in the output. Copy-paste the path up to, but not
# including, the folders you want to keep.
#
# For an original recording at:
#   D:\Drive\2026\mgw_dec_segments\mgw_2MU01820_20251024_180702.wav
#
#   BASE_PATH = r"D:\Drive\2026"
#     -> OUTPUT_DIR\mgw_dec_segments\mgw_2MU01820_...birdnet.embeddings.txt
#
#   BASE_PATH = r"D:\Drive"
#     -> OUTPUT_DIR\2026\mgw_dec_segments\mgw_2MU01820_...birdnet.embeddings.txt
#
#   BASE_PATH = r"D:\Drive\2026\mgw_dec_segments"
#     -> OUTPUT_DIR\mgw_2MU01820_...birdnet.embeddings.txt        (flat)
#
# Keeping at least one level of folder structure is worth it: pardalote treats
# the first folder under the embeddings root as the "site" name.
BASE_PATH = r"Z:\validation\bulk_snippets_bins_v6\Common_Bronzewing"
# =========================================================================


def get_output_path(original_path_str, base_path_str, output_dir):
    """Work out where one recording's .txt should be written."""
    p = PureWindowsPath(original_path_str)
    base = PureWindowsPath(base_path_str)

    # Preserve everything between BASE_PATH and the file itself.
    try:
        rel_parent = p.parent.relative_to(base)
        sub_parts = rel_parent.parts
    except ValueError:
        # The original path does not start with BASE_PATH. Fall back to just
        # the immediate parent folder and warn once.
        sub_parts = (p.parent.name,)

    out_filename = p.stem + ".birdnet.embeddings.txt"
    return Path(output_dir, *sub_parts, out_filename)


# ---- Peek at the file to work out the delimiter -------------------------
with open(INPUT_CSV, "r", encoding="utf-8-sig") as f:
    header_line = f.readline().rstrip("\n\r")
    first_data_line = f.readline().rstrip("\n\r")

print("Header repr :", repr(header_line[:200]))
print("Row 1  repr :", repr(first_data_line[:200]))

if "\t" in header_line:
    sep_mode = "tab"
    print("-> Detected TAB-separated columns\n")
else:
    sep_mode = "comma3"
    print("-> No tabs found; assuming comma-separated with the embedding "
          "as the 4th field onwards\n")


def parse_line(line):
    """Split a row into (file_path, start, end, embedding)."""
    if sep_mode == "tab":
        parts = line.split("\t", 3)
    else:
        parts = line.split(",", 3)
    if len(parts) < 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


# ---- Main pass ----------------------------------------------------------
seen_files = set()
current_file = None
current_handle = None
rows_written = 0
warned_base = False

try:
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as infile:
        next(infile, None)  # skip header
        for lineno, raw in enumerate(infile, start=2):
            line = raw.rstrip("\n\r")
            if not line:
                continue

            parsed = parse_line(line)
            if parsed is None:
                continue
            file_path, start, end, embedding = parsed

            if file_path != current_file:
                if current_handle is not None:
                    current_handle.close()

                # Sanity check BASE_PATH the first time we see a mismatch
                if not warned_base:
                    try:
                        PureWindowsPath(file_path).parent.relative_to(
                            PureWindowsPath(BASE_PATH))
                    except ValueError:
                        print(f"WARNING: BASE_PATH {BASE_PATH!r} is not a prefix of")
                        print(f"         {file_path!r}")
                        print(f"         Falling back to the immediate parent "
                              f"folder only.\n")
                        warned_base = True

                out_path = get_output_path(file_path, BASE_PATH, OUTPUT_DIR)
                out_path.parent.mkdir(parents=True, exist_ok=True)

                mode = "w" if file_path not in seen_files else "a"
                current_handle = open(out_path, mode, encoding="utf-8")
                seen_files.add(file_path)
                current_file = file_path

            current_handle.write(f"{start}\t{end}\t{embedding}\n")
            rows_written += 1
finally:
    if current_handle is not None:
        current_handle.close()

print(f"Done. Wrote {rows_written:,} rows across {len(seen_files):,} file(s) "
      f"into {OUTPUT_DIR}")
print("\nNext: notebook 02 if your embeddings live in bin folders that do not "
      "match your audio folders, otherwise go straight to the pardalote GUI.")
