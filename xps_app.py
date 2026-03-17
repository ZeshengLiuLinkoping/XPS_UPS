import os
import traceback

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ui_theme import COLORS, FONTS, apply_ttk_theme
from file_loader import FileLoader
from fit_window import FitWindow


class XPSApp(tk.Tk):
    """
    XPS 模块主窗口：负责选择文件、加载谱、打开分峰拟合窗口。
    复用现有 FitWindow 的交互与拟合/导出逻辑。
    """

    def __init__(self):
        super().__init__()
        self.title("XPS Peak Fitting")
        self.geometry("980x680")
        self.minsize(900, 620)

        self.configure(bg=COLORS["bg"])
        self.option_add("*Font", FONTS["body"])
        self.option_add("*Background", COLORS["bg"])
        apply_ttk_theme(self)

        self.files: list[str] = []
        self.spectra: list[dict] = []
        self.out_dir: str | None = None

        self._loader = FileLoader(schedule_fn=lambda fn: self.after(0, fn))
        self._build_ui()

    # ------------------------------ UI helpers ------------------------------ #

    def _btn(self, parent, text, command, primary=False, danger=False):
        if primary:
            bg, fg, hover = COLORS["primary"], "#ffffff", COLORS["primary_hover"]
        elif danger:
            bg, fg, hover = "#fef2f2", COLORS["error"], "#fee2e2"
        else:
            bg, fg, hover = COLORS["button_bg"], COLORS["text"], COLORS["button_hover"]

        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=FONTS["body"],
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            borderwidth=0,
            highlightthickness=0,
        )
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    def _section(self, parent, title, **pack_kw):
        outer = tk.Frame(parent, bg=COLORS["card"], highlightbackground=COLORS["card_border"], highlightthickness=1)
        outer.pack(**pack_kw)
        tk.Frame(outer, bg=COLORS["primary"], width=3).pack(side="left", fill="y")
        right = tk.Frame(outer, bg=COLORS["card"])
        right.pack(side="left", fill="both", expand=True)
        title_bar = tk.Frame(right, bg=COLORS["card"])
        title_bar.pack(fill="x", padx=14, pady=(8, 4))
        tk.Label(title_bar, text=title, font=FONTS["section"], fg=COLORS["primary"], bg=COLORS["card"]).pack(
            side="left"
        )
        tk.Frame(right, bg=COLORS["divider"], height=1).pack(fill="x", padx=14)
        inner = tk.Frame(right, bg=COLORS["card"])
        inner.pack(fill="both", expand=True, padx=14, pady=(8, 10))
        return inner

    # ------------------------------ UI build ------------------------------ #

    def _build_ui(self):
        tk.Frame(self, bg=COLORS["primary"], height=3).pack(fill="x")

        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=20, pady=(12, 6))
        tk.Label(header, text="XPS Peak Fitting", font=FONTS["title"], fg=COLORS["text"], bg=COLORS["bg"]).pack(
            side="left"
        )
        tk.Label(
            header,
            text="Core-level peak deconvolution",
            font=FONTS["badge"],
            fg=COLORS["secondary"],
            bg=COLORS["button_bg"],
            padx=8,
            pady=3,
        ).pack(side="left", padx=10)

        file_box = self._section(self, "1) Files", fill="x", padx=20, pady=4)
        row = tk.Frame(file_box, bg=COLORS["card"])
        row.pack(fill="x")
        self._btn(row, "Select .ibw files", self.pick_files, primary=True).pack(side="left")
        self._btn(row, "Choose output folder", self.pick_out_dir).pack(side="left", padx=8)

        self.out_dir_var = tk.StringVar(value="Default: same folder as first IBW")
        tk.Label(row, textvariable=self.out_dir_var, fg=COLORS["secondary"], bg=COLORS["card"], font=FONTS["small"]).pack(
            side="left", padx=8
        )

        act_box = self._section(self, "2) Actions", fill="x", padx=20, pady=4)
        self._btn(act_box, "⚙  Open Peak Fitting", self.open_fit_window, primary=True).pack(side="left")
        self._btn(act_box, "Clear list", self.clear_list, danger=True).pack(side="left", padx=8)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        left = self._section(main, "Selected Files", side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(
            left,
            height=12,
            font=FONTS["body"],
            bg=COLORS["list_bg"],
            fg=COLORS["list_fg"],
            selectbackground=COLORS["list_select"],
            selectforeground=COLORS["text"],
            relief="flat",
            highlightthickness=0,
            activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        right = self._section(main, "Log", side="left", fill="both", expand=True, padx=(8, 0))
        log_wrap = tk.Frame(right, bg=COLORS["card"])
        log_wrap.pack(fill="both", expand=True)
        log_sb = ttk.Scrollbar(log_wrap, orient="vertical")
        log_sb.pack(side="right", fill="y")
        self.log = tk.Text(
            log_wrap,
            height=12,
            font=FONTS["mono"],
            bg=COLORS["list_bg"],
            fg=COLORS["list_fg"],
            relief="flat",
            highlightthickness=0,
            padx=10,
            pady=8,
            wrap="word",
            yscrollcommand=log_sb.set,
        )
        self.log.pack(side="left", fill="both", expand=True)
        log_sb.config(command=self.log.yview)

        self.log.tag_configure("ok", foreground=COLORS["success"])
        self.log.tag_configure("err", foreground=COLORS["error"])
        self.log.tag_configure("warn", foreground=COLORS["warning"])
        self.log.tag_configure("dim", foreground=COLORS["secondary"])
        self.log.tag_configure("bold", font=FONTS["section"])

    # ------------------------------ actions ------------------------------ #

    def _log(self, msg: str, tag: str = ""):
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")

    def pick_files(self):
        files = filedialog.askopenfilenames(title="Select .ibw files", filetypes=[("IGOR Binary Wave", "*.ibw")])
        if not files:
            return
        self.files = list(files)
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", os.path.basename(f))
        self._log(f"Selected {len(self.files)} file(s).", "ok")

        self._log("Loading spectra in background…", "dim")
        self._loader.load(self.files, self._on_loaded)

    def _on_loaded(self, spectra, ok_count, bad_count, failures):
        self.spectra = spectra
        self._log(f"Loaded: {ok_count}  Failed: {bad_count}", "ok" if bad_count == 0 else "warn")
        for fp, err in failures:
            self._log(f"  {os.path.basename(fp)}: {err}", "err")

    def pick_out_dir(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if not d:
            return
        self.out_dir = d
        self.out_dir_var.set(d)

    def clear_list(self):
        self.files = []
        self.spectra = []
        self.listbox.delete(0, "end")
        self._log("Cleared.", "ok")

    def get_out_dir(self):
        if self.out_dir:
            return self.out_dir
        if self.files:
            return os.path.dirname(self.files[0])
        return os.getcwd()

    def open_fit_window(self):
        if not self.spectra:
            messagebox.showwarning("Not Loaded", "Please select and load at least one .ibw file first.")
            return
        try:
            FitWindow(self, self.spectra)
        except Exception:
            self._log("Open fit window failed:\n" + traceback.format_exc(), "err")
            messagebox.showerror("Error", "Failed to open fit window. Check Log.")

