# plots.py - UPS/XPS 绘图（与桌面版一致，HF 使用 Agg 后端）
# ============================================================
# UPS 绘图：叠加/分开、双 zoom 面板、SECO/功函数、保存 PNG
# ============================================================

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

# He I 光子能量 (eV)，功函数 φ = HV_HEI - BE_cutoff
HV_HEI = 21.22


def find_seco(x, y_norm, search_region=(15.0, 18.0), hv=HV_HEI):
    """
    在给定 BE 范围内找二次电子截止边 (SECO)，并计算功函数 φ = hv - BE_cutoff。
    正确做法：在上升沿最陡处做切线，取切线与基线的交点作为 SECO。

    x, y_norm: 结合能 (eV) 与归一化强度。
    search_region: (lo, hi) eV。
    返回 (BE_cutoff, work_function, aux)；
    aux 为 None 或 dict(x0, y0, slope, y_baseline, lo, hi)，用于在主图上画切线与基线。
    """
    lo, hi = min(search_region), max(search_region)
    mask = (x >= lo) & (x <= hi)
    if not np.any(mask) or np.sum(mask) < 5:
        return None, None, None
    xr = np.asarray(x[mask], dtype=float)
    yr = np.asarray(y_norm[mask], dtype=float)
    idx = np.argsort(xr)
    xr = xr[idx]
    yr = yr[idx]
    grad = np.gradient(yr, xr)
    i_edge = np.argmin(grad)
    x0 = float(xr[i_edge])
    y0 = float(yr[i_edge])
    m = float(grad[i_edge])
    y_baseline = float(np.min(yr))
    if abs(m) < 1e-10:
        BE_cutoff = x0
    else:
        BE_cutoff = x0 + (y_baseline - y0) / m
    BE_cutoff = float(np.clip(BE_cutoff, lo, hi))
    work_function = hv - BE_cutoff
    aux = {"x0": x0, "y0": y0, "slope": m, "y_baseline": y_baseline, "lo": lo, "hi": hi}
    return BE_cutoff, work_function, aux


def _draw_seco_on_main_ax(ax, BE_cutoff, work_function, aux, label=None, color="C1", line_offset=0):
    """
    在 UPS 主图（全谱，20 eV 起始）上画出：短基线、短切线、功函数标注（不画交点竖线）。
    """
    if aux is None:
        return
    lo, hi = aux["lo"], aux["hi"]
    x0, y0 = aux["x0"], aux["y0"]
    m = aux["slope"]
    y_baseline = aux["y_baseline"]
    dx_short = 0.2
    x_lo = max(lo, BE_cutoff - dx_short)
    x_hi = min(hi, BE_cutoff + dx_short)
    ax.hlines(y_baseline, x_lo, x_hi, colors=color, linestyles="-", linewidth=1.0, alpha=0.85, zorder=4)
    x_tan = np.linspace(x_lo, x_hi, 20)
    y_tan = y0 + m * (x_tan - x0)
    y_tan = np.maximum(y_tan, 0.0)
    ax.plot(x_tan, y_tan, color=color, linestyle="-", linewidth=1.0, alpha=0.85, zorder=4)
    ylim = ax.get_ylim()
    y_pos = ylim[1] - (0.06 + 0.10 * line_offset) * (ylim[1] - ylim[0])
    text = f"φ = {work_function:.2f} eV"
    if label:
        text = f"{label}: {text}"
    ax.text(BE_cutoff, y_pos, text, fontsize=9, color=color, ha="center", va="top",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.9), zorder=6)


def add_zoom_inset(ax, x_left, x_right, loc="upper right", width="38%", height="38%"):
    lo = min(x_left, x_right)
    hi = max(x_left, x_right)
    axins = inset_axes(ax, width=width, height=height, loc=loc, borderpad=1.2)
    for line in ax.lines:
        axins.plot(line.get_xdata(), line.get_ydata(),
                   lw=max(1.0, float(line.get_linewidth())))
    axins.set_xlim(hi, lo)
    y_vals = []
    for line in ax.lines:
        xdata = np.asarray(line.get_xdata())
        ydata = np.asarray(line.get_ydata())
        mask = (xdata >= lo) & (xdata <= hi)
        if np.any(mask):
            y_vals.append(ydata[mask])
    if y_vals:
        y_all = np.concatenate(y_vals)
        y0 = float(np.nanmin(y_all))
        y1 = float(np.nanmax(y_all))
        pad = 0.05 * (y1 - y0) if (y1 - y0) != 0 else 0.05
        axins.set_ylim(y0 - pad, y1 + pad)
    axins.grid(alpha=0.2)
    axins.tick_params(labelsize=8)
    try:
        mark_inset(ax, axins, loc1=2, loc2=4, fc="none", ec="0.4")
    except Exception:
        pass
    return axins


def plot_overlay(spectra, zoom_enable=True, zoomA=(18.0, 15.0), zoomB=(-1.0, 2.0)):
    """叠加多条谱于一张图；仅当 zoom_enable 为 True 时右侧显示 18–15 eV、-1–2 eV 两块 zoom。"""
    all_x_min = min(np.min(s["x"]) for s in spectra)
    all_x_max = max(np.max(s["x"]) for s in spectra)

    if zoom_enable:
        fig = plt.figure(figsize=(12, 5.5), dpi=140)
        gs = GridSpec(2, 2, width_ratios=[3, 1], height_ratios=[1, 1])
        ax_main = fig.add_subplot(gs[:, 0])
        ax_zoom1 = fig.add_subplot(gs[0, 1])
        ax_zoom2 = fig.add_subplot(gs[1, 1])
    else:
        fig = plt.figure(figsize=(8, 5), dpi=140)
        ax_main = fig.add_subplot(111)

    for s in spectra:
        ax_main.plot(s["x"], s["y_norm"], lw=1.3, label=s["base"])
    ax_main.set_xlim(all_x_max, all_x_min)
    ax_main.set_xlabel("Binding Energy (eV)")
    ax_main.set_ylabel("Normalized Intensity (0–1)")
    ax_main.grid(alpha=0.25)
    ax_main.legend(frameon=False, fontsize=8)

    if zoom_enable:
        loA, hiA = min(zoomA), max(zoomA)
        colors = plt.cm.tab10(np.linspace(0, 1, max(len(spectra), 1)))
        for i, s in enumerate(spectra):
            BE_cut, phi, aux = find_seco(s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
            if BE_cut is not None and aux is not None:
                _draw_seco_on_main_ax(ax_main, BE_cut, phi, aux, label=s["base"], color=colors[i % 10], line_offset=i)

        for s in spectra:
            ax_zoom1.plot(s["x"], s["y_norm"], lw=1.2)
        ax_zoom1.set_xlim(hiA, loA)
        ax_zoom1.set_title("Zoom 18–15 eV", fontsize=10)
        ax_zoom1.grid(alpha=0.2)
        y_vals = []
        for s in spectra:
            mask = (s["x"] >= loA) & (s["x"] <= hiA)
            if np.any(mask):
                y_vals.append(s["y_norm"][mask])
        if y_vals:
            y = np.concatenate(y_vals)
            ax_zoom1.set_ylim(np.min(y), np.max(y) * 1.05)

        loB, hiB = min(zoomB), max(zoomB)
        for s in spectra:
            ax_zoom2.plot(s["x"], s["y_norm"], lw=1.2)
        ax_zoom2.set_xlim(hiB, loB)
        ax_zoom2.set_title("Zoom -1–2 eV", fontsize=10)
        ax_zoom2.grid(alpha=0.2)
        y_vals = []
        for s in spectra:
            mask = (s["x"] >= loB) & (s["x"] <= hiB)
            if np.any(mask):
                y_vals.append(s["y_norm"][mask])
        if y_vals:
            y = np.concatenate(y_vals)
            ax_zoom2.set_ylim(np.min(y), np.max(y) * 1.05)

    fig.tight_layout()
    return fig


def plot_separate(spectra, zoom_enable=True, zoomA=(18.0, 15.0), zoomB=(-1.0, 2.0)):
    """每条谱一张图。zoom_enable 为 True 时每张图 3 面板：左全谱，右上 18–15 eV，右下 -1–2 eV。"""
    figs = []
    loA, hiA = min(zoomA), max(zoomA)
    loB, hiB = min(zoomB), max(zoomB)

    for s in spectra:
        if zoom_enable:
            fig = plt.figure(figsize=(10.2, 5.6), dpi=140)
            gs = GridSpec(2, 2, width_ratios=[3, 1], height_ratios=[1, 1])
            ax_main = fig.add_subplot(gs[:, 0])
            ax_z1 = fig.add_subplot(gs[0, 1])
            ax_z2 = fig.add_subplot(gs[1, 1])
        else:
            fig = plt.figure(figsize=(7, 5), dpi=140)
            ax_main = fig.add_subplot(111)

        ax_main.plot(s["x"], s["y_norm"], lw=1.4)
        ax_main.set_xlim(np.max(s["x"]), np.min(s["x"]))
        ax_main.set_xlabel("Binding Energy (eV)")
        ax_main.set_ylabel("Normalized Intensity (0–1)")
        ax_main.set_title(s["base"])
        ax_main.grid(alpha=0.25)

        if zoom_enable:
            BE_cut, phi, aux = find_seco(s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
            if BE_cut is not None and aux is not None:
                _draw_seco_on_main_ax(ax_main, BE_cut, phi, aux, color="C1")

            ax_z1.plot(s["x"], s["y_norm"], lw=1.2)
            ax_z1.set_xlim(hiA, loA)
            ax_z1.set_title("Zoom 18–15 eV", fontsize=10)
            ax_z1.grid(alpha=0.2)
            mA = (s["x"] >= loA) & (s["x"] <= hiA)
            if np.any(mA):
                yA = s["y_norm"][mA]
                y0, y1 = float(np.min(yA)), float(np.max(yA))
                pad = 0.08 * (y1 - y0) if (y1 - y0) != 0 else 0.08
                ax_z1.set_ylim(y0 - pad, y1 + pad)

            ax_z2.plot(s["x"], s["y_norm"], lw=1.2)
            ax_z2.set_xlim(hiB, loB)
            ax_z2.set_title("Zoom -1–2 eV", fontsize=10)
            ax_z2.grid(alpha=0.2)
            mB = (s["x"] >= loB) & (s["x"] <= hiB)
            if np.any(mB):
                yB = s["y_norm"][mB]
                y0, y1 = float(np.min(yB)), float(np.max(yB))
                pad = 0.08 * (y1 - y0) if (y1 - y0) != 0 else 0.08
                ax_z2.set_ylim(y0 - pad, y1 + pad)

        fig.tight_layout()
        figs.append((s["base"], fig))

    return figs


def save_png(fig, path):
    """保存图为 PNG 并关闭 figure。"""
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path
