# fit_window.py
# ============================================================
# XPS 峰拟合交互窗口（Toplevel）
#
# 布局：
#   左侧固定面板 ── 谱选择 / 拟合范围 / 背景 / 峰列表 / 操作按钮
#   右侧可扩展   ── matplotlib 画布（主图 + 残差图）+ 拟合结果表格
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import numpy as np
import pandas as pd
import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.pyplot as plt

from ui_theme import COLORS, FONTS
from peak_fit import fit_xps, pseudo_voigt
from xps_chem_states import guess_core_from_range, match_chem_states


# ------------------------------------------------------------------ #
#  内部工具函数                                                         #
# ------------------------------------------------------------------ #

def _btn(parent, text, command, primary=False, danger=False, **kw):
    """统一按钮（与 app.py 保持相同风格）。"""
    if primary:
        bg, fg, hover = COLORS["primary"], "#ffffff", COLORS["primary_hover"]
    elif danger:
        bg, fg, hover = "#fef2f2", COLORS["error"], "#fee2e2"
    else:
        bg, fg, hover = COLORS["button_bg"], COLORS["text"], COLORS["button_hover"]
    # 允许调用方覆盖 padding；并且屏蔽重复 kwargs 导致的 Tk 报错
    padx = kw.pop("padx", 12)
    pady = kw.pop("pady", 5)
    b = tk.Button(parent, text=text, command=command, font=FONTS["body"],
                  bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
                  relief="flat", cursor="hand2",
                  borderwidth=0, highlightthickness=0,
                  padx=padx, pady=pady, **kw)
    b.bind("<Enter>", lambda _e: b.configure(bg=hover))
    b.bind("<Leave>", lambda _e: b.configure(bg=bg))
    return b


def _section_header(parent, title):
    """在左侧面板内画一个带分割线的小节标题。"""
    tk.Label(parent, text=title, font=FONTS["section"],
             fg=COLORS["primary"], bg=COLORS["card"]).pack(anchor="w", padx=12, pady=(10, 2))
    tk.Frame(parent, bg=COLORS["divider"], height=1).pack(fill="x", padx=12, pady=(0, 6))


# ------------------------------------------------------------------ #
#  添加峰对话框                                                         #
# ------------------------------------------------------------------ #

class _AddPeakDialog(tk.Toplevel):
    """模态对话框：输入峰中心、FWHM、η。"""

    def __init__(self, parent, default_center="", default_fwhm="1.0", default_eta="0.3"):
        super().__init__(parent)
        self.title("Add Peak")
        self.resizable(False, False)
        self.configure(bg=COLORS["card"])
        self.grab_set()
        self.result = None

        # 顶部彩条
        tk.Frame(self, bg=COLORS["primary"], height=3).pack(fill="x")

        # 在 Toplevel 内不要混用 pack/grid：外层用 pack，内容区单独用 grid
        body = tk.Frame(self, bg=COLORS["card"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)

        rows = [
            ("Center (eV):",              default_center),
            ("FWHM (eV):",                default_fwhm),
            ("η  (0 = Gauss, 1 = Lorentz):", default_eta),
        ]
        self._vars = []
        for i, (label, default) in enumerate(rows):
            tk.Label(body, text=label, bg=COLORS["card"],
                     font=FONTS["body"], fg=COLORS["text"],
                     ).grid(row=i, column=0, sticky="w", padx=(16, 8), pady=7)
            v = tk.StringVar(value=default)
            entry = tk.Entry(body, textvariable=v, width=11,
                             bg=COLORS["list_bg"], fg=COLORS["text"],
                             relief="flat", font=FONTS["body"],
                             highlightthickness=1,
                             highlightbackground=COLORS["card_border"],
                             insertbackground=COLORS["primary"])
            entry.grid(row=i, column=1, sticky="ew", padx=(0, 16), pady=7)
            self._vars.append(v)

        btn_row = tk.Frame(body, bg=COLORS["card"])
        btn_row.grid(row=len(rows), column=0, columnspan=2, pady=(4, 14))
        _btn(btn_row, "OK",     self._ok,       primary=True).pack(side="left", padx=6)
        _btn(btn_row, "Cancel", self.destroy,              ).pack(side="left", padx=6)

        self.wait_window()

    def _ok(self):
        try:
            center = float(self._vars[0].get())
            fwhm   = float(self._vars[1].get())
            eta    = float(self._vars[2].get())
            if fwhm <= 0:
                raise ValueError("FWHM 必须 > 0")
            if not (0.0 <= eta <= 1.0):
                raise ValueError("η 须在 0–1 之间")
            self.result = {"center": center, "fwhm": fwhm, "eta": eta}
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Input error", str(e), parent=self)


# ------------------------------------------------------------------ #
#  峰拟合主窗口                                                         #
# ------------------------------------------------------------------ #

class FitWindow(tk.Toplevel):
    """XPS 峰拟合窗口。"""

    _PEAK_COLORS = plt.cm.tab10(np.linspace(0, 1, 10))

    def __init__(self, parent, spectra):
        super().__init__(parent)
        self.title("XPS Peak Fitting")
        self.geometry("1140x740")
        self.minsize(940, 620)
        self.configure(bg=COLORS["bg"])

        self.spectra = spectra
        self._peak_guesses: list[dict] = []
        self._fit_result:   dict | None = None

        self._build_ui()
        self._refresh_canvas()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- #
    #  UI 构建                                                           #
    # ---------------------------------------------------------------- #

    def _build_ui(self):
        # 顶部彩条
        tk.Frame(self, bg=COLORS["primary"], height=3).pack(fill="x")

        # 标题栏
        hdr = tk.Frame(self, bg=COLORS["bg"])
        hdr.pack(fill="x", padx=16, pady=(10, 6))
        badge = tk.Frame(hdr, bg=COLORS["primary"], padx=9, pady=3)
        badge.pack(side="left")
        tk.Label(badge, text="⚙", font=("Segoe UI", 12),
                 fg="white", bg=COLORS["primary"]).pack(side="left")
        tk.Label(badge, text=" Peak Fitting", font=FONTS["section"],
                 fg="white", bg=COLORS["primary"]).pack(side="left")
        tk.Label(hdr, text="  Pseudo-Voigt  ·  Linear / Shirley Background",
                 font=FONTS["subtitle"], fg=COLORS["secondary"],
                 bg=COLORS["bg"]).pack(side="left", padx=8)

        # 主体
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # 左侧控制面板
        left = tk.Frame(body, bg=COLORS["card"], width=282,
                        highlightbackground=COLORS["card_border"],
                        highlightthickness=1)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(left, bg=COLORS["primary"], width=3).pack(side="left", fill="y")

        ctrl = tk.Frame(left, bg=COLORS["card"])
        ctrl.pack(side="left", fill="both", expand=True)

        self._build_controls(ctrl)

        # 右侧画布 + 结果
        right = tk.Frame(body, bg=COLORS["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._build_canvas(right)

    def _build_controls(self, parent):
        """左侧控制面板内容。"""
        pad = {"padx": 12, "pady": 3}

        # ── 谱选择 ──────────────────────────────────────────────────
        _section_header(parent, "Spectrum")
        self._spec_var = tk.StringVar()
        names = [s["base"] for s in self.spectra]
        self._spec_var.set(names[0] if names else "")
        cmb = ttk.Combobox(parent, textvariable=self._spec_var,
                           values=names, state="readonly", width=28)
        cmb.pack(anchor="w", **pad)
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._on_spectrum_changed())

        # ── 拟合范围 ────────────────────────────────────────────────
        _section_header(parent, "Fit Range (eV)")
        rng = tk.Frame(parent, bg=COLORS["card"])
        rng.pack(anchor="w", **pad)
        self._range_lo = tk.StringVar()
        self._range_hi = tk.StringVar()
        e_kw = dict(bg=COLORS["list_bg"], fg=COLORS["text"], relief="flat",
                    font=FONTS["body"], width=7,
                    highlightthickness=1, highlightbackground=COLORS["card_border"],
                    insertbackground=COLORS["primary"])
        tk.Entry(rng, textvariable=self._range_lo, **e_kw).pack(side="left")
        tk.Label(rng, text="  –  ", bg=COLORS["card"],
                 fg=COLORS["secondary"], font=FONTS["body"]).pack(side="left")
        tk.Entry(rng, textvariable=self._range_hi, **e_kw).pack(side="left")
        _btn(rng, "↺", self._auto_range, padx=6, pady=3).pack(side="left", padx=(6, 0))

        # ── 背景类型 ────────────────────────────────────────────────
        _section_header(parent, "Background")
        self._bg_var = tk.StringVar(value="shirley")
        bg_row = tk.Frame(parent, bg=COLORS["card"])
        bg_row.pack(anchor="w", **pad)
        for val, label in [("none", "None"), ("linear", "Linear"), ("shirley", "Shirley")]:
            tk.Radiobutton(bg_row, text=label, variable=self._bg_var, value=val,
                           bg=COLORS["card"], fg=COLORS["text"],
                           selectcolor=COLORS["primary_light"],
                           activebackground=COLORS["card"],
                           activeforeground=COLORS["primary"],
                           font=FONTS["body"], cursor="hand2",
                           ).pack(side="left", padx=3)

        # ── 峰列表 ──────────────────────────────────────────────────
        _section_header(parent, "Peaks")
        tree_fr = tk.Frame(parent, bg=COLORS["card"])
        tree_fr.pack(fill="x", padx=12, pady=(0, 4))
        cols = ("center", "fwhm", "eta")
        self._peak_tree = ttk.Treeview(tree_fr, columns=cols,
                                       show="headings", height=6)
        self._peak_tree.heading("center", text="Center (eV)")
        self._peak_tree.heading("fwhm",   text="FWHM (eV)")
        self._peak_tree.heading("eta",    text="η")
        for c in cols:
            self._peak_tree.column(c, width=72, anchor="center")
        self._peak_tree.pack(fill="x")
        self._peak_tree.bind("<Double-1>", lambda _e: self._edit_peak())
        self._peak_tree.bind("<Return>",   lambda _e: self._edit_peak())

        pb_row = tk.Frame(parent, bg=COLORS["card"])
        pb_row.pack(anchor="w", padx=12, pady=(2, 0))
        _btn(pb_row, "+ Add", self._add_peak   ).pack(side="left", padx=(0, 6))
        _btn(pb_row, "Edit",  self._edit_peak  ).pack(side="left", padx=(0, 6))
        _btn(pb_row, "Remove", self._remove_peak, danger=True).pack(side="left")

        # ── 化学态/官能团标注 ───────────────────────────────────────
        _section_header(parent, "Chemical state hints")
        self._assign_enable = tk.BooleanVar(value=True)
        tk.Checkbutton(
            parent,
            text="Suggest chemical state / functional group",
            variable=self._assign_enable,
            bg=COLORS["card"],
            fg=COLORS["text"],
            selectcolor=COLORS["primary_light"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["primary"],
            font=FONTS["body"],
            cursor="hand2",
            command=self._refresh_canvas,
        ).pack(anchor="w", padx=12, pady=(0, 2))

        row = tk.Frame(parent, bg=COLORS["card"])
        row.pack(anchor="w", padx=12, pady=(0, 6))

        tk.Label(row, text="Core:", bg=COLORS["card"], fg=COLORS["secondary"], font=FONTS["small"]).pack(side="left")
        self._assign_core = tk.StringVar(value="Auto")
        core_cmb = ttk.Combobox(
            row,
            textvariable=self._assign_core,
            values=["Auto", "C1s", "O1s", "N1s", "S2p", "F1s"],
            state="readonly",
            width=6,
        )
        core_cmb.pack(side="left", padx=(6, 10))
        core_cmb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_canvas())

        tk.Label(row, text="Tolerance (eV):", bg=COLORS["card"], fg=COLORS["secondary"], font=FONTS["small"]).pack(
            side="left"
        )
        self._assign_tol = tk.StringVar(value="1.0")
        tk.Entry(
            row,
            textvariable=self._assign_tol,
            width=5,
            bg=COLORS["list_bg"],
            fg=COLORS["text"],
            relief="flat",
            font=FONTS["body"],
            highlightthickness=1,
            highlightbackground=COLORS["card_border"],
            insertbackground=COLORS["primary"],
        ).pack(side="left", padx=(6, 10))

        tk.Label(row, text="Top N:", bg=COLORS["card"], fg=COLORS["secondary"], font=FONTS["small"]).pack(side="left")
        self._assign_topn = tk.StringVar(value="1")
        tk.Entry(
            row,
            textvariable=self._assign_topn,
            width=3,
            bg=COLORS["list_bg"],
            fg=COLORS["text"],
            relief="flat",
            font=FONTS["body"],
            highlightthickness=1,
            highlightbackground=COLORS["card_border"],
            insertbackground=COLORS["primary"],
        ).pack(side="left", padx=(6, 0))

        # ── 操作按钮 ────────────────────────────────────────────────
        _section_header(parent, "Actions")
        _btn(parent, "▶  Fit", self._run_fit,
             primary=True).pack(fill="x", padx=12, pady=(0, 4))
        _btn(parent, "⬇  Export CSV", self._export_csv,
             ).pack(fill="x", padx=12, pady=(0, 4))
        _btn(parent, "✕  Clear Fit", self._clear_fit,
             danger=True).pack(fill="x", padx=12, pady=(0, 8))

        self._auto_range()

    def _build_canvas(self, parent):
        """右侧 matplotlib 画布 + 结果表格。"""
        # matplotlib 图（主 + 残差）
        self._fig, (self._ax, self._ax_res) = plt.subplots(
            2, 1, figsize=(7.2, 5.2), dpi=110,
            gridspec_kw={"height_ratios": [4, 1], "hspace": 0.06},
        )
        self._fig.patch.set_facecolor(COLORS["bg"])
        for ax in (self._ax, self._ax_res):
            ax.set_facecolor(COLORS["list_bg"])

        canvas_frame = tk.Frame(parent, bg=COLORS["bg"],
                                highlightbackground=COLORS["card_border"],
                                highlightthickness=1)
        canvas_frame.pack(fill="both", expand=True)

        self._canvas = FigureCanvasTkAgg(self._fig, master=canvas_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        tb_frame = tk.Frame(parent, bg=COLORS["bg"])
        tb_frame.pack(fill="x")
        NavigationToolbar2Tk(self._canvas, tb_frame)

        # 结果区标题
        res_hdr = tk.Frame(parent, bg=COLORS["bg"])
        res_hdr.pack(fill="x", pady=(8, 2))
        tk.Label(res_hdr, text="Fit Results", font=FONTS["section"],
                 fg=COLORS["primary"], bg=COLORS["bg"]).pack(side="left")
        self._r2_var = tk.StringVar(value="")
        tk.Label(res_hdr, textvariable=self._r2_var, font=FONTS["body"],
                 fg=COLORS["success"], bg=COLORS["bg"]).pack(side="right", padx=4)

        # 结果 Treeview
        res_cols = ("peak", "center", "fwhm", "eta", "area")
        self._res_tree = ttk.Treeview(parent, columns=res_cols,
                                      show="headings", height=4)
        headers = {
            "peak":   "#",
            "center": "Center ±σ (eV)",
            "fwhm":   "FWHM ±σ (eV)",
            "eta":    "η ±σ",
            "area":   "Area (a.u.)",
        }
        widths = {"peak": 32, "center": 145, "fwhm": 125, "eta": 95, "area": 90}
        for c in res_cols:
            self._res_tree.heading(c, text=headers[c])
            self._res_tree.column(c, width=widths[c], anchor="center")
        self._res_tree.pack(fill="x")

    # ---------------------------------------------------------------- #
    #  Helpers                                                           #
    # ---------------------------------------------------------------- #

    def _current_spectrum(self):
        name = self._spec_var.get()
        for s in self.spectra:
            if s["base"] == name:
                return s
        return self.spectra[0] if self.spectra else None

    def _auto_range(self):
        s = self._current_spectrum()
        if s is None:
            return
        self._range_lo.set(f"{float(np.min(s['x'])):.2f}")
        self._range_hi.set(f"{float(np.max(s['x'])):.2f}")

    def _parse_range(self):
        try:
            a, b = float(self._range_lo.get()), float(self._range_hi.get())
            return (min(a, b), max(a, b))
        except ValueError:
            return None

    def _on_spectrum_changed(self):
        self._auto_range()
        self._fit_result = None
        self._refresh_canvas()

    # ---------------------------------------------------------------- #
    #  峰管理                                                            #
    # ---------------------------------------------------------------- #

    def _add_peak(self):
        rng = self._parse_range()
        default = f"{(rng[0] + rng[1]) / 2:.2f}" if rng else ""
        dlg = _AddPeakDialog(self, default_center=default)
        if dlg.result:
            self._peak_guesses.append(dlg.result)
            pg = dlg.result
            self._peak_tree.insert("", "end", values=(
                f"{pg['center']:.2f}",
                f"{pg['fwhm']:.2f}",
                f"{pg['eta']:.2f}",
            ))
            self._fit_result = None
            self._refresh_canvas()

    def _edit_peak(self):
        sel = self._peak_tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self._peak_tree.index(item)
        if not (0 <= idx < len(self._peak_guesses)):
            return

        pg0 = self._peak_guesses[idx]
        dlg = _AddPeakDialog(
            self,
            default_center=f"{pg0.get('center', 0.0):.2f}",
            default_fwhm=f"{pg0.get('fwhm', 1.0):.2f}",
            default_eta=f"{pg0.get('eta', 0.3):.2f}",
        )
        if not dlg.result:
            return

        self._peak_guesses[idx] = dlg.result
        pg = dlg.result
        self._peak_tree.item(item, values=(
            f"{pg['center']:.2f}",
            f"{pg['fwhm']:.2f}",
            f"{pg['eta']:.2f}",
        ))
        self._fit_result = None
        self._refresh_canvas()

    def _remove_peak(self):
        sel = self._peak_tree.selection()
        if not sel:
            return
        for item in reversed(sel):
            idx = self._peak_tree.index(item)
            self._peak_tree.delete(item)
            if 0 <= idx < len(self._peak_guesses):
                self._peak_guesses.pop(idx)
        self._fit_result = None
        self._refresh_canvas()

    def _clear_fit(self):
        self._fit_result = None
        for row in self._res_tree.get_children():
            self._res_tree.delete(row)
        self._r2_var.set("")
        self._refresh_canvas()

    # ---------------------------------------------------------------- #
    #  画布绘制                                                           #
    # ---------------------------------------------------------------- #

    def _refresh_canvas(self):
        self._ax.cla()
        self._ax_res.cla()

        s = self._current_spectrum()
        if s is None:
            self._canvas.draw_idle()
            return

        rng = self._parse_range()
        x_all, y_all = s["x"], s["y"]
        if rng:
            lo, hi = rng
            mask = (x_all >= lo) & (x_all <= hi)
            x_d, y_d = x_all[mask], y_all[mask]
        else:
            x_d, y_d = x_all, y_all

        idx = np.argsort(x_d)
        x_d, y_d = x_d[idx], y_d[idx]

        colors = self._PEAK_COLORS
        # 数据散点
        self._ax.plot(x_d, y_d, "o", ms=2.2, color=COLORS["secondary"],
                      label="Data", zorder=2, rasterized=True)

        if self._fit_result and self._fit_result.get("success"):
            r  = self._fit_result
            xf = r["x_fit"]
            rng = self._parse_range()
            core_auto = guess_core_from_range(*rng) if rng else None

            # 背景（灰虚线）
            self._ax.plot(xf, r["y_bg"], "--", color="#9ca3af",
                          lw=1.3, label="Background", zorder=3)

            # 各峰（填色 + 轮廓）
            for i, (py, fp) in enumerate(zip(r["peaks_y"], r["params"])):
                c = colors[i % 10]
                self._ax.fill_between(xf, r["y_bg"], r["y_bg"] + py,
                                      alpha=0.20, color=c)
                peak_label = f"Peak {i + 1}: {fp['center']:.2f} eV"

                # 自动峰归属（在峰顶附近标注）
                if getattr(self, "_assign_enable", None) and self._assign_enable.get():
                    try:
                        tol = float(self._assign_tol.get())
                    except Exception:
                        tol = 1.0
                    try:
                        topn = int(float(self._assign_topn.get()))
                    except Exception:
                        topn = 1
                    core_sel = getattr(self, "_assign_core", None)
                    core = core_sel.get() if core_sel else "Auto"
                    if core == "Auto":
                        core = core_auto or "C1s"
                    hits = match_chem_states(core, fp["center"], tol_ev=tol, top_n=topn)
                    if hits:
                        labels = []
                        for st, _d in hits:
                            labels.append(f"{st.label}")
                        txt = " / ".join(labels)
                        peak_label = f"Peak {i + 1}: {core} · {txt}"

                self._ax.plot(
                    xf,
                    r["y_bg"] + py,
                    lw=1.4,
                    color=c,
                    label=peak_label,
                )

            # 总拟合（主色实线）
            self._ax.plot(xf, r["y_bg"] + r["y_total_fit"],
                          color=COLORS["error"], lw=1.9,
                          label="Total fit", zorder=5)

            # 残差
            residuals = r["y_corrected"] - r["y_total_fit"]
            self._ax_res.plot(xf, residuals, ".", ms=1.8,
                              color=COLORS["secondary"], rasterized=True)
            self._ax_res.axhline(0, color=COLORS["error"], lw=0.9)
            self._ax_res.set_ylabel("Residual", fontsize=8, color=COLORS["secondary"])
            self._ax_res.set_xlim(max(xf), min(xf))
            self._ax_res.set_visible(True)
        else:
            # 仅显示峰猜测竖线
            for i, pg in enumerate(self._peak_guesses):
                self._ax.axvline(pg["center"], color=colors[i % 10],
                                 alpha=0.5, linestyle="--", lw=1.3,
                                 label=f"Guess {i + 1}:  {pg['center']:.2f} eV")
            self._ax_res.set_visible(False)

        # 主图样式
        self._ax.set_xlim(max(x_d), min(x_d))
        self._ax.set_xlabel("Binding Energy (eV)", fontsize=10)
        self._ax.set_ylabel("Intensity (counts)",  fontsize=10)
        self._ax.set_title(s["base"], fontsize=10, fontweight="bold",
                           color=COLORS["text"])
        self._ax.legend(fontsize=8, frameon=True,
                        framealpha=0.9, edgecolor=COLORS["divider"])
        self._ax.grid(alpha=0.18, color=COLORS["divider"])

        self._ax_res.grid(alpha=0.15, color=COLORS["divider"])
        self._ax_res.tick_params(labelsize=7, colors=COLORS["secondary"])

        self._fig.tight_layout(pad=1.2)
        self._canvas.draw_idle()

    # ---------------------------------------------------------------- #
    #  拟合                                                              #
    # ---------------------------------------------------------------- #

    def _run_fit(self):
        s = self._current_spectrum()
        if s is None:
            messagebox.showwarning("No spectrum",
                                   "Please load IBW files in the main window first.",
                                   parent=self)
            return
        if not self._peak_guesses:
            messagebox.showwarning("No peaks",
                                   "Click [+ Add] to add at least one peak guess.",
                                   parent=self)
            return

        result = fit_xps(
            s["x"], s["y"],
            peak_guesses=self._peak_guesses,
            bg_type=self._bg_var.get(),
            fit_range=self._parse_range(),
        )
        self._fit_result = result

        if not result["success"]:
            messagebox.showerror("Fit failed", result["message"], parent=self)
            return

        self._populate_results(result)
        self._refresh_canvas()

    def _populate_results(self, r):
        for row in self._res_tree.get_children():
            self._res_tree.delete(row)
        xf = r["x_fit"]
        for i, (fp, fe) in enumerate(zip(r["params"], r["errors"])):
            area = float(np.trapz(
                pseudo_voigt(xf, fp["center"], fp["amplitude"],
                             fp["fwhm"], fp["eta"]), xf))
            self._res_tree.insert("", "end", values=(
                f"{i + 1}",
                f"{fp['center']:.3f} ±{fe['center']:.3f}",
                f"{fp['fwhm']:.3f} ±{fe['fwhm']:.3f}",
                f"{fp['eta']:.3f} ±{fe['eta']:.3f}",
                f"{abs(area):.2f}",
            ))
        self._r2_var.set(f"R²  =  {r['r_squared']:.5f}")

    # ---------------------------------------------------------------- #
    #  导出                                                              #
    # ---------------------------------------------------------------- #

    def _export_csv(self):
        if self._fit_result is None or not self._fit_result.get("success"):
            messagebox.showwarning("No fit",
                                   "Run a fit first, then export.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Save Fit Results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"{self._spec_var.get()}_fit.csv",
            parent=self,
        )
        if not path:
            return
        r = self._fit_result
        xf = r["x_fit"]
        df_dict = {
            "BE_eV":      xf,
            "Intensity":  r["y_raw"],
            "Background": r["y_bg"],
            "Corrected":  r["y_corrected"],
            "TotalFit":   r["y_total_fit"],
        }
        for i, py in enumerate(r["peaks_y"]):
            df_dict[f"Peak{i + 1}"] = py
        pd.DataFrame(df_dict).to_csv(path, index=False)
        with open(path, "a", newline="", encoding="utf-8") as f:
            f.write("\nFit Parameters\n")
            f.write("Peak,Center_eV,Center_err,FWHM_eV,FWHM_err,"
                    "eta,eta_err,Amplitude,Amp_err,Area\n")
            for i, (fp, fe) in enumerate(zip(r["params"], r["errors"])):
                area = float(np.trapz(
                    pseudo_voigt(xf, fp["center"], fp["amplitude"],
                                 fp["fwhm"], fp["eta"]), xf))
                f.write(f"{i+1},"
                        f"{fp['center']:.4f},{fe['center']:.4f},"
                        f"{fp['fwhm']:.4f},{fe['fwhm']:.4f},"
                        f"{fp['eta']:.4f},{fe['eta']:.4f},"
                        f"{fp['amplitude']:.4f},{fe['amplitude']:.4f},"
                        f"{abs(area):.4f}\n")
            f.write(f"\nBackground,{self._bg_var.get()}\n")
            f.write(f"R_squared,{r['r_squared']:.6f}\n")
        messagebox.showinfo("Saved",
                            f"Fit results exported to:\n{path}", parent=self)

    # ---------------------------------------------------------------- #
    #  清理                                                              #
    # ---------------------------------------------------------------- #

    def _on_close(self):
        plt.close(self._fig)
        self.destroy()
