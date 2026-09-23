"""
Copy the GUI cell out of notebooks/pardalote_gui.ipynb into pardalote_app.py.

Run from the repository root (the build workflow does this for you):
    python desktop/extract_app.py
"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
nb_path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "notebooks" / "pardalote_gui.ipynb"
out_path = Path(__file__).resolve().parent / "pardalote_app.py"

nb = json.loads(nb_path.read_text(encoding="utf-8"))
cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
gui = [c for c in cells if "class EmbeddingClusteringGUI" in c]
if len(gui) != 1:
    sys.exit(f"Expected exactly one GUI cell in {nb_path}, found {len(gui)}")

out_path.write_text("# GENERATED from " + nb_path.name + " by extract_app.py. Edit the notebook, not this file.\n\n"
                    + gui[0], encoding="utf-8")
print(f"Wrote {out_path}")
