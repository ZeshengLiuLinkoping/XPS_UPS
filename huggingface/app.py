"""
UPS/XPS IBW Processor - Hugging Face Space (与桌面版 v3.1 功能同步)
上传 .ibw → 预览（分开模式显示全部图）→ 直接导出图片和 CSV（不打包 zip）
"""
import io
import os
import tempfile
import numpy as np
import matplotlib.pyplot as plt
import gradio as gr

from reader import read_ibw_ups
from plots import plot_overlay, plot_separate, save_png, find_seco, HV_HEI
from export_csv import (
    export_csv_separate,
    export_csv_merged_horizontal,
    get_scan_range_tag,
)

# 默认 Zoom 范围（与桌面版一致）
ZOOM_A_DEFAULT = (18.0, 15.0)   # SECO 区域
ZOOM_B_DEFAULT = (-1.0, 2.0)    # 费米边附近


def _parse_zoom(alo, ahi, blo, bhi):
    """从界面数值解析 Zoom A/B，无效则用默认值。返回 (zoomA, zoomB) 每项为 (lo, hi)。"""
    try:
        a_lo, a_hi = float(alo), float(ahi)
        zoomA = (min(a_lo, a_hi), max(a_lo, a_hi))
    except (ValueError, TypeError):
        zoomA = (min(ZOOM_A_DEFAULT), max(ZOOM_A_DEFAULT))
    try:
        b_lo, b_hi = float(blo), float(bhi)
        zoomB = (min(b_lo, b_hi), max(b_lo, b_hi))
    except (ValueError, TypeError):
        zoomB = (min(ZOOM_B_DEFAULT), max(ZOOM_B_DEFAULT))
    return zoomA, zoomB


def _append_work_function_msg(msg, spectra, zoomA):
    """在 msg 后追加功函数 φ = 21.22 − SECO 的文本。"""
    loA, hiA = min(zoomA), max(zoomA)
    lines = ["Work function φ = 21.22 − SECO (eV):"]
    for s in spectra:
        BE_cut, phi, _ = find_seco(s["x"], s["y_norm"], search_region=(loA, hiA), hv=HV_HEI)
        if BE_cut is not None:
            lines.append(f"  {s['base']}: SECO = {BE_cut:.2f} eV  →  φ = {phi:.2f} eV")
        else:
            lines.append(f"  {s['base']}: SECO not found in {loA}–{hiA} eV")
    return msg + "\n" + "\n".join(lines)


def load_spectra(files):
    """files: from gr.File — single path or list of paths."""
    if files is None:
        return [], ""
    if not isinstance(files, list):
        files = [files]
    paths = []
    for f in files:
        if f is None:
            continue
        path = f.name if hasattr(f, "name") else (f if isinstance(f, str) else getattr(f, "path", None))
        if path and os.path.isfile(path):
            paths.append(path)
    if not paths:
        return [], "No valid .ibw files."
    spectra = []
    errors = []
    for path in paths:
        try:
            x, y, y_norm, meta = read_ibw_ups(path)
            base = os.path.splitext(os.path.basename(path))[0]
            spectra.append({
                "file": path, "base": base,
                "x": x, "y": y, "y_norm": y_norm, "meta": meta,
            })
        except Exception as e:
            errors.append(f"{os.path.basename(path)}: {e}")
    msg = f"Loaded {len(spectra)} file(s)."
    if errors:
        msg += " Errors: " + "; ".join(errors)
    return spectra, msg


def spectra_start_from_20ev(spectra):
    if not spectra:
        return False
    return any(float(np.max(s["x"])) >= 20.0 for s in spectra)


def _fig_to_gallery_item(fig, caption):
    """把 matplotlib fig 转为 RGB 数组供 Gallery 显示，避免点开裂图。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    from PIL import Image
    img = Image.open(buf).convert("RGB")
    img.load()
    arr = np.array(img, dtype=np.uint8)
    return (arr, caption)


def run_preview(files, plot_mode, csv_mode, export_png, use_zoom,
                zoom_a_lo, zoom_a_hi, zoom_b_lo, zoom_b_hi):
    spectra, msg = load_spectra(files)
    if not spectra:
        return None, [], [], gr.update(choices=["(先点 Preview 生成图)"]), msg
    zoomA, zoomB = _parse_zoom(zoom_a_lo, zoom_a_hi, zoom_b_lo, zoom_b_hi)
    zoom_ok = spectra_start_from_20ev(spectra) and use_zoom
    plot_fig = None
    gallery_list = []
    if plot_mode == "overlay":
        plot_fig = plot_overlay(spectra, zoom_enable=zoom_ok, zoomA=zoomA, zoomB=zoomB)
        dropdown_choices = ["(Overlay 模式请看上方案图)"]
    else:
        figs = plot_separate(spectra, zoom_enable=zoom_ok, zoomA=zoomA, zoomB=zoomB)
        for base, fig in figs:
            gallery_list.append(_fig_to_gallery_item(fig, base))
        dropdown_choices = [cap for _, cap in gallery_list]
    if zoom_ok:
        msg = _append_work_function_msg(msg, spectra, zoomA)
    return plot_fig, gallery_list, gallery_list, gr.update(choices=dropdown_choices), msg


def show_large_image(gallery_state, selected_caption):
    """Separate 模式下从下拉选择后，在下方大图区显示对应谱图（避免 Gallery 点开放大不显示）。"""
    if not gallery_state or not selected_caption or str(selected_caption).strip().startswith("("):
        return None
    for img_arr, cap in gallery_state:
        if cap == selected_caption:
            return img_arr
    return None


def run_export(files, plot_mode, csv_mode, export_png, use_zoom,
               zoom_a_lo, zoom_a_hi, zoom_b_lo, zoom_b_hi):
    spectra, msg = load_spectra(files)
    if not spectra:
        return [], msg
    zoomA, zoomB = _parse_zoom(zoom_a_lo, zoom_a_hi, zoom_b_lo, zoom_b_hi)
    zoom_ok = spectra_start_from_20ev(spectra) and use_zoom
    out_dir = tempfile.mkdtemp(prefix="ups_export_")
    try:
        if csv_mode == "separate_csv":
            export_csv_separate(spectra, out_dir)
        else:
            export_csv_merged_horizontal(spectra, out_dir)
        if export_png:
            if plot_mode == "overlay":
                fig = plot_overlay(spectra, zoom_enable=zoom_ok, zoomA=zoomA, zoomB=zoomB)
                tag = get_scan_range_tag(spectra[0])
                save_png(fig, os.path.join(out_dir, f"UPS_overlay_norm_zoom_{tag}.png"))
            else:
                figs = plot_separate(spectra, zoom_enable=zoom_ok, zoomA=zoomA, zoomB=zoomB)
                for (base, fig), s in zip(figs, spectra):
                    tag = get_scan_range_tag(s)
                    save_png(fig, os.path.join(out_dir, f"{base}_{tag}_norm_zoom.png"))
        # 直接返回所有文件路径，不打包 zip；用户可逐个下载
        out_paths = [os.path.join(out_dir, name) for name in os.listdir(out_dir)]
        out_msg = "Export done. Download CSV and PNG below (click each file)."
        if zoom_ok:
            out_msg = _append_work_function_msg(out_msg, spectra, zoomA)
        return out_paths, out_msg
    except Exception as e:
        return [], f"Export failed: {e}"


def build_ui():
    with gr.Blocks(title="UPS/XPS IBW Processor", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# UPS / XPS IBW Processor")
        gr.Markdown(
            "Upload IGOR **.ibw** files (multi-select). Preview normalized spectra with **SECO / work function φ** and optional zoom panels. "
            "Export CSV + PNG. Filenames include auto-detected orbital/range (e.g. C1s, O1s). "
            "**φ = 21.22 − SECO** (He I)."
        )
        with gr.Row():
            files = gr.File(
                label="Upload .ibw files",
                file_count="multiple",
                file_types=[".ibw"],
                type="filepath",
            )
        with gr.Row():
            plot_mode = gr.Radio(
                ["overlay", "separate"],
                value="overlay",
                label="Plot mode",
                info="Overlay: one figure; Separate: one per file",
            )
            csv_mode = gr.Radio(
                ["separate_csv", "merged_horizontal"],
                value="separate_csv",
                label="CSV export",
                info="Separate CSV per file, or one merged (columns per file + empty column between files)",
            )
        with gr.Row():
            export_png = gr.Checkbox(value=True, label="Export PNG figures")
            use_zoom = gr.Checkbox(
                value=True,
                label="Add zoom panels (Zoom A & B). Only when spectrum starts from 20 eV.",
            )
        with gr.Row():
            gr.Markdown("**Zoom A (eV)** — SECO region, e.g. 18–15:")
            zoom_a_lo = gr.Number(value=18.0, label="Zoom A low", precision=2)
            zoom_a_hi = gr.Number(value=15.0, label="Zoom A high", precision=2)
            gr.Markdown("**Zoom B (eV)** — near EF, e.g. -1–2:")
            zoom_b_lo = gr.Number(value=-1.0, label="Zoom B low", precision=2)
            zoom_b_hi = gr.Number(value=2.0, label="Zoom B high", precision=2)
        with gr.Row():
            run_btn = gr.Button("Preview", variant="primary")
            export_btn = gr.Button("Export CSV + PNG")
        status = gr.Textbox(label="Status", interactive=False, lines=8)
        plot_out = gr.Plot(label="Preview (Overlay 模式直接显示在此)")
        gallery_out = gr.Gallery(label="Preview (Separate 模式：小图)", columns=3, object_fit="contain", height="auto")
        gallery_state = gr.State(value=None)
        zoom_dropdown = gr.Dropdown(
            label="Separate 模式：选一张谱图在下方放大查看（避免点小图放大不显示）",
            choices=["(先点 Preview 生成图)"],
            value=None,
        )
        large_image = gr.Image(label="放大图", type="numpy", height=400)
        download = gr.File(label="Download CSV & PNG (click each file)", file_count="multiple")

        inputs = [files, plot_mode, csv_mode, export_png, use_zoom,
                  zoom_a_lo, zoom_a_hi, zoom_b_lo, zoom_b_hi]
        run_btn.click(
            fn=run_preview,
            inputs=inputs,
            outputs=[plot_out, gallery_out, gallery_state, zoom_dropdown, status],
        )
        zoom_dropdown.change(
            fn=show_large_image,
            inputs=[gallery_state, zoom_dropdown],
            outputs=[large_image],
        )
        export_btn.click(fn=run_export, inputs=inputs, outputs=[download, status])
    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch()
