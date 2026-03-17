# reader.py - UPS/XPS IBW 读取（与桌面版一致）
# ============================================================
# UPS IBW 读取：从 IGOR .ibw 构建能量轴并归一化
# ============================================================

import os
import numpy as np
from igor2 import binarywave


def read_ibw_ups(file_path: str):
    """
    Read UPS spectrum from IGOR IBW.

    English:
    - sfB: start value of x-axis
    - sfA: step size (can be negative)
    - x = sfB + sfA * arange(N)
    - Sort x descending for UPS plotting (high -> low BE)
    - Normalize y to 0–1 using min-max

    中文：
    - sfB：横轴起点
    - sfA：横轴步长（可能为负）
    - x = sfB + sfA * np.arange(N)
    - UPS 画图习惯：结合能从大到小显示
    - y 使用 min-max 归一化到 0–1
    """
    w = binarywave.load(file_path)
    wave = w["wave"]

    y = np.asarray(wave["wData"]).squeeze()
    if y.ndim != 1:
        raise ValueError(f"{os.path.basename(file_path)}: not 1D wave, shape={y.shape}")

    wh = wave["wave_header"]

    start = float(wh["sfB"][0])  # x start / 起点
    step  = float(wh["sfA"][0])  # x step / 步长

    x = start + step * np.arange(len(y))

    # Sort x descending (UPS convention) / 按 BE 从大到小排序
    idx = np.argsort(x)[::-1]
    x = x[idx]
    y = y[idx]

    # Normalize to 0–1 / 归一化到 0–1
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    if (y_max - y_min) == 0:
        y_norm = y.copy()
    else:
        y_norm = (y - y_min) / (y_max - y_min)

    meta = {"sfB_start": start, "sfA_step": step, "N": len(y)}
    return x, y, y_norm, meta
