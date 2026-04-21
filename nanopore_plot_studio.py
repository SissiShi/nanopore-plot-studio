
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd

APP_TITLE = "Nanopore Plot Studio"
PLOT_TYPES = ["Histogram", "Scatter", "2D Histogram", "Hexbin", "CDF", "Time Plot"]

NUMERIC_PRIORITY = [
    "deli", "frac", "dwell", "dt", "mean", "stdev", "skewness", "kurtosis",
    "index", "global_startpt", "global_endpt", "local_startpt", "local_endpt",
    "offset_first_min", "stdev_tt", "skewness_tt", "kurtosis_tt", "N_child", "seg",
]

DISPLAY_NAME_MAP = {
    "deli": "ΔI",
    "frac": "Fractional Current Blockage",
    "dwell": "Dwell time",
    "dt": "Inter-event interval",
    "stdev": "Stdev",
    "skewness": "Skewness",
    "kurtosis": "Kurtosis",
    "mean": "Mean current",
    "index": "Event index",
    "global_startpt": "Global start",
    "global_endpt": "Global end",
}

UNIT_OPTIONS = {
    "deli": [("A", 1.0), ("nA", 1e9), ("pA", 1e12)],
    "dwell": [("µs", 1.0), ("ms", 1e-3), ("s", 1e-6)],
    "dt": [("s", 1.0), ("ms", 1e3), ("µs", 1e6)],
    "frac": [("fraction", 1.0), ("%", 100.0)],
    "stdev": [("raw", 1.0)],
    "skewness": [("raw", 1.0)],
    "kurtosis": [("raw", 1.0)],
    "mean": [("A", 1.0), ("nA", 1e9), ("pA", 1e12)],
}
DEFAULT_UNITS = {
    "deli": "pA",
    "dwell": "µs",
    "dt": "s",
    "frac": "fraction",
    "stdev": "raw",
    "skewness": "raw",
    "kurtosis": "raw",
    "mean": "pA",
}


def df_has_few_unique(series: pd.Series, threshold: int = 30) -> bool:
    try:
        return series.dropna().nunique() <= threshold
    except Exception:
        return False


class ScrollableFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg="#eef2f6")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="Pane.TFrame")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Enter>", self._bind_mousewheel)
        self.inner.bind("<Leave>", self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def _bind_mousewheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class NanoporePlotGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1710x1020")
        self.root.minsize(1420, 920)

        self.df = None
        self.filtered_df = None
        self.current_file = None
        self.numeric_columns = []
        self.all_columns = []

        # hard binding for presets, independent of dropdown display logic
        self.forced_raw_x = None
        self.forced_raw_y = None

        self._configure_style()
        self._build_variables()
        self._build_layout()
        self._update_status("Open a txt/csv/tsv event table to begin.")

    def _configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(bg="#edf2f7")
        style.configure("TFrame", background="#edf2f7")
        style.configure("Pane.TFrame", background="#edf2f7")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("SoftCard.TFrame", background="#ffffff", relief="flat")
        style.configure("SidebarCard.TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("SidebarCard.TLabelframe.Label", background="#ffffff", foreground="#243447", font=("Segoe UI Semibold", 10))
        style.configure("TLabel", background="#edf2f7", foreground="#243447", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#ffffff", foreground="#334155", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#edf2f7", foreground="#0f172a", font=("Segoe UI Semibold", 19))
        style.configure("SubHeader.TLabel", background="#edf2f7", foreground="#64748b", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=7)
        style.configure("Small.TButton", font=("Segoe UI", 9), padding=5)
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=8)
        style.configure("TCheckbutton", background="#ffffff", font=("Segoe UI", 10))
        style.configure("Treeview", font=("Consolas", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))

    def _build_variables(self):
        self.plot_type_var = tk.StringVar(value="Histogram")
        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()
        self.filter_col_var = tk.StringVar()
        self.category_col_var = tk.StringVar(value="")
        self.category_value_var = tk.StringVar(value="All")

        self.x_unit_var = tk.StringVar(value="")
        self.y_unit_var = tk.StringVar(value="")
        self.x_transform_var = tk.StringVar(value="none")

        self.bins_var = tk.StringVar(value="50")
        self.hexbin_size_var = tk.StringVar(value="40")
        self.fig_w_var = tk.StringVar(value="7.5")
        self.fig_h_var = tk.StringVar(value="5.5")
        self.point_size_var = tk.StringVar(value="18")
        self.alpha_var = tk.StringVar(value="0.55")

        self.title_var = tk.StringVar(value="")
        self.x_label_var = tk.StringVar(value="")
        self.y_label_var = tk.StringVar(value="")

        self.xmin_var = tk.StringVar(value="")
        self.xmax_var = tk.StringVar(value="")
        self.ymin_var = tk.StringVar(value="")
        self.ymax_var = tk.StringVar(value="")
        self.filter_min_var = tk.StringVar(value="")
        self.filter_max_var = tk.StringVar(value="")

        self.kde_var = tk.BooleanVar(value=False)
        self.use_xlog_var = tk.BooleanVar(value=False)
        self.use_ylog_var = tk.BooleanVar(value=False)
        self.density_var = tk.BooleanVar(value=False)
        self.dropna_var = tk.BooleanVar(value=True)
        self.grid_var = tk.BooleanVar(value=False)
        self.color_by_category_var = tk.BooleanVar(value=False)

        self.export_dpi_var = tk.StringVar(value="300")
        self.export_format_var = tk.StringVar(value="png")
        self.transparent_bg_var = tk.BooleanVar(value=False)

        self.tick_direction_var = tk.StringVar(value="in")
        self.show_top_ticks_var = tk.BooleanVar(value=False)
        self.show_right_ticks_var = tk.BooleanVar(value=False)
        self.show_top_spine_var = tk.BooleanVar(value=True)
        self.show_right_spine_var = tk.BooleanVar(value=True)

        self.line_width_var = tk.StringVar(value="1.5")
        self.edge_width_var = tk.StringVar(value="0.8")
        self.marker_shape_var = tk.StringVar(value="o")
        self.hist_filled_var = tk.BooleanVar(value=True)

        self.plot_color_var = tk.StringVar(value="#4f83cc")
        self.edge_color_var = tk.StringVar(value="#1f1f1f")
        self.bg_color_var = tk.StringVar(value="#ffffff")

    def _build_layout(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="Nanopore Plot GUI", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="Now with stricter raw-column binding and explicit unit selectors.", style="SubHeader.TLabel").pack(side="left", padx=(12, 0))

        main = ttk.Frame(outer)
        main.pack(fill="both", expand=True)

        sidebar_shell = ttk.Frame(main, style="Card.TFrame")
        sidebar_shell.pack(side="left", fill="y", padx=(0, 14))
        sidebar_shell.configure(width=540)
        sidebar_shell.pack_propagate(False)

        self.sidebar = ScrollableFrame(sidebar_shell)
        self.sidebar.pack(fill="both", expand=True)

        right = ttk.Frame(main, style="Card.TFrame", padding=12)
        right.pack(side="right", fill="both", expand=True)

        self._build_left_panel(self.sidebar.inner)
        self._build_right_panel(right)

        status_frame = ttk.Frame(outer, style="Card.TFrame", padding=(10, 8))
        status_frame.pack(fill="x", pady=(10, 0))
        self.status_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.status_var, background="#ffffff", font=("Segoe UI", 10)).pack(anchor="w")

    def _build_left_panel(self, parent):
        file_box = ttk.LabelFrame(parent, text="File", style="SidebarCard.TLabelframe", padding=12)
        file_box.pack(fill="x", pady=(0, 10))
        top = ttk.Frame(file_box, style="Card.TFrame")
        top.pack(fill="x")
        self.file_label = ttk.Label(top, text="No file loaded", style="Card.TLabel", wraplength=340)
        self.file_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(top, text="Open File", style="Small.TButton", command=self.open_file).pack(side="right")
        info = ttk.Frame(file_box, style="Card.TFrame")
        info.pack(fill="x", pady=(6, 0))
        self.rows_label = ttk.Label(info, text="Rows: -", style="Card.TLabel")
        self.rows_label.pack(side="left")
        self.filtered_rows_label = ttk.Label(info, text="Filtered: -", style="Card.TLabel")
        self.filtered_rows_label.pack(side="right")
        self.raw_mapping_label = ttk.Label(file_box, text="Raw X: - | Raw Y: -", style="Card.TLabel")
        self.raw_mapping_label.pack(anchor="w", pady=(6, 0))
        self.range_label = ttk.Label(file_box, text="Current plot values: -", style="Card.TLabel")
        self.range_label.pack(anchor="w", pady=(4, 0))

        action_box = ttk.LabelFrame(parent, text="Actions", style="SidebarCard.TLabelframe", padding=12)
        action_box.pack(fill="x", pady=(0, 10))
        r1 = ttk.Frame(action_box, style="Card.TFrame")
        r1.pack(fill="x")
        ttk.Button(r1, text="Plot", style="Accent.TButton", command=self.plot_data).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(r1, text="Save Figure", command=self.save_figure).pack(side="left", expand=True, fill="x", padx=(5, 0))
        r2 = ttk.Frame(action_box, style="Card.TFrame")
        r2.pack(fill="x", pady=(8, 0))
        ttk.Button(r2, text="Apply Filters", command=self.apply_filters).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(r2, text="Reset Filters", command=self.reset_filters).pack(side="left", expand=True, fill="x", padx=(5, 0))
        ttk.Button(action_box, text="Export Filtered Table", command=self.export_filtered_table).pack(fill="x", pady=(8, 0))

        preset_box = ttk.LabelFrame(parent, text="Presets", style="SidebarCard.TLabelframe", padding=12)
        preset_box.pack(fill="x", pady=(0, 10))
        ttk.Label(preset_box, text="Scatter panels vs log dwell", style="Card.TLabel").pack(anchor="w", pady=(0, 6))
        p1 = ttk.Frame(preset_box, style="Card.TFrame")
        p1.pack(fill="x")
        ttk.Button(p1, text="Blockade", command=self.preset_frac_vs_logdwell).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(p1, text="Stdev", command=self.preset_stdev_vs_logdwell).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(p1, text="Skewness", command=self.preset_skewness_vs_logdwell).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(p1, text="Kurtosis", command=self.preset_kurtosis_vs_logdwell).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Separator(preset_box, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(preset_box, text="Matching histograms", style="Card.TLabel").pack(anchor="w", pady=(0, 6))
        p2 = ttk.Frame(preset_box, style="Card.TFrame")
        p2.pack(fill="x")
        ttk.Button(p2, text="Frac Hist", command=self.preset_frac_hist).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(p2, text="ΔI Hist", command=self.preset_deli_hist).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(p2, text="Dwell Hist", command=self.preset_log_dwell_hist).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(p2, text="dt Hist", command=self.preset_dt_hist).pack(side="left", fill="x", expand=True, padx=(4, 0))

        plot_box = ttk.LabelFrame(parent, text="Plot Controls", style="SidebarCard.TLabelframe", padding=12)
        plot_box.pack(fill="x", pady=(0, 10))
        self.plot_type_combo = self._add_labeled_combo(plot_box, "Plot type", self.plot_type_var, PLOT_TYPES, self.on_plot_type_changed)
        self.x_combo = self._add_labeled_combo(plot_box, "X column", self.x_var, [], self.on_x_changed)
        self.y_combo = self._add_labeled_combo(plot_box, "Y column", self.y_var, [], self.on_y_changed)

        units_row = ttk.Frame(plot_box, style="Card.TFrame")
        units_row.pack(fill="x", pady=(4, 0))
        self.x_unit_combo = self._add_labeled_combo_inline(units_row, "X unit", self.x_unit_var, [""], self.on_label_related_change)
        self.y_unit_combo = self._add_labeled_combo_inline(units_row, "Y unit", self.y_unit_var, [""], self.on_label_related_change)

        transform_row = ttk.Frame(plot_box, style="Card.TFrame")
        transform_row.pack(fill="x", pady=(6, 0))
        self.x_transform_combo = self._add_labeled_combo_inline(transform_row, "X transform", self.x_transform_var, ["none", "log10"], self.on_label_related_change)

        self._add_entry_pair(plot_box, "Bins", self.bins_var, "Hexbin grids", self.hexbin_size_var)
        self._add_entry_pair(plot_box, "Figure W", self.fig_w_var, "Figure H", self.fig_h_var)
        self._add_entry_pair(plot_box, "Point size", self.point_size_var, "Alpha", self.alpha_var)

        ttk.Label(plot_box, text="Figure title", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Entry(plot_box, textvariable=self.title_var).pack(fill="x", pady=(2, 0))
        ttk.Label(plot_box, text="X axis title", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Entry(plot_box, textvariable=self.x_label_var).pack(fill="x", pady=(2, 0))
        ttk.Label(plot_box, text="Y axis title", style="Card.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Entry(plot_box, textvariable=self.y_label_var).pack(fill="x", pady=(2, 0))

        axis_box = ttk.LabelFrame(parent, text="Axes + Labels", style="SidebarCard.TLabelframe", padding=12)
        axis_box.pack(fill="x", pady=(0, 10))
        self._add_entry_pair(axis_box, "X min", self.xmin_var, "X max", self.xmax_var)
        self._add_entry_pair(axis_box, "Y min", self.ymin_var, "Y max", self.ymax_var)
        ttk.Checkbutton(axis_box, text="Log X axis", variable=self.use_xlog_var).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(axis_box, text="Log Y axis", variable=self.use_ylog_var).pack(anchor="w")
        ttk.Checkbutton(axis_box, text="Grid", variable=self.grid_var).pack(anchor="w")
        ttk.Checkbutton(axis_box, text="KDE (histogram)", variable=self.kde_var).pack(anchor="w")
        ttk.Checkbutton(axis_box, text="Color scatter by category", variable=self.color_by_category_var).pack(anchor="w")

        tick_row = ttk.Frame(axis_box, style="Card.TFrame")
        tick_row.pack(fill="x", pady=(8, 0))
        self._add_labeled_combo_inline(tick_row, "Tick direction", self.tick_direction_var, ["in", "out", "inout"], None)
        ttk.Checkbutton(axis_box, text="Show top ticks", variable=self.show_top_ticks_var).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(axis_box, text="Show right ticks", variable=self.show_right_ticks_var).pack(anchor="w")
        ttk.Checkbutton(axis_box, text="Show top border", variable=self.show_top_spine_var).pack(anchor="w")
        ttk.Checkbutton(axis_box, text="Show right border", variable=self.show_right_spine_var).pack(anchor="w")

        style_box = ttk.LabelFrame(parent, text="Plot Style", style="SidebarCard.TLabelframe", padding=12)
        style_box.pack(fill="x", pady=(0, 10))
        self._add_entry_pair(style_box, "Line width", self.line_width_var, "Edge width", self.edge_width_var)
        marker_row = ttk.Frame(style_box, style="Card.TFrame")
        marker_row.pack(fill="x", pady=(8, 0))
        self._add_labeled_combo_inline(marker_row, "Marker shape", self.marker_shape_var, ["o", "s", "^", "v", "D", "P", "X", "*", "+"], None)
        ttk.Checkbutton(style_box, text="Histogram filled", variable=self.hist_filled_var).pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(style_box, text="Density", variable=self.density_var).pack(anchor="w")
        color_row = ttk.Frame(style_box, style="Card.TFrame")
        color_row.pack(fill="x", pady=(8, 0))
        self._add_color_picker(color_row, "Main color", self.plot_color_var)
        self._add_color_picker(color_row, "Edge color", self.edge_color_var)
        bg_row = ttk.Frame(style_box, style="Card.TFrame")
        bg_row.pack(fill="x", pady=(8, 0))
        self._add_color_picker(bg_row, "Background", self.bg_color_var)

        export_box = ttk.LabelFrame(parent, text="Export", style="SidebarCard.TLabelframe", padding=12)
        export_box.pack(fill="x", pady=(0, 10))
        self._add_entry_pair(export_box, "Save width", self.fig_w_var, "Save height", self.fig_h_var)
        export_row = ttk.Frame(export_box, style="Card.TFrame")
        export_row.pack(fill="x", pady=(8, 0))
        self._add_labeled_combo_inline(export_row, "Format", self.export_format_var, ["png", "pdf", "svg"], None)
        left = ttk.Frame(export_row, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(left, text="DPI", style="Card.TLabel").pack(anchor="w")
        ttk.Entry(left, textvariable=self.export_dpi_var).pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(export_box, text="Transparent background", variable=self.transparent_bg_var).pack(anchor="w", pady=(8, 0))

        filter_box = ttk.LabelFrame(parent, text="Filters", style="SidebarCard.TLabelframe", padding=12)
        filter_box.pack(fill="x", pady=(0, 12))
        self.filter_combo = self._add_labeled_combo(filter_box, "Numeric filter column", self.filter_col_var, [""], None)
        self._add_entry_pair(filter_box, "Filter min", self.filter_min_var, "Filter max", self.filter_max_var)
        self.category_col_combo = self._add_labeled_combo(filter_box, "Category column", self.category_col_var, [""], self.on_category_column_changed)
        self.category_value_combo = self._add_labeled_combo(filter_box, "Category value", self.category_value_var, ["All"], None)
        ttk.Checkbutton(filter_box, text="Drop NaN in used columns", variable=self.dropna_var).pack(anchor="w", pady=(6, 0))

    def _build_right_panel(self, parent):
        top = ttk.Frame(parent, style="Card.TFrame")
        top.pack(fill="both", expand=True)

        plot_holder = ttk.Frame(top, style="Card.TFrame")
        plot_holder.pack(fill="both", expand=True)

        self.fig, self.ax = plt.subplots(figsize=(7.5, 5.5), dpi=100)
        self.fig.patch.set_facecolor("white")
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_holder)
        self.canvas.draw()
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(expand=True, pady=(2, 2))

        toolbar_frame = ttk.Frame(parent, style="Card.TFrame")
        toolbar_frame.pack(fill="x", pady=(6, 8))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", padx=(2,0))

        preview_box = ttk.LabelFrame(parent, text="Preview", style="SidebarCard.TLabelframe", padding=8)
        preview_box.pack(fill="x", pady=(4, 0))
        columns = ["column", "dtype", "non-null"]
        self.preview_table = ttk.Treeview(preview_box, columns=columns, show="headings", height=4)
        for col, width in zip(columns, [200, 140, 110]):
            self.preview_table.heading(col, text=col)
            self.preview_table.column(col, width=width, anchor="w")
        self.preview_table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(preview_box, orient="vertical", command=self.preview_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.preview_table.configure(yscrollcommand=scrollbar.set)

    def _add_labeled_combo(self, parent, label, variable, values, callback):
        ttk.Label(parent, text=label, style="Card.TLabel").pack(anchor="w", pady=(6, 0))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.pack(fill="x", pady=(2, 0))
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda e: callback())
        return combo

    def _add_labeled_combo_inline(self, parent, label, variable, values, callback):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(frame, text=label, style="Card.TLabel").pack(anchor="w")
        combo = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly")
        combo.pack(fill="x", pady=(2, 0))
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda e: callback())
        return combo

    def _add_entry_pair(self, parent, label1, var1, label2, var2):
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        left = ttk.Frame(row, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(left, text=label1, style="Card.TLabel").pack(anchor="w")
        ttk.Entry(left, textvariable=var1).pack(fill="x", pady=(2, 0))
        right = ttk.Frame(row, style="Card.TFrame")
        right.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(right, text=label2, style="Card.TLabel").pack(anchor="w")
        ttk.Entry(right, textvariable=var2).pack(fill="x", pady=(2, 0))

    def _add_color_picker(self, parent, label, var):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(frame, text=label, style="Card.TLabel").pack(anchor="w")
        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill="x", pady=(2, 0))
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(row, text="Pick", style="Small.TButton", command=lambda: self._pick_color(var)).pack(side="right")

    def _pick_color(self, var):
        color = colorchooser.askcolor(color=var.get())[1]
        if color:
            var.set(color)

    def _display_name(self, raw_col):
        return DISPLAY_NAME_MAP.get(raw_col, raw_col)

    def _axis_label_text(self, raw_col, unit, transform):
        if not raw_col:
            return ""
        label = self._display_name(raw_col)

        if raw_col == "frac":
            return label

        if raw_col == "dwell" and transform == "log10":
            unit_txt = unit if unit else ""
            return f"Log Dwell Time (log10({unit_txt}))" if unit_txt else "Log Dwell Time"

        if transform == "log10":
            label = f"log10({label})"
        if unit and unit != "raw":
            label = f"{label} ({unit})"
        return label

    def _refresh_unit_combo(self, raw_col, axis="x"):
        options = [""]
        default = ""
        if raw_col in UNIT_OPTIONS:
            options = [u for u, _ in UNIT_OPTIONS[raw_col]]
            default = DEFAULT_UNITS.get(raw_col, options[0])
        combo = self.x_unit_combo if axis == "x" else self.y_unit_combo
        var = self.x_unit_var if axis == "x" else self.y_unit_var
        combo["values"] = options
        if var.get() not in options:
            var.set(default if default in options else options[0])

    def _convert_series(self, series, raw_col, unit_name):
        values = pd.to_numeric(series, errors="coerce").astype(float)
        factor = 1.0
        if raw_col in UNIT_OPTIONS and unit_name:
            for name, scale in UNIT_OPTIONS[raw_col]:
                if name == unit_name:
                    factor = scale
                    break
        return values * factor

    def _apply_x_transform(self, values):
        if self.x_transform_var.get() == "log10":
            values = np.asarray(values, dtype=float)
            values = values[values > 0]
            return np.log10(values)
        return np.asarray(values, dtype=float)

    def _current_raw_x(self):
        return self.forced_raw_x or self.x_var.get().strip()

    def _current_raw_y(self):
        return self.forced_raw_y or self.y_var.get().strip()

    def _update_raw_mapping_label(self):
        x_raw = self._current_raw_x() or "-"
        y_needed = self.plot_type_var.get() in {"Scatter", "2D Histogram", "Hexbin", "Time Plot"}
        y_raw = self._current_raw_y() if y_needed else "-"
        self.raw_mapping_label.configure(text=f"Raw X: {x_raw} | Raw Y: {y_raw}")

    def _update_status(self, text):
        self.status_var.set(text)

    def _clear_plot(self):
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.text(0.5, 0.5, "File loaded.\nChoose a preset or adjust the controls,\nthen click Plot.",
                     ha="center", va="center", transform=self.ax.transAxes, fontsize=13)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)
        self.fig.subplots_adjust(left=0.10, right=0.94, top=0.90, bottom=0.12)
        self.canvas.draw()

    def _update_default_titles(self):
        # Keep figure title empty by default; only show it if the user manually enters one.
        x_raw = self._current_raw_x()
        y_raw = self._current_raw_y()

        if not self.x_label_var.get().strip():
            self.x_label_var.set(self._axis_label_text(x_raw, self.x_unit_var.get(), self.x_transform_var.get()))
        if not self.y_label_var.get().strip():
            if self.plot_type_var.get() == "Histogram":
                self.y_label_var.set("Density" if self.density_var.get() or self.kde_var.get() else "Counts")
            elif self.plot_type_var.get() == "CDF":
                self.y_label_var.set("Cumulative probability")
            else:
                self.y_label_var.set(self._axis_label_text(y_raw, self.y_unit_var.get(), "none"))

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open event table",
            filetypes=[("Data files", "*.txt *.tsv *.csv"), ("Text", "*.txt"), ("TSV", "*.tsv"), ("CSV", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            df = self._read_table(path)
        except Exception as exc:
            messagebox.showerror("Load Error", f"Could not open file.\n\n{exc}")
            return
        if df.empty:
            messagebox.showwarning("Empty File", "The selected file contains no rows.")
            return

        self.df = df
        self.filtered_df = df.copy()
        self.current_file = path
        self.all_columns = list(df.columns)
        self.numeric_columns = [c for c in NUMERIC_PRIORITY if c in df.columns] + sorted([c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in NUMERIC_PRIORITY])

        self.forced_raw_x = None
        self.forced_raw_y = None

        self._refresh_column_controls()
        self._refresh_preview_table()
        self._refresh_file_labels()
        self._clear_plot()
        self._update_status(f"Loaded {os.path.basename(path)} with {len(df):,} rows. Choose settings, then click Plot.")

    def _read_table(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            return pd.read_csv(path)
        try:
            return pd.read_csv(path, sep=None, engine="python")
        except Exception:
            return pd.read_csv(path, sep="\t")

    def _refresh_column_controls(self):
        values_numeric = self.numeric_columns.copy()
        self.x_combo["values"] = values_numeric
        self.y_combo["values"] = values_numeric
        self.filter_combo["values"] = [""] + values_numeric

        if self.x_var.get() not in values_numeric:
            self.x_var.set("dwell" if "dwell" in values_numeric else (values_numeric[0] if values_numeric else ""))
        if self.y_var.get() not in values_numeric:
            self.y_var.set("frac" if "frac" in values_numeric else (values_numeric[1] if len(values_numeric) > 1 else ""))

        category_candidates = [c for c in self.all_columns if df_has_few_unique(self.df[c])]
        preferred = [c for c in ["category", "parent_id", "N_child"] if c in category_candidates]
        category_values = preferred + [c for c in category_candidates if c not in preferred]
        if not category_values:
            category_values = [""]

        self.category_col_combo["values"] = category_values
        if self.category_col_var.get() not in category_values:
            self.category_col_var.set("category" if "category" in category_values else category_values[0])

        self.on_x_changed()
        self.on_y_changed()
        self.on_category_column_changed()
        self.on_plot_type_changed()

    def on_x_changed(self):
        if self.forced_raw_x is None:
            self._refresh_unit_combo(self.x_var.get().strip(), axis="x")
        self.title_var.set("")
        self.x_label_var.set("")
        self._update_default_titles()
        self._update_raw_mapping_label()

    def on_y_changed(self):
        if self.forced_raw_y is None:
            self._refresh_unit_combo(self.y_var.get().strip(), axis="y")
        self.title_var.set("")
        self.y_label_var.set("")
        self._update_default_titles()
        self._update_raw_mapping_label()

    def on_label_related_change(self):
        self.title_var.set("")
        self.x_label_var.set("")
        self.y_label_var.set("")
        self._update_default_titles()

    def on_category_column_changed(self):
        if self.df is None:
            return
        col = self.category_col_var.get()
        if col and col in self.df.columns:
            values = ["All"] + [str(v) for v in sorted(self.df[col].dropna().astype(str).unique(), key=str)]
        else:
            values = ["All"]
        self.category_value_combo["values"] = values
        if self.category_value_var.get() not in values:
            self.category_value_var.set("All")

    def _refresh_preview_table(self):
        for row in self.preview_table.get_children():
            self.preview_table.delete(row)
        if self.df is None:
            return
        for col in self.df.columns:
            self.preview_table.insert("", "end", values=(col, str(self.df[col].dtype), int(self.df[col].notna().sum())))

    def _refresh_file_labels(self):
        self.file_label.configure(text=self.current_file if self.current_file else "No file loaded")
        self.rows_label.configure(text=f"Rows: {len(self.df):,}" if self.df is not None else "Rows: -")
        self.filtered_rows_label.configure(text=f"Filtered: {len(self.filtered_df):,}" if self.filtered_df is not None else "Filtered: -")
        self._update_raw_mapping_label()

    def on_plot_type_changed(self):
        pt = self.plot_type_var.get()
        y_needed = pt in {"Scatter", "2D Histogram", "Hexbin", "Time Plot"}
        self.y_combo.configure(state="readonly" if y_needed else "disabled")
        self.y_unit_combo.configure(state="readonly" if y_needed else "disabled")
        if pt == "Time Plot" and self.forced_raw_x is None:
            if "index" in self.numeric_columns:
                self.x_var.set("index")
            elif "global_startpt" in self.numeric_columns:
                self.x_var.set("global_startpt")
        self.title_var.set("")
        self.x_label_var.set("")
        self.y_label_var.set("")
        self._update_default_titles()
        self._update_raw_mapping_label()


    def apply_filters(self):
        if self.df is None:
            messagebox.showinfo("No Data", "Open a file first.")
            return

        data = self.df.copy()
        filter_col = self.filter_col_var.get().strip()
        filter_min = self._parse_optional_float(self.filter_min_var.get())
        filter_max = self._parse_optional_float(self.filter_max_var.get())

        if filter_col:
            if filter_col not in data.columns:
                messagebox.showerror("Filter Error", f"Column not found: {filter_col}")
                return
            if filter_min is not None:
                data = data[data[filter_col] >= filter_min]
            if filter_max is not None:
                data = data[data[filter_col] <= filter_max]

        cat_col = self.category_col_var.get().strip()
        cat_val = self.category_value_var.get().strip()
        if cat_col and cat_val and cat_val != "All" and cat_col in data.columns:
            data = data[data[cat_col].astype(str) == cat_val]

        self.filtered_df = data
        self.filtered_rows_label.configure(text=f"Filtered: {len(self.filtered_df):,}")
        self._update_status(f"Filters applied. {len(self.filtered_df):,} rows remain.")

    def reset_filters(self):
        if self.df is None:
            return

        self.filtered_df = self.df.copy()
        self.filter_col_var.set("")
        self.filter_min_var.set("")
        self.filter_max_var.set("")
        self.category_value_var.set("All")
        self.xmin_var.set("")
        self.xmax_var.set("")
        self.ymin_var.set("")
        self.ymax_var.set("")
        self.filtered_rows_label.configure(text=f"Filtered: {len(self.filtered_df):,}")
        self._update_status("Filters reset.")

    def _get_plot_df(self, require_y=False):
        if self.filtered_df is None:
            raise ValueError("No data loaded.")
        data = self.filtered_df.copy()
        required = [self._current_raw_x()]
        if require_y:
            required.append(self._current_raw_y())
        required = [c for c in required if c]
        if self.dropna_var.get() and required:
            data = data.dropna(subset=required)
        return data

    def _update_range_label(self, x=None, y=None):
        parts = []
        if x is not None and len(x) > 0:
            parts.append(f"X range: {np.nanmin(x):.4g} to {np.nanmax(x):.4g}")
        if y is not None and len(y) > 0:
            parts.append(f"Y range: {np.nanmin(y):.4g} to {np.nanmax(y):.4g}")
        self.range_label.configure(text=" | ".join(parts) if parts else "Current plot values: -")

    def plot_data(self):
        if self.df is None:
            messagebox.showinfo("No Data", "Open a file first.")
            return
        try:
            fig_w = self._parse_positive_float(self.fig_w_var.get(), "Figure width")
            fig_h = self._parse_positive_float(self.fig_h_var.get(), "Figure height")
            bins = self._parse_positive_int(self.bins_var.get(), "Bins")
            gridsize = self._parse_positive_int(self.hexbin_size_var.get(), "Hexbin grids")
            point_size = self._parse_positive_float(self.point_size_var.get(), "Point size")
            alpha = self._parse_float_in_range(self.alpha_var.get(), "Alpha", 0.0, 1.0)

            self.fig.set_size_inches(fig_w, fig_h)
            self.fig.clear()
            self.ax = self.fig.add_subplot(111)

            pt = self.plot_type_var.get()
            if pt == "Histogram":
                used_rows = self._plot_histogram(bins)
            elif pt == "Scatter":
                used_rows = self._plot_scatter(point_size, alpha)
            elif pt == "2D Histogram":
                used_rows = self._plot_2d_histogram(bins)
            elif pt == "Hexbin":
                used_rows = self._plot_hexbin(gridsize)
            elif pt == "CDF":
                used_rows = self._plot_cdf()
            elif pt == "Time Plot":
                used_rows = self._plot_time(point_size, alpha)
            else:
                raise ValueError("Unsupported plot type")

            self._apply_style_and_axes()
            self.fig.tight_layout()
            self.canvas.draw()

            x_raw = self._current_raw_x()
            y_raw = self._current_raw_y() if pt in {"Scatter", "2D Histogram", "Hexbin", "Time Plot"} else "-"
            self._update_status(f"Plotted {pt} | raw x = {x_raw} | raw y = {y_raw} | rows = {used_rows:,}")
        except Exception as exc:
            messagebox.showerror("Plot Error", str(exc))

    def _plot_histogram(self, bins):
        raw_x = self._current_raw_x()
        data = self._get_plot_df(require_y=False)
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        x = x[np.isfinite(x)]
        x = self._apply_x_transform(x)
        x = x[np.isfinite(x)]
        if len(x) == 0:
            raise ValueError("No finite values available for histogram after transform/unit conversion.")

        histtype = "bar" if self.hist_filled_var.get() else "step"
        self.ax.hist(
            x, bins=bins, density=self.density_var.get(), alpha=self._parse_float_in_range(self.alpha_var.get(), "Alpha", 0.0, 1.0),
            color=self.plot_color_var.get(), edgecolor=self.edge_color_var.get(),
            linewidth=self._parse_positive_float(self.edge_width_var.get(), "Edge width"), histtype=histtype,
        )
        if self.kde_var.get() and len(x) > 1:
            xs, ys = self._gaussian_kde_curve(x)
            self.ax.plot(xs, ys, linewidth=self._parse_positive_float(self.line_width_var.get(), "Line width"), color=self.plot_color_var.get())
        self._update_range_label(x=x)
        return len(x)

    def _plot_scatter(self, point_size, alpha):
        data = self._get_plot_df(require_y=True)
        raw_x = self._current_raw_x()
        raw_y = self._current_raw_y()
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        y = self._convert_series(data[raw_y], raw_y, self.y_unit_var.get()).to_numpy()
        x = self._apply_x_transform(x)
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]

        if self.color_by_category_var.get():
            cat_col = self.category_col_var.get().strip()
            if cat_col and cat_col in data.columns:
                categories = data.loc[mask, cat_col].astype(str).to_numpy()
                unique_cats = list(pd.unique(categories))
                markers = ["o", "v", "^", "s", "D", "P", "X", "<", ">"]
                for idx, cat in enumerate(unique_cats):
                    m = categories == cat
                    self.ax.scatter(x[m], y[m], s=point_size, alpha=alpha, label=cat,
                                    marker=markers[idx % len(markers)],
                                    edgecolors=self.edge_color_var.get(),
                                    linewidths=max(self._parse_positive_float(self.edge_width_var.get(), "Edge width") * 0.5, 0.2))
                if len(unique_cats) <= 12:
                    self.ax.legend(title=cat_col, fontsize=8, title_fontsize=9, frameon=False)
            else:
                self.ax.scatter(x, y, s=point_size, alpha=alpha, color=self.plot_color_var.get(),
                                marker=self.marker_shape_var.get(), edgecolors=self.edge_color_var.get(),
                                linewidths=max(self._parse_positive_float(self.edge_width_var.get(), "Edge width") * 0.5, 0.2))
        else:
            self.ax.scatter(x, y, s=point_size, alpha=alpha, color=self.plot_color_var.get(),
                            marker=self.marker_shape_var.get(), edgecolors=self.edge_color_var.get(),
                            linewidths=max(self._parse_positive_float(self.edge_width_var.get(), "Edge width") * 0.5, 0.2))
        self.ax.text(0.98, 0.96, f"n = {len(x)}", transform=self.ax.transAxes,
                     ha="right", va="top", fontsize=10)
        self._update_range_label(x=x, y=y)
        return len(x)

    def _plot_2d_histogram(self, bins):
        data = self._get_plot_df(require_y=True)
        raw_x = self._current_raw_x()
        raw_y = self._current_raw_y()
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        y = self._convert_series(data[raw_y], raw_y, self.y_unit_var.get()).to_numpy()
        x = self._apply_x_transform(x)
        mask = np.isfinite(x) & np.isfinite(y)
        h = self.ax.hist2d(x[mask], y[mask], bins=bins)
        self.fig.colorbar(h[3], ax=self.ax, label="Counts")
        self._update_range_label(x=x[mask], y=y[mask])
        return int(np.sum(mask))

    def _plot_hexbin(self, gridsize):
        data = self._get_plot_df(require_y=True)
        raw_x = self._current_raw_x()
        raw_y = self._current_raw_y()
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        y = self._convert_series(data[raw_y], raw_y, self.y_unit_var.get()).to_numpy()
        x = self._apply_x_transform(x)
        mask = np.isfinite(x) & np.isfinite(y)
        hb = self.ax.hexbin(x[mask], y[mask], gridsize=gridsize, mincnt=1)
        self.fig.colorbar(hb, ax=self.ax, label="Counts")
        self._update_range_label(x=x[mask], y=y[mask])
        return int(np.sum(mask))

    def _plot_cdf(self):
        data = self._get_plot_df(require_y=False)
        raw_x = self._current_raw_x()
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        x = x[np.isfinite(x)]
        x = self._apply_x_transform(x)
        x = x[np.isfinite(x)]
        if len(x) == 0:
            raise ValueError("No finite values available for CDF after transform/unit conversion.")
        x = np.sort(x)
        y = np.arange(1, len(x) + 1) / len(x)
        self.ax.plot(x, y, linewidth=self._parse_positive_float(self.line_width_var.get(), "Line width"), color=self.plot_color_var.get())
        self._update_range_label(x=x, y=y)
        return len(x)

    def _plot_time(self, point_size, alpha):
        data = self._get_plot_df(require_y=True)
        raw_x = self._current_raw_x()
        raw_y = self._current_raw_y()
        x = self._convert_series(data[raw_x], raw_x, self.x_unit_var.get()).to_numpy()
        y = self._convert_series(data[raw_y], raw_y, self.y_unit_var.get()).to_numpy()
        x = self._apply_x_transform(x)
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]
        self.ax.plot(x, y, linewidth=self._parse_positive_float(self.line_width_var.get(), "Line width"), alpha=0.75, color=self.plot_color_var.get())
        self.ax.scatter(x, y, s=max(point_size * 0.7, 8), alpha=alpha, color=self.plot_color_var.get(),
                        marker=self.marker_shape_var.get(), edgecolors=self.edge_color_var.get(),
                        linewidths=max(self._parse_positive_float(self.edge_width_var.get(), "Edge width") * 0.5, 0.2))
        self._update_range_label(x=x, y=y)
        return len(x)

    def _apply_style_and_axes(self):
        self.ax.set_facecolor(self.bg_color_var.get())
        self.fig.patch.set_facecolor(self.bg_color_var.get() if not self.transparent_bg_var.get() else "none")

        title = self.title_var.get().strip()
        x_label = self.x_label_var.get().strip() or self._axis_label_text(self._current_raw_x(), self.x_unit_var.get(), self.x_transform_var.get())
        if self.plot_type_var.get() == "Histogram":
            y_label = self.y_label_var.get().strip() or ("Density" if self.density_var.get() or self.kde_var.get() else "Counts")
        elif self.plot_type_var.get() == "CDF":
            y_label = self.y_label_var.get().strip() or "Cumulative probability"
        else:
            y_label = self.y_label_var.get().strip() or self._axis_label_text(self._current_raw_y(), self.y_unit_var.get(), "none")

        if title:
            self.ax.set_title(title, fontsize=12, pad=12)
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel(y_label)

        x_min = self._parse_optional_float(self.xmin_var.get())
        x_max = self._parse_optional_float(self.xmax_var.get())
        y_min = self._parse_optional_float(self.ymin_var.get())
        y_max = self._parse_optional_float(self.ymax_var.get())

        if self.use_xlog_var.get():
            self.ax.set_xscale("log")
        if self.use_ylog_var.get():
            self.ax.set_yscale("log")
        if x_min is not None or x_max is not None:
            self.ax.set_xlim(left=x_min, right=x_max)
        if y_min is not None or y_max is not None:
            self.ax.set_ylim(bottom=y_min, top=y_max)

        # Explicitly control grid so previous axis state never leaks through
        self.ax.grid(False)
        if self.grid_var.get():
            self.ax.grid(True, alpha=0.25)

        self.ax.tick_params(direction=self.tick_direction_var.get(), top=self.show_top_ticks_var.get(), right=self.show_right_ticks_var.get())
        self.ax.spines["top"].set_visible(self.show_top_spine_var.get())
        self.ax.spines["right"].set_visible(self.show_right_spine_var.get())
        self.fig.subplots_adjust(left=0.11, right=0.96, top=0.90, bottom=0.14)

    def _gaussian_kde_curve(self, x):
        x = np.asarray(x, dtype=float)
        x = x[np.isfinite(x)]
        n = len(x)
        std = np.std(x, ddof=1)
        if n < 2 or std == 0:
            raise ValueError("Need at least 2 non-identical points for KDE.")
        bw = 1.06 * std * (n ** (-1 / 5))
        if not np.isfinite(bw) or bw <= 0:
            bw = std / 5
        xs = np.linspace(np.min(x), np.max(x), 400)
        diffs = (xs[:, None] - x[None, :]) / bw
        kernel = np.exp(-0.5 * diffs ** 2) / np.sqrt(2 * np.pi)
        density = np.mean(kernel, axis=1) / bw
        if not self.density_var.get():
            bin_width = (np.max(x) - np.min(x)) / max(self._parse_positive_int(self.bins_var.get(), "Bins"), 1)
            if np.isfinite(bin_width) and bin_width > 0:
                density = density * len(x) * bin_width
        return xs, density

    def save_figure(self):
        if not self.fig.axes:
            messagebox.showinfo("No Figure", "Generate a plot first.")
            return
        fmt = self.export_format_var.get().strip() or "png"
        dpi = self._parse_positive_int(self.export_dpi_var.get(), "DPI")
        path = filedialog.asksaveasfilename(
            title="Save figure",
            defaultextension=f".{fmt}",
            filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg"), ("All files", "*.*")]
        )
        if not path:
            return
        self.fig.set_size_inches(self._parse_positive_float(self.fig_w_var.get(), "Save width"),
                                 self._parse_positive_float(self.fig_h_var.get(), "Save height"))
        self.fig.savefig(path, bbox_inches="tight", dpi=dpi, transparent=self.transparent_bg_var.get(), facecolor=self.fig.get_facecolor())
        self._update_status(f"Saved figure to {path}")

    def export_filtered_table(self):
        if self.filtered_df is None:
            messagebox.showinfo("No Data", "No filtered table available.")
            return
        path = filedialog.asksaveasfilename(
            title="Export filtered table",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("TSV", "*.tsv"), ("All files", "*.*")]
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".tsv":
            self.filtered_df.to_csv(path, sep="\t", index=False)
        else:
            self.filtered_df.to_csv(path, index=False)
        self._update_status(f"Exported filtered data to {path}")

    def _set_forced_binding(self, raw_x, raw_y=None, x_unit=None, y_unit=None, x_transform="none", plot_type="Histogram", title=""):
        self.forced_raw_x = raw_x
        self.forced_raw_y = raw_y
        self.plot_type_var.set(plot_type)

        # keep dropdowns visually aligned, but plotting uses forced bindings
        if raw_x in self.numeric_columns:
            self.x_var.set(raw_x)
        if raw_y in self.numeric_columns:
            self.y_var.set(raw_y)

        self._refresh_unit_combo(raw_x, axis="x")
        if raw_y:
            self._refresh_unit_combo(raw_y, axis="y")

        if x_unit and x_unit in self.x_unit_combo["values"]:
            self.x_unit_var.set(x_unit)
        if raw_y and y_unit and y_unit in self.y_unit_combo["values"]:
            self.y_unit_var.set(y_unit)

        self.x_transform_var.set(x_transform)
        self.title_var.set(title)
        self.x_label_var.set("")
        self.y_label_var.set("")
        self.on_plot_type_changed()
        self._update_raw_mapping_label()

    def preset_frac_vs_logdwell(self):
        self._set_forced_binding("dwell", "frac", x_unit="µs", y_unit="fraction", x_transform="log10", plot_type="Scatter", title="")

    def preset_stdev_vs_logdwell(self):
        self._set_forced_binding("dwell", "stdev", x_unit="µs", y_unit="raw", x_transform="log10", plot_type="Scatter", title="")

    def preset_skewness_vs_logdwell(self):
        self._set_forced_binding("dwell", "skewness", x_unit="µs", y_unit="raw", x_transform="log10", plot_type="Scatter", title="")

    def preset_kurtosis_vs_logdwell(self):
        self._set_forced_binding("dwell", "kurtosis", x_unit="µs", y_unit="raw", x_transform="log10", plot_type="Scatter", title="")

    def preset_frac_hist(self):
        self._set_forced_binding("frac", None, x_unit="fraction", x_transform="none", plot_type="Histogram", title="")

    def preset_deli_hist(self):
        # hard-binding to deli only
        self._set_forced_binding("deli", None, x_unit="pA", x_transform="none", plot_type="Histogram", title="")

    def preset_log_dwell_hist(self):
        self._set_forced_binding("dwell", None, x_unit="µs", x_transform="log10", plot_type="Histogram", title="")

    def preset_dt_hist(self):
        self._set_forced_binding("dt", None, x_unit="s", x_transform="none", plot_type="Histogram", title="")

    def _parse_optional_float(self, value):
        value = str(value).strip()
        if value == "":
            return None
        return float(value)

    def _parse_positive_float(self, value, name):
        v = float(value)
        if v <= 0:
            raise ValueError(f"{name} must be > 0")
        return v

    def _parse_positive_int(self, value, name):
        v = int(float(value))
        if v <= 0:
            raise ValueError(f"{name} must be > 0")
        return v

    def _parse_float_in_range(self, value, name, low, high):
        v = float(value)
        if not (low <= v <= high):
            raise ValueError(f"{name} must be between {low} and {high}")
        return v


if __name__ == "__main__":
    root = tk.Tk()
    app = NanoporePlotGUI(root)
    root.mainloop()
