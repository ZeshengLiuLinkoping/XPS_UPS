# export_csv.py
# ============================================================
# UPS CSV 导出：按文件单独 / 横向合并
# 输出文件名包含扫描轨道/能量范围信息（根据数据范围推断）
# ============================================================

import os
import numpy as np
import pandas as pd

# 常见 XPS 轨道典型结合能范围 (eV)：用于根据扫描范围自动识别轨道名
# 格式 (轨道名, 范围低, 范围高)；匹配时取谱中心落在范围内的轨道，多选时选轨道中心最接近谱中心的
_XPS_ORBITAL_RANGES = [
    # 低 BE
    ("Ta4f", 18, 30),
    ("Hf4f", 12, 20),
    ("W4f", 28, 38),
    ("Au4f", 80, 96),
    ("Pt4f", 68, 80),
    ("Ir4f", 58, 68),
    ("Br3d", 65, 72),
    ("Se3d", 52, 60),
    ("As3d", 40, 48),
    ("Ga3d", 16, 22),
    ("Zn2p", 1016, 1028),
    ("Cu2p", 925, 960),
    ("Ni2p", 848, 862),
    ("Co2p", 775, 788),
    ("Fe2p", 702, 728),
    ("Mn2p", 635, 648),
    ("Cr2p", 572, 582),
    ("V2p", 512, 522),
    ("Ti2p", 452, 468),
    ("Ca2p", 344, 352),
    ("K2p", 290, 298),
    ("Ru3d", 278, 286),   # 与 C1s 重叠，中心更近的会优先
    ("C1s", 276, 300),
    ("Cl2p", 195, 205),
    ("Pb4f", 134, 144),
    ("P2p", 126, 136),
    ("S2p", 158, 172),
    ("Si2p", 96, 106),
    ("Al2p", 70, 78),
    ("Ag3d", 363, 378),
    ("Pd3d", 332, 342),
    ("Sn3d", 482, 494),
    ("In3d", 440, 452),
    ("Sb3d", 525, 535),
    ("Te3d", 568, 582),
    ("I3d", 616, 632),
    ("Ce3d", 878, 918),
    ("La3d", 830, 840),
    ("Ba3d", 776, 788),
    ("Sr3d", 130, 138),
    ("Y3d", 153, 162),
    ("Zr3d", 176, 186),
    ("Nb3d", 203, 212),
    ("Mo3d", 223, 238),
    ("Rh3d", 304, 314),
    ("Cd3d", 402, 412),
    ("B1s", 184, 194),
    ("N1s", 392, 408),
    ("O1s", 522, 542),
    ("F1s", 678, 695),
    ("Na1s", 1068, 1076),
    ("Mg1s", 1298, 1310),
    ("Ga2p", 1112, 1122),
]


def get_scan_range_tag(spectrum):
    """
    根据谱的扫描范围（结合能 min/max）自动识别轨道并生成命名标签。
    若谱中心落在某轨道范围内则返回该轨道名+扫描范围；多轨道重叠时选轨道中心最接近谱中心的。
    否则返回 BE 范围，如 BE120-135。
    例如: "C1s_284-292", "O1s_528-536", "S2p_162-168"
    """
    x = spectrum["x"]
    be_min = float(np.min(x))
    be_max = float(np.max(x))
    center = (be_min + be_max) / 2.0
    range_str = f"{be_min:.0f}-{be_max:.0f}"

    candidates = []
    for orb_name, low, high in _XPS_ORBITAL_RANGES:
        if low <= center <= high:
            orb_center = (low + high) / 2.0
            candidates.append((abs(center - orb_center), orb_name))
    if candidates:
        candidates.sort(key=lambda t: t[0])
        orb_name = candidates[0][1]
        return f"{orb_name}_{range_str}"
    return f"BE{range_str}"


def export_csv_separate(spectra, out_dir):
    """
    Export one CSV per spectrum.
    每条谱导出一个 CSV（含 raw + norm），文件名中加入该谱的扫描轨道/范围标签。
    """
    paths = []
    for s in spectra:
        tag = get_scan_range_tag(s)
        df = pd.DataFrame({
            "BindingEnergy_eV": s["x"],
            "Intensity": s["y"],
            "Normalized_Intensity": s["y_norm"],
        })
        path = os.path.join(out_dir, f"{s['base']}_{tag}_with_raw_and_norm.csv")
        df.to_csv(path, index=False)
        paths.append(path)
    return paths


def export_csv_merged_horizontal(spectra, out_dir):
    """
    Export ONE merged CSV: 按文件顺序横向拼接，每个文件保留自己的 3 列（BE、raw、norm），
    每两个文件之间插入一列空列作为间隔。行数按最长文件补齐，不足处为空。

    Output columns (example for 2 files A, B):
    A_BE, A_raw, A_norm, (空), B_BE, B_raw, B_norm, (空), ...
    """
    max_len = max(len(s["x"]) for s in spectra)
    sep_col_name = ""  # 间隔列列名留空

    parts = []
    for i, s in enumerate(spectra):
        n = len(s["x"])
        pad = max_len - n
        # 该文件的 3 列：横坐标、原始强度、归一化强度
        col_be = np.concatenate([np.asarray(s["x"]).ravel(), [np.nan] * pad])
        col_raw = np.concatenate([np.asarray(s["y"]).ravel(), [np.nan] * pad])
        col_norm = np.concatenate([np.asarray(s["y_norm"]).ravel(), [np.nan] * pad])
        base = s["base"]
        parts.append(pd.DataFrame({
            f"{base}_BE": col_be,
            f"{base}_raw": col_raw,
            f"{base}_norm": col_norm,
        }))
        # 每两个文件之间加一列空列（最后一组后不加）
        if i < len(spectra) - 1:
            parts.append(pd.DataFrame({sep_col_name: [np.nan] * max_len}))

    merged = pd.concat(parts, axis=1)
    tag = get_scan_range_tag(spectra[0])
    path = os.path.join(out_dir, f"UPS_merged_horizontal_{tag}.csv")
    merged.to_csv(path, index=False)
    return path
