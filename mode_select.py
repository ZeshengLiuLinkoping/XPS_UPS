import tkinter as tk
from tkinter import messagebox

from ui_theme import COLORS, FONTS, apply_ttk_theme


class ModeSelectApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Select Module")
        self.geometry("520x320")
        self.minsize(520, 320)
        self.configure(bg=COLORS["bg"])
        self.option_add("*Font", FONTS["body"])
        apply_ttk_theme(self)

        self.selected_mode: str | None = None  # "ups" | "xps"

        self._build_ui()

    def _build_ui(self):
        tk.Frame(self, bg=COLORS["primary"], height=3).pack(fill="x")

        wrap = tk.Frame(self, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=22, pady=18)

        tk.Label(
            wrap,
            text="Choose a module",
            font=FONTS["title"],
            fg=COLORS["text"],
            bg=COLORS["bg"],
        ).pack(anchor="w")

        tk.Label(
            wrap,
            text="UPS: work function / SECO / HOMO readout\nXPS: peak fitting (deconvolution)",
            font=FONTS["body"],
            fg=COLORS["secondary"],
            bg=COLORS["bg"],
            justify="left",
        ).pack(anchor="w", pady=(6, 14))

        cards = tk.Frame(wrap, bg=COLORS["bg"])
        cards.pack(fill="both", expand=True)

        self._card(
            cards,
            title="UPS module",
            desc="Work function (φ), SECO detection,\nUPS plots & export, HOMO stitched plot.",
            primary=True,
            command=lambda: self._choose("ups"),
        ).pack(side="left", fill="both", expand=True, padx=(0, 10))

        self._card(
            cards,
            title="XPS module",
            desc="Peak fitting window for core-level spectra.\nAdd/Edit peaks, fit background, export fit.",
            primary=False,
            command=lambda: self._choose("xps"),
        ).pack(side="left", fill="both", expand=True, padx=(10, 0))

        tk.Label(
            wrap,
            text="Tip: you can always restart to switch modules.",
            font=FONTS["small"],
            fg=COLORS["secondary"],
            bg=COLORS["bg"],
        ).pack(anchor="w", pady=(14, 0))

    def _card(self, parent, title: str, desc: str, primary: bool, command):
        outer = tk.Frame(
            parent,
            bg=COLORS["card"],
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
        )

        tk.Frame(outer, bg=COLORS["primary"] if primary else COLORS["divider"], height=4).pack(fill="x")

        body = tk.Frame(outer, bg=COLORS["card"])
        body.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(body, text=title, font=FONTS["section"], fg=COLORS["primary"], bg=COLORS["card"]).pack(anchor="w")
        tk.Label(body, text=desc, font=FONTS["body"], fg=COLORS["secondary"], bg=COLORS["card"], justify="left").pack(
            anchor="w", pady=(8, 12)
        )

        btn = tk.Button(
            body,
            text="Open",
            command=command,
            font=FONTS["body"],
            bg=COLORS["primary"] if primary else COLORS["button_bg"],
            fg="#ffffff" if primary else COLORS["text"],
            activebackground=COLORS["primary_hover"] if primary else COLORS["button_hover"],
            activeforeground="#ffffff" if primary else COLORS["text"],
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=8,
            borderwidth=0,
            highlightthickness=0,
        )
        btn.pack(anchor="w")

        return outer

    def _choose(self, mode: str):
        if mode not in ("ups", "xps"):
            messagebox.showerror("Error", f"Unknown mode: {mode}")
            return
        self.selected_mode = mode
        self.destroy()

