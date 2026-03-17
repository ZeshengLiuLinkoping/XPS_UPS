# ui_theme.py
# ============================================================
# UPS 工具 UI 配色、字体与 TTK 主题
# ============================================================

from tkinter import ttk

# ── 配色（基于 Tailwind CSS 色板，科研风）────────────────────
COLORS = {
    # 背景层
    "bg":            "#f0f2f5",   # 主窗口背景（微蓝灰）
    "card":          "#ffffff",   # 卡片/区块
    "card_border":   "#dde1e7",   # 卡片边框

    # 主色 - 青蓝（专业、科研感）
    "primary":       "#0e7490",   # 主操作色 (cyan-700)
    "primary_hover": "#0c6275",   # 悬停加深
    "primary_light": "#ecfeff",   # 极浅青，用于徽章/标签背景

    # 文字
    "text":          "#111827",   # 主文字（近黑，更清晰）
    "secondary":     "#6b7280",   # 次要文字（灰）

    # 语义色（用于 log 彩色标注）
    "success":       "#16a34a",   # 绿：加载成功、导出完成
    "error":         "#dc2626",   # 红：失败、错误
    "warning":       "#d97706",   # 琥珀：加载中、导出中

    # 控件
    "button_bg":     "#e5e7eb",   # 次要按钮背景
    "button_hover":  "#d1d5db",   # 次要按钮悬停

    # 列表/输入框
    "list_bg":       "#f9fafb",
    "list_fg":       "#111827",
    "list_select":   "#cffafe",   # 选中行（浅青）

    # 分割线
    "divider":       "#e5e7eb",
}

# ── 字体 ────────────────────────────────────────────────────
FONTS = {
    "title":    ("Segoe UI", 15, "bold"),
    "subtitle": ("Segoe UI", 9),
    "section":  ("Segoe UI", 10, "bold"),
    "body":     ("Segoe UI", 10),
    "mono":     ("Consolas", 10),
    "small":    ("Segoe UI", 9),
    "badge":    ("Segoe UI", 9, "bold"),
}


def apply_ttk_theme(root):
    """将 TTK 控件（Treeview、Combobox、Progressbar）统一为与 COLORS 匹配的风格。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")   # clam 是自定义性最好的基础主题
    except Exception:
        pass

    # ── Treeview ──────────────────────────────────────────
    style.configure("Treeview",
        background=COLORS["list_bg"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["list_bg"],
        rowheight=24,
        font=FONTS["body"],
        borderwidth=0,
        relief="flat",
    )
    style.configure("Treeview.Heading",
        background=COLORS["divider"],
        foreground=COLORS["secondary"],
        font=FONTS["section"],
        relief="flat",
        padding=(6, 4),
    )
    style.map("Treeview",
        background=[("selected", COLORS["list_select"])],
        foreground=[("selected", COLORS["text"])],
    )
    style.map("Treeview.Heading",
        background=[("active", COLORS["card_border"])],
        relief=[("active", "flat")],
    )

    # ── Progressbar ────────────────────────────────────────
    style.configure("TProgressbar",
        background=COLORS["primary"],
        troughcolor=COLORS["divider"],
        thickness=4,
        borderwidth=0,
    )

    # ── Combobox ───────────────────────────────────────────
    style.configure("TCombobox",
        fieldbackground=COLORS["list_bg"],
        background=COLORS["card_border"],
        foreground=COLORS["text"],
        selectbackground=COLORS["list_select"],
        selectforeground=COLORS["text"],
        arrowcolor=COLORS["secondary"],
        font=FONTS["body"],
        padding=(4, 2),
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", COLORS["list_bg"])],
        selectbackground=[("readonly", COLORS["list_select"])],
        arrowcolor=[("active", COLORS["primary"])],
    )

    # ── Scrollbar ──────────────────────────────────────────
    style.configure("Vertical.TScrollbar",
        background=COLORS["divider"],
        arrowcolor=COLORS["secondary"],
        troughcolor=COLORS["list_bg"],
        borderwidth=0,
        relief="flat",
        width=10,
    )
    style.map("Vertical.TScrollbar",
        background=[("active", COLORS["card_border"])],
    )
