# app.py
# ============================================================
# UPS IBW Processor - 图形界面 (v3.2)
# 依赖：reader, plots, export_csv, ui_theme, file_loader, fit_window
# 可选：windnd（拖拽添加文件，Windows）
# ============================================================

import os
import sys
import traceback

import numpy as np

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from reader import read_ibw_ups
from export_csv import (
    export_csv_separate,
    export_csv_merged_horizontal,
    get_scan_range_tag,
)
from ui_theme import COLORS, FONTS, apply_ttk_theme
from file_loader import FileLoader
from fit_window import FitWindow

try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False


class UPSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XPS / UPS IBW Processor")
        self.geometry("1020x700")
        self.minsize(960, 660)

        self.configure(bg=COLORS["bg"])
        self.option_add("*Font", FONTS["body"])
        self.option_add("*Background", COLORS["bg"])

        # Apply TTK styles globally
        apply_ttk_theme(self)

        self.files = []
        self.spectra = []
        self.out_dir = None

        self.zoomA = (18.0, 15.0)
        self.zoomB = (-1.0, 2.0)

        self._loader = FileLoader(schedule_fn=lambda fn: self.after(0, fn))

        self._build_ui()
        self._setup_drag_drop()

    # ------------------------------------------------------------------ #
    #  Styled widget helpers                                               #
    # ------------------------------------------------------------------ #

    def _btn(self, parent, text, command, width=0, primary=False, danger=False):
        """统一按钮工厂：primary=蓝绿主色，danger=红色，默认=灰色。"""
        if primary:
            bg, fg, hover = COLORS["primary"], "#ffffff", COLORS["primary_hover"]
        elif danger:
            bg, fg, hover = "#fef2f2", COLORS["error"], "#fee2e2"
        else:
            bg, fg, hover = COLORS["button_bg"], COLORS["text"], COLORS["button_hover"]

        kw = dict(font=FONTS["body"], bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg,
                  relief="flat", cursor="hand2",
                  padx=14, pady=6, borderwidth=0, highlightthickness=0)
        if width:
            kw["width"] = width

        btn = tk.Button(parent, text=text, command=command, **kw)
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    def _section(self, parent, title, **pack_kw):
        """
        创建带左侧彩条的卡片式分区。
        返回 inner Frame（内部可自由使用 pack 或 grid）。
        """
        outer = tk.Frame(parent, bg=COLORS["card"],
                         highlightbackground=COLORS["card_border"],
                         highlightthickness=1)
        outer.pack(**pack_kw)

        # 3px 主色左边框
        tk.Frame(outer, bg=COLORS["primary"], width=3).pack(side="left", fill="y")

        # 右侧：标题栏 + 内容
        right = tk.Frame(outer, bg=COLORS["card"])
        right.pack(side="left", fill="both", expand=True)

        title_bar = tk.Frame(right, bg=COLORS["card"])
        title_bar.pack(fill="x", padx=14, pady=(8, 4))
        tk.Label(title_bar, text=title, font=FONTS["section"],
                 fg=COLORS["primary"], bg=COLORS["card"]).pack(side="left")

        tk.Frame(right, bg=COLORS["divider"], height=1).pack(fill="x", padx=14)

        inner = tk.Frame(right, bg=COLORS["card"])
        inner.pack(fill="both", expand=True, padx=14, pady=(8, 10))
        return inner

    def _opt_label(self, parent, text, row):
        tk.Label(parent, text=text, bg=COLORS["card"],
                 fg=COLORS["text"], font=FONTS["body"],
                 ).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)

    def _opt_radio(self, parent, text, var, value, row, col):
        tk.Radiobutton(
            parent, text=text, variable=var, value=value,
            bg=COLORS["card"], fg=COLORS["text"],
            selectcolor=COLORS["primary_light"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["primary"],
            font=FONTS["body"], cursor="hand2",
        ).grid(row=row, column=col, sticky="w", padx=8, pady=4)

    def _opt_check(self, parent, text, var, row, col):
        cb = tk.Checkbutton(
            parent, text=text, variable=var,
            bg=COLORS["card"], fg=COLORS["text"],
            selectcolor=COLORS["primary_light"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["primary"],
            font=FONTS["body"], cursor="hand2",
        )
        cb.grid(row=row, column=col, sticky="w", padx=8, pady=4)
        return cb

    def _zoom_entry(self, parent, textvar, row, col):
        e = tk.Entry(
            parent, textvariable=textvar, width=6,
            bg=COLORS["list_bg"], fg=COLORS["text"], relief="flat",
            font=FONTS["body"],
            highlightthickness=1, highlightbackground=COLORS["card_border"],
            insertbackground=COLORS["primary"],
        )
        e.grid(row=row, column=col, sticky="w", padx=2, pady=3)
        return e

    # ------------------------------------------------------------------ #
    #  UI build                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # ── 顶部 3px 主色彩条 ─────────────────────────────────────────
        tk.Frame(self, bg=COLORS["primary"], height=3).pack(fill="x")

        # ── Header ────────────────────────────────────────────────────
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=20, pady=(12, 6))

        # 左侧：图标徽章 + 标题
        left_h = tk.Frame(header, bg=COLORS["bg"])
        left_h.pack(side="left")

        badge = tk.Frame(left_h, bg=COLORS["primary"], padx=10, pady=4)
        badge.pack(side="left")
        tk.Label(badge, text="⚗", font=("Segoe UI", 13),
                 fg="white", bg=COLORS["primary"]).pack(side="left")
        tk.Label(badge, text="XPS / UPS", font=FONTS["section"],
                 fg="white", bg=COLORS["primary"]).pack(side="left", padx=(4, 0))

        tk.Label(left_h, text="  IBW Processor", font=FONTS["title"],
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(side="left")

        # 右侧：版本 & 光子能量徽章
        right_h = tk.Frame(header, bg=COLORS["bg"])
        right_h.pack(side="right", padx=(0, 4))

        for txt, fg, bg in [
            ("v3.2",          COLORS["secondary"],  COLORS["button_bg"]),
            ("He I  21.22 eV", COLORS["primary"],   COLORS["primary_light"]),
        ]:
            tk.Label(right_h, text=txt, font=FONTS["badge"],
                     fg=fg, bg=bg, padx=8, pady=3,
                     ).pack(side="left", padx=4)

        # ── 1) Files ──────────────────────────────────────────────────
        file_box = self._section(self, "1)  Files",
                                 fill="x", padx=20, pady=4)

        row = tk.Frame(file_box, bg=COLORS["card"])
        row.pack(fill="x")
        self._btn(row, "Select .ibw files", self.pick_files,
                  primary=True).pack(side="left")
        self._btn(row, "Choose output folder", self.pick_out_dir,
                  ).pack(side="left", padx=8)

        self.out_dir_var = tk.StringVar(value="Default: same folder as first IBW")
        tk.Label(row, textvariable=self.out_dir_var,
                 fg=COLORS["secondary"], bg=COLORS["card"],
                 font=FONTS["small"]).pack(side="left", padx=8)

        row2 = tk.Frame(file_box, bg=COLORS["card"])
        row2.pack(fill="x", pady=(6, 0))
        self._btn(row2, "Remove selected", self.remove_selected,
                  ).pack(side="left")
        self._btn(row2, "Clear list", self.clear_list,
                  danger=True).pack(side="left", padx=8)

        tk.Label(file_box,
                 text="Tip: Drag & drop .ibw files directly onto the window to add them.",
                 fg=COLORS["secondary"], bg=COLORS["card"],
                 font=FONTS["small"]).pack(anchor="w", pady=(8, 0))

        # ── 2) Options ────────────────────────────────────────────────
        opt_box = self._section(self, "2)  Options",
                                fill="x", padx=20, pady=4)

        self.plot_mode = tk.StringVar(value="overlay")
        self._opt_label(opt_box, "Plot mode:", 0)
        self._opt_radio(opt_box, "Overlay (one figure)",  self.plot_mode, "overlay",   0, 1)
        self._opt_radio(opt_box, "Separate (per file)",   self.plot_mode, "separate",  0, 2)

        self.export_mode = tk.StringVar(value="separate_csv")
        self._opt_label(opt_box, "CSV export:", 1)
        self._opt_radio(opt_box, "Separate CSV per file",    self.export_mode, "separate_csv",        1, 1)
        self._opt_radio(opt_box, "Merged CSV (horizontal)",  self.export_mode, "merged_horizontal",   1, 2)

        self.save_png_var = tk.BooleanVar(value=True)
        self._opt_check(opt_box, "Export PNG figures", self.save_png_var, 2, 1)

        self.save_homo_png_var = tk.BooleanVar(value=False)
        # 放在单独一行，避免被窗口宽度挤掉看不见
        self._opt_check(opt_box, "Export HOMO stitched PNG (EF + SECO)", self.save_homo_png_var, 5, 1)

        self.zoom_enable = tk.BooleanVar(value=True)
        self.zoom_check_btn = self._opt_check(
            opt_box, "Add two zoom panels", self.zoom_enable, 2, 3)

        # Zoom range entries
        tk.Label(opt_box, text="Zoom A (eV):", bg=COLORS["card"],
                 fg=COLORS["text"], font=FONTS["body"],
                 ).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=3)
        self.zoom_a_lo_var = tk.StringVar(value="18")
        self.zoom_a_hi_var = tk.StringVar(value="15")
        self._zoom_entry(opt_box, self.zoom_a_lo_var, 3, 1)
        tk.Label(opt_box, text="–", bg=COLORS["card"],
                 fg=COLORS["secondary"], font=FONTS["body"],
                 ).grid(row=3, column=2, sticky="w", padx=2, pady=3)
        self._zoom_entry(opt_box, self.zoom_a_hi_var, 3, 3)

        tk.Label(opt_box, text="Zoom B (eV):", bg=COLORS["card"],
                 fg=COLORS["text"], font=FONTS["body"],
                 ).grid(row=4, column=0, sticky="w", padx=(0, 8), pady=3)
        self.zoom_b_lo_var = tk.StringVar(value="-1")
        # 费米边默认用 -1~3 eV
        self.zoom_b_hi_var = tk.StringVar(value="3")
        self._zoom_entry(opt_box, self.zoom_b_lo_var, 4, 1)
        tk.Label(opt_box, text="–", bg=COLORS["card"],
                 fg=COLORS["secondary"], font=FONTS["body"],
                 ).grid(row=4, column=2, sticky="w", padx=2, pady=3)
        self._zoom_entry(opt_box, self.zoom_b_hi_var, 4, 3)

        self.zoom_hint_label = tk.Label(
            opt_box,
            text="Zoom A: SECO region  ·  Zoom B: near EF  ·  Available when spectrum starts ≥ 20 eV",
            fg=COLORS["secondary"], bg=COLORS["card"],
            font=FONTS["small"], justify="left",
        )
        self.zoom_hint_label.grid(row=6, column=0, columnspan=4,
                                  sticky="w", padx=0, pady=(4, 0))
        self.zoom_check_btn.grid_remove()
        self.zoom_hint_label.grid_remove()

        # ── 3) Actions ────────────────────────────────────────────────
        act_box = self._section(self, "3)  Actions",
                                fill="x", padx=20, pady=4)

        self._btn(act_box, "▶  Preview",        self.preview,         primary=True ).pack(side="left")
        self._btn(act_box, "⬇  Export CSV + PNG", self.export,                     ).pack(side="left", padx=8)
        # XPS 功能已拆分为独立模块，入口留在启动页
        self._btn(act_box, "⚙  XPS Peak Fitting (open module)", self._open_xps_module,            ).pack(side="left")

        # ── Main area: file list + log ────────────────────────────────
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        # File list
        left = self._section(main, "Selected Files",
                             side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(
            left, height=12,
            font=FONTS["body"],
            bg=COLORS["list_bg"], fg=COLORS["list_fg"],
            selectbackground=COLORS["list_select"],
            selectforeground=COLORS["text"],
            relief="flat", highlightthickness=0,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        lb_sb = ttk.Scrollbar(left, orient="vertical",
                              command=self.listbox.yview)
        lb_sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=lb_sb.set)

        # Log panel
        right = self._section(main, "Log",
                              side="left", fill="both", expand=True,
                              padx=(8, 0))
        log_wrap = tk.Frame(right, bg=COLORS["card"])
        log_wrap.pack(fill="both", expand=True)
        log_sb = ttk.Scrollbar(log_wrap, orient="vertical")
        log_sb.pack(side="right", fill="y")
        self.log = tk.Text(
            log_wrap, height=12,
            font=FONTS["mono"],
            bg=COLORS["list_bg"], fg=COLORS["list_fg"],
            relief="flat", highlightthickness=0,
            padx=10, pady=8,
            wrap="word",
            yscrollcommand=log_sb.set,
        )
        self.log.pack(side="left", fill="both", expand=True)
        log_sb.config(command=self.log.yview)

        # Log color tags
        self.log.tag_configure("ok",      foreground=COLORS["success"])
        self.log.tag_configure("err",     foreground=COLORS["error"])
        self.log.tag_configure("warn",    foreground=COLORS["warning"])
        self.log.tag_configure("phi",     foreground=COLORS["primary"])
        self.log.tag_configure("dim",     foreground=COLORS["secondary"])
        self.log.tag_configure("bold",    font=FONTS["section"])

        # ── Status bar ────────────────────────────────────────────────
        status_frame = tk.Frame(self, bg=COLORS["card"],
                                highlightbackground=COLORS["card_border"],
                                highlightthickness=1, height=30)
        status_frame.pack(fill="x", side="bottom", padx=20, pady=6)
        status_frame.pack_propagate(False)

        self._status_dot = tk.Label(
            status_frame, text="●", font=("Segoe UI", 11),
            fg=COLORS["success"], bg=COLORS["card"])
        self._status_dot.pack(side="left", padx=(10, 4), pady=4)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(status_frame, textvariable=self.status_var,
                 font=FONTS["small"], fg=COLORS["secondary"],
                 bg=COLORS["card"]).pack(side="left", pady=4)

        self.progress = ttk.Progressbar(status_frame,
                                        mode="indeterminate", length=120)

        self._log("Ready — select or drag & drop .ibw files to begin.", "dim")

    # ------------------------------------------------------------------ #
    #  Zoom helpers                                                        #
    # ------------------------------------------------------------------ #

    def _spectra_start_from_20ev(self):
        if not self.spectra:
            return False
        return any(float(np.max(s["x"])) >= 20.0 for s in self.spectra)

    def _update_zoom_ui(self):
        if self._spectra_start_from_20ev():
            self.zoom_check_btn.grid(row=2, column=2, sticky="w", padx=8, pady=4)
            self.zoom_hint_label.grid(row=5, column=0, columnspan=4,
                                      sticky="w", padx=0, pady=(4, 0))
        else:
            self.zoom_check_btn.grid_remove()
            self.zoom_hint_label.grid_remove()
            self.zoom_enable.set(False)

    def _get_zoom_ranges(self):
        try:
            a_lo, a_hi = float(self.zoom_a_lo_var.get()), float(self.zoom_a_hi_var.get())
            zoomA = (min(a_lo, a_hi), max(a_lo, a_hi))
        except (ValueError, TypeError):
            zoomA = (15.0, 18.0)
        try:
            b_lo, b_hi = float(self.zoom_b_lo_var.get()), float(self.zoom_b_hi_var.get())
            zoomB = (min(b_lo, b_hi), max(b_lo, b_hi))
        except (ValueError, TypeError):
            zoomB = (-1.0, 2.0)
        return zoomA, zoomB

    def _zoom_effective(self):
        return self._spectra_start_from_20ev() and self.zoom_enable.get()

    # ------------------------------------------------------------------ #
    #  Drag & drop                                                         #
    # ------------------------------------------------------------------ #

    def _setup_drag_drop(self):
        if HAS_WINDND:
            try:
                windnd.hook_dropfiles(self, func=self._on_drop_files)
            except Exception:
                pass

    def _on_drop_files(self, paths):
        if not paths:
            return
        decoded = []
        for p in paths:
            if isinstance(p, bytes):
                try:
                    p = p.decode("utf-8")
                except UnicodeDecodeError:
                    p = p.decode("gbk", errors="ignore")
            if p and p.lower().endswith(".ibw"):
                decoded.append(p)
        if decoded:
            self._add_files(decoded, replace=False)

    # ------------------------------------------------------------------ #
    #  File management                                                     #
    # ------------------------------------------------------------------ #

    def _add_files(self, paths, replace=True):
        paths = [os.path.normpath(p) for p in paths]
        if replace:
            self.files = list(paths)
        else:
            seen = set(self.files)
            for p in paths:
                if p not in seen:
                    seen.add(p)
                    self.files.append(p)
        self._refresh_listbox()
        if not self.files:
            self._set_status("Ready")
            return
        if self.out_dir is None:
            self.out_dir_var.set(f"→  {os.path.dirname(self.files[0])}")
        self._log(f"Loading {len(self.files)} file(s)…", "dim")
        self._load_spectra_async()

    def _refresh_listbox(self):
        self.listbox.delete(0, "end")
        for p in self.files:
            # Show "filename  (folder)" for readability
            base = os.path.basename(p)
            folder = os.path.basename(os.path.dirname(p))
            self.listbox.insert("end", f"  {base}  ({folder})")

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            self._log("No file selected — click a row to select first.", "dim")
            return
        for i in reversed(sel):
            self.files.pop(i)
        self._refresh_listbox()
        if not self.files:
            self.spectra = []
            self.out_dir_var.set("Default: same folder as first IBW")
            self._update_zoom_ui()
            self._log("List cleared.", "dim")
            return
        self._log(f"Reloading {len(self.files)} file(s)…", "dim")
        self._load_spectra_async()

    def clear_list(self):
        self._loader.cancel()
        self.files = []
        self.spectra = []
        self.listbox.delete(0, "end")
        self.out_dir_var.set("Default: same folder as first IBW")
        self._set_status("Ready")
        self._update_zoom_ui()
        self._log("List cleared.", "dim")

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select IBW files",
            filetypes=[("IBW files", "*.ibw"), ("All files", "*.*")],
        )
        if not paths:
            return
        self._add_files(list(paths), replace=True)

    def pick_out_dir(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if not d:
            return
        self.out_dir = d
        self.out_dir_var.set(f"→  {d}")
        self._log(f"Output folder: {d}", "dim")

    # ------------------------------------------------------------------ #
    #  Async loading                                                       #
    # ------------------------------------------------------------------ #

    def _load_spectra_async(self):
        self._set_status("Loading…")
        self.progress.pack(side="right", padx=10, pady=5)
        self.progress.start(40)
        self._loader.load(list(self.files), on_done=self._on_load_done)

    def _on_load_done(self, spectra, ok, bad, failures):
        self.spectra = spectra
        self.progress.stop()
        self.progress.pack_forget()
        self._set_status("Ready")
        for fp, err in failures:
            self._log(f"FAILED  {os.path.basename(fp)}: {err}", "err")
        tag = "ok" if bad == 0 else "warn"
        self._log(f"Loaded {ok} spectrum{'s' if ok != 1 else ''}   Failed {bad}", tag)
        self._update_zoom_ui()

    # ------------------------------------------------------------------ #
    #  Guard / helpers                                                     #
    # ------------------------------------------------------------------ #

    def ensure_ready(self):
        if not self.files:
            messagebox.showwarning("No Files",
                                   "Please select one or more .ibw files first.")
            return False
        if not self.spectra:
            messagebox.showwarning("Not Loaded",
                                   "No spectrum was loaded successfully.")
            return False
        return True

    def get_out_dir(self):
        return self.out_dir or os.path.dirname(self.files[0])

    def _log(self, msg: str, tag: str = ""):
        """向日志追加一行，tag 控制颜色：ok/err/warn/phi/dim/bold。"""
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")

    def _set_status(self, text: str):
        self.status_var.set(text)
        dot_color = {
            "Ready":       COLORS["success"],
            "Loading…":    COLORS["warning"],
            "Exporting…":  COLORS["warning"],
        }.get(text, COLORS["secondary"])
        self._status_dot.configure(fg=dot_color)

    def _log_seco_results(self, spectra, loA, hiA):
        from plots import find_seco, HV_HEI
        self._log("Work function  φ = 21.22 − SECO (eV):", "bold")
        for s in spectra:
            BE_cut, phi, aux = find_seco(
                s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
            if BE_cut is not None:
                self._log(
                    f"  {s['base']}:  SECO = {BE_cut:.2f} eV  →  φ = {phi:.2f} eV",
                    "phi")
            else:
                reason = (aux.get("reason", "unknown") if aux
                          else f"no edge in {loA}–{hiA} eV")
                self._log(f"  {s['base']}:  not found — {reason}", "warn")

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def preview(self):
        if not self.ensure_ready():
            return
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from plots import plot_overlay, plot_separate, plot_homo_stitched, HV_HEI

            z = self._zoom_effective()
            zA, zB = self._get_zoom_ranges()
            if self.plot_mode.get() == "overlay":
                fig = plot_overlay(self.spectra, zoom_enable=z, zoomA=zA, zoomB=zB)
                fig.canvas.manager.set_window_title("UPS Overlay")
                plt.show()
            else:
                figs = plot_separate(self.spectra, zoom_enable=z, zoomA=zA, zoomB=zB)
                for base, fig in figs:
                    fig.canvas.manager.set_window_title(base)
                plt.show()

            # 额外预览：HOMO stitched 图（与导出同一个勾选项）
            if self.save_homo_png_var.get():
                for s in self.spectra:
                    fig = plot_homo_stitched(s, zoomA=zA, homo_range=(-1.0, 5.0), hv=HV_HEI)
                    fig.canvas.manager.set_window_title(f"{s['base']} · HOMO stitched")
                plt.show()

            if z:
                self._log_seco_results(self.spectra, min(zA), max(zA))
            self._log("Preview done.", "ok")
        except Exception:
            self._log("Preview failed:\n" + traceback.format_exc(), "err")
            messagebox.showerror("Error", "Preview failed — check the Log.")

    def export(self):
        if not self.ensure_ready():
            return
        self._set_status("Exporting…")
        self.update_idletasks()
        out_dir = self.get_out_dir()
        os.makedirs(out_dir, exist_ok=True)
        try:
            from plots import plot_overlay, plot_separate, plot_homo_stitched, save_png, HV_HEI

            if self.export_mode.get() == "separate_csv":
                paths = export_csv_separate(self.spectra, out_dir)
                self._log(f"CSV: {len(paths)} file(s)  →  {out_dir}", "ok")
            else:
                path = export_csv_merged_horizontal(self.spectra, out_dir)
                self._log(f"Merged CSV  →  {path}", "ok")

            z = self._zoom_effective()
            zA, zB = self._get_zoom_ranges()

            if self.save_png_var.get():
                if self.plot_mode.get() == "overlay":
                    fig = plot_overlay(self.spectra, zoom_enable=z, zoomA=zA, zoomB=zB)
                    tag = get_scan_range_tag(self.spectra[0])
                    png = os.path.join(out_dir, f"UPS_overlay_{tag}.png")
                    save_png(fig, png)
                    self._log(f"PNG  →  {png}", "ok")
                else:
                    figs = plot_separate(self.spectra, zoom_enable=z, zoomA=zA, zoomB=zB)
                    for (base, fig), s in zip(figs, self.spectra):
                        tag = get_scan_range_tag(s)
                        png = os.path.join(out_dir, f"{base}_{tag}.png")
                        save_png(fig, png)
                    self._log(f"PNG: {len(figs)} figure(s)  →  {out_dir}", "ok")

            # HOMO stitched readout figure (always per spectrum)
            if self.save_homo_png_var.get():
                for s in self.spectra:
                    fig = plot_homo_stitched(s, zoomA=zA, homo_range=(-1.0, 5.0), hv=HV_HEI)
                    tag = get_scan_range_tag(s)
                    png = os.path.join(out_dir, f"{s['base']}_HOMO_{tag}.png")
                    save_png(fig, png)
                self._log(f"HOMO PNG: {len(self.spectra)} figure(s)  →  {out_dir}", "ok")

            if z:
                self._log_seco_results(self.spectra, min(zA), max(zA))

            self._set_status("Ready")
            messagebox.showinfo("Export done", f"All files saved to:\n{out_dir}")
        except Exception:
            self._set_status("Ready")
            self._log("Export failed:\n" + traceback.format_exc(), "err")
            messagebox.showerror("Error", "Export failed — check the Log.")

    def _open_xps_module(self):
        messagebox.showinfo("XPS module", "Please restart the program and choose the XPS module from the start screen.")


if __name__ == "__main__":
    try:
        UPSApp().mainloop()
    except Exception:
        print(traceback.format_exc())
        sys.exit(1)
