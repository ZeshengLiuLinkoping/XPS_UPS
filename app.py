# app.py
# ============================================================
# UPS IBW Processor - 图形界面 (v3.1)
# 依赖：reader, plots, export_csv
# 可选：windnd（拖拽添加文件，Windows）
# ============================================================

import os
import sys
import traceback
import threading

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from reader import read_ibw_ups
from plots import plot_overlay, plot_separate, save_png, find_seco, HV_HEI
from export_csv import (
    export_csv_separate,
    export_csv_merged_horizontal,
    get_scan_range_tag,
)

try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

# ---------- 界面配色与字体 ----------
COLORS = {
    "bg": "#f5f6f8",           # 窗口背景
    "card": "#ffffff",         # 卡片/区块背景
    "card_border": "#e1e4e8",  # 卡片边框色
    "primary": "#0d7377",      # 主色（按钮、标题点缀）
    "primary_hover": "#0a5c5f",
    "secondary": "#5f6368",    # 次要文字
    "text": "#202124",         # 主文字
    "accent": "#32e0c4",       # 强调色（可选）
    "button_bg": "#e8eaed",    # 次要按钮背景
    "list_bg": "#fafafa",      # 列表/日志背景
    "list_fg": "#202124",
    "list_select": "#cce5e0",  # 选中行背景
}
FONTS = {
    "title": ("Segoe UI", 16, "bold"),
    "subtitle": ("Segoe UI", 10),
    "section": ("Segoe UI", 10, "bold"),
    "body": ("Segoe UI", 10),
}


class UPSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UPS IBW Processor v3.1")
        self.geometry("1000x680")
        self.minsize(940, 640)

        self.configure(bg=COLORS["bg"])
        self.option_add("*Font", FONTS["body"])
        self.option_add("*Background", COLORS["bg"])

        self.files = []
        self.spectra = []
        self.out_dir = None

        self.zoomA = (18.0, 15.0)   # SECO region (defaults)
        self.zoomB = (-1.0, 2.0)    # near EF/onset

        self._build_ui()
        self._setup_drag_drop()

    def _styled_btn(self, parent, text, command, width, primary=False):
        bg = COLORS["primary"] if primary else COLORS["button_bg"]
        fg = "#ffffff" if primary else COLORS["text"]
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            font=FONTS["body"],
            bg=bg,
            fg=fg,
            activebackground=COLORS["primary_hover"] if primary else "#d2d4d6",
            activeforeground=fg,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            borderwidth=0,
            highlightthickness=0,
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=COLORS["primary_hover"] if primary else "#d2d4d6"))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def _styled_frame(self, parent, text, **pack_kw):
        f = tk.LabelFrame(
            parent,
            text=text,
            font=FONTS["section"],
            fg=COLORS["primary"],
            bg=COLORS["card"],
            padx=14,
            pady=10,
            relief="flat",
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
        )
        f.pack(**pack_kw)
        return f

    def _build_ui(self):
        # ---------------- Header ----------------
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=20, pady=(16, 10))

        tk.Label(
            header,
            text="UPS IBW Processor",
            font=FONTS["title"],
            fg=COLORS["text"],
            bg=COLORS["bg"],
        ).pack(side="left")

        tk.Label(
            header,
            text="v3.1  ·  Load → Preview → Export",
            font=FONTS["subtitle"],
            fg=COLORS["secondary"],
            bg=COLORS["bg"],
        ).pack(side="right")

        # ---------------- Files ----------------
        file_box = self._styled_frame(self, "1)  Files", fill="x", padx=20, pady=6)

        row = tk.Frame(file_box, bg=COLORS["card"])
        row.pack(fill="x")

        self._styled_btn(row, "Select .ibw files (multi)", self.pick_files, 26, primary=True).pack(side="left")
        self._styled_btn(row, "Choose output folder", self.pick_out_dir, 20).pack(side="left", padx=10)

        self.out_dir_var = tk.StringVar(value="Default: same folder as the first IBW")
        tk.Label(
            row,
            textvariable=self.out_dir_var,
            fg=COLORS["secondary"],
            bg=COLORS["card"],
            font=FONTS["subtitle"],
        ).pack(side="left", padx=10)

        row2 = tk.Frame(file_box, bg=COLORS["card"])
        row2.pack(fill="x", pady=(6, 0))
        self._styled_btn(row2, "Remove selected", self.remove_selected, 16).pack(side="left")
        self._styled_btn(row2, "Clear list", self.clear_list, 12).pack(side="left", padx=8)

        tk.Label(
            file_box,
            text="Tip: Output folder defaults to the first IBW's folder. Drag & drop .ibw files here to add.",
            fg=COLORS["secondary"],
            bg=COLORS["card"],
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # ---------------- Options ----------------
        opt_box = self._styled_frame(self, "2)  Options", fill="x", padx=20, pady=6)

        self.plot_mode = tk.StringVar(value="overlay")
        self._opt_label(opt_box, "Plot mode:", 0)
        self._opt_radio(opt_box, "Overlay (one figure)", self.plot_mode, "overlay", 0, 1)
        self._opt_radio(opt_box, "Separate (per file)", self.plot_mode, "separate", 0, 2)

        self.export_mode = tk.StringVar(value="separate_csv")
        self._opt_label(opt_box, "CSV export:", 1)
        self._opt_radio(opt_box, "Separate CSV per file", self.export_mode, "separate_csv", 1, 1)
        self._opt_radio(opt_box, "Merged CSV (horizontal)", self.export_mode, "merged_horizontal", 1, 2)

        self.save_png_var = tk.BooleanVar(value=True)
        self._opt_check(opt_box, "Export PNG figures", self.save_png_var, 2, 1)

        self.zoom_enable = tk.BooleanVar(value=True)
        self.zoom_check_btn = self._opt_check(
            opt_box, "Add TWO zoom panels", self.zoom_enable, 2, 2
        )
        # Custom Zoom range (eV)
        tk.Label(opt_box, text="Zoom A (eV):", bg=COLORS["card"], fg=COLORS["text"], font=FONTS["body"]).grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.zoom_a_lo_var = tk.StringVar(value="18")
        self.zoom_a_hi_var = tk.StringVar(value="15")
        self._zoom_entry(opt_box, self.zoom_a_lo_var, 3, 1)
        tk.Label(opt_box, text="to", bg=COLORS["card"], fg=COLORS["secondary"], font=FONTS["body"]).grid(row=3, column=2, sticky="w", padx=2, pady=4)
        self._zoom_entry(opt_box, self.zoom_a_hi_var, 3, 3)
        tk.Label(opt_box, text="Zoom B (eV):", bg=COLORS["card"], fg=COLORS["text"], font=FONTS["body"]).grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self.zoom_b_lo_var = tk.StringVar(value="-1")
        self.zoom_b_hi_var = tk.StringVar(value="2")
        self._zoom_entry(opt_box, self.zoom_b_lo_var, 4, 1)
        tk.Label(opt_box, text="to", bg=COLORS["card"], fg=COLORS["secondary"], font=FONTS["body"]).grid(row=4, column=2, sticky="w", padx=2, pady=4)
        self._zoom_entry(opt_box, self.zoom_b_hi_var, 4, 3)
        self.zoom_hint_label = tk.Label(
            opt_box,
            text="Zoom A: SECO region. Zoom B: near EF. Shown only when spectrum starts from 20 eV.",
            fg=COLORS["secondary"],
            bg=COLORS["card"],
            font=("Segoe UI", 9),
            justify="left",
        )
        self.zoom_hint_label.grid(row=5, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 0))
        self.zoom_check_btn.grid_remove()
        self.zoom_hint_label.grid_remove()

        # ---------------- Actions ----------------
        act_box = self._styled_frame(self, "3)  Actions", fill="x", padx=20, pady=6)

        self._styled_btn(act_box, "Preview plots", self.preview, 18, primary=True).pack(side="left")
        self._styled_btn(act_box, "Export CSV (+PNG)", self.export, 20).pack(side="left", padx=10)

        # ---------------- Main area: files + log ----------------
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=20, pady=12)

        left = self._styled_frame(main, "Selected files", side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(
            left,
            height=14,
            font=FONTS["body"],
            bg=COLORS["list_bg"],
            fg=COLORS["list_fg"],
            selectbackground=COLORS["list_select"],
            selectforeground=COLORS["text"],
            relief="flat",
            highlightthickness=0,
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(left, orient="vertical", command=self.listbox.yview, bg=COLORS["card_border"])
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        right = self._styled_frame(main, "Log", side="left", fill="both", expand=True, padx=(12, 0))
        self.log = tk.Text(
            right,
            height=16,
            font=("Consolas", 10),
            bg=COLORS["list_bg"],
            fg=COLORS["list_fg"],
            relief="flat",
            highlightthickness=0,
            padx=8,
            pady=8,
        )
        self.log.pack(fill="both", expand=True)

        # ---------------- Status bar ----------------
        status_frame = tk.Frame(self, bg=COLORS["card_border"], height=28)
        status_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 8))
        status_frame.pack_propagate(False)
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=FONTS["subtitle"],
            fg=COLORS["secondary"],
            bg=COLORS["card_border"],
        ).pack(side="left", padx=8, pady=4)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=120)
        # progress 仅在加载时 pack 显示，见 _load_spectra_async / _on_load_done

        self._log("Ready. Step 1: Select IBW files or drag & drop .ibw here.")

    def _opt_label(self, parent, text, row):
        tk.Label(
            parent,
            text=text,
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=FONTS["body"],
        ).grid(row=row, column=0, sticky="w", padx=8, pady=5)

    def _opt_radio(self, parent, text, var, value, row, col):
        tk.Radiobutton(
            parent,
            text=text,
            variable=var,
            value=value,
            bg=COLORS["card"],
            fg=COLORS["text"],
            selectcolor=COLORS["card"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["primary"],
            font=FONTS["body"],
            cursor="hand2",
        ).grid(row=row, column=col, sticky="w", padx=8, pady=5)

    def _opt_check(self, parent, text, var, row, col):
        cb = tk.Checkbutton(
            parent,
            text=text,
            variable=var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            selectcolor=COLORS["list_select"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["text"],
            font=FONTS["body"],
            cursor="hand2",
        )
        cb.grid(row=row, column=col, sticky="w", padx=8, pady=5)
        return cb

    def _zoom_entry(self, parent, textvar, row, col):
        e = tk.Entry(
            parent, textvariable=textvar, width=6,
            bg=COLORS["list_bg"], fg=COLORS["text"], relief="flat",
            font=FONTS["body"], highlightthickness=1, highlightbackground=COLORS["card_border"],
        )
        e.grid(row=row, column=col, sticky="w", padx=2, pady=4)
        return e

    def _log(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _spectra_start_from_20ev(self):
        """仅当至少有一条谱的结合能范围包含 20 eV（高 BE 端 ≥20 eV）时返回 True。"""
        if not self.spectra:
            return False
        return any(float(np.max(s["x"])) >= 20.0 for s in self.spectra)

    def _update_zoom_ui(self):
        """根据当前加载的谱是否从 20 eV 开始，显示或隐藏放大区选项。"""
        if self._spectra_start_from_20ev():
            self.zoom_check_btn.grid(row=2, column=2, sticky="w", padx=8, pady=5)
            self.zoom_hint_label.grid(row=5, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 0))
        else:
            self.zoom_check_btn.grid_remove()
            self.zoom_hint_label.grid_remove()
            self.zoom_enable.set(False)

    def _setup_drag_drop(self):
        if HAS_WINDND:
            try:
                windnd.hook_dropfiles(self, func=self._on_drop_files)
            except Exception:
                pass

    def _on_drop_files(self, paths):
        if not paths:
            return
        # windnd may pass bytes or str paths
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
        self.listbox.delete(0, "end")
        for p in self.files:
            self.listbox.insert("end", p)
        if not self.files:
            self.status_var.set("Ready")
            return
        if self.out_dir is None:
            self.out_dir_var.set(f"Default: {os.path.dirname(self.files[0])}")
        self._log(f"Loading {len(self.files)} file(s)...")
        self._load_spectra_async()

    def remove_selected(self):
        sel = list(self.listbox.curselection())
        if not sel:
            self._log("No item selected. Select one or more files to remove.")
            return
        for i in reversed(sel):
            self.files.pop(i)
        self.listbox.delete(0, "end")
        for p in self.files:
            self.listbox.insert("end", p)
        if not self.files:
            self.spectra = []
            self.out_dir_var.set("Default: same folder as the first IBW")
            self._update_zoom_ui()
            self._log("List cleared.")
            return
        self._log(f"Reloading {len(self.files)} file(s)...")
        self._load_spectra_async()

    def clear_list(self):
        self.files = []
        self.spectra = []
        self.listbox.delete(0, "end")
        self.out_dir_var.set("Default: same folder as the first IBW")
        self.status_var.set("Ready")
        self._update_zoom_ui()
        self._log("List cleared. Select or drag & drop .ibw files to add.")

    def pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select UPS IBW files",
            filetypes=[("IBW files", "*.ibw")]
        )
        if not paths:
            self._log("No files selected.")
            return
        self._add_files(list(paths), replace=True)

    def pick_out_dir(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if not d:
            self._log("Output folder not changed.")
            return
        self.out_dir = d
        self.out_dir_var.set(d)
        self._log(f"Output folder set to: {d}")

    def _load_spectra_body(self):
        """在后台线程中执行，返回 (spectra_list, ok_count, bad_count, failures: [(path, err_str), ...])。"""
        spectra = []
        failures = []
        for fp in self.files:
            try:
                x, y, y_norm, meta = read_ibw_ups(fp)
                spectra.append({
                    "file": fp,
                    "dir": os.path.dirname(fp),
                    "base": os.path.splitext(os.path.basename(fp))[0],
                    "x": x, "y": y, "y_norm": y_norm,
                    "meta": meta
                })
            except Exception as e:
                failures.append((fp, str(e)))
        ok = len(spectra)
        bad = len(failures)
        return spectra, ok, bad, failures

    def _on_load_done(self, result):
        spectra, ok, bad, failures = result
        self.spectra = spectra
        self.progress.stop()
        self.progress.pack_forget()
        self.status_var.set("Ready")
        for fp, err in failures:
            self._log(f"FAILED: {fp}\n  {err}")
        self._log(f"Loaded: {ok} | Failed: {bad}")
        self._update_zoom_ui()

    def _load_spectra_async(self):
        self.status_var.set("Loading...")
        self.progress.pack(side="right", padx=8, pady=4)
        self.progress.start(50)

        def run():
            result = self._load_spectra_body()
            self.after(0, lambda: self._on_load_done(result))

        threading.Thread(target=run, daemon=True).start()

    def ensure_ready(self):
        if not self.files:
            messagebox.showwarning("Warning", "Please select one or more .ibw files first.")
            return False
        if not self.spectra:
            messagebox.showwarning("Warning", "No spectrum was loaded successfully.")
            return False
        return True

    def get_out_dir(self):
        if self.out_dir:
            return self.out_dir
        return os.path.dirname(self.files[0])

    def _get_zoom_ranges(self):
        """从输入框读取 Zoom A/B 范围（eV），解析失败则用默认值。返回 (zoomA, zoomB) 每项为 (lo, hi)。"""
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
        """仅当谱从 20 eV 开始且用户勾选时启用放大区。"""
        return self._spectra_start_from_20ev() and self.zoom_enable.get()

    def preview(self):
        if not self.ensure_ready():
            return
        try:
            z = self._zoom_effective()
            zoomA, zoomB = self._get_zoom_ranges()
            if self.plot_mode.get() == "overlay":
                fig = plot_overlay(self.spectra, zoom_enable=z, zoomA=zoomA, zoomB=zoomB)
                fig.canvas.manager.set_window_title("UPS Overlay (Normalized + Zoom)")
                plt.show()
            else:
                figs = plot_separate(self.spectra, zoom_enable=z, zoomA=zoomA, zoomB=zoomB)
                for base, fig in figs:
                    fig.canvas.manager.set_window_title(base)
                plt.show()

            if z:
                loA, hiA = min(zoomA), max(zoomA)
                self._log("Work function φ = 21.22 − SECO (eV):")
                for s in self.spectra:
                    BE_cut, phi, _ = find_seco(s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
                    if BE_cut is not None:
                        self._log(f"  {s['base']}: SECO = {BE_cut:.2f} eV  →  φ = {phi:.2f} eV")
                    else:
                        self._log(f"  {s['base']}: SECO not found in {loA}–{hiA} eV")
            self._log("Preview done.")
        except Exception:
            self._log("Preview failed:\n" + traceback.format_exc())
            messagebox.showerror("Error", "Preview failed. Check the Log for details.")

    def export(self):
        if not self.ensure_ready():
            return

        self.status_var.set("Exporting...")
        self.update_idletasks()
        out_dir = self.get_out_dir()
        os.makedirs(out_dir, exist_ok=True)

        try:
            if self.export_mode.get() == "separate_csv":
                paths = export_csv_separate(self.spectra, out_dir)
                self._log(f"CSV exported: {len(paths)} file(s) -> {out_dir}")
            else:
                path = export_csv_merged_horizontal(self.spectra, out_dir)
                self._log(f"Merged CSV (horizontal) exported: {path}")

            if self.save_png_var.get():
                z = self._zoom_effective()
                zoomA, zoomB = self._get_zoom_ranges()
                if self.plot_mode.get() == "overlay":
                    fig = plot_overlay(self.spectra, zoom_enable=z, zoomA=zoomA, zoomB=zoomB)
                    tag = get_scan_range_tag(self.spectra[0])
                    png = os.path.join(out_dir, f"UPS_overlay_norm_zoom_{tag}.png")
                    save_png(fig, png)
                    self._log(f"PNG exported: {png}")
                else:
                    figs = plot_separate(self.spectra, zoom_enable=z, zoomA=zoomA, zoomB=zoomB)
                    count = 0
                    for (base, fig), s in zip(figs, self.spectra):
                        tag = get_scan_range_tag(s)
                        png = os.path.join(out_dir, f"{base}_{tag}_norm_zoom.png")
                        save_png(fig, png)
                        count += 1
                    self._log(f"PNG exported: {count} figure(s) -> {out_dir}")
                if z:
                    loA, hiA = min(zoomA), max(zoomA)
                    self._log("Work function φ = 21.22 − SECO (eV):")
                    for s in self.spectra:
                        BE_cut, phi, _ = find_seco(s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
                        if BE_cut is not None:
                            self._log(f"  {s['base']}: SECO = {BE_cut:.2f} eV  →  φ = {phi:.2f} eV")

            self.status_var.set("Ready")
            messagebox.showinfo("Done", f"Export finished.\n\nFolder:\n{out_dir}")
        except Exception:
            self.status_var.set("Ready")
            self._log("Export failed:\n" + traceback.format_exc())
            messagebox.showerror("Error", "Export failed. Check the Log for details.")


if __name__ == "__main__":
    try:
        UPSApp().mainloop()
    except Exception:
        print(traceback.format_exc())
        sys.exit(1)
