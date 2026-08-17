# pardalote clustering GUI - v6
# v6 changes
#  - 3D UMAP plot option (rotate by drag, view angle persists across replots)
#  - Reverted clip loading to librosa throughout
#  - Click-to-play on button release with a drag threshold, so rotating does not play audio
#  - 3D hit testing via proj3d projection into screen pixels
# v5 changes
#  - Defaults: click-to-play on, 10000 files/site, sample rate 1.0, PCA off, 10000 plot points
#  - Cluster in N-D UMAP space; fixed custom_label colouring, master_df noise sync, undo
#  - Dropdown text -> cluster id mapping, seeded subsampling, vectorised removal marking
#  - Threaded playback + stop, cancellable export, thread-safe logging, RAM pre-flight

import os
import gc
import re
import json
import queue
import umap
import hdbscan
import librosa
import psutil
import warnings
import threading
import numpy as np
import pandas as pd
import soundfile as sf
import sounddevice as sd
import tkinter as tk
from pathlib import Path
from datetime import datetime
import librosa.display
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d  # noqa: F401 (also registers 3d projection)
from tkinter import ttk, filedialog, messagebox
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import multiprocessing as mp

warnings.filterwarnings('ignore')

MAX_HISTORY = 5
CLICK_RADIUS_PX = 25
DRAG_TOLERANCE_PX = 5


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_clip(path, start_s, duration_s):
    """Load an audio clip with librosa."""
    y, sr = librosa.load(str(path), sr=None, offset=float(start_s),
                         duration=max(0.01, float(duration_s)))
    return np.asarray(y, dtype=np.float32), sr


def norm_key(name):
    """Normalise a filename stem so embedding and audio files match reliably."""
    s = str(name).lower()
    for suffix in ('.birdnet.embeddings', '.embeddings', '_embeddings',
                   '.perch.embeddings', '.embed'):
        s = s.replace(suffix, '')
    return re.sub(r'[^a-z0-9]', '', s)


class CollapsibleFrame(ttk.Frame):
    """A frame with a toggle button that shows/hides its content."""

    def __init__(self, parent, text, start_collapsed=False, **kwargs):
        super().__init__(parent, **kwargs)
        self._text = text
        self._collapsed = False

        self.toggle_btn = tk.Button(
            self, text=f"▼  {text}",
            anchor="w", relief="flat",
            bg="#dde3ec", fg="#1a2236",
            font=("TkDefaultFont", 8, "bold"),
            cursor="hand2",
            command=self.toggle
        )
        self.toggle_btn.pack(fill=tk.X, pady=(2, 0))

        self.content = ttk.Frame(self)
        self.content.pack(fill=tk.X, pady=(0, 4))

        if start_collapsed:
            self.toggle()

    def toggle(self):
        if self._collapsed:
            self.content.pack(fill=tk.X, pady=(0, 4))
            self.toggle_btn.config(text=f"▼  {self._text}")
        else:
            self.content.pack_forget()
            self.toggle_btn.config(text=f"▶  {self._text}")
        self._collapsed = not self._collapsed


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

class EmbeddingClusteringGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("pardalote - embeddings clustering tool")

        self.master.state('zoomed')
        self.master.minsize(1200, 700)
        self.master.config(bg="#f0f0f0")

        # Data storage
        self.embeddings = None
        self.metadata = None
        self.plot_data = None
        self.embedding_nd = None
        self.embedding_2d = None
        self.cluster_labels = None
        self.progress_queue = queue.Queue()

        # Labelling and filtering
        self.cluster_custom_labels = {}
        self.clusters_to_remove = set()
        self.iteration_count = 0
        self.clustering_history = []

        # File mapping
        self.file_mapping = {}

        # Click to play
        self.plot_data_sample = None
        self.click_conns = []
        self.pop_out_click_conns = []
        self._press_xy = None
        self._cluster_option_map = {}

        # 3D view state
        self.view_elev = 22.0
        self.view_azim = -60.0
        self.ax = None
        self.pop_out_ax = None

        # Pop-out window
        self.pop_out_window = None
        self.pop_out_fig = None
        self.pop_out_canvas = None

        # Master tracking CSV
        self.master_df = None
        self.autosave_dir = None
        self.autosave_path = None

        # Export control
        self.cancel_export = threading.Event()

        print("System Info:")
        print(f"Available CPU cores: {mp.cpu_count()}")
        print(f"Available RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB")

        self.create_main_layout()
        self.master.bind("<space>", lambda e: self.stop_playback())
        self.master.after(200, self.check_progress_queue)

    # ─────────────────────────────────────────────────────────────────────────
    # LAYOUT
    # ─────────────────────────────────────────────────────────────────────────

    def create_main_layout(self):
        self.create_status_bar()

        self.outer_paned = ttk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.outer_paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.sidebar_frame = ttk.Frame(self.outer_paned)
        self.outer_paned.add(self.sidebar_frame, weight=0)

        self.viz_outer = ttk.Frame(self.outer_paned)
        self.outer_paned.add(self.viz_outer, weight=5)

        self.cluster_panel = ttk.Frame(self.outer_paned)
        self.outer_paned.add(self.cluster_panel, weight=0)

        self._build_sidebar()
        self.create_viz_panel(self.viz_outer)
        self.create_cluster_panel(self.cluster_panel)

        self.master.after(100, self._set_initial_sash)

    def _set_initial_sash(self):
        try:
            total = self.master.winfo_width()
            self.outer_paned.sashpos(0, 230)
            self.outer_paned.sashpos(1, total - 240)
        except Exception:
            pass

    # ── Left sidebar ─────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb_canvas = tk.Canvas(self.sidebar_frame, width=225, bg="#f0f0f0",
                              highlightthickness=0)
        sb_scroll = ttk.Scrollbar(self.sidebar_frame, orient="vertical",
                                  command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sb_inner = ttk.Frame(sb_canvas)
        sb_canvas.create_window((0, 0), window=self.sb_inner, anchor="nw")
        self.sb_inner.bind(
            "<Configure>",
            lambda e: sb_canvas.configure(scrollregion=sb_canvas.bbox("all"))
        )

        p = self.sb_inner

        cf_paths = CollapsibleFrame(p, "📁  Data Paths")
        cf_paths.pack(fill=tk.X, padx=4)
        self._build_paths_section(cf_paths.content)

        cf_main = CollapsibleFrame(p, "🔧  Main Controls")
        cf_main.pack(fill=tk.X, padx=4)
        self._build_main_controls(cf_main.content)

        cf_settings = CollapsibleFrame(p, "⚙️  Settings", start_collapsed=True)
        cf_settings.pack(fill=tk.X, padx=4)
        self._build_settings(cf_settings.content)

        cf_state = CollapsibleFrame(p, "💾  State / Iteration")
        cf_state.pack(fill=tk.X, padx=4)
        self._build_state_controls(cf_state.content)

        cf_export = CollapsibleFrame(p, "📤  Export", start_collapsed=True)
        cf_export.pack(fill=tk.X, padx=4)
        self._build_export_controls(cf_export.content)

        cf_log = CollapsibleFrame(p, "📋  Log")
        cf_log.pack(fill=tk.X, padx=4)
        self._build_log(cf_log.content)

    def _build_paths_section(self, parent):
        g = ttk.Frame(parent)
        g.pack(fill=tk.X, padx=4, pady=2)
        g.columnconfigure(1, weight=1)

        ttk.Label(g, text="Embeddings:").grid(row=0, column=0, sticky="w")
        self.embed_path_var = tk.StringVar()
        ttk.Entry(g, textvariable=self.embed_path_var, width=16).grid(row=0, column=1, sticky="ew")
        ttk.Button(g, text="…", width=2, command=self.browse_embed_path).grid(row=0, column=2)

        ttk.Label(g, text="Audio:").grid(row=1, column=0, sticky="w")
        self.audio_path_var = tk.StringVar()
        ttk.Entry(g, textvariable=self.audio_path_var, width=16).grid(row=1, column=1, sticky="ew")
        ttk.Button(g, text="…", width=2, command=self.browse_audio_path).grid(row=1, column=2)

        ttk.Label(g, text="Autosave:").grid(row=2, column=0, sticky="w")
        self.autosave_dir_var = tk.StringVar()
        ttk.Entry(g, textvariable=self.autosave_dir_var, width=16).grid(row=2, column=1, sticky="ew")
        ttk.Button(g, text="…", width=2, command=self.browse_autosave_dir).grid(row=2, column=2)

        pf = ttk.Frame(parent)
        pf.pack(fill=tk.X, padx=4, pady=2)
        ttk.Label(pf, text="Embed pattern:").pack(anchor="w")
        self.embed_pattern_var = tk.StringVar(value="*.embeddings.txt")
        ttk.Entry(pf, textvariable=self.embed_pattern_var).pack(fill=tk.X)
        ttk.Label(pf, text="Audio ext:").pack(anchor="w")
        self.audio_ext_var = tk.StringVar(value=".wav,.WAV,.mp3,.MP3,.flac,.FLAC")
        ttk.Entry(pf, textvariable=self.audio_ext_var).pack(fill=tk.X)

        default_embed = os.path.expanduser("~/data/embed") if os.name != 'nt' else r"M:\songmeter_2025\embed"
        default_audio = os.path.expanduser("~/data/audio") if os.name != 'nt' else r"M:\songmeter_2025"
        self.embed_path_var.set(default_embed)
        self.audio_path_var.set(default_audio)

    def _build_main_controls(self, parent):
        g = ttk.Frame(parent)
        g.pack(padx=4, pady=2)
        ttk.Button(g, text="1. Scan",    command=self.scan_files,       width=11).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(g, text="2. Load",    command=self.load_data,        width=11).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(g, text="3. Cluster", command=self.run_clustering,   width=11).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(g, text="4. Plot",    command=self.update_umap_plot, width=11).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(g, text="⏹ Stop audio (space)", command=self.stop_playback,
                   width=24).grid(row=2, column=0, columnspan=2, padx=2, pady=2)

    def _build_settings(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.X, padx=4, pady=2)
        self.create_data_settings_tab(nb)
        self.create_umap_settings_tab(nb)
        self.create_hdbscan_settings_tab(nb)

    def _build_state_controls(self, parent):
        g = ttk.Frame(parent)
        g.pack(padx=4, pady=2)
        ttk.Button(g, text="💾 Save",         command=self.save_state,                 width=11).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(g, text="📂 Load",         command=self.load_state,                 width=11).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(g, text="🔄 Re-cluster",   command=self.recluster_filtered,         width=11).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(g, text="↩️ Undo",         command=self.undo_last_removal,          width=11).grid(row=1, column=1, padx=2, pady=2)
        ttk.Button(g, text="🎯 Assign Noise", command=self.assign_noise_to_clusters,   width=11).grid(row=2, column=0, padx=2, pady=2)
        ttk.Button(g, text="🗑️ Keep Only",    command=self.keep_only_selected_cluster, width=11).grid(row=2, column=1, padx=2, pady=2)

    def _build_export_controls(self, parent):
        g = ttk.Frame(parent)
        g.pack(padx=4, pady=2)
        ttk.Button(g, text="📤 Export Audio + CSV",   command=self.export_results,       width=22).pack(pady=2)
        ttk.Button(g, text="📋 Export Manifest Only", command=self.export_manifest_only, width=22).pack(pady=2)
        ttk.Button(g, text="✖ Cancel Export",         command=self.cancel_export_job,    width=22).pack(pady=2)

    def _build_log(self, parent):
        self.local_progress_var = tk.IntVar(value=0)
        self.local_progress_bar = ttk.Progressbar(parent, variable=self.local_progress_var)
        self.local_progress_bar.pack(fill=tk.X, padx=4, pady=2)
        self.log_text = tk.Text(parent, height=8, wrap=tk.WORD, font=('Courier', 7))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

    # ── Right cluster panel ──────────────────────────────────────────────────

    def create_cluster_panel(self, parent):
        parent.config(width=230)
        cf = CollapsibleFrame(parent, "🗂️  Cluster Management")
        cf.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._build_cluster_management(cf.content)

    def _build_cluster_management(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Cluster:").grid(row=0, column=0, sticky="w", pady=2)
        self.cluster_var = tk.StringVar()
        self.cluster_dropdown = ttk.Combobox(parent, textvariable=self.cluster_var,
                                             state="disabled", width=18)
        self.cluster_dropdown.grid(row=0, column=1, columnspan=2, pady=2)
        self.cluster_dropdown.bind("<<ComboboxSelected>>", self.on_cluster_selected)

        ttk.Label(parent, text="Label:").grid(row=1, column=0, sticky="w", pady=2)
        self.custom_label_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.custom_label_var, width=12).grid(row=1, column=1, pady=2)
        ttk.Button(parent, text="Apply", command=self.apply_custom_label, width=6).grid(row=1, column=2, pady=2)

        self.mark_removal_var = tk.BooleanVar()
        ttk.Checkbutton(parent, text="Mark for Removal", variable=self.mark_removal_var,
                        command=self.toggle_removal_mark).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Separator(parent, orient="horizontal").grid(row=3, column=0, columnspan=3,
                                                        sticky="ew", pady=4)

        ttk.Label(parent, text="Samples:").grid(row=4, column=0, sticky="w", pady=2)
        self.sample_size_var = tk.IntVar(value=6)
        ttk.Spinbox(parent, from_=1, to=20, textvariable=self.sample_size_var, width=5).grid(row=4, column=1, pady=2)
        ttk.Button(parent, text="Show", command=self.update_samples, width=6).grid(row=4, column=2, pady=2)

        lf = ttk.LabelFrame(parent, text="Summary")
        lf.grid(row=5, column=0, columnspan=3, pady=4, sticky="ew")
        self.labels_text = tk.Text(lf, width=26, height=6, font=('Arial', 8), wrap=tk.WORD)
        self.labels_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.stats_text = tk.Text(parent, width=26, height=10, font=('Arial', 8), wrap=tk.WORD)
        self.stats_text.grid(row=6, column=0, columnspan=3, sticky="nsew")
        parent.rowconfigure(6, weight=1)

    # ─────────────────────────────────────────────────────────────────────────
    # VIZ PANEL
    # ─────────────────────────────────────────────────────────────────────────

    def create_viz_panel(self, parent):
        self.viz_tabs = ttk.Notebook(parent)
        self.viz_tabs.pack(fill=tk.BOTH, expand=True)

        self.umap_tab = ttk.Frame(self.viz_tabs)
        self.viz_tabs.add(self.umap_tab, text="UMAP Plot")

        toolbar = ttk.Frame(self.umap_tab)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        ttk.Label(toolbar, text="Color:").pack(side=tk.LEFT)
        self.color_by_var = tk.StringVar(value="cluster")
        self.color_by_combo = ttk.Combobox(
            toolbar, textvariable=self.color_by_var,
            values=["cluster", "site", "custom_label", "removal_status"],
            width=14, state="readonly")
        self.color_by_combo.pack(side=tk.LEFT, padx=4)
        self.color_by_combo.bind("<<ComboboxSelected>>", lambda e: self.update_umap_plot())

        ttk.Label(toolbar, text="Dims:").pack(side=tk.LEFT, padx=(8, 0))
        self.plot_dims_var = tk.StringVar(value="2D")
        self.plot_dims_combo = ttk.Combobox(
            toolbar, textvariable=self.plot_dims_var,
            values=["2D", "3D"], width=4, state="readonly")
        self.plot_dims_combo.pack(side=tk.LEFT, padx=4)
        self.plot_dims_combo.bind("<<ComboboxSelected>>", lambda e: self.on_dims_changed())

        self.clickable_status_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.clickable_status_var,
                  foreground='darkgreen').pack(side=tk.LEFT, padx=8)

        self.last_click_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self.last_click_var,
                  foreground='#333333').pack(side=tk.LEFT, padx=8)

        ttk.Button(toolbar, text="Pop Out",  command=self.pop_out_plot,   width=9).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="Save PNG", command=self.save_umap_plot, width=9).pack(side=tk.RIGHT, padx=3)

        self.umap_fig = Figure(dpi=100)
        self.umap_canvas = FigureCanvasTkAgg(self.umap_fig, self.umap_tab)
        self.umap_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.spectro_tab = ttk.Frame(self.viz_tabs)
        self.viz_tabs.add(self.spectro_tab, text="Audio Samples")
        self.spectro_canvas = tk.Canvas(self.spectro_tab)
        sb = ttk.Scrollbar(self.spectro_tab, orient="vertical",
                           command=self.spectro_canvas.yview)
        self.spectro_frame = ttk.Frame(self.spectro_canvas)
        self.spectro_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.spectro_canvas.pack(side="left", fill="both", expand=True)
        self.spectro_canvas.create_window((0, 0), window=self.spectro_frame, anchor="nw")
        self.spectro_frame.bind(
            "<Configure>",
            lambda e: self.spectro_canvas.configure(
                scrollregion=self.spectro_canvas.bbox("all")))

    # ─────────────────────────────────────────────────────────────────────────
    # SETTINGS TABS
    # ─────────────────────────────────────────────────────────────────────────

    def create_data_settings_tab(self, notebook):
        t = ttk.Frame(notebook, padding=6)
        notebook.add(t, text="Data")

        ttk.Label(t, text="Max Files/Site:").grid(row=0, column=0, sticky="w", pady=2)
        self.max_files_var = tk.IntVar(value=10000)
        ttk.Spinbox(t, from_=1, to=100000, textvariable=self.max_files_var, width=7).grid(row=0, column=1)

        ttk.Label(t, text="Sample Rate:").grid(row=1, column=0, sticky="w", pady=2)
        self.sample_rate_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(t, from_=0.01, to=1.0, increment=0.05,
                    textvariable=self.sample_rate_var, width=7).grid(row=1, column=1)

        ttk.Label(t, text="Use PCA:").grid(row=2, column=0, sticky="w", pady=2)
        self.use_pca_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(t, variable=self.use_pca_var).grid(row=2, column=1)

        ttk.Label(t, text="PCA Components:").grid(row=3, column=0, sticky="w", pady=2)
        self.pca_components_var = tk.IntVar(value=30)
        ttk.Spinbox(t, from_=10, to=200, textvariable=self.pca_components_var, width=7).grid(row=3, column=1)

        ttk.Label(t, text="Max Plot Points:").grid(row=4, column=0, sticky="w", pady=2)
        self.max_plot_var = tk.IntVar(value=10000)
        ttk.Spinbox(t, from_=1000, to=100000, increment=1000,
                    textvariable=self.max_plot_var, width=7).grid(row=4, column=1)

        self.clickable_audio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(t, text="Click to play", variable=self.clickable_audio_var,
                        command=self.setup_clickable_audio).grid(
            row=5, column=0, columnspan=2, pady=2, sticky="w")

        ttk.Label(t, text="Play pad (s):").grid(row=6, column=0, sticky="w", pady=2)
        self.play_pad_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(t, from_=0.0, to=5.0, increment=0.25,
                    textvariable=self.play_pad_var, width=7).grid(row=6, column=1)

        ttk.Label(t, text="Load seed:").grid(row=7, column=0, sticky="w", pady=2)
        self.seed_var = tk.IntVar(value=42)
        ttk.Spinbox(t, from_=0, to=99999, textvariable=self.seed_var, width=7).grid(row=7, column=1)

    def create_umap_settings_tab(self, notebook):
        t = ttk.Frame(notebook, padding=6)
        notebook.add(t, text="UMAP")

        ttk.Label(t, text="n_neighbors:").grid(row=0, column=0, sticky="w")
        self.n_neighbors_var = tk.IntVar(value=15)
        ttk.Spinbox(t, from_=5, to=200, textvariable=self.n_neighbors_var, width=7).grid(row=0, column=1)

        ttk.Label(t, text="min_dist:").grid(row=1, column=0, sticky="w")
        self.min_dist_var = tk.DoubleVar(value=0.1)
        ttk.Spinbox(t, from_=0.0, to=1.0, increment=0.01, textvariable=self.min_dist_var, width=7).grid(row=1, column=1)

        ttk.Label(t, text="metric:").grid(row=2, column=0, sticky="w")
        self.umap_metric_var = tk.StringVar(value="euclidean")
        ttk.Combobox(t, textvariable=self.umap_metric_var,
                     values=["euclidean", "cosine", "manhattan", "correlation"],
                     width=11).grid(row=2, column=1)

        ttk.Label(t, text="spread:").grid(row=3, column=0, sticky="w")
        self.spread_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(t, from_=0.1, to=5.0, increment=0.1, textvariable=self.spread_var, width=7).grid(row=3, column=1)

        ttk.Label(t, text="n_components:").grid(row=4, column=0, sticky="w")
        self.n_components_var = tk.IntVar(value=2)
        ttk.Spinbox(t, from_=2, to=20, textvariable=self.n_components_var, width=7).grid(row=4, column=1)
        ttk.Label(t, text="(clustering space; 3+ enables the 3D plot)",
                  font=('Arial', 7), wraplength=180).grid(row=5, column=0, columnspan=2, sticky="w")

        self.deterministic_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(t, text="Deterministic (slower, single core)",
                        variable=self.deterministic_var).grid(row=6, column=0, columnspan=2,
                                                              sticky="w", pady=2)

    def create_hdbscan_settings_tab(self, notebook):
        t = ttk.Frame(notebook, padding=6)
        notebook.add(t, text="HDBSCAN")

        ttk.Label(t, text="min_cluster_size:").grid(row=0, column=0, sticky="w")
        self.min_cluster_size_var = tk.IntVar(value=50)
        ttk.Spinbox(t, from_=5, to=5000, textvariable=self.min_cluster_size_var, width=7).grid(row=0, column=1)

        ttk.Label(t, text="min_samples:").grid(row=1, column=0, sticky="w")
        self.min_samples_var = tk.IntVar(value=10)
        ttk.Spinbox(t, from_=1, to=500, textvariable=self.min_samples_var, width=7).grid(row=1, column=1)

        ttk.Label(t, text="epsilon:").grid(row=2, column=0, sticky="w")
        self.epsilon_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(t, from_=0.0, to=1.0, increment=0.05, textvariable=self.epsilon_var, width=7).grid(row=2, column=1)

        ttk.Label(t, text="metric:").grid(row=3, column=0, sticky="w")
        self.hdbscan_metric_var = tk.StringVar(value="euclidean")
        ttk.Combobox(t, textvariable=self.hdbscan_metric_var,
                     values=["euclidean", "manhattan"], width=11).grid(row=3, column=1)

        ttk.Label(t, text="selection:").grid(row=4, column=0, sticky="w")
        self.selection_method_var = tk.StringVar(value="eom")
        ttk.Combobox(t, textvariable=self.selection_method_var,
                     values=["eom", "leaf"], width=11).grid(row=4, column=1)

    # ─────────────────────────────────────────────────────────────────────────
    # MASTER TRACKING CSV
    # ─────────────────────────────────────────────────────────────────────────

    def _init_master_df(self):
        if self.metadata is None:
            return
        self.master_df = self.metadata.copy()
        self.master_df['cluster']            = np.nan
        self.master_df['custom_label']       = ''
        self.master_df['status']             = 'unprocessed'
        self.master_df['iteration_assigned'] = np.nan
        self.master_df['iteration_removed']  = np.nan
        self.master_df['removal_reason']     = ''
        self.master_df['umap_x']             = np.nan
        self.master_df['umap_y']             = np.nan
        self.master_df['umap_z']             = np.nan
        self.master_df['row_id']             = np.arange(len(self.master_df))
        self.log_message(f"Master tracking table initialised ({len(self.master_df):,} rows)", "INFO")

    def _active_master_ids(self):
        if self.master_df is None:
            return None
        return self.master_df.index[self.master_df['status'] != 'removed']

    def _sync_master_df_after_cluster(self):
        if self.master_df is None or self.plot_data is None:
            return
        active_ids = self._active_master_ids()
        if len(active_ids) != len(self.plot_data):
            self.log_message(
                f"Row count mismatch during sync ({len(active_ids)} vs {len(self.plot_data)}), "
                "master CSV not updated this round", "ERROR")
            return
        self.master_df.loc[active_ids, 'cluster'] = self.plot_data['cluster'].values
        self.master_df.loc[active_ids, 'umap_x']  = self.plot_data['umap_x'].values
        self.master_df.loc[active_ids, 'umap_y']  = self.plot_data['umap_y'].values
        if 'umap_z' in self.plot_data.columns:
            self.master_df.loc[active_ids, 'umap_z'] = self.plot_data['umap_z'].values
        self.master_df.loc[active_ids, 'status'] = np.where(
            self.plot_data['cluster'].values == -1, 'noise', 'active')
        self.master_df.loc[active_ids, 'iteration_assigned'] = self.iteration_count

    def _mark_removed_in_master(self, removed_cluster_ids, reason="recluster"):
        if self.master_df is None or self.plot_data is None:
            return
        active_ids = self._active_master_ids()
        if len(active_ids) != len(self.plot_data):
            return
        removed_mask = self.plot_data['cluster'].isin(removed_cluster_ids).values
        target_ids = active_ids[removed_mask]
        self.master_df.loc[target_ids, 'status']            = 'removed'
        self.master_df.loc[target_ids, 'iteration_removed'] = self.iteration_count
        self.master_df.loc[target_ids, 'removal_reason']    = reason

    def _update_labels_in_master(self):
        if self.master_df is None:
            return
        for cid, label in self.cluster_custom_labels.items():
            self.master_df.loc[self.master_df['cluster'] == cid, 'custom_label'] = label

    def browse_autosave_dir(self):
        d = filedialog.askdirectory(title="Select Autosave Directory")
        if d:
            self.autosave_dir_var.set(d)
            self.autosave_dir = d

    def autosave_master(self, trigger_label="update"):
        if self.master_df is None:
            return
        save_dir = self.autosave_dir_var.get().strip() or self.embed_path_var.get().strip()
        if not save_dir or not os.path.isdir(save_dir):
            return
        self._update_labels_in_master()
        if self.autosave_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.autosave_path = os.path.join(save_dir, f"master_tracking_{ts}.csv")
        try:
            self.master_df.to_csv(self.autosave_path, index=False)
            self.log_message(
                f"Master CSV autosaved -> {Path(self.autosave_path).name} [{trigger_label}]", "INFO")
        except Exception as e:
            self.log_message(f"Autosave failed: {e}", "ERROR")

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT
    # ─────────────────────────────────────────────────────────────────────────

    def _safe_filename(self, text):
        return re.sub(r'[\\/:*?"<>|]', '_', str(text)).strip()

    def _folder_for_cluster(self, cid):
        if cid == -1:
            return "noise"
        label = self.cluster_custom_labels.get(cid, "")
        return (f"cluster_{cid:02d}_{self._safe_filename(label)}"
                if label else f"cluster_{cid:02d}")

    def cancel_export_job(self):
        self.cancel_export.set()
        self.log_message("Export cancellation requested", "INFO")

    def export_results(self):
        if self.plot_data is None:
            messagebox.showwarning("Warning", "No clustering data available.")
            return
        output_dir = filedialog.askdirectory(title="Select Export Root Directory")
        if not output_dir:
            return
        active_clusters = set(np.unique(self.cluster_labels)) - self.clusters_to_remove
        include_noise = messagebox.askyesno(
            "Noise points",
            "Include noise points (cluster = -1) in the export?\n"
            "They will be placed in a 'noise' folder.")
        if not include_noise:
            active_clusters.discard(-1)
        if not active_clusters:
            messagebox.showinfo("Nothing to export", "All clusters are marked for removal.")
            return
        n_clips = int(self.plot_data['cluster'].isin(active_clusters).sum())
        if not messagebox.askyesno(
                "Confirm Export",
                f"Export {n_clips:,} clips across {len(active_clusters)} cluster(s)?"):
            return
        self.cancel_export.clear()
        threading.Thread(target=self._export_thread,
                         args=(output_dir, active_clusters), daemon=True).start()

    def _export_thread(self, output_dir, active_clusters):
        try:
            rows = self.plot_data[self.plot_data['cluster'].isin(active_clusters)].copy()
            total = len(rows)
            processed = 0
            manifest_rows = []

            rows['_folder'] = rows['cluster'].map(self._folder_for_cluster)
            for folder in rows['_folder'].unique():
                (Path(output_dir) / folder).mkdir(parents=True, exist_ok=True)

            self.progress_queue.put(("status", f"Exporting {total:,} segments…"))
            self.progress_queue.put(("progress", 0))

            for _, row in rows.iterrows():
                if self.cancel_export.is_set():
                    break
                cid        = row['cluster']
                folder     = row['_folder']
                audio_path = row.get('audio_file_path', '')
                site_safe  = self._safe_filename(row['site'])
                audio_stem = self._safe_filename(Path(str(row['filename'])).stem) if row['filename'] else "unknown"
                start_s    = float(row['start_time'])
                end_s      = float(row['end_time'])
                out_name   = f"{site_safe}__{audio_stem}__{start_s:.1f}s_{end_s:.1f}s.wav"
                out_path   = Path(output_dir) / folder / out_name
                clip_written = False

                if audio_path and os.path.exists(str(audio_path)):
                    try:
                        y, sr = load_clip(audio_path, start_s, end_s - start_s)
                        sf.write(str(out_path), y, sr)
                        clip_written = True
                    except Exception as clip_err:
                        self.progress_queue.put(("status", f"Clip error: {str(clip_err)[:60]}"))

                manifest_rows.append({
                    'cluster': cid, 'cluster_folder': folder,
                    'custom_label': self.cluster_custom_labels.get(cid, ''),
                    'site': row['site'], 'source_file': row['filename'],
                    'start_time_s': start_s, 'end_time_s': end_s,
                    'duration_s': round(end_s - start_s, 2),
                    'audio_source_path': audio_path,
                    'exported_filename': out_name if clip_written else '',
                    'clip_written': clip_written,
                    'umap_x': row.get('umap_x', ''), 'umap_y': row.get('umap_y', ''),
                    'umap_z': row.get('umap_z', ''),
                    'iteration': self.iteration_count,
                })
                processed += 1
                if processed % 50 == 0:
                    self.progress_queue.put(("progress", int(processed / max(1, total) * 100)))
                    self.progress_queue.put(("status", f"Exporting… {processed:,}/{total:,}"))

            manifest_df = pd.DataFrame(manifest_rows)
            manifest_path = Path(output_dir) / "manifest.csv"
            manifest_df.to_csv(manifest_path, index=False)
            clips_written = int(manifest_df['clip_written'].sum()) if len(manifest_df) else 0
            self.progress_queue.put(("progress", 100))
            state = "cancelled" if self.cancel_export.is_set() else "complete"
            self.progress_queue.put(("success",
                f"Export {state}: {clips_written:,}/{total:,} clips, manifest -> {manifest_path}"))
        except Exception as e:
            import traceback
            self.progress_queue.put(("error", f"Export error: {e}\n{traceback.format_exc()[:300]}"))

    def export_manifest_only(self):
        if self.plot_data is None:
            messagebox.showwarning("Warning", "No clustering data available.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save Manifest CSV", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not save_path:
            return
        df = self.plot_data.copy()
        df['cluster_folder'] = df['cluster'].map(self._folder_for_cluster)
        df['custom_label']   = df['cluster'].map(self.cluster_custom_labels).fillna('')
        df['status'] = np.where(df['cluster'].isin(self.clusters_to_remove), 'removed',
                                np.where(df['cluster'] == -1, 'noise', 'active'))
        df['duration_s'] = (df['end_time'] - df['start_time']).round(2)
        df['iteration']  = self.iteration_count
        cols = ['cluster', 'cluster_folder', 'custom_label', 'status', 'site', 'filename',
                'start_time', 'end_time', 'duration_s', 'audio_file_path',
                'umap_x', 'umap_y', 'umap_z', 'iteration']
        df[[c for c in cols if c in df.columns]].to_csv(save_path, index=False)
        self.log_message(f"Manifest exported -> {Path(save_path).name}", "SUCCESS")

    # ─────────────────────────────────────────────────────────────────────────
    # PLOT
    # ─────────────────────────────────────────────────────────────────────────

    def is_3d(self):
        return (self.plot_dims_var.get() == "3D"
                and self.plot_data is not None
                and 'umap_z' in self.plot_data.columns)

    def on_dims_changed(self):
        if self.plot_dims_var.get() == "3D":
            if self.plot_data is None or 'umap_z' not in self.plot_data.columns:
                # A 3D plot needs a third UMAP dimension, which only exists if
                # the embedding was fitted with n_components >= 3
                if self.n_components_var.get() < 3:
                    self.n_components_var.set(3)
                self.plot_dims_var.set("2D")
                messagebox.showinfo(
                    "3D needs 3 components",
                    "The current embedding is 2-D.\n\n"
                    "n_components has been set to 3. Re-run clustering, then "
                    "switch to 3D.")
                return
        self.update_umap_plot()

    def _make_axes(self, fig):
        if self.is_3d():
            ax = fig.add_subplot(111, projection='3d')
            ax.view_init(elev=self.view_elev, azim=self.view_azim)
            return ax
        return fig.add_subplot(111)

    def _scat(self, ax, d, **kw):
        """Scatter in whichever projection is active."""
        if self.is_3d():
            return ax.scatter(d['umap_x'], d['umap_y'], d['umap_z'],
                              depthshade=False, **kw)
        return ax.scatter(d['umap_x'], d['umap_y'], **kw)

    def _generate_plot(self, fig, ax):
        three_d = self.is_3d()
        if not three_d:
            ax.set_facecolor('#f8f8f8')
        color_by = self.color_by_var.get()
        plot_data = self.plot_data

        max_pts = self.max_plot_var.get()
        plot_title = 'UMAP Embedding'
        if len(plot_data) > max_pts:
            plot_data = plot_data.sample(n=max_pts, random_state=42)
            plot_title += f' (showing {max_pts:,} of {len(self.plot_data):,} points)'
        plot_data = plot_data.copy()

        plot_data['custom_label'] = (plot_data['cluster']
                                     .map(self.cluster_custom_labels)
                                     .fillna('Unlabeled'))

        full_counts = self.plot_data['cluster'].value_counts()
        pt_size = 4 if three_d else 3

        if color_by == 'cluster':
            unique_clusters = sorted(plot_data['cluster'].unique())
            colors = plt.cm.tab20(np.linspace(0, 1, 20))
            show_legend = len(unique_clusters) <= 15
            for i, cluster in enumerate(unique_clusters):
                c_data = plot_data[plot_data['cluster'] == cluster]
                is_marked = cluster in self.clusters_to_remove
                label_text = (f'Noise ({len(c_data)})' if cluster == -1
                              else f'Cluster {cluster} ({len(c_data)})')
                if cluster in self.cluster_custom_labels:
                    label_text += f" - {self.cluster_custom_labels[cluster]}"
                if is_marked:
                    label_text = f"[x] {label_text}"
                self._scat(ax, c_data,
                           c='lightgray' if cluster == -1 else [colors[i % 20]],
                           label=label_text if show_legend else None,
                           alpha=0.15 if is_marked else 0.5, s=pt_size,
                           edgecolors='red' if is_marked else 'none', linewidths=0.5)
                if cluster != -1 and full_counts.get(cluster, 0) >= 20 and len(c_data):
                    lbl = self.cluster_custom_labels.get(cluster, str(cluster))
                    cx, cy = c_data['umap_x'].mean(), c_data['umap_y'].mean()
                    if three_d:
                        ax.text(cx, cy, c_data['umap_z'].mean(), lbl,
                                fontsize=7, ha='center', va='center', color='black')
                    else:
                        ax.annotate(lbl, xy=(cx, cy), fontsize=7, ha='center', va='center',
                                    color='black',
                                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                              alpha=0.6, edgecolor='none'))
            if show_legend:
                ax.legend(loc='upper left', frameon=True, fancybox=True,
                          shadow=True, fontsize='small')

        elif color_by == 'site':
            unique_sites = sorted(plot_data['site'].astype(str).unique())
            site_colors = plt.cm.tab20(np.linspace(0, 1, 20))
            for i, site in enumerate(unique_sites):
                sd_ = plot_data[plot_data['site'].astype(str) == site]
                self._scat(ax, sd_, c=[site_colors[i % 20]],
                           label=f'{site} ({len(sd_)})', alpha=0.5, s=pt_size)
            if len(unique_sites) <= 15:
                ax.legend(loc='upper left', fontsize='small')

        elif color_by == 'custom_label':
            unique_labels = sorted(plot_data['custom_label'].unique())
            label_colors = plt.cm.tab20(np.linspace(0, 1, 20))
            for i, label in enumerate(unique_labels):
                ld = plot_data[plot_data['custom_label'] == label]
                self._scat(ax, ld,
                           c=['lightgray' if label == 'Unlabeled' else label_colors[i % 20]],
                           label=f'{label} ({len(ld)})', alpha=0.5, s=pt_size)
            if len(unique_labels) <= 20:
                ax.legend(loc='upper left', fontsize='small')

        elif color_by == 'removal_status':
            marked_mask = plot_data['cluster'].isin(self.clusters_to_remove)
            unmarked = plot_data[~marked_mask]
            marked   = plot_data[marked_mask]
            if len(unmarked):
                self._scat(ax, unmarked, c='#377eb8',
                           label=f'Keep ({len(unmarked)})', alpha=0.5, s=pt_size)
            if len(marked):
                self._scat(ax, marked, c='red',
                           label=f'Remove ({len(marked)})', alpha=0.5, s=pt_size)
            ax.legend(loc='upper left', fontsize='small')

        ndim = self.embedding_nd.shape[1] if self.embedding_nd is not None else 2
        dim_note = f' [clustered in {ndim}-D]' if ndim > 2 else ''
        ax.set_title(f'{plot_title} (Iteration {self.iteration_count}){dim_note}',
                     fontsize=12, pad=15)
        ax.set_xlabel('UMAP 1')
        ax.set_ylabel('UMAP 2')
        if three_d:
            ax.set_zlabel('UMAP 3')
            ax.grid(True, linestyle='--', alpha=0.2)
        else:
            ax.grid(True, linestyle='--', alpha=0.3)
            fig.tight_layout()

    def update_umap_plot(self):
        if self.plot_data is None:
            messagebox.showinfo("Info", "Please run clustering first.")
            return
        self.umap_fig.clear()
        self.ax = self._make_axes(self.umap_fig)
        self._generate_plot(self.umap_fig, self.ax)
        self.umap_canvas.draw()

        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self.pop_out_fig.clear()
            self.pop_out_ax = self._make_axes(self.pop_out_fig)
            self._generate_plot(self.pop_out_fig, self.pop_out_ax)
            self.pop_out_canvas.draw()

        max_pts = self.max_plot_var.get()
        self.plot_data_sample = (self.plot_data.sample(n=max_pts, random_state=42)
                                 if len(self.plot_data) > max_pts
                                 else self.plot_data.copy())
        self.setup_clickable_audio()

    def save_umap_plot(self):
        if self.plot_data is None:
            messagebox.showinfo("Information", "No UMAP plot available.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save UMAP Plot", defaultextension=".png",
            filetypes=(("PNG files", "*.png"), ("All files", "*.*")))
        if save_path:
            try:
                temp_fig = Figure(figsize=(12, 8), dpi=300)
                temp_ax = self._make_axes(temp_fig)
                self._generate_plot(temp_fig, temp_ax)
                temp_fig.savefig(save_path, dpi=300, bbox_inches='tight')
                self.log_message(f"Plot saved to {save_path}", "SUCCESS")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save plot: {e}")

    def pop_out_plot(self):
        if self.plot_data is None:
            messagebox.showinfo("Info", "Please run clustering first.")
            return
        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self.pop_out_window.lift()
            return
        self.pop_out_window = tk.Toplevel(self.master)
        self.pop_out_window.title("UMAP Plot (Pop-out)")
        self.pop_out_window.geometry("1200x900")

        self.pop_out_fig = Figure(dpi=100)
        self.pop_out_canvas = FigureCanvasTkAgg(self.pop_out_fig, self.pop_out_window)
        self.pop_out_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.pop_out_ax = self._make_axes(self.pop_out_fig)
        self._generate_plot(self.pop_out_fig, self.pop_out_ax)
        self.pop_out_canvas.draw()
        self._attach_pop_out_click()

        self.pop_out_window.bind("<space>", lambda e: self.stop_playback())
        self.pop_out_window.protocol("WM_DELETE_WINDOW", self.on_pop_out_close)
        self.log_message("Opened plot in separate window", "SUCCESS")

    def on_pop_out_close(self):
        for cid in self.pop_out_click_conns:
            try:
                self.pop_out_canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self.pop_out_click_conns = []
        if self.pop_out_window:
            self.pop_out_window.destroy()
        self.pop_out_window = self.pop_out_fig = self.pop_out_canvas = None
        self.pop_out_ax = None

    # ─────────────────────────────────────────────────────────────────────────
    # CLICK TO PLAY
    # ─────────────────────────────────────────────────────────────────────────

    def setup_clickable_audio(self):
        for cid in self.click_conns:
            try:
                self.umap_canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self.click_conns = []

        if self.clickable_audio_var.get() and self.plot_data_sample is not None:
            self.click_conns = [
                self.umap_canvas.mpl_connect('button_press_event', self.on_press),
                self.umap_canvas.mpl_connect('button_release_event', self.on_release),
            ]
            hint = "🎵 Click a point to play"
            if self.is_3d():
                hint += " (drag to rotate)"
            self.clickable_status_var.set(hint)
        else:
            self.clickable_status_var.set("")

        if self.pop_out_window and self.pop_out_window.winfo_exists():
            self._attach_pop_out_click()

    def _attach_pop_out_click(self):
        for cid in self.pop_out_click_conns:
            try:
                self.pop_out_canvas.mpl_disconnect(cid)
            except Exception:
                pass
        self.pop_out_click_conns = []
        if self.clickable_audio_var.get() and self.plot_data_sample is not None:
            self.pop_out_click_conns = [
                self.pop_out_canvas.mpl_connect('button_press_event', self.on_press),
                self.pop_out_canvas.mpl_connect('button_release_event', self.on_release),
            ]

    def on_press(self, event):
        self._press_xy = (event.x, event.y)

    def on_release(self, event):
        ax = event.inaxes
        # Rotating a 3D axes is a drag, so only treat near-stationary
        # press/release pairs as a click
        if self._press_xy is not None and ax is not None:
            moved = np.hypot(event.x - self._press_xy[0], event.y - self._press_xy[1])
        else:
            moved = 999
        self._press_xy = None

        if ax is not None and self.is_3d():
            # Remember wherever the user rotated to
            self.view_elev, self.view_azim = float(ax.elev), float(ax.azim)

        if ax is None or self.plot_data_sample is None or moved > DRAG_TOLERANCE_PX:
            return
        if event.x is None or event.y is None:
            return

        xs = self.plot_data_sample['umap_x'].values
        ys = self.plot_data_sample['umap_y'].values

        if self.is_3d():
            zs = self.plot_data_sample['umap_z'].values
            x2, y2, _ = proj3d.proj_transform(xs, ys, zs, ax.get_proj())
            disp = ax.transData.transform(np.column_stack([x2, y2]))
        else:
            disp = ax.transData.transform(np.column_stack([xs, ys]))

        d = np.hypot(disp[:, 0] - event.x, disp[:, 1] - event.y)
        i = int(np.argmin(d))
        if d[i] > CLICK_RADIUS_PX:
            self.last_click_var.set("no point near click")
            return
        row = self.plot_data_sample.iloc[i]
        cid = int(row['cluster'])
        self.last_click_var.set(
            f"C{cid} | {row['filename']} @ {float(row['start_time']):.1f}s")
        self.select_cluster_in_dropdown(cid)
        if row['audio_file_path']:
            self.play_audio_segment(row['audio_file_path'], row)

    # ─────────────────────────────────────────────────────────────────────────
    # CLUSTER ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def assign_noise_to_clusters(self):
        if self.plot_data is None or self.embedding_nd is None:
            messagebox.showwarning("Warning", "No clustering data available.")
            return
        noise_mask = self.cluster_labels == -1
        n_noise = int(noise_mask.sum())
        if n_noise == 0:
            messagebox.showinfo("Info", "No noise points to assign.")
            return
        if (~noise_mask).sum() == 0:
            messagebox.showinfo("Info", "Everything is noise, nothing to assign to.")
            return
        if not messagebox.askyesno("Confirm", f"Assign {n_noise:,} noise points to nearest clusters?"):
            return
        try:
            self.log_message(f"Assigning {n_noise:,} noise points…", "PROGRESS")
            non_noise = ~noise_mask
            nbrs = NearestNeighbors(n_neighbors=1).fit(self.embedding_nd[non_noise])
            _, indices = nbrs.kneighbors(self.embedding_nd[noise_mask])
            new_labels = self.cluster_labels.copy()
            new_labels[noise_mask] = self.cluster_labels[non_noise][indices.flatten()]
            self._push_history()
            self.cluster_labels = new_labels
            self.plot_data['cluster'] = self.cluster_labels
            self.log_message(f"Assigned {n_noise:,} noise points", "SUCCESS")
            self.update_ui_after_clustering()
            self.autosave_master("noise_assigned")
        except Exception as e:
            messagebox.showerror("Error", f"Could not assign noise points: {e}")

    def keep_only_selected_cluster(self):
        cid = self._selected_cluster_id()
        if cid is None or cid == -1:
            messagebox.showwarning("Warning", "Select a real cluster first (not noise).")
            return
        others = set(np.unique(self.cluster_labels)) - {cid}
        if not others:
            messagebox.showinfo("Info", "This is the only cluster.")
            return
        label = self.cluster_custom_labels.get(cid, f"Cluster {cid}")
        if messagebox.askyesno("Confirm",
                f"Mark {len(others)} other cluster(s) for removal?\n"
                f"Only '{label}' will remain."):
            self.clusters_to_remove.update(others)
            self.log_message(f"Marked {len(others)} clusters for removal (keeping {label})", "SUCCESS")
            self.update_cluster_dropdown()
            self.update_labels_summary()
            self.update_umap_plot()
            self.autosave_master("keep_only")

    def apply_custom_label(self):
        cid = self._selected_cluster_id()
        if cid is None:
            return
        lab = self.custom_label_var.get().strip()
        if lab:
            self.cluster_custom_labels[cid] = lab
            self.log_message(f"Applied label '{lab}' to cluster {cid}", "SUCCESS")
        elif cid in self.cluster_custom_labels:
            del self.cluster_custom_labels[cid]
            self.log_message(f"Removed label from cluster {cid}", "INFO")
        self.update_cluster_dropdown(keep_selection=cid)
        self.update_labels_summary()
        self.update_umap_plot()
        self.autosave_master("label_applied")

    def toggle_removal_mark(self):
        cid = self._selected_cluster_id()
        if cid is None:
            return
        if self.mark_removal_var.get():
            self.clusters_to_remove.add(cid)
            self.log_message(f"Marked cluster {cid} for removal", "INFO")
        else:
            self.clusters_to_remove.discard(cid)
            self.log_message(f"Unmarked cluster {cid} for removal", "INFO")
        self.update_cluster_dropdown(keep_selection=cid)
        self.update_labels_summary()
        self.update_umap_plot()
        self.autosave_master("removal_toggled")

    def _selected_cluster_id(self):
        text = self.cluster_var.get()
        if not text:
            return None
        if text in self._cluster_option_map:
            return self._cluster_option_map[text]
        if "Noise" in text:
            return -1
        m = re.search(r'Cluster (-?\d+)', text)
        return int(m.group(1)) if m else None

    # ─────────────────────────────────────────────────────────────────────────
    # FILE BROWSING
    # ─────────────────────────────────────────────────────────────────────────

    def browse_embed_path(self):
        d = filedialog.askdirectory(title="Select Embeddings Directory")
        if d:
            self.embed_path_var.set(d)

    def browse_audio_path(self):
        d = filedialog.askdirectory(title="Select Audio Directory")
        if d:
            self.audio_path_var.set(d)

    # ─────────────────────────────────────────────────────────────────────────
    # SCAN
    # ─────────────────────────────────────────────────────────────────────────

    def scan_files(self):
        ep, ap = self.embed_path_var.get(), self.audio_path_var.get()
        if not os.path.exists(ep) or not os.path.exists(ap):
            messagebox.showerror("Error", "Invalid paths")
            return
        threading.Thread(target=self._scan_files_thread, daemon=True).start()

    def _scan_files_thread(self):
        try:
            self.progress_queue.put(("status", "Scanning embedding files…"))
            embed_path = Path(self.embed_path_var.get())
            e_files = []
            for f in embed_path.rglob(self.embed_pattern_var.get()):
                if f.is_file():
                    rel_path = f.relative_to(embed_path)
                    site = rel_path.parts[0] if len(rel_path.parts) > 1 else "unknown"
                    e_files.append({'full_path': str(f),
                                    'name_without_ext': f.stem,
                                    'site': site})
            self.progress_queue.put(("status", f"Found {len(e_files):,} embedding files"))

            self.progress_queue.put(("status", "Scanning audio files…"))
            audio_path = Path(self.audio_path_var.get())
            a_exact, a_norm = {}, {}
            for ext in self.audio_ext_var.get().split(','):
                ext = ext.strip()
                if not ext:
                    continue
                for f in audio_path.rglob(f"*{ext}"):
                    if f.is_file():
                        a_exact.setdefault(f.stem.lower(), str(f))
                        a_norm.setdefault(norm_key(f.stem), str(f))
            self.progress_queue.put(("status", f"Found {len(a_exact):,} audio files"))

            self.file_mapping = {}
            for f in e_files:
                stem = f['name_without_ext']
                audio_file = (a_exact.get(stem.lower())
                              or a_norm.get(norm_key(stem))
                              or a_norm.get(norm_key(stem.split('.')[0])))
                self.file_mapping[f['full_path']] = {'audio': audio_file, 'site': f['site']}

            matched = sum(1 for v in self.file_mapping.values() if v['audio'])
            self.progress_queue.put(("success",
                f"Mapped {matched:,}/{len(self.file_mapping):,} embedding files to audio"))
            if matched == 0:
                self.progress_queue.put(("error", "No matching audio files found. Check patterns and extensions."))
        except Exception as e:
            self.progress_queue.put(("error", f"Scan error: {e}"))

    # ─────────────────────────────────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────────────────────────────────

    def load_data(self):
        if not self.file_mapping:
            messagebox.showinfo("Info", "Please scan files first.")
            return
        threading.Thread(target=self._load_data_thread, daemon=True).start()

    def _load_data_thread(self):
        try:
            self.progress_queue.put(("status", "Loading embeddings…"))
            rng = np.random.default_rng(self.seed_var.get())

            site_files = {}
            for epath, info in self.file_mapping.items():
                site_files.setdefault(info['site'], []).append((epath, info))
            max_files = self.max_files_var.get()
            if max_files:
                for site in site_files:
                    site_files[site] = site_files[site][:max_files]

            all_e, all_m = [], []
            total_files = sum(len(v) for v in site_files.values())
            processed, failed = 0, 0

            for site, files in site_files.items():
                for epath, info in files:
                    try:
                        with open(epath, 'r') as f:
                            first_line = f.readline().strip()
                        if '\t' in first_line:
                            df = pd.read_csv(epath, sep='\t', header=None)
                            embeddings = np.array(
                                [np.fromstring(s, sep=',') for s in df.iloc[:, 2].astype(str)],
                                dtype=np.float32)
                        else:
                            df = pd.read_csv(epath, header=None)
                            embeddings = df.iloc[:, 2:].values.astype(np.float32)

                        start_times = df.iloc[:, 0].values
                        end_times   = df.iloc[:, 1].values

                        sample_rate = self.sample_rate_var.get()
                        if sample_rate < 1.0 and len(embeddings) > 1:
                            n_samples = max(1, int(len(embeddings) * sample_rate))
                            idx = np.sort(rng.choice(len(embeddings), n_samples, replace=False))
                            embeddings  = embeddings[idx]
                            start_times = start_times[idx]
                            end_times   = end_times[idx]

                        filename = (Path(info['audio']).name if info['audio']
                                    else Path(epath).name)
                        all_e.append(embeddings)
                        all_m.append(pd.DataFrame({
                            'site': site, 'filename': filename,
                            'start_time': start_times, 'end_time': end_times,
                            'audio_file_path': info['audio']
                        }))
                        processed += 1
                        if processed % 25 == 0:
                            self.progress_queue.put(("progress", int(processed / total_files * 100)))
                            self.progress_queue.put(("status", f"Processed {processed:,}/{total_files:,} files…"))
                    except Exception as e:
                        failed += 1
                        if failed <= 5:
                            self.progress_queue.put(
                                ("status", f"Error loading {Path(epath).name}: {str(e)[:50]}"))
                        continue

            if all_e:
                self.embeddings = np.vstack(all_e)
                self.metadata   = pd.concat(all_m, ignore_index=True)
                del all_e, all_m
                gc.collect()
                self.master_df = None
                self.autosave_path = None
                mem_gb = self.embeddings.nbytes / (1024 ** 3)
                self.progress_queue.put(("success",
                    f"Loaded {len(self.metadata):,} embeddings x {self.embeddings.shape[1]} dims "
                    f"from {processed:,} files ({mem_gb:.2f} GB, {failed} failed)"))
                self.progress_queue.put(("data_loaded", None))
            else:
                self.progress_queue.put(("error", "No valid embeddings loaded"))
        except Exception as e:
            self.progress_queue.put(("error", f"Load error: {e}"))

    # ─────────────────────────────────────────────────────────────────────────
    # CLUSTERING
    # ─────────────────────────────────────────────────────────────────────────

    def run_clustering(self):
        if self.embeddings is None:
            messagebox.showinfo("Info", "Please load data first.")
            return
        n, d = self.embeddings.shape
        est_gb = (n * d * 4 * 3) / (1024 ** 3)
        avail_gb = psutil.virtual_memory().available / (1024 ** 3)
        if est_gb > avail_gb * 0.6:
            if not messagebox.askyesno(
                    "Memory warning",
                    f"{n:,} rows x {d} dims needs roughly {est_gb:.1f} GB, "
                    f"but only {avail_gb:.1f} GB is free.\n\n"
                    "Consider turning PCA on or lowering the sample rate.\n\nProceed anyway?"):
                return
        threading.Thread(target=self.clustering_process, daemon=True).start()

    def clustering_process(self):
        try:
            self.progress_queue.put(("status", "Standardising embeddings…"))
            x = StandardScaler().fit_transform(self.embeddings).astype(np.float32)

            if self.use_pca_var.get() and x.shape[1] > self.pca_components_var.get():
                self.progress_queue.put(("status", "Running PCA…"))
                x = PCA(n_components=self.pca_components_var.get(),
                        random_state=42).fit_transform(x).astype(np.float32)

            n_comp = max(2, self.n_components_var.get())
            deterministic = self.deterministic_var.get()
            self.progress_queue.put((
                "status",
                f"Running UMAP -> {n_comp}-D "
                f"({'deterministic, 1 core' if deterministic else 'parallel'})…"))

            reducer = umap.UMAP(
                n_neighbors=self.n_neighbors_var.get(),
                min_dist=self.min_dist_var.get(),
                metric=self.umap_metric_var.get(),
                spread=self.spread_var.get(),
                n_components=n_comp,
                random_state=42 if deterministic else None,
                n_jobs=1 if deterministic else -1,
                low_memory=True, verbose=False
            )
            self.embedding_nd = reducer.fit_transform(x).astype(np.float32)
            self.embedding_2d = self.embedding_nd[:, :2]
            del x
            gc.collect()

            self.progress_queue.put(("status", "Running HDBSCAN…"))
            self.cluster_labels = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size_var.get(),
                min_samples=self.min_samples_var.get(),
                cluster_selection_epsilon=self.epsilon_var.get(),
                cluster_selection_method=self.selection_method_var.get(),
                metric=self.hdbscan_metric_var.get(),
                core_dist_n_jobs=-1
            ).fit_predict(self.embedding_nd.astype(np.float64))

            self.plot_data = self.metadata.copy()
            self.plot_data['umap_x'] = self.embedding_nd[:, 0]
            self.plot_data['umap_y'] = self.embedding_nd[:, 1]
            if self.embedding_nd.shape[1] >= 3:
                self.plot_data['umap_z'] = self.embedding_nd[:, 2]
            self.plot_data['cluster'] = self.cluster_labels

            n_clusters = len(set(self.cluster_labels)) - (1 if -1 in self.cluster_labels else 0)
            n_noise = int((self.cluster_labels == -1).sum())
            pct = n_noise / len(self.cluster_labels) * 100
            self.progress_queue.put(("success",
                f"Found {n_clusters} clusters ({n_noise:,} noise, {pct:.1f}%)"))
            self.progress_queue.put(("update_ui", None))
        except Exception as e:
            import traceback
            self.progress_queue.put(("error", f"Clustering error: {e}\n{traceback.format_exc()[:300]}"))

    # ─────────────────────────────────────────────────────────────────────────
    # UI UPDATE HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def update_ui_after_clustering(self):
        if self.master_df is None:
            self._init_master_df()
        self._sync_master_df_after_cluster()
        # Fall back to 2D if the new embedding has no third dimension
        if self.plot_dims_var.get() == "3D" and 'umap_z' not in self.plot_data.columns:
            self.plot_dims_var.set("2D")
        self.update_cluster_dropdown()
        if self.cluster_dropdown['values']:
            self.cluster_dropdown.current(0)
            self.on_cluster_selected(None)
        self.update_labels_summary()
        self.update_umap_plot()
        self.autosave_master("cluster_complete")

    def update_ui_after_data_load(self):
        self.log_message(f"Data ready: {len(self.metadata):,} embeddings", "SUCCESS")

    def on_cluster_selected(self, event):
        cid = self._selected_cluster_id()
        if cid is None:
            return
        self.mark_removal_var.set(cid in self.clusters_to_remove)
        self.custom_label_var.set(self.cluster_custom_labels.get(cid, ""))
        self.update_cluster_stats()

    def update_cluster_dropdown(self, keep_selection=None):
        if self.cluster_labels is None:
            return
        opts = []
        self._cluster_option_map = {}
        counts = pd.Series(self.cluster_labels).value_counts()
        for c in sorted(np.unique(self.cluster_labels)):
            count = int(counts.get(c, 0))
            text = f"Noise ({count})" if c == -1 else f"Cluster {c} ({count})"
            if c in self.cluster_custom_labels:
                text += f" - {self.cluster_custom_labels[c]}"
            if c in self.clusters_to_remove:
                text = "[x] " + text
            opts.append(text)
            self._cluster_option_map[text] = int(c)
        self.cluster_dropdown['values'] = opts
        self.cluster_dropdown['state'] = 'readonly'
        if keep_selection is not None:
            for text, cid in self._cluster_option_map.items():
                if cid == keep_selection:
                    self.cluster_var.set(text)
                    break

    def select_cluster_in_dropdown(self, cid):
        for text, mapped in self._cluster_option_map.items():
            if mapped == cid:
                self.cluster_var.set(text)
                self.on_cluster_selected(None)
                return

    def update_labels_summary(self):
        n_clusters = (len(set(self.cluster_labels)) - (1 if -1 in self.cluster_labels else 0)
                      if self.cluster_labels is not None else 0)
        s  = f"Iteration: {self.iteration_count}\n"
        s += f"Clusters: {n_clusters}\n"
        s += f"Labelled: {len(self.cluster_custom_labels)}\n"
        s += f"Marked for Removal: {len(self.clusters_to_remove)}\n"
        if self.cluster_custom_labels:
            s += "\nLabels:\n"
            for cid, label in list(self.cluster_custom_labels.items())[:8]:
                s += f"  C{cid}: {label}\n"
        self.labels_text.delete(1.0, tk.END)
        self.labels_text.insert(tk.END, s)

    def update_cluster_stats(self):
        cid = self._selected_cluster_id()
        if cid is None or self.plot_data is None:
            return
        c_data = self.plot_data[self.plot_data['cluster'] == cid]
        s  = f"Cluster: {cid if cid != -1 else 'Noise'}\n"
        if cid in self.cluster_custom_labels:
            s += f"Label: {self.cluster_custom_labels[cid]}\n"
        s += f"Points: {len(c_data):,} ({len(c_data)/len(self.plot_data)*100:.1f}%)\n"
        if cid in self.clusters_to_remove:
            s += "MARKED FOR REMOVAL\n"
        s += f"\nSites: {c_data['site'].nunique()}\n"
        for site, count in c_data['site'].value_counts().head(6).items():
            s += f"  {site}: {count:,}\n"
        s += f"\nFiles: {c_data['filename'].nunique():,}\n"
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, s)

    def update_samples(self):
        for w in self.spectro_frame.winfo_children():
            w.destroy()
        cid = self._selected_cluster_id()
        if cid is None or self.plot_data is None:
            return
        c_data = self.plot_data[self.plot_data['cluster'] == cid]
        if len(c_data) == 0:
            return
        sample_size = min(self.sample_size_var.get(), len(c_data))
        samples = c_data.sample(sample_size, random_state=np.random.randint(0, 9999))
        for i, (_, r) in enumerate(samples.iterrows()):
            f = ttk.Frame(self.spectro_frame, padding=5, relief="ridge", borderwidth=1)
            f.grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky="nsew")
            ttk.Label(f, text=f"Sample {i+1}", font=('Arial', 10, 'bold')).pack()
            ttk.Label(f, text=f"Site: {r['site']}").pack()
            ttk.Label(f, text=f"File: {r['filename']}").pack()
            ttk.Label(f, text=f"Time: {r['start_time']:.1f}s - {r['end_time']:.1f}s").pack()
            if r['audio_file_path'] and os.path.exists(str(r['audio_file_path'])):
                try:
                    y, sr = load_clip(r['audio_file_path'], float(r['start_time']),
                                      float(r['end_time']) - float(r['start_time']))
                    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64)
                    mel_db = librosa.power_to_db(mel, ref=np.max)
                    thumb_fig = Figure(figsize=(2.8, 1.4), dpi=72)
                    thumb_ax = thumb_fig.add_subplot(111)
                    librosa.display.specshow(mel_db, sr=sr, ax=thumb_ax,
                                             x_axis='time', y_axis='mel', cmap='magma')
                    thumb_ax.set_xlabel('')
                    thumb_ax.set_ylabel('')
                    thumb_ax.tick_params(labelsize=5)
                    thumb_fig.tight_layout(pad=0.2)
                    thumb_canvas = FigureCanvasTkAgg(thumb_fig, f)
                    thumb_canvas.draw()
                    thumb_canvas.get_tk_widget().pack(pady=2)
                except Exception:
                    pass
                ttk.Button(f, text="▶️ Play",
                           command=lambda path=r['audio_file_path'], row=r:
                               self.play_audio_segment(path, row)).pack(pady=3)
            else:
                ttk.Button(f, text="Not found", state="disabled").pack(pady=3)

    # ─────────────────────────────────────────────────────────────────────────
    # PLAYBACK
    # ─────────────────────────────────────────────────────────────────────────

    def play_audio_segment(self, path, row):
        if not path or not os.path.exists(str(path)):
            self.log_message("Audio file not found", "ERROR")
            return
        pad = float(self.play_pad_var.get())
        start_s = max(0.0, float(row['start_time']) - pad)
        end_s = float(row['end_time']) + pad
        threading.Thread(target=self._play_thread,
                         args=(str(path), start_s, end_s, str(row.get('filename', ''))),
                         daemon=True).start()

    def _play_thread(self, path, start_s, end_s, name):
        try:
            y, sr = load_clip(path, start_s, end_s - start_s)
            sd.stop()
            sd.play(y, sr)
            self.log_message(f"Playing {name} [{start_s:.1f}-{end_s:.1f}s]", "INFO")
        except Exception as e:
            self.log_message(f"Play error: {str(e)[:80]}", "ERROR")

    def stop_playback(self):
        sd.stop()

    # ─────────────────────────────────────────────────────────────────────────
    # SAVE / LOAD STATE
    # ─────────────────────────────────────────────────────────────────────────

    def save_state(self):
        if self.plot_data is None:
            messagebox.showwarning("Warning", "No data to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.plot_data.to_csv(path, index=False)
            state = {
                'custom_labels':      {str(k): v for k, v in self.cluster_custom_labels.items()},
                'clusters_to_remove': [int(c) for c in self.clusters_to_remove],
                'iteration_count':    self.iteration_count,
                'n_components':       int(self.n_components_var.get()),
                'view_elev':          self.view_elev,
                'view_azim':          self.view_azim,
            }
            with open(path.replace('.csv', '_state.json'), 'w') as f:
                json.dump(state, f, indent=2)
            if self.embedding_nd is not None:
                np.savez_compressed(path.replace('.csv', '_umap.npz'),
                                    embedding_nd=self.embedding_nd)
            self.log_message(f"Saved to {path} (+ state, + UMAP coords)", "SUCCESS")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_state(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            self.plot_data = pd.read_csv(path)
            self.embedding_2d = self.plot_data[['umap_x', 'umap_y']].values
            self.cluster_labels = self.plot_data['cluster'].values
            npz = path.replace('.csv', '_umap.npz')
            self.embedding_nd = (np.load(npz)['embedding_nd']
                                 if os.path.exists(npz) else self.embedding_2d)
            state_path = path.replace('.csv', '_state.json')
            if os.path.exists(state_path):
                with open(state_path) as f:
                    state = json.load(f)
                self.cluster_custom_labels = {int(k): v for k, v in state.get('custom_labels', {}).items()}
                self.clusters_to_remove = set(state.get('clusters_to_remove', []))
                self.iteration_count = state.get('iteration_count', 0)
                self.view_elev = state.get('view_elev', self.view_elev)
                self.view_azim = state.get('view_azim', self.view_azim)
            self.metadata = self.plot_data.drop(
                columns=[c for c in ('umap_x', 'umap_y', 'umap_z', 'cluster', 'custom_label')
                         if c in self.plot_data.columns]).copy()
            self.master_df = None
            self.embeddings = None
            self.log_message(f"Loaded from {path}", "SUCCESS")
            self.log_message("Note: raw embeddings are not restored, so re-clustering "
                             "needs a fresh Load", "INFO")
            self.update_ui_after_clustering()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # RE-CLUSTER / UNDO
    # ─────────────────────────────────────────────────────────────────────────

    def _push_history(self):
        self.clustering_history.append({
            'plot_data':          self.plot_data.copy(),
            'embeddings':         self.embeddings,
            'metadata':           self.metadata,
            'embedding_nd':       self.embedding_nd,
            'custom_labels':      self.cluster_custom_labels.copy(),
            'clusters_to_remove': self.clusters_to_remove.copy(),
            'iteration':          self.iteration_count
        })
        if len(self.clustering_history) > MAX_HISTORY:
            self.clustering_history.pop(0)

    def recluster_filtered(self):
        if self.plot_data is None or not self.clusters_to_remove:
            messagebox.showinfo("Info", "No clusters marked for removal.")
            return
        if self.embeddings is None:
            messagebox.showwarning("Warning", "Raw embeddings not in memory. Reload data first.")
            return
        n_remove = len(self.clusters_to_remove)
        n_rows = int(self.plot_data['cluster'].isin(self.clusters_to_remove).sum())
        if not messagebox.askyesno("Confirm",
                f"Re-cluster with {n_remove} cluster(s) removed ({n_rows:,} rows)?"):
            return
        self._push_history()
        self._mark_removed_in_master(self.clusters_to_remove, reason="recluster")
        keep = (~self.plot_data['cluster'].isin(self.clusters_to_remove)).values
        self.embeddings = self.embeddings[keep]
        self.metadata = self.metadata.iloc[keep].reset_index(drop=True)
        self.clusters_to_remove.clear()
        self.cluster_custom_labels.clear()
        self.iteration_count += 1
        self.autosave_master("pre_recluster")
        gc.collect()
        self.run_clustering()

    def undo_last_removal(self):
        if not self.clustering_history:
            messagebox.showinfo("Info", "Nothing to undo.")
            return
        if not messagebox.askyesno("Confirm", "Restore previous state?"):
            return
        last = self.clustering_history.pop()
        self.plot_data             = last['plot_data']
        self.embeddings            = last['embeddings']
        self.metadata              = last['metadata']
        self.embedding_nd          = last['embedding_nd']
        self.cluster_custom_labels = last['custom_labels']
        self.clusters_to_remove    = last['clusters_to_remove']
        self.iteration_count       = last['iteration']
        self.embedding_2d          = self.plot_data[['umap_x', 'umap_y']].values
        self.cluster_labels        = self.plot_data['cluster'].values
        self.log_message("State restored (data, embeddings and labels)", "SUCCESS")
        self.update_ui_after_clustering()
        self.autosave_master("undo")

    # ─────────────────────────────────────────────────────────────────────────
    # LOGGING / STATUS
    # ─────────────────────────────────────────────────────────────────────────

    def log_message(self, m, level="INFO"):
        if threading.current_thread() is not threading.main_thread():
            self.progress_queue.put(("log", (m, level)))
            return
        prefix = f"[{level}] " if level != "INFO" else ""
        self.log_text.insert(tk.END, f"{prefix}{m}\n")
        self.log_text.see(tk.END)

    def create_status_bar(self):
        status_frame = ttk.Frame(self.master)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status_frame, textvariable=self.status_var,
                  relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress_var = tk.IntVar()
        ttk.Progressbar(status_frame, variable=self.progress_var,
                        length=200).pack(side=tk.RIGHT, padx=10)

    def check_progress_queue(self):
        try:
            count = 0
            while count < 25:
                m, d = self.progress_queue.get_nowait()
                if m == "update_ui":
                    self.update_ui_after_clustering()
                elif m == "data_loaded":
                    self.update_ui_after_data_load()
                elif m == "log":
                    self.log_message(d[0], d[1])
                elif m == "status":
                    self.log_message(d, "PROGRESS")
                    self.status_var.set(d)
                elif m == "success":
                    self.log_message(d, "SUCCESS")
                    self.status_var.set(d)
                elif m == "error":
                    self.log_message(d, "ERROR")
                    messagebox.showerror("Error", d)
                elif m == "progress":
                    self.progress_var.set(d)
                    self.local_progress_var.set(d)
                count += 1
        except queue.Empty:
            pass
        self.master.after(200, self.check_progress_queue)

    def on_closing(self):
        self.cancel_export.set()
        sd.stop()
        for cid in self.click_conns:
            try:
                self.umap_canvas.mpl_disconnect(cid)
            except Exception:
                pass
        for cid in self.pop_out_click_conns:
            try:
                self.pop_out_canvas.mpl_disconnect(cid)
            except Exception:
                pass
        if self.pop_out_window:
            self.pop_out_window.destroy()
        self.master.destroy()


# ─────────────────────────────────────────────────────────────────────────────

def start_gui():
    print("starting pardalote")
    root = tk.Tk()
    app = EmbeddingClusteringGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    start_gui()